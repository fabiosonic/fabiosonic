"""Contexto da auditoria: empresa auditada, papel de cada documento e receita bruta."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from ..modelos import DocumentoFiscal, Empresa, Lote
from ..util import ZERO, limpar_doc, mes
from . import tabelas as T

CRT_PARA_REGIME = {"1": "simples", "2": "simples", "3": "normal", "4": "mei"}


def inferir_empresa(lote: Lote, cnpj: str | None = None, regime: str | None = None) -> Empresa:
    if cnpj:
        alvo = limpar_doc(cnpj)
    else:
        cont = Counter()
        for d in lote.documentos:
            for doc in (d.emitente.documento, d.destinatario.documento):
                doc = limpar_doc(doc)
                if len(doc) == 14:
                    cont[doc] += 1
        alvo = cont.most_common(1)[0][0] if cont else ""

    nome, uf, crts = "", "", Counter()
    for d in lote.documentos:
        if limpar_doc(d.emitente.documento) == alvo:
            nome = nome or d.emitente.nome
            uf = uf or d.emitente.uf
            if d.emitente.crt:
                crts[d.emitente.crt] += 1
        elif limpar_doc(d.destinatario.documento) == alvo:
            nome = nome or d.destinatario.nome
            uf = uf or d.destinatario.uf

    inferido = False
    if not regime or regime == "auto":
        inferido = True
        regime = CRT_PARA_REGIME.get(crts.most_common(1)[0][0], "desconhecido") if crts else "desconhecido"
    return Empresa(cnpj=alvo, regime=regime, nome=nome, uf=uf, regime_inferido=inferido)


@dataclass
class Contexto:
    lote: Lote
    empresa: Empresa
    emitidas: list[DocumentoFiscal] = field(default_factory=list)
    recebidas: list[DocumentoFiscal] = field(default_factory=list)
    terceiros: list[DocumentoFiscal] = field(default_factory=list)
    receita_mensal: dict[str, Decimal] = field(default_factory=dict)
    receita_por_doc: dict[str, Decimal] = field(default_factory=dict)

    @property
    def simples(self) -> bool:
        return self.empresa.regime in {"simples", "mei"}

    def eh_emitida(self, doc: DocumentoFiscal) -> bool:
        return limpar_doc(doc.emitente.documento) == self.empresa.cnpj

    def papel(self, doc: DocumentoFiscal) -> str:
        if self.eh_emitida(doc):
            return "Emitida"
        if limpar_doc(doc.destinatario.documento) == self.empresa.cnpj:
            return "Recebida"
        return "Terceiros"

    @property
    def autorizadas_emitidas(self) -> list[DocumentoFiscal]:
        return [d for d in self.emitidas if d.autorizada]


def receita_documento(doc: DocumentoFiscal, cnpj: str) -> Decimal:
    """Receita bruta (positiva) ou dedução por devolução (negativa) do documento."""
    if not doc.autorizada:
        return ZERO
    emitida = limpar_doc(doc.emitente.documento) == cnpj
    recebida = limpar_doc(doc.destinatario.documento) == cnpj
    if doc.tipo == "NFSE":
        return doc.valor_servico - doc.desconto_incondicionado if emitida else ZERO
    total = ZERO
    for it in doc.itens:
        cfop = it.cfop
        if emitida and doc.tipo_operacao == "saida" and cfop[:1] in "567" and cfop[1:] in T.SUFIXOS_CFOP_RECEITA:
            total += it.valor_liquido
        elif emitida and doc.tipo_operacao == "entrada" and cfop in T.CFOP_DEVOLUCAO_VENDA_ENTRADA:
            total -= it.valor_liquido
        elif recebida and not emitida and cfop in T.CFOP_DEVOLUCAO_VENDA_SAIDA_CLIENTE:
            total -= it.valor_liquido
    return total


def montar_contexto(lote: Lote, empresa: Empresa) -> Contexto:
    ctx = Contexto(lote=lote, empresa=empresa)
    receita = defaultdict(lambda: ZERO)
    for d in lote.documentos:
        if limpar_doc(d.emitente.documento) == empresa.cnpj:
            ctx.emitidas.append(d)
        elif limpar_doc(d.destinatario.documento) == empresa.cnpj:
            ctx.recebidas.append(d)
        else:
            ctx.terceiros.append(d)
        valor = receita_documento(d, empresa.cnpj)
        if valor and d.data_emissao:
            receita[mes(d.data_emissao)] += valor
            ctx.receita_por_doc[d.chave] = valor
    ctx.receita_mensal = dict(sorted(receita.items()))
    return ctx
