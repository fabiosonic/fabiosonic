"""Consenso de analistas (sell-side) por ação: recomendação média, preço-alvo e distribuição.

Fonte: Yahoo Finance, que consolida as estimativas de bancos e corretoras que cobrem
cada papel (dados LSEG/Refinitiv). Escala da recomendação média: 1 = compra forte,
2 = compra, 3 = neutro, 4 = venda, 5 = venda forte.
"""
import datetime as dt
import json
from pathlib import Path

import yfinance as yf

PASTA = Path("dados_cache/pesquisa")


def consenso(ticker: str) -> dict | None:
    tk = yf.Ticker(f"{ticker}.SA")
    info = tk.info or {}
    if not info.get("numberOfAnalystOpinions"):
        return None
    dist = {}
    try:
        r = tk.recommendations_summary
        if r is not None and not r.empty:
            atual = r[r["period"] == "0m"].iloc[0]
            dist = {k: int(atual[k]) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    except Exception:
        pass
    return {
        "recomendacao": info.get("recommendationKey"),
        "nota_media": info.get("recommendationMean"),
        "analistas": info.get("numberOfAnalystOpinions"),
        "alvo_medio": info.get("targetMeanPrice"),
        "alvo_max": info.get("targetHighPrice"),
        "alvo_min": info.get("targetLowPrice"),
        "preco": info.get("currentPrice") or info.get("regularMarketPrice"),
        "distribuicao": dist,
        "setor": info.get("sector"),
        "nome": info.get("shortName"),
    }


if __name__ == "__main__":
    nomes = sorted(f.stem for f in PASTA.glob("*.csv") if not f.stem.startswith("_"))
    saida = {"atualizado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "ativos": {}}
    for t in nomes:
        try:
            c = consenso(t)
        except Exception as e:  # noqa: BLE001
            print(t, "erro", e)
            continue
        if c:
            saida["ativos"][t] = c
            print(f"{t}: {c['recomendacao']} ({c['analistas']} analistas) alvo {c['alvo_medio']}")
    (PASTA / "_consenso.json").write_text(json.dumps(saida, indent=2, ensure_ascii=False), encoding="utf-8")
