"""Simulador de setups (long e short) com custos, aluguel de ações (BTC) e CDI."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd

PASTA = Path("dados_cache/pesquisa")
EXCLUIDOS = {"UGPA3", "JBSS32"}   # erros de ajuste no Yahoo (saltos falsos de +119% e +100%)
AQUECIMENTO = 260                  # pregões para aquecer indicadores (MMS200 etc.)


def carregar_universo():
    ativos = {}
    for f in sorted(PASTA.glob("*.csv")):
        nome = f.stem
        if nome.startswith("_") or nome in EXCLUIDOS:
            continue
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        ativos[nome] = d[d.volume > 0]          # remove feriados/pregões sem negócio
    cdi = pd.read_csv(PASTA / "_CDI.csv", index_col=0, parse_dates=True)["cdi"]
    ibov = pd.read_csv(PASTA / "_BVSP.csv", index_col=0, parse_dates=True)["close"]
    return ativos, cdi, ibov


def espelhar(df):
    """Gráfico espelhado para testar o lado vendido com a mesma lógica."""
    return pd.DataFrame({"open": -df.open, "high": -df.low, "low": -df.high, "close": -df.close}, index=df.index)


def simular(df, sinais, i0, custo, btc_aa, vendido):
    """Simula um ativo. Retorna (retornos diários, em posição?, lista de trades)."""
    O, H, L, C = (df[c].to_numpy(float) for c in ("open", "high", "low", "close"))
    s = sinais
    n = len(C)
    usa_nivel = not np.all(np.isnan(s["nivel"]))
    btc_dia = btc_aa / 252 if vendido else 0.0
    ret = np.full(n, np.nan)
    pos = np.zeros(n, bool)
    trades = []
    eq = 1.0
    em = False
    E = base = units = stop = alvo = 0.0
    eq_entrada = 0.0
    dias = i_ent = 0
    aluguel = 0.0
    for t in range(i0, n):
        eq_ant = eq
        saiu_hoje = False
        if em:
            px = None
            if s["saida"][t - 1]:
                px = O[t]
            elif not math.isnan(stop) and O[t] <= stop:
                px = O[t]
            elif not math.isnan(stop) and L[t] <= stop:
                px = stop
            elif not math.isnan(alvo) and O[t] >= alvo:
                px = O[t]
            elif not math.isnan(alvo) and H[t] >= alvo:
                px = alvo
            elif s["max_dias"] and dias + 1 >= s["max_dias"]:
                px = C[t]
            aluguel += base * btc_dia
            if px is not None:
                eq = base + units * (px - E) - custo * units * abs(px) - aluguel
                trades.append((i_ent, t, eq / eq_entrada - 1))
                em, saiu_hoje = False, True
            else:
                dias += 1
                tr = s["trail"][t]
                if not math.isnan(tr) and (math.isnan(stop) or tr > stop):
                    stop = tr
                ad = s["alvo_dyn"][t]
                if not math.isnan(ad):
                    alvo = ad
                eq = base + units * (C[t] - E) - aluguel
                pos[t] = True
        if not em and not saiu_hoje and s["entrada"][t - 1]:
            px = None
            if not usa_nivel:
                px = O[t]
            else:
                nv = s["nivel"][t - 1]
                if not math.isnan(nv) and H[t] >= nv:
                    px = max(O[t], nv)
            if px is not None:
                eq_entrada = eq
                base = eq * (1 - custo)
                E, units = px, base / abs(px)
                stop, alvo = s["stop"][t - 1], s["alvo"][t - 1]
                if math.isnan(alvo):
                    alvo = s["alvo_dyn"][t - 1]
                if not math.isnan(stop) and stop >= px:
                    stop = math.nan
                dias, i_ent, aluguel = 0, t, 0.0
                if not math.isnan(stop) and L[t] <= stop:      # stopado no dia da entrada
                    eq = base + units * (stop - E) - custo * units * abs(stop)
                    trades.append((t, t, eq / eq_entrada - 1))
                else:
                    em = True
                    eq = base + units * (C[t] - E)
                    pos[t] = True
        if eq <= 0:                       # ruína: perdeu todo o capital do ativo
            ret[t] = -1.0
            ret[t + 1:] = 0.0
            if em:
                trades.append((i_ent, t, -1.0))
            break
        ret[t] = eq / eq_ant - 1
    return ret, pos, trades


def buy_and_hold(df, i0, custo):
    O, C = df.open.to_numpy(float), df.close.to_numpy(float)
    ret = np.full(len(C), np.nan)
    ret[i0] = C[i0] / O[i0] * (1 - custo) - 1
    ret[i0 + 1:] = C[i0 + 1:] / C[i0:-1] - 1
    pos = np.zeros(len(C), bool)
    pos[i0:] = True
    return ret, pos, [(i0, len(C) - 1, float(np.nanprod(1 + ret) - 1))]


def metricas(r: pd.Series, cdi: pd.Series) -> dict:
    r = r.dropna()
    if r.empty:
        return {}
    c = cdi.reindex(r.index).fillna(0.0)
    anos = len(r) / 252
    total = max(float((1 + r).prod()), 0.0)
    total_cdi = float((1 + c).prod())
    eq = (1 + r).cumprod()
    dd = float((eq / eq.cummax() - 1).min())
    exc = r - c
    sharpe = float(exc.mean() / exc.std() * math.sqrt(252)) if exc.std() > 0 else 0.0
    return {
        "cagr": total ** (1 / anos) - 1,
        "cagr_cdi": total_cdi ** (1 / anos) - 1,
        "excesso_aa": total ** (1 / anos) - total_cdi ** (1 / anos),
        "retorno_total": total - 1,
        "dd_max": dd,
        "sharpe": sharpe,
    }
