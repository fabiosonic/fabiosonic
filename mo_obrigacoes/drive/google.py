"""Cliente do Google Drive (API v3) usando conta de serviço.

Configuração (ver docs/implantacao.md):
  1. Crie um projeto no Google Cloud e ative a "Google Drive API".
  2. Crie uma conta de serviço e baixe a chave JSON (MO_GOOGLE_CREDENTIALS).
  3. Compartilhe a pasta raiz "Clientes" com o e-mail da conta de serviço
     (leitor basta para monitorar; editor para o sistema criar a estrutura de pastas).
     Em Google Workspace, alternativamente use delegação em todo o domínio
     (MO_GOOGLE_IMPERSONATE=usuario@dominio).
"""
from __future__ import annotations

import io
import re
from collections import deque
from datetime import datetime
from typing import Iterator
from zoneinfo import ZoneInfo

from .base import ArquivoDrive, DriveClient

PASTA = "application/vnd.google-apps.folder"
ATALHO = "application/vnd.google-apps.shortcut"
EXPORTACOES = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
}
FUSO_ESCRITORIO = ZoneInfo("America/Sao_Paulo")
TENTATIVAS = 5  # novas tentativas com espera exponencial em 429/5xx (googleapiclient)
_RE_ID = re.compile(r"[A-Za-z0-9_-]+")


def validar_id(valor: str) -> str:
    """IDs do Drive têm só letras, números, '_' e '-'. Impede injeção na query (q=...)."""
    if not _RE_ID.fullmatch(valor or ""):
        raise ValueError(f"ID de pasta do Drive inválido: {valor!r}")
    return valor


CAMPOS = (
    "nextPageToken, files(id, name, mimeType, size, md5Checksum, createdTime, modifiedTime, "
    "webViewLink, lastModifyingUser(emailAddress, displayName), owners(emailAddress))"
)


def _dt(valor: str | None) -> datetime | None:
    if not valor:
        return None
    # converte para o horário de Brasília (sem tzinfo): a data de entrega é comparada com o vencimento local
    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(FUSO_ESCRITORIO).replace(tzinfo=None)


class GoogleDriveClient(DriveClient):
    def __init__(self, credenciais: str, impersonar: str = "", somente_leitura: bool = False, servico=None):
        if servico is not None:  # injeção para testes
            self.servico = servico
            return
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        escopo = "https://www.googleapis.com/auth/drive" + (".readonly" if somente_leitura else "")
        cred = service_account.Credentials.from_service_account_file(credenciais, scopes=[escopo])
        if impersonar:
            cred = cred.with_subject(impersonar)
        self.servico = build("drive", "v3", credentials=cred, cache_discovery=False)

    def _filhos(self, pasta_id: str) -> Iterator[dict]:
        token = None
        while True:
            resp = self.servico.files().list(
                q=f"'{validar_id(pasta_id)}' in parents and trashed = false",
                fields=CAMPOS,
                pageSize=1000,
                pageToken=token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute(num_retries=TENTATIVAS)
            yield from resp.get("files", [])
            token = resp.get("nextPageToken")
            if not token:
                break

    def listar_arquivos(self, pasta_id: str, modificado_apos: datetime | None = None) -> Iterator[ArquivoDrive]:
        fila = deque([(pasta_id, "")])
        visitadas = set()
        while fila:
            atual, prefixo = fila.popleft()
            if atual in visitadas:
                continue
            visitadas.add(atual)
            for f in self._filhos(atual):
                caminho = f"{prefixo}{f['name']}"
                if f["mimeType"] == PASTA:
                    fila.append((f["id"], caminho + "/"))
                    continue
                if f["mimeType"] == ATALHO:
                    continue
                modificado = _dt(f.get("modifiedTime"))
                if modificado_apos and modificado and modificado <= modificado_apos:
                    continue
                usuario = (f.get("lastModifyingUser") or {}).get("emailAddress") or \
                    ((f.get("owners") or [{}])[0].get("emailAddress", ""))
                yield ArquivoDrive(
                    id=f["id"],
                    nome=f["name"],
                    mime_type=f["mimeType"],
                    caminho=caminho,
                    tamanho=int(f.get("size", 0) or 0),
                    md5=f.get("md5Checksum", ""),
                    criado_em=_dt(f.get("createdTime")),
                    modificado_em=modificado,
                    link=f.get("webViewLink", ""),
                    enviado_por=usuario or "",
                )

    def baixar(self, arquivo: ArquivoDrive) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload

        if arquivo.mime_type in EXPORTACOES:
            req = self.servico.files().export_media(fileId=arquivo.id, mimeType=EXPORTACOES[arquivo.mime_type])
        elif arquivo.mime_type.startswith("application/vnd.google-apps"):
            return b""
        else:
            req = self.servico.files().get_media(fileId=arquivo.id, supportsAllDrives=True)
        buf = io.BytesIO()
        down = MediaIoBaseDownload(buf, req)
        concluido = False
        while not concluido:
            _, concluido = down.next_chunk(num_retries=TENTATIVAS)
        return buf.getvalue()

    def garantir_pasta(self, nome: str, pai_id: str) -> str:
        nome_q = nome.replace("\\", "\\\\").replace("'", "\\'")
        resp = self.servico.files().list(
            q=f"'{validar_id(pai_id)}' in parents and name = '{nome_q}' and mimeType = '{PASTA}' and trashed = false",
            fields="files(id)",
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute(num_retries=TENTATIVAS)
        if resp.get("files"):
            return resp["files"][0]["id"]
        criada = self.servico.files().create(
            body={"name": nome, "mimeType": PASTA, "parents": [pai_id]},
            fields="id",
            supportsAllDrives=True,
        ).execute()  # sem retry: create não é idempotente (evita pasta duplicada)
        return criada["id"]
