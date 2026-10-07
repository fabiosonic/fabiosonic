"""CNPJ/CPF: validação de dígitos, normalização e máscara."""
from __future__ import annotations

import re

_SO_DIGITOS = re.compile(r"\D")


def so_digitos(texto: str | None) -> str:
    return _SO_DIGITOS.sub("", texto or "")


def _dv(base: str, pesos: list[int]) -> str:
    resto = sum(int(d) * p for d, p in zip(base, pesos)) % 11
    return "0" if resto < 2 else str(11 - resto)


def cnpj_valido(cnpj: str | None) -> bool:
    c = so_digitos(cnpj)
    if len(c) != 14 or c == c[0] * 14:
        return False
    d1 = _dv(c[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _dv(c[:12] + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return c[12:] == d1 + d2


def cpf_valido(cpf: str | None) -> bool:
    c = so_digitos(cpf)
    if len(c) != 11 or c == c[0] * 11:
        return False
    d1 = _dv(c[:9], list(range(10, 1, -1)))
    d2 = _dv(c[:9] + d1, list(range(11, 1, -1)))
    return c[9:] == d1 + d2


def gerar_cnpj(base12: str) -> str:
    """Completa os dígitos verificadores (uso em testes com CNPJ fictício)."""
    b = so_digitos(base12)[:12].rjust(12, "0")
    d1 = _dv(b, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = _dv(b + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return b + d1 + d2


def gerar_cpf(base9: str) -> str:
    b = so_digitos(base9)[:9].rjust(9, "0")
    d1 = _dv(b, list(range(10, 1, -1)))
    d2 = _dv(b + d1, list(range(11, 1, -1)))
    return b + d1 + d2


def formatar_cnpj(cnpj: str) -> str:
    c = so_digitos(cnpj)
    if len(c) != 14:
        return cnpj
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
