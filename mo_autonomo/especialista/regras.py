"""Regras do especialista.

Cada regra declara: normas que a sustentam, parâmetros que exige (norma, nome), escopo,
tipos de documento, papel da empresa (EMITENTE/DESTINATARIO/QUALQUER) e pré-condição de
perfil. Parâmetro legal só vem de norma CONFERIDO; sem ele a regra fica INATIVA (regra 3).
Nenhum número legal é escrito aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from ..util.dinheiro import soma
from ..util.documentos_id import cnpj_valido

EMITENTE, DESTINATARIO, QUALQUER = "EMITENTE", "DESTINATARIO", "QUALQUER"


@dataclass
class Resultado:
    mensagem: str
    correcao: str | None = None
    bloqueia: bool = True
    valor: object = None
    documento: str | None = None


@dataclass
class Regra:
    id: str
    titulo: str
    funcao: Callable
    normas: tuple[str, ...] = ()
    parametros: tuple[tuple[str, str], ...] = ()
    escopo: str = "documento"  # documento | competencia
    tipos: tuple[str, ...] = ()
    papel: str = QUALQUER
    precondicao: Callable | None = None
    descricao: str = ""
    extras: dict = field(default_factory=dict)


@dataclass
class Contexto:
    perfil: object
    papel: str | None
    params: dict
    catalogo: object
    data_processamento: date
    documentos: list[dict] = field(default_factory=list)  # escopo competência
    trilha: object = None


def _comp_anterior(d: date) -> str:
    y, m = (d.year, d.month - 1) if d.month > 1 else (d.year - 1, 12)
    return f"{y:04d}-{m:02d}"


# ---------------------------------------------------------------- documento
def r_soma_itens(doc, ctx):
    total = doc["totais"].get("vProd")
    if total is None or not doc["itens"]:
        return []
    itens = [i["v_prod"] for i in doc["itens"] if i["v_prod"] is not None]
    s = soma(itens)
    if s != total:
        return [Resultado(f"Soma dos itens (vProd) {s} difere do total vProd {total}.",
                          "Solicitar ao emitente carta de correção/substituição; não escriturar até esclarecer.",
                          valor=total - s)]
    return []


def r_sem_protocolo(doc, ctx):
    if doc["tipo"] in ("NFE", "NFCE", "CTE") and doc.get("autorizacao_cstat") is None:
        return [Resultado("XML sem protocolo de autorização (veio a NF/CT sem o grupo de protocolo).",
                          "Pedir o XML de distribuição (com protocolo) ou baixar pelo portal/DF-e.")]
    return []


def r_cstat(doc, ctx):
    ok = [str(x) for x in ctx.params["cstat_autorizado"]]
    c = doc.get("autorizacao_cstat")
    if c is not None and c not in ok:
        return [Resultado(f"Protocolo com cStat {c}, fora da lista de autorização do MOC.",
                          "Verificar situação da nota no portal antes de escriturar.")]
    return []


def r_crt_regime(doc, ctx):
    mapa = ctx.params["crt_por_regime"]
    crt = doc.get("crt")
    regime = getattr(ctx.perfil, "regime", None)
    if crt is None or regime is None:
        return []
    permitidos = [str(r) for r in mapa.get(str(crt), [])]
    if regime not in permitidos:
        return [Resultado(f"CRT {crt} incompatível com o regime {regime} do perfil (fonte {ctx.perfil.regime_fonte}).",
                          "Corrigir o CRT no emissor da empresa; avaliar substituição/CC-e conforme o MOC.")]
    return []


def r_cfop_tpnf(doc, ctx):
    mapa = ctx.params["cfop_digitos_por_tpnf"]
    validos = [str(x) for x in mapa.get(str(doc.get("tp_nf")), [])]
    if not validos:
        return []
    out = []
    for i in doc["itens"]:
        if i["cfop"] and i["cfop"][0] not in validos:
            out.append(Resultado(f"Item {i['n']}: CFOP {i['cfop']} incompatível com tpNF {doc.get('tp_nf')}.",
                                 "Corrigir o CFOP com o emitente (avaliar o instrumento cabível conforme o MOC)."))
    return out


def r_cfop_iddest(doc, ctx):
    mapa = ctx.params["cfop_digito_por_iddest"]
    validos = [str(x) for x in mapa.get(str(doc.get("id_dest")), [])]
    if not validos:
        return []
    return [Resultado(f"Item {i['n']}: CFOP {i['cfop']} incompatível com idDest {doc.get('id_dest')}.",
                      "Revisar destino da operação e CFOP.")
            for i in doc["itens"] if i["cfop"] and i["cfop"][0] not in validos]


def r_devolucao_sem_ref(doc, ctx):
    fins = [str(x) for x in ctx.params["fin_nfe_devolucao"]]
    if str(doc.get("fin_nfe")) in fins and not doc.get("refs"):
        return [Resultado("NF-e de devolução sem chave referenciada (NFref).",
                          "Pedir ao emitente a nota com a referência ou CC-e quando cabível.")]
    return []


def r_monofasico_simples(doc, ctx):
    prefixos = [str(p) for p in ctx.params["ncm_prefixos_monofasicos"]]
    itens = [i for i in doc["itens"] if i["ncm"] and any(i["ncm"].startswith(p) for p in prefixos)]
    if not itens:
        return []
    total = soma(i["v_prod"] for i in itens if i["v_prod"] is not None)
    return [Resultado(f"{len(itens)} item(ns) com NCM de tributação monofásica de PIS/COFINS (total {total}).",
                      "Segregar essa receita no PGDAS-D como monofásica para não recolher PIS/COFINS em duplicidade.",
                      bloqueia=False, valor=total)]


def _iss_retido(padrao):
    def regra(doc, ctx):
        if doc.get("padrao") != padrao:
            return []
        codigos = [str(x) for x in ctx.params["codigos_iss_retido"]]
        if str(doc.get("iss_retencao_codigo")) not in codigos:
            return []
        return [Resultado("NFS-e tomada com ISS retido: a empresa (tomadora) deve recolher o ISS retido.",
                          "Gerar a guia de ISS retido no município de incidência e escriturar a retenção.",
                          bloqueia=False, valor=doc["totais"].get("vServ"))]
    return regra


def r_retencoes_federais(doc, ctx):
    servicos = [str(x) for x in ctx.params["codigos_servico_sujeitos"]]
    regimes = [str(x) for x in ctx.params["regimes_tomador_obrigados"]]
    cod = str(doc.get("c_trib_nac") or "")
    if getattr(ctx.perfil, "regime", None) not in regimes or not any(cod.startswith(s) for s in servicos):
        return []
    ret = doc.get("retencoes_federais") or {}
    if not any(v for v in ret.values() if v):
        return [Resultado(f"Serviço {cod} sujeito a retenção de CSLL/COFINS/PIS sem retenção destacada na NFS-e.",
                          "Conferir enquadramento e efetuar/recolher a retenção (DARF) ou documentar a dispensa.")]
    return []


def r_competencia_rotina(doc, ctx):
    comp = doc.get("competencia")
    d = ctx.data_processamento
    if comp and comp < _comp_anterior(d):
        return [Resultado(f"Competência {comp} anterior à aceita pela rotina automática (atual ou anterior).",
                          "Importar manualmente no Domínio.", bloqueia=False)]
    return []


def r_emissao_futura(doc, ctx):
    if doc.get("emissao") and doc["emissao"] > ctx.data_processamento:
        return [Resultado(f"Data de emissão {doc['emissao']:%d/%m/%Y} posterior à data de processamento.",
                          "Conferir a data no XML com o emitente.")]
    return []


def r_cnpj_invalido(doc, ctx):
    out = []
    for campo in ("emitente_cnpj", "destinatario_cnpj"):
        v = doc.get(campo)
        if v and len(v) == 14 and not cnpj_valido(v):
            out.append(Resultado(f"{campo} com dígito verificador inválido: {v}.", "Corrigir o cadastro do participante."))
    return out


# ---------------------------------------------------------------- competência
def r_duplicidade(docs, ctx):
    out, vistos = [], {}
    for d in docs:
        ch = d.get("chave")
        if not ch:
            continue
        if ch in vistos and vistos[ch] != d["_sha256"]:
            out.append(Resultado(f"Chave {ch} recebida com conteúdos diferentes.",
                                 "Usar o XML com protocolo de autorização; descartar a versão divergente após conferência.",
                                 documento=ch))
        vistos.setdefault(ch, d["_sha256"])
    if ctx.trilha is not None:
        for ch, sha in vistos.items():
            outros = [s for s, _ in ctx.trilha.documento_por_chave(ch) if s != sha]
            if outros:
                out.append(Resultado(f"Chave {ch} já recebida antes com conteúdo diferente.",
                                     "Conferir qual versão foi importada no Domínio.", documento=ch))
    return out


def r_cancelamento(docs, ctx):
    codigos = [str(x) for x in ctx.params["tp_evento_cancelamento"]]
    canceladas = {d["chave_ref"] for d in docs if d["tipo"].startswith("EVENTO_") and str(d.get("tp_evento")) in codigos}
    return [Resultado(f"Evento de cancelamento recebido para a chave {ch}.",
                      "Garantir que a nota esteja como cancelada no Domínio (não escriturar como válida).",
                      bloqueia=False, documento=ch) for ch in sorted(canceladas)]


def r_sequencia(docs, ctx):
    grupos: dict = {}
    for d in docs:
        if d["tipo"] in ("NFE", "NFCE") and d.get("emitente_cnpj") == ctx.perfil.cnpj and (d.get("numero") or "").isdigit():
            grupos.setdefault((d["modelo"], d["serie"]), set()).add(int(d["numero"]))
    out = []
    for (mod, serie), nums in sorted(grupos.items()):
        faltam = sorted(set(range(min(nums), max(nums) + 1)) - nums)
        if faltam:
            amostra = ", ".join(map(str, faltam[:20])) + (" ..." if len(faltam) > 20 else "")
            out.append(Resultado(f"Modelo {mod} série {serie}: {len(faltam)} número(s) sem XML recebido ({amostra}).",
                                 "Pedir ao cliente os XML faltantes ou o comprovante de inutilização/cancelamento.",
                                 bloqueia=False, valor=len(faltam)))
    return out


REGRAS: list[Regra] = [
    Regra("NFE_SOMA_ITENS", "Soma dos itens × total da NF-e", r_soma_itens, tipos=("NFE", "NFCE")),
    Regra("DFE_SEM_PROTOCOLO", "Documento sem protocolo de autorização", r_sem_protocolo, tipos=("NFE", "NFCE", "CTE")),
    Regra("DFE_CSTAT", "Situação do protocolo", r_cstat, normas=("MOC_NFE",),
          parametros=(("MOC_NFE", "cstat_autorizado"),), tipos=("NFE", "NFCE")),
    Regra("NFE_CRT_REGIME", "CRT × regime tributário", r_crt_regime, normas=("MOC_NFE",),
          parametros=(("MOC_NFE", "crt_por_regime"),), tipos=("NFE", "NFCE"), papel=EMITENTE),
    Regra("NFE_CFOP_TPNF", "CFOP × tipo da operação", r_cfop_tpnf, normas=("TABELA_CFOP", "MOC_NFE"),
          parametros=(("TABELA_CFOP", "cfop_digitos_por_tpnf"),), tipos=("NFE", "NFCE")),
    Regra("NFE_CFOP_IDDEST", "CFOP × destino da operação", r_cfop_iddest, normas=("TABELA_CFOP", "MOC_NFE"),
          parametros=(("TABELA_CFOP", "cfop_digito_por_iddest"),), tipos=("NFE",)),
    Regra("NFE_DEVOLUCAO_SEM_REF", "Devolução sem nota referenciada", r_devolucao_sem_ref, normas=("MOC_NFE",),
          parametros=(("MOC_NFE", "fin_nfe_devolucao"),), tipos=("NFE",)),
    Regra("SIMPLES_MONOFASICO", "Receita monofásica no Simples (segregação no PGDAS-D)", r_monofasico_simples,
          normas=("TABELA_NCM_MONOFASICO", "LC_123_2006", "RES_CGSN_140_2018"),
          parametros=(("TABELA_NCM_MONOFASICO", "ncm_prefixos_monofasicos"),), tipos=("NFE", "NFCE"),
          papel=EMITENTE, precondicao=lambda p: p.regime == "SIMPLES"),
    Regra("NFSE_ISS_RETIDO_NACIONAL", "ISS retido a recolher pelo tomador (NFS-e Nacional)", _iss_retido("NACIONAL"),
          normas=("LC_116_2003", "LEIAUTE_NFSE_NACIONAL"),
          parametros=(("LEIAUTE_NFSE_NACIONAL", "codigos_iss_retido"),), tipos=("NFSE",), papel=DESTINATARIO),
    Regra("NFSE_ISS_RETIDO_ABRASF", "ISS retido a recolher pelo tomador (NFS-e ABRASF)", _iss_retido("ABRASF"),
          normas=("LC_116_2003", "LEIAUTE_NFSE_ABRASF"),
          parametros=(("LEIAUTE_NFSE_ABRASF", "codigos_iss_retido"),), tipos=("NFSE",), papel=DESTINATARIO),
    Regra("NFSE_RETENCOES_FEDERAIS", "Retenção de CSLL/COFINS/PIS esperada e ausente", r_retencoes_federais,
          normas=("LEI_10833_ART30",),
          parametros=(("LEI_10833_ART30", "codigos_servico_sujeitos"), ("LEI_10833_ART30", "regimes_tomador_obrigados")),
          tipos=("NFSE",), papel=DESTINATARIO),
    Regra("DOC_COMPETENCIA_ROTINA", "Competência fora da janela da rotina automática", r_competencia_rotina,
          tipos=("NFE", "NFCE", "CTE", "NFSE")),
    Regra("DOC_EMISSAO_FUTURA", "Emissão posterior ao processamento", r_emissao_futura,
          tipos=("NFE", "NFCE", "CTE", "NFSE")),
    Regra("DOC_CNPJ_INVALIDO", "CNPJ com dígito inválido", r_cnpj_invalido, tipos=("NFE", "NFCE", "CTE", "NFSE")),
    Regra("COMP_DUPLICIDADE", "Mesma chave com conteúdos diferentes", r_duplicidade, escopo="competencia"),
    Regra("COMP_CANCELAMENTO", "Cancelamento recebido", r_cancelamento, normas=("MOC_NFE",),
          parametros=(("MOC_NFE", "tp_evento_cancelamento"),), escopo="competencia"),
    Regra("COMP_SEQUENCIA", "Completude por sequência de numeração", r_sequencia, escopo="competencia"),
]
