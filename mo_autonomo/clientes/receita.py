"""Leitura dos Dados Abertos do CNPJ (Receita Federal) filtrando só a carteira.

Os arquivos oficiais são CSV sem cabeçalho, separador `;`, aspas, codificação latin-1.
As POSIÇÕES de coluna abaixo são configuráveis (config `receita.colunas`) e devem ser
conferidas contra o PDF de metadados oficial. Os VALORES de código (situação ativa,
opção 'sim') vêm da norma DICIONARIO_DADOS_ABERTOS_CNPJ — sem ela conferida, o perfil
não usa esses campos (fica pendência).
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date
from pathlib import Path

COLUNAS_PADRAO = {
    "empresas": {"cnpj_basico": 0, "razao_social": 1, "natureza_juridica": 2, "porte": 5},
    "estabelecimentos": {
        "cnpj_basico": 0, "cnpj_ordem": 1, "cnpj_dv": 2, "matriz_filial": 3,
        "situacao_cadastral": 5, "data_situacao": 6, "data_inicio": 10,
        "cnae_principal": 11, "cnae_secundarias": 12, "uf": 19, "municipio_rfb": 20,
    },
    "simples": {
        "cnpj_basico": 0, "opcao_simples": 1, "data_opcao_simples": 2, "data_exclusao_simples": 3,
        "opcao_mei": 4, "data_opcao_mei": 5, "data_exclusao_mei": 6,
    },
}


def data_rfb(valor: str | None) -> date | None:
    v = (valor or "").strip()
    if len(v) != 8 or not v.isdigit() or v == "00000000":
        return None
    try:
        return date(int(v[:4]), int(v[4:6]), int(v[6:]))
    except ValueError:
        return None


def _linhas(caminho: Path):
    """Itera linhas de um CSV da RFB, aceitando o .zip oficial ou o CSV extraído."""
    if zipfile.is_zipfile(caminho):
        with zipfile.ZipFile(caminho) as z:
            for nome in z.namelist():
                with z.open(nome) as f:
                    yield from csv.reader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
    else:
        with open(caminho, encoding="latin-1", newline="") as f:
            yield from csv.reader(f, delimiter=";")


def _campo(linha, idx):
    return linha[idx].strip() if idx < len(linha) else ""


def extrair_carteira(pasta: Path, cnpjs: set[str], colunas: dict | None = None) -> dict[str, dict]:
    """Varre os arquivos da pasta e devolve {cnpj14: dados} só dos CNPJs da carteira."""
    col = {k: dict(v) for k, v in COLUNAS_PADRAO.items()}
    for k, v in (colunas or {}).items():
        col[k].update(v)
    basicos = {c[:8] for c in cnpjs}
    pasta = Path(pasta)
    empresas: dict[str, dict] = {}
    simples: dict[str, dict] = {}
    estab: dict[str, dict] = {}
    for arq in sorted(pasta.iterdir()):
        nome = arq.name.upper()
        if "EMPRE" in nome:
            tipo = "empresas"
        elif "ESTABELE" in nome:
            tipo = "estabelecimentos"
        elif "SIMPLES" in nome:
            tipo = "simples"
        else:
            continue
        c = col[tipo]
        for linha in _linhas(arq):
            if not linha:
                continue
            base = _campo(linha, c["cnpj_basico"])
            if base not in basicos:
                continue
            if tipo == "empresas":
                empresas[base] = {
                    "razao_social": _campo(linha, c["razao_social"]),
                    "natureza_juridica": _campo(linha, c["natureza_juridica"]),
                    "porte": _campo(linha, c["porte"]),
                }
            elif tipo == "simples":
                simples[base] = {
                    "opcao_simples": _campo(linha, c["opcao_simples"]),
                    "data_opcao_simples": data_rfb(_campo(linha, c["data_opcao_simples"])),
                    "data_exclusao_simples": data_rfb(_campo(linha, c["data_exclusao_simples"])),
                    "opcao_mei": _campo(linha, c["opcao_mei"]),
                    "data_opcao_mei": data_rfb(_campo(linha, c["data_opcao_mei"])),
                    "data_exclusao_mei": data_rfb(_campo(linha, c["data_exclusao_mei"])),
                }
            else:
                cnpj = base + _campo(linha, c["cnpj_ordem"]) + _campo(linha, c["cnpj_dv"])
                if cnpj not in cnpjs:
                    continue
                sec = _campo(linha, c["cnae_secundarias"])
                estab[cnpj] = {
                    "matriz_filial": _campo(linha, c["matriz_filial"]),
                    "situacao_cadastral": _campo(linha, c["situacao_cadastral"]),
                    "data_situacao": data_rfb(_campo(linha, c["data_situacao"])),
                    "data_inicio": data_rfb(_campo(linha, c["data_inicio"])),
                    "cnae_principal": _campo(linha, c["cnae_principal"]),
                    "cnaes_secundarias": [s for s in sec.split(",") if s.strip()],
                    "uf": _campo(linha, c["uf"]),
                    "municipio_rfb": _campo(linha, c["municipio_rfb"]),
                }
    out = {}
    for cnpj in cnpjs:
        base = cnpj[:8]
        if cnpj in estab or base in empresas or base in simples:
            out[cnpj] = {
                "estabelecimento": estab.get(cnpj), "empresa": empresas.get(base), "simples": simples.get(base),
            }
    return out
