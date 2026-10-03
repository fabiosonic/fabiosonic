"""Geração do XML de envio (RpsNfse) e de cancelamento (CancelaNfse).

Estrutura validada contra o XSD oficial da prefeitura (schemas/webserviceNFSe.xsd).
Autenticação, transporte e cancelamento seguem o provedor CTA 2.00 do Projeto ACBr
(Fontes/ACBrDFe/ACBrNFSeX/Provedores/CTA.*). Formatos de desdobro e de
ResponsavelRecolhimento conferidos com a NFS-e 3385 (08/2026) aceita pelo webservice.
"""

from __future__ import annotations

import base64
import hashlib
import re
import unicodedata
from datetime import datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from .modelos import Prestador, Rps, dinheiro

VERSAO = "2.00"
MAX_ITENS = 5
PRODUCAO = "2"
HOMOLOGACAO = "1"


def so_digitos(texto) -> str:
    return re.sub(r"\D", "", str(texto or ""))


def texto(valor) -> str:
    """Remove acentos, compacta espaços e escapa para XML (como o ACBr faz)."""
    s = unicodedata.normalize("NFKD", str(valor or ""))
    # Só ASCII: o envio declara Cp1252 e o ACBr retira acentos; assim não há ambiguidade.
    s = "".join(c for c in s if not unicodedata.combining(c)).encode("ascii", "ignore").decode()
    s = re.sub(r"\s+", " ", s).strip()
    return escape(s, {'"': "&quot;", "'": "&#39;"})


def dec(valor) -> str:
    return f"{dinheiro(valor):.2f}"


def data_hora(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def formatar_item_lista(item: str) -> str:
    """'1719' / '17.19' / '701' -> 'NN.NN' (o XSD exige exatamente 5 caracteres)."""
    d = so_digitos(item).zfill(4)[:4]
    return f"{d[0:2]}.{d[2:4]}"


def formatar_desdobro(codigo: str) -> str:
    """'171901' -> '17.19.01' (formato aceito na NFS-e 3385 de 08/2026)."""
    d = so_digitos(codigo)
    return f"{d[0:2]}.{d[2:4]}.{d[4:6]}" if len(d) == 6 else d


def chave_seguranca_envio(cnpj: str, chave: str, data_emissao: str) -> str:
    """Base64 do SHA-256 (hex minúsculo) de CNPJ + chave privada + DataEmissao."""
    hexa = hashlib.sha256((cnpj + chave + data_emissao).encode("utf-8")).hexdigest().lower()
    return base64.b64encode(hexa.encode("ascii")).decode("ascii")


def chave_seguranca_cancelamento(cnpj: str, chave: str, data_emissao: str) -> str:
    """Base64 do SHA-1 binário de CNPJ + chave privada + DataEmissao."""
    return base64.b64encode(hashlib.sha1((cnpj + chave + data_emissao).encode("utf-8")).digest()).decode("ascii")


def _tag(nome: str, conteudo: str = "") -> str:
    return f"<{nome}>{conteudo}</{nome}>" if conteudo != "" else f"<{nome}/>"


def gerar_xml_rps(rps: Rps) -> str:
    """Elemento <Rps> (sem declaração XML)."""
    emissao = rps.data_emissao or datetime.now()
    competencia = rps.competencia or emissao.date()

    partes = ["<Rps>"]
    partes.append("<IdentificacaoRps>"
                  + _tag("Numero", so_digitos(rps.numero))
                  + _tag("DataDeEmissao", data_hora(emissao))
                  + _tag("Competencia", competencia.strftime("%m-%Y"))
                  + _tag("LocalDaPrestacao", so_digitos(rps.local_prestacao))
                  + _tag("LocalDoRecolhimento", str(int(so_digitos(rps.local_recolhimento) or 0)))
                  + _tag("CodigoDaObra", texto(rps.codigo_obra))
                  + _tag("TipoDeTributacao", rps.tipo_tributacao)
                  + "</IdentificacaoRps>")

    # O layout tem sempre 5 blocos Servico1..Servico5; os não usados vão zerados.
    for i in range(MAX_ITENS):
        if i < len(rps.itens):
            it = rps.itens[i]
            qtd, desc, unit, tot = int(it.quantidade), it.descricao, it.valor_unitario, it.valor_total
        else:
            qtd, desc, unit, tot = 0, "", Decimal(0), Decimal(0)
        partes.append(f"<Servico{i + 1}>"
                      + _tag("QuantidadeDoItem", str(qtd))
                      + _tag("DescritivoDoItem", texto(desc))
                      + _tag("ValorUnitarioDoItem", dec(unit))
                      + _tag("ValorTotalDoItem", dec(tot))
                      + f"</Servico{i + 1}>")

    liquido = rps.valor_liquido
    # manual 2026: Simples Nacional no item 17.19 não destaca alíquota nem valor do ISS
    sem_iss = rps.tipo_tributacao == "4" and formatar_item_lista(rps.item_lista_servico) == "17.19"
    carga = (rps.valor_total_tributos / liquido * 100) if liquido > 0 else Decimal(0)
    partes.append("<Valores>"
                  + _tag("ValorTotalDosServicos", dec(rps.valor_servicos))
                  + _tag("ValorDeducoes", dec(rps.valor_deducoes))
                  + _tag("DescontoIncondicionado", dec(rps.desconto_incondicionado))
                  + _tag("DescontoCondicionado", dec(rps.desconto_condicionado))
                  + _tag("BaseDeCalculoDoISS", dec(rps.base_calculo))
                  + _tag("Aliquota", dec(Decimal(0) if sem_iss else rps.aliquota_iss))
                  + _tag("ValorIss", dec(Decimal(0) if sem_iss else rps.valor_iss))
                  + _tag("ValorLiquidoNota", dec(liquido))
                  + _tag("CargaTributariaTotal", dec(carga))
                  + _tag("ValorCargaTributariaTotal", dec(rps.valor_total_tributos))
                  + "</Valores>")

    partes.append("<Informacoes>"
                  + _tag("IssRetido", rps.iss_retido)
                  + _tag("ResponsavelRecolhimento", rps.responsavel)
                  + _tag("ItemListaServico", formatar_item_lista(rps.item_lista_servico))
                  + _tag("CodigoNbs", so_digitos(rps.codigo_nbs))
                  + _tag("CodigoLsnDesdobro", formatar_desdobro(rps.codigo_desdobro))
                  + _tag("ClassificacaoCNAE", so_digitos(rps.cnae))
                  # manual 2026: "Não se aplica em Itaboraí" — vai sempre vazio
                  + _tag("CodigoTributacaoMunicipio", "")
                  + "</Informacoes>")

    x = rps.extras or {}
    imovel = ""
    if x.get("imovel_cep") and x.get("imovel_lgr"):     # serviço sobre bem imóvel (exceto obra)
        imovel = ("<ImovelIBSCBS>" + _tag("Cep", so_digitos(x["imovel_cep"])[:8])
                  + _tag("CodigoMunicipio", so_digitos(x.get("imovel_cmun"))[:7]) + _tag("Uf", texto(x.get("imovel_uf"))[:2].upper())
                  + _tag("TipoLogradouro", texto(x.get("imovel_tipo_lgr"))[:10]) + _tag("Logradouro", texto(x["imovel_lgr"])[:80])
                  + _tag("Bairro", texto(x.get("imovel_bairro"))[:30]) + _tag("Numero", texto(x.get("imovel_nro"))[:6])
                  + _tag("Complemento", texto(x.get("imovel_cpl"))[:30]) + "</ImovelIBSCBS>")
    # obrigatório desde 01/06/2026 (validacao.py exige os dois códigos a partir dessa data)
    if so_digitos(rps.indicador_operacao) or so_digitos(rps.classificacao_tributaria):
        partes.append("<InformacoesIBSCBS>"
                      + _tag("IndicadorOperacao", so_digitos(rps.indicador_operacao))
                      + _tag("ClassificacaoTributaria", so_digitos(rps.classificacao_tributaria))
                      + imovel + "</InformacoesIBSCBS>")

    r = rps.retencoes
    partes.append("<ValoresRetencoes>"
                  + _tag("AliquotaPIS", dec(r.aliquota_pis))
                  + _tag("ValorPIS", dec(r.valor_pis))
                  + _tag("AliquotaCOFINS", dec(r.aliquota_cofins))
                  + _tag("ValorCOFINS", dec(r.valor_cofins))
                  + _tag("AliquotaCSLL", dec(r.aliquota_csll))
                  + _tag("ValorCSLL", dec(r.valor_csll))
                  + _tag("BaseCalculoINSS", dec(rps.base_calculo if r.valor_inss else 0))
                  + _tag("AliquotaINSS", dec(r.aliquota_inss))
                  + _tag("ValorINSS", dec(r.valor_inss))
                  + _tag("AliquotaIR", dec(r.aliquota_ir))
                  + _tag("ValorIR", dec(r.valor_ir))
                  + "</ValoresRetencoes>")

    partes.append(_tag("Observacoes", texto(rps.observacoes)))

    t = rps.tomador
    partes.append("<Tomador>"
                  + _tag("Tipo", t.tipo)
                  + _tag("CpfCnpj", so_digitos(t.cpf_cnpj))
                  # Sem inscrição municipal a prefeitura exige "0" (como no retorno da NFS-e 3385)
                  + _tag("InscricaoMunicipal", texto(t.inscricao_municipal) or ("0" if t.tipo else ""))
                  + _tag("InscricaoEstadual", texto(t.inscricao_estadual))
                  + _tag("RazaoSocial", texto(t.razao_social))
                  + "</Tomador>")

    e = t.endereco
    partes.append("<Endereco>"
                  + _tag("TipoLogradouro", texto(e.tipo_logradouro))
                  + _tag("Logradouro", texto(e.logradouro))
                  + _tag("Numero", texto(e.numero))
                  + _tag("Complemento", texto(e.complemento))
                  + _tag("Bairro", texto(e.bairro))
                  + _tag("CodigoMunicipio", so_digitos(e.codigo_municipio))
                  + _tag("Uf", texto(e.uf).upper())
                  + _tag("CodigoPais", str(int(e.codigo_pais)).zfill(4))
                  + _tag("Cep", so_digitos(e.cep))
                  + _tag("TelefoneContatoTomador", so_digitos(t.telefone))
                  + _tag("EmailTomador", texto(t.email))
                  + "</Endereco>")

    if x.get("evento_nome"):
        partes.append("<Evento>" + _tag("NomeEvento", texto(x["evento_nome"])[:255])
                      + _tag("DataInicio", x.get("evento_ini", "")) + _tag("DataFim", x.get("evento_fim") or x.get("evento_ini", ""))
                      + "<EnderecoEvento>" + _tag("Cep", so_digitos(x.get("evento_cep"))[:8])
                      + _tag("TipoLogradouro", texto(x.get("evento_tipo_lgr"))[:10]) + _tag("Logradouro", texto(x.get("evento_lgr"))[:80])
                      + _tag("Numero", texto(x.get("evento_nro") or "S/N")[:6]) + _tag("Bairro", texto(x.get("evento_bairro"))[:30])
                      + _tag("Complemento", texto(x.get("evento_cpl"))[:30]) + "</EnderecoEvento></Evento>")

    partes.append("</Rps>")
    return "".join(partes)


def gerar_envio(prestador: Prestador, lista_rps: list[Rps], lote: str,
                producao: bool, agora: datetime | None = None) -> str:
    """Documento completo <RpsNfse> enviado ao webservice."""
    agora = agora or datetime.now()
    data_emissao = data_hora(agora)
    cnpj = so_digitos(prestador.cnpj)
    sim_nao = lambda b: "1" if b else "2"  # noqa: E731

    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<RpsNfse versao="{VERSAO}" Id="{so_digitos(lote)}">'
            + _tag("ChaveSeguranca", chave_seguranca_envio(cnpj, prestador.chave_webservice, data_emissao))
            + _tag("Producao", PRODUCAO if producao else HOMOLOGACAO)
            + "<Prestador>"
            + _tag("DataEmissao", data_emissao)
            + _tag("Cnpj", cnpj)
            + _tag("InscricaoEstadual", texto(prestador.inscricao_estadual))
            + _tag("InscricaoMunicipal", so_digitos(prestador.inscricao_municipal))
            + _tag("OptanteSimplesNacional", sim_nao(prestador.optante_simples))
            + _tag("IncentivoFiscalImunidade", prestador.incentivo_fiscal if prestador.incentivo_fiscal in ("1", "2", "3")
                   else sim_nao(prestador.incentivo_fiscal))
            + "</Prestador>"
            + "<ListaRps>" + "".join(gerar_xml_rps(r) for r in lista_rps) + "</ListaRps>"
            + "</RpsNfse>")


def gerar_cancelamento(prestador: Prestador, numero_nfse: str, justificativa: str,
                       producao: bool, agora: datetime | None = None) -> str:
    agora = agora or datetime.now()
    data_emissao = data_hora(agora)
    cnpj = so_digitos(prestador.cnpj)
    numero = so_digitos(numero_nfse)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            f'<CancelaNfse versao="{VERSAO}" Id="{numero}">'
            + _tag("ChaveSeguranca", chave_seguranca_cancelamento(cnpj, prestador.chave_webservice, data_emissao))
            + _tag("Producao", PRODUCAO if producao else HOMOLOGACAO)
            + "<Prestador>" + _tag("DataEmissao", data_emissao) + _tag("Cnpj", cnpj) + "</Prestador>"
            + "<Nfse><IdentificacaoNfse>"
            + _tag("Numero", numero)
            + _tag("Justificativa", texto(justificativa))
            + "</IdentificacaoNfse></Nfse>"
            + "</CancelaNfse>")
