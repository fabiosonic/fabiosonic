"""Envio automático de WhatsApp pela Evolution API, com as travas que reduzem
o risco de bloqueio do número.

O que bloqueia número é, nesta ordem: destinatário que denuncia ou bloqueia,
volume alto para quem nunca conversou com você, texto repetido e falha em
série. As travas atacam essas causas (mecânica inspirada no
kobie3717/baileys-antiban, com tetos bem menores porque aqui todo envio é
primeiro contato):

- rampa de aquecimento: o teto diário cresce devagar a partir do 1º envio;
- intervalo aleatório longo entre envios e teto por hora;
- só em horário comercial de dia útil;
- número conferido antes (existe no WhatsApp?) e texto único por empresa;
- monitor de risco: falha de envio, 401/403 e queda de conexão somam pontos;
  ao passar do limite o motor PARA sozinho e só volta por decisão humana;
- guarda de resposta: muita mensagem sem resposta = número sendo ignorado
  ou marcado; o motor para;
- pedido de saída tratado na hora, sem humano.

Nenhuma trava garante que o número não será bloqueado: o WhatsApp proíbe
mensagem automatizada a frio em qualquer volume.
"""
from __future__ import annotations

import json
import random
import re
import unicodedata
from datetime import date, datetime, timedelta

import requests

from . import base as B
from . import fila

PADRAO = {
    "rampa": [5, 5, 8, 8, 10, 12, 15, 15, 18, 20],  # teto por dia de uso do número; depois vale teto_dia
    "teto_dia": 20,
    "max_por_hora": 4,
    "intervalo_min": [9, 22],          # minutos entre um envio e o próximo, sorteado
    "risco_pausa": 60,
    "resposta_minima": 0.05,           # abaixo disso, com amostra suficiente, o motor para
    "amostra_resposta": 20,
    "dias_sem_resposta": 7,
}
SAIDA_RE = re.compile(
    r"\b(remov\w*|descadastr\w*|sair|pare|parar|stop|spam|denunci\w*|bloque\w*|"
    r"n[aã]o (me )?(mande|envie|enviem|mandem|perturbe|incomode)\w*|n[aã]o (quero|tenho interesse)|sem interesse)\b", re.I)


def opcoes(cfg: dict) -> dict:
    return {**PADRAO, **cfg.get("whatsapp", {})}


# ------------------------------------------------------------------ Evolution API
class Evolution:
    def __init__(self, cfg: dict, http=requests):
        e = cfg["evolution"]
        self.url, self.instancia, self.http = e["url"].rstrip("/"), e["instancia"], http
        self.cab = {"apikey": e["apikey"], "Content-Type": "application/json"}

    def conectado(self) -> bool:
        r = self.http.get(f"{self.url}/instance/connectionState/{self.instancia}", headers=self.cab, timeout=20)
        r.raise_for_status()
        return r.json().get("instance", {}).get("state") == "open"

    def existe(self, numero: str) -> bool:
        r = self.http.post(f"{self.url}/chat/whatsappNumbers/{self.instancia}", headers=self.cab,
                           json={"numbers": ["55" + numero]}, timeout=30)
        r.raise_for_status()
        dados = r.json()
        itens = dados.get("numbers", []) if isinstance(dados, dict) else dados
        return bool(itens) and bool(itens[0].get("exists"))

    def enviar(self, numero: str, texto: str) -> int:
        """Devolve o status HTTP. O corpo mudou entre versões da Evolution
        (texto dentro de `textMessage` ou direto em `text`); se a primeira forma
        der 400, tenta a outra uma vez."""
        alvo = f"{self.url}/message/sendText/{self.instancia}"
        for corpo in ({"number": "55" + numero, "textMessage": {"text": texto}, "linkPreview": False},
                      {"number": "55" + numero, "text": texto, "linkPreview": False}):
            r = self.http.post(alvo, headers=self.cab, json=corpo, timeout=60)
            if r.status_code != 400:
                break
        return r.status_code


    def configurar_webhook(self, url: str) -> int:
        """Aponta o webhook da instância para o servidor de prospecção. Como no envio,
        o corpo varia entre versões (campos soltos ou dentro de `webhook`)."""
        dados = {"enabled": True, "url": url, "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE"], "base64": False}
        for corpo in (dados, {"webhook": dados}):
            r = self.http.post(f"{self.url}/webhook/set/{self.instancia}", headers=self.cab, json=corpo, timeout=30)
            if r.status_code != 400:
                break
        return r.status_code


# ------------------------------------------------------------------ estado do motor
def ler_estado(base: B.Base) -> dict:
    arq = base.pasta / "estado.json"
    padrao = {"pausado": False, "motivo": "", "risco": 0, "primeiro_envio": "", "proximo_envio": "",
              "quedas": 0, "eventos": []}
    return {**padrao, **(json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {})}


def salvar_estado(base: B.Base, est: dict) -> None:
    est["eventos"] = est["eventos"][-200:]
    (base.pasta / "estado.json").write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


def evento(est: dict, tipo: str, detalhe: str, agora: datetime | None = None) -> None:
    est["eventos"].append({"quando": (agora or datetime.now(fila.FUSO)).strftime("%d/%m %H:%M"),
                           "tipo": tipo, "detalhe": detalhe})


def pausar(est: dict, motivo: str, agora: datetime | None = None) -> None:
    est["pausado"], est["motivo"] = True, motivo
    evento(est, "pausa", motivo, agora)


def teto_hoje(cfg: dict, est: dict, hoje: date) -> int:
    op = opcoes(cfg)
    if not est["primeiro_envio"]:
        return min(op["rampa"][0], op["teto_dia"])
    dia = max(0, (hoje - date.fromisoformat(est["primeiro_envio"])).days)
    return min(op["rampa"][dia] if dia < len(op["rampa"]) else op["teto_dia"], op["teto_dia"])


def taxa_resposta(base: B.Base, hoje: date, dias: int = 3) -> tuple[int, int]:
    """(maduros, respondidos): envios com pelo menos `dias` dias e quantos tiveram resposta humana."""
    limite = (hoje - timedelta(days=dias)).isoformat()
    maduros = [l for l in base.leads if l["canal_usado"] == "whatsapp" and l["data_1"] and l["data_1"] <= limite]
    return len(maduros), sum(1 for l in maduros if l["resultado"] not in ("", "sem_resposta"))


# ------------------------------------------------------------------ um passo do motor
def passo(cfg: dict, base: B.Base, api: Evolution, agora: datetime | None = None, sorteio=random.uniform) -> str:
    """Envia no máximo UMA mensagem. Chamado a cada minuto pelo servidor."""
    agora = agora or datetime.now(fila.FUSO)
    op, est = opcoes(cfg), ler_estado(base)
    try:
        return _passo(cfg, base, api, agora, op, est, sorteio)
    finally:
        salvar_estado(base, est)


def _passo(cfg, base, api, agora, op, est, sorteio) -> str:
    hoje = agora.date()
    _fechar_sem_resposta(base, hoje, op["dias_sem_resposta"])
    if est["pausado"]:
        return f"pausado: {est['motivo']}"
    aberta, motivo = fila.janela_aberta(cfg, agora)
    if not aberta:
        return f"aguardando janela comercial: {motivo}"
    maduros, respondidos = taxa_resposta(base, hoje)
    if maduros >= op["amostra_resposta"] and respondidos / maduros < op["resposta_minima"]:
        pausar(est, f"só {respondidos} resposta(s) em {maduros} envios — o número pode estar sendo ignorado ou "
                    "marcado. Reveja nicho e texto antes de retomar.", agora)
        return "pausado por taxa de resposta"
    teto = teto_hoje(cfg, est, hoje)
    if fila.enviados_hoje(base, hoje) >= teto:
        return f"teto de hoje atingido ({teto})"
    hora = agora.strftime("%Y-%m-%dT%H")
    if sum(1 for l in base.leads if l["observacao"].endswith(f"[envio {hora}]")) >= op["max_por_hora"]:
        return "teto por hora atingido"
    if est["proximo_envio"] and agora.isoformat() < est["proximo_envio"]:
        return "aguardando intervalo entre envios"

    try:
        if not api.conectado():
            est["quedas"] += 1
            est["risco"] = min(100, est["risco"] + 15)
            evento(est, "conexão", "instância desconectada do WhatsApp", agora)
            if est["quedas"] >= 3 or est["risco"] >= op["risco_pausa"]:
                pausar(est, "WhatsApp desconectado repetidas vezes — confira o aparelho e a instância.", agora)
            return "instância desconectada"
        est["quedas"] = 0

        aptos = [l for l in base.leads if l["status"] == B.PRONTO and not l["alertas"]
                 and B.eh_celular(l["whatsapp"]) and l["fonte_whatsapp"] and not base.esta_removido(l)]
        if not aptos:
            return "nenhum lead pronto"
        lead = sorted(aptos, key=lambda l: (l["prioridade"] or "C", l["decisor_nivel"] or "Z"))[0]
        if not api.existe(lead["whatsapp"]):
            lead["status"], lead["observacao"] = B.DESCARTADO, "descartado: número não está no WhatsApp. " + lead["observacao"]
            base.salvar()
            return f"{lead['id']} descartado: número sem WhatsApp"
        texto = fila.montar_texto(cfg, lead, agora)
        status = api.enviar(lead["whatsapp"], texto)
    except requests.RequestException as erro:
        est["risco"] = min(100, est["risco"] + 10)
        evento(est, "erro", f"Evolution API fora do ar: {erro}"[:160], agora)
        if est["risco"] >= op["risco_pausa"]:
            pausar(est, "Evolution API inacessível repetidas vezes.", agora)
        return "erro de comunicação com a Evolution API"

    if status >= 300:
        est["risco"] = min(100, est["risco"] + {401: 60, 403: 40}.get(status, 20))
        evento(est, "falha", f"{lead['id']} {lead['empresa']}: envio recusado (HTTP {status})", agora)
        if est["risco"] >= op["risco_pausa"]:
            pausar(est, f"falhas de envio em série (risco {est['risco']}). Não retome sem entender a causa.", agora)
        return f"falha no envio (HTTP {status})"

    lead.update(status=B.ENVIADO, data_1=hoje.isoformat(), canal_usado="whatsapp", gancho_usado=lead["gancho"],
                texto_enviado=texto, observacao=f"{lead['observacao']} [envio {hora}]".strip())
    base.salvar()
    est["primeiro_envio"] = est["primeiro_envio"] or hoje.isoformat()
    est["risco"] = max(0, est["risco"] - 5)
    est["proximo_envio"] = (agora + timedelta(minutes=sorteio(*op["intervalo_min"]))).isoformat()
    evento(est, "envio", f"{lead['id']} {lead['empresa']}", agora)
    return f"enviado para {lead['id']} {lead['empresa']}"


def _fechar_sem_resposta(base: B.Base, hoje: date, dias: int) -> None:
    limite, mudou = (hoje - timedelta(days=dias)).isoformat(), False
    for l in base.leads:
        if l["status"] == B.ENVIADO and not l["resultado"] and l["data_1"] and l["data_1"] <= limite:
            l["resultado"], l["data_resultado"], mudou = "sem_resposta", hoje.isoformat(), True
    if mudou:
        base.salvar()


# ------------------------------------------------------------------ respostas (webhook)
def _texto_da_mensagem(msg: dict) -> str:
    return (msg.get("conversation") or msg.get("extendedTextMessage", {}).get("text") or "").strip()


def receber(cfg: dict, base: B.Base, api: Evolution | None, payload: dict, agora: datetime | None = None) -> str:
    """Trata um evento do webhook da Evolution API."""
    agora = agora or datetime.now(fila.FUSO)
    nome = str(payload.get("event", "")).lower().replace("_", ".")
    dados = payload.get("data") or {}
    est = ler_estado(base)
    try:
        if nome == "connection.update":
            estado_con = dados.get("state", "")
            if estado_con == "close":
                est["risco"] = min(100, est["risco"] + 15)
                evento(est, "conexão", f"conexão fechada (motivo {dados.get('statusReason', '?')})", agora)
                if str(dados.get("statusReason")) in ("401", "403"):
                    pausar(est, "o WhatsApp encerrou a sessão do número (possível restrição). Não retome sem conferir o aparelho.", agora)
            return f"conexão: {estado_con}"
        if nome != "messages.upsert":
            return "ignorado"
        chave = dados.get("key", {})
        jid = chave.get("remoteJid", "")
        if chave.get("fromMe") or not jid.endswith("@s.whatsapp.net"):
            return "ignorado"
        fone8 = B.so_digitos(jid.split("@")[0])[-8:]
        lead = next((l for l in base.leads if l["status"] in (B.ENVIADO, "em conversa") and l["whatsapp"][-8:] == fone8), None)
        if not lead:
            return "mensagem de quem não está na prospecção"
        texto = _texto_da_mensagem(dados.get("message", {}))
        limpo = unicodedata.normalize("NFKC", texto)
        lead["notas_resultado"] = (lead["notas_resultado"] + " | " if lead["notas_resultado"] else "") + limpo[:300]
        lead["data_resultado"] = agora.date().isoformat()
        if SAIDA_RE.search(limpo):
            fila.registrar_resultado(base, lead["id"], "optout", limpo[:300])
            evento(est, "remoção", f"{lead['id']} {lead['empresa']} pediu para sair", agora)
            if api:
                try:
                    api.enviar(lead["whatsapp"], "Entendido. Retiramos o contato da nossa lista e não enviaremos mais mensagens.")
                except requests.RequestException:
                    pass
            return "removido a pedido"
        lead["status"], lead["resultado"] = "em conversa", lead["resultado"] if lead["resultado"] not in ("", "sem_resposta") else "respondeu"
        base.salvar()
        evento(est, "resposta", f"{lead['id']} {lead['empresa']}: {limpo[:80]}", agora)
        return "resposta registrada"
    finally:
        salvar_estado(base, est)
