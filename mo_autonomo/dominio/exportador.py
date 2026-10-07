"""Exportador de lançamentos contábeis no formato TXT que o escritório já importa no Domínio.

Leiaute: dominio/leiautes/LANCAMENTOS_TXT_ESCRITORIO.md (aprovado pelo usuário em 07/10/2026).
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal

from ..util.dinheiro import dinheiro


class LancamentoInvalido(ValueError):
    pass


def historico_dominio(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    t = re.sub(r"[;\r\n\t]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        raise LancamentoInvalido("histórico vazio")
    return t


def _conta(c) -> str:
    s = str(c or "").strip()
    if not s.isdigit():
        raise LancamentoInvalido(f"conta {c!r} não é código reduzido do Domínio")
    return s


def _valor(v) -> str:
    d = dinheiro(v if not isinstance(v, (int,)) else str(v))
    if d <= Decimal("0"):
        raise LancamentoInvalido(f"valor {v!r} deve ser positivo")
    return f"{d:.2f}".replace(".", ",")


def _data(d) -> str:
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return f"{d:%d/%m/%Y}"


def linha(lanc: dict) -> str:
    deb, cred = _conta(lanc["debito"]), _conta(lanc["credito"])
    if deb == cred:
        raise LancamentoInvalido("débito e crédito na mesma conta")
    return f"{_data(lanc['data'])};{deb};{cred};{_valor(lanc['valor'])};{historico_dominio(lanc['historico'])};1;;;;;;"


def gerar(lancamentos: list[dict]) -> bytes:
    """Arquivo completo (CRLF, ASCII). Lançamento inválido levanta erro: nada de arquivo parcial."""
    linhas = [linha(l) for l in sorted(lancamentos, key=lambda x: (str(x["data"]), str(x.get("fitid") or "")))]
    return ("\r\n".join(linhas) + "\r\n").encode("ascii")
