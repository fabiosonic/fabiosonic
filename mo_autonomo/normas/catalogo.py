"""Base normativa (regras 1, 3 e 4).

Cada norma é um YAML em config/normas/ (um arquivo pode ter uma lista). Esquema em
config/normas/LEIA-ME.md. Parâmetro legal só é entregue a uma regra se a norma estiver
CONFERIDO; caso contrário a regra fica INATIVA.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import yaml

STATUS = ("PENDENTE", "FONTE_LOCALIZADA", "CONFERIDO", "REVOGADA")
DOMINIOS_OFICIAIS = (".gov.br", ".jus.br", ".leg.br", "cfc.org.br", "cpc.org.br")


class NormaInvalida(ValueError):
    pass


def url_oficial(url: str | None) -> bool:
    if not url:
        return False
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lstrip(".") or host.endswith(d) for d in DOMINIOS_OFICIAIS) and url.startswith("https://")


@dataclass
class Norma:
    id: str
    titulo: str
    area: str
    status: str = "PENDENTE"
    fonte_url: str | None = None
    fonte_url_sugerida: str | None = None
    conferido_por: str | None = None
    conferido_em: date | None = None
    dispositivos: list[str] = field(default_factory=list)
    aplica_se: dict = field(default_factory=dict)
    vigencia_inicio: date | None = None
    vigencia_fim: date | None = None
    parametros: dict = field(default_factory=dict)
    decisao_judicial: dict | None = None
    hash_texto: str | None = None
    observacao: str = ""

    @property
    def conferida(self) -> bool:
        return self.status == "CONFERIDO"

    def vigente_em(self, d: date | None) -> bool:
        if d is None:
            return True
        if self.vigencia_inicio and d < self.vigencia_inicio:
            return False
        if self.vigencia_fim and d > self.vigencia_fim:
            return False
        return True

    def validar(self) -> None:
        if self.status not in STATUS:
            raise NormaInvalida(f"{self.id}: status inválido {self.status}")
        if self.conferida:
            faltas = [n for n, v in (("fonte_url", self.fonte_url), ("conferido_por", self.conferido_por),
                                       ("conferido_em", self.conferido_em)) if not v]
            if faltas:
                raise NormaInvalida(f"{self.id}: CONFERIDO sem {', '.join(faltas)}")
            if not url_oficial(self.fonte_url):
                raise NormaInvalida(f"{self.id}: fonte não oficial {self.fonte_url}")
            if str(self.conferido_por).strip().lower() in {"claude", "ia", "modelo", "sistema", "auto"}:
                raise NormaInvalida(f"{self.id}: conferido_por precisa ser uma pessoa")
            if self.decisao_judicial is not None:
                dj = self.decisao_judicial
                if not dj.get("transito_em_julgado") or not dj.get("modulacao"):
                    raise NormaInvalida(f"{self.id}: decisão judicial sem trânsito/modulação (regra 4)")
        elif self.parametros:
            # parâmetros podem ser PROPOSTOS numa norma não conferida, mas nunca usados
            pass

    def aplica_ao_perfil(self, perfil) -> bool:
        """`perfil`: objeto com regime, cnae, uf, municipio, natureza_juridica (ou None)."""
        a = self.aplica_se or {}
        if not a:
            return True
        checagens = [
            ("regimes", getattr(perfil, "regime", None)),
            ("ufs", getattr(perfil, "uf", None)),
            ("municipios", getattr(perfil, "municipio", None)),
            ("naturezas_juridicas", getattr(perfil, "natureza_juridica", None)),
        ]
        for chave, valor in checagens:
            if chave in a:
                if valor is None or str(valor) not in [str(x) for x in a[chave]]:
                    return False
        if "cnae_prefixos" in a:
            cnaes = list(getattr(perfil, "cnaes", []) or [])
            if not any(str(c).startswith(str(p)) for c in cnaes for p in a["cnae_prefixos"]):
                return False
        return True


def _data(v):
    if v in (None, ""):
        return None
    if isinstance(v, date):
        return v
    return date.fromisoformat(str(v))


def _norma(d: dict) -> Norma:
    vig = d.get("vigencia") or {}
    n = Norma(
        id=d["id"], titulo=d.get("titulo", ""), area=d.get("area", ""), status=d.get("status", "PENDENTE"),
        fonte_url=d.get("fonte_url"), fonte_url_sugerida=d.get("fonte_url_sugerida"),
        conferido_por=d.get("conferido_por"), conferido_em=_data(d.get("conferido_em")),
        dispositivos=list(d.get("dispositivos") or []), aplica_se=dict(d.get("aplica_se") or {}),
        vigencia_inicio=_data(vig.get("inicio")), vigencia_fim=_data(vig.get("fim")),
        parametros=dict(d.get("parametros") or {}), decisao_judicial=d.get("decisao_judicial"),
        hash_texto=d.get("hash_texto"), observacao=d.get("observacao", ""),
    )
    n.validar()
    return n


class Catalogo:
    def __init__(self, normas: dict[str, Norma]):
        self.normas = normas

    @classmethod
    def carregar(cls, pasta: Path | str) -> "Catalogo":
        normas: dict[str, Norma] = {}
        for arq in sorted(Path(pasta).rglob("*.yaml")):
            conteudo = yaml.safe_load(arq.read_text(encoding="utf-8")) or []
            itens = conteudo if isinstance(conteudo, list) else conteudo.get("normas", [conteudo])
            for item in itens:
                n = _norma(item)
                if n.id in normas:
                    raise NormaInvalida(f"norma duplicada: {n.id} ({arq})")
                normas[n.id] = n
        return cls(normas)

    @classmethod
    def de_lista(cls, itens: list[dict]) -> "Catalogo":
        return cls({i["id"]: _norma(i) for i in itens})

    def get(self, id_: str) -> Norma | None:
        return self.normas.get(id_)

    def status(self, id_: str) -> str:
        n = self.normas.get(id_)
        return n.status if n else "AUSENTE"

    def todas_conferidas(self, ids) -> bool:
        return all(self.status(i) == "CONFERIDO" for i in ids)

    def parametro(self, id_norma: str, nome: str, em: date | None = None):
        """Devolve o parâmetro só se a norma estiver CONFERIDO e vigente. Senão None (regra 3)."""
        n = self.normas.get(id_norma)
        if n is None or not n.conferida or not n.vigente_em(em):
            return None
        return n.parametros.get(nome)

    def resumo(self) -> dict[str, int]:
        out = {s: 0 for s in STATUS}
        for n in self.normas.values():
            out[n.status] += 1
        return out

    def aplicaveis(self, perfil, em: date | None = None) -> list[Norma]:
        return [n for n in self.normas.values() if n.vigente_em(em) and n.aplica_ao_perfil(perfil)]
