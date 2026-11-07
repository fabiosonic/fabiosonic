"""Servidor local do painel: python -m swingbot painel  ->  http://127.0.0.1:8050"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import dados_painel as dp
from . import ia

ESTATICO = Path(__file__).parent / "static"
app = FastAPI(title="Painel Quant B3", docs_url="/api/docs")


def _proteger(fn, *a, **k):
    try:
        return fn(*a, **k)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    except KeyError as e:
        raise HTTPException(404, f"Não encontrado: {e}") from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@app.get("/")
def index():
    return FileResponse(ESTATICO / "index.html")


@app.get("/api/resumo")
def resumo():
    return _proteger(dp.resumo)


@app.get("/api/ranking")
def ranking():
    return _proteger(dp.ranking)


@app.get("/api/rebalanceamento")
def rebalanceamento(estrategia: str = "dividendos", capital: float = 10000.0):
    if estrategia not in ("dividendos", "momentum", "mix"):
        raise HTTPException(400, "estratégia inválida")
    return _proteger(dp.rebalanceamento, estrategia, capital)


@app.get("/api/scanner")
def scanner():
    return _proteger(dp.scanner)


@app.get("/api/ativos")
def ativos():
    return _proteger(dp.lista_ativos)


@app.get("/api/grafico/{ticker}")
def grafico(ticker: str, dias: int = 500):
    return _proteger(dp.grafico, ticker, max(60, min(dias, 3000)))


@app.get("/api/alertas")
def alertas():
    return _proteger(dp.alertas)


@app.get("/api/consenso")
def consenso():
    return _proteger(dp.consenso)


@app.get("/api/laboratorio")
def laboratorio():
    return _proteger(dp.laboratorio)


@app.get("/api/fiscal")
def fiscal():
    return _proteger(dp.apuracao_fiscal)


@app.post("/api/dados/atualizar")
def atualizar():
    try:
        return dp.atualizar_dados()
    except subprocess.CalledProcessError as e:
        raise HTTPException(502, f"Falha ao baixar dados: {e.stderr.decode(errors='ignore')[-300:]}") from e


# ------------------------------------------------------------------ fila de ordens / robô
class ProtecaoIn(BaseModel):
    ticker: str = ""
    quantidade: int = 0
    preco_entrada: float = 0.0
    stop: float
    take_profit: float | None = None
    trailing: dict | None = None
    breakeven_pct: float | None = None
    usa_oco: bool = False
    na_reversao: str = "avisar"


class OrdemIn(BaseModel):
    ticker: str
    lado: str
    quantidade: int
    preco: float
    tipo: str = "limitada"
    disparo: float | None = None
    motivo: str = ""
    origem: str = "painel"
    protecao: ProtecaoIn | None = None


@app.get("/api/fila")
def fila():
    return dp.fila()


@app.post("/api/fila")
def adicionar(ordem: OrdemIn):
    return _proteger(dp.adicionar_fila, ordem.model_dump())


@app.delete("/api/fila/{item_id}")
def remover(item_id: str):
    if not dp.remover_fila(item_id):
        raise HTTPException(404, "ordem não encontrada")
    return {"ok": True}


@app.get("/api/protecoes")
def listar_protecoes():
    return dp.protecoes()


@app.post("/api/protecoes")
def salvar_protecao(p: ProtecaoIn):
    return _proteger(dp.salvar_protecao, p.model_dump())


@app.delete("/api/protecoes/{ticker}")
def remover_protecao(ticker: str):
    if not dp.remover_protecao(ticker):
        raise HTTPException(404, "proteção não encontrada")
    return {"ok": True}


class OperacaoManual(BaseModel):
    ticker: str
    quantidade: int
    preco: float
    stop: float | None = None
    take_profit: float | None = None
    trailing: dict | None = None
    breakeven_pct: float | None = None
    stop_na_clear: bool = True
    motivo: str = ""


@app.post("/api/manual/compra")
def manual_compra(o: OperacaoManual):
    return _proteger(dp.registrar_compra, o.model_dump())


@app.post("/api/manual/venda")
def manual_venda(o: OperacaoManual):
    return _proteger(dp.registrar_venda, o.model_dump())


@app.get("/api/manual/acoes")
def manual_acoes():
    return _proteger(dp.acoes_manuais)


class NovoStop(BaseModel):
    stop: float


@app.post("/api/protecoes/{ticker}/stop")
def protecao_stop(ticker: str, n: NovoStop):
    return _proteger(dp.ajustar_stop, ticker, n.stop)


@app.get("/api/robo/logs")
def logs():
    return dp.logs_robo()


@app.post("/api/robo/sincronizar")
def sincronizar():
    """Abre o navegador (no seu computador) para ler a custódia da Clear."""
    subprocess.Popen([sys.executable, "-m", "swingbot", "sincronizar"], cwd=dp.RAIZ)
    return {"ok": True, "mensagem": "Navegador aberto: faça login na Clear para sincronizar a custódia."}


# ------------------------------------------------------------------ IA
def _contexto() -> dict:
    r = dp.resumo()
    rk = dp.ranking()
    sc = dp.scanner()
    lab = dp.laboratorio()
    top = sorted(rk["ativos"], key=lambda a: a["rank_dy"] or 99)[:12]
    top += [a for a in sorted(rk["ativos"], key=lambda a: a["rank_mom"] or 99)[:10] if a not in top]
    melhores_setups = sorted(lab["setups"], key=lambda s: -(s.get("excesso_cdi_aa") or -9))[:8]
    return {
        "data_dos_dados": r["mercado"]["data_dados"], "mercado": r["mercado"], "regras_risco": r["regras"],
        "carteira": {k: r[k] for k in ("modo", "patrimonio", "caixa", "exposicao_pct", "risco_aberto_pct",
                                       "kill_switch", "posicoes")},
        "carteira_alvo_dividendos": rk["carteiras_alvo"]["dividendos"],
        "ranking_resumido": top, "scanner_oportunidades": sc["oportunidades"][:15],
        "evidencia_setups": [{k: s.get(k) for k in ("setup", "lado", "universo", "excesso_cdi_aa", "dd_max",
                                                    "excesso_1a_metade", "excesso_2a_metade")}
                             for s in melhores_setups],
        "consenso_top": [c for c in dp.consenso()["ativos"] if (c.get("nota_media") or 9) <= 2.5][:20],
        "alertas": [a for a in dp.alertas()["alertas"]],
        "ranking_completo": rk["ativos"],
    }


@app.post("/api/ia/analise")
def ia_analise():
    try:
        return ia.analisar(_proteger(_contexto))
    except ia.IAIndisponivel as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/ia/uso")
def ia_uso():
    return ia.uso_mes()


@app.get("/api/casas")
def casas():
    dados = ia.carteiras_casas_cache() or {"casas": [], "mais_citados": [], "atualizado_em": None}
    cons = {a["ticker"]: a for a in _proteger(dp.consenso)["ativos"]}
    for m in dados.get("mais_citados", []):
        c = cons.get(m["ticker"].upper().replace(".SA", ""))
        m["consenso"] = c["recomendacao"] if c else None
        m["upside"] = c["upside"] if c else None
        m["convergencia"] = c["convergencia"] if c else []
    return dados


@app.post("/api/casas/atualizar")
def casas_atualizar():
    try:
        return ia.pesquisar_carteiras_casas()
    except ia.IAIndisponivel as e:
        raise HTTPException(503, str(e)) from e


class Pergunta(BaseModel):
    pergunta: str
    historico: list[dict] = []
    pesquisar_web: bool = False


@app.post("/api/ia/chat")
def ia_chat(p: Pergunta):
    if not p.pergunta.strip():
        raise HTTPException(400, "pergunta vazia")
    try:
        return ia.conversar(p.pergunta, p.historico, _proteger(_contexto), p.pesquisar_web)
    except ia.IAIndisponivel as e:
        raise HTTPException(503, str(e)) from e


app.mount("/static", StaticFiles(directory=ESTATICO), name="static")


def iniciar(porta: int = 8050, abrir: bool = True):
    import threading
    import webbrowser

    import uvicorn
    if abrir:
        threading.Timer(1.5, lambda: webbrowser.open(f"http://127.0.0.1:{porta}")).start()
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="warning")  # só na sua máquina
