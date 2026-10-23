"""Etapa 1: coleta de pautas em feeds RSS."""
from __future__ import annotations

import hashlib
import html
import re
from datetime import datetime, timedelta, timezone

from . import config
from .modelos import Pauta

VISTAS = "pautas_vistas.txt"


def _limpar(texto: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(texto or ""))).strip()


def _id(link: str) -> str:
    return hashlib.sha1(link.encode()).hexdigest()[:12]


def _vistas() -> set[str]:
    arq = config.DADOS / VISTAS
    return set(arq.read_text().split()) if arq.exists() else set()


def marcar_vistas(ids: list[str]) -> None:
    config.DADOS.mkdir(parents=True, exist_ok=True)
    with open(config.DADOS / VISTAS, "a") as f:
        f.writelines(i + "\n" for i in ids)


def coletar(cfg: dict) -> list[Pauta]:
    """Lê as fontes configuradas e devolve pautas novas (não vistas antes)."""
    import feedparser

    opc = cfg["pauta"]
    limite = datetime.now(timezone.utc) - timedelta(days=opc.get("dias_retroativos", 3))
    vistas = _vistas()
    pautas: dict[str, Pauta] = {}

    for fonte in opc["fontes"]:
        feed = feedparser.parse(fonte["url"])
        for item in feed.entries[: opc.get("max_itens_por_fonte", 15)]:
            link = item.get("link", "")
            if not link:
                continue
            data = item.get("published_parsed") or item.get("updated_parsed")
            quando = datetime(*data[:6], tzinfo=timezone.utc) if data else None
            if quando and quando < limite:
                continue
            pid = _id(link)
            if pid in vistas or pid in pautas:
                continue
            pautas[pid] = Pauta(
                id=pid,
                titulo=_limpar(item.get("title", "")),
                resumo=_limpar(item.get("summary", ""))[:800],
                link=link,
                fonte=fonte["nome"],
                publicado_em=quando.isoformat() if quando else None,
            )
    return list(pautas.values())


def exemplo() -> list[Pauta]:
    """Pautas fixas para o modo de teste (DRY_RUN)."""
    return [
        Pauta(
            id="exemplo0001",
            titulo="Receita divulga calendário de transição do IBS e da CBS para empresas do Simples",
            resumo="Empresas optantes pelo Simples Nacional poderão escolher recolher IBS e CBS por fora do regime.",
            link="https://exemplo.invalid/noticia-1",
            fonte="Exemplo",
        ),
        Pauta(
            id="exemplo0002",
            titulo="MEI que ultrapassar o limite de faturamento deve comunicar desenquadramento",
            resumo="O microempreendedor que faturar acima do limite anual precisa comunicar o desenquadramento no Portal do Simples.",
            link="https://exemplo.invalid/noticia-2",
            fonte="Exemplo",
        ),
    ]
