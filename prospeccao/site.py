"""Leitura do site de uma empresa: texto das páginas institucionais e contatos
publicados por ela mesma (cada contato sai com a URL da página onde estava)."""
from __future__ import annotations

import re
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from .base import eh_celular, so_digitos

UA = {"User-Agent": "Mozilla/5.0 (compatible; leitor-institucional/1.0)"}
PISTAS = ("sobre", "quem-somos", "quemsomos", "empresa", "institucional", "equipe", "time",
          "diretoria", "socios", "contato", "fale-conosco", "unidades", "servicos", "historia")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
FONE_RE = re.compile(r"\(?\b\d{2}\)?[\s.-]?9\d{4}[\s.-]?\d{4}\b")
MAX_PAGINAS = 6
MAX_CHARS = 6000


def baixar(url: str) -> str:
    r = requests.get(url, headers=UA, timeout=15)
    r.raise_for_status()
    return r.text


def _fone_de_link(href: str) -> str:
    u = urlparse(href)
    if "wa.me" in u.netloc:
        return so_digitos(u.path)
    if "whatsapp.com" in u.netloc:
        return so_digitos(parse_qs(u.query).get("phone", [""])[0])
    return ""


def ler_pagina(url: str, html: str) -> dict:
    sopa = BeautifulSoup(html, "html.parser")
    links, whats, emails, redes = [], [], [], {}
    for a in sopa.find_all("a", href=True):
        href = urljoin(url, a["href"])
        if href.startswith("mailto:"):
            emails.append(unquote(href[7:].split("?")[0]).lower())
        elif "wa.me" in href or "whatsapp.com/send" in href:
            n = _fone_de_link(href)
            if eh_celular(n):
                whats.append(n)
        elif "instagram.com/" in href:
            redes.setdefault("instagram", href)
        elif "linkedin.com/company/" in href:
            redes.setdefault("linkedin", href.split("?")[0])
        elif urlparse(href).netloc == urlparse(url).netloc:
            links.append(href.split("#")[0])
    for t in sopa(["script", "style", "noscript", "svg"]):
        t.decompose()
    texto = re.sub(r"\s+", " ", sopa.get_text(" ")).strip()
    emails += [e.lower() for e in EMAIL_RE.findall(texto)]
    celulares_texto = [so_digitos(f) for f in FONE_RE.findall(texto)]
    return {"url": url, "texto": texto, "links": links, "whats": whats,
            "celulares_texto": [c for c in celulares_texto if eh_celular(c)],
            "emails": [e for e in dict.fromkeys(emails) if not e.endswith((".png", ".jpg", ".webp"))],
            "redes": redes}


def ler_site(url: str, baixar_fn=baixar) -> dict:
    """Lê a home e até MAX_PAGINAS páginas institucionais.

    Devolve {vivo, paginas:[{url,texto}], whatsapp, fonte_whatsapp, email, fonte_email, instagram, linkedin}.
    Botão de WhatsApp (link wa.me) tem preferência sobre número solto no texto.
    """
    if not url:
        return {"vivo": False, "paginas": []}
    if not url.startswith("http"):
        url = "https://" + url
    try:
        home = ler_pagina(url, baixar_fn(url))
    except Exception:
        return {"vivo": False, "paginas": []}
    candidatos = [l for l in dict.fromkeys(home["links"])
                  if any(p in urlparse(l).path.lower() for p in PISTAS) and l.rstrip("/") != url.rstrip("/")]
    lidas = [home]
    for link in candidatos[: MAX_PAGINAS - 1]:
        try:
            lidas.append(ler_pagina(link, baixar_fn(link)))
        except Exception:
            continue
    out = {"vivo": True, "paginas": [{"url": p["url"], "texto": p["texto"][:MAX_CHARS]} for p in lidas]}
    for chave_lista, campo in (("whats", "whatsapp"), ("celulares_texto", "whatsapp"), ("emails", "email")):
        for p in lidas:
            if p[chave_lista] and not out.get(campo):
                out[campo], out["fonte_" + campo] = p[chave_lista][0], p["url"]
    for p in lidas:
        for rede, href in p["redes"].items():
            out.setdefault(rede, href)
    return out


def texto_para_ia(leitura: dict) -> str:
    return "\n\n".join(f"### Página: {p['url']}\n{p['texto']}" for p in leitura.get("paginas", []))
