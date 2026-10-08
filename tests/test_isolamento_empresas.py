"""Dados de uma empresa nunca aparecem nem são gravados em outra (janelas, XML, extratos, serviço, migração)."""

import pytest

from nfse_itaborai import clientes, config, emissor, empresas, importacao, servicos, tela
from test_empresas import OFX, multi  # noqa: F401  (fixture)

NOTA = """<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe><nNFSe>77</nNFSe>{emit}<DPS><infDPS>
<dhEmi>2026-09-10T10:00:00-03:00</dhEmi><dCompet>2026-09-10</dCompet>{prest}
<toma><CNPJ>00482301000107</CNPJ><xNome>MERCADINHO GIRASSOL</xNome></toma>
<serv><cServ><xDescServ>servicos</xDescServ></cServ></serv><valores><vServPrest><vServ>802.98</vServ></vServPrest></valores>
</infDPS></DPS></infNFSe></NFSe>"""


def _segunda():
    return empresas.criar({"nome": "JAQUELINE MEI", "cnpj": "58.416.516/0001-00", "chave": "k2", "canal": "nacional"})


def test_janela_de_outra_empresa_e_recusada_e_pedido_fica_preso_a_empresa(multi):  # noqa: F811
    principal = empresas.listar()[0]["id"]
    _segunda()                                           # a 2ª passa a ser a empresa em uso
    r = tela._Handler._na_empresa(None, principal, "clientes", lambda: clientes.listar())
    assert r["empresa_trocada"] and "recarregada" in r["erro"]
    # pedido da janela certa: roda na pasta da empresa em uso, mesmo se outra janela trocar no meio
    def troca_no_meio():
        empresas.ativar(principal)
        return emissor.raiz()
    assert tela._Handler._na_empresa(None, "58416516000100", "x", troca_no_meio) == multi / "empresas" / "58416516000100"
    assert emissor.raiz() == multi                       # a troca valeu para os pedidos seguintes


def test_xml_sem_emissor_ou_de_outra_empresa_nao_entra(multi, tmp_path):  # noqa: F811
    pasta = tmp_path / "xmls"
    pasta.mkdir()
    (pasta / "sem_emissor.xml").write_text(NOTA.format(emit="", prest=""), encoding="utf-8")
    (pasta / "da_moraes.xml").write_text(NOTA.format(emit="<emit><CNPJ>24875410000144</CNPJ></emit>",
                                                     prest="<prest><CNPJ>24875410000144</CNPJ></prest>"), encoding="utf-8")
    _segunda()
    r = clientes.importar_xmls(pasta, "58416516000100")
    assert r["clientes_novos"] == 0 and clientes.listar() == []
    (pasta / "da_jaqueline.xml").write_text(NOTA.format(emit="<emit><CNPJ>58416516000100</CNPJ></emit>",
                                                        prest="<prest><CNPJ>58416516000100</CNPJ></prest>"), encoding="utf-8")
    assert clientes.importar_xmls(pasta, "58416516000100")["clientes_novos"] == 1
    with pytest.raises(ValueError, match="CNPJ"):
        clientes.importar_xmls(pasta, "")


def test_extrato_da_conta_de_outra_empresa_e_sem_conta_nao_vao_para_a_outra(multi):  # noqa: F811
    assert importacao.conta_da_empresa(OFX.format(conta="111", fit="1"))      # 1ª conta vincula à principal
    _segunda()
    assert not importacao.conta_da_empresa(OFX.format(conta="111", fit="2"))  # conta da Moraes: nunca na 2ª
    sem_conta = OFX.replace("<BANKID>077<BRANCHID>0001<ACCTID>{conta}", "").format(fit="3")
    assert not importacao.conta_da_empresa(sem_conta)                         # robô não adivinha a empresa
    assert importacao.conta_da_empresa(OFX.format(conta="222", fit="4"))      # conta nova: fica com a 2ª
    assert config.carregar()["financeiro"]["contas_bancarias"] == ["077-0001-222"]


def test_nova_empresa_nao_herda_o_servico_da_primeira(multi):  # noqa: F811
    servicos.salvar({**servicos.padrao(), "descricao": "HONORARIOS DA MORAES", "padrao": True})
    _segunda()
    assert all("MORAES" not in (s.get("descricao") or "") for s in servicos.listar())
    assert "MORAES" not in (multi / "empresas" / "58416516000100" / "servico_padrao.json").read_text(encoding="utf-8")


def test_telas_de_versao_anterior_nao_mexem_na_primeira_estando_na_segunda(multi):  # noqa: F811
    _segunda()
    r = tela.tratar("migracao/dados_anteriores", {})
    assert r["sucesso"] is False and "principal" in r["erro"]
    assert tela.tratar("migracao/misturas", {}) == [] and tela.tratar("migracao/identidade", {}) is None


def test_lista_de_empresas_usa_o_cnpj_do_env_e_nao_deixa_duplicar(multi):  # noqa: F811
    _segunda()
    (multi / ".env").write_text("ITABORAI_CNPJ=24875410000144\n", encoding="utf-8")
    reg = empresas._ler()
    reg["empresas"][0]["cnpj"] = ""                      # registro antigo sem o CNPJ da principal
    empresas._gravar(reg)
    assert empresas.listar()[0]["cnpj"] == "24875410000144"
    with pytest.raises(ValueError, match="já está cadastrada"):
        empresas.criar({"nome": "COPIA", "cnpj": "24.875.410/0001-44"})


def test_cliente_excluido_nao_volta_pelo_xml_so_pelo_cadastro(multi, tmp_path):  # noqa: F811
    pasta = tmp_path / "x"
    pasta.mkdir()
    (pasta / "n.xml").write_text(NOTA.format(emit="<emit><CNPJ>24875410000144</CNPJ></emit>",
                                             prest="<prest><CNPJ>24875410000144</CNPJ></prest>"), encoding="utf-8")
    assert clientes.importar_xmls(pasta, "24875410000144")["clientes_novos"] == 1
    clientes.excluir("00482301000107")
    assert clientes.importar_xmls(pasta, "24875410000144")["clientes_novos"] == 0 and not clientes.obter("00482301000107")
    clientes.salvar({"cpf_cnpj": "00482301000107", "razao_social": "MERCADINHO GIRASSOL"})
    clientes.excluir("00482301000107")
    clientes.salvar({"cpf_cnpj": "00482301000107", "razao_social": "MERCADINHO GIRASSOL"})
    assert "00482301000107" not in clientes.excluidos()
