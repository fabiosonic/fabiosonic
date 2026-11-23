"""Conciliação extrato bancário (OFX) x documentos fiscais emitidos.

Depósitos sem origem comprovada caracterizam omissão de receita
(Lei 9.430/1996, art. 42). É o cruzamento de maior risco fiscal do portal.
"""
from __future__ import annotations

import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from ..modelos import Achado, DocumentoFiscal, LancamentoBancario
from ..util import ZERO, mes, moeda, pct
from . import tabelas as T
from .contexto import Contexto

JANELA_ANTES = timedelta(days=5)
JANELA_DEPOIS = timedelta(days=120)
TOL_EXATA = Decimal("0.01")
TOL_TARIFA = Decimal("0.05")  # até 5% de diferença: tarifa de boleto/cartão, juros
PRAZO_RECEBIMENTO = timedelta(days=30)  # notas mais recentes que isso ainda estão "a vencer"


@dataclass
class Par:
    documento: DocumentoFiscal
    lancamento: LancamentoBancario
    diferenca: Decimal


@dataclass
class ResultadoConciliacao:
    conciliados: list[Par] = field(default_factory=list)
    creditos_sem_nota: list[LancamentoBancario] = field(default_factory=list)
    creditos_nao_operacionais: list[LancamentoBancario] = field(default_factory=list)
    creditos_adquirente: list[LancamentoBancario] = field(default_factory=list)
    notas_sem_recebimento: list[DocumentoFiscal] = field(default_factory=list)
    notas_no_prazo: list[DocumentoFiscal] = field(default_factory=list)
    executada: bool = False
    inicio: date | None = None
    fim: date | None = None


def _norm(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper() + " "


def valor_esperado(d: DocumentoFiscal) -> Decimal:
    if d.tipo == "NFSE":
        return d.valor_liquido or (d.valor_servico - d.desconto_incondicionado - d.total_retencoes_federais
                                   - (d.valor_iss if d.iss_retido else ZERO))
    return d.valor_total


def conciliar(ctx: Contexto) -> ResultadoConciliacao:
    res = ResultadoConciliacao()
    # débitos também delimitam o período do extrato
    datas = [l.data for l in ctx.lote.lancamentos if l.data]
    if not datas:
        return res
    lancs = [l for l in ctx.lote.lancamentos if l.valor > 0 and l.data]
    res.executada = True
    ini, fim = min(datas), max(datas)
    res.inicio, res.fim = ini, fim

    candidatos = []
    for l in lancs:
        memo = _norm(l.memo)
        if any(p in memo for p in T.PALAVRAS_NAO_OPERACIONAL):
            res.creditos_nao_operacionais.append(l)
        elif any(p in memo for p in T.PALAVRAS_ADQUIRENTE):
            res.creditos_adquirente.append(l)
        else:
            candidatos.append(l)

    docs = [d for d in ctx.autorizadas_emitidas
            if d.tipo in {"NFE", "NFSE"} and d.data_emissao and ctx.receita_por_doc.get(d.chave, ZERO) > 0
            and ini - JANELA_DEPOIS <= d.data_emissao <= fim]
    docs.sort(key=lambda d: d.data_emissao)
    livres = set(range(len(candidatos)))

    def melhor(doc, tolerancia_relativa):
        esperado = valor_esperado(doc)
        tol = max(TOL_EXATA, esperado * tolerancia_relativa)
        escolha, menor = None, None
        for idx in livres:
            l = candidatos[idx]
            if not (doc.data_emissao - JANELA_ANTES <= l.data <= doc.data_emissao + JANELA_DEPOIS):
                continue
            dif = l.valor - esperado
            if abs(dif) <= tol and (dif <= 0 or tolerancia_relativa == 0):
                chave = (abs(dif), abs((l.data - doc.data_emissao).days))
                if menor is None or chave < menor:
                    escolha, menor = idx, chave
        return escolha

    pendentes = []
    for tolerancia in (Decimal("0"), TOL_TARIFA):
        pendentes = []
        for d in docs:
            idx = melhor(d, tolerancia)
            if idx is None:
                pendentes.append(d)
                continue
            livres.discard(idx)
            res.conciliados.append(Par(d, candidatos[idx], candidatos[idx].valor - valor_esperado(d)))
        docs = pendentes

    # Notas anteriores ao início do extrato podem ter sido pagas antes dele: não acusar.
    pendentes = [d for d in pendentes if d.data_emissao >= ini]
    res.notas_sem_recebimento = [d for d in pendentes if d.data_emissao <= fim - PRAZO_RECEBIMENTO]
    res.notas_no_prazo = [d for d in pendentes if d.data_emissao > fim - PRAZO_RECEBIMENTO]
    res.creditos_sem_nota = [candidatos[i] for i in sorted(livres)]
    return res


def regra_conciliacao(ctx: Contexto, res: ResultadoConciliacao) -> list[Achado]:
    if not res.executada:
        return []
    out = []
    if res.creditos_sem_nota:
        total = sum((l.valor for l in res.creditos_sem_nota), ZERO)
        por_mes = defaultdict(lambda: ZERO)
        for l in res.creditos_sem_nota:
            por_mes[mes(l.data)] += l.valor
        # compara com o faturamento das competências cobertas pelo extrato
        faturamento = sum((v for m, v in ctx.receita_mensal.items()
                           if mes(res.inicio) <= m <= mes(res.fim) and v > 0), ZERO)
        critico = faturamento == 0 or total > faturamento * Decimal("0.05")
        out.append(Achado(
            "CON001", "CRITICO" if critico else "ALTO", "Conciliação bancária",
            f"{len(res.creditos_sem_nota)} crédito(s) bancário(s) sem documento fiscal",
            f"{moeda(total)} em créditos operacionais não foram vinculados a nenhuma nota emitida"
            + (f" ({pct(total / faturamento)} do faturamento do período do extrato)" if faturamento else "")
            + ". Por mês: "
            + "; ".join(f"{m}: {moeda(v)}" for m, v in sorted(por_mes.items())) + ".",
            "Identifique a origem de cada crédito (venda sem nota, adiantamento de cliente, empréstimo de sócio). "
            "Emita as notas faltantes ou documente a origem. Depósito sem origem comprovada é presumido como receita omitida.",
            "Lei 9.430/1996, art. 42; LC 123/2006, art. 34", "", total))
    if res.creditos_nao_operacionais:
        total = sum((l.valor for l in res.creditos_nao_operacionais), ZERO)
        out.append(Achado(
            "CON002", "INFO", "Conciliação bancária",
            f"{len(res.creditos_nao_operacionais)} crédito(s) classificado(s) como não operacionais",
            f"{moeda(total)} em resgates, empréstimos, aportes, estornos e transferências entre contas.",
            "Guarde o lastro de cada um (contrato de mútuo, alteração contratual de aporte, extrato da aplicação). "
            "Sem lastro, a fiscalização pode tratá-los como receita.",
            "Lei 9.430/1996, art. 42", "", total))
    if res.creditos_adquirente:
        total = sum((l.valor for l in res.creditos_adquirente), ZERO)
        nfce = sum((d.valor_total for d in ctx.autorizadas_emitidas if d.tipo == "NFCE"), ZERO)
        out.append(Achado(
            "CON003", "MEDIO" if nfce < total * Decimal("0.9") else "INFO", "Conciliação bancária",
            "Liquidações de cartão e PIX de adquirentes",
            f"{moeda(total)} recebidos de adquirentes, contra {moeda(nfce)} em NFC-e emitidas no lote. As adquirentes "
            "informam as vendas ao fisco (DIMP/DECRED), o que gera malha automática.",
            "Concilie o relatório de vendas da adquirente com as NFC-e/NF-e. A diferença relevante indica venda sem documento fiscal.",
            "Convênio ICMS 134/2016 (DIMP)", "", total))
    if res.notas_sem_recebimento:
        total = sum((valor_esperado(d) for d in res.notas_sem_recebimento), ZERO)
        out.append(Achado(
            "CON004", "MEDIO", "Conciliação bancária",
            f"{len(res.notas_sem_recebimento)} nota(s) emitida(s) sem recebimento identificado",
            f"{moeda(total)} em notas sem crédito correspondente no extrato: "
            + ", ".join(d.rotulo for d in res.notas_sem_recebimento[:8])
            + (" …" if len(res.notas_sem_recebimento) > 8 else "") + ".",
            "Confirme se estão em aberto (inadimplência), se foram recebidas em outra conta ou em dinheiro. "
            "Atualize o contas a receber. A perda só é dedutível dentro dos limites da Lei 9.430/1996.",
            "Lei 9.430/1996, arts. 9º a 14", "", total))
    if res.notas_no_prazo:
        total = sum((valor_esperado(d) for d in res.notas_no_prazo), ZERO)
        out.append(Achado(
            "CON006", "INFO", "Conciliação bancária",
            f"{len(res.notas_no_prazo)} nota(s) recente(s) ainda dentro do prazo de recebimento",
            f"{moeda(total)} em notas emitidas nos últimos 30 dias do extrato, ainda sem crédito.",
            "Reavalie na próxima conciliação, com o extrato do mês seguinte.", "", "", total))
    if res.conciliados:
        diferencas = [p for p in res.conciliados if p.diferenca]
        if diferencas:
            total = sum((p.diferenca for p in diferencas), ZERO)
            out.append(Achado(
                "CON005", "INFO", "Conciliação bancária",
                f"{len(diferencas)} recebimento(s) conciliado(s) com diferença de valor",
                f"Diferença líquida de {moeda(total)}, compatível com tarifas bancárias, de boleto ou de cartão.",
                "Contabilize as tarifas como despesa financeira, com suporte nos extratos e nos relatórios da adquirente.",
                "NBC TG 1000, seção 2 (competência)", "", total))
    return out
