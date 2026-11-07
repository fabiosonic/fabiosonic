"""Cotações diárias da B3 (Yahoo Finance, sufixo .SA) com cache local em CSV.

Usa preços NÃO ajustados (são os preços que de fato aparecem no book e nas ordens).
Atenção: desdobramentos/grupamentos distorcem o histórico; confira eventos
corporativos dos ativos da lista.
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd

COLUNAS = ["open", "high", "low", "close", "volume"]


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[COLUNAS].dropna(subset=["open", "high", "low", "close"])
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df[(df["close"] > 0) & (df["high"] >= df["low"])]


def baixar(ticker: str, inicio: str, pasta_cache: str | Path = "dados_cache", forcar: bool = False) -> pd.DataFrame:
    pasta = Path(pasta_cache)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f"{ticker}.csv"
    cache_recente = arquivo.exists() and arquivo.stat().st_mtime > dt.datetime.now().timestamp() - 3600 * 6
    if cache_recente and not forcar:
        return normalizar(pd.read_csv(arquivo, index_col=0, parse_dates=True))
    try:
        import yfinance as yf
    except ImportError as e:  # pragma: no cover
        raise SystemExit("Instale as dependências: pip install -r requirements.txt") from e
    bruto = yf.download(f"{ticker}.SA", start=inicio, end=None, auto_adjust=False,
                        progress=False, threads=False)
    if bruto is None or bruto.empty:
        raise RuntimeError(f"Sem dados para {ticker} (ticker correto? conexão?)")
    df = normalizar(bruto)
    df.to_csv(arquivo)
    return df


def historicos(tickers: list[str], inicio: str, ate: str | None = None,
               pasta_cache: str | Path = "dados_cache") -> dict[str, pd.DataFrame]:
    """Baixa todos os ativos. `ate` (exclusivo) corta o pregão em andamento."""
    saida = {}
    for t in tickers:
        df = baixar(t, inicio, pasta_cache)
        if ate:
            df = df[df.index < pd.Timestamp(ate)]
        saida[t] = df
    return saida
