"""Histórico diário longo para o b3-backtest: baixa do Yahoo desde 2000 (ou a
data pedida), ajusta abertura, máxima, mínima e fechamento pelo fator de
proventos e desdobramentos (adjclose / close) e guarda em
trader-b3/cache/historico/<TICKER>.json.gz.

Com preços ajustados por proventos, o comprado recebe os dividendos e o
vendido paga, como acontece com quem vende a descoberto e reembolsa o doador.
"""

import datetime
import gzip
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

IBOV = "^BVSP"


def pasta():
    return b3lib.caminho("cache", "historico")


def arquivo(sym):
    return os.path.join(pasta(), sym.replace("^", "_") + ".json.gz")


def url(sym, desde):
    p1 = int((datetime.datetime.combine(desde, datetime.time()) - b3lib.EPOCH).total_seconds())
    p2 = int(time.time()) + 86400
    ysym = sym if sym.startswith("^") else b3lib.yahoo(sym)
    return ("/v8/finance/chart/%s?period1=%d&period2=%d&interval=1d&events=div%%2Csplits&includeAdjustedClose=true"
            % (ysym.replace("^", "%5E"), p1, p2))


def converter(texto, sym):
    """JSON do Yahoo -> {"symbol", "d": [ordinal], "o","h","l","c","v"} ajustados."""
    doc = json.loads(texto)
    res = ((doc.get("chart") or {}).get("result") or [None])[0]
    if not res or not res.get("timestamp"):
        raise b3lib.B3Erro("sem histórico para %s" % sym)
    q = res["indicators"]["quote"][0]
    adj = ((res["indicators"].get("adjclose") or [{}])[0] or {}).get("adjclose") or q["close"]
    out = {"symbol": sym, "d": [], "o": [], "h": [], "l": [], "c": [], "v": []}
    for i, t in enumerate(res["timestamp"]):
        c, a = q["close"][i], adj[i]
        o, h, l, v = q["open"][i], q["high"][i], q["low"][i], q["volume"][i]
        if None in (c, a, o, h, l) or c <= 0 or l <= 0:
            continue
        f = a / c
        dia = b3lib.ts_para_brt(t).date()
        if out["d"] and dia.toordinal() <= out["d"][-1]:
            continue
        out["d"].append(dia.toordinal())
        out["o"].append(round(o * f, 6))
        out["h"].append(round(max(h, o, c) * f, 6))
        out["l"].append(round(min(l, o, c) * f, 6))
        out["c"].append(round(a, 6))
        out["v"].append(int((v or 0) / f) if f else 0)   # volume em ações ajustadas
    return out


def baixar(syms, desde=datetime.date(2000, 1, 1), forcar=False, log=print):
    os.makedirs(pasta(), exist_ok=True)
    ok, falhas = [], {}
    for i, s in enumerate(syms):
        p = arquivo(s)
        if os.path.exists(p) and not forcar and time.time() - os.path.getmtime(p) < 20 * 3600:
            ok.append(s)
            continue
        try:
            doc = converter(b3lib.yahoo_get(url(s, desde)), s)
            with gzip.open(p, "wt", encoding="utf-8") as f:
                json.dump(doc, f, separators=(",", ":"))
            ok.append(s)
        except (b3lib.B3Erro, ValueError, KeyError) as e:
            falhas[s] = str(e)
        if log and (i + 1) % 20 == 0:
            log("  %d de %d ativos" % (i + 1, len(syms)))
    return ok, falhas


def carregar(sym, base=None):
    p = os.path.join(base, os.path.basename(arquivo(sym))) if base else arquivo(sym)
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


CDI_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4391/dados?formato=json&dataInicial=01/01/%d&dataFinal=%s"


def baixar_cdi(desde_ano=2000):
    """CDI mensal (% ao mês) do Banco Central, série SGS 4391 -> {(ano, mês): taxa}."""
    p = os.path.join(pasta(), "cdi.json")
    if not (os.path.exists(p) and time.time() - os.path.getmtime(p) < 20 * 3600):
        hoje = datetime.date.today().strftime("%d/%m/%Y")
        texto = b3lib.http_get(CDI_URL % (desde_ano, hoje), timeout=60).decode("utf-8")
        json.loads(texto)
        os.makedirs(pasta(), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(texto)
    return ler_cdi(p)


def ler_cdi(p=None):
    p = p or os.path.join(pasta(), "cdi.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return {(int(x["data"][6:]), int(x["data"][3:5])): float(x["valor"]) for x in json.load(f)}
