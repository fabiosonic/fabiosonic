"""Testa todos os setups (long e short) no universo de ações e gera o relatório.

Uso:  python pesquisa/baixar.py   (uma vez)
      python pesquisa/rodar.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pesquisa.motor_pesquisa import (AQUECIMENTO, buy_and_hold, carregar_universo,  # noqa: E402
                                     espelhar, metricas, simular)
from pesquisa.setups import SETUPS  # noqa: E402

INICIO = pd.Timestamp("2016-11-07")
FIM = pd.Timestamp("2026-11-06")
METADE = pd.Timestamp("2021-11-08")
CUSTO_LADO = 0.0010     # 0,10% por lado: emolumentos B3 (~0,03%) + slippage; corretagem zero
BTC_AA = 0.02           # aluguel de ações para o short: 2% a.a. (ativos líquidos)
SAIDA = Path("relatorios")


def carteira_anual(R: pd.DataFrame) -> pd.Series:
    """Capital dividido igualmente entre os ativos e rebalanceado 1x por ano.
    (Rebalancear todo dia dá peso igual a fatias quase zeradas e distorce o resultado.)"""
    partes = []
    for _, bloco in R.groupby(R.index.year):
        cresc = (1 + bloco).cumprod().mean(axis=1)
        partes.append(cresc / cresc.shift(1, fill_value=1.0) - 1)
    return pd.concat(partes)


def rodar_setup(nome, func, vendido, ativos, cdi):
    rets, poss, trades = {}, {}, []
    for t, df in ativos.items():
        df = df.loc[:FIM]
        validos = np.where(df.index >= INICIO)[0]
        if not len(validos):
            continue
        i0 = max(int(validos[0]), AQUECIMENTO)
        if i0 >= len(df) - 1:
            continue
        if func is None:
            r, p, tr = buy_and_hold(df, i0, CUSTO_LADO)
        else:
            base = espelhar(df) if vendido else df
            r, p, tr = simular(base, func(base), i0, CUSTO_LADO, BTC_AA, vendido)
        rets[t] = pd.Series(r, index=df.index)
        poss[t] = pd.Series(p, index=df.index)
        trades += [(t, df.index[a], df.index[b], x) for a, b, x in tr]
    R = pd.DataFrame(rets).loc[INICIO:FIM]
    P = pd.DataFrame(poss).reindex(R.index).fillna(False).astype(bool)
    c = cdi.reindex(R.index).fillna(0.0)
    # caixa parado rende CDI; no short a garantia (capital) rende CDI o tempo todo
    caixa = (~P).astype(float) if not vendido else pd.DataFrame(1.0, index=R.index, columns=R.columns)
    R_cdi = R + caixa.mul(c, axis=0).where(R.notna())
    # ativo ainda não listado/aquecendo: a fatia dele fica no CDI (ou parada, na versão bruta)
    carteira = carteira_anual(R_cdi.apply(lambda col: col.fillna(c)))
    carteira_bruta = carteira_anual(R.fillna(0.0))

    m = metricas(carteira, c)
    m1 = metricas(carteira.loc[:METADE - pd.Timedelta(days=1)], c)
    m2 = metricas(carteira.loc[METADE:], c)
    mb = metricas(carteira_bruta, c)
    por_ativo = []
    for t in R_cdi.columns:
        mt = metricas(R_cdi[t], c)
        if mt:
            por_ativo.append(mt["excesso_aa"])
    x = np.array([tr[3] for tr in trades]) if trades else np.array([0.0])
    ganhos, perdas = x[x > 0].sum(), -x[x <= 0].sum()
    dias = np.array([(tr[2] - tr[1]).days for tr in trades]) if trades else np.array([0])
    return {
        "setup": nome, "lado": "Vendido (short)" if vendido else "Comprado (long)",
        "categoria": SETUPS[nome][0] if nome in SETUPS else "Referência",
        "cagr_com_cdi": m["cagr"], "cdi_aa": m["cagr_cdi"], "excesso_cdi_aa": m["excesso_aa"],
        "cagr_so_operacoes": mb["cagr"], "retorno_total": m["retorno_total"],
        "dd_max": m["dd_max"], "sharpe_vs_cdi": m["sharpe"],
        "excesso_1a_metade": m1["excesso_aa"], "excesso_2a_metade": m2["excesso_aa"],
        "pct_ativos_batem_cdi": float(np.mean(np.array(por_ativo) > 0)) if por_ativo else 0.0,
        "trades": len(trades), "acerto": float((x > 0).mean()) if trades else 0.0,
        "media_trade": float(x.mean()), "fator_lucro": float(ganhos / perdas) if perdas > 0 else np.nan,
        "duracao_media_dias": float(dias.mean()), "exposicao": float(P.values.mean()),
    }, carteira


def bateria(ativos, cdi, rotulo):
    linhas, curvas = [], {}
    tarefas = [("Buy & hold", None, False)]
    tarefas += [(n, f, v) for n, (_, f) in SETUPS.items() for v in (False, True)]
    for nome, func, vendido in tarefas:
        linha, curva = rodar_setup(nome, func, vendido, ativos, cdi)
        linha["universo"] = rotulo
        linhas.append(linha)
        curvas[f"{nome} | {linha['lado']}"] = curva
    return pd.DataFrame(linhas).sort_values("excesso_cdi_aa", ascending=False), curvas


def main():
    t0 = time.time()
    ativos, cdi, ibov = carregar_universo()
    ibov_ohlc = pd.read_csv("dados_cache/pesquisa/_BVSP.csv", index_col=0, parse_dates=True)
    ibov_ohlc = ibov_ohlc[ibov_ohlc.high > ibov_ohlc.low]
    print(f"{len(ativos)} ativos | {INICIO.date()} a {FIM.date()}")
    SAIDA.mkdir(exist_ok=True)
    res_acoes, curvas = bateria(ativos, cdi, "44 ações")
    res_ibov, curvas_ibov = bateria({"IBOV": ibov_ohlc}, cdi, "Ibovespa")
    res = pd.concat([res_acoes, res_ibov])
    res.to_csv(SAIDA / "ranking_setups.csv", index=False, float_format="%.5f")
    eq = (1 + pd.DataFrame(curvas).fillna(0)).cumprod()
    eq["CDI"] = (1 + cdi.reindex(eq.index).fillna(0)).cumprod()
    eq["Ibovespa"] = ibov.reindex(eq.index).ffill() / ibov.loc[INICIO:].iloc[0]
    eq.to_csv(SAIDA / "curvas_patrimonio.csv", float_format="%.5f")
    cols = ["setup", "lado", "excesso_cdi_aa", "dd_max", "excesso_1a_metade", "excesso_2a_metade", "trades"]
    with pd.option_context("display.width", 200, "display.max_rows", 100):
        print(res_acoes[cols].to_string(index=False))
        print(res_ibov[cols].to_string(index=False))
    print(f"Concluído em {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
