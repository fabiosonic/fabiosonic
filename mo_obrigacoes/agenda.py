"""Geração da agenda de obrigações (tarefas por empresa × obrigação × competência)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .calendario import calcular_vencimento, parse_competencia
from .models import Empresa, Evento, Obrigacao, Tarefa


def _avaliar_regra(empresa: Empresa, regra: dict) -> bool:
    regimes = regra.get("regimes")
    if regimes and empresa.regime not in regimes:
        return False
    for flag in regra.get("exige", []):
        if not getattr(empresa, flag, False):
            return False
    algum = regra.get("exige_algum")
    if algum and not any(getattr(empresa, f, False) for f in algum):
        return False
    for flag in regra.get("nao_exige", []):
        if getattr(empresa, flag, False):
            return False
    return True


def obrigacao_aplicavel(empresa: Empresa, obrigacao: Obrigacao) -> bool:
    pers = (empresa.personalizacoes or {}).get(obrigacao.codigo, {})
    if pers.get("ignorar"):
        return False
    if pers.get("incluir"):
        return True
    ap = obrigacao.aplicabilidade or {}
    if "qualquer" in ap:
        return any(_avaliar_regra(empresa, r) for r in ap["qualquer"])
    return _avaliar_regra(empresa, ap)


def ocorre_na_competencia(obrigacao: Obrigacao, competencia: str) -> bool:
    _, mes = parse_competencia(competencia)
    if obrigacao.periodicidade == "trimestral":
        return mes in (3, 6, 9, 12)
    if obrigacao.periodicidade == "anual":
        return mes == 12
    return True


def regra_efetiva(empresa: Empresa, obrigacao: Obrigacao) -> dict:
    """Regra de vencimento do catálogo com as personalizações da empresa aplicadas."""
    regra = dict(obrigacao.regra_vencimento or {})
    pers = (empresa.personalizacoes or {}).get(obrigacao.codigo, {})
    if "regra" in pers:
        regra = dict(pers["regra"])
    if "dia" in pers:
        regra["tipo"] = "dia_fixo"
        regra["dia"] = int(pers["dia"])
    if "ajuste" in pers:
        regra["ajuste"] = pers["ajuste"]
    return regra


def gerar_agenda(sessao: Session, competencia: str, empresas: list[Empresa] | None = None,
                 usuario: str = "sistema") -> dict:
    """Cria as tarefas da competência (idempotente). Retorna estatísticas."""
    if empresas is None:
        empresas = list(sessao.scalars(select(Empresa).where(Empresa.ativa.is_(True))))
    obrigacoes = list(sessao.scalars(select(Obrigacao).where(Obrigacao.ativa.is_(True))))
    existentes = {
        (t.empresa_id, t.obrigacao_id)
        for t in sessao.scalars(select(Tarefa).where(Tarefa.competencia == competencia))
    }
    criadas = 0
    for emp in empresas:
        for ob in obrigacoes:
            if not ocorre_na_competencia(ob, competencia) or not obrigacao_aplicavel(emp, ob):
                continue
            if (emp.id, ob.id) in existentes:
                continue
            venc = calcular_vencimento(regra_efetiva(emp, ob), competencia, ob.periodicidade)
            sessao.add(Tarefa(empresa_id=emp.id, obrigacao_id=ob.id, competencia=competencia, vencimento=venc))
            existentes.add((emp.id, ob.id))
            criadas += 1
    if criadas:
        sessao.add(Evento(tipo="agenda_gerada", usuario=usuario,
                          mensagem=f"Agenda {competencia}: {criadas} tarefa(s) criada(s)"))
    sessao.flush()
    return {"competencia": competencia, "empresas": len(empresas), "tarefas_criadas": criadas}


def recalcular_vencimentos(sessao: Session, empresa: Empresa) -> int:
    """Recalcula prazos das tarefas pendentes após mudança de personalização."""
    n = 0
    for t in empresa.tarefas:
        if t.concluida:
            continue
        novo = calcular_vencimento(regra_efetiva(empresa, t.obrigacao), t.competencia, t.obrigacao.periodicidade)
        if novo != t.vencimento:
            t.vencimento = novo
            n += 1
    return n
