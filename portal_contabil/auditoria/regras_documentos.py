"""Regras de integridade documental (vale para todo tipo de documento)."""
from __future__ import annotations

from collections import defaultdict

from ..modelos import TIPO_ROTULO, Achado
from ..util import ZERO, chave_nfe_valida, documento_valido, fmt_doc, limpar_doc, moeda
from .contexto import Contexto


def _lista(itens, limite=15) -> str:
    itens = list(itens)
    extra = f" … e mais {len(itens) - limite}" if len(itens) > limite else ""
    return ", ".join(str(i) for i in itens[:limite]) + extra


def regra_situacao(ctx: Contexto) -> list[Achado]:
    out = []
    for d in ctx.lote.documentos:
        if d.situacao == "sem_protocolo":
            out.append(Achado(
                "DOC001", "ALTO", "Integridade documental",
                f"{d.rotulo} sem protocolo de autorização",
                f"O XML {d.arquivo} não traz o protocolo da SEFAZ (protNFe). Pode ser um "
                "arquivo de pré-visualização, uma nota rejeitada ou o XML errado.",
                "Baixe o XML autorizado (nfeProc) no portal da SEFAZ/emissor. Nota sem "
                "autorização não tem validade jurídica e não pode ser escriturada.",
                "Ajuste SINIEF 07/2005, cláusula 7ª", d.chave, d.valor_total))
        elif d.situacao == "denegada":
            out.append(Achado(
                "DOC002", "ALTO", "Integridade documental", f"{d.rotulo} com uso denegado",
                "A SEFAZ denegou o uso da nota por irregularidade cadastral do emitente ou do destinatário.",
                "Verifique a situação cadastral (Sintegra/CCC) antes de pagar ou escriturar a nota.",
                "Ajuste SINIEF 07/2005, cláusula 5ª", d.chave, d.valor_total))
    return out


def regra_chave_e_cadastro(ctx: Contexto) -> list[Achado]:
    out = []
    for d in ctx.lote.documentos:
        if d.layout == "nfe" and not chave_nfe_valida(d.chave):
            out.append(Achado(
                "DOC003", "ALTO", "Integridade documental",
                f"{d.rotulo}: chave de acesso inválida",
                f"A chave {d.chave or '(vazia)'} não confere no dígito verificador (módulo 11).",
                "Arquivo possivelmente adulterado ou corrompido. Consulte a chave no portal nacional da NF-e.",
                "MOC NF-e, item 5.4", d.chave))
        for papel, p in (("emitente", d.emitente), ("destinatário", d.destinatario)):
            doc = limpar_doc(p.documento)
            if len(doc) in (11, 14) and not documento_valido(doc):
                out.append(Achado(
                    "DOC004", "MEDIO", "Cadastro",
                    f"{d.rotulo}: CNPJ/CPF do {papel} inválido",
                    f"O documento {fmt_doc(doc)} ({p.nome or 'sem nome'}) não confere no dígito verificador.",
                    "Corrija o cadastro do participante. Documentos inválidos são rejeitados no SPED e na DCTFWeb.",
                    "IN RFB 2.119/2022 (CNPJ)", d.chave))
    return out


def regra_numeracao(ctx: Contexto) -> list[Achado]:
    out = []
    series = defaultdict(dict)
    for d in ctx.emitidas:
        if d.layout != "nfe" or not d.numero.isdigit():
            continue
        series[(d.tipo, d.serie)].setdefault(int(d.numero), []).append(d)

    for (tipo_bruto, serie), nums in series.items():
        tipo = TIPO_ROTULO.get(tipo_bruto, tipo_bruto)
        duplicados = {n: ds for n, ds in nums.items() if len({x.chave for x in ds}) > 1}
        for n, ds in duplicados.items():
            out.append(Achado(
                "DOC005", "ALTO", "Integridade documental",
                f"{tipo} nº {n} série {serie} emitida mais de uma vez",
                f"Existem {len(ds)} chaves diferentes com a mesma numeração.",
                "Verifique se houve emissão em contingência ou em duplicidade; cancele a nota indevida.",
                "Ajuste SINIEF 07/2005", ", ".join(x.chave for x in ds)))
        ordenados = sorted(nums)
        faltantes = sorted(set(range(ordenados[0], ordenados[-1] + 1)) - set(ordenados))
        if faltantes:
            out.append(Achado(
                "DOC006", "MEDIO", "Integridade documental",
                f"Lacunas na numeração de {tipo} série {serie}",
                f"Entre os nº {ordenados[0]} e {ordenados[-1]} faltam {len(faltantes)} número(s): "
                f"{_lista(faltantes)}.",
                "Confirme se esses números foram inutilizados ou cancelados. Caso contrário, "
                "o cliente não enviou todas as notas e a receita pode estar subdeclarada.",
                "Ajuste SINIEF 07/2005, cláusula 14ª (inutilização)",
                f"{tipo}-{serie}"))
    return out


def regra_resumo_lote(ctx: Contexto) -> list[Achado]:
    out = []
    lote = ctx.lote
    if not ctx.empresa.cnpj:
        out.append(Achado(
            "DOC007", "ALTO", "Configuração", "Empresa auditada não identificada",
            "Nenhum CNPJ foi informado ou encontrado nos documentos.",
            "Informe o CNPJ da empresa para separar notas emitidas e recebidas.", ""))
    if ctx.terceiros:
        out.append(Achado(
            "DOC008", "BAIXO", "Integridade documental",
            f"{len(ctx.terceiros)} documento(s) não envolvem a empresa auditada",
            f"Esses documentos não têm {fmt_doc(ctx.empresa.cnpj)} como emitente nem como destinatário. "
            f"Exemplos: {_lista((d.rotulo for d in ctx.terceiros), 5)}.",
            "Retire do lote documentos de outras empresas. O envio misturado é um risco de LGPD e gera lançamento errado.",
            "Lei 13.709/2018 (LGPD), art. 6º, III",
            valor=sum((d.valor_total for d in ctx.terceiros), ZERO)))
    if lote.duplicados:
        out.append(Achado(
            "DOC009", "INFO", "Importação",
            f"{len(lote.duplicados)} documento(s) duplicado(s) ignorados",
            f"O mesmo documento foi enviado mais de uma vez: {_lista(lote.duplicados, 5)}.",
            "Nenhuma ação necessária: o portal considerou cada documento uma única vez."))
    if lote.erros:
        out.append(Achado(
            "DOC010", "BAIXO", "Importação",
            f"{len(lote.erros)} arquivo(s) não importado(s)",
            "; ".join(f"{e.arquivo}: {e.motivo}" for e in lote.erros[:5])
            + (" …" if len(lote.erros) > 5 else ""),
            "Veja a aba 'Erros de importação' e reenvie os arquivos nos formatos suportados."))
    canceladas = [d for d in lote.documentos if d.situacao == "cancelada"]
    if canceladas:
        out.append(Achado(
            "DOC011", "INFO", "Integridade documental",
            f"{len(canceladas)} documento(s) cancelado(s) excluído(s) da apuração",
            f"Total cancelado: {moeda(sum((d.valor_total for d in canceladas), ZERO))}.",
            "Confira se o cancelamento foi feito dentro do prazo legal."))
    return out


REGRAS = [regra_situacao, regra_chave_e_cadastro, regra_numeracao, regra_resumo_lote]
