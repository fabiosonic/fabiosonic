"""Extrato completo na conciliação: entradas e saídas, transferências da própria empresa, aportes e despesas."""

from nfse_itaborai import conciliacao, config, db, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _movs():
    return [{"data": "2026-09-30", "valor_cent": 13000, "descricao": "Pix recebido Moraes & Oliveira Contabilidade", "fitid": "inter:1"},
            {"data": "2026-09-29", "valor_cent": 26000, "descricao": "Pix recebido Fabio Moraes Oliveira", "fitid": "inter:2"},
            {"data": "2026-09-28", "valor_cent": 10000, "descricao": "Pix recebido Fabio Moraes Oliveira", "fitid": "inter:3"},
            {"data": "2026-09-27", "valor_cent": -200000, "descricao": "Pix enviado Laila Jardim Gestao", "fitid": "inter:4"},
            {"data": "2026-09-26", "valor_cent": 30000, "descricao": f"Pix recebido RPS CONSULTORIA T{{tid}}", "fitid": "inter:5"}]


def test_extrato_completo_e_classificacao(base):  # noqa: F811
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}, "automacao": {"despesas_do_extrato": False}})
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    movs = _movs()
    movs[-1]["descricao"] = movs[-1]["descricao"].replace("{tid}", str(tid))
    r = conciliacao.importar("", movs)
    assert r["novos"] == 5 and r["titulos"] == 1 and r["entradas"] == 4 and r["saidas"] == 1
    e = conciliacao.extrato()
    # resumo por origem: mostra que as saídas também vieram do banco (mesmo já conciliadas)
    assert e["fontes"]["inter"] == {"n": 5, "entradas": 4, "saidas": 1, "de": "2026-09-26", "ate": "2026-09-30", "pendentes": 3}
    assert conciliacao.extrato("2026-10-01", "2026-10-31")["movimentos"] == []       # mês sem movimento: lista vazia, resumo igual
    sit = {m["descricao"][:30]: m["situacao"] for m in e["movimentos"]}
    assert sit["Pix recebido Moraes & Oliveira"] == "classificado"              # transferência da própria empresa
    assert e["entradas"] == 79000 and e["saidas"] == 200000 and e["pendentes"] == 3
    pend = conciliacao.nao_conciliados()
    assert {m["descricao"] for m in pend} == {"Pix recebido Fabio Moraes Oliveira", "Pix enviado Laila Jardim Gestao"}
    aporte = next(m for m in pend if m["valor_cent"] == 26000)
    assert conciliacao.classificar(aporte["id"], "aporte")["aplicados"] == 2      # os dois Pix do sócio
    saida = next(m for m in pend if m["valor_cent"] < 0)
    r = conciliacao.classificar(saida["id"], "despesa", categoria_desp="Pessoal")
    d = db.linhas("SELECT * FROM despesas WHERE id=?", (r["despesa"],))[0]
    assert d["status"] == "pago" and d["categoria"] == "Pessoal" and d["valor_cent"] == 200000
    assert conciliacao.nao_conciliados() == [] and conciliacao.extrato()["pendentes"] == 0
    conciliacao.classificar(aporte["id"], "", iguais=False)                      # desfazer um
    assert len(conciliacao.nao_conciliados()) == 1


def test_transferencia_que_virou_despesa_e_corrigida(base):  # noqa: F811
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}})
    did = financeiro.salvar_despesa({"descricao": "Pix enviado Moraes Oliveira Contabilidade", "fornecedor": "extrato",
                                     "valor": "200,00", "vencimento": "2026-08-18"})
    financeiro.pagar_despesa(did, "2026-08-18")
    with db.conexao() as con:
        con.execute("INSERT INTO movimentos (data, valor_cent, descricao, fitid, despesa_id, importado_em) VALUES "
                    "('2026-08-18', -20000, 'Pix enviado Moraes Oliveira Contabilidade', 'inter:x', ?, '2026-10-03')", (did,))
    conciliacao.conciliar()
    m = db.linhas("SELECT * FROM movimentos")[0]
    assert m["despesa_id"] is None and m["classificacao"] == "transferencia"
    assert db.linhas("SELECT status FROM despesas WHERE id=?", (did,))[0]["status"] == "cancelado"


def test_despesa_automatica_do_extrato_pode_ser_recategorizada_e_desfeita(base):  # noqa: F811
    """Caso real (extrato Inter 04/09 a 04/10/2026): as saídas viraram despesa 'Outras' sozinhas e não apareciam para
    conciliar. Agora o extrato mostra quais revisar, a categoria vale para a contraparte e vira regra; e dá para desfazer."""
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}, "automacao": {"despesas_do_extrato": True}})
    movs = [{"data": "2026-09-18", "valor_cent": -65000, "descricao": "Pix enviado Miguel Dos Santos Silva Jose", "fitid": "inter:a"},
            {"data": "2026-09-30", "valor_cent": -335000, "descricao": "Pix enviado Miguel Dos Santos Silva Jose", "fitid": "inter:b"},
            {"data": "2026-09-21", "valor_cent": -70000, "descricao": "Pix enviado Luna Francisco Figueira Faria", "fitid": "inter:c"}]
    r = conciliacao.importar("", movs)
    assert r["despesas"] == 3 or len(db.linhas("SELECT id FROM despesas WHERE fornecedor='extrato'")) == 3
    e = conciliacao.extrato("2026-09-01", "2026-09-30")
    assert e["a_revisar"] == 3 and all(m["despesa_auto"] and m["categoria"] == "Outras" for m in e["movimentos"])
    grupos = {g["grupo"]: g for g in e["categorias"]}
    assert "Folha" in grupos["Despesas com pessoal"]["categorias"] and "Bancárias" in grupos["Despesas financeiras"]["categorias"]
    assert [f["valor"] for f in grupos["Fora da DRE (não é despesa)"]["fora"]] == ["__cls:distribuicao", "__cls:transferencia", "__cls:outra_saida"]
    miguel = next(m for m in e["movimentos"] if m["fitid"] == "inter:a")
    x = conciliacao.recategorizar(miguel["id"], "Folha")
    assert x["aplicados"] == 2 and x["regra"] == "MIGUEL DOS SANTOS SILVA JOSE"
    cats = {m["fitid"]: m["categoria"] for m in conciliacao.extrato("2026-09-01", "2026-09-30")["movimentos"]}
    assert cats == {"inter:a": "Folha", "inter:b": "Folha", "inter:c": "Outras"}
    assert conciliacao.categoria("Pix enviado Miguel Dos Santos Silva Jose") == "Folha"   # próximos já entram certos
    from nfse_itaborai import contabil
    assert contabil._grupo("Folha") == "Despesas com pessoal"                          # e caem na linha certa da DRE
    luna = next(m for m in e["movimentos"] if m["fitid"] == "inter:c")
    conciliacao.classificar(luna["id"], "")                                     # desfazer: volta a pendente
    assert [m["descricao"] for m in conciliacao.nao_conciliados()] == ["Pix enviado Luna Francisco Figueira Faria"]
    assert db.linhas("SELECT status FROM despesas WHERE id=?", (luna["despesa_id"],))[0]["status"] == "cancelado"
    conciliacao.conciliar()                                                     # o robô não recria a despesa desfeita
    assert [m["descricao"] for m in conciliacao.nao_conciliados()] == ["Pix enviado Luna Francisco Figueira Faria"]


def test_pix_ao_socio_sai_da_dre_como_distribuicao_de_lucros(base):  # noqa: F811
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}, "automacao": {"despesas_do_extrato": True}})
    conciliacao.importar("", [{"data": "2026-09-26", "valor_cent": -16000, "descricao": "Pix enviado Fabio Moraes Oliveira", "fitid": "inter:f1"}])
    m = conciliacao.extrato()["movimentos"][0]
    assert m["despesa_auto"]
    r = conciliacao.recategorizar(m["id"], "__cls:distribuicao")
    assert r["fora_dre"] == "distribuicao"
    m = conciliacao.extrato()["movimentos"][0]
    assert m["situacao"] == "classificado" and m["classificacao"] == "distribuicao" and not m["despesa_id"]
    assert db.linhas("SELECT COUNT(*) n FROM despesas WHERE status!='cancelado'")[0]["n"] == 0     # não é despesa
    # o próximo Pix ao sócio já entra como distribuição, sem virar despesa
    conciliacao.importar("", [{"data": "2026-10-05", "valor_cent": -50000, "descricao": "Pix enviado Fabio Moraes Oliveira", "fitid": "inter:f2"}])
    novo = next(x for x in conciliacao.extrato()["movimentos"] if x["fitid"] == "inter:f2")
    assert novo["classificacao"] == "distribuicao" and not novo["despesa_id"]
    with __import__("pytest").raises(ValueError):
        conciliacao.recategorizar(novo["id"], "__cls:aporte")


def test_banco_de_versao_anterior_nao_trava_ao_classificar(base):  # noqa: F811
    """Caso real: vários Pix ao sócio (mesma contraparte); classificar 'fora da DRE' abria uma gravação dentro da outra
    e ficava em 'database is locked'."""
    import sqlite3
    config.salvar({"empresa": {"nome": "MORAES & OLIVEIRA CONTABILIDADE"}, "automacao": {"despesas_do_extrato": True}})
    conciliacao.importar("", [{"data": "2026-09-26", "valor_cent": -16000, "descricao": "Pix enviado Fabio Moraes Oliveira", "fitid": "inter:f1"},
                              {"data": "2026-08-31", "valor_cent": -40000, "descricao": "Pix enviado Fabio Moraes Oliveira", "fitid": "inter:f2"},
                              {"data": "2026-07-31", "valor_cent": -77837, "descricao": "Pix enviado Fabio Moraes Oliveira", "fitid": "inter:f3"}])
    mid = conciliacao.extrato()["movimentos"][0]["id"]
    con = sqlite3.connect(db.caminho())
    con.execute("ALTER TABLE movimentos DROP COLUMN manual")             # como o banco da versão anterior
    con.commit(); con.close()
    import time
    t0 = time.time()
    r = conciliacao.recategorizar(mid, "__cls:distribuicao")
    assert r["fora_dre"] == "distribuicao" and r["aplicados"] == 3 and time.time() - t0 < 5
    assert {m["classificacao"] for m in conciliacao.extrato()["movimentos"]} == {"distribuicao"}
