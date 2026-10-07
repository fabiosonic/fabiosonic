"""Amostra para conferência humana da classificação/roteamento (critério de aceite da Fase 1).

`gerar`: sorteia até N documentos por classe (semente fixa = reprodutível) e grava CSV com a
coluna `conferencia` vazia. A pessoa preenche CERTO ou ERRADO (e `observacao`).
`medir`: lê o CSV preenchido e calcula a taxa de acerto por classe e geral.
"""
from __future__ import annotations

import csv
import random
from collections import defaultdict
from pathlib import Path

COLUNAS = ["sha256", "classe", "chave", "competencia", "empresas", "destinos", "situacao", "arquivo_bruto",
           "conferencia", "observacao"]


def gerar(trilha, destino: Path, por_classe: int = 20, semente: int = 2026) -> dict:
    docs = trilha.documentos()
    caminhos = dict(trilha.con.execute("SELECT sha256, caminho_bruto FROM anexos").fetchall())
    grupos = defaultdict(list)
    for d in docs:
        grupos[d["tipo"]].append(d)
    rnd = random.Random(semente)
    linhas = []
    for classe in sorted(grupos):
        itens = sorted(grupos[classe], key=lambda d: d["sha256"])
        for d in rnd.sample(itens, min(por_classe, len(itens))):
            linhas.append({"sha256": d["sha256"], "classe": classe, "chave": d["chave"] or "",
                           "competencia": d["competencia"] or "", "empresas": ",".join(d["cnpjs"] or []),
                           "destinos": ",".join(f"{x['cnpj']}:{x['tipo']}" for x in d["destinos"] or []),
                           "situacao": d["situacao"], "arquivo_bruto": caminhos.get(d["sha256"], ""),
                           "conferencia": "", "observacao": ""})
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUNAS, delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    return {"amostra": len(linhas), "universo": len(docs), "classes": {k: len(v) for k, v in grupos.items()}}


def medir(arquivo: Path) -> dict:
    por = defaultdict(lambda: {"certo": 0, "errado": 0, "sem_conferencia": 0})
    with open(arquivo, encoding="utf-8-sig", newline="") as f:
        for l in csv.DictReader(f, delimiter=";"):
            v = (l.get("conferencia") or "").strip().upper()
            chave = "certo" if v == "CERTO" else "errado" if v == "ERRADO" else "sem_conferencia"
            por[l["classe"]][chave] += 1
    total_c = sum(x["certo"] for x in por.values())
    total_e = sum(x["errado"] for x in por.values())
    res = {"por_classe": {}, "conferidos": total_c + total_e,
           "sem_conferencia": sum(x["sem_conferencia"] for x in por.values())}
    for k, x in sorted(por.items()):
        n = x["certo"] + x["errado"]
        res["por_classe"][k] = {**x, "taxa": round(x["certo"] / n, 4) if n else None}
    res["taxa_geral"] = round(total_c / (total_c + total_e), 4) if total_c + total_e else None
    return res
