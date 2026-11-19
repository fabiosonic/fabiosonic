"""Chave de acesso NF-e/NFC-e (44 posições) — MOC 7.0, item 2.2.

Layout: cUF(2) AAMM(4) CNPJ/CPF(14) mod(2) serie(3) nNF(9) tpEmis(1) cNF(8) cDV(1).
O CNPJ pode ser alfanumérico a partir da NT 2025.001 (CNPJ alfa); o DV continua
módulo 11 sobre o valor (ord(c) - 48) de cada caractere.

Este módulo NÃO gera códigos numéricos (cNF): a chave só pode ser conhecida a
partir de uma fonte legítima. Não há função de força bruta, por decisão de projeto.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

UF_CODIGO = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14", "PA": "15", "AP": "16", "TO": "17",
    "MA": "21", "PI": "22", "CE": "23", "RN": "24", "PB": "25", "PE": "26", "AL": "27",
    "SE": "28", "BA": "29", "MG": "31", "ES": "32", "RJ": "33", "SP": "35", "PR": "41",
    "SC": "42", "RS": "43", "MS": "50", "MT": "51", "GO": "52", "DF": "53", "AN": "91",
}
CODIGO_UF = {v: k for k, v in UF_CODIGO.items()}

_RE_CHAVE = re.compile(r"^[0-9]{6}[0-9A-Z]{12}[0-9]{2}[0-9]{2}[0-9]{3}[0-9]{9}[0-9][0-9]{8}[0-9]$")


class ChaveInvalida(ValueError):
    pass


def _valor(c: str) -> int:
    return ord(c) - 48


def calcular_dv(chave43: str) -> int:
    """Módulo 11 com pesos 2..9 da direita para a esquerda."""
    if len(chave43) != 43:
        raise ChaveInvalida("base da chave deve ter 43 posições")
    soma, peso = 0, 2
    for c in reversed(chave43):
        soma += _valor(c) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


@dataclass(frozen=True, slots=True)
class ChaveAcesso:
    chave: str
    uf: str
    ano: int
    mes: int
    cnpj: str
    modelo: str
    serie: int
    numero: int
    tp_emis: int
    codigo_numerico: str
    dv: int

    @property
    def competencia(self) -> date:
        return date(self.ano, self.mes, 1)


def normalizar(chave: str) -> str:
    return re.sub(r"[^0-9A-Za-z]", "", chave or "").upper().removeprefix("NFE")


def analisar(chave: str) -> ChaveAcesso:
    """Valida comprimento, estrutura, UF, mês, modelo e DV. Lança ChaveInvalida."""
    c = normalizar(chave)
    if len(c) != 44:
        raise ChaveInvalida(f"chave deve ter 44 posições (recebido {len(c)})")
    if not _RE_CHAVE.match(c):
        raise ChaveInvalida("estrutura da chave inválida")
    uf = CODIGO_UF.get(c[0:2])
    if not uf or uf == "AN":
        raise ChaveInvalida(f"código de UF inválido: {c[0:2]}")
    ano, mes = 2000 + int(c[2:4]), int(c[4:6])
    if not 1 <= mes <= 12:
        raise ChaveInvalida(f"mês inválido na chave: {mes}")
    modelo = c[20:22]
    if modelo not in ("55", "65"):
        raise ChaveInvalida(f"modelo {modelo} não suportado (apenas 55 e 65)")
    dv = int(c[43])
    if calcular_dv(c[:43]) != dv:
        raise ChaveInvalida("dígito verificador inválido")
    return ChaveAcesso(
        chave=c, uf=uf, ano=ano, mes=mes, cnpj=c[6:20], modelo=modelo,
        serie=int(c[22:25]), numero=int(c[25:34]), tp_emis=int(c[34]),
        codigo_numerico=c[35:43], dv=dv,
    )


def valida(chave: str) -> bool:
    try:
        analisar(chave)
        return True
    except ChaveInvalida:
        return False


def montar_chave(uf: str, ano: int, mes: int, cnpj: str, modelo: str, serie: int, numero: int,
                 tp_emis: int, codigo_numerico: str) -> str:
    """Monta chave a partir de campos CONHECIDOS (ex.: lidos de um XML). Uso em testes e
    na reconstrução de chaves de XMLs sem atributo Id. Não deve ser usado para adivinhar cNF."""
    base = (
        f"{UF_CODIGO[uf]}{ano % 100:02d}{mes:02d}{cnpj.upper():>014}{modelo}"
        f"{serie:03d}{numero:09d}{tp_emis}{codigo_numerico:>08}"
    ).replace(" ", "0")
    return base + str(calcular_dv(base))
