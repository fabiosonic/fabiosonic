"""Backtest diário usando exatamente o motor e o simulador do robô."""
from __future__ import annotations

import math

import pandas as pd

from . import motor
from .carteira import Carteira
from .config import Config
from .estrategia import criar
from .modelos import ResultadoBacktest
from .simulador import executar_dia


def rodar(cfg: Config, historicos: dict[str, pd.DataFrame], inicio: str | None = None) -> ResultadoBacktest:
    estrategia = criar(cfg.estrategia)
    carteira = Carteira(cfg.risco.capital_teste, cfg.risco.custo_percentual)
    datas = sorted(set().union(*[set(df.index) for df in historicos.values()]))
    if inicio:
        datas = [d for d in datas if d >= pd.Timestamp(inicio)]
    res = ResultadoBacktest()
    for i, d in enumerate(datas):
        data = d.date().isoformat()
        barras = {t: df.loc[d] for t, df in historicos.items() if d in df.index}
        executar_dia(carteira, barras, data)
        proxima = datas[i + 1].date().isoformat() if i + 1 < len(datas) else None
        ordens, _ = motor.planejar(cfg, estrategia, carteira, historicos, data, proxima)
        carteira.pendentes = ordens
        precos = {t: float(b["close"]) for t, b in barras.items()}
        res.patrimonio.append((data, carteira.patrimonio(precos)))
    res.operacoes = carteira.operacoes
    res.trades = carteira.trades
    return res


def metricas(res: ResultadoBacktest, capital: float) -> dict:
    if not res.patrimonio:
        return {}
    serie = pd.Series([v for _, v in res.patrimonio], index=pd.to_datetime([d for d, _ in res.patrimonio]))
    final = float(serie.iloc[-1])
    anos = max((serie.index[-1] - serie.index[0]).days / 365.25, 1 / 365.25)
    pico = serie.cummax()
    dd = float(((serie - pico) / pico).min())
    resultados = [t["resultado"] for t in res.trades]
    ganhos = [r for r in resultados if r > 0]
    perdas = [r for r in resultados if r <= 0]
    retornos = serie.pct_change().dropna()
    sharpe = float(retornos.mean() / retornos.std() * math.sqrt(252)) if retornos.std() > 0 else 0.0
    return {
        "capital_inicial": capital,
        "patrimonio_final": round(final, 2),
        "retorno_total_%": round((final / capital - 1) * 100, 2),
        "retorno_anual_%": round(((final / capital) ** (1 / anos) - 1) * 100, 2),
        "drawdown_maximo_%": round(dd * 100, 2),
        "sharpe": round(sharpe, 2),
        "trades": len(resultados),
        "taxa_acerto_%": round(len(ganhos) / len(resultados) * 100, 1) if resultados else 0.0,
        "fator_lucro": round(sum(ganhos) / abs(sum(perdas)), 2) if perdas and sum(perdas) else None,
        "day_trades_por_stop": sum(1 for t in res.trades if t["day_trade"]),
    }
