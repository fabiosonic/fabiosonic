"""Indicadores (KPIs) e relatórios."""
from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .calendario import formatar_competencia
from .models import (
    DEPARTAMENTOS,
    STATUS_DISPENSADA,
    STATUS_ENTREGUE,
    STATUS_ENTREGUE_ATRASO,
    STATUS_LABELS,
    STATUS_PENDENTE,
    Tarefa,
)


def _tarefas(sessao: Session, competencia: str | None = None, empresa_id: int | None = None) -> list[Tarefa]:
    stmt = select(Tarefa).options(joinedload(Tarefa.empresa), joinedload(Tarefa.obrigacao))
    if competencia:
        stmt = stmt.where(Tarefa.competencia == competencia)
    if empresa_id:
        stmt = stmt.where(Tarefa.empresa_id == empresa_id)
    return list(sessao.scalars(stmt).unique())


def indicadores(tarefas: list[Tarefa], hoje: date | None = None, dias_alerta: int = 3) -> dict:
    hoje = hoje or date.today()
    total = len(tarefas)
    no_prazo = sum(t.status == STATUS_ENTREGUE for t in tarefas)
    atraso = sum(t.status == STATUS_ENTREGUE_ATRASO for t in tarefas)
    dispensadas = sum(t.status == STATUS_DISPENSADA for t in tarefas)
    pendentes = [t for t in tarefas if t.status == STATUS_PENDENTE]
    atrasadas = sum(t.vencimento < hoje for t in pendentes)
    a_vencer = sum(0 <= (t.vencimento - hoje).days <= dias_alerta for t in pendentes)
    entregues = no_prazo + atraso
    considerar = total - dispensadas
    return {
        "total": total,
        "entregues": entregues,
        "no_prazo": no_prazo,
        "com_atraso": atraso,
        "dispensadas": dispensadas,
        "pendentes": len(pendentes),
        "atrasadas": atrasadas,
        "a_vencer": a_vencer,
        "conclusao_pct": round(100 * (entregues + dispensadas) / total, 1) if total else 0.0,
        "pontualidade_pct": round(100 * no_prazo / entregues, 1) if entregues else 0.0,
        "risco_pct": round(100 * atrasadas / considerar, 1) if considerar else 0.0,
    }


def por_grupo(tarefas: list[Tarefa], chave, hoje: date | None = None) -> list[tuple[str, dict]]:
    grupos: dict[str, list[Tarefa]] = defaultdict(list)
    for t in tarefas:
        grupos[chave(t)].append(t)
    return sorted(((k, indicadores(v, hoje)) for k, v in grupos.items()), key=lambda x: x[0])


def resumo_competencia(sessao: Session, competencia: str, hoje: date | None = None) -> dict:
    tarefas = _tarefas(sessao, competencia)
    return {
        "geral": indicadores(tarefas, hoje),
        "departamentos": por_grupo(tarefas, lambda t: DEPARTAMENTOS.get(t.obrigacao.departamento, "?"), hoje),
        "obrigacoes": por_grupo(tarefas, lambda t: t.obrigacao.nome, hoje),
        "empresas": por_grupo(tarefas, lambda t: f"{t.empresa.codigo} - {t.empresa.nome_exibicao}", hoje),
        "responsaveis": por_grupo(
            [t for t in tarefas if t.obrigacao.tipo == "entrega"],
            lambda t: (r.nome if (r := t.empresa.responsavel_do(t.obrigacao.departamento)) else "Sem responsável"),
            hoje),
    }


def exportar_csv(tarefas: list[Tarefa]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Código", "Empresa", "CNPJ", "Regime", "Departamento", "Obrigação", "Competência",
                "Vencimento", "Situação", "Data da entrega", "Origem da baixa", "Comprovantes", "Observação"])
    for t in sorted(tarefas, key=lambda x: (x.empresa.codigo, x.vencimento)):
        w.writerow([
            t.empresa.codigo, t.empresa.razao_social, t.empresa.cnpj_formatado, t.empresa.regime,
            DEPARTAMENTOS.get(t.obrigacao.departamento, ""), t.obrigacao.nome,
            formatar_competencia(t.competencia, t.obrigacao.periodicidade), t.vencimento.strftime("%d/%m/%Y"),
            STATUS_LABELS.get(t.status, t.status),
            t.data_entrega.strftime("%d/%m/%Y %H:%M") if t.data_entrega else "",
            t.origem_baixa, " | ".join(d.link for d in t.documentos), t.observacao,
        ])
    return "﻿" + buf.getvalue()  # BOM para o Excel abrir acentos corretamente
