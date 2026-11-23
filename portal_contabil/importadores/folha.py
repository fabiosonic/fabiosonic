"""Importador do resumo de folha (CSV) usado no cálculo do Fator R.

Colunas aceitas (cabeçalho obrigatório, separador ; ou ,):
    competencia;salarios;pro_labore;encargos
competencia em MM/AAAA ou AAAA-MM. `encargos` = CPP (INSS patronal) + FGTS,
que integram a folha de salários do Fator R (LC 123/2006, art. 18, §24).
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata

from ..modelos import FolhaCompetencia
from ..util import dec


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip()
    return re.sub(r"[^a-z]+", "_", s).strip("_")


def _competencia(valor: str) -> str:
    v = valor.strip()
    m = re.fullmatch(r"(\d{1,2})/(\d{4})", v)
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    m = re.fullmatch(r"(\d{4})-(\d{1,2})(-\d{1,2})?", v)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}"
    raise ValueError(f"competência inválida: {valor!r}")


def eh_csv_folha(texto: str) -> bool:
    cabecalho = _norm(texto.splitlines()[0]) if texto.strip() else ""
    return "competencia" in cabecalho and ("salario" in cabecalho or "pro_labore" in cabecalho)


def ler_folha(texto: str, arquivo: str) -> list[FolhaCompetencia]:
    amostra = texto[:2048]
    delim = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.DictReader(io.StringIO(texto), delimiter=delim)
    leitor.fieldnames = [_norm(c) for c in (leitor.fieldnames or [])]
    saida = []
    for linha in leitor:
        if not (linha.get("competencia") or "").strip():
            continue
        saida.append(FolhaCompetencia(
            competencia=_competencia(linha["competencia"]),
            salarios=dec(linha.get("salarios") or linha.get("salario")),
            pro_labore=dec(linha.get("pro_labore")),
            encargos=dec(linha.get("encargos")) + dec(linha.get("inss_cpp")) + dec(linha.get("fgts")),
            arquivo=arquivo,
        ))
    return saida
