"""Notícias e carteiras recomendadas — 100% gratuito, sem chave.

Fonte: RSS público do Google Notícias -> link decodificado (googlenewsdecoder) ->
texto da matéria -> tickers da B3 encontrados no texto.
A extração é automática: confira sempre na fonte (o link fica salvo).
"""
from __future__ import annotations

import datetime as dt
import html as html_mod
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

AGENTE = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) PainelQuantB3/1.0"}
TICKER = re.compile(r"\b([A-Z]{4}(?:3|4|5|6|11))\b")
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
         "outubro", "novembro", "dezembro"]

# casa -> nomes como aparecem nos títulos
CASAS = {
    "BTG Pactual": ["BTG"], "XP": ["XP"], "Itaú BBA": ["Itaú BBA", "Itaú"], "Bradesco BBI": ["Bradesco BBI", "BBI", "Ágora"],
    "Santander": ["Santander"], "Safra": ["Safra"], "Genial": ["Genial"], "BB Investimentos": ["BB-BI", "BB Investimentos", "BB-BI"],
    "Goldman Sachs": ["Goldman"], "JPMorgan": ["JPMorgan", "JP Morgan"], "Morgan Stanley": ["Morgan Stanley"],
    "UBS BB": ["UBS"], "Bank of America": ["BofA", "Bank of America"], "Citi": ["Citi"], "Itaú Unibanco": [],
    "Inter": ["Inter Invest"], "Terra Investimentos": ["Terra Investimentos"], "Rico": ["Rico"], "Toro": ["Toro"], "Empiricus": ["Empiricus"], "Nord": ["Nord"],
}


def _baixar(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=AGENTE)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def google_noticias(consulta: str, limite: int = 10) -> list[dict]:
    q = urllib.parse.quote(consulta)
    xml = _baixar(f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419")
    itens = []
    for it in ET.fromstring(xml).findall(".//item")[:limite]:
        titulo = it.findtext("title") or ""
        fonte = it.findtext("source") or ""
        if fonte and titulo.endswith(f" - {fonte}"):
            titulo = titulo[: -len(fonte) - 3]
        itens.append({"titulo": titulo, "fonte": fonte, "link": it.findtext("link"), "data": it.findtext("pubDate")})
    return itens


def decodificar(link: str) -> str | None:
    try:
        from googlenewsdecoder import gnewsdecoder
        d = gnewsdecoder(link, interval=1)
        return d.get("decoded_url") if d.get("status") or d.get("success") else None
    except Exception:  # noqa: BLE001
        return None


def texto_da_pagina(html: str) -> str:
    html = re.sub(r"(?is)<(script|style|nav|header|footer|aside|form)\b.*?</\1>", " ", html)
    return html_mod.unescape(re.sub(r"<[^>]+>", " ", html))


def tickers_do_texto(texto: str, universo: set[str] | None = None) -> Counter:
    c = Counter(TICKER.findall(texto))
    return Counter({t: n for t, n in c.items() if universo is None or t in universo or n >= 2})


def noticias_do_ativo(ticker: str, limite: int = 6) -> list[dict]:
    return google_noticias(f"{ticker} ações", limite)


def _casa_do_titulo(titulo: str) -> str | None:
    t = f" {titulo} "
    for casa, apelidos in CASAS.items():
        for a in apelidos or [casa]:
            if re.search(rf"(?<![A-Za-zÀ-ú]){re.escape(a)}(?![A-Za-zÀ-ú])", t):
                return casa
    return None


def carteiras_recomendadas(universo: set[str] | None = None, data: dt.date | None = None,
                           max_materias: int = 14, log=print) -> dict:
    data = data or dt.date.today()
    mes = f"{MESES[data.month - 1]} {data.year}"
    vistos, materias = set(), []
    for consulta in (f"carteira recomendada ações {mes}", f"ações recomendadas {mes}",
                     f"top ações {mes} carteira", f"carteira de dividendos {mes}"):
        try:
            for n in google_noticias(consulta, 15):
                tit = n["titulo"].lower()
                if re.search(r"\bfiis?\b|fundos? imobili", tit):
                    continue  # carteiras de FII não são de ações
                if n["link"] not in vistos and (MESES[data.month - 1] in tit or "carteira" in tit):
                    vistos.add(n["link"])
                    materias.append(n)
        except Exception as e:  # noqa: BLE001
            log(f"busca '{consulta}' falhou: {e}")
    casas, consolidadas = [], []
    for n in materias[: max_materias * 2]:
        if len(casas) + len(consolidadas) >= max_materias:
            break
        url = decodificar(n["link"])
        if not url:
            continue
        try:
            tick = tickers_do_texto(texto_da_pagina(_baixar(url)), universo)
        except Exception as e:  # noqa: BLE001 - site bloqueou ou caiu: segue para a próxima
            log(f"{n['fonte']}: não foi possível ler ({e})")
            continue
        if not tick:
            continue
        casa = _casa_do_titulo(f"{n['titulo']} {n['fonte']}")
        item = {"casa": casa or f"Consolidado ({n['fonte']})", "carteira": n["titulo"], "ativos": [t for t, _ in tick.most_common(15)],
                "fonte": url, "data": n["data"][5:16] if n.get("data") else "", "veiculo": n["fonte"]}
        (casas if casa else consolidadas).append(item)
    por_ticker: dict[str, set] = defaultdict(set)
    for c in casas:
        for t in c["ativos"]:
            por_ticker[t].add(c["casa"])
    mencoes = Counter(t for c in casas + consolidadas for t in c["ativos"])
    mais = [{"ticker": t, "casas": len(por_ticker[t]), "nomes_casas": sorted(por_ticker[t]), "materias": mencoes[t]}
            for t in mencoes]
    mais.sort(key=lambda x: (-x["casas"], -x["materias"]))
    return {
        "mes_referencia": mes, "casas": casas + consolidadas, "mais_citados": mais[:20],
        "observacoes": "Extração automática de tickers de matérias públicas (Google Notícias). Gratuito; confira cada "
                       "carteira na fonte, pois a matéria pode citar ativos que não fazem parte da recomendação.",
        "atualizado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "custo_usd": 0.0,
        "modelo": "Gratuito: Google Notícias + extração automática",
        "fontes": [c["fonte"] for c in casas + consolidadas],
    }
