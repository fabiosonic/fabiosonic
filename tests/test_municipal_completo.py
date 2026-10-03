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
    # 17.19 prestado fora sem retenção: ISS devido no estabelecimento do prestador (LC 116, art. 3º; manual 2026)
    assert v(".//LocalDaPrestacao") == "3304557" and v(".//LocalDoRecolhimento") == "3301900"
    assert v(".//TipoDeTributacao") == "0" and not v(".//CodigoTributacaoMunicipio")
    assert v(".//IncentivoFiscalImunidade") == "1" and v(".//OptanteSimplesNacional") == "2"


def test_tipo_de_tributacao_pela_regra(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido"}})
    assert _envio().findtext(".//TipoDeTributacao") == "0"
    assert _envio(fiscal_tomador={"usar_geral": False, "trib_issqn": "2", "tp_imunidade": "1"}).findtext(".//TipoDeTributacao") == "2"
    assert _envio(fiscal_tomador={"usar_geral": False, "exig_susp_tp": "1", "exig_susp_proc": "1" * 30}).findtext(".//TipoDeTributacao") == "3"
    config.salvar({"fiscal": {"regime": "simples"}})
    assert _envio(fiscal_tomador={"usar_geral": True}).findtext(".//TipoDeTributacao") == "4"


# ---- Manual do webservice (versão 2026, XML a partir de 28/09/2026) ----
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402

from nfse_itaborai import itaborai_regras as ir  # noqa: E402
from nfse_itaborai.validacao import ErroValidacao  # noqa: E402

PREFEITURA = "28741080000155"


@pytest.mark.parametrize("regime,retido,rec,tomador,esperado", [
    ("mei", False, "", "", ("2", False)),                      # MEI: Isento/Imune em qualquer item
    ("mei", True, "", PREFEITURA, ("2", False)),
    ("simples", False, "", "", ("4", False)),
    ("simples", True, "", "", ("5", True)),                    # retido pelo tomador em Itaboraí
    ("simples", True, "3304557", "", ("1", True)),             # retido fora
    ("simples", False, "", PREFEITURA, ("5", True)),           # Prefeitura retém sempre
    ("presumido", False, "", "", ("0", False)),
    ("presumido", True, "", "", ("5", True)),
    ("real", False, "", "00360305081198", ("5", True)),        # Caixa
    ("presumido", False, "", ir.PETROBRAS, ("0", False)),      # Petrobras: regra normal, o webservice ajusta
])
def test_tipo_de_tributacao_do_manual(regime, retido, rec, tomador, esperado):
    assert ir.tipo_tributacao(regime, "17.19", retido, "", rec, tomador)[:2] == esperado


def test_item_devido_no_local_da_prestacao():
    assert ir.tipo_tributacao("presumido", "07.02", False, "3304557", "", "") == ("1", False, "3304557")
    assert ir.tipo_tributacao("presumido", "17.19", False, "3304557", "", "")[0] == "0"
    assert ir.tipo_tributacao("simples", "17.19", False, "", "", "", imune=True)[0] == "2"
    assert ir.tipo_tributacao("presumido", "17.19", False, "", "", "", suspensa=True)[0] == "3"


def test_prefeitura_forca_retencao_no_xml(base):  # noqa: F811
    from nfse_itaborai import clientes
    config.salvar({"fiscal": {"regime": "presumido"}})
    clientes.salvar(clientes.obter(CLI_A["cpf_cnpj"]) | {"cpf_cnpj": PREFEITURA, "razao_social": "PREFEITURA"})
    d = lote.montar_rps(PREFEITURA, "1000")
    assert d["tipo_tributacao"] == "5" and d["iss_retido"] == "1" and d["responsavel_recolhimento"] == "1"
    assert any("obrigado a reter" in a for a in d["_alertas_fiscais"])


def test_mei_sem_aliquota(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "mei"}})
    r = _envio()
    assert r.findtext(".//TipoDeTributacao") == "2" and r.findtext(".//Aliquota") == "0.00"
    assert r.findtext(".//OptanteSimplesNacional") == "1"


def test_simples_1719_sem_destaque_do_iss(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "simples"}})
    r = _envio()
    assert r.findtext(".//ItemListaServico") == "17.19" and r.findtext(".//TipoDeTributacao") == "4"
    assert r.findtext(".//Aliquota") == "0.00" and r.findtext(".//ValorIss") == "0.00"


def test_incentivo_imunidade_3(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido", "incentivo_fiscal": "imune"}})
    assert _envio().findtext(".//IncentivoFiscalImunidade") == "3"


def _rps(**kw):
    d = lote.montar_rps(CLI_A["cpf_cnpj"], "1000", extras=kw.pop("extras", None))
    d.pop("_alertas_fiscais")
    rps = emissor.rps_de_dict(d)
    for k, v in kw.items():
        setattr(rps, k, v)
    return rps


def test_validacoes_do_manual(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "simples"}})
    rps = _rps(item_lista_servico="17.01", codigo_desdobro="170101", aliquota_iss=Decimal(0))
    assert any("alíquota EFETIVA" in e for e in ir.validar(rps, "simples"))
    rps = _rps(valor_deducoes=Decimal(500))
    erros = ir.validar(rps, "simples")
    assert any("Código da Obra" in e for e in erros) and any("40%" in e for e in erros)
    rps = _rps(indicador_operacao="020101", codigo_desdobro="070301", item_lista_servico="07.03")
    assert any("imóvel" in e for e in ir.validar(rps, "simples"))
    rps = _rps(indicador_operacao="020101", codigo_desdobro="070201", item_lista_servico="07.02")
    assert not any("imóvel" in e for e in ir.validar(rps, "simples"))
    rps = _rps(codigo_desdobro="120101", item_lista_servico="12.01", aliquota_iss=Decimal(3))
    assert any("evento" in e for e in ir.validar(rps, "simples"))
    rps = _rps()
    rps.tomador.endereco.bairro = ""
    assert any("bairro" in e for e in ir.validar(rps, "simples"))


def test_emissao_recusa_localmente(base):  # noqa: F811
    config.salvar({"fiscal": {"regime": "presumido"}})
    rps = _rps(aliquota_iss=Decimal(0))
    with pytest.raises(ErroValidacao) as ex:
        emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
    assert any("Tabela de Atividades" in e for e in ex.value.erros)
