"""Leitura de extrato OFX (SGML v1.x e XML v2.x) sem dependências externas.

Um arquivo pode ter vários extratos (um `STMTRS`/`CCSTMTRS` por conta): cada um é lido
separadamente com sua própria conta.
"""
from __future__ import annotations

import re
from datetime import date

from ..util.dinheiro import dinheiro

_TAG = re.compile(r"<(\w+)>([^<\r\n]*)")
_BLOCO_EXTRATO = re.compile(r"<(CC)?STMTRS>(.*?)(?:</(?:CC)?STMTRS>|(?=<(?:CC)?STMTRS>)|\Z)", re.IGNORECASE | re.DOTALL)


class OFXInvalido(ValueError):
    pass


def _data(v: str) -> date:
    v = v.strip()[:8]
    return date(int(v[:4]), int(v[4:6]), int(v[6:8]))


def _campo(nome, base):
    m = re.search(rf"<{nome}>([^<\r\n]*)", base, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extrato(corpo: str) -> dict:
    conta = {"banco": _campo("BANKID", corpo), "agencia": _campo("BRANCHID", corpo), "conta": _campo("ACCTID", corpo)}
    transacoes = []
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", corpo, re.IGNORECASE | re.DOTALL):
        valores = {k.upper(): v.strip() for k, v in _TAG.findall(bloco)}
        if "TRNAMT" not in valores or "DTPOSTED" not in valores:
            raise OFXInvalido("transação sem TRNAMT/DTPOSTED")
        transacoes.append({
            "fitid": valores.get("FITID"), "tipo": valores.get("TRNTYPE"), "data": _data(valores["DTPOSTED"]),
            "valor": dinheiro(valores["TRNAMT"]),
            "memo": valores.get("MEMO") or valores.get("NAME") or "",
            "documento": valores.get("CHECKNUM") or valores.get("REFNUM"),
        })
    ini, fim = _campo("DTSTART", corpo), _campo("DTEND", corpo)
    return {"conta": conta, "inicio": _data(ini) if ini else None, "fim": _data(fim) if fim else None,
            "transacoes": transacoes}


def ler_ofx(dados: bytes) -> dict:
    texto = dados.decode("latin-1")
    if "<OFX>" not in texto.upper():
        raise OFXInvalido("arquivo sem <OFX>")
    corpo = texto[texto.upper().index("<OFX>"):]
    blocos = [m.group(2) for m in _BLOCO_EXTRATO.finditer(corpo)]
    extratos = [_extrato(b) for b in blocos] if blocos else [_extrato(corpo)]
    return {"tipo": "OFX", "extratos": extratos}
