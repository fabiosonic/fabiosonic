"""Gera `empresas.csv` a partir da planilha do escritório "CONTROLE EMPRESAS POR REGIME".

- Aba "Cadastro de Clientes": CÓD. | RAZÃO SOCIAL | CNPJ / CPF | CIDADE | REGIME TRIBUTÁRIO | SEGMENTO | OBS | STATUS.
- CÓD. é usado como código do Domínio (conferido para 1 empresa: LMG ENGENHARIA = 12). CONFERIR.
- A planilha não tem o apelido das pastas `XML NOTAS\\<Código-Apelido>`: o apelido sai da razão
  social e precisa ser conferido com `python -m mo_autonomo cadastro conferir-pastas`.
- Nada é chutado: CNPJ inválido, CPF (pessoa física), regime fora da lista ou status inativo ficam
  de fora e vão para o relatório de pendências.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from pathlib import Path

from ..util.documentos_id import cnpj_valido, so_digitos

REGIMES = {"SIMPLES NACIONAL": "SIMPLES", "SIMPLES": "SIMPLES", "LUCRO PRESUMIDO": "PRESUMIDO",
           "PRESUMIDO": "PRESUMIDO", "LUCRO REAL": "REAL", "REAL": "REAL", "MEI": "MEI",
           "IMUNE": "IMUNE", "ISENTA": "ISENTA", "IMUNE E ISENTA": "IMUNE"}
CAMPOS = ["codigo_dominio", "apelido", "cnpj", "regime", "codigo_apuracao", "uf", "municipio_ibge", "ie", "ativa"]


def _norm(t) -> str:
    return unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode().upper().strip()


def apelido_de(razao: str) -> str:
    a = _norm(razao)
    a = re.sub(r"[\\/:*?\"<>|]+", " ", a).replace("..", ".")
    return re.sub(r"\s+", " ", a).strip(" .")[:60]


def _codigo(v) -> str | None:
    s = str(v or "").strip()
    if re.fullmatch(r"\d+(\.0+)?", s):
        return str(int(float(s)))
    return None


def ler_planilha(caminho: Path) -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    aba = next((ws for ws in wb.worksheets if "CADASTRO DE CLIENTES" in _norm(ws.title)), None)
    if aba is None:
        raise ValueError("aba 'Cadastro de Clientes' não encontrada")
    linhas, cab = [], None
    for r in aba.iter_rows(values_only=True):
        celulas = [str(c).strip() if c is not None else "" for c in r]
        if cab is None:
            if any(_norm(c).startswith("COD") for c in celulas) and any("RAZAO" in _norm(c) for c in celulas):
                cab = [_norm(c) for c in celulas]
            continue
        if not any(celulas):
            continue
        linhas.append(dict(zip(cab, celulas)))
    if cab is None:
        raise ValueError("cabeçalho (CÓD., RAZÃO SOCIAL...) não encontrado")
    return linhas


def converter(linhas: list[dict]) -> tuple[list[dict], list[str]]:
    empresas, pendencias, vistos = [], [], set()

    def campo(l, *nomes):
        for k, v in l.items():
            if any(n in k for n in nomes):
                return v
        return ""

    for n, l in enumerate(linhas, start=1):
        razao = campo(l, "RAZAO")
        doc = so_digitos(campo(l, "CNPJ"))
        regime_txt = _norm(campo(l, "REGIME"))
        status = _norm(campo(l, "STATUS"))
        cod = _codigo(campo(l, "COD"))
        ref = f"linha {n} ({razao or 'sem nome'})"
        if len(doc) == 11:
            pendencias.append(f"{ref}: pessoa física (CPF) — fora do cadastro de empresas")
            continue
        if not cnpj_valido(doc):
            pendencias.append(f"{ref}: CNPJ ausente ou inválido")
            continue
        if doc in vistos:
            pendencias.append(f"{ref}: CNPJ repetido na planilha")
            continue
        regime = REGIMES.get(regime_txt)
        if regime is None:
            pendencias.append(f"{ref}: regime {regime_txt or 'vazio'!r} não reconhecido")
            continue
        if not cod:
            pendencias.append(f"{ref}: CÓD. vazio — código do Domínio desconhecido")
            continue
        vistos.add(doc)
        empresas.append({"codigo_dominio": cod, "apelido": apelido_de(razao), "cnpj": doc, "regime": regime,
                         "codigo_apuracao": "", "uf": "", "municipio_ibge": "", "ie": "",
                         "ativa": "S" if status in ("ATIVO", "") else "N"})
    return empresas, pendencias


def escrever(empresas: list[dict], destino: Path) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=CAMPOS, delimiter=";", lineterminator="\n")
    w.writeheader()
    w.writerows(empresas)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(buf.getvalue(), encoding="utf-8")


def conferir_pastas(carteira, base_xml: Path, tipos: dict) -> list[str]:
    """Empresas sem nenhuma pasta <Código-Apelido> em XML NOTAS (apelido provavelmente diferente)."""
    faltam = []
    existentes = {p.name for t in set(tipos.values()) if (base_xml / t).is_dir() for p in (base_xml / t).iterdir()}
    for e in carteira:
        if e.pasta not in existentes:
            parecidas = sorted(x for x in existentes if x.split("-", 1)[0] == e.codigo_dominio)
            faltam.append(f"{e.pasta}: não existe em {base_xml}" + (f" (pastas com o mesmo código: {parecidas})" if parecidas else ""))
    return faltam
