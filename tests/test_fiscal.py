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


def _dps_extras(doc, extras, valor="10000"):
    d = lote.montar_rps(doc, valor, extras=extras)
    d.pop("_alertas_fiscais")
    xml = nacional.gerar_dps(emissor.rps_de_dict(d), emissor.prestador_do_ambiente(), False, "900", "1")
    nacional.validar_xsd(xml, "DPS_v1.01.xsd")
    raiz = etree.fromstring(xml.encode())
    return raiz, lambda p: raiz.findtext(p, namespaces=NS)


def test_todos_os_grupos_da_nota_validam_no_xsd(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido", "ibscbs": "sempre", "tot_trib_modo": "percentual",
                              "p_tot_fed": "13,45", "p_tot_mun": "2", "cst_reg": "000", "class_trib_reg": "000001",
                              "p_dif_uf": "0", "p_dif_mun": "0", "p_dif_cbs": "10"}})
    extras = {"local_prestacao": "3304557", "c_trib_mun": "001", "desc_incond": "100", "desc_cond": "50", "ded_pct": "10",
              "obra_cno": "123456789012", "obra_insc_imob": "IPTU-55", "evento_nome": "Feira Contábil",
              "evento_ini": "2026-10-01", "evento_fim": "2026-10-03", "evento_cep": "24800000",
              "evento_lgr": "RUA A", "evento_bairro": "Centro", "pedido": "PC-2026-15", "doc_tec": "ART 123",
              "doc_ref": "Contrato 10/2026", "imovel_cib": "ABCD1234", "ree_valor": "200", "ree_tipo": "99",
              "ree_ndoc": "REC-9", "ree_xdoc": "Recibo de taxa", "ree_fornec_doc": CLI_B["cpf_cnpj"],
              "ree_fornec_nome": "FORNECEDOR", "ree_dt_emi": "2026-09-30",
              "ref_nfse": "33019002248754100001440000000000001260900000000011",
              "interm_doc": "11222333000181", "interm_nome": "INTERMEDIARIO LTDA"}
    raiz, v = _dps_extras(CLI_A["cpf_cnpj"], extras)
    assert v(".//n:cLocPrestacao") == "3304557" and v(".//n:cTribMun") == "001"
    assert v(".//n:obra/n:cObra") == "123456789012" and v(".//n:atvEvento/n:xNome") == "Feira Contábil"
    assert v(".//n:infoCompl/n:xPed") == "PC-2026-15" and v(".//n:idDocTec") == "ART 123"
    assert v(".//n:vDescIncond") == "100.00" and v(".//n:vDescCond") == "50.00" and v(".//n:pDR") == "10.00"
    assert v(".//n:pTotTribFed") == "13.45" and v(".//n:interm/n:CNPJ") == "11222333000181"
    assert v(".//n:imovel/n:cCIB") == "ABCD1234" and v(".//n:gReeRepRes//n:vlrReeRepRes") == "200.00"
    assert v(".//n:gTribRegular/n:cClassTribReg") == "000001" and v(".//n:gDif/n:pDifCBS") == "10.00"


def test_regra_do_tomador_imune_suspensa_beneficio_e_destinatario(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "real", "ibscbs": "sempre"}})
    c = clientes.obter(CLI_A["cpf_cnpj"])
    tratar("cliente/salvar", c | {"fiscal": {"usar_geral": False, "trib_issqn": "2", "tp_imunidade": "3",
                                             "pis_cofins_cst": "07", "tp_ente_gov": "4", "tp_oper": "1",
                                             "dest_doc": CLI_B["cpf_cnpj"], "dest_nome": "FILIAL DESTINO"}})
    raiz, v = _dps(CLI_A["cpf_cnpj"])
    assert v(".//n:tribISSQN") == "2" and v(".//n:tpImunidade") == "3" and v(".//n:tpRetISSQN") == "1"
    assert v(".//n:piscofins/n:CST") == "07" and raiz.find(".//n:vPis", NS) is None
    assert v(".//n:tpEnteGov") == "4" and v(".//n:tpOper") == "1" and v(".//n:indDest") == "1"
    assert v(".//n:dest/n:CNPJ") == CLI_B["cpf_cnpj"]
    tratar("cliente/salvar", c | {"fiscal": {"usar_geral": False, "exig_susp_tp": "1", "exig_susp_proc": "1" * 30,
                                             "n_bm": "12345678901234", "p_red_bm": "20", "trib_issqn": "3",
                                             "pais_result": "us"}})
    raiz, v = _dps(CLI_A["cpf_cnpj"])
    assert v(".//n:tribISSQN") == "3" and v(".//n:cPaisResult") == "US"
    assert v(".//n:exigSusp/n:tpSusp") == "1" and v(".//n:BM/n:nBM") == "12345678901234"
    import pytest
    with pytest.raises(ValueError, match="30 dígitos"):
        fiscal.normalizar_tomador({"usar_geral": False, "exig_susp_tp": "1", "exig_susp_proc": "123"})


def test_campos_da_nota_ficam_no_titulo_e_vao_na_emissao(base):  # noqa: F811
    r = tratar("emitir", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "cobrar": False,
                          "extras": {"pedido": "PED-77", "desc_incond": "10"}})
    assert r["sucesso"], r
    from nfse_itaborai import financeiro
    import json
    assert json.loads(financeiro.obter_titulo(r["titulo_id"])["extras"])["pedido"] == "PED-77"
    import pytest
    with pytest.raises(ValueError, match="CIB"):
        fiscal.normalizar_nota({"obra_cib": "123"})
