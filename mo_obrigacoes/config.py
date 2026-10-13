"""Configurações do sistema, lidas de variáveis de ambiente (ou de um arquivo .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _carregar_dotenv(caminho: str = ".env") -> None:
    """Carrega um .env simples (CHAVE=valor) sem dependências externas."""
    p = Path(caminho)
    if not p.exists():
        return
    for linha in p.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.strip())


def _bool(valor: str | None, padrao: bool = False) -> bool:
    if valor is None or valor == "":
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


@dataclass
class Config:
    database_url: str = "sqlite:///./dados/mo_obrigacoes.db"
    admin_user: str = "admin"
    admin_password: str = ""
    drive_backend: str = "local"
    google_credentials: str = "./credenciais/service-account.json"
    google_impersonate: str = ""
    drive_root_folder_id: str = ""
    local_drive_path: str = "./dados/drive_local"
    sync_interval_minutes: int = 15
    dias_alerta_vencimento: int = 3
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_remetente: str = ""
    email_gestor: str = ""
    cobranca_automatica_cliente: bool = False
    webhook_url: str = ""
    nome_escritorio: str = "Moraes e Oliveira Contabilidade"
    extras: dict = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> "Config":
        _carregar_dotenv()
        e = os.environ.get
        return cls(
            database_url=e("MO_DATABASE_URL", cls.database_url),
            admin_user=e("MO_ADMIN_USER", "admin"),
            admin_password=e("MO_ADMIN_PASSWORD", ""),
            drive_backend=e("MO_DRIVE_BACKEND", "local"),
            google_credentials=e("MO_GOOGLE_CREDENTIALS", cls.google_credentials),
            google_impersonate=e("MO_GOOGLE_IMPERSONATE", ""),
            drive_root_folder_id=e("MO_DRIVE_ROOT_FOLDER_ID", ""),
            local_drive_path=e("MO_LOCAL_DRIVE_PATH", cls.local_drive_path),
            sync_interval_minutes=int(e("MO_SYNC_INTERVAL_MINUTES", "15")),
            dias_alerta_vencimento=int(e("MO_DIAS_ALERTA_VENCIMENTO", "3")),
            smtp_host=e("MO_SMTP_HOST", ""),
            smtp_port=int(e("MO_SMTP_PORT", "587")),
            smtp_user=e("MO_SMTP_USER", ""),
            smtp_password=e("MO_SMTP_PASSWORD", ""),
            email_remetente=e("MO_EMAIL_REMETENTE", ""),
            email_gestor=e("MO_EMAIL_GESTOR", ""),
            cobranca_automatica_cliente=_bool(e("MO_COBRANCA_AUTOMATICA_CLIENTE")),
            webhook_url=e("MO_WEBHOOK_URL", ""),
            nome_escritorio=e("MO_NOME_ESCRITORIO", cls.nome_escritorio),
        )


_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(cfg: Config) -> None:
    """Usado nos testes para injetar uma configuração."""
    global _config
    _config = cfg
