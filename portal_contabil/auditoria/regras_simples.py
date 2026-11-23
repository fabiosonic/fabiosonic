"""Regras do Simples Nacional e do MEI: limites de receita, RBT12 e Fator R."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from ..modelos import Achado
from ..util import ZERO, moeda, pct, somar_meses
from . import tabelas as T
from .contexto import Contexto


@dataclass
class LinhaApuracao:
    competencia: str
    receita: Decimal
    rbt12: Decimal
    meses_base: int  # quantos dos 12 meses anteriores têm dados
    folha12: Decimal | None = None
    fator_r: Decimal | None = None

    @property
    def parcial(self) -> bool:
        return self.meses_base < 12


def apuracao_mensal(ctx: Contexto) -> list[LinhaApuracao]:
    rec = ctx.receita_mensal
    folha = {f.competencia: f.total for f in ctx.lote.folha}
    meses = sorted(set(rec) | set(folha))
    if not meses:
        return []
    inicio = min(meses)
    linhas = []
    competencia = inicio
    while competencia <= max(meses):
        anteriores = [somar_meses(competencia, -k) for k in range(1, 13)]
        rbt12 = sum((rec.get(m, ZERO) for m in anteriores), ZERO)
        base = sum(1 for m in anteriores if m >= inicio)
        linha = LinhaApuracao(competencia, rec.get(competencia, ZERO), rbt12, base)
        if folha:
            f12 = sum((folha.get(m, ZERO) for m in anteriores), ZERO)
            linha.folha12 = f12
            if rbt12 > 0:
                linha.fator_r = f12 / rbt12
        linhas.append(linha)
        competencia = somar_meses(competencia, 1)
    return linhas


def regra_limites(ctx: Contexto) -> list[Achado]:
    if not ctx.simples:
        return []
    por_ano = defaultdict(lambda: ZERO)
    for comp, valor in ctx.receita_mensal.items():
        por_ano[comp[:4]] += valor
    out = []
    mei = ctx.empresa.regime == "mei"
    for ano, total in sorted(por_ano.items()):
        if mei:
            if total > T.LIMITE_MEI * T.TOLERANCIA_EXCESSO:
                out.append(Achado(
                    "SN001", "CRITICO", "Limites de receita", f"MEI: receita de {ano} supera o limite em mais de 20%",
                    f"Receita bruta de {moeda(total)}, acima de {moeda(T.LIMITE_MEI * T.TOLERANCIA_EXCESSO)}.",
                    "Desenquadramento retroativo a 1º de janeiro (ou ao início das atividades): recolher como ME pelo "
                    "Simples, com acréscimos legais. Comunique o desenquadramento no Portal do Simples.",
                    "LC 123/2006, art. 18-A, §7º, III, 'b'", ano, total))
            elif total > T.LIMITE_MEI:
                out.append(Achado(
                    "SN001", "ALTO", "Limites de receita", f"MEI: receita de {ano} acima de R$ 81.000",
                    f"Receita bruta de {moeda(total)}. O excesso de até 20% é tributado em DAS complementar.",
                    "Recolha o DAS sobre o excesso e comunique o desenquadramento, com efeitos a partir de 1º de janeiro do ano seguinte.",
                    "LC 123/2006, art. 18-A, §7º, III, 'a'", ano, total - T.LIMITE_MEI))
            continue

        if total > T.LIMITE_SIMPLES * T.TOLERANCIA_EXCESSO:
            out.append(Achado(
                "SN002", "CRITICO", "Limites de receita", f"Receita de {ano} excede o limite do Simples em mais de 20%",
                f"Receita bruta de {moeda(total)}, acima de {moeda(T.LIMITE_SIMPLES * T.TOLERANCIA_EXCESSO)}.",
                "Exclusão obrigatória com efeitos retroativos ao mês seguinte ao excesso. Planeje imediatamente a "
                "migração para o Lucro Presumido ou Real e apure as diferenças.",
                "LC 123/2006, art. 3º, §§ 9º e 9º-A; art. 30, IV e §1º, IV", ano, total))
        elif total > T.LIMITE_SIMPLES:
            out.append(Achado(
                "SN002", "CRITICO", "Limites de receita", f"Receita de {ano} acima de R$ 4,8 milhões",
                f"Receita bruta de {moeda(total)}. Como o excesso é de até 20%, a exclusão vale a partir de 1º de janeiro do ano seguinte.",
                "Comunique a exclusão e prepare a mudança de regime para o próximo exercício.",
                "LC 123/2006, art. 3º, §9º-A; art. 30, IV", ano, total))
        elif total > T.SUBLIMITE_SIMPLES * T.TOLERANCIA_EXCESSO:
            out.append(Achado(
                "SN003", "ALTO", "Limites de receita", f"Receita de {ano} excede o sublimite estadual/municipal em mais de 20%",
                f"Receita bruta de {moeda(total)}. O ICMS e o ISS saem do DAS a partir do mês seguinte ao excesso.",
                "Passe a apurar ICMS e ISS pelas regras normais do estado e do município (inscrição, EFD ICMS/IPI, guias próprias).",
                "LC 123/2006, art. 20, §§ 1º e 1º-A", ano, total))
        elif total > T.SUBLIMITE_SIMPLES:
            out.append(Achado(
                "SN003", "ALTO", "Limites de receita", f"Receita de {ano} acima do sublimite de R$ 3,6 milhões",
                f"Receita bruta de {moeda(total)}. ICMS e ISS deixam o DAS a partir de 1º de janeiro do ano seguinte.",
                "Prepare a apuração própria de ICMS e ISS para o próximo exercício.",
                "LC 123/2006, art. 20, §1º", ano, total))
        elif total > T.SUBLIMITE_SIMPLES * Decimal("0.8"):
            out.append(Achado(
                "SN004", "MEDIO", "Limites de receita", f"Receita de {ano} acima de 80% do sublimite",
                f"Receita bruta de {moeda(total)} ({pct(total / T.SUBLIMITE_SIMPLES)} de R$ 3,6 milhões).",
                "Monitore o faturamento mês a mês e simule o Lucro Presumido para o próximo ano.",
                "LC 123/2006, art. 20", ano, total))
    return out


def regra_fator_r(ctx: Contexto) -> list[Achado]:
    if ctx.empresa.regime != "simples" or not ctx.lote.folha:
        return []
    linhas = [l for l in apuracao_mensal(ctx) if l.fator_r is not None]
    if not linhas:
        return []
    abaixo = [l for l in linhas if l.fator_r < T.FATOR_R_MINIMO]
    ultima = linhas[-1]
    if not abaixo:
        return [Achado(
            "SN005", "INFO", "Fator R", "Fator R acima de 28% em todas as competências",
            f"Última competência ({ultima.competencia}): Fator R de {pct(ultima.fator_r)}.",
            "Mantenha a folha (incluindo o pró-labore) no patamar atual para preservar o Anexo III.",
            "LC 123/2006, art. 18, §§ 5º-J, 5º-M e 24")]
    ref = abaixo[-1]
    deficit = T.FATOR_R_MINIMO * ref.rbt12 - (ref.folha12 or ZERO)
    return [Achado(
        "SN005", "MEDIO", "Fator R",
        f"Fator R abaixo de 28% em {len(abaixo)} competência(s)",
        f"Em {ref.competencia}, o Fator R foi de {pct(ref.fator_r)} (folha de 12 meses de {moeda(ref.folha12)} "
        f"sobre RBT12 de {moeda(ref.rbt12)}). As atividades sujeitas ao Fator R são tributadas pelo Anexo V, com alíquota "
        f"inicial de 15,5% contra 6% no Anexo III." + (" Base de 12 meses incompleta." if ref.parcial else ""),
        f"Para atingir 28%, a folha dos últimos 12 meses precisaria de mais {moeda(deficit)}. Avalie aumentar o pró-labore "
        "(considerando o INSS de 11% e o IRPF do sócio) e compare o custo com a economia no DAS.",
        "LC 123/2006, art. 18, §§ 5º-J, 5º-M e 24", ref.competencia, deficit)]


def regra_base_incompleta(ctx: Contexto) -> list[Achado]:
    if not ctx.simples or not ctx.receita_mensal:
        return []
    meses = len(ctx.receita_mensal)
    if meses >= 13:
        return []
    return [Achado(
        "SN006", "INFO", "Limites de receita", "Histórico inferior a 13 meses",
        f"O lote tem receita em {meses} competência(s). O RBT12 exige os 12 meses anteriores a cada apuração.",
        "Envie as notas dos 12 meses anteriores para validar as alíquotas efetivas do PGDAS-D.",
        "LC 123/2006, art. 18, §1º")]


REGRAS = [regra_limites, regra_fator_r, regra_base_incompleta]
