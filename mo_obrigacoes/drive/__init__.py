from __future__ import annotations

from ..config import Config, get_config
from .base import ArquivoDrive, DriveClient, extrair_texto

__all__ = ["ArquivoDrive", "DriveClient", "extrair_texto", "criar_cliente", "extrair_id_pasta"]


def criar_cliente(cfg: Config | None = None) -> DriveClient:
    cfg = cfg or get_config()
    if cfg.drive_backend == "google":
        from .google import GoogleDriveClient

        return GoogleDriveClient(cfg.google_credentials, cfg.google_impersonate)
    from .local import LocalDriveClient

    return LocalDriveClient(cfg.local_drive_path)


def extrair_id_pasta(valor: str) -> str:
    """Aceita o ID ou a URL da pasta (https://drive.google.com/drive/folders/<ID>)."""
    valor = (valor or "").strip()
    if "/folders/" in valor:
        valor = valor.split("/folders/", 1)[1].split("?")[0].split("/")[0]
    return valor
