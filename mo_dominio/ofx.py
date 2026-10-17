"""
Leitura de extrato bancário OFX (1.x SGML e 2.x XML). Só biblioteca padrão.

Devolve um dict:
  banco, agencia, conta, inicio, fim (AAAA-MM-DD), saldo_final (Decimal), data_saldo,
  transacoes: lista de {fitid, data (AAAA-MM-DD), valor (Decimal, + crédito / - débito), tipo, memo, documento}
"""
import re
from decimal import Decimal, InvalidOperation

D0 = Decimal("0")


def _dec(x):
    x = (x or "").strip().replace(",", ".")
    try:
        return Decimal(x)
    except InvalidOperation:
        return D0


def _data(x):
    x = re.sub(r"\D", "", (x or "")[:8])
    return f"{x[0:4]}-{x[4:6]}-{x[6:8]}" if len(x) == 8 else ""


def _decodificar(data):
    if isinstance(data, str):
        return data
    m = re.search(rb"CHARSET:\s*(\S+)", data[:1000]) or re.search(rb'encoding="([^"]+)"', data[:300])
    enc = (m.group(1).decode(errors="ignore") if m else "").lower()
    enc = {"1252": "cp1252", "none": "", "utf8": "utf-8"}.get(enc, enc)
    for e in filter(None, (enc, "utf-8", "cp1252")):
        try:
            return data.decode(e)
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("latin-1")


def _campo(bloco, tag):
    """Valor de <TAG> em SGML (sem fechamento) ou XML (com fechamento)."""
    m = re.search(rf"<{tag}>([^<\r\n]*)", bloco, re.I)
    return m.group(1).strip() if m else ""


def _blocos(texto, tag):
    """Blocos <TAG>...</TAG>; em SGML os agregados sempre fecham, só os campos folha não."""
    return re.findall(rf"<{tag}>(.*?)</{tag}>", texto, re.I | re.S)


def ler_ofx(data):
    t = _decodificar(data)
    conta_bl = (_blocos(t, "BANKACCTFROM") or _blocos(t, "CCACCTFROM") or [""])[0]
    lista = (_blocos(t, "BANKTRANLIST") or [""])[0]
    saldo = (_blocos(t, "LEDGERBAL") or [""])[0]
    trans = []
    for b in _blocos(t, "STMTTRN"):
        valor = _dec(_campo(b, "TRNAMT"))
        memo = _campo(b, "MEMO")
        nome = _campo(b, "NAME")
        if nome and nome not in memo:
            memo = f"{nome} {memo}".strip()
        trans.append({"fitid": _campo(b, "FITID"), "data": _data(_campo(b, "DTPOSTED")), "valor": valor,
                      "tipo": _campo(b, "TRNTYPE").upper(), "memo": re.sub(r"\s+", " ", memo),
                      "documento": _campo(b, "CHECKNUM") or _campo(b, "REFNUM")})
    return {"banco": _campo(conta_bl, "BANKID"), "agencia": _campo(conta_bl, "BRANCHID"), "conta": _campo(conta_bl, "ACCTID"),
            "inicio": _data(_campo(lista, "DTSTART")), "fim": _data(_campo(lista, "DTEND")),
            "saldo_final": _dec(_campo(saldo, "BALAMT")), "data_saldo": _data(_campo(saldo, "DTASOF")),
            "transacoes": trans}
