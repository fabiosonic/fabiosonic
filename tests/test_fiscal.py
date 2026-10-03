"""Regras fiscais: regra geral (Configurações) e regra específica do tomador, nos canais nacional e municipal."""

from decimal import Decimal

from lxml import etree

from nfse_itaborai import clientes, config, emissor, fiscal, lote, nacional
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)

NS = {"n": "http://www.sped.fazenda.gov.br/nfse"}


def _dps(doc, valor="10000"):
    d = lote.montar_rps(doc, valor)
    d.pop("_alertas_fiscais")
    xml = nacional.gerar_dps(emissor.rps_de_dict(d), emissor.prestador_do_ambiente(), False, "900", "1")
    nacional.validar_xsd(xml, "DPS_v1.01.xsd")
    raiz = etree.fromstring(xml.encode())
    return raiz, lambda p: raiz.findtext(p, namespaces=NS)


def test_regra_geral_do_presumido_com_retencoes(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido", "ret_irrf_pct": "1,5", "ret_pis_pct": "0.65",
                              "ret_cofins_pct": "3", "ret_csll_pct": "1"}})
    d = lote.montar_rps(CLI_A["cpf_cnpj"], "10000")
    r = d["retencoes"]
    assert (r["valor_ir"], r["valor_pis"], r["valor_cofins"], r["valor_csll"]) == ("150.00", "65.00", "300.00", "100.00")
    assert d["tipo_tributacao"] == "0"
    raiz, v = _dps(CLI_A["cpf_cnpj"])
    assert v(".//n:opSimpNac") == "1" and raiz.find(".//n:regApTribSN", NS) is None
    assert v(".//n:piscofins/n:CST") == "01" and v(".//n:pAliqPis") == "0.65" and v(".//n:pAliqCofins") == "3.00"
    assert v(".//n:vPis") == "65.00" and v(".//n:vCofins") == "300.00" and v(".//n:tpRetPisCofins") == "3"
    assert v(".//n:vRetIRRF") == "150.00" and v(".//n:vRetCSLL") == "465.00"       # NT 007: PIS+COFINS+CSLL
    assert raiz.find(".//n:pTotTribSN", NS) is None and raiz.find(".//n:IBSCBS", NS) is not None


def test_regra_do_tomador_vale_so_para_ele(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "simples"}})
    c = clientes.obter(CLI_A["cpf_cnpj"])
    tratar("cliente/salvar", c | {"fiscal": {"usar_geral": False, "iss_retido": True, "aliquota_iss_retido": "2,01",
                                             "ret_irrf_pct": "1.5"}})
    assert clientes.obter(CLI_A["cpf_cnpj"])["fiscal"]["usar_geral"] is False
    raiz, v = _dps(CLI_A["cpf_cnpj"])
    assert v(".//n:tpRetISSQN") == "2" and v(".//n:pAliq") == "2.01" and v(".//n:vRetIRRF") == "150.00"
    assert raiz.find(".//n:piscofins", NS) is None and v(".//n:opSimpNac") == "3"
    raiz, v = _dps(CLI_B["cpf_cnpj"])                                   # outro tomador: regra geral
    assert v(".//n:tpRetISSQN") == "1" and raiz.find(".//n:pAliq", NS) is None and raiz.find(".//n:tribFed", NS) is None
    # dispensa legal: IRRF de até R$ 10 não é retido
    d = lote.montar_rps(CLI_A["cpf_cnpj"], "500")
    assert d["retencoes"]["valor_ir"] == "0" and "dispensado" in d["_alertas_fiscais"][0]
    # volta para a regra geral
    tratar("cliente/salvar", clientes.obter(CLI_A["cpf_cnpj"]) | {"fiscal": {"usar_geral": True}})
    assert fiscal.do_tomador(clientes.obter(CLI_A["cpf_cnpj"]))["origem"] == "geral"


def test_mei_sem_campos_de_iss_e_federais(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "mei"}})
    raiz, v = _dps(CLI_A["cpf_cnpj"])
    assert v(".//n:opSimpNac") == "2" and v(".//n:regEspTrib") == "0"
    assert raiz.find(".//n:pAliq", NS) is None and raiz.find(".//n:tribFed", NS) is None
    assert v(".//n:indTotTrib") == "0" and raiz.find(".//n:IBSCBS", NS) is None      # MEI: IBS/CBS só em 2027


def test_simples_com_retencao_de_pis_cofins_e_recusado_no_nacional(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "simples", "ret_pis_pct": "0.65", "ret_cofins_pct": "3"}})
    d = lote.montar_rps(CLI_A["cpf_cnpj"], "10000")
    d.pop("_alertas_fiscais")
    try:
        nacional.gerar_dps(emissor.rps_de_dict(d), emissor.prestador_do_ambiente(), False, "900", "1")
        assert False, "deveria recusar"
    except ValueError as ex:
        assert "Lei 10.833" in str(ex)


def test_pessoa_fisica_e_consumo_final_e_regime_no_municipal(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "real", "ibscbs": "sempre"}})
    clientes.salvar({"cpf_cnpj": "52998224725", "razao_social": "FULANO DE TAL", "endereco": CLI_A["endereco"]})
    raiz, v = _dps("52998224725")
    assert v(".//n:indFinal") == "1" and v(".//n:pAliqPis") == "1.65" and v(".//n:pAliqCofins") == "7.60"
    assert emissor.prestador_do_ambiente().optante_simples is False
    config.salvar({"fiscal": {"regime": "simples"}})
    assert emissor.prestador_do_ambiente().optante_simples is True
    assert Decimal(lote.montar_rps("52998224725", "100")["aliquota_iss"]) >= 0
