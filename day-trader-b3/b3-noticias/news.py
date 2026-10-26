#!/usr/bin/env python3
"""Monitor de notícias para b3-noticias. Só biblioteca padrão.

Para cada ativo acompanhado (carteira, watchlist do scanner ou --symbols):
  1. documentos da CVM (IPE): fatos relevantes, comunicados ao mercado,
     avisos aos acionistas, reuniões da administração (dividendos, JCP,
     recompras), proventos e afins, com link para o PDF no RAD da CVM;
  2. variação do dia no Yahoo, destacando movimentos acima de --move (3%);
  3. com --manchetes, manchetes do Google Notícias em português (feed RSS de
     uso pessoal, não comercial).

    python3 news.py                          # carteira + watchlist, últimos 3 dias
    python3 news.py --symbols PETR4,VALE3 --dias 10
    python3 news.py --todos                  # mostra também o que já foi visto
    python3 news.py --manchetes --json

Só mostra o que é novo desde a última execução (trader-b3/estado/noticias.json),
a menos que --todos. O arquivo IPE da CVM é atualizado uma vez por dia: para o
que saiu hoje, consulte o RAD (https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx).
Notícia não é sinal de compra ou venda.
"""

import argparse
import datetime
import json
import os
import sys
import urllib.parse
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "b3-comum"))
import b3lib  # noqa: E402
import cvm  # noqa: E402

CATEGORIAS = ("Fato Relevante", "Comunicado ao Mercado", "Aviso aos Acionistas", "Aviso aos Debenturistas",
              "Calendário de Eventos Corporativos", "Assembleia", "Dados Econômico-Financeiros",
              "Reunião da Administração", "Relatório Proventos")
IMPORTANTES = ("Fato Relevante",)
GNEWS = "https://news.google.com/rss/search?q=%s&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def acompanhados(a):
    if a.symbols:
        return sorted({b3lib.sem_fracionario(s) for s in a.symbols.split(",") if s.strip()})
    syms = set()
    cart = b3lib.ler_json(b3lib.caminho("carteira.json"), {}) or {}
    syms.update((cart.get("posicoes") or {}).keys())
    wl = b3lib.ler_json(b3lib.caminho("watchlist.json"), {}) or {}
    syms.update(h["symbol"] for h in wl.get("hits") or [])
    if not syms:
        raise b3lib.B3Erro("nada para acompanhar: passe --symbols ou rode /b3-scanner")
    return sorted(syms)


def documentos(cnpjs, desde, ano, offline=None):
    """Documentos IPE das companhias desde `desde` (data de entrega)."""
    por_cnpj = {}
    for sym, info in cnpjs.items():
        por_cnpj.setdefault(info["cnpj"], []).append(sym)
    anos = [ano] if desde.year == ano else [desde.year, ano]
    out = []
    for a in anos:
        z = cvm.zip_ano("IPE", a, offline=offline)
        for r in cvm.linhas(z, "ipe_cia_aberta", lambda r: r["CNPJ_Companhia"] in por_cnpj):
            if r["Categoria"] not in CATEGORIAS or (r.get("Data_Entrega") or "") < desde.isoformat():
                continue
            out.append({"symbols": por_cnpj[r["CNPJ_Companhia"]], "empresa": r["Nome_Companhia"].strip(),
                        "data": r["Data_Entrega"], "categoria": r["Categoria"],
                        "assunto": (r.get("Assunto") or r.get("Tipo") or "").strip(),
                        "link": r["Link_Download"], "id": r["Protocolo_Entrega"] + "v" + (r.get("Versao") or "1"),
                        "importante": r["Categoria"] in IMPORTANTES})
    out.sort(key=lambda d: (d["data"], d["importante"]), reverse=True)
    return out


def movimento(sym, offline=None):
    ch = b3lib.obter_chart(sym, "5d", "1d", offline)
    meta = ch["meta"]
    preco = meta.get("regularMarketPrice")
    ant = meta.get("chartPreviousClose") or meta.get("previousClose")
    if len(ch["bars"]) >= 2:
        preco, ant = ch["bars"][-1]["c"], ch["bars"][-2]["c"]
    if not preco or not ant:
        return None
    return {"preco": round(preco, 2), "variacao_pct": round((preco / ant - 1) * 100, 2)}


def manchetes(sym, nome, n=5):
    q = urllib.parse.quote('"%s" OR "%s"' % (sym, nome.split(" S.A")[0].split(" S/A")[0].title()))
    root = ET.fromstring(b3lib.http_get(GNEWS % q))
    out = []
    for it in root.iter("item"):
        quando = it.findtext("pubDate")
        try:
            quando = parsedate_to_datetime(quando).strftime("%Y-%m-%d %H:%M") if quando else ""
        except (TypeError, ValueError):
            pass
        out.append({"titulo": it.findtext("title"), "link": it.findtext("link"), "quando": quando,
                    "id": "gn:" + (it.findtext("guid") or it.findtext("link") or "")})
        if len(out) >= n:
            break
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--symbols")
    p.add_argument("--dias", type=int, default=3)
    p.add_argument("--move", type=float, default=3.0)
    p.add_argument("--manchetes", action="store_true")
    p.add_argument("--todos", action="store_true")
    p.add_argument("--now")
    p.add_argument("--offline", help="pasta com os ZIPs da CVM")
    p.add_argument("--offline-precos", help="pasta com <TICKER>.json do Yahoo")
    p.add_argument("--sem-precos", action="store_true")
    p.add_argument("--json", action="store_true")
    a = p.parse_args(argv)
    try:
        hoje = b3lib.para_brt(b3lib.ler_agora(a.now)).date()
        syms = acompanhados(a)
        cnpjs, faltou = cvm.cnpj_de(syms, hoje.year, a.offline)
        docs = documentos(cnpjs, hoje - datetime.timedelta(days=a.dias), hoje.year, a.offline)
        estado_p = b3lib.caminho("estado", "noticias.json")
        estado = b3lib.ler_json(estado_p, {"vistos": []}) or {"vistos": []}
        vistos = set(estado["vistos"])
        novos = [d for d in docs if a.todos or d["id"] not in vistos]
        movs, gn = {}, {}
        if not a.sem_precos:
            for s in syms:
                try:
                    movs[s] = movimento(s, a.offline_precos)
                except b3lib.B3Erro:
                    movs[s] = None
        if a.manchetes:
            for s in syms:
                try:
                    gn[s] = [m for m in manchetes(s, (cnpjs.get(s) or {}).get("nome", s)) if a.todos or m["id"] not in vistos]
                except Exception as e:  # feed fora do ar não derruba o resto
                    gn[s] = [{"titulo": "manchetes indisponíveis (%s)" % e, "link": "", "quando": "", "id": ""}]
        estado["vistos"] = sorted(vistos | {d["id"] for d in docs} | {m["id"] for v in gn.values() for m in v if m["id"]})[-5000:]
        b3lib.gravar_json(estado_p, estado)
        if a.json:
            print(json.dumps({"documentos": novos, "movimentos": movs, "manchetes": gn, "sem_cadastro": faltou},
                             ensure_ascii=False, indent=2))
            return 0 if novos else 1
        print("Notícias de %s (CVM desde %s):" % (", ".join(syms), (hoje - datetime.timedelta(days=a.dias)).strftime("%d/%m")))
        for s in syms:
            m = movs.get(s)
            if m:
                alerta = "  <- movimento forte" if abs(m["variacao_pct"]) >= a.move else ""
                print("  %-7s %s (%s no último pregão)%s" % (s, b3lib.reais(m["preco"]),
                                                             ("+" if m["variacao_pct"] >= 0 else "") + b3lib.pct(m["variacao_pct"]), alerta))
        if novos:
            for d in novos:
                print("  %s %s %s — %s: %s\n      %s" % ("!!" if d["importante"] else "  ", d["data"], "/".join(d["symbols"]),
                                                     d["categoria"], d["assunto"] or "(sem assunto)", d["link"]))
        else:
            print("  nenhum documento novo na CVM")
        for s, ms in gn.items():
            for m in ms:
                print("  [%s] %s %s\n      %s" % (s, m["quando"], m["titulo"], m["link"]))
        if faltou:
            print("  sem cadastro na CVM (BDR, ETF ou FII?): %s" % ", ".join(faltou))
        print("Notícia não é sinal. O arquivo da CVM é D-1: para hoje, consulte o RAD.")
        return 0 if novos else 1
    except b3lib.B3Erro as e:
        print("noticias: %s" % e, file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
