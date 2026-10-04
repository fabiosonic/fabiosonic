"""Importação de clientes e padrões da NFS-e pela pasta IMPORTAR XML (dentro do sistema), por empresa."""

import zipfile
from pathlib import Path

import pytest

from nfse_itaborai import automacao, clientes, config, emissor, empresas, importacao, importador, lote
from nfse_itaborai.tela import tratar
from test_empresas import multi  # noqa: F401  (fixture)

MUNICIPAL = (Path(__file__).parent / "dados" / "retorno_nfse_real.xml").read_text(encoding="utf-8")


def nacional(prest: str, toma: str, nome: str, n: int, desc="HONORARIOS CONTABEIS MENSAIS", ctrib="171901") -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?><NFSe xmlns="http://www.sped.fazenda.gov.br/nfse" versao="1.01">
<infNFSe><nNFSe>{n}</nNFSe><emit><CNPJ>{prest}</CNPJ><xNome>EMPRESA {prest[:4]}</xNome></emit><DPS versao="1.01"><infDPS>
<dhEmi>2026-09-{10 + n % 9:02d}T10:00:00-03:00</dhEmi><prest><CNPJ>{prest}</CNPJ><regTrib><opSimpNac>3</opSimpNac></regTrib></prest>
<toma><CNPJ>{toma}</CNPJ><xNome>{nome}</xNome><end><endNac><cMun>3304557</cMun><CEP>20071904</CEP></endNac>
<xLgr>AV PRESIDENTE VARGAS</xLgr><nro>435</nro><xBairro>Centro</xBairro></end></toma>
<serv><cServ><cTribNac>{ctrib}</cTribNac><xDescServ>{desc}</xDescServ><cNBS>113022100</cNBS></cServ></serv>
<valores><vServPrest><vServ>374.40</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun></trib></valores>
<IBSCBS><cIndOp>100301</cIndOp><valores><trib><gIBSCBS><CST>200</CST><cClassTrib>200052</cClassTrib></gIBSCBS></trib></valores></IBSCBS>
</infDPS></DPS></infNFSe></NFSe>"""


MORAES, PADARIA = "24875410000144", "11222333000181"


@pytest.fixture
def caixa(multi):  # noqa: F811
    c = importador.caixa()
    assert c == multi / "IMPORTAR XML"
    (c / "a.xml").write_text(nacional(MORAES, "33000167000101", "RPS CONSULTORIA", 1), encoding="utf-8")
    (c / "b.xml").write_text(nacional(MORAES, "54399432000146", "ESPACO CULTIVAR", 2), encoding="utf-8")
    (c / "municipal.xml").write_text(MUNICIPAL, encoding="utf-8")                       # Moraes, tomador 11222333000181
    with zipfile.ZipFile(c / "padaria.zip", "w") as z:
        z.writestr("set/p1.xml", nacional(PADARIA, "07526557000100", "MERCADO X", 3, "VENDA DE PAES", "010701"))
    (c / "outra.xml").write_text(nacional("45309710000136", "07526557000100", "Y", 4), encoding="utf-8")
    (c / "lixo.xml").write_text("<nao-e-nota/>", encoding="utf-8")
    return c


def test_analisa_por_prestador_com_padroes(caixa, multi):  # noqa: F811
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA})
    a = tratar("importador/analisar", {})
    assert a["zips_descompactados"] == 1 and a["invalidos"] == 1
    assert (caixa / "importados" / "_zips" / "padaria.zip").exists()
    g = {x["cnpj"]: x for x in a["grupos"]}
    assert g[MORAES]["notas"] == 3 and g[MORAES]["clientes"] == 3 and g[MORAES]["empresa_id"] == MORAES
    assert g[MORAES]["clientes_novos"] == 3                                    # o cliente da fixture é outro
    p = g[MORAES]["padroes"]
    assert p["codigo_desdobro"] == "171901" and p["item_lista_servico"] == "17.19" and p["codigo_nbs"] == "113022100"
    assert p["descricao"] == "HONORARIOS CONTABEIS MENSAIS" and p["classificacao_tributaria"] == "200052"
    assert g[PADARIA]["empresa_id"] == PADARIA and g[PADARIA]["padroes"]["item_lista_servico"] == "01.07"
    assert g["45309710000136"]["empresa_id"] == ""                             # prestador não cadastrado


def test_importa_so_para_a_empresa_emissora(caixa, multi):  # noqa: F811
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA})
    tratar("importador/analisar", {})
    erro = tratar("importador/importar", {"empresa_id": MORAES, "cnpj": PADARIA})["erro"]
    assert "não podem ser cadastrados em outra" in erro
    r = tratar("importador/importar", {"empresa_id": PADARIA, "cnpj": PADARIA,
                                       "servico": {"descricao": "VENDA DE PAES", "item_lista_servico": "01.07",
                                                   "codigo_desdobro": "010701"}})
    assert r["xml"] == 1 and r["clientes_novos"] == 1 and r["padrao_salvo"]
    assert [c["razao_social"] for c in clientes.listar()] == ["MERCADO X"]       # empresa ativa: padaria
    assert lote.servico_padrao()["descricao"] == "VENDA DE PAES"
    assert config.carregar()["pastas"]["xml_nfse"] == str(caixa / "importados" / PADARIA)
    assert (caixa / "importados" / PADARIA / "p1.xml").exists() and not (caixa / "padaria").exists()
    # Moraes: os clientes dela continuam só nela, e o serviço padrão dela não mudou
    empresas.ativar(MORAES)
    r = tratar("importador/importar", {"empresa_id": MORAES, "cnpj": MORAES})
    assert r["xml"] == 3 and r["clientes_novos"] == 3 and not r["padrao_salvo"]
    nomes = {c["razao_social"] for c in clientes.listar()}
    assert "MERCADO X" not in nomes and "RPS CONSULTORIA" in nomes
    assert lote.servico_padrao()["descricao"] == "HONORARIOS CONTABEIS MENSAIS"
    # sobram na caixa só o lixo e a nota do prestador não cadastrado
    assert sorted(p.name for p in importador._pendentes()) == ["lixo.xml", "outra.xml"]


def test_robo_importa_sozinho_as_notas_da_empresa(caixa, multi):  # noqa: F811
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA})
    importador.analisar()                                                       # descompacta o ZIP
    r = automacao.rodar_todas(forcar=True)
    assert r["MORAES & OLIVEIRA CONTABILIDADE"]["caixa_xml"]["xml"] == 3
    assert r["PADARIA BOM PAO LTDA"]["caixa_xml"]["xml"] == 1
    with emissor.usar_empresa(multi):
        assert {c["razao_social"] for c in clientes.listar()} >= {"RPS CONSULTORIA", "ESPACO CULTIVAR"}
        assert importacao.importar_xml()["notas_lidas"] == 3                    # robô lê a pasta da empresa
    assert [c["razao_social"] for c in clientes.listar()] == ["MERCADO X"]


def test_config_antiga_com_downloads_passa_para_a_pasta_do_sistema(tmp_path, monkeypatch):
    import json
    monkeypatch.setattr(emissor, "RAIZ", tmp_path)
    (tmp_path / "dados").mkdir()
    (tmp_path / "dados" / "config.json").write_text(json.dumps(
        {"pastas": {"xml_nfse": "~/Downloads/nfse/MORAES OLIVEIRA CONTABILIDADE LTDA"}}), encoding="utf-8")
    assert config.carregar()["pastas"]["xml_nfse"] == ""


def test_importacao_completa_o_cadastro_da_empresa(multi):  # noqa: F811
    """Instalação nova: o nome, a inscrição municipal, o município e a numeração da DPS vêm das notas já emitidas.
    Só preenche o que está vazio e só avança a numeração."""
    import json
    from nfse_itaborai import nacional as nac
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": PADARIA, "canal": "nacional"})
    pasta = multi / "empresas" / PADARIA
    cfg = json.loads((pasta / "dados" / "config.json").read_text(encoding="utf-8"))
    cfg["empresa"]["nome"] = cfg["empresa"]["assinatura"] = ""
    cfg["emissao"].pop("municipio_emissor")                        # como numa instalação nova ainda sem município
    (pasta / "dados" / "config.json").write_text(json.dumps(cfg), encoding="utf-8")
    c = importador.caixa()
    for n in (57, 58):
        x = nacional(PADARIA, "07526557000100", "MERCADO X", n, "VENDA DE PAES", "010701")
        x = x.replace(f"<xNome>EMPRESA {PADARIA[:4]}</xNome>", "<xNome>PADARIA BOM PAO LTDA</xNome><IM>4455667</IM>")
        x = x.replace("<dhEmi>", f"<nDPS>{n}</nDPS><serie>900</serie><cLocEmi>3303302</cLocEmi><dhEmi>")
        (c / f"p{n}.xml").write_text(x, encoding="utf-8")
    r = tratar("importador/importar", {"empresa_id": PADARIA, "cnpj": PADARIA})
    feito = " | ".join(r["empresa_completada"])
    assert "nome da empresa: PADARIA BOM PAO LTDA" in feito and "inscrição municipal: 4455667" in feito
    assert "município emissor (IBGE): 3303302" in feito and "próximo número da DPS: 59" in feito
    with emissor.usar_empresa(pasta):
        cfg = config.carregar()
        assert cfg["empresa"]["nome"] == cfg["empresa"]["assinatura"] == "PADARIA BOM PAO LTDA"
        assert cfg["emissao"]["municipio_emissor"] == "3303302" and nac._proximo_dps() == 59
        assert emissor.env("ITABORAI_IM") == "4455667"
        # nada é sobrescrito nem volta: nome trocado e numeração à frente continuam
        config.salvar({"empresa": {"nome": "PADARIA NOVA"}, "emissao": {"proximo_dps": 100}})
        assert importador.completar_empresa(importador.arquivo_da_empresa(PADARIA), PADARIA) == []
        assert config.carregar()["empresa"]["nome"] == "PADARIA NOVA" and nac._proximo_dps() == 100
