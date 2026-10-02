"""Multiempresa: cadastro, isolamento de dados/credenciais e robô processando todas as empresas."""

import threading

import pytest

from nfse_itaborai import automacao, clientes, config, emissor, empresas, financeiro, importacao, lote
from nfse_itaborai.tela import tratar

OFX = """<OFX><BANKACCTFROM><BANKID>077<BRANCHID>0001<ACCTID>{conta}</BANKACCTFROM><BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261001<TRNAMT>-50.00<FITID>{fit}<MEMO>TARIFA PACOTE</STMTTRN></BANKTRANLIST></OFX>"""


@pytest.fixture
def multi(tmp_path, monkeypatch):
    for k in ("ITABORAI_CNPJ", "ITABORAI_IM", "ITABORAI_CHAVE", "ITABORAI_AMBIENTE", "ITABORAI_CIENTE_IRREVERSIVEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(emissor, "BASE", tmp_path)
    monkeypatch.setattr(emissor, "RAIZ", emissor._Raiz(tmp_path))
    (tmp_path / ".env").write_text("ITABORAI_CNPJ=24875410000144\nITABORAI_IM=1034265\nITABORAI_CHAVE=abc\n", encoding="utf-8")
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}})
    clientes.salvar({"cpf_cnpj": "32396063000103", "razao_social": "CLIENTE DA MORAES"})
    return tmp_path


def test_empresa_original_vira_a_primeira_sem_mover_nada(multi):
    l = empresas.listar()
    assert len(l) == 1 and l[0]["pasta"] == "." and l[0]["cnpj"] == "24875410000144" and l[0]["ativa"]
    assert l[0]["nome"] == "MORAES & OLIVEIRA CONTABILIDADE"


def test_nova_empresa_isolada(multi):
    with pytest.raises(ValueError, match="CNPJ inválido"):
        empresas.criar({"nome": "X", "cnpj": "11.111.111/1111-11"})
    e = empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11.222.333/0001-81", "im": "555", "chave": "k2",
                        "canal": "nacional"})
    assert e["cnpj"] == "11222333000181" and emissor.raiz() == multi / "empresas" / "11222333000181"
    # credenciais, configurações, clientes e serviço padrão são da nova empresa
    assert emissor.env("ITABORAI_CNPJ") == "11222333000181" and emissor.env("ITABORAI_CHAVE") == "k2"
    assert not emissor.em_producao() and config.carregar()["emissao"]["canal"] == "nacional"
    assert clientes.listar() == [] and lote.servico_padrao()["item_lista_servico"] == "17.19"
    assert config.carregar()["pastas"]["extratos"].endswith("PADARIA BOM PAO LTDA")
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE DA PADARIA"})
    financeiro.criar_titulo("54399432000146", "100", vencimento="2026-10-10", emitir_nfse=False)
    with pytest.raises(ValueError, match="já está cadastrada"):
        empresas.criar({"nome": "DUPLICADA", "cnpj": "11222333000181"})
    # volta para a Moraes: nada da padaria aparece
    empresas.ativar("24875410000144")
    assert emissor.env("ITABORAI_CNPJ") == "24875410000144"
    assert [c["razao_social"] for c in clientes.listar()] == ["CLIENTE DA MORAES"]
    assert financeiro.listar_titulos() == []
    assert len(tratar("estado", {})["empresas"]) == 2


def test_credenciais_e_servico_pela_tela(multi):
    assert tratar("empresa/credenciais", {})["chave"] == "••••••"
    tratar("empresa/credenciais/salvar", {"im": "999", "chave": "••••••", "proximo_rps": "3600"})
    assert emissor.env("ITABORAI_IM") == "999" and emissor.env("ITABORAI_CHAVE") == "abc"
    assert emissor.env("ITABORAI_PROXIMO_RPS") == "3600"
    assert "inválido" in tratar("empresa/credenciais/salvar", {"cnpj": "123"})["erro"]
    tratar("servico/salvar", {"item_lista_servico": "01.07", "codigo_desdobro": "010701", "aliquota_iss": "2.00"})
    assert lote.servico_padrao()["item_lista_servico"] == "01.07"


def test_robo_roda_todas_sem_misturar(multi):
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11222333000181"})
    vistos = []
    monkey = automacao._rodar
    automacao._rodar = lambda em=None, forcar=False, url=None: vistos.append(
        (emissor.env("ITABORAI_CNPJ"), str(emissor.raiz()))) or {"executado": True}
    try:
        r = automacao.rodar_todas(forcar=True)
    finally:
        automacao._rodar = monkey
    assert set(r) == {"MORAES & OLIVEIRA CONTABILIDADE", "PADARIA BOM PAO LTDA"}
    assert vistos == [("24875410000144", str(multi)), ("11222333000181", str(multi / "empresas" / "11222333000181"))]
    assert emissor.raiz() == multi / "empresas" / "11222333000181"     # a tela continua na empresa ativa


def test_contexto_por_thread_nao_vaza(multi):
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11222333000181"})
    pronto, liberar, visto = threading.Event(), threading.Event(), {}

    def robo():
        with emissor.usar_empresa(multi):
            pronto.set()
            liberar.wait(5)
            visto["robo"] = emissor.env("ITABORAI_CNPJ")

    t = threading.Thread(target=robo)
    t.start()
    pronto.wait(5)
    visto["tela"] = emissor.env("ITABORAI_CNPJ")          # outra thread (tela) enquanto o robô está na Moraes
    liberar.set()
    t.join()
    assert visto == {"tela": "11222333000181", "robo": "24875410000144"}


def test_extrato_de_outra_conta_nao_e_conciliado(multi, tmp_path):
    pasta = tmp_path / "extratos"
    pasta.mkdir()
    config.salvar({"pastas": {"extratos": str(pasta)}})
    (pasta / "a.ofx").write_text(OFX.format(conta="12345", fit="1"), encoding="utf-8")
    assert importacao.importar_extratos()["arquivos"] == 1
    assert config.carregar()["financeiro"]["contas_bancarias"] == ["077-0001-12345"]
    (pasta / "b.ofx").write_text(OFX.format(conta="99999", fit="2"), encoding="utf-8")
    r = importacao.importar_extratos()
    assert r["arquivos"] == 0 and r["outras_contas"] == 1


def test_empresa_nova_de_outro_municipio(multi):
    from nfse_itaborai import saude
    empresas.criar({"nome": "PADARIA BOM PAO LTDA", "cnpj": "11222333000181", "canal": "nacional", "municipio": "3304557"})
    clientes.salvar({"cpf_cnpj": "54399432000146", "razao_social": "CLIENTE", "endereco": {"codigo_municipio": "3304557"}})
    d = lote.montar_rps("54399432000146", "100")
    assert d["local_prestacao"] == "3304557" and d["local_recolhimento"] == "3304557"
    i = {x["id"]: x for x in saude.checklist()["itens"]}
    assert i["prefeitura"]["ok"] and i["prefeitura"]["titulo"] == "Dados da empresa emissora"   # nacional: só o CNPJ
    assert not i["servico"]["ok"]
    tratar("servico/salvar", {"descricao": "VENDA DE PAES"})
    assert {x["id"]: x for x in saude.checklist()["itens"]}["servico"]["ok"]
    empresas.ativar("24875410000144")
    assert lote.montar_rps("32396063000103", "100")["local_prestacao"] == "3301900"   # Moraes segue em Itaboraí
