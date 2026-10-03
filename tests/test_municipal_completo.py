"""Webservice de Itaboraí: todos os grupos do leiaute (IBS/CBS com imóvel, evento, tipo de tributação, recolhimento)."""

import xml.etree.ElementTree as ET

from nfse_itaborai import config, emissor, lote
from nfse_itaborai.xml_rps import gerar_envio
from nfse_itaborai.xsd import validar_xsd
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _envio(extras=None, fiscal_tomador=None):
    from nfse_itaborai import clientes
    if fiscal_tomador:
        clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"fiscal": fiscal_tomador})
    d = lote.montar_rps(CLI_A["cpf_cnpj"], "1000", extras=extras)
    d.pop("_alertas_fiscais")
    rps = emissor.rps_de_dict(d)
    rps.numero = "77"
    xml = gerar_envio(emissor.prestador_do_ambiente(), [rps], lote="1", producao=False)
    validar_xsd(xml)
    return ET.fromstring(xml.split("?>", 1)[1])


def test_evento_imovel_recolhimento_e_incentivo(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido", "incentivo_fiscal": "sim"}})
    r = _envio({"evento_nome": "Feira", "evento_ini": "2026-10-01", "evento_fim": "2026-10-02", "evento_cep": "24800000",
                "evento_tipo_lgr": "RUA", "evento_lgr": "DAS FLORES", "evento_nro": "10", "evento_bairro": "Centro",
                "imovel_cep": "24800000", "imovel_lgr": "RUA A", "imovel_nro": "5", "imovel_bairro": "Centro",
                "imovel_cmun": "3301900", "imovel_uf": "rj", "local_prestacao": "3304557", "local_recolhimento": "3304557",
                "c_trib_mun": "171901001"})
    v = lambda p: r.findtext(p)  # noqa: E731
    assert v(".//Evento/NomeEvento") == "Feira" and v(".//EnderecoEvento/Logradouro") == "DAS FLORES"
    assert v(".//ImovelIBSCBS/Cep") == "24800000" and v(".//ImovelIBSCBS/Uf") == "RJ"
    assert v(".//LocalDaPrestacao") == "3304557" and v(".//LocalDoRecolhimento") == "3304557"
    assert v(".//TipoDeTributacao") == "1" and v(".//CodigoTributacaoMunicipio") == "171901001"
    assert v(".//IncentivoFiscalImunidade") == "1" and v(".//OptanteSimplesNacional") == "2"


def test_tipo_de_tributacao_pela_regra(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido"}})
    assert _envio().findtext(".//TipoDeTributacao") == "0"
    assert _envio(fiscal_tomador={"usar_geral": False, "trib_issqn": "2", "tp_imunidade": "1"}).findtext(".//TipoDeTributacao") == "2"
    assert _envio(fiscal_tomador={"usar_geral": False, "exig_susp_tp": "1", "exig_susp_proc": "1" * 30}).findtext(".//TipoDeTributacao") == "3"
    config.salvar({"fiscal": {"regime": "simples"}})
    assert _envio(fiscal_tomador={"usar_geral": True}).findtext(".//TipoDeTributacao") == "4"
