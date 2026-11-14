"""Processo único do modo automático: motor de envio, abastecimento do funil,
webhook de respostas e painel web.

    python -m prospeccao servidor
"""
from __future__ import annotations

import hmac
import json
import threading
import time
from collections import Counter
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import base as B
from . import etapas, fila
from . import whatsapp as W

TRAVA = threading.Lock()   # motor, webhook e ações do painel: um por vez (operações curtas)
PAGINA = Path(__file__).parent / "painel.html"


# ------------------------------------------------------------------ abastecimento
def abastecer(cfg: dict, pasta: str, agora: datetime | None = None) -> list[str]:
    """Mantém o funil cheio: nichos -> busca -> qualificação -> material.
    Cada etapa roda em lote pequeno e só quando falta lead para os próximos dias."""
    agora = agora or datetime.now(fila.FUSO)
    feito = []
    with TRAVA:
        base = B.Base(pasta)
        est = W.ler_estado(base)
        conta = Counter(l["status"] for l in base.leads)
        alvo = W.opcoes(cfg)["teto_dia"] * 2
    try:
        if not (Path(pasta) / "nichos.json").exists():
            etapas.nichos(cfg, pasta)
            feito.append("nichos definidos a partir do site")
        if conta[B.PRONTO] < alvo:
            if conta[B.NOVO] < 10 and est.get("ultima_busca") != agora.date().isoformat():
                r = etapas.buscar(cfg, B.Base(pasta), maximo=20)
                feito.append(f"busca: {r['entraram']} empresas novas")
                est["ultima_busca"] = agora.date().isoformat()
            # as etapas com IA demoram: rodam fora da trava, cada uma na sua cópia da base
            # (Base.salvar mescla com o disco), para não segurar o painel nem o webhook
            for nome, etapa in (("qualificação", etapas.qualificar), ("material", etapas.material)):
                r = etapa(cfg, B.Base(pasta), limite=5)
                if any(r.values()):
                    feito.append(f"{nome}: {r}")
    except SystemExit as erro:      # falta de chave ou de configuração
        feito.append(f"abastecimento parado: {erro}")
    except Exception as erro:       # site fora do ar, API indisponível etc.
        feito.append(f"erro no abastecimento: {type(erro).__name__}: {erro}"[:200])
    with TRAVA:
        base = B.Base(pasta)
        atual = W.ler_estado(base)
        atual["ultima_busca"] = est.get("ultima_busca", "")
        for f in feito:
            W.evento(atual, "funil", f, agora)
        W.salvar_estado(base, atual)
    return feito


# ------------------------------------------------------------------ dados do painel
def painel(cfg: dict, base: B.Base, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(fila.FUSO)
    hoje, est, L = agora.date(), W.ler_estado(base), base.leads
    enviados = [l for l in L if l["data_1"]]
    bom = lambda l: l["resultado"] in ("positiva", "reuniao")
    respondeu = lambda l: l["resultado"] not in ("", "sem_resposta")

    def grupo(campo):
        linhas = []
        for chave in sorted({l[campo] for l in enviados}):
            g = [l for l in enviados if l[campo] == chave]
            linhas.append({"nome": chave or "(sem gancho)", "enviados": len(g), "respostas": sum(map(respondeu, g)),
                           "positivas": sum(map(bom, g)), "saidas": sum(l["resultado"] == "optout" for l in g)})
        return sorted(linhas, key=lambda x: -x["enviados"])

    dias = [(hoje - timedelta(days=d)) for d in range(13, -1, -1)]
    aberta, motivo_janela = fila.janela_aberta(cfg, agora)
    maduros, resp = W.taxa_resposta(base, hoje)
    descartes = Counter(l["observacao"].split(".")[0].replace("descartado: ", "") for l in L if l["status"] == B.DESCARTADO)
    resumo = lambda l: {k: l[k] for k in ("id", "empresa", "subsetor", "municipio", "prioridade", "decisor_nome",
                                         "decisor_cargo", "whatsapp", "fonte_whatsapp", "o_que_vimos", "a_conta",
                                         "gancho", "alertas", "resultado", "notas_resultado", "data_1", "status")}
    return {
        "escritorio": cfg["escritorio"]["nome"], "agora": agora.strftime("%d/%m/%Y %H:%M"),
        "motor": {"pausado": est["pausado"], "motivo": est["motivo"], "risco": est["risco"],
                  "limite_risco": W.opcoes(cfg)["risco_pausa"], "janela": aberta, "motivo_janela": motivo_janela,
                  "enviados_hoje": fila.enviados_hoje(base, hoje), "teto_hoje": W.teto_hoje(cfg, est, hoje),
                  "proximo_envio": est["proximo_envio"][11:16] if est["proximo_envio"][:10] == hoje.isoformat() else "",
                  "maduros": maduros, "respostas": resp},
        "funil": [{"etapa": nome, "n": sum(l["status"] in st for l in L)} for nome, st in (
            ("Encontradas", {s for s in {l["status"] for l in L}}), ("Qualificadas", {B.QUALIFICADO, B.PRONTO, B.NA_FILA, B.ENVIADO, B.EM_CONVERSA, B.BARRADO, B.REMOVIDO}),
            ("Texto aprovado", {B.PRONTO, B.NA_FILA, B.ENVIADO, B.EM_CONVERSA, B.REMOVIDO}), ("Enviadas", {B.ENVIADO, B.EM_CONVERSA, B.REMOVIDO}),
            ("Em conversa", {B.EM_CONVERSA}))] + [{"etapa": "Proposta / reunião", "n": sum(map(bom, L))}],
        "totais": {"enviados": len(enviados), "respostas": sum(map(respondeu, enviados)), "positivas": sum(map(bom, enviados)),
                   "saidas": len(base.removidos()), "prontos": sum(l["status"] == B.PRONTO for l in L),
                   "barrados": sum(l["status"] == B.BARRADO for l in L)},
        "por_dia": [{"dia": d.strftime("%d/%m"), "n": sum(l["data_1"] == d.isoformat() for l in L)} for d in dias],
        "por_setor": grupo("setor"), "por_gancho": grupo("gancho_usado"),
        "conversas": [resumo(l) for l in L if l["status"] == B.EM_CONVERSA],
        "proximos": [resumo(l) for l in sorted((l for l in L if l["status"] == B.PRONTO),
                                               key=lambda l: (l["prioridade"] or "C", l["decisor_nivel"] or "Z"))[:10]],
        "barrados": [resumo(l) for l in L if l["status"] == B.BARRADO or (l["status"] == B.QUALIFICADO and l["alertas"])][:20],
        "descartes": [{"motivo": m, "n": n} for m, n in descartes.most_common(8)],
        "eventos": est["eventos"][-40:][::-1],
    }


# ------------------------------------------------------------------ HTTP
def criar_handler(cfg: dict, pasta: str, api):
    token = cfg.get("painel", {}).get("token", "")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _responde(self, codigo, corpo, tipo="application/json"):
            dados = corpo if isinstance(corpo, bytes) else json.dumps(corpo, ensure_ascii=False).encode()
            self.send_response(codigo)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def _autorizado(self, u) -> bool:
            dado = parse_qs(u.query).get("t", [""])[0]
            return not token or hmac.compare_digest(dado, token)

        def do_GET(self):
            u = urlparse(self.path)
            if not self._autorizado(u):
                return self._responde(403, {"erro": "token ausente ou inválido"})
            if u.path == "/":
                return self._responde(200, PAGINA.read_bytes(), "text/html")
            if u.path == "/api/painel":
                with TRAVA:
                    return self._responde(200, painel(cfg, B.Base(pasta)))
            self._responde(404, {"erro": "não encontrado"})

        def do_POST(self):
            u = urlparse(self.path)
            tamanho = int(self.headers.get("Content-Length") or 0)
            try:
                corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            except ValueError:
                return self._responde(400, {"erro": "JSON inválido"})
            if u.path.startswith("/webhook/"):
                if token and not hmac.compare_digest(u.path.split("/")[2], token):
                    return self._responde(403, {"erro": "token inválido"})
                with TRAVA:
                    return self._responde(200, {"ok": W.receber(cfg, B.Base(pasta), api, corpo)})
            if not self._autorizado(u):
                return self._responde(403, {"erro": "token ausente ou inválido"})
            with TRAVA:
                base = B.Base(pasta)
                est = W.ler_estado(base)
                if u.path == "/api/pausar":
                    W.pausar(est, "pausado pelo painel")
                elif u.path == "/api/retomar":
                    est.update(pausado=False, motivo="", risco=0, quedas=0)
                    W.evento(est, "retomada", "retomado pelo painel")
                elif u.path == "/api/resultado":
                    try:
                        lead = fila.registrar_resultado(base, corpo["id"], corpo["resultado"], corpo.get("notas", ""))
                        if lead["status"] == B.EM_CONVERSA:      # o escritório assumiu: sai da lista de pendências
                            lead["status"] = B.ENVIADO
                            base.salvar()
                    except (SystemExit, KeyError) as erro:
                        return self._responde(400, {"erro": str(erro)})
                    return self._responde(200, {"ok": True})
                else:
                    return self._responde(404, {"erro": "não encontrado"})
                W.salvar_estado(base, est)
            self._responde(200, {"ok": True})

    return H


def laco(cfg: dict, pasta: str, api, parar: threading.Event) -> None:
    ultimo_abastecimento = 0.0
    while not parar.is_set():
        try:
            with TRAVA:
                W.passo(cfg, B.Base(pasta), api)
            if time.time() - ultimo_abastecimento > 30 * 60:
                ultimo_abastecimento = time.time()
                abastecer(cfg, pasta)
        except Exception as erro:
            print("erro no laço:", erro)
        parar.wait(60)


def rodar(cfg: dict, pasta: str) -> None:
    p = cfg.get("painel", {})
    if not p.get("token") or p["token"].startswith("troque"):
        raise SystemExit("Defina painel.token em config.json (um texto longo e aleatório) antes de ligar o servidor.")
    api = W.Evolution(cfg)
    parar = threading.Event()
    threading.Thread(target=laco, args=(cfg, pasta, api, parar), daemon=True).start()
    host, porta = p.get("host", "127.0.0.1"), int(p.get("porta", 8787))
    srv = ThreadingHTTPServer((host, porta), criar_handler(cfg, pasta, api))
    print(f"Painel: http://{host}:{porta}/?t=<token>   Webhook da Evolution: http://{host}:{porta}/webhook/<token>")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        parar.set()
