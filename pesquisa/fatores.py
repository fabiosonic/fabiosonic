"""Estudo de seleção de ações por fatores (carteira long-only rebalanceada).

Pergunta: QUAIS ações comprar (e não QUANDO entrar). A cada fim de mês as ações
são ranqueadas por um critério; compram-se as N melhores com pesos iguais.

Execução sem olhar o futuro: sinal no fechamento do último pregão do mês,
compra/venda no fechamento do pregão seguinte, custos de 0,10% sobre o giro.

IR (pessoa física): simulado mês a mês com custo médio por ativo, isenção para
vendas de ações até R$ 20 mil no mês, compensação de prejuízo, alíquota de 15%
e dividendos isentos (abaixo de R$ 50 mil/mês por empresa — Lei 15.270/2025).
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from pesquisa.motor_pesquisa import EXCLUIDOS, metricas

PASTA = Path("dados_cache/pesquisa")
CUSTO = 0.0010
ISENCAO = 20000.0
ALIQ = 0.15


def carregar_paineis():
    fech, brutos, divs = {}, {}, {}
    for f in sorted(PASTA.glob("*.csv")):
        t = f.stem
        if t.startswith("_") or t in EXCLUIDOS:
            continue
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        fech[t] = d.loc[d.volume > 0, "close"]
        b = PASTA / "brutos" / f"{t}.csv"
        if b.exists():
            x = pd.read_csv(b, index_col=0, parse_dates=True)
            brutos[t], divs[t] = x["Close"], x["Dividends"]
    C = pd.DataFrame(fech).sort_index()
    datas = C.index
    C = C.ffill(limit=5)
    U = pd.DataFrame(brutos).reindex(datas).ffill(limit=5)
    D = pd.DataFrame(divs).reindex(datas).fillna(0.0)
    cdi = pd.read_csv(PASTA / "_CDI.csv", index_col=0, parse_dates=True)["cdi"].reindex(datas).fillna(0.0)
    ibov = pd.read_csv(PASTA / "_BVSP.csv", index_col=0, parse_dates=True)["close"].reindex(datas).ffill()
    return C, U, D, cdi, ibov


# ----------------------------------------------------------------------------- fatores
def _rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True)


def sinais(C, U, D, i):
    """Escores (maior = melhor) de cada fator no pregão de índice i."""
    hist = C.iloc[: i + 1]
    elegiveis = hist.columns[hist.notna().sum() >= 273]
    elegiveis = [t for t in elegiveis if not math.isnan(C.iloc[i][t])]
    c = C[elegiveis]
    r = c.iloc[i - 252: i + 1].pct_change()
    mom12 = c.iloc[i - 21] / c.iloc[i - 252] - 1
    mom6 = c.iloc[i - 21] / c.iloc[i - 126] - 1
    vol = r.std()
    dy = D[elegiveis].iloc[i - 251: i + 1].sum() / U[elegiveis].iloc[i]
    rev = -(c.iloc[i] / c.iloc[i - 21] - 1)
    return {
        "Momentum 12-1": mom12,
        "Momentum 6-1": mom6,
        "Baixa volatilidade": -vol,
        "Dividend yield": dy,
        "Reversão de 1 mês": rev,
        "Momentum + baixa vol.": _rank(mom12) + _rank(-vol),
        "Momentum + dividendos": _rank(mom12) + _rank(dy),
        "Baixa vol. + dividendos": _rank(-vol) + _rank(dy),
        "Universo inteiro (peso igual)": pd.Series(1.0, index=elegiveis),
    }


def datas_rebalanceamento(idx: pd.DatetimeIndex, inicio, meses: int = 1):
    s = pd.Series(range(len(idx)), index=idx)
    fim_mes = s.groupby([idx.year, idx.month]).max()
    pos = [p for p in fim_mes.values if idx[p] >= inicio and p + 1 < len(idx)]
    return pos[::meses]


# ----------------------------------------------------------------------------- simulação
def simular(C, U, D, cdi, ibov, fator, inicio, fim, n=10, meses=1, capital=None, filtro_mercado=False):
    """Carteira do fator. Se `capital` for informado, desconta o IR mês a mês."""
    C = C.loc[:fim]
    idx = C.index
    R = C.pct_change().fillna(0.0)
    q = (D / U.shift(1)).reindex(columns=C.columns).fillna(0.0)     # dividendo do dia / preço
    mm200 = ibov.rolling(200).mean()
    reb = set(datas_rebalanceamento(idx, inicio, meses))
    i0 = min(reb)
    h = pd.Series(0.0, index=C.columns)      # valor por ativo
    b = pd.Series(0.0, index=C.columns)      # custo de aquisição (base fiscal)
    caixa = float(capital or 1.0)
    alvo_pend = None
    eq = []
    giro_total = 0.0
    vendas_mes = ganho_mes = prejuizo = 0.0
    impostos = 0.0
    mes_atual = None
    for i in range(i0 + 1, len(idx)):
        d = idx[i]
        # 1) mercado do dia: ações variam, dividendos reinvestidos entram na base fiscal, caixa rende CDI
        r = R.iloc[i]
        b += h * q.iloc[i]
        h *= 1 + r
        caixa *= 1 + cdi.iloc[i]
        # 2) apuração do IR na virada do mês
        if mes_atual is not None and (d.year, d.month) != mes_atual and capital:
            if vendas_mes > ISENCAO:
                base = ganho_mes - prejuizo
                if base > 0:
                    imposto = ALIQ * base
                    prejuizo = 0.0
                    caixa -= imposto
                    impostos += imposto
                else:
                    prejuizo = -base
            elif ganho_mes < 0:
                prejuizo -= ganho_mes   # prejuízo compensa mesmo em mês isento
            vendas_mes = ganho_mes = 0.0
        mes_atual = (d.year, d.month)
        # 3) rebalanceamento (decidido no pregão anterior)
        if alvo_pend is not None:
            total = h.sum() + caixa
            alvo = alvo_pend * total
            delta = alvo - h
            vendas = (-delta).clip(lower=0)
            compras = delta.clip(lower=0)
            if capital:
                frac = (vendas / h.where(h > 0)).fillna(0.0)
                ganho_mes += float((frac * (h - b)).sum())
                vendas_mes += float(vendas.sum())
                b -= frac * b
            b += compras
            giro = float(vendas.sum() + compras.sum())
            giro_total += giro / total
            caixa += float(vendas.sum() - compras.sum()) - giro * CUSTO
            h = alvo.copy()
            alvo_pend = None
        eq.append(h.sum() + caixa)
        # 4) decide o próximo rebalanceamento no fechamento de hoje
        if i in reb:
            esc = sinais(C, U, D, i)[fator].dropna()
            w = pd.Series(0.0, index=C.columns)
            if not (filtro_mercado and ibov.iloc[i] < mm200.iloc[i]):
                escolhidas = esc.sort_values(ascending=False).index[: (n if n else len(esc))]
                w[escolhidas] = 1.0 / len(escolhidas)
            alvo_pend = w
    eq = pd.Series(eq, index=idx[i0 + 1:])
    ret = eq.pct_change().fillna(eq.iloc[0] / float(capital or 1.0) - 1)
    anos = len(ret) / 252
    return ret, {"giro_aa": giro_total / anos, "impostos": impostos}


def estatistica_t(ret, ref):
    """t da diferença mensal de retornos (fator - referência)."""
    m = (1 + ret).resample("ME").prod() - (1 + ref.reindex(ret.index).fillna(0)).resample("ME").prod()
    return float(m.mean() / m.std() * math.sqrt(len(m))) if m.std() > 0 else 0.0


def resumo(ret, cdi, ew, metade):
    m = metricas(ret, cdi)
    a = metricas(ret.loc[:metade - pd.Timedelta(days=1)], cdi)
    z = metricas(ret.loc[metade:], cdi)
    ew_m = metricas(ew, cdi)
    return {
        "cagr": m["cagr"], "excesso_cdi": m["excesso_aa"], "excesso_universo": m["cagr"] - ew_m["cagr"],
        "excesso_cdi_1a": a["excesso_aa"], "excesso_cdi_2a": z["excesso_aa"],
        "dd_max": m["dd_max"], "sharpe_vs_cdi": m["sharpe"],
        "t_vs_cdi": estatistica_t(ret, cdi), "t_vs_universo": estatistica_t(ret, ew),
    }
