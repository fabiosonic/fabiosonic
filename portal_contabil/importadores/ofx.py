"""Importador de extratos OFX (SGML 1.x e XML 2.x)."""
from __future__ import annotations

import re

from ..modelos import LancamentoBancario
from ..util import dec, parse_data

_BLOCO = re.compile(r"<STMTTRN>(.*?)(?=</STMTTRN>|<STMTTRN>|</BANKTRANLIST>)", re.S | re.I)


def _tag(bloco: str, nome: str) -> str:
    m = re.search(rf"<{nome}>([^<\r\n]*)", bloco, re.I)
    return m.group(1).strip() if m else ""


def decodificar(conteudo: bytes) -> str:
    for cod in ("utf-8", "cp1252"):
        try:
            return conteudo.decode(cod)
        except UnicodeDecodeError:
            continue
    return conteudo.decode("latin-1", errors="replace")


def ler_ofx(conteudo: bytes, arquivo: str) -> list[LancamentoBancario]:
    txt = decodificar(conteudo)
    if "<OFX" not in txt.upper():
        raise ValueError("arquivo não contém cabeçalho OFX")
    banco = _tag(txt, "BANKID")
    conta = "-".join(p for p in (banco, _tag(txt, "BRANCHID"), _tag(txt, "ACCTID")) if p)
    lancs = []
    for m in _BLOCO.finditer(txt):
        b = m.group(1)
        memo = " ".join(p for p in (_tag(b, "NAME"), _tag(b, "MEMO")) if p)
        lancs.append(LancamentoBancario(
            data=parse_data(_tag(b, "DTPOSTED")),
            valor=dec(_tag(b, "TRNAMT")),
            tipo=_tag(b, "TRNTYPE"),
            fitid=_tag(b, "FITID"),
            memo=memo,
            conta=conta,
            arquivo=arquivo,
        ))
    return lancs
