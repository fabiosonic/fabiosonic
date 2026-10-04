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


def _psicologia(prest: str, toma: str, n: int, nbs: bool = True) -> str:
    """Nota do Emissor Nacional como a de uma clínica de psicologia (dados fictícios)."""
    return f"""<?xml version="1.0" encoding="utf-8"?><NFSe versao="1.01" xmlns="http://www.sped.fazenda.gov.br/nfse">
<infNFSe><xTribNac>Psicologia.</xTribNac><nNFSe>{100 + n}</nNFSe><emit><CNPJ>{prest}</CNPJ><xNome>CLINICA EXEMPLO PSICOLOGIA LTDA</xNome>
<enderNac><cMun>3304557</cMun><UF>RJ</UF></enderNac></emit><DPS versao="1.01"><infDPS><serie>70000</serie><nDPS>{80 + n}</nDPS>
<dCompet>2026-09-01</dCompet><cLocEmi>3304557</cLocEmi><prest><CNPJ>{prest}</CNPJ><regTrib><opSimpNac>3</opSimpNac><regApTribSN>1</regApTribSN>
<regEspTrib>0</regEspTrib></regTrib></prest><toma><CPF>{toma}</CPF><xNome>PACIENTE {n}</xNome></toma><serv><locPrest><cLocPrestacao>3304557</cLocPrestacao></locPrest>
<cServ><cTribNac>041601</cTribNac><cTribMun>001</cTribMun><xDescServ>PRESTAÇÃO DE SERVIÇO</xDescServ>{"<cNBS>123019800</cNBS>" if nbs else ""}</cServ></serv>
<valores><vServPrest><vServ>640.00</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN><tpRetISSQN>1</tpRetISSQN></tribMun>
<tribFed><piscofins><CST>08</CST></piscofins></tribFed><totTrib><pTotTribSN>6.00</pTotTribSN></totTrib></trib></valores></infDPS></DPS></infNFSe></NFSe>"""


def test_importacao_cadastra_o_servico_completo_e_troca_o_modelo_de_fabrica(multi):  # noqa: F811
    """Caso real (clínica de psicologia, Emissor Nacional): o serviço da empresa vem completo das notas — item 04.16,
    desdobro 041601, NBS, código municipal, carga tributária e nome 'Psicologia' — uma nota sem NBS não cria serviço
    duplicado, e o modelo 'Contabilidade' de fábrica deixa de ser o padrão."""
    import re
    from nfse_itaborai import lote, nacional as nac, servicos
    empresas.criar({"nome": "CLINICA EXEMPLO PSICOLOGIA LTDA", "cnpj": PADARIA, "canal": "nacional", "municipio": "3304557"})
    pasta = multi / "empresas" / PADARIA
    c = importador.caixa()
    for n, cpf, nbs in ((1, "52998224725", True), (2, "11144477735", True), (3, "39053344705", False)):
        (c / f"n{n}.xml").write_text(_psicologia(PADARIA, cpf, n, nbs), encoding="utf-8")
    g = next(x for x in tratar("importador/analisar", {})["grupos"] if x["cnpj"] == PADARIA)
    assert len(g["servicos"]) == 1 and g["servicos"][0]["nome"] == "Psicologia" and g["servicos"][0]["notas"] == 3
    sv = [{"nome": s["nome"], "campos": s["campos"], "padrao": k == 0} for k, s in enumerate(g["servicos"])]
    r = tratar("importador/importar", {"empresa_id": PADARIA, "cnpj": PADARIA, "servicos": sv})
    assert r["clientes_novos"] == 3 and "aliquota_simples_pct" in r["regra_geral"]
    with emissor.usar_empresa(pasta):
        cat = servicos.listar()
        assert [(s["nome"], s["padrao"]) for s in cat] == [("Psicologia", True)]          # o modelo de fábrica saiu
        s = cat[0]
        assert (s["item_lista_servico"], s["codigo_desdobro"], s["codigo_nbs"], s["codigo_tributacao_municipio"],
                s["ibpt_percentual"]) == ("04.16", "041601", "123019800", "001", "6.00")
        xml = nac.gerar_dps(emissor.rps_de_dict(lote.montar_rps("52998224725", "640", "", "2026-10")),
                            emissor.prestador_do_ambiente(), False, "900", "84")
        campos = {t: re.search(rf"<{t}>([^<]*)</{t}>", xml).group(1) for t in ("cTribNac", "cTribMun", "cNBS", "pTotTribSN", "cLocEmi")}
        assert campos == {"cTribNac": "041601", "cTribMun": "001", "cNBS": "123019800", "pTotTribSN": "6.00", "cLocEmi": "3304557"}


def _presumido(prest: str, toma: str, n: int) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?><NFSe versao="1.01" xmlns="http://www.sped.fazenda.gov.br/nfse">
<infNFSe><xTribNac>Engenharia.</xTribNac><emit><CNPJ>{prest}</CNPJ><xNome>ENGENHARIA EXEMPLO LTDA</xNome><IM>778899</IM></emit><DPS versao="1.01"><infDPS>
<serie>1</serie><nDPS>{200 + n}</nDPS><cLocEmi>3303302</cLocEmi><prest><CNPJ>{prest}</CNPJ><regTrib><opSimpNac>1</opSimpNac><regEspTrib>0</regEspTrib></regTrib></prest>
<toma><CNPJ>{toma}</CNPJ><xNome>CONSTRUTORA {n}</xNome></toma><serv><cServ><cTribNac>070101</cTribNac><xDescServ>PROJETO DE ENGENHARIA</xDescServ>
<cNBS>114012100</cNBS></cServ></serv><valores><vServPrest><vServ>10000.00</vServ></vServPrest><trib><tribMun><tribISSQN>1</tribISSQN>
<pAliq>5.00</pAliq><tpRetISSQN>1</tpRetISSQN></tribMun><tribFed><piscofins><CST>01</CST><vBCPisCofins>10000.00</vBCPisCofins><pAliqPis>0.65</pAliqPis>
<pAliqCofins>3.00</pAliqCofins><vPis>65.00</vPis><vCofins>300.00</vCofins></piscofins></tribFed>
<totTrib><pTotTrib><pTotTribFed>13.33</pTotTribFed><pTotTribEst>0.00</pTotTribEst><pTotTribMun>5.00</pTotTribMun></pTotTrib></totTrib></trib></valores>
</infDPS></DPS></infNFSe></NFSe>"""


def test_importar_clientes_bat_lucro_presumido_completo(multi, capsys):  # noqa: F811
    """IMPORTAR_CLIENTES.bat (importação completa sem a tela) numa empresa do Lucro Presumido: regime, ISS 5%,
    PIS/COFINS, carga tributária por esfera, serviço, inscrição municipal e numeração."""
    from nfse_itaborai import __main__ as cli, servicos
    empresas.criar({"nome": "ENGENHARIA EXEMPLO LTDA", "cnpj": PADARIA, "canal": "nacional", "municipio": "3303302"})
    pasta = multi / "empresas" / PADARIA
    for n, toma in ((1, "33000167000101"), (2, "54399432000146")):
        (importador.caixa() / f"e{n}.xml").write_text(_presumido(PADARIA, toma, n), encoding="utf-8")
    assert cli.importar_clientes() == 0
    saida = capsys.readouterr().out
    assert "Serviço PADRÃO: Engenharia — item 07.01, desdobro 070101, NBS 114012100" in saida and "ISS 5.00%" in saida
    assert "regime tributário" in saida and "forma da carga tributária" in saida
    with emissor.usar_empresa(pasta):
        cfg = config.carregar()
        assert cfg["fiscal"]["regime"] == "presumido" and cfg["fiscal"]["tot_trib_modo"] == "percentual"
        assert (cfg["fiscal"]["p_tot_fed"], cfg["fiscal"]["p_tot_mun"]) == ("13.33", "5.00")
        s = servicos.padrao()
        assert (s["nome"], s["aliquota_iss"], s["ibpt_percentual"]) == ("Engenharia", "5.00", "18.33")
        assert emissor.env("ITABORAI_IM") == "778899" and len(clientes.listar()) == 2
