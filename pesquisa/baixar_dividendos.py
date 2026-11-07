"""Baixa cotações NÃO ajustadas e dividendos/JCP pagos (para o dividend yield)."""
from pathlib import Path

import pandas as pd
import yfinance as yf

PASTA = Path("dados_cache/pesquisa/brutos")

if __name__ == "__main__":
    PASTA.mkdir(parents=True, exist_ok=True)
    nomes = [f.stem for f in Path("dados_cache/pesquisa").glob("*.csv") if not f.stem.startswith("_")]
    for t in sorted(nomes):
        h = yf.Ticker(f"{t}.SA").history(start="2015-06-01", auto_adjust=False, actions=True)
        if h.empty:
            print(t, "sem dados")
            continue
        h.index = pd.to_datetime(h.index).tz_localize(None).normalize()
        h[["Close", "Dividends", "Stock Splits"]].to_csv(PASTA / f"{t}.csv")
        print(f"{t}: {int((h.Dividends > 0).sum())} pagamentos de proventos")
