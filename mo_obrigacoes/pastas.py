"""Criação da estrutura padrão de pastas no Google Drive.

    Clientes/
      0001 - PADARIA BOM PAO LTDA/
        2026/
          01 - Janeiro/
            01 - Fiscal/
            02 - Contabil/
            03 - Pessoal/
            04 - Documentos do Cliente/
          ...
          Anual/

O classificador não depende desta estrutura (lê o conteúdo dos arquivos), mas
ela ajuda a equipe e serve de dica de competência e de departamento.
"""
from __future__ import annotations

import re

from .drive.base import DriveClient
from .models import Empresa

NOMES_MESES = ["Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho", "Julho",
               "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
SUBPASTAS = ["01 - Fiscal", "02 - Contabil", "03 - Pessoal", "04 - Documentos do Cliente"]


def nome_pasta_empresa(emp: Empresa) -> str:
    nome = re.sub(r'[\\/:*?"<>|]', "", emp.razao_social).strip()
    return f"{emp.codigo} - {nome}"


def criar_pasta_empresa(drive: DriveClient, emp: Empresa, raiz_id: str) -> str:
    if not emp.drive_folder_id:
        emp.drive_folder_id = drive.garantir_pasta(nome_pasta_empresa(emp), raiz_id)
    return emp.drive_folder_id


def criar_estrutura_ano(drive: DriveClient, emp: Empresa, ano: int, meses: list[int] | None = None) -> int:
    """Cria (idempotente) as pastas do ano. Retorna a quantidade de pastas garantidas."""
    if not emp.drive_folder_id:
        raise ValueError(f"Empresa {emp.codigo} sem pasta no Drive")
    pasta_ano = drive.garantir_pasta(str(ano), emp.drive_folder_id)
    n = 1
    for m in meses or range(1, 13):
        pasta_mes = drive.garantir_pasta(f"{m:02d} - {NOMES_MESES[m - 1]}", pasta_ano)
        n += 1
        for sub in SUBPASTAS:
            drive.garantir_pasta(sub, pasta_mes)
            n += 1
    drive.garantir_pasta("Anual", pasta_ano)
    return n + 1
