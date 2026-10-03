"""Aba Notas emitidas: lista por competência, filtros e cancelamento da NFS-e."""

from nfse_itaborai import financeiro
from nfse_itaborai.tela import tratar
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)


def _emitir(doc, valor):
    r = tratar("emitir", {"cpf_cnpj": doc, "valor": valor, "cobrar": False})
    assert r["sucesso"], r
    return r["titulo_id"], r["nfse"]


def test_lista_filtra_e_cancela(base):  # noqa: F811
    a, na = _emitir(CLI_A["cpf_cnpj"], "350")
    b, _ = _emitir(CLI_B["cpf_cnpj"], "400")
    antiga = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "100", competencia="2026-08", emitir_nfse=False)
    financeiro.atualizar_titulo(antiga, nfse_status="emitida", nfse_numero="77", origem="importado")
    comp = financeiro.obter_titulo(a)["competencia"]
    r = tratar("nfse/listar", {"competencia": comp})
    assert r["qtd"] == 2 and r["total_cent"] == 75000 and {n["id"] for n in r["notas"]} == {a, b}
    assert all(n["pode_cancelar"] and n["data"] for n in r["notas"])
    assert tratar("nfse/listar", {"competencia": ""})["qtd"] == 3                       # todas as competências
    assert [n["id"] for n in tratar("nfse/listar", {"competencia": comp, "busca": "cultivar"})["notas"]] == [b]
    assert [n["id"] for n in tratar("nfse/listar", {"competencia": comp, "busca": CLI_A["cpf_cnpj"]})["notas"]] == [a]
    importada = tratar("nfse/listar", {"competencia": "2026-08"})["notas"][0]
    assert not importada["pode_cancelar"]
    assert "portal" in tratar("titulo/cancelar_nfse", {"id": antiga, "justificativa": "Emitida em duplicidade"})["erros"][0]
    assert not tratar("titulo/cancelar_nfse", {"id": a, "justificativa": "curta"})["sucesso"]
    c = tratar("titulo/cancelar_nfse", {"id": a, "justificativa": "Nota emitida com valor incorreto"})
    assert c["sucesso"], c
    t = financeiro.obter_titulo(a)
    assert t["nfse_status"] == "cancelada" and t["status"] == "cancelado"
    r = tratar("nfse/listar", {"competencia": comp})
    assert r["qtd"] == 1 and r["canceladas"] == 1
    assert [n["id"] for n in tratar("nfse/listar", {"competencia": comp, "situacao": "cancelada"})["notas"]] == [a]


def test_nota_de_conta_paga_exige_estorno(base):  # noqa: F811
    a, _ = _emitir(CLI_A["cpf_cnpj"], "350")
    financeiro.baixar(a, forma="manual")
    r = tratar("titulo/cancelar_nfse", {"id": a, "justificativa": "Nota emitida com valor incorreto"})
    assert not r["sucesso"] and "estorno" in r["erros"][0]
    assert financeiro.obter_titulo(a)["nfse_status"] == "emitida"


def test_encerrar_sistema_pela_tela_e_ja_aberto(base, monkeypatch):  # noqa: F811
    import os
    import time
    from nfse_itaborai import tela
    saiu = []
    monkeypatch.setattr(os, "_exit", lambda c: saiu.append(c))
    assert tratar("sistema/encerrar", {})["ok"]
    time.sleep(1.2)
    assert saiu == [0]
    monkeypatch.setattr(tela, "_quem_esta_na_porta", lambda p: {})
    assert tela.abrir_se_ja_aberto() is False


def test_copiar_dados_da_ultima_nota(base):  # noqa: F811
    from nfse_itaborai.tela import tratar
    assert tratar("nfse/ultima", {"cpf_cnpj": CLI_A["cpf_cnpj"]})["nota"] is None
    x = {"local_prestacao": "3304557", "desc_incond": "10", "pedido": "PED-1", "subst_chave": "", "doc_ref": "Contrato 7"}
    financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "374,40", "HONORARIOS SETEMBRO", vencimento="2026-10-10", extras=x)
    financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "400,00", "HONORARIOS OUTUBRO", vencimento="2026-11-10", extras=x)
    n = tratar("nfse/ultima", {"cpf_cnpj": CLI_A["cpf_cnpj"]})["nota"]
    assert n["valor_cent"] == 40000 and n["descricao"] == "HONORARIOS OUTUBRO" and n["nfse_numero"]
    assert n["extras"]["local_prestacao"] == "3304557" and n["extras"]["doc_ref"] == "Contrato 7"
    assert "pedido" not in n["extras"]                       # campo de uma nota só não é copiado
    assert tratar("nfse/ultima", {"cpf_cnpj": "54399432000146"})["nota"] is None   # outro tomador
    assert tratar("nfse/dados", {"id": n["id"]})["valor_cent"] == 40000


def test_correcoes_do_teste_de_ponta_a_ponta(base):  # noqa: F811
    from nfse_itaborai import clientes, config
    config.salvar({"cobranca": {"provedor": "pix"}})
    # emissão com "Gerar cobrança": PIX/boleto na hora (não espera o robô) e o título não fica "sem cobrança"
    r = financeiro.emitir_avulsa(CLI_A["cpf_cnpj"], "300,00", "HONORARIOS", vencimento="2026-10-10")
    t = financeiro.obter_titulo(r["titulo_id"])
    assert t["pix_copia_cola"] and financeiro.situacao(t) != "sem_cobranca"
    # a última nota emitida pelo sistema vira o valor sugerido do cliente (lote e recorrência)
    assert clientes.obter(CLI_A["cpf_cnpj"])["ultimo_valor"] == "300.00"
    # despesa excluída some das listas
    d = financeiro.salvar_despesa({"descricao": "X", "valor": "10"})
    financeiro.excluir_despesa(d)
    assert not any(x["id"] == d for x in financeiro.listar_despesas("todos"))
