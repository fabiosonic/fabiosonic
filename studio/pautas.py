"""Pautas: notícias (RSS), calendário fiscal e ideias livres."""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

import yaml

from avatar_contabil import config, pauta as rss

from .db import Pauta, select


@dataclass
class Obrigacao:
    nome: str
    data: date
    publico: str
    dica: str


def _calendario() -> dict:
    with open(config.RAIZ / "config" / "calendario_fiscal.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def obrigacoes_do_mes(ano: int, mes: int) -> list[Obrigacao]:
    cal = _calendario()
    ultimo = calendar.monthrange(ano, mes)[1]
    itens = [Obrigacao(o["nome"], date(ano, mes, min(o["dia"], ultimo)), o["publico"], o["dica"]) for o in cal.get("mensais", [])]
    itens += [
        Obrigacao(o["nome"], date(ano, mes, min(o["dia"], ultimo)), o["publico"], o["dica"])
        for o in cal.get("anuais", []) if o["mes"] == mes
    ]
    return sorted(itens, key=lambda o: o.data)


def _adicionar(s, origem: str, titulo: str, resumo: str, link: str, data_ref: str | None, chave: str) -> bool:
    if s.exec(select(Pauta).where(Pauta.chave == chave)).first():
        return False
    s.add(Pauta(origem=origem, titulo=titulo, resumo=resumo, link=link, data_ref=data_ref, chave=chave))
    return True


def importar_fiscais(s, ano: int, mes: int) -> int:
    novas = 0
    for o in obrigacoes_do_mes(ano, mes):
        titulo = f"{o.nome}: vencimento em {o.data:%d/%m/%Y}"
        resumo = f"{o.dica} Público: {o.publico}. Data de referência do calendário interno; confirme a data oficial e regras de dia útil."
        novas += _adicionar(s, "fiscal", titulo, resumo, "", o.data.isoformat(), f"fiscal:{o.nome}:{o.data}")
    return novas


def importar_noticias(s, cfg: dict) -> int:
    itens = rss.exemplo() if config.dry_run() else rss.coletar(cfg)
    novas = 0
    for p in itens:
        novas += _adicionar(s, "noticia", p.titulo, p.resumo, p.link, (p.publicado_em or "")[:10] or None, f"rss:{p.id}")
    return novas


def nova_ideia(s, titulo: str, resumo: str) -> Pauta:
    p = Pauta(origem="ideia", titulo=titulo.strip(), resumo=resumo.strip())
    s.add(p)
    return p
