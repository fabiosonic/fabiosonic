#!/usr/bin/env python3
"""Scanner de gráficos da B3 para b3-scanner. Só biblioteca padrão.

    python3 scan.py universo                       # carteira do IBRA -> trader-b3/universo.txt
    python3 scan.py universo --indice IBXX         # IBOV, IBXX (IBrX-100), IBRA, SMLL, IDIV...
    python3 scan.py diario                         # antes da abertura -> trader-b3/watchlist.json
    python3 scan.py diario --symbols PETR4,VALE3,ITUB4
    python3 scan.py orb                            # depois das 10h20: rompimentos da faixa de abertura
    python3 scan.py orb --at 10:45 --or-minutes 15

Setups diários (fechamentos de pregões completos, os mesmos do day-trader-skill):
  rompimento_20d   fechamento acima da máxima de fechamento dos 20 pregões anteriores
  bandeira_alta    alta de mais de 10% entre 15 e 5 pregões atrás e faixa dos
                   últimos 5 fechamentos menor que 5% do preço
  retomou_mm20     fechou abaixo da média de 20 ontem e acima dela hoje
  sobrevendido     IFR(14) de Wilder abaixo de 30
  repique          IFR(14) de ontem abaixo de 30 e fechamento de hoje acima do de ontem

ORB (opening-range breakout) em candles de 5 minutos: a faixa é a máxima e a
mínima dos primeiros --or-minutes (padrão 15: candles das 10h00, 10h05 e
10h10). Sinal = primeiro candle COMPLETO depois da faixa que FECHA acima da
máxima. Pavio acima não conta.

Liquidez: --min-preco (padrão R$ 1,00) e --min-volume-fin, a média do volume
financeiro dos últimos 20 pregões (padrão R$ 5 milhões no diário).

Dados: Yahoo Finance (gratuito, não oficial, com atraso possível), sufixo .SA;
carteira teórica dos índices no site da B3. --offline PASTA lê arquivos salvos
(universo: o JSON da B3; diario/orb: <TICKER>.json do v8 chart).
Código de saída 0 quando achou algo, 1 quando não achou ou não conseguiu rodar.
"""

import argparse
import base64
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402

B3_INDICE = "https://sistemaswebb3-listados.b3.com.br/indexProxy/indexCall/GetPortfolioDay/"
MIN_PREGOES = 30
PASSO = 300


# ---------------------------------------------------------------- universo

def url_indice(indice):
    q = {"language": "pt-br", "pageNumber": 1, "pageSize": 500, "index": indice, "segment": "1"}
    return B3_INDICE + base64.b64encode(json.dumps(q, separators=(",", ":")).encode()).decode()


def ler_indice(texto):
    doc = json.loads(texto)
    linhas = []
    for r in doc.get("results") or []:
        cod = b3lib.normalizar(r.get("cod"))
        if b3lib.valido(cod):
            linhas.append((cod, (r.get("asset") or "").strip(), (r.get("type") or "").split()[0:1]))
    if not linhas:
        raise b3lib.B3Erro("a B3 não devolveu a carteira do índice")
    return sorted({c: (c, n, t[0] if t else "") for c, n, t in linhas}.values())


def ler_universo(path):
    if not os.path.exists(path):
        raise b3lib.B3Erro("não há %s: rode `scan.py universo` antes, ou passe --symbols" % path)
    out = []
    with open(path, encoding="utf-8") as f:
        for linha in f:
            s = linha.split("|")[0].strip()
            if s and not s.startswith("#"):
                out.append(b3lib.normalizar(s))
    return out


def simbolos(a):
    if a.symbols:
        return [b3lib.normalizar(s) for s in a.symbols.split(",") if s.strip()]
    if a.watchlist:
        doc = b3lib.ler_json(a.watchlist, obrigatorio=True, o_que="a watchlist")
        return [h["symbol"] for h in doc.get("hits") or []]
    syms = ler_universo(a.universo)
    return syms[:a.limit] if a.limit else syms


# ---------------------------------------------------------------- setups diários

def ifr(fech, n=14):
    """IFR (RSI) de Wilder."""
    if len(fech) < n + 1:
        return None
    g = [max(0.0, fech[i] - fech[i - 1]) for i in range(1, len(fech))]
    p = [max(0.0, fech[i - 1] - fech[i]) for i in range(1, len(fech))]
    mg, mp = sum(g[:n]) / n, sum(p[:n]) / n
    for i in range(n, len(g)):
        mg = (mg * (n - 1) + g[i]) / n
        mp = (mp * (n - 1) + p[i]) / n
    return 100 - 100 / (1 + mg / mp) if mp else 100.0


def setups(c):
    """fechamentos (mais antigo primeiro, >= 30) -> (setups, números)."""
    ultimo = c[-1]
    max20 = max(c[-21:-1])
    mm20 = sum(c[-20:]) / 20.0
    mm20_ant = sum(c[-21:-1]) / 20.0
    alta = c[-6] / c[-16] - 1
    faixa5 = (max(c[-5:]) - min(c[-5:])) / ultimo
    r, r_ant = ifr(c), ifr(c[:-1])
    tags = []
    if ultimo > max20:
        tags.append("rompimento_20d")
    if alta > 0.10 and faixa5 < 0.05:
        tags.append("bandeira_alta")
    if c[-2] < mm20_ant and ultimo > mm20:
        tags.append("retomou_mm20")
    if r is not None and r < 30:
        tags.append("sobrevendido")
    if r_ant is not None and r_ant < 30 and ultimo > c[-2]:
        tags.append("repique")
    return tags, {"ifr": r, "max20": max20, "mm20": mm20}


def pregoes_completos(chart, agora_utc, cfg):
    """[(data, fechamento, volume financeiro)] sem o pregão de hoje enquanto aberto."""
    agora = b3lib.para_brt(agora_utc)
    hoje = agora.date()
    s = b3lib.sessao(hoje, cfg)
    hoje_ok = s is None or agora.time() >= b3lib.mais_min(hoje, s[1], 5)
    out = {}
    for b in chart["bars"]:
        d = b3lib.ts_para_brt(b["t"]).date()
        if d > hoje or (d == hoje and not hoje_ok):
            continue
        out[d] = (b["c"], b["c"] * b["v"])
    return [(d, c, vf) for d, (c, vf) in sorted(out.items())]


def scan_diario(charts, syms, agora_utc, min_preco, min_vol_fin, cfg):
    hits = []
    cont = {"pedidos": len(syms), "lidos": 0, "iliquidos": 0, "curtos": 0, "analisados": 0}
    for sym in syms:
        ch = charts.get(sym)
        if not ch:
            continue
        cont["lidos"] += 1
        dias = pregoes_completos(ch, agora_utc, cfg)
        if len(dias) < MIN_PREGOES:
            cont["curtos"] += 1
            continue
        fech = [c for _, c, _ in dias]
        vol_fin = sum(v for _, _, v in dias[-20:]) / 20.0
        if fech[-1] < min_preco or vol_fin < min_vol_fin:
            cont["iliquidos"] += 1
            continue
        cont["analisados"] += 1
        tags, n = setups(fech)
        if tags:
            hits.append({"symbol": sym, "setups": tags, "preco": round(fech[-1], 2),
                         "data_fechamento": dias[-1][0].isoformat(), "ifr": round(n["ifr"], 1),
                         "max20": round(n["max20"], 2), "mm20": round(n["mm20"], 2),
                         "volume_fin_medio_20d": round(vol_fin)})
    hits.sort(key=lambda h: (-h["volume_fin_medio_20d"], h["symbol"]))
    cont["sinais"] = len(hits)
    return hits, cont


# ---------------------------------------------------------------- ORB

def janela_orb(agora_utc, at, or_minutes, cfg, dia=None):
    """(dia, corte) ou B3Erro com o motivo."""
    agora = b3lib.para_brt(agora_utc)
    dia = dia or agora.date()
    if or_minutes < 5 or or_minutes % 5 or or_minutes > 120:
        raise b3lib.B3Erro("--or-minutes espera um múltiplo de 5 entre 5 e 120 (15 é o clássico)")
    ok, motivo = b3lib.dia_de_pregao(dia, cfg)
    if not ok:
        raise b3lib.B3Erro("não há pregão em %s (%s)" % (dia.strftime("%d/%m/%Y"), motivo))
    abre, fecha = b3lib.sessao(dia, cfg)
    fim_faixa = datetime.datetime.combine(dia, abre) + datetime.timedelta(minutes=or_minutes)
    primeiro = fim_faixa + datetime.timedelta(minutes=5)
    fecha_dt = datetime.datetime.combine(dia, fecha)
    corte = datetime.datetime.combine(dia, at) if at else agora.replace(second=0, microsecond=0)
    if at and corte > agora + datetime.timedelta(seconds=59) and dia == agora.date():
        raise b3lib.B3Erro("--at %s é depois de agora (%s)" % (b3lib.hm(at), agora.strftime("%H:%M")))
    corte = min(corte, fecha_dt)
    if corte < primeiro:
        raise b3lib.B3Erro("são %s: a faixa de %d minutos vai até %s e o primeiro candle depois dela fecha "
                           "às %s. Rode de novo depois disso." % (corte.strftime("%H:%M"), or_minutes,
                                                                   fim_faixa.strftime("%H:%M"),
                                                                   primeiro.strftime("%H:%M")))
    return dia, corte


def candles_ate(chart, dia, corte, cfg):
    c = b3lib.candles_do_dia(chart, dia, PASSO, cfg)
    return [c[k] for k in sorted(c) if c[k]["fim"] <= corte]


def orb_sinal(candles, n_faixa):
    """Primeiro candle completo que fecha acima da máxima da faixa, ou None."""
    faixa = candles[:n_faixa]
    if len(faixa) < n_faixa or [b["slot"] for b in faixa] != list(range(n_faixa)):
        return None
    mx, mn = max(b["h"] for b in faixa), min(b["l"] for b in faixa)
    for b in candles[n_faixa:]:
        if b["c"] > mx:
            return {"preco": round(b["c"], 2), "hora": b["fim"].strftime("%H:%M"),
                    "candle": b["local"].strftime("%H:%M"), "faixa_max": round(mx, 2),
                    "faixa_min": round(mn, 2), "pct_acima": round((b["c"] / mx - 1) * 100, 2)}
    return None


def scan_orb(charts, syms, dia, corte, or_minutes, min_preco, min_vol_fin, cfg):
    n = or_minutes // 5
    hits = []
    cont = {"pedidos": len(syms), "lidos": 0, "incompletos": 0, "iliquidos": 0, "analisados": 0}
    for sym in syms:
        ch = charts.get(sym)
        if not ch:
            continue
        cont["lidos"] += 1
        cs = candles_ate(ch, dia, corte, cfg)
        if len(cs) < n + 1:
            cont["incompletos"] += 1
            continue
        vol_fin = sum(b["c"] * b["v"] for b in cs)
        if cs[-1]["c"] < min_preco or vol_fin < min_vol_fin:
            cont["iliquidos"] += 1
            continue
        cont["analisados"] += 1
        s = orb_sinal(cs, n)
        if s:
            hits.append(dict({"symbol": sym, "setups": ["orb"], "volume_fin_dia": round(vol_fin)}, **s))
    hits.sort(key=lambda h: (h["hora"], h["symbol"]))
    cont["sinais"] = len(hits)
    return hits, cont


# ---------------------------------------------------------------- comandos

def baixar(syms, rng, interval, offline, a):
    charts, falhas = {}, {}
    for i, s in enumerate(syms):
        try:
            charts[s] = b3lib.obter_chart(s, rng, interval, offline)
        except b3lib.B3Erro as e:
            falhas[s] = str(e)
        if not a.json and not offline and (i + 1) % 25 == 0:
            print("  %d de %d ativos lidos" % (i + 1, len(syms)), file=sys.stderr)
    return charts, falhas


def gravar_watchlist(a, modo, hits, cont, falhas, agora_utc, extra=None):
    doc = dict({"modo": modo, "gerado_em": b3lib.para_brt(agora_utc).strftime("%Y-%m-%d %H:%M"),
                "contagem": cont, "falhas": falhas, "hits": hits}, **(extra or {}))
    if not a.no_write:
        b3lib.gravar_json(a.saida, doc)
    return doc


def mostrar(doc, a, titulo):
    if a.json:
        print(json.dumps(doc, ensure_ascii=False, indent=2))
        return
    print(titulo)
    c = doc["contagem"]
    print("  %s" % ", ".join("%s %s" % (k, v) for k, v in c.items()))
    for h in doc["hits"][:a.show]:
        if "hora" in h:
            print("  %-7s %s às %s, %s acima da máxima da faixa (faixa %s a %s)" % (
                h["symbol"], b3lib.reais(h["preco"]), h["hora"], b3lib.pct(h["pct_acima"]),
                b3lib.reais(h["faixa_min"]), b3lib.reais(h["faixa_max"])))
        else:
            print("  %-7s %-10s IFR %5s  %s  vol. fin. médio %s" % (
                h["symbol"], b3lib.reais(h["preco"]), b3lib.num(h["ifr"], 1), ", ".join(h["setups"]),
                b3lib.reais(h["volume_fin_medio_20d"], 0)))
    if len(doc["hits"]) > a.show:
        print("  ... e mais %d (use --show)" % (len(doc["hits"]) - a.show))
    if doc["falhas"]:
        print("  sem dados: %s" % ", ".join(sorted(doc["falhas"])[:15]))
    if not a.no_write:
        print("Gravado em %s. Uma lista de gráficos não é recomendação de compra." % a.saida)


def cmd_universo(a):
    texto = b3lib.ler_texto(a.offline) if a.offline else b3lib.http_get(url_indice(a.indice)).decode("utf-8")
    linhas = ler_indice(texto)
    if not a.no_write:
        os.makedirs(os.path.dirname(a.universo) or ".", exist_ok=True)
        with open(a.universo, "w", encoding="utf-8") as f:
            f.write("# carteira do %s na B3, %s\n" % (a.indice, datetime.date.today().isoformat()))
            for c, n, t in linhas:
                f.write("%s|%s|%s\n" % (c, n, t))
    print("%d ativos do %s%s" % (len(linhas), a.indice, "" if a.no_write else " gravados em " + a.universo))
    return 0


def cmd_diario(a, cfg):
    agora = b3lib.ler_agora(a.now)
    syms = simbolos(a)
    charts, falhas = baixar(syms, "3mo", "1d", a.offline, a)
    min_vol = 5e6 if a.min_volume_fin is None else a.min_volume_fin
    hits, cont = scan_diario(charts, syms, agora, a.min_preco, min_vol, cfg)
    doc = gravar_watchlist(a, "diario", hits, cont, falhas, agora)
    mostrar(doc, a, "Scanner diário (fechamentos completos):")
    return 0 if hits else 1


def cmd_orb(a, cfg):
    agora = b3lib.ler_agora(a.now)
    at = b3lib.ler_hhmm(a.at, "--at") if a.at else None
    dia, corte = janela_orb(agora, at, a.or_minutes, cfg)
    _, depois, _ = b3lib.janela_entradas(dia, cfg)
    syms = simbolos(a)
    charts, falhas = baixar(syms, "1d", "5m", a.offline, a)
    min_vol = 0 if a.min_volume_fin is None else a.min_volume_fin
    hits, cont = scan_orb(charts, syms, dia, corte, a.or_minutes, a.min_preco, min_vol, cfg)
    doc = gravar_watchlist(a, "orb", hits, cont, falhas, agora,
                           {"dia": dia.isoformat(), "corte": corte.strftime("%H:%M"), "or_minutes": a.or_minutes})
    aviso = ""
    if corte.time() > depois:
        aviso = " Atenção: já passou de %s, o horário limite para novas entradas." % b3lib.hm(depois)
    mostrar(doc, a, "Rompimentos da faixa de %d min em %s até %s:%s" % (
        a.or_minutes, dia.strftime("%d/%m/%Y"), corte.strftime("%H:%M"), aviso))
    return 0 if hits else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("modo", choices=["universo", "diario", "orb"])
    p.add_argument("--indice", default="IBRA")
    p.add_argument("--symbols")
    p.add_argument("--watchlist")
    p.add_argument("--universo", default=b3lib.caminho("universo.txt"))
    p.add_argument("--saida", default=b3lib.caminho("watchlist.json"))
    p.add_argument("--limit", type=int)
    p.add_argument("--min-preco", type=float, default=1.0)
    p.add_argument("--min-volume-fin", type=float)
    p.add_argument("--or-minutes", type=int, default=15)
    p.add_argument("--at")
    p.add_argument("--now")
    p.add_argument("--offline")
    p.add_argument("--config")
    p.add_argument("--show", type=int, default=25)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-write", action="store_true")
    a = p.parse_args(argv)
    try:
        cfg = b3lib.ler_config(a.config)
        if a.modo == "universo":
            return cmd_universo(a)
        return cmd_diario(a, cfg) if a.modo == "diario" else cmd_orb(a, cfg)
    except b3lib.B3Erro as e:
        print("scanner: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
