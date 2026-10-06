"""Envio automático pelo WhatsApp do escritório, pela API oficial da Meta (WhatsApp Cloud API) — sem intermediário.

Mensagens que o escritório inicia (cobrança) precisam usar MODELOS aprovados pela Meta (categoria "Utilidade").
O sistema traz os textos prontos (MODELOS) para cadastrar no Gerenciador do WhatsApp; os campos {{1}}…{{8}} são
preenchidos a cada envio:
  1 nome do cliente · 2 valor · 3 referência · 4 vencimento · 5 linha digitável · 6 PIX copia e cola
  7 pagamento com cartão · 8 assinatura do escritório

API: POST https://graph.facebook.com/{versão}/{phone_number_id}/messages (Authorization: Bearer <token>).
Custo informado pela Meta para o Brasil: cobrança por mensagem entregue (categoria utilidade).
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import date

from . import clientes, config, db, financeiro

URL_API = "https://graph.facebook.com"
VERSAO = "v23.0"

MODELOS = {
    "lembrete": ("cobranca_lembrete",
                 "Olá, {{1}}! Lembramos que os honorários de {{2}}, referentes a {{3}}, vencem em {{4}}.\n\n"
                 "Linha digitável do boleto: {{5}}\nPIX copia e cola: {{6}}\n{{7}}\n\n"
                 "Se precisar, é só responder esta mensagem. Atenciosamente, {{8}}."),
    "hoje": ("cobranca_vence_hoje",
             "Olá, {{1}}! Os honorários de {{2}}, referentes a {{3}}, vencem hoje ({{4}}).\n\n"
             "Linha digitável do boleto: {{5}}\nPIX copia e cola: {{6}}\n{{7}}\n\n"
             "Se já pagou, desconsidere. Atenciosamente, {{8}}."),
    "atraso": ("cobranca_atraso",
               "Olá, {{1}}! Não identificamos o pagamento dos honorários de {{2}}, referentes a {{3}}, vencidos em {{4}}.\n\n"
               "Linha digitável do boleto: {{5}}\nPIX copia e cola: {{6}}\n{{7}}\n\n"
               "Se já pagou, desconsidere e nos envie o comprovante. Atenciosamente, {{8}}."),
}


class ErroWhatsApp(RuntimeError):
    pass


def _cfg(cfg: dict | None = None) -> dict:
    return (cfg or config.carregar())["cobranca"]


def configurado(cfg: dict | None = None) -> bool:
    c = _cfg(cfg)
    return bool(c.get("whatsapp_api") and c.get("whatsapp_token") and c.get("whatsapp_phone_id"))


def numero(telefone: str) -> str:
    """Celular brasileiro no formato da API (55 + DDD + número); vazio se não for celular válido."""
    d = clientes._digitos(telefone)
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11 and d[2] == "9":
        return "55" + d
    return ""


def _api(metodo: str, caminho: str, corpo: dict | None = None, cfg: dict | None = None) -> dict:
    c = _cfg(cfg)
    url = f"{c.get('whatsapp_api_url') or URL_API}/{c.get('whatsapp_versao') or VERSAO}/{caminho}"
    req = urllib.request.Request(url, method=metodo, data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Authorization": f"Bearer {c.get('whatsapp_token', '')}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        try:
            err = json.loads(bruto).get("error", {})
            msg = err.get("error_user_msg") or err.get("message") or bruto[:300]
            cod = err.get("code")
        except ValueError:
            msg, cod = bruto[:300], None
        dica = {190: " (token inválido ou expirado — gere um token permanente no Gerenciador de Negócios)",
                132001: " (modelo não encontrado ou ainda não aprovado pela Meta)",
                131026: " (o número não tem WhatsApp)", 131047: " (fora da janela de 24 h: use um modelo aprovado)",
                100: " (confira o ID do número de telefone)"}.get(cod, "")
        raise ErroWhatsApp(f"WhatsApp: {msg}{dica}") from e


def testar(cfg: dict | None = None) -> dict:
    c = _cfg(cfg)
    if not configurado(cfg):
        raise ErroWhatsApp("WhatsApp: ligue a API e informe o token e o ID do número em Configurações.")
    r = _api("GET", f"{c['whatsapp_phone_id']}?fields=display_phone_number,verified_name,quality_rating", cfg=cfg)
    return {"ok": True, "mensagem": f"WhatsApp OK: {r.get('verified_name', '')} {r.get('display_phone_number', '')}".strip()
            + (f" (qualidade {r['quality_rating']})" if r.get("quality_rating") else "")}


def _txt(v) -> str:
    """Parâmetro de modelo: sem quebra de linha, tabulação ou mais de 4 espaços seguidos (regra da Meta)."""
    v = re.sub(r"\s+", " ", str(v or "")).strip()
    return v[:1000] or "-"


def parametros(t: dict, etapa: int, cfg: dict | None = None, em: date | None = None) -> list[str]:
    from .cobranca import _brl, _data, nome_cliente
    cfg = cfg or config.carregar()
    t = financeiro.enriquecer(t, em)
    valor = _brl(t["valor_cent"]) + (f" (atualizado com multa e juros: {_brl(t['total_cent'])})" if etapa > 0 else "")
    ref = f"{t['descricao']} - competência {t['competencia'][5:]}/{t['competencia'][:4]}"
    cartao = "Também aceitamos PIX e boleto, sem acréscimo."
    if t.get("cartao_link") and t.get("cartao_status") == "aberto":
        cartao = (f"Prefere cartão de crédito? {t['cartao_link']} - valor no cartão {_brl(t['cartao_total_cent'])}, "
                  "com a taxa da operadora por conta de quem paga com cartão (pelo boleto ou PIX, sem acréscimo).")
    emp = cfg["empresa"]
    return [_txt(x) for x in (nome_cliente(t["cliente_nome"]), valor, ref, _data(t["vencimento"]),
                              t.get("linha_digitavel") or "não se aplica", t.get("pix_copia_cola") or "não se aplica",
                              cartao, emp.get("assinatura") or emp["nome"])]


def enviar_cobranca(t: dict, etapa: int, telefone: str, cfg: dict | None = None, em: date | None = None) -> str:
    """Envia o modelo da etapa (lembrete, vence hoje ou atraso) e devolve o id da mensagem na Meta."""
    cfg = cfg or config.carregar()
    c = _cfg(cfg)
    para = numero(telefone)
    if not para:
        raise ErroWhatsApp("WhatsApp: telefone do cliente não é um celular válido (DDD + 9 dígitos).")
    tipo = "lembrete" if etapa < 0 else "hoje" if etapa == 0 else "atraso"
    nome_modelo = c.get(f"whatsapp_modelo_{tipo}") or MODELOS[tipo][0]
    corpo = {"messaging_product": "whatsapp", "to": para, "type": "template",
             "template": {"name": nome_modelo, "language": {"code": c.get("whatsapp_idioma") or "pt_BR"},
                          "components": [{"type": "body", "parameters": [{"type": "text", "text": p}
                                                                          for p in parametros(t, etapa, cfg, em)]}]}}
    from . import mensagens
    reg = {"tipo": mensagens.tipo_da_etapa(etapa), "titulo_id": t["id"], "cliente": t["cliente_nome"]}
    texto = f"Modelo {nome_modelo}: " + " | ".join(parametros(t, etapa, cfg, em))
    try:
        r = _api("POST", f"{c['whatsapp_phone_id']}/messages", corpo, cfg)
    except Exception as ex:
        mensagens.registrar("whatsapp", para, "", texto, "erro", str(ex)[:500], **reg)
        raise
    mid = ((r.get("messages") or [{}])[0]).get("id", "")
    mensagens.registrar("whatsapp", para, "", texto, "enviado", f"API oficial (Meta) {mid}", **reg)
    db.registrar("whatsapp", f"Título {t['id']} ({t['cliente_nome']}): modelo {nome_modelo} enviado para {para}")
    return mid
