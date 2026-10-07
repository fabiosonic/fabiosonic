"""Extração de anexos (inclusive ZIP aninhado) com limites contra zip-bomba."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from email import message_from_bytes, policy
from pathlib import PurePosixPath

LIMITE_PROFUNDIDADE = 5
LIMITE_ARQUIVOS = 2000
LIMITE_BYTES = 500 * 1024 * 1024
LIMITE_RAZAO = 200  # descompactado / compactado


class ZipSuspeito(ValueError):
    pass


@dataclass
class Anexo:
    nome: str
    dados: bytes
    origem: str  # ex.: "email:<uid>/lote.zip/notas/1.xml"


def _nome_seguro(nome: str) -> str:
    return PurePosixPath(nome.replace("\\", "/")).name or "sem_nome"


def _expandir_zip(dados: bytes, origem: str, profundidade: int, contagem: dict) -> list[Anexo]:
    if profundidade > LIMITE_PROFUNDIDADE:
        raise ZipSuspeito(f"ZIP aninhado além de {LIMITE_PROFUNDIDADE} níveis: {origem}")
    saida: list[Anexo] = []
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            contagem["arquivos"] += 1
            contagem["bytes"] += info.file_size
            if contagem["arquivos"] > LIMITE_ARQUIVOS or contagem["bytes"] > LIMITE_BYTES:
                raise ZipSuspeito(f"ZIP excede limites (arquivos/bytes): {origem}")
            if info.compress_size and info.file_size / max(info.compress_size, 1) > LIMITE_RAZAO:
                raise ZipSuspeito(f"razão de compressão suspeita em {info.filename}")
            conteudo = z.read(info)
            caminho = f"{origem}/{info.filename}"
            if conteudo.startswith(b"PK\x03\x04"):
                saida.extend(_expandir_zip(conteudo, caminho, profundidade + 1, contagem))
            else:
                saida.append(Anexo(_nome_seguro(info.filename), conteudo, caminho))
    return saida


def expandir(nome: str, dados: bytes, origem: str) -> list[Anexo]:
    if dados.startswith(b"PK\x03\x04"):
        return _expandir_zip(dados, f"{origem}/{nome}", 1, {"arquivos": 0, "bytes": 0})
    return [Anexo(_nome_seguro(nome), dados, f"{origem}/{nome}")]


def anexos_do_email(dados_email: bytes, uid: str, erros: list | None = None) -> list[Anexo]:
    """Cada parte é tratada sozinha: um ZIP corrompido/suspeito não derruba os anexos bons.

    O ZIP ruim entra como anexo bruto (vira documento PENDENTE e aparece para uma pessoa);
    a parte ilegível é registrada em `erros`.
    """
    msg = message_from_bytes(dados_email, policy=policy.default)
    saida: list[Anexo] = []
    for parte in msg.walk():
        try:
            if parte.is_multipart():
                continue
            nome = parte.get_filename()
            tipo = parte.get_content_type()
            if not nome and tipo not in ("application/xml", "text/xml", "application/zip", "application/pdf"):
                continue
            conteudo = parte.get_payload(decode=True)
            if not conteudo:
                continue
            nome = nome or f"anexo.{tipo.split('/')[-1]}"
        except Exception as exc:  # noqa: BLE001 — MIME quebrado nesta parte
            if erros is not None:
                erros.append(f"parte ilegível: {type(exc).__name__}: {exc}")
            continue
        try:
            saida.extend(expandir(nome, conteudo, f"email:{uid}"))
        except Exception as exc:  # noqa: BLE001 — ZIP corrompido/suspeito: guarda o próprio ZIP
            saida.append(Anexo(_nome_seguro(nome), conteudo, f"email:{uid}/{nome}#ilegivel:{type(exc).__name__}"))
    return saida
