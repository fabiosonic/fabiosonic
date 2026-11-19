"""Configuração central.

O sistema opera SEMPRE com notas reais das fontes oficiais: não existe modo de simulação
em produção (o laboratório de testes fica em tests/ e não é instalado).

Todas as opções podem vir de variáveis de ambiente com prefixo ``MOXML_`` ou do
arquivo ``<MOXML_HOME>/moxml.env``. Senhas e chaves NUNCA ficam aqui: ficam no
cofre (``moxml.seguranca.cofre``), protegido por DPAPI no Windows.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _home_padrao() -> Path:
    if os.name == "nt":
        base = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        return Path(base) / "MO-XML-Captador"
    return Path.home() / ".moxml"


class Configuracoes(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MOXML_", extra="ignore")

    home: Path = Field(default_factory=_home_padrao)
    database_url: str | None = None  # padrão: SQLite em <home>/moxml.db

    # Servidor web local
    host: str = "127.0.0.1"
    porta: int = 8765
    api_token: str | None = None  # se definido, exigido em todas as rotas /api

    # Agendamento (cron simplificado: horários HH:MM separados por vírgula)
    horarios_execucao: str = "07:30,12:30,19:30"
    agendamento_ativo: bool = True
    executar_ao_iniciar: bool = True  # primeira captura dispara alguns segundos após iniciar o serviço

    # Rede / SEFAZ
    timeout_segundos: float = 30.0
    retentativas: int = 3
    ca_bundle: Path | None = None  # cadeia ICP-Brasil + AC raízes para validar servidores SEFAZ
    janela_sobreposicao_horas: int = 6  # sobreposição entre execuções para não perder documentos

    # Armazenamento
    raiz_xml: Path | None = None  # padrão: <home>/xml
    raiz_drive_nome: str = "MORAES & OLIVEIRA CONTABILIDADE"

    # Google Drive
    gdrive_ativo: bool = False
    gdrive_credenciais: Path | None = None  # JSON de conta de serviço ou OAuth (fora do repositório)
    gdrive_pasta_raiz_id: str | None = None  # id da pasta "MORAES & OLIVEIRA CONTABILIDADE" (ou drive compartilhado)

    # Fornecedores comerciais (desligados por padrão)
    apisimples_ativo: bool = False
    apisimples_base_url: str = "https://api.apisimples.com/v1"

    # Escritório (para DistDFe via autXML)
    escritorio_cnpj: str | None = None
    escritorio_uf: str = "RJ"

    @property
    def url_banco(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.home / 'moxml.db').as_posix()}"

    @property
    def pasta_xml(self) -> Path:
        return self.raiz_xml or (self.home / "xml")

    @property
    def pasta_logs(self) -> Path:
        return self.home / "logs"

    @property
    def pasta_cofre(self) -> Path:
        return self.home / "cofre"

    @property
    def pasta_backup(self) -> Path:
        return self.home / "backup"

    def garantir_pastas(self) -> None:
        for p in (self.home, self.pasta_xml, self.pasta_logs, self.pasta_cofre, self.pasta_backup):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def obter_config() -> Configuracoes:
    home = Path(os.environ.get("MOXML_HOME", str(_home_padrao())))
    env_file = home / "moxml.env"
    cfg = Configuracoes(_env_file=env_file if env_file.exists() else None)  # type: ignore[call-arg]
    return cfg


def redefinir_config() -> None:
    obter_config.cache_clear()
