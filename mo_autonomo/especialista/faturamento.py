"""Faturamento do mês pelos XML emitidos × receita declarada (PGDAS-D/DCTFWeb).

Fato objetivo (CONTROLE): soma de documentos emitidos pela empresa na competência.
- NF-e só entra como receita se o sentido for saída (MOC_NFE.tp_nf_saida conferido);
  sem o parâmetro, as NF-e ficam fora da soma e isso é dito no resultado.
- Canceladas só são excluídas com MOC_NFE.tp_evento_cancelamento conferido.
- Receita declarada vem de arquivo fornecido pelo escritório (dados/apuracao/receitas.csv:
  cnpj;competencia;receita_declarada;fonte). Sem arquivo, não há cruzamento.
"""
from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from ..util.dinheiro import dinheiro
from ..util.documentos_id import so_digitos
from .modelo import CONTROLE, Achado


def faturamento(registros: list[dict], cnpj: str, catalogo) -> dict:
    saida = catalogo.parametro("MOC_NFE", "tp_nf_saida")
    canc = catalogo.parametro("MOC_NFE", "tp_evento_cancelamento")
    homol = catalogo.parametro("MOC_NFE", "cstat_evento_homologado")
    canc = [str(x) for x in canc] if canc is not None and homol is not None else None
    canceladas = set()
    if canc is not None:
        homol = [str(x) for x in homol]
        canceladas = {r["resumo"].get("chave_ref") for r in registros
                      if (r["resumo"].get("tipo") or "").startswith("EVENTO_") and str(r["resumo"].get("tp_evento")) in canc
                      and str(r["resumo"].get("cstat")) in homol}
    por_tipo = {"NFE": Decimal("0.00"), "NFCE": Decimal("0.00"), "NFSE": Decimal("0.00")}
    obs = []
    nfe_ignoradas = 0
    vistos = set()
    for r in registros:
        res = r.get("resumo") or {}
        tipo, valor = res.get("tipo"), res.get("valor")
        if valor is None or r.get("chave") in vistos:
            continue
        if r.get("chave") in canceladas or res.get("cancelada"):
            continue
        if tipo == "NFE" and res.get("emitente") == cnpj:
            if saida is None:
                nfe_ignoradas += 1
                continue
            if str(res.get("tp_nf")) != str(saida):
                continue
        elif tipo == "NFCE" and res.get("emitente") == cnpj:
            pass
        elif tipo == "NFSE" and res.get("prestador") == cnpj:
            pass
        else:
            continue
        vistos.add(r.get("chave"))
        por_tipo[tipo] += dinheiro(valor)
    if nfe_ignoradas:
        obs.append(f"{nfe_ignoradas} NF-e emitida(s) fora da soma: sentido não verificável (MOC_NFE.tp_nf_saida não conferido).")
    if canc is None:
        obs.append("NF-e canceladas não excluídas: MOC_NFE.tp_evento_cancelamento/cstat_evento_homologado não conferidos.")
    total = sum(por_tipo.values(), Decimal("0.00"))
    return {"total": total, "por_tipo": por_tipo, "observacoes": obs, "completo": not obs}


def ler_receitas_declaradas(caminho: Path) -> dict[tuple[str, str], dict]:
    if not Path(caminho).exists():
        return {}
    out = {}
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            out[(so_digitos(l["cnpj"]), l["competencia"].strip())] = {
                "valor": dinheiro(l["receita_declarada"]), "fonte": (l.get("fonte") or "").strip() or "declaração"}
    return out


def cruzar(fat: dict, declarada: dict | None, cnpj: str, competencia: str, tolerancia: Decimal) -> list[Achado]:
    if declarada is None:
        return []
    dif = fat["total"] - declarada["valor"]
    if abs(dif) <= tolerancia:
        return []
    ressalva = "" if fat["completo"] else " Ressalva: " + " ".join(fat["observacoes"])
    return [Achado("COMP_RECEITA_X_DECLARADA", "Faturamento dos XML × receita declarada", CONTROLE,
                   f"XML emitidos somam {fat['total']}; {declarada['fonte']} declara {declarada['valor']} "
                   f"(diferença {dif}).{ressalva}", cnpj, competencia, None, [],
                   "Conferir notas não recebidas/canceladas e a apuração antes de retificar.",
                   bool(fat["completo"]), dif)]
