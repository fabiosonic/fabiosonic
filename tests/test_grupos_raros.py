"""Casos raros da NFS-e: tomador do exterior (nacional e Itaboraí), comércio exterior, serviço prestado no
exterior, dedução por documentos e emissão pelo tomador/intermediário — sempre conferidos no XSD oficial."""

import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest
from lxml import etree

from nfse_itaborai import clientes, config, emissor, fiscal, lote, nacional
from nfse_itaborai.modelos import Endereco, Tomador
from nfse_itaborai.validacao import ErroValidacao
from nfse_itaborai.xml_rps import gerar_envio
from nfse_itaborai.xsd import validar_xsd
from test_nacional import CNPJ, NS, _rps, sefin  # noqa: F401  (fixture)

EXT = {"pessoa": "1", "nif": "98-7654321", "pais_iso": "US", "pais_bacen": "2496", "cidade": "Miami",
       "estado": "Florida", "cod_postal": "33101"}


def _ext_tomador():
    return Tomador("990000001", "ACME CORPORATION", Endereco("BRICKELL AVE", "100", "Downtown", "", "", ""),
                   estrangeiro=dict(EXT))


def _xml(rps):
    xml, _n, alertas = nacional.preparar(rps, producao=False)
    return etree.fromstring(xml.encode()), alertas


def test_cliente_do_exterior_no_cadastro(sefin):
    c = clientes.salvar({"razao_social": "ACME CORPORATION", "estrangeiro": {**EXT, "pais_bacen": ""},
                         "endereco": {"logradouro": "BRICKELL AVE", "numero": "100"}})
    assert c["cpf_cnpj"] == "990000001" and c["estrangeiro"]["pais_bacen"] == "2496"   # tabela de países
    assert clientes.salvar({**c, "razao_social": "ACME CORP"})["cpf_cnpj"] == "990000001"
    with pytest.raises(ValueError, match="NIF"):
        clientes.salvar({"razao_social": "X", "estrangeiro": {**EXT, "nif": ""}})
    with pytest.raises(ValueError, match="cidade"):
        clientes.salvar({"razao_social": "X", "estrangeiro": {**EXT, "cidade": ""}})
    from nfse_itaborai import inter
    with pytest.raises(inter.ErroInter, match="exterior"):
        inter.pagador("990000001")


def test_exportacao_de_servico_nacional(sefin):
    x = {"trib_issqn": "3", "pais_result": "US", "comext_moeda": "220", "comext_valor": "75.00",
         "local_prestacao_pais": "US"}
    raiz, _ = _xml(_rps(tomador=_ext_tomador(), extras=x))
    v = lambda p: raiz.findtext(p, namespaces=NS)  # noqa: E731
    assert v(".//n:toma/n:NIF") == "98-7654321" and raiz.find(".//n:toma/n:CNPJ", NS) is None
    assert v(".//n:endExt/n:cPais") == "US" and v(".//n:endExt/n:xCidade") == "Miami"
    assert v(".//n:locPrest/n:cPaisPrestacao") == "US"
    assert v(".//n:comExt/n:tpMoeda") == "220" and v(".//n:comExt/n:vServMoeda") == "75.00"
    assert v(".//n:comExt/n:mdPrestacao") == "1" and v(".//n:comExt/n:mecAFComexT") == "01"
    assert v(".//n:tribISSQN") == "3" and v(".//n:cPaisResult") == "US"


def test_exportacao_sem_comercio_exterior_e_recusada(sefin):
    with pytest.raises(ErroValidacao, match="Comércio exterior"):
        nacional.preparar(_rps(tomador=_ext_tomador(), extras={"trib_issqn": "3", "pais_result": "US"}), producao=False)
    _, alertas = _xml(_rps(tomador=_ext_tomador()))
    assert any("exterior" in a for a in alertas)


def test_sem_nif(sefin):
    t = _ext_tomador()
    t.estrangeiro = {**EXT, "nif": "", "sem_nif": "2"}
    raiz, _ = _xml(_rps(tomador=t))
    assert raiz.findtext(".//n:toma/n:cNaoNIF", namespaces=NS) == "2"


def test_deducao_por_documentos(sefin):
    docs = fiscal.normalizar_nota({"ded_docs": [
        {"chave": "3" * 44, "tp": "2", "data": "2026-09-10", "valor_dedutivel": "100", "valor_deducao": "80",
         "fornec_doc": "11222333000181", "fornec_nome": "FORNECEDOR"},
        {"tipo": "nDoc", "numero": "RECIBO 15", "tp": "99", "descricao": "Taxa", "data": "2026-09-11", "valor_deducao": "20"}]})
    assert [d["tipo"] for d in docs["ded_docs"]] == ["chNFe", "nDoc"]
    raiz, _ = _xml(_rps(extras=docs, valor_deducoes=Decimal("100")))
    d = raiz.findall(".//n:vDedRed/n:documentos/n:docDedRed", NS)
    assert len(d) == 2 and d[0].findtext("n:chNFe", namespaces=NS) == "3" * 44
    assert d[0].findtext("n:fornec/n:CNPJ", namespaces=NS) == "11222333000181"
    assert d[1].findtext("n:xDescOutDed", namespaces=NS) == "Taxa"
    with pytest.raises(ValueError, match="não pode passar"):
        fiscal.normalizar_nota({"ded_docs": [{"chave": "3" * 44, "data": "2026-09-10", "valor_dedutivel": "10",
                                              "valor_deducao": "20"}]})
    with pytest.raises(ValueError, match="OU"):
        fiscal.normalizar_nota({"ded_pct": "10", "ded_docs": docs["ded_docs"]})


def test_deducao_por_documentos_reduz_a_base(sefin):
    x = {"ded_docs": [{"tipo": "nDoc", "numero": "R1", "data": "2026-09-10", "valor_deducao": "74.40"}]}
    d = lote.montar_rps("32396063000103", "374.40", extras=x)
    assert d["valor_deducoes"] == "74.40"


def test_emissao_pelo_tomador_importacao(sefin):
    config.salvar({"empresa": {"nome": "MORAES E OLIVEIRA"}})
    x = {"tp_emit": "2", "motivo_emis_ti": "1", "comext_moeda": "220", "comext_valor": "50", "comext_md": "1"}
    raiz, _ = _xml(_rps(tomador=_ext_tomador(), extras=x))
    v = lambda p: raiz.findtext(p, namespaces=NS)  # noqa: E731
    assert v(".//n:tpEmit") == "2" and v(".//n:cMotivoEmisTI") == "1"
    assert v(".//n:prest/n:NIF") == "98-7654321" and v(".//n:prest/n:xNome") == "ACME CORPORATION"
    assert v(".//n:prest/n:regTrib/n:opSimpNac") == "1"
    assert v(".//n:toma/n:CNPJ") == CNPJ and v(".//n:toma/n:xNome") == "MORAES E OLIVEIRA"


def test_emissao_pelo_intermediario(sefin):
    x = {"tp_emit": "3", "motivo_emis_ti": "2", "toma_doc": "54399432000146", "toma_nome": "TOMADOR FINAL"}
    raiz, _ = _xml(_rps(extras=x))
    v = lambda p: raiz.findtext(p, namespaces=NS)  # noqa: E731
    assert v(".//n:tpEmit") == "3" and v(".//n:prest/n:CNPJ") == "32396063000103"
    assert v(".//n:toma/n:CNPJ") == "54399432000146" and v(".//n:interm/n:CNPJ") == CNPJ
    with pytest.raises(ErroValidacao, match="intermediário"):
        nacional.preparar(_rps(extras={"tp_emit": "3"}), producao=False)


def test_tomador_do_exterior_no_webservice_de_itaborai(sefin):
    from nfse_itaborai.modelos import Prestador
    rps = _rps(tomador=_ext_tomador(), numero="5")
    xml = gerar_envio(Prestador(CNPJ, "1034265", "x"), [rps], lote="1", producao=False)
    validar_xsd(xml)
    raiz = ET.fromstring(xml.split("?>", 1)[1])
    assert raiz.findtext(".//Tomador/CpfCnpj") == "" and raiz.findtext(".//Tomador/Nif") == "98-7654321"
    assert raiz.findtext(".//Tomador/InscricaoMunicipal") == "" and raiz.findtext(".//Tomador/Tipo") == "1"
    assert raiz.findtext(".//Endereco/CodigoPais") == "2496" and raiz.findtext(".//Endereco/CidadeEstrangeiro") == "Miami"
    assert raiz.findtext(".//Endereco/CodigoMunicipio") == "" and raiz.findtext(".//Endereco/Cep") == "33101"
    assert emissor.rps_de_dict({"tomador": clientes.para_dict_tomador(
        {"cpf_cnpj": "990000001", "razao_social": "ACME", "estrangeiro": EXT}), "itens": []}).tomador.estrangeiro == EXT


def test_emissao_pelo_tomador_nao_vira_conta_a_receber(sefin, monkeypatch):
    from nfse_itaborai import db, tela
    chamadas = []
    monkeypatch.setattr(lote, "emitir_um", lambda *a, **k: chamadas.append(k) or {"sucesso": True, "chave": "X" * 50,
                                                                                  "alertas": []})
    r = tela._emitir_item({"cpf_cnpj": "32396063000103", "valor": "100", "extras": {"tp_emit": "2"}})
    assert r["sucesso"] and chamadas[0]["canal"] == "nacional" and chamadas[0]["producao"] is False
    assert not db.linhas("SELECT * FROM titulos")
    assert any("tomadora" in a for a in r["alertas"])
