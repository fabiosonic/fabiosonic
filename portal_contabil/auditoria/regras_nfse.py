"""Regras de NFS-e: retenções federais, ISS e valor líquido."""
from __future__ import annotations

from decimal import Decimal

from ..modelos import Achado, DocumentoFiscal
from ..util import ZERO, limpar_doc, moeda, pct
from .contexto import Contexto

TOL = Decimal("0.05")
CSRF = Decimal("0.0465")
ALIQ_IRRF = (Decimal("0.01"), Decimal("0.015"))
ALIQ_INSS = (Decimal("0.11"), Decimal("0.035"))
MINIMO_CSRF = Decimal("215.05")  # 4,65% x 215,05 = R$ 10,00 (DARF mínimo, Lei 13.137/2015)


def _nfses(docs) -> list[DocumentoFiscal]:
    return [d for d in docs if d.tipo == "NFSE" and d.autorizada]


def _prestador_simples(d: DocumentoFiscal, ctx: Contexto) -> bool:
    if d.emitente.optante_simples is not None:
        return d.emitente.optante_simples
    return limpar_doc(d.emitente.documento) == ctx.empresa.cnpj and ctx.simples


def _base(d: DocumentoFiscal) -> Decimal:
    return d.valor_servico - d.desconto_incondicionado or d.valor_total


def regra_retencao_simples(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfses(ctx.emitidas + ctx.recebidas):
        if not _prestador_simples(d, ctx):
            continue
        indevidas = {k: v for k, v in d.retencoes.items() if k in {"irrf", "pis", "cofins", "csll"}}
        if not indevidas:
            continue
        total = sum(indevidas.values(), ZERO)
        emitida = ctx.eh_emitida(d)
        out.append(Achado(
            "NFS001", "ALTO" if emitida else "MEDIO", "Retenções",
            f"{d.rotulo}: retenção federal sobre prestador do Simples Nacional",
            f"Foram retidos {moeda(total)} ({', '.join(k.upper() for k in indevidas)}) de um prestador optante do Simples, "
            "que é dispensado dessas retenções.",
            ("Oriente o tomador a não reter, apresentando a declaração de optante. O valor retido pode ser "
             "compensado ou restituído via PER/DCOMP." if emitida else
             "A empresa reteve indevidamente. Devolva o valor ao prestador ou ajuste a DCTFWeb/EFD-Reinf."),
            "LC 123/2006, art. 13, §3º; IN RFB 765/2007 (IRRF); IN SRF 459/2004, art. 3º (CSRF)",
            d.chave, total))
    return out


def regra_aliquotas_retencao(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfses(ctx.emitidas + ctx.recebidas):
        base = _base(d)
        if base <= 0:
            continue
        r = d.retencoes
        problemas = []
        if r.get("irrf") and not any(abs(r["irrf"] - base * a) <= TOL for a in ALIQ_IRRF):
            problemas.append(f"IRRF de {pct(r['irrf'] / base)} (usual: 1% ou 1,5%)")
        csrf = r.get("pis", ZERO) + r.get("cofins", ZERO) + r.get("csll", ZERO)
        if all(k in r for k in ("pis", "cofins", "csll")) and abs(csrf - base * CSRF) > TOL:
            problemas.append(f"CSRF de {pct(csrf / base)} (esperado: 4,65%)")
        if r.get("inss") and not any(abs(r["inss"] - base * a) <= TOL for a in ALIQ_INSS):
            problemas.append(f"INSS de {pct(r['inss'] / base)} (usual: 11% ou 3,5% para empresas na CPRB)")
        if problemas:
            out.append(Achado(
                "NFS002", "MEDIO", "Retenções", f"{d.rotulo}: alíquota de retenção fora do padrão",
                "; ".join(problemas) + f" sobre a base de {moeda(base)}.",
                "Confira a natureza do serviço e se a base considera deduções legais (materiais, por exemplo). "
                "Retenção a maior é recuperável e retenção a menor gera responsabilidade do tomador.",
                "RIR/2018, arts. 714 e 716; Lei 10.833/2003, art. 31; Lei 8.212/1991, art. 31",
                d.chave))
    return out


def regra_iss(ctx: Contexto) -> list[Achado]:
    out = []
    retido_simples = ZERO
    for d in _nfses(ctx.lote.documentos):
        if d.aliquota_iss and not (Decimal("2") <= d.aliquota_iss <= Decimal("5")):
            out.append(Achado(
                "NFS003", "MEDIO", "ISS", f"{d.rotulo}: alíquota de ISS de {d.aliquota_iss}%",
                "A alíquota de ISS deve ficar entre 2% e 5%, salvo as exceções expressas da LC 116.",
                "Verifique o código de serviço e a legislação municipal. Alíquota abaixo de 2% sujeita o tomador "
                "à cobrança no município do estabelecimento.",
                "LC 116/2003, arts. 8º, II e 8º-A", d.chave))
        if ctx.eh_emitida(d) and d.iss_retido and ctx.simples:
            retido_simples += d.valor_iss or (_base(d) * (d.aliquota_iss or ZERO) / 100)
    if retido_simples:
        out.append(Achado(
            "SN012", "MEDIO", "Recuperação tributária", "ISS retido pelo tomador: evitar pagar em duplicidade no DAS",
            f"{moeda(retido_simples)} de ISS foram retidos pelos tomadores nas notas emitidas.",
            "No PGDAS-D, informe essas receitas como 'com retenção de ISS'. Assim o ISS sai do DAS. Se foram declaradas "
            "sem retenção, retifique o PGDAS-D e peça a restituição.",
            "LC 123/2006, art. 21, §4º", valor=retido_simples))
    return out


def regra_valor_liquido(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfses(ctx.lote.documentos):
        if not d.valor_liquido:
            continue
        esperado = (d.valor_servico - d.desconto_incondicionado - d.total_retencoes_federais
                    - (d.valor_iss if d.iss_retido else ZERO))
        if abs(esperado - d.valor_liquido) > TOL:
            out.append(Achado(
                "NFS004", "BAIXO", "Cálculo da nota", f"{d.rotulo}: valor líquido inconsistente",
                f"Recalculado: {moeda(esperado)}; informado: {moeda(d.valor_liquido)}. "
                "Pode haver desconto condicionado ou outras retenções não detalhadas.",
                "Confira com o financeiro o valor efetivamente recebido ou pago.", "", d.chave,
                d.valor_liquido - esperado))
    return out


def regra_tomador_sem_retencao(ctx: Contexto) -> list[Achado]:
    docs = [d for d in _nfses(ctx.recebidas)
            if d.emitente.optante_simples is False and len(limpar_doc(d.emitente.documento)) == 14
            and not d.retencoes and _base(d) > MINIMO_CSRF]
    if not docs:
        return []
    return [Achado(
        "NFS005", "INFO", "Retenções", f"{len(docs)} serviço(s) tomado(s) sem nenhuma retenção federal",
        "Prestadores fora do Simples, com valor acima de R$ 215,05, sem IRRF/CSRF/INSS retidos: "
        + ", ".join(f"{d.rotulo} ({d.emitente.nome or d.emitente.documento})" for d in docs[:5])
        + (" …" if len(docs) > 5 else "") + ".",
        "Verifique se o serviço consta na lista sujeita a retenção (serviços profissionais, limpeza, "
        "vigilância, cessão de mão de obra etc.). Se constar, a empresa tomadora responde pelo tributo não retido.",
        "RIR/2018, art. 714; Lei 10.833/2003, art. 30; Lei 8.212/1991, art. 31",
        valor=sum((_base(d) for d in docs), ZERO))]


REGRAS = [regra_retencao_simples, regra_aliquotas_retencao, regra_iss, regra_valor_liquido,
          regra_tomador_sem_retencao]
