"""Catálogo de serviços oficiais por autorizador/modelo/ambiente.

Nunca adicione endpoints sem documento oficial que os publique. Para incluir uma UF,
edite ``catalogo.json`` (ou um ``catalogo_local.json`` em MOXML_HOME) e registre a
evidência em FONTES_FISCAIS.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class Servico:
    nome: str
    url: str
    operation: str
    method: str
    versao: str
    wrapper: str | None

    @property
    def namespace_wsdl(self) -> str:
        return f"http://www.portalfiscal.inf.br/nfe/wsdl/{self.operation}"

    @property
    def action(self) -> str:
        return f"{self.namespace_wsdl}/{self.method}"


class ServicoIndisponivel(LookupError):
    pass


@lru_cache
def _carregar(extra: str | None = None) -> dict:
    base = json.loads((Path(__file__).with_name("catalogo.json")).read_text(encoding="utf-8"))
    if extra and Path(extra).exists():
        loc = json.loads(Path(extra).read_text(encoding="utf-8"))
        for k, v in loc.get("servicos", {}).items():
            base["servicos"].setdefault(k, v)
            base["servicos"][k]["urls"].update(v.get("urls", {}))
        for mod, ufs in loc.get("autorizador_por_uf", {}).items():
            base["autorizador_por_uf"].setdefault(mod, {}).update(ufs)
    return base


def autorizador(uf: str, modelo: str, extra: str | None = None) -> str | None:
    return _carregar(extra)["autorizador_por_uf"].get(modelo, {}).get(uf)


def servico(nome: str, autorizador_ou_uf: str, modelo: str, ambiente: int, extra: str | None = None) -> Servico:
    cat = _carregar(extra)
    s = cat["servicos"].get(nome)
    if not s:
        raise ServicoIndisponivel(f"serviço {nome} não catalogado")
    aut = cat["autorizador_por_uf"].get(modelo, {}).get(autorizador_ou_uf, autorizador_ou_uf)
    url = s["urls"].get(f"{aut}|{modelo}|{ambiente}")
    if not url:
        motivo = cat.get("indisponiveis_documentados", {}).get(f"{autorizador_ou_uf}|{modelo}|{'SAE' if nome.startswith('NFCe') else nome}")
        raise ServicoIndisponivel(motivo or f"{nome} não publicado para {autorizador_ou_uf}/modelo {modelo}/ambiente {ambiente}")
    return Servico(nome, url, s["operation"], s["method"], s["versao"], s.get("wrapper"))


def portal(nome: str, uf: str, modelo: str, ambiente: int, extra: str | None = None) -> str:
    cat = _carregar(extra)
    p = cat.get("portais", {}).get(nome)
    if not p:
        raise ServicoIndisponivel(f"portal {nome} não catalogado")
    aut = cat["autorizador_por_uf"].get(modelo, {}).get(uf, uf)
    url = p["urls"].get(f"{aut}|{modelo}|{ambiente}")
    if not url:
        raise ServicoIndisponivel(f"portal {nome} não publicado para {uf}/{modelo}/ambiente {ambiente}")
    return url


def motivo_indisponivel(chave: str) -> str | None:
    return _carregar().get("indisponiveis_documentados", {}).get(chave)
