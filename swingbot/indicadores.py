"""Indicadores técnicos (pandas puro, sem dependências externas)."""
from __future__ import annotations

import pandas as pd


def mms(serie: pd.Series, periodo: int) -> pd.Series:
    """Média móvel simples."""
    return serie.rolling(periodo, min_periods=periodo).mean()


def mme(serie: pd.Series, periodo: int) -> pd.Series:
    """Média móvel exponencial (alfa = 2 / (n + 1))."""
    return serie.ewm(span=periodo, adjust=False, min_periods=periodo).mean()


def atr(df: pd.DataFrame, periodo: int = 14) -> pd.Series:
    """Average True Range (suavização de Wilder)."""
    fechamento_anterior = df["close"].shift(1)
    tr = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - fechamento_anterior).abs(),
            (df["low"] - fechamento_anterior).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()


def ifr(serie: pd.Series, periodo: int = 14) -> pd.Series:
    """Índice de Força Relativa (RSI de Wilder)."""
    delta = serie.diff()
    ganho = delta.clip(lower=0).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    perda = (-delta.clip(upper=0)).ewm(alpha=1 / periodo, adjust=False, min_periods=periodo).mean()
    rs = ganho / perda
    return 100 - 100 / (1 + rs)
