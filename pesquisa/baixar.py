"""Baixa cotações AJUSTADAS (proventos e desdobramentos) e o CDI diário do BCB."""
import json
import sys
import urllib.request
from pathlib import Path

import pandas as pd
import yfinance as yf

PASTA = Path("dados_cache/pesquisa")
INICIO = "2015-06-01"
CANDIDATOS = [
    "PETR4", "PETR3", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "B3SA3", "WEGE3", "RENT3",
    "SUZB3", "ITSA4", "GGBR4", "GOAU4", "CSNA3", "USIM5", "LREN3", "RADL3", "EQTL3", "CMIG4",
    "SBSP3", "PRIO3", "EMBJ3", "CPLE3", "VIVT3", "HYPE3", "CYRE3", "MGLU3", "KLBN11", "TOTS3",
    "BBSE3", "CSAN3", "UGPA3", "MULT3", "ENEV3", "SANB11", "BRAP4", "CPFE3", "EGIE3", "TAEE11",
    "MRVE3", "BRKM5", "ELET6", "JBSS32", "BPAC11", "RAIL3", "FLRY3",
]


def baixar_ativo(t):
    s = t if t.startswith("^") else f"{t}.SA"
    d = yf.download(s, start=INICIO, auto_adjust=True, progress=False, threads=False)
    if d is None or d.empty:
        return None
    if isinstance(d.columns, pd.MultiIndex):
        d.columns = d.columns.get_level_values(0)
    d = d.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
    return d[(d.close > 0) & (d.high >= d.low)]


def baixar_cdi():
    partes = []
    for ini, fim in [("01/01/2015", "31/12/2020"), ("01/01/2021", "31/12/2026")]:
        url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados?formato=json&dataInicial={ini}&dataFinal={fim}"
        dados = json.load(urllib.request.urlopen(url, timeout=60))
        partes += dados
    s = pd.Series({pd.to_datetime(x["data"], dayfirst=True): float(x["valor"]) / 100 for x in partes})
    return s.sort_index()


if __name__ == "__main__":
    PASTA.mkdir(parents=True, exist_ok=True)
    baixar_cdi().to_csv(PASTA / "_CDI.csv", header=["cdi"])
    for t in CANDIDATOS + ["^BVSP"]:
        d = baixar_ativo(t)
        if d is None:
            print(f"{t}: sem dados", file=sys.stderr)
            continue
        d.to_csv(PASTA / f"{t.replace('^', '_')}.csv")
        print(f"{t}: {len(d)} pregões {d.index[0].date()} a {d.index[-1].date()}")
