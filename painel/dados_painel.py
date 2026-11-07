"""Camada de dados do painel: carteira, mercado, rankings, scanner, gráficos e fila."""
from __future__ import annotations

import json
import math
import time
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from pesquisa.fatores import carregar_paineis, sinais
from pesquisa.motor_pesquisa import EXCLUIDOS
from swingbot import config as config_mod
from swingbot import fiscal, risco
from swingbot.carteira import Carteira
from swingbot.indicadores import atr, ifr, mme, mms

RAIZ = Path(__file__).resolve().parents[1]
PESQ = RAIZ / "dados_cache" / "pesquisa"
REL = RAIZ / "relatorios"


def _cfg():
    return config_mod.carregar(RAIZ / "config" / "config.yaml")


def _f(v, casas=4):
    """float JSON-seguro."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) or math.isinf(v) else round(v, casas)


# ============================================================================ dados de mercado
def _assinatura_dados() -> float:
    return max((f.stat().st_mtime for f in PESQ.glob("*.csv")), default=0.0)


@lru_cache(maxsize=2)
def _paineis(_assinatura: float):
    C, U, D, cdi, ibov = carregar_paineis()
    ohlc = {}
    for f in PESQ.glob("*.csv"):
        if (f.stem.startswith("_") and f.stem != "_BVSP") or f.stem in EXCLUIDOS:
            continue
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        if f.stem != "_BVSP":
            d = d[d.volume > 0]
        ohlc[f.stem.replace("_BVSP", "IBOV")] = d[d.high >= d.low]
    return C, U, D, cdi, ibov, ohlc


def paineis():
    if not PESQ.exists() or not any(PESQ.glob("*.csv")):
        raise RuntimeError("Sem dados. Clique em 'Atualizar dados' ou rode: python pesquisa/baixar.py")
    return _paineis(_assinatura_dados())


def atualizar_dados() -> dict:
    """Baixa cotações ajustadas, dividendos e CDI atualizados."""
    import subprocess
    import sys
    t0 = time.time()
    for script in ("pesquisa/baixar.py", "pesquisa/baixar_dividendos.py", "pesquisa/baixar_consenso.py"):
        subprocess.run([sys.executable, script], cwd=RAIZ, check=True, capture_output=True, timeout=900)
    _paineis.cache_clear()
    return {"ok": True, "segundos": round(time.time() - t0, 1)}


def cdi_anual(cdi: pd.Series) -> float:
    ult = cdi[cdi > 0].iloc[-1] if (cdi > 0).any() else 0.0
    return (1 + ult) ** 252 - 1


# ============================================================================ carteira / robô
def carregar_carteira(cfg=None) -> tuple[Carteira, str]:
    cfg = cfg or _cfg()
    nome = "real" if cfg.modo == "real" else "simulada"
    caminho = RAIZ / cfg.pasta_estado / f"carteira_{nome}.json"
    cart = Carteira.carregar_ou_criar(caminho, cfg.risco.capital_teste, cfg.risco.custo_percentual)
    return cart, nome


def custodia_clear(cfg=None) -> dict | None:
    cfg = cfg or _cfg()
    arq = RAIZ / cfg.pasta_estado / "custodia_clear.json"
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def resumo() -> dict:
    cfg = _cfg()
    C, U, D, cdi, ibov, ohlc = paineis()
    cart, nome = carregar_carteira(cfg)
    precos = {t: float(C[t].dropna().iloc[-1]) for t in C.columns if C[t].notna().any()}
    posicoes = []
    risco_aberto = valor_pos = 0.0
    for t, p in cart.posicoes.items():
        preco = precos.get(t, p.preco_medio)
        valor = p.quantidade * preco
        valor_pos += valor
        risco_aberto += max(0.0, p.quantidade * (preco - p.stop))
        posicoes.append({
            "ticker": t, "quantidade": p.quantidade, "preco_medio": _f(p.preco_medio, 2), "preco": _f(preco, 2),
            "valor": _f(valor, 2), "resultado": _f(p.quantidade * (preco - p.preco_medio), 2),
            "resultado_pct": _f(preco / p.preco_medio - 1), "stop": p.stop, "alvo": p.alvo,
            "dist_stop_pct": _f(p.stop / preco - 1), "entrada": p.data_entrada, "stop_enviado": p.stop_enviado,
        })
    patrimonio = cart.patrimonio(precos)
    realizado = sum(t["resultado"] for t in cart.trades)
    ib = ibov.dropna()
    mm200 = ib.rolling(200).mean()
    return {
        "modo": cfg.modo, "carteira": nome, "capital_inicial": cart.capital_inicial,
        "patrimonio": _f(patrimonio, 2), "caixa": _f(cart.caixa, 2),
        "resultado_total": _f(patrimonio - cart.capital_inicial, 2),
        "resultado_total_pct": _f(patrimonio / cart.capital_inicial - 1),
        "resultado_realizado": _f(realizado, 2),
        "exposicao_pct": _f(valor_pos / patrimonio if patrimonio else 0),
        "risco_aberto": _f(risco_aberto, 2), "risco_aberto_pct": _f(risco_aberto / patrimonio if patrimonio else 0),
        "kill_switch": risco.kill_switch(cfg.risco, patrimonio), "parar": risco.parada_manual_ativa(RAIZ),
        "posicoes": posicoes, "trades": cart.trades[-50:], "pendentes": [o.to_dict() for o in cart.pendentes],
        "mercado": {
            "ibov": _f(ib.iloc[-1], 0), "ibov_dia": _f(ib.iloc[-1] / ib.iloc[-2] - 1),
            "ibov_12m": _f(ib.iloc[-1] / ib.iloc[-253] - 1) if len(ib) > 253 else None,
            "ibov_acima_mm200": bool(ib.iloc[-1] > mm200.iloc[-1]),
            "ibov_dist_mm200": _f(ib.iloc[-1] / mm200.iloc[-1] - 1),
            "cdi_aa": _f(cdi_anual(cdi)), "data_dados": C.index[-1].date().isoformat(),
        },
        "custodia_clear": custodia_clear(cfg),
        "regras": {"capital_teste": cfg.risco.capital_teste, "risco_por_operacao": cfg.risco.risco_por_operacao,
                   "max_posicoes": cfg.risco.max_posicoes, "perda_maxima_total": cfg.risco.perda_maxima_total},
    }


# ============================================================================ rankings por fatores
def ranking() -> dict:
    C, U, D, cdi, ibov, _ = paineis()
    i = len(C) - 1
    s = sinais(C, U, D, i)
    mom, dy, vol = s["Momentum 12-1"], s["Dividend yield"], -s["Baixa volatilidade"]
    linhas = []
    for t in mom.index:
        serie = C[t].dropna()
        linhas.append({
            "ticker": t, "preco": _f(serie.iloc[-1], 2), "var_dia": _f(serie.iloc[-1] / serie.iloc[-2] - 1),
            "var_mes": _f(serie.iloc[-1] / serie.iloc[-22] - 1), "var_3m": _f(serie.iloc[-1] / serie.iloc[-64] - 1),
            "queda_max_6m": _f(serie.iloc[-1] / serie.iloc[-126:].max() - 1),
            "momentum_12_1": _f(mom[t]),
            "dy_12m": _f(dy.get(t)), "vol_anual": _f(vol[t] * math.sqrt(252)),
        })
    df = pd.DataFrame(linhas).set_index("ticker")
    df["rank_dy"] = df.dy_12m.rank(ascending=False, method="first")
    df["rank_mom"] = df.momentum_12_1.rank(ascending=False, method="first")
    # DY alto por queda forte do preço costuma ser armadilha (dividendo passado, empresa em problema)
    df["alerta_dy"] = (df.queda_max_6m < -0.30) & (df.dy_12m > 0.06)
    df["top_dividendos"] = df.rank_dy <= 10
    df["top_momentum"] = df.rank_mom <= 10
    alvo_div = list(df.sort_values("rank_dy").index[:10])
    alvo_mom = list(df.sort_values("rank_mom").index[:10])
    pesos_mix: dict[str, float] = {}
    for t in alvo_div:
        pesos_mix[t] = pesos_mix.get(t, 0) + 0.05
    for t in alvo_mom:
        pesos_mix[t] = pesos_mix.get(t, 0) + 0.05
    out = df.reset_index().replace({np.nan: None}).to_dict("records")
    for r in out:
        for k in ("rank_dy", "rank_mom"):
            r[k] = int(r[k]) if r[k] is not None else None
    return {
        "data": C.index[i].date().isoformat(), "ativos": out,
        "carteiras_alvo": {
            "dividendos": {t: 0.1 for t in alvo_div},
            "momentum": {t: 0.1 for t in alvo_mom},
            "mix": {t: round(w, 4) for t, w in sorted(pesos_mix.items(), key=lambda x: -x[1])},
        },
    }


def rebalanceamento(estrategia: str, capital: float) -> dict:
    """Ordens para levar a custódia (ou carteira vazia) à carteira-alvo."""
    rk = ranking()
    alvo = rk["carteiras_alvo"][estrategia]
    precos = {a["ticker"]: a["preco"] for a in rk["ativos"]}
    atual = {}
    cust = custodia_clear()
    if cust:
        atual = {t: v["quantidade"] for t, v in cust.get("posicoes", {}).items()}
    ordens = []
    for t in sorted(set(alvo) | set(atual)):
        preco = precos.get(t)
        if not preco:
            continue
        qtd_alvo = int(capital * alvo.get(t, 0) // preco)
        dif = qtd_alvo - int(atual.get(t, 0))
        if dif:
            ordens.append({"ticker": t, "lado": "C" if dif > 0 else "V", "quantidade": abs(dif),
                           "preco_ref": preco, "valor": _f(abs(dif) * preco, 2),
                           "motivo": f"rebalanceamento {estrategia}"})
    return {"estrategia": estrategia, "capital": capital, "ordens": ordens, "usa_custodia": bool(cust)}


# ============================================================================ scanner de setups
def _evidencia() -> dict:
    arq = REL / "ranking_setups.csv"
    if not arq.exists():
        return {}
    r = pd.read_csv(arq)
    ev = {}
    for x in r.itertuples():
        ev[(x.setup, x.lado.startswith("Comprado"), x.universo)] = {
            "excesso_cdi_aa": _f(x.excesso_cdi_aa), "dd_max": _f(x.dd_max), "acerto": _f(x.acerto),
            "metade1": _f(x.excesso_1a_metade), "metade2": _f(x.excesso_2a_metade)}
    return ev


def scanner() -> dict:
    C, U, D, cdi, ibov, ohlc = paineis()
    ev = _evidencia()
    opps = []
    for t, df in ohlc.items():
        if len(df) < 260:
            continue
        c = df.close
        a = float(atr(df, 14).iloc[-1])
        ult = float(c.iloc[-1])
        m200 = float(mms(c, 200).iloc[-1])
        macd = mme(c, 12) - mme(c, 26)
        sig = mme(macd, 9)
        m9 = mme(c, 9)
        r2 = float(ifr(c, 2).iloc[-1])
        universo = "Ibovespa" if t == "IBOV" else "44 ações"
        base = {"ticker": t, "preco": _f(ult, 2), "atr": _f(a, 2), "acima_mm200": ult > m200}

        def add(setup, comprado, gatilho, entrada, stop, saida, forca):
            e = ev.get((setup, comprado, universo), {})
            risco_pct = abs(entrada - stop) / entrada if entrada else None
            opps.append({**base, "setup": setup, "direcao": "Compra" if comprado else "Venda",
                         "gatilho": gatilho, "entrada": _f(entrada, 2), "stop": _f(stop, 2),
                         "risco_pct": _f(risco_pct), "saida": saida, "forca": _f(forca, 2), "evidencia": e})

        if macd.iloc[-1] > sig.iloc[-1] and macd.iloc[-2] <= sig.iloc[-2]:
            add("MACD cruzamento", True, "MACD cruzou acima da linha de sinal no fechamento",
                ult, ult - 2 * a, "Cruzamento inverso do MACD", (ult - m200) / a)
        sobe = m9.iloc[-1] > m9.iloc[-2]
        if sobe and m9.iloc[-2] <= m9.iloc[-3]:
            h, lo = float(df.high.iloc[-1]), float(df.low.iloc[-1])
            add("Setup 9.1 (Larry Williams)", True, f"MME9 virou para cima: compra acima de {h:.2f}",
                h + 0.01, lo - 0.01, "MME9 virar para baixo (stop na mínima)", (ult - m200) / a)
        if r2 < 10:
            add("IFR2 (Connors)", True, f"IFR(2) = {r2:.1f} (sobrevenda extrema)", ult, ult - 2 * a,
                "Máxima dos 2 últimos candles ou 7 dias", (10 - r2))
        if r2 > 90:
            add("IFR2 (Connors)", False, f"IFR(2) = {r2:.1f} (sobrecompra extrema)", ult, ult + 2 * a,
                "Mínima dos 2 últimos candles ou 7 dias", (r2 - 90))
        if macd.iloc[-1] < sig.iloc[-1] and macd.iloc[-2] >= sig.iloc[-2]:
            add("MACD cruzamento", False, "MACD cruzou abaixo da linha de sinal", ult, ult + 2 * a,
                "Cruzamento inverso do MACD", (m200 - ult) / a)
    # ordena: primeiro setups com evidência positiva
    opps.sort(key=lambda o: (-(o["evidencia"].get("excesso_cdi_aa") or -1), -(o["forca"] or 0)))
    return {"data": C.index[-1].date().isoformat(), "oportunidades": opps}


# ============================================================================ gráfico
def grafico(ticker: str, dias: int = 500) -> dict:
    *_, ohlc = paineis()
    t = ticker.upper()
    if t not in ohlc:
        raise KeyError(t)
    df = ohlc[t]
    c = df.close
    ind = pd.DataFrame({"mme9": mme(c, 9), "mme21": mme(c, 21), "mms200": mms(c, 200)})
    macd = mme(c, 12) - mme(c, 26)
    ind["macd"], ind["sinal"] = macd, mme(macd, 9)
    ind["hist"] = ind.macd - ind.sinal
    df, ind = df.iloc[-dias:], ind.iloc[-dias:]
    tempo = [d.strftime("%Y-%m-%d") for d in df.index]
    velas = [{"time": tm, "open": _f(o, 2), "high": _f(h, 2), "low": _f(lo, 2), "close": _f(cl, 2)}
             for tm, o, h, lo, cl in zip(tempo, df.open, df.high, df.low, df.close)]
    vol = [{"time": tm, "value": _f(v, 0), "color": "up" if cl >= o else "down"}
           for tm, v, o, cl in zip(tempo, df.volume, df.open, df.close)]
    linhas = {k: [{"time": tm, "value": _f(v, 3)} for tm, v in zip(tempo, ind[k]) if _f(v) is not None]
              for k in ind.columns}
    cruz = (ind.macd > ind.sinal) & (ind.macd.shift(1) <= ind.sinal.shift(1))
    cruz_b = (ind.macd < ind.sinal) & (ind.macd.shift(1) >= ind.sinal.shift(1))
    marcas = [{"time": tm, "tipo": "compra"} for tm, x in zip(tempo, cruz) if x]
    marcas += [{"time": tm, "tipo": "venda"} for tm, x in zip(tempo, cruz_b) if x]
    return {"ticker": t, "velas": velas, "volume": vol, "linhas": linhas, "marcas": sorted(marcas, key=lambda m: m["time"])}


def lista_ativos() -> list[str]:
    *_, ohlc = paineis()
    return sorted(ohlc)


# ============================================================================ laboratório e fiscal
def laboratorio() -> dict:
    out = {"setups": [], "fatores": [], "curvas": {}}
    if (REL / "ranking_setups.csv").exists():
        out["setups"] = pd.read_csv(REL / "ranking_setups.csv").replace({np.nan: None}).to_dict("records")
    if (REL / "ranking_fatores.csv").exists():
        out["fatores"] = pd.read_csv(REL / "ranking_fatores.csv").replace({np.nan: None}).to_dict("records")
    arq = REL / "curvas_fatores.csv"
    if arq.exists():
        eq = pd.read_csv(arq, index_col=0, parse_dates=True).resample("W").last()
        for col in ["Dividend yield", "Momentum 12-1", "Universo", "Ibovespa", "CDI"]:
            if col in eq:
                out["curvas"][col] = [{"time": d.strftime("%Y-%m-%d"), "value": _f(v, 4)}
                                      for d, v in eq[col].dropna().items()]
    return out


def apuracao_fiscal() -> dict:
    cfg = _cfg()
    cart, nome = carregar_carteira(cfg)
    meses = fiscal.apurar(cart.operacoes, cfg.fiscal.limite_isencao_mensal, cfg.fiscal.tipos_ativo)
    return {"carteira": nome, "meses": [m.__dict__ for m in meses],
            "estimadas": sum(1 for o in cart.operacoes if o.estimado)}


# ============================================================================ fila de ordens
def _arq_fila() -> Path:
    cfg = _cfg()
    p = RAIZ / cfg.pasta_estado / "fila_ordens.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def fila() -> list[dict]:
    p = _arq_fila()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else []


def _salvar_fila(itens: list[dict]) -> None:
    p = _arq_fila()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(itens, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def adicionar_fila(ordem: dict) -> dict:
    lado = str(ordem.get("lado", "")).upper()
    tipo = str(ordem.get("tipo", "limitada")).lower()
    ticker = str(ordem.get("ticker", "")).upper().strip()
    qtd = int(ordem.get("quantidade", 0))
    preco = float(ordem.get("preco", 0))
    if lado not in ("C", "V") or tipo not in ("limitada", "stop") or not ticker or qtd <= 0 or preco <= 0:
        raise ValueError("Ordem inválida: informe ticker, lado C/V, quantidade e preço positivos")
    if tipo == "stop" and lado != "V":
        raise ValueError("Stop só é aceito como stop de venda (proteção)")
    protecao = ordem.get("protecao") or None
    if protecao:
        if lado != "C":
            raise ValueError("Proteções (stop/alvo/trailing) valem para ordens de compra")
        stop = float(protecao.get("stop") or 0)
        if not 0 < stop < preco:
            raise ValueError("Stop loss deve ficar abaixo do preço de compra")
        tp = protecao.get("take_profit")
        if tp is not None and float(tp) <= preco:
            raise ValueError("Take profit deve ficar acima do preço de compra")
        tr = protecao.get("trailing")
        if tr:
            from swingbot.protecoes import Trailing
            Trailing(**tr).validar()
    item = {"id": f"{int(time.time() * 1000)}", "ticker": ticker, "lado": lado, "tipo": tipo, "quantidade": qtd,
            "preco": round(preco, 2), "disparo": _f(ordem.get("disparo"), 2), "motivo": ordem.get("motivo", ""),
            "origem": ordem.get("origem", "painel"), "criada_em": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "aguardando robô", "protecao": protecao}
    itens = fila()
    itens.append(item)
    _salvar_fila(itens)
    return item


def remover_fila(item_id: str) -> bool:
    itens = fila()
    novos = [i for i in itens if i["id"] != item_id]
    _salvar_fila(novos)
    return len(novos) != len(itens)


def logs_robo(linhas: int = 80) -> list[str]:
    cfg = _cfg()
    pasta = RAIZ / cfg.pasta_logs
    arqs = sorted(pasta.glob("*/relatorio.txt"))
    if not arqs:
        return []
    return arqs[-1].read_text(encoding="utf-8").splitlines()[-linhas:]


# ============================================================================ proteções
def _repo():
    from swingbot.protecoes import Repositorio
    return Repositorio(RAIZ / _cfg().pasta_estado / "protecoes.json")


def protecoes() -> list[dict]:
    from swingbot.protecoes import stop_desejado
    try:
        C, *_ = paineis()
        precos = {t: float(C[t].dropna().iloc[-1]) for t in C.columns if C[t].notna().any()}
    except RuntimeError:
        precos = {}
    out = []
    for p in _repo().carregar().values():
        d = p.to_dict()
        preco = precos.get(p.ticker)
        d["preco"] = _f(preco, 2)
        d["resultado_pct"] = _f(preco / p.preco_entrada - 1) if preco else None
        d["dist_stop_pct"] = _f(p.stop / preco - 1) if preco else None
        d["dist_alvo_pct"] = _f(p.take_profit / preco - 1) if preco and p.take_profit else None
        if preco and p.ativa:  # projeta com o preço atual (o monitor atualiza a máxima no pregão)
            p.maior_preco = max(p.maior_preco, preco)
        d["proximo_stop"] = _f(stop_desejado(p), 2)
        out.append(d)
    return sorted(out, key=lambda x: (not x["ativa"], x["ticker"]))


def salvar_protecao(dados: dict) -> dict:
    from swingbot.protecoes import Protecao
    campos = {k: dados.get(k) for k in ("ticker", "quantidade", "preco_entrada", "stop", "take_profit", "trailing",
                                         "breakeven_pct", "usa_oco", "na_reversao")}
    campos = {k: v for k, v in campos.items() if v is not None}
    return _repo().upsert(Protecao(origem="painel", **campos)).to_dict()


def remover_protecao(ticker: str) -> bool:
    return _repo().remover(ticker)


# ============================================================================ consenso dos analistas
ROTULOS_REC = {"strong_buy": "Compra forte", "buy": "Compra", "hold": "Neutro", "underperform": "Venda",
               "sell": "Venda", "strong_sell": "Venda forte", "none": "Sem consenso", None: "Sem consenso"}


def consenso() -> dict:
    arq = PESQ / "_consenso.json"
    if not arq.exists():
        return {"atualizado_em": None, "ativos": []}
    dados = json.loads(arq.read_text(encoding="utf-8"))
    C, U, D, cdi, ibov, ohlc = paineis()
    rk = {a["ticker"]: a for a in ranking()["ativos"]}
    linhas = []
    for t, c in dados["ativos"].items():
        if t in EXCLUIDOS or t not in C.columns or not c.get("alvo_medio"):
            continue
        serie = C[t].dropna()
        preco = float(serie.iloc[-1])
        acima = bool(preco > serie.rolling(200).mean().iloc[-1])
        r = rk.get(t, {})
        conv = []
        if r.get("top_dividendos") and not r.get("alerta_dy"):
            conv.append("Top 10 dividendos")
        if r.get("top_momentum"):
            conv.append("Top 10 momentum")
        if acima:
            conv.append("Tendência de alta")
        dist = c.get("distribuicao") or {}
        linhas.append({
            "ticker": t, "nome": c.get("nome"), "setor": c.get("setor"),
            "recomendacao": ROTULOS_REC.get(c.get("recomendacao"), c.get("recomendacao")),
            "nota_media": _f(c.get("nota_media"), 2), "analistas": c.get("analistas"),
            "preco": _f(preco, 2), "alvo_medio": _f(c["alvo_medio"], 2), "alvo_min": _f(c.get("alvo_min"), 2),
            "alvo_max": _f(c.get("alvo_max"), 2), "upside": _f(c["alvo_medio"] / preco - 1),
            "compra": dist.get("strongBuy", 0) + dist.get("buy", 0), "neutro": dist.get("hold", 0),
            "venda": dist.get("sell", 0) + dist.get("strongSell", 0), "convergencia": conv,
        })
    # 1º consenso de compra (nota <= 2,5), depois convergência com os fatores, nota e potencial
    linhas.sort(key=lambda x: (0 if (x["nota_media"] or 9) <= 2.5 else 1, -len(x["convergencia"]),
                               x["nota_media"] or 9, -(x["upside"] or 0)))
    return {"atualizado_em": dados.get("atualizado_em"), "ativos": linhas}


# ============================================================================ alertas de reversão
def alertas() -> dict:
    """Diagnóstico de reversão para cada posição acompanhada (proteções ativas + posições do robô)."""
    from swingbot.reversao import avaliar as avaliar_rev
    *_, ohlc = paineis()
    acompanhar: dict[str, dict] = {}
    for p in _repo().carregar().values():
        if p.ativa:
            acompanhar[p.ticker] = {"quantidade": p.quantidade, "entrada": p.preco_entrada,
                                    "maior_preco": p.maior_preco, "origem": "proteção", "na_reversao": p.na_reversao}
    cart, _ = carregar_carteira()
    for t, p in cart.posicoes.items():
        acompanhar.setdefault(t, {"quantidade": p.quantidade, "entrada": p.preco_medio, "maior_preco": None,
                                  "data_entrada": p.data_entrada, "origem": "robô",
                                  "na_reversao": "robô (saída na regra da estratégia)"})
    saida = []
    for t, info in acompanhar.items():
        df = ohlc.get(t)
        if df is None or df.empty:
            continue
        maior = info["maior_preco"]
        if info.get("data_entrada"):
            desde = df.loc[info.pop("data_entrada"):, "high"]
            maior = float(desde.max()) if len(desde) else None
        d = avaliar_rev(df, maior)
        saida.append({"ticker": t, **info, **d.to_dict(),
                      "resultado_pct": _f(d.preco / info["entrada"] - 1) if info["entrada"] else None})
    ordem = {"SAIR": 0, "ATENÇÃO": 1, "OK": 2}
    saida.sort(key=lambda x: (ordem.get(x["nivel"], 3), -x["pontos"]))
    return {"data": paineis()[0].index[-1].date().isoformat(), "alertas": saida}
