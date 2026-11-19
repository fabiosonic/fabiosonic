"""Sincronização incremental com o Google Drive (API v3).

- Espelha a árvore local ``1-CLIENTES/CLIENTES ATIVOS/<EMPRESA>/XML/<ANO>/<MM>/...`` dentro da pasta raiz
  "MORAES & OLIVEIRA CONTABILIDADE" (id configurado), reaproveitando pastas existentes por nome
  normalizado (sem acento/caixa) — adapta-se à estrutura real sem criar duplicatas.
- Nunca sobrescreve: arquivo remoto com mesmo nome e conteúdo diferente gera CONFLITO e o novo é enviado
  como ``<nome>-vN``.
- Um arquivo só é CONFIRMADO quando a API devolve o id e o ``md5Checksum`` igual ao MD5 local.
- Suporta Drives compartilhados (supportsAllDrives).
"""

from __future__ import annotations

import hashlib
import json
import logging
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy import select

from ..db.modelos import ArquivoDrive

log = logging.getLogger("moxml.gdrive")
PASTA_MIME = "application/vnd.google-apps.folder"


def normalizar(nome: str) -> str:
    n = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return " ".join(n.upper().split())


class ClienteDrive(Protocol):
    def listar_filhos(self, pai_id: str, somente_pastas: bool) -> list[dict]: ...
    def criar_pasta(self, nome: str, pai_id: str) -> str: ...
    def enviar(self, caminho: Path, nome: str, pai_id: str) -> dict: ...  # {"id", "md5Checksum"}


class ClienteDriveGoogle:
    def __init__(self, credenciais: Path):
        from google.oauth2 import service_account
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        info = json.loads(Path(credenciais).read_text(encoding="utf-8"))
        escopos = ["https://www.googleapis.com/auth/drive"]
        if info.get("type") == "service_account":
            cred = service_account.Credentials.from_service_account_info(info, scopes=escopos)
        else:
            cred = Credentials.from_authorized_user_info(info, escopos)
        self.svc = build("drive", "v3", credentials=cred, cache_discovery=False)

    def listar_filhos(self, pai_id: str, somente_pastas: bool) -> list[dict]:
        q = f"'{pai_id}' in parents and trashed = false"
        if somente_pastas:
            q += f" and mimeType = '{PASTA_MIME}'"
        itens, token = [], None
        while True:
            r = self.svc.files().list(q=q, fields="nextPageToken, files(id, name, md5Checksum, mimeType)",
                                      pageSize=1000, pageToken=token, supportsAllDrives=True,
                                      includeItemsFromAllDrives=True).execute()
            itens += r.get("files", [])
            token = r.get("nextPageToken")
            if not token:
                return itens

    def criar_pasta(self, nome: str, pai_id: str) -> str:
        r = self.svc.files().create(body={"name": nome, "mimeType": PASTA_MIME, "parents": [pai_id]},
                                    fields="id", supportsAllDrives=True).execute()
        return r["id"]

    def enviar(self, caminho: Path, nome: str, pai_id: str) -> dict:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(caminho), mimetype="application/xml", resumable=False)
        return self.svc.files().create(body={"name": nome, "parents": [pai_id]}, media_body=media,
                                       fields="id, md5Checksum", supportsAllDrives=True).execute()


class SincronizadorDrive:
    def __init__(self, cliente: ClienteDrive, raiz_id: str):
        self.c = cliente
        self.raiz = raiz_id
        self._pastas: dict[tuple[str, ...], str] = {(): raiz_id}
        self._filhos: dict[str, dict[str, dict]] = {}

    def pasta(self, partes: tuple[str, ...]) -> str:
        if partes in self._pastas:
            return self._pastas[partes]
        pai = self.pasta(partes[:-1])
        nome = partes[-1]
        existentes = {normalizar(f["name"]): f["id"] for f in self.c.listar_filhos(pai, True)}
        fid = existentes.get(normalizar(nome)) or self.c.criar_pasta(nome, pai)
        self._pastas[partes] = fid
        return fid

    def _arquivos(self, pasta_id: str) -> dict[str, dict]:
        if pasta_id not in self._filhos:
            self._filhos[pasta_id] = {f["name"]: f for f in self.c.listar_filhos(pasta_id, False)
                                      if f.get("mimeType") != PASTA_MIME}
        return self._filhos[pasta_id]

    def enviar(self, local: Path, rel: str) -> tuple[str, str | None, str]:
        """Retorna (status, file_id, mensagem)."""
        md5 = hashlib.md5(local.read_bytes()).hexdigest()  # noqa: S324 - comparação com md5Checksum do Drive
        partes = tuple(Path(rel).parts)
        pid = self.pasta(partes[:-1])
        arquivos = self._arquivos(pid)
        nome = partes[-1]
        if nome in arquivos:
            if arquivos[nome].get("md5Checksum") == md5:
                return "CONFIRMADO", arquivos[nome]["id"], "já existia com conteúdo idêntico"
            base, ext = nome.rsplit(".", 1) if "." in nome else (nome, "")
            v = 2
            while f"{base}-v{v}.{ext}" in arquivos:
                if arquivos[f"{base}-v{v}.{ext}"].get("md5Checksum") == md5:
                    return "CONFIRMADO", arquivos[f"{base}-v{v}.{ext}"]["id"], "versão já enviada"
                v += 1
            nome_envio, status = f"{base}-v{v}.{ext}", "CONFLITO"
        else:
            nome_envio, status = nome, "CONFIRMADO"
        r = self.c.enviar(local, nome_envio, pid)
        if not r.get("id") or r.get("md5Checksum") != md5:
            return "ERRO", r.get("id"), f"API não confirmou integridade (md5 local {md5}, remoto {r.get('md5Checksum')})"
        arquivos[nome_envio] = {"id": r["id"], "name": nome_envio, "md5Checksum": md5}
        return status, r["id"], "enviado" if status == "CONFIRMADO" else f"remoto divergente; enviado como {nome_envio}"


def sincronizar_drive(app, cliente: ClienteDrive | None = None, limite: int | None = None) -> dict:  # noqa: ANN001
    cfg = app.cfg
    if cliente is None:
        if not (cfg.gdrive_credenciais and cfg.gdrive_pasta_raiz_id):
            raise RuntimeError("Google Drive não configurado (MOXML_GDRIVE_CREDENCIAIS / MOXML_GDRIVE_PASTA_RAIZ_ID)")
        cliente = ClienteDriveGoogle(cfg.gdrive_credenciais)
    sync = SincronizadorDrive(cliente, cfg.gdrive_pasta_raiz_id or "raiz")
    res = {"confirmados": 0, "conflitos": 0, "erros": 0, "ignorados": 0}
    raiz = Path(cfg.pasta_xml)
    arquivos = sorted(p for p in raiz.rglob("*.xml") if p.is_file())
    with app.sessoes() as s:
        for i, p in enumerate(arquivos):
            if limite and i >= limite:
                break
            rel = p.relative_to(raiz).as_posix()
            md5 = hashlib.md5(p.read_bytes()).hexdigest()  # noqa: S324
            reg = s.scalar(select(ArquivoDrive).where(ArquivoDrive.caminho_local == rel))
            if reg and reg.status in ("CONFIRMADO", "CONFLITO") and reg.hash_md5 == md5:
                res["ignorados"] += 1
                continue
            if reg is None:
                reg = ArquivoDrive(caminho_local=rel, caminho_remoto=rel, hash_md5=md5, tentativas=0, status="PENDENTE")
                s.add(reg)
            reg.hash_md5 = md5
            reg.tentativas += 1
            try:
                status, fid, msg = sync.enviar(p, rel)
            except Exception as e:  # noqa: BLE001 - falha do Drive não derruba a rotina
                status, fid, msg = "ERRO", None, f"{type(e).__name__}: {e}"
            reg.status, reg.drive_file_id, reg.erro = status, fid, None if status != "ERRO" else msg
            if status in ("CONFIRMADO", "CONFLITO"):
                reg.confirmado_em = datetime.now(UTC)
            res[{"CONFIRMADO": "confirmados", "CONFLITO": "conflitos", "ERRO": "erros"}[status]] += 1
            s.commit()
    log.info("drive: %s", res)
    return res
