"""PIX copia-e-cola (BR Code estático, padrão EMV do Banco Central) com valor e identificador do título.

Não depende de banco nem de tarifa: o cliente paga direto na chave PIX do escritório. O identificador
(txid) volta no extrato e ajuda a conciliação automática.
"""

from __future__ import annotations

import re
import unicodedata


def _campo(id_: str, valor: str) -> str:
    return f"{id_}{len(valor):02d}{valor}"


def _limpar(texto: str, tamanho: int) -> str:
    s = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().upper()
    return re.sub(r"[^A-Z0-9 ]", "", s).strip()[:tamanho] or "NA"


def crc16(dados: str) -> str:
    crc = 0xFFFF
    for b in dados.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def normalizar_chave(chave: str) -> str:
    c = chave.strip()
    if "@" in c or re.fullmatch(r"[0-9a-fA-F-]{36}", c):
        return c.lower() if "@" in c else c
    d = re.sub(r"\D", "", c)
    if c.startswith("+"):
        return "+" + d
    if len(d) in (11, 14) and not c.startswith("("):
        return d                      # CPF / CNPJ
    if len(d) in (10, 11):
        return "+55" + d              # telefone
    return c


def payload(chave: str, valor_cent: int, nome: str, cidade: str, txid: str = "***", descricao: str = "") -> str:
    if not chave:
        raise ValueError("Configure a chave PIX do escritório em Configurações.")
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", normalizar_chave(chave))
    if descricao:
        conta += _campo("02", _limpar(descricao, 40))
    tx = re.sub(r"[^A-Za-z0-9]", "", txid)[:25] or "***"
    corpo = (_campo("00", "01") + _campo("26", conta) + _campo("52", "0000") + _campo("53", "986")
             + (_campo("54", f"{valor_cent / 100:.2f}") if valor_cent else "") + _campo("58", "BR")
             + _campo("59", _limpar(nome, 25)) + _campo("60", _limpar(cidade, 15))
             + _campo("62", _campo("05", tx)) + "6304")
    return corpo + crc16(corpo)
