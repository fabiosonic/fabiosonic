"""Leitor de XML: reconstrói a regra geral da empresa e a regra de cada tomador a partir das notas emitidas."""

import xml.etree.ElementTree as ET

from nfse_itaborai import clientes, config, emissor, fiscal, leitura_fiscal, lote, nacional
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)


def _xml(doc, valor="10000"):
    d = lote.montar_rps(doc, valor)
    d.pop("_alertas_fiscais")
    return nacional.gerar_dps(emissor.rps_de_dict(d), emissor.prestador_do_ambiente(), False, "900", "1")


def test_reconstroi_regime_e_regra_dos_tomadores(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido", "ibscbs": "sempre"}, "emissao": {"reg_esp_trib": "0"}})
    a = clientes.obter(CLI_A["cpf_cnpj"])
    clientes.salvar(a | {"fiscal": {"usar_geral": False, "iss_retido": True, "ret_irrf_pct": "1.5", "ret_pis_pct": "0.65",
                                    "ret_cofins_pct": "3", "ret_csll_pct": "1", "tp_ente_gov": "4", "tp_oper": "1"}})
    notas = [leitura_fiscal.fatos(ET.fromstring(_xml(CLI_A["cpf_cnpj"]))),
             leitura_fiscal.fatos(ET.fromstring(_xml(CLI_B["cpf_cnpj"]))),
             leitura_fiscal.fatos(ET.fromstring(_xml(CLI_B["cpf_cnpj"], "500")))]
    t = notas[0]["tomador"]
    assert t["iss_retido"] and t["ret_irrf_pct"] == "1.5" and t["ret_csll_pct"] == "1"
    assert (t["ret_pis_pct"], t["ret_cofins_pct"]) == ("0.65", "3") and t["tp_ente_gov"] == "4"
    assert notas[0]["geral"]["regime"] == "presumido" and notas[0]["geral"]["tem_ibscbs"] == "1"
    # instalação "nova": regra geral vazia e tomadores sem regra
    cfg = config.carregar()
    cfg["fiscal"] = {**config.PADRAO["fiscal"]}
    cfg["emissao"]["op_simp_nac"] = "3"
    config._arquivo().write_text(__import__("json").dumps(cfg), encoding="utf-8")
    for doc in (CLI_A["cpf_cnpj"], CLI_B["cpf_cnpj"]):
        c = clientes.obter(doc)
        c.pop("fiscal", None)
        lst = [x for x in clientes.listar() if x["cpf_cnpj"] != doc] + [c]
        clientes._gravar(lst)
    aplicados = leitura_fiscal.aplicar_geral(notas)
    assert "regime" in aplicados and fiscal.geral()["regime"] == "presumido"
    assert config.carregar()["emissao"]["op_simp_nac"] == "1"
    assert leitura_fiscal.aplicar_geral(notas) == []                 # só uma vez: depois o usuário manda
    assert leitura_fiscal.aplicar_tomadores(notas) == 1               # só o tomador diferente da regra geral
    ra = clientes.obter(CLI_A["cpf_cnpj"])["fiscal"]
    assert ra["usar_geral"] is False and ra["iss_retido"] is True and ra["ret_irrf_pct"] == "1.5"
    assert ra["ret_pis_pct"] == "0.65" and ra["tp_ente_gov"] == "4" and ra["tp_oper"] == "1"
    assert "fiscal" not in clientes.obter(CLI_B["cpf_cnpj"])          # segue a regra geral
    # regra já gravada pelo usuário não é sobrescrita
    assert leitura_fiscal.aplicar_tomadores(notas) == 0


def test_xml_municipal_de_itaborai(base):  # noqa: F811
    xml = f"""<RetornoNfse><Nfse><NumeroNFSe>10</NumeroNFSe><DataEmissaoNFSe>2026-09-10T10:00:00</DataEmissaoNFSe>
      <PrestadorServico><Cnpj>24875410000144</Cnpj><OptanteSimplesNacional>1</OptanteSimplesNacional></PrestadorServico>
      <TomadorServico><CpfCnpj>{CLI_A["cpf_cnpj"]}</CpfCnpj><RazaoSocial>X</RazaoSocial></TomadorServico>
      <ValorTotalDosServicos>2000.00</ValorTotalDosServicos><IssRetido>1</IssRetido><Aliquota>2.01</Aliquota>
      <ValorIR>0.00</ValorIR><ValorINSS>220.00</ValorINSS></Nfse></RetornoNfse>"""
    f = leitura_fiscal.fatos(ET.fromstring(xml))
    assert f["geral"]["regime"] == "simples" and f["doc"] == CLI_A["cpf_cnpj"]
    assert f["tomador"]["iss_retido"] and f["tomador"]["aliquota_iss_retido"] == "2.01"
    assert f["tomador"]["ret_inss_pct"] == "11" and f["tomador"]["ret_irrf_pct"] == ""
