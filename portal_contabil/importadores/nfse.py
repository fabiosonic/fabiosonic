"""Importador de NFS-e: Padrão Nacional (ADN/Sefin Nacional) e ABRASF (municipais).

O layout nacional é obrigatório para emissão desde jan/2026 (LC 214/2025, art. 62),
mas o histórico de 2025 e de municípios em transição ainda chega em ABRASF.
"""
from __future__ import annotations

from ..modelos import DocumentoFiscal, EventoFiscal, Participante
from ..util import ZERO, dec, parse_data, primeiro, texto


# --------------------------------------------------------------- nacional

def ler_nfse_nacional(raiz, arquivo: str) -> DocumentoFiscal:
    inf = raiz.find(".//infNFSe")
    if inf is None:
        raise ValueError("grupo infNFSe não encontrado")
    dps = inf.find(".//infDPS")
    prest = dps.find("prest") if dps is not None else None
    toma = dps.find("toma") if dps is not None else None
    emit = inf.find("emit")
    serv = dps.find("serv") if dps is not None else None
    vals_dps = dps.find("valores") if dps is not None else None
    vals = inf.find("valores")

    # opSimpNac: 1 = não optante; 2 = MEI; 3 = ME/EPP optante
    op_simples = texto(prest, "regTrib/opSimpNac")
    prestador = Participante(
        documento=texto(emit, "CNPJ") or texto(emit, "CPF") or texto(prest, "CNPJ") or texto(prest, "CPF"),
        nome=texto(emit, "xNome") or texto(prest, "xNome"),
        uf=texto(emit, "enderNac/UF"),
        crt={"2": "4", "3": "1", "1": "3"}.get(op_simples, ""),
        optante_simples=None if not op_simples else op_simples in {"2", "3"},
    )
    tomador = Participante(
        documento=texto(toma, "CNPJ") or texto(toma, "CPF") or texto(toma, "NIF"),
        nome=texto(toma, "xNome"),
        uf=texto(toma, "end/endNac/UF"),
    )

    trib_mun = vals_dps.find("trib/tribMun") if vals_dps is not None else None
    trib_fed = vals_dps.find("trib/tribFed") if vals_dps is not None else None
    piscofins = trib_fed.find("piscofins") if trib_fed is not None else None
    retencoes: dict = {}
    for chave, campo in (("irrf", "vRetIRRF"), ("csll", "vRetCSLL"), ("inss", "vRetCP")):
        v = dec(texto(trib_fed, campo))
        if v:
            retencoes[chave] = v
    # tpRetPisCofins "1" = retido (leiaute 1.00). Conferir a tabela da versão do leiaute em uso.
    if texto(piscofins, "tpRetPisCofins") == "1":
        for chave, campo in (("pis", "vPis"), ("cofins", "vCofins")):
            v = dec(texto(piscofins, campo))
            if v:
                retencoes[chave] = v

    valor_servico = dec(texto(vals_dps, "vServPrest/vServ"))
    desconto = dec(texto(vals_dps, "vDescCondIncond/vDescIncond"))
    aliq = texto(vals, "pAliqAplic") or texto(trib_mun, "pAliq")
    valor_iss = dec(texto(vals, "vISSQN"))
    tp_ret = texto(trib_mun, "tpRetISSQN")  # 1 = não retido; 2 = tomador; 3 = intermediário
    liquido = dec(texto(vals, "vLiq"))

    chave = inf.get("Id", "").removeprefix("NFS")
    return DocumentoFiscal(
        tipo="NFSE",
        chave=chave or f"NFSE-{prestador.documento}-{texto(inf, 'nNFSe')}",
        numero=texto(inf, "nNFSe"),
        serie=texto(dps, "serie"),
        data_emissao=parse_data(texto(dps, "dhEmi") or texto(inf, "dhProc")),
        emitente=prestador,
        destinatario=tomador,
        valor_total=valor_servico,
        arquivo=arquivo,
        situacao="autorizada",
        layout="nacional",
        valor_servico=valor_servico,
        desconto_incondicionado=desconto,
        valor_liquido=liquido,
        base_iss=dec(texto(vals, "vBC")) or (valor_servico - desconto),
        aliquota_iss=dec(aliq) if aliq else None,
        valor_iss=valor_iss,
        iss_retido=tp_ret in {"2", "3"},
        retencoes=retencoes,
        codigo_servico=texto(serv, "cServ/cTribNac"),
        descricao_servico=texto(serv, "cServ/xDescServ"),
    )


def ler_evento_nfse_nacional(raiz, arquivo: str) -> EventoFiscal | None:
    ped = raiz.find(".//infPedReg")
    if ped is None:
        return None
    if ped.find("e101101") is None and ped.find("e105102") is None:
        return None  # só cancelamento / cancelamento por substituição
    return EventoFiscal(
        chave=texto(ped, "chNFSe"),
        tipo="cancelamento",
        data=parse_data(texto(ped, "dhEvento")),
        arquivo=arquivo,
    )


# ----------------------------------------------------------------- ABRASF

def _ou(a, b):
    return a if a is not None else b


def _doc_abrasf(el) -> str:
    if el is None:
        return ""
    return texto(el, ".//Cnpj") or texto(el, ".//Cpf")


def ler_nfse_abrasf(raiz, arquivo: str) -> list[DocumentoFiscal]:
    canceladas = {
        texto(c, ".//Numero") for c in raiz.iter("NfseCancelamento")
    }
    docs = []
    for inf in raiz.iter("InfNfse"):
        decl = primeiro(inf, ".//InfDeclaracaoPrestacaoServico", ".//DeclaracaoPrestacaoServico")
        base = decl if decl is not None else inf
        serv = base.find(".//Servico")
        valores = serv.find("Valores") if serv is not None else None
        vnfse = inf.find("ValoresNfse")

        prest_el = _ou(primeiro(inf, "PrestadorServico", ".//PrestadorServico"), primeiro(base, "Prestador"))
        toma_el = primeiro(base, ".//TomadorServico", ".//Tomador")
        optante = texto(base, ".//OptanteSimplesNacional") or texto(inf, "OptanteSimplesNacional")
        prestador = Participante(
            documento=_doc_abrasf(_ou(primeiro(prest_el, "IdentificacaoPrestador"), prest_el)),
            nome=texto(prest_el, "RazaoSocial"),
            uf=texto(prest_el, "Endereco/Uf"),
            optante_simples=None if not optante else optante == "1",
            crt="1" if optante == "1" else ("3" if optante == "2" else ""),
        )
        tomador = Participante(
            documento=_doc_abrasf(_ou(primeiro(toma_el, "IdentificacaoTomador"), toma_el)),
            nome=texto(toma_el, "RazaoSocial"),
            uf=texto(toma_el, "Endereco/Uf"),
        )

        def v(campo):
            return dec(texto(valores, campo))

        retencoes = {k: v(c) for k, c in (("irrf", "ValorIr"), ("pis", "ValorPis"),
                                          ("cofins", "ValorCofins"), ("csll", "ValorCsll"),
                                          ("inss", "ValorInss")) if v(c)}
        aliq_txt = texto(vnfse, "Aliquota") or texto(valores, "Aliquota")
        aliq = dec(aliq_txt) if aliq_txt else None
        if aliq is not None and aliq < 1:  # alguns municípios informam 0,05 em vez de 5
            aliq = aliq * 100
        iss_retido = (texto(serv, "IssRetido") or texto(valores, "IssRetido")) == "1"
        valor_servico = v("ValorServicos")
        numero = texto(inf, "Numero")
        docs.append(DocumentoFiscal(
            tipo="NFSE",
            chave=f"ABRASF-{prestador.documento}-{numero}-{texto(inf, 'CodigoVerificacao')}",
            numero=numero,
            serie="",
            data_emissao=parse_data(texto(inf, "DataEmissao") or texto(base, "Competencia")),
            emitente=prestador,
            destinatario=tomador,
            valor_total=valor_servico,
            arquivo=arquivo,
            situacao="cancelada" if numero in canceladas else "autorizada",
            layout="abrasf",
            valor_servico=valor_servico,
            desconto_incondicionado=v("DescontoIncondicionado"),
            valor_liquido=dec(texto(vnfse, "ValorLiquidoNfse")) or v("ValorLiquidoNfse"),
            base_iss=dec(texto(vnfse, "BaseCalculo")) or valor_servico,
            aliquota_iss=aliq,
            valor_iss=dec(texto(vnfse, "ValorIss")) or v("ValorIss"),
            iss_retido=iss_retido,
            retencoes=retencoes,
            codigo_servico=texto(serv, "ItemListaServico"),
            descricao_servico=texto(serv, "Discriminacao")[:200],
        ))
    if not docs:
        raise ValueError("nenhuma InfNfse encontrada")
    return docs


__all__ = ["ler_nfse_nacional", "ler_nfse_abrasf", "ler_evento_nfse_nacional", "ZERO"]
