"""Extração de anexos (inclusive ZIP aninhado) com limites contra zip-bomba."""
from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from email import message_from_bytes, policy
from pathlib import PurePosixPath

LIMITES_PADRAO = {
    "zip_max_profundidade": 5,
    "zip_max_arquivos": 50000,           # lote mensal de NFC-e de varejo passa fácil de 2000
    "zip_max_bytes": 2 * 1024 * 1024 * 1024,
    "zip_max_razao": 200,                # descompactado / compactado (zip-bomba)
}
LIMITE_PROFUNDIDADE = LIMITES_PADRAO["zip_max_profundidade"]


class ZipSuspeito(ValueError):
    pass


@dataclass
class Anexo:
    nome: str
    dados: bytes
    origem: str  # ex.: "email:<uid>/lote.zip/notas/1.xml"


def _nome_seguro(nome: str) -> str:
    return PurePosixPath(nome.replace("\\", "/")).name or "sem_nome"


def _e_pacote_office(dados: bytes) -> bool:
    """xlsx/docx/pptx/ods/odt são ZIP por dentro, mas são UM documento: não desmontar."""
    try:
        with zipfile.ZipFile(io.BytesIO(dados)) as z:
            nomes = set(z.namelist())
    except zipfile.BadZipFile:
        return False
    return "[Content_Types].xml" in nomes or "mimetype" in nomes


def _e_zip_para_abrir(nome: str, dados: bytes) -> bool:
    return dados.startswith(b"PK\x03\x04") and not _e_pacote_office(dados)


def _expandir_zip(dados: bytes, origem: str, profundidade: int, contagem: dict, lim: dict) -> list[Anexo]:
    if profundidade > lim["zip_max_profundidade"]:
        raise ZipSuspeito(f"ZIP aninhado além de {lim['zip_max_profundidade']} níveis (zip_max_profundidade): {origem}")
    saida: list[Anexo] = []
    with zipfile.ZipFile(io.BytesIO(dados)) as z:
        for info in z.infolist():
            if info.is_dir():
                continue
            contagem["arquivos"] += 1
            contagem["bytes"] += info.file_size
            if contagem["arquivos"] > lim["zip_max_arquivos"]:
                raise ZipSuspeito(f"ZIP com mais de {lim['zip_max_arquivos']} arquivos (zip_max_arquivos): {origem}")
            if contagem["bytes"] > lim["zip_max_bytes"]:
                raise ZipSuspeito(f"ZIP acima de {lim['zip_max_bytes']} bytes descompactado (zip_max_bytes): {origem}")
            if info.compress_size and info.file_size / max(info.compress_size, 1) > lim["zip_max_razao"]:
                raise ZipSuspeito(f"razão de compressão suspeita em {info.filename} (zip_max_razao)")
            conteudo = z.read(info)
            caminho = f"{origem}/{info.filename}"
            if _e_zip_para_abrir(info.filename, conteudo):
                saida.extend(_expandir_zip(conteudo, caminho, profundidade + 1, contagem, lim))
            else:
                saida.append(Anexo(_nome_seguro(info.filename), conteudo, caminho))
    return saida


def expandir(nome: str, dados: bytes, origem: str, limites: dict | None = None) -> list[Anexo]:
    lim = {**LIMITES_PADRAO, **(limites or {})}
    if _e_zip_para_abrir(nome, dados):
        return _expandir_zip(dados, f"{origem}/{nome}", 1, {"arquivos": 0, "bytes": 0}, lim)
    return [Anexo(_nome_seguro(nome), dados, f"{origem}/{nome}")]


def anexos_do_email(dados_email: bytes, uid: str, erros: list | None = None, limites: dict | None = None) -> list[Anexo]:
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
            saida.extend(expandir(nome, conteudo, f"email:{uid}", limites))
        except Exception as exc:  # noqa: BLE001 — ZIP corrompido/suspeito: guarda o próprio ZIP
            saida.append(Anexo(_nome_seguro(nome), conteudo, f"email:{uid}/{nome}#ilegivel:{type(exc).__name__}"))
            if erros is not None:
                erros.append(f"{nome}: {exc} (guardado como documento pendente)")
    return saida
