"""Modelo de achado do especialista (regra 5: natureza derivada do status das normas)."""
from __future__ import annotations

from dataclasses import dataclass, field

APONTAMENTO, INDICIO, CONTROLE = "APONTAMENTO", "INDÍCIO", "CONTROLE"


def natureza_por_normas(normas: tuple[str, ...], catalogo) -> str:
    if not normas:
        return CONTROLE
    return APONTAMENTO if catalogo.todas_conferidas(normas) else INDICIO


@dataclass
class Achado:
    regra: str
    titulo: str
    natureza: str
    mensagem: str
    cnpj: str | None
    competencia: str | None
    documento: str | None
    normas: list[dict] = field(default_factory=list)  # [{id, status, dispositivos}]
    correcao: str | None = None
    bloqueia: bool = True
    valor: object = None

    def como_dict(self):
        return dict(self.__dict__)
