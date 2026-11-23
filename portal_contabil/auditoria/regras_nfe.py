"""Regras de NF-e/NFC-e: totais, CFOP, CRT x CST/CSOSN, NCM e Reforma Tributária."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..modelos import Achado
from ..util import ZERO, moeda
from . import tabelas as T
from .contexto import Contexto

TOL = Decimal("0.05")
INICIO_IBS_CBS = date(2026, 1, 1)


def _nfes(docs):
    return [d for d in docs if d.layout == "nfe" and d.autorizada]


def regra_totais(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfes(ctx.lote.documentos):
        t = d.totais
        if not t or not d.itens:
            continue
        soma_itens = sum((i.valor_produto for i in d.itens), ZERO)
        if abs(soma_itens - t.get("vProd", ZERO)) > TOL:
            out.append(Achado(
                "NFE001", "ALTO", "Cálculo da nota", f"{d.rotulo}: soma dos itens difere do total",
                f"A soma dos itens é {moeda(soma_itens)} e o total de produtos (vProd) é {moeda(t.get('vProd'))}.",
                "Conferir o XML. Totais divergentes indicam adulteração ou erro do emissor.",
                "MOC NF-e - regra de validação W16", d.chave, soma_itens - t.get("vProd", ZERO)))
        g = t.get
        esperado = (g("vProd", ZERO) - g("vDesc", ZERO) - g("vICMSDeson", ZERO) + g("vST", ZERO)
                    + g("vFCPST", ZERO) + g("vFrete", ZERO) + g("vSeg", ZERO) + g("vOutro", ZERO)
                    + g("vII", ZERO) + g("vIPI", ZERO) + g("vIPIDevol", ZERO))
        if abs(esperado - g("vNF", ZERO)) > TOL:
            out.append(Achado(
                "NFE002", "MEDIO", "Cálculo da nota", f"{d.rotulo}: valor total (vNF) inconsistente",
                f"Recalculado: {moeda(esperado)}; informado: {moeda(g('vNF'))}.",
                "Verifique descontos, frete, IPI e ST. A diferença afeta o valor a receber ou a pagar e a base dos tributos.",
                "MOC NF-e - regra de validação W16 (vNF)", d.chave, g("vNF", ZERO) - esperado))
    return out


def regra_cfop(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfes(ctx.lote.documentos):
        validos = "567" if d.tipo_operacao == "saida" else "123"
        errados = sorted({i.cfop for i in d.itens if i.cfop and i.cfop[0] not in validos})
        if errados:
            out.append(Achado(
                "NFE003", "ALTO", "CFOP", f"{d.rotulo}: CFOP incompatível com o tipo de operação",
                f"A nota é de {'saída' if d.tipo_operacao == 'saida' else 'entrada'}, mas usa CFOP {', '.join(errados)}.",
                "Uma nota de saída usa CFOP 5/6/7 e uma de entrada usa CFOP 1/2/3. Emita uma NF-e de ajuste ou corrija a escrituração.",
                "Convênio s/nº de 1970 (Tabela CFOP), Ajuste SINIEF 07/2001", d.chave))
    for d in _nfes(ctx.emitidas):
        if d.tipo != "NFE" or not d.emitente.uf or not d.destinatario.uf or d.destinatario.uf == "EX":
            continue
        mesma_uf = d.emitente.uf == d.destinatario.uf
        errados = sorted({i.cfop for i in d.itens
                          if (mesma_uf and i.cfop[:1] in "26") or (not mesma_uf and i.cfop[:1] in "15")})
        if errados:
            out.append(Achado(
                "NFE004", "MEDIO", "CFOP", f"{d.rotulo}: CFOP não corresponde à UF de destino",
                f"Emitente em {d.emitente.uf}, destinatário em {d.destinatario.uf}, CFOP {', '.join(errados)}.",
                "Operação interna usa CFOP 5xxx/1xxx e interestadual usa 6xxx/2xxx. O erro afeta a alíquota de ICMS e o DIFAL.",
                "Tabela CFOP; CF/88, art. 155, §2º, VII", d.chave))
    return out


def regra_crt(ctx: Contexto) -> list[Achado]:
    out = []
    for d in _nfes(ctx.emitidas):
        crt = d.emitente.crt
        if crt in {"1", "4"} and any(i.cst_icms and not i.csosn for i in d.itens):
            out.append(Achado(
                "NFE005", "MEDIO", "Enquadramento", f"{d.rotulo}: optante do Simples usando CST de regime normal",
                "Com CRT 1/4, o ICMS deve ser informado por CSOSN (Tabela B do Ajuste SINIEF 07/2005).",
                "Ajuste o cadastro tributário no emissor. A inconsistência gera rejeição e malha fiscal.",
                "Ajuste SINIEF 07/2005, Anexo - CSOSN; LC 123/2006", d.chave))
        elif crt == "3" and any(i.csosn for i in d.itens):
            out.append(Achado(
                "NFE005", "ALTO", "Enquadramento", f"{d.rotulo}: regime normal usando CSOSN do Simples",
                "Com CRT 3, o ICMS deve ser informado por CST. O uso de CSOSN sugere que o enquadramento no emissor está errado.",
                "Confirme o regime vigente (consulta optantes) e corrija o emissor. Pode haver ICMS não destacado.",
                "Ajuste SINIEF 07/2005", d.chave))
    return out


def regra_ncm(ctx: Contexto) -> list[Achado]:
    docs = [d for d in _nfes(ctx.emitidas)
            if any(len(i.ncm) != 8 and i.ncm != "00" for i in d.itens)]
    if not docs:
        return []
    return [Achado(
        "NFE006", "BAIXO", "Cadastro de produtos", f"{len(docs)} nota(s) com NCM ausente ou inválido",
        "Exemplos: " + ", ".join(d.rotulo for d in docs[:5]) + ".",
        "Revise o cadastro de produtos. O NCM determina o IPI, a ST, a monofasia de PIS/COFINS e as alíquotas de IBS/CBS.",
        "Decreto 11.158/2022 (TIPI)")]


def regra_reforma(ctx: Contexto) -> list[Achado]:
    docs = [d for d in _nfes(ctx.emitidas)
            if d.emitente.crt in {"2", "3"} and d.data_emissao and d.data_emissao >= INICIO_IBS_CBS
            and not d.tem_ibscbs]
    if not docs:
        return []
    return [Achado(
        "NFE007", "MEDIO", "Reforma Tributária",
        f"{len(docs)} NF-e de 2026 sem o grupo IBS/CBS",
        "Em 2026 (ano-teste), os contribuintes do regime regular devem destacar a CBS (0,9%) e o IBS (0,1%) "
        "nos documentos fiscais. Notas emitidas sem o grupo IBSCBS: "
        + ", ".join(d.rotulo for d in docs[:5]) + (" …" if len(docs) > 5 else "") + ".",
        "Atualize o emissor para a NT 2025.002 e confirme no portal da SEFAZ o cronograma de validação. "
        "O valor do ano-teste é compensável com PIS/COFINS, mas a ausência do destaque é uma não conformidade.",
        "LC 214/2025, arts. 343 a 348; NT 2025.002",
        valor=sum((d.valor_total for d in docs), ZERO))]


def _ncm_monofasico(ncm: str) -> str | None:
    for prefixo, desc in T.NCM_MONOFASICO.items():
        if ncm.startswith(prefixo):
            return desc
    return None


def regra_oportunidades_simples(ctx: Contexto) -> list[Achado]:
    if not ctx.simples or ctx.empresa.regime == "mei":
        return []
    mono, st = ZERO, ZERO
    grupos: dict[str, Decimal] = {}
    for d in _nfes(ctx.emitidas):
        if d.tipo_operacao != "saida":
            continue
        for i in d.itens:
            if i.cfop[1:] not in T.SUFIXOS_CFOP_RECEITA:
                continue
            desc = _ncm_monofasico(i.ncm)
            if desc:
                mono += i.valor_liquido
                grupos[desc] = grupos.get(desc, ZERO) + i.valor_liquido
            if i.csosn in T.CSOSN_ST_RETIDO_ANTERIORMENTE:
                st += i.valor_liquido
    out = []
    if mono:
        detalhe = "; ".join(f"{k}: {moeda(v)}" for k, v in sorted(grupos.items(), key=lambda x: -x[1]))
        out.append(Achado(
            "SN010", "MEDIO", "Recuperação tributária",
            "Receita de produtos monofásicos (PIS/COFINS) a segregar no PGDAS-D",
            f"Foram identificados {moeda(mono)} em vendas de produtos com PIS/COFINS concentrado. {detalhe}.",
            "Confirme se essa receita foi informada como 'tributação monofásica' no PGDAS-D. Se não foi, retifique "
            "as apurações e peça a restituição ou compensação do PIS/COFINS pago a maior (prazo de 5 anos). "
            "Valide o NCM completo de cada produto antes de retificar.",
            "LC 123/2006, art. 18, §4º-A, I; Leis 10.147/2000, 10.485/2002 e 13.097/2015; CTN, art. 168",
            valor=mono))
    if st:
        out.append(Achado(
            "SN011", "MEDIO", "Recuperação tributária",
            "Receita com ICMS já retido por substituição tributária (CSOSN 500)",
            f"{moeda(st)} em vendas com CSOSN 500. A parcela de ICMS dessas receitas não deve ser recolhida novamente no DAS.",
            "Confirme a segregação 'com substituição tributária' no PGDAS-D. Se não foi feita, retifique e "
            "peça a restituição do ICMS pago em duplicidade.",
            "LC 123/2006, art. 18, §4º-A, I e art. 13, §1º, XIII, 'a'",
            valor=st))
    return out


REGRAS = [regra_totais, regra_cfop, regra_crt, regra_ncm, regra_reforma, regra_oportunidades_simples]
