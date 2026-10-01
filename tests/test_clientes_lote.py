import json
from pathlib import Path

import pytest

from nfse_itaborai import clientes, emissor, lote
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)

DADOS = Path(__file__).parent / "dados"

CLIENTE = {
    "cpf_cnpj": "32.396.063/0001-03", "razao_social": "RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA",
    "endereco": {"logradouro": "AV AVENIDA PRESIDENTE VARGAS", "numero": "435", "bairro": "Centro",
                 "codigo_municipio": "3304557", "cep": "20071904"},
    "ultimo_valor": "374.40",
}

NACIONAL = """<?xml version="1.0" encoding="UTF-8"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
<infNFSe><nNFSe>99003801</nNFSe><emit><CNPJ>24875410000144</CNPJ></emit><DPS versao="1.01"><infDPS>
<dhEmi>2026-08-29T12:19:10-03:00</dhEmi><prest><CNPJ>24875410000144</CNPJ></prest>
<toma><CNPJ>32396063000103</CNPJ><xNome>RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA</xNome><end><endNac>
<cMun>3304557</cMun><CEP>20071904</CEP></endNac><xLgr>AV AVENIDA PRESIDENTE VARGAS</xLgr><nro>435</nro>
<xBairro>Centro</xBairro></end></toma><valores><vServPrest><vServ>374.40</vServ></vServPrest></valores>
</infDPS></DPS></infNFSe></NFSe>"""


@pytest.fixture
def pasta(tmp_path, monkeypatch):
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    return tmp_path


def test_salvar_normaliza_e_separa_tipo_logradouro(pasta):
    c = clientes.salvar(CLIENTE)
    assert c["cpf_cnpj"] == "32396063000103"
    assert c["endereco"]["tipo_logradouro"] == "AV"
    assert c["endereco"]["logradouro"] == "AVENIDA PRESIDENTE VARGAS"
    assert c["endereco"]["uf"] == "RJ"
    assert clientes.obter("32396063000103")["razao_social"].startswith("RPS")
    assert clientes.excluir("32396063000103") and clientes.listar() == []


def test_salvar_rejeita_sem_nome_ou_documento(pasta):
    with pytest.raises(ValueError):
        clientes.salvar({"cpf_cnpj": "123", "razao_social": "X"})
    with pytest.raises(ValueError):
        clientes.salvar({"cpf_cnpj": "32396063000103", "razao_social": ""})


def test_importa_xml_nacional_e_retorno_do_webservice(pasta):
    xmls = pasta / "xmls"
    xmls.mkdir()
    (xmls / "a.xml").write_text(NACIONAL, encoding="utf-8")
    (xmls / "b.xml").write_text((DADOS / "retorno_nfse_real.xml").read_text(encoding="utf-8"), encoding="utf-8")
    (xmls / "lixo.xml").write_text("<x/>", encoding="utf-8")
    r = clientes.importar_xmls(xmls, "24875410000144")
    assert r == {"xml_lidos": 2, "xml_ignorados": 1, "clientes_novos": 2, "clientes_total": 2}
    rps = clientes.obter("32396063000103")
    assert rps["ultimo_valor"] == "374.40" and rps["ultima_nfse"] == "99003801"
    ret = clientes.obter("11222333000181")
    assert ret["inscricao_municipal"] == ""          # "0" no retorno = sem inscrição
    assert ret["endereco"]["tipo_logradouro"] == "R" and ret["endereco"]["numero"] == "100"


def test_importacao_ignora_notas_de_outro_prestador(pasta):
    xmls = pasta / "x"
    xmls.mkdir()
    (xmls / "a.xml").write_text(NACIONAL, encoding="utf-8")
    assert clientes.importar_xmls(xmls, "11111111000111")["xml_lidos"] == 0


def test_brasilapi_convertida():
    c = clientes.de_brasilapi({"cnpj": "54399432000146", "razao_social": "ESPACO CULTIVAR FONOAUDIOLOGIA LTDA",
                               "descricao_tipo_de_logradouro": "RUA", "logradouro": "FREI CANECA", "numero": "441",
                               "bairro": "ESTACIO", "codigo_municipio_ibge": 3304557, "uf": "RJ",
                               "cep": "20211020", "ddd_telefone_1": "2199999999", "email": "X@Y.COM"})
    assert c["endereco"] == {"tipo_logradouro": "RUA", "logradouro": "FREI CANECA", "numero": "441",
                             "complemento": "", "bairro": "ESTACIO", "codigo_municipio": "3304557", "uf": "RJ",
                             "cep": "20211020"}
    assert c["email"] == "x@y.com"


def test_montar_rps_usa_cadastro_e_servico_padrao(pasta):
    clientes.salvar(CLIENTE)
    d = lote.montar_rps("32396063000103", "1.234,56")
    assert d["itens"][0]["valor_unitario"] == "1234.56"
    assert d["itens"][0]["descricao"] == "HONORARIOS CONTABEIS MENSAIS"
    assert d["classificacao_tributaria"] == "200052" and d["indicador_operacao"] == "100301"
    assert d["valor_total_tributos"] == "224.44"       # 18,18% (IBPT das notas da empresa)
    assert d["tomador"]["cpf_cnpj"] == "32396063000103"
    with pytest.raises(ValueError):
        lote.montar_rps("00000000000000", 10)


def test_lote_emite_em_sequencia_e_ignora_duplicada(ambiente):  # noqa: F811
    url, pasta = ambiente
    clientes.salvar(CLIENTE)
    clientes.salvar(CLIENTE | {"cpf_cnpj": "54399432000146", "razao_social": "Espaco Cultivar Fonoaudiologia Ltda"})
    r = lote.emitir_lote([{"cpf_cnpj": "32396063000103", "valor": "374,40"},
                          {"cpf_cnpj": "54399432000146", "valor": "350"},
                          {"cpf_cnpj": "54399432000146", "valor": "350"},
                          {"cpf_cnpj": "99999999000199", "valor": "10"}], url=url)
    assert [x["sucesso"] for x in r] == [True, True, False, False]
    assert "duplicada" in r[2]["erros"][0] and "cadastro" in r[3]["erros"][0]
    assert len(Simulador.recebidos) == 2


def test_tela_estado_e_ambiente(pasta, monkeypatch):
    for k in ("ITABORAI_AMBIENTE", "ITABORAI_CIENTE_IRREVERSIVEL"):
        monkeypatch.delenv(k, raising=False)
    (pasta / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_AMBIENTE=homologacao\n", encoding="utf-8")
    clientes.salvar(CLIENTE)
    e = tratar("estado", {})
    assert e["producao"] is False and len(e["clientes"]) == 1 and e["padrao"]["descricao"]
    assert tratar("ambiente", {"producao": True})["producao"] is True
    env = (pasta / ".env").read_text(encoding="utf-8")
    assert "ITABORAI_AMBIENTE=producao" in env and "ITABORAI_CIENTE_IRREVERSIVEL=SIM" in env
    assert "ITABORAI_CNPJ=24875410000144" in env
    assert tratar("ambiente", {"producao": False})["producao"] is False
    assert tratar("cliente/salvar", {"cpf_cnpj": "1", "razao_social": ""})["erro"]


def test_reimportacao_preserva_correcao_manual(pasta):
    xmls = pasta / "x"
    xmls.mkdir()
    (xmls / "a.xml").write_text(NACIONAL, encoding="utf-8")
    clientes.importar_xmls(xmls, "24875410000144")
    c = clientes.obter("32396063000103")
    c["endereco"]["cep"] = "20071000"
    c["email"] = "novo@cliente.com"
    clientes.salvar(c)
    r = clientes.importar_xmls(xmls, "24875410000144")
    assert r["clientes_novos"] == 0
    c = clientes.obter("32396063000103")
    assert c["endereco"]["cep"] == "20071000" and c["email"] == "novo@cliente.com"
    assert c["ultimo_valor"] == "374.40"
