"""Leitura de extrato OFX (SGML v1.x e XML v2.x) sem dependências externas."""
from __future__ import annotations

import re
from datetime import date

from ..util.dinheiro import dinheiro

_TAG = re.compile(r"<(\w+)>([^<\r\n]*)")


class OFXInvalido(ValueError):
    pass


def _data(v: str) -> date:
    v = v.strip()[:8]
    return date(int(v[:4]), int(v[4:6]), int(v[6:8]))


def ler_ofx(dados: bytes) -> dict:
    texto = dados.decode("latin-1")
    if "<OFX>" not in texto.upper():
        raise OFXInvalido("arquivo sem <OFX>")
    corpo = texto[texto.upper().index("<OFX>"):]

    def campo(nome, base=corpo):
        m = re.search(rf"<{nome}>([^<\r\n]*)", base, re.IGNORECASE)
        return m.group(1).strip() if m else None

    conta = {"banco": campo("BANKID"), "agencia": campo("BRANCHID"), "conta": campo("ACCTID")}
    transacoes = []
    for bloco in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", corpo, re.IGNORECASE | re.DOTALL):
        valores = {k.upper(): v.strip() for k, v in _TAG.findall(bloco)}
        if "TRNAMT" not in valores or "DTPOSTED" not in valores:
            raise OFXInvalido("transação sem TRNAMT/DTPOSTED")
        transacoes.append({
            "fitid": valores.get("FITID"), "tipo": valores.get("TRNTYPE"), "data": _data(valores["DTPOSTED"]),
            "valor": dinheiro(valores["TRNAMT"].replace(",", ".")),
            "memo": valores.get("MEMO") or valores.get("NAME") or "",
            "documento": valores.get("CHECKNUM") or valores.get("REFNUM"),
        })
    ini, fim = campo("DTSTART"), campo("DTEND")
    return {"tipo": "OFX", "conta": conta, "inicio": _data(ini) if ini else None,
            "fim": _data(fim) if fim else None, "transacoes": transacoes}
