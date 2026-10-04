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
    assert r["novos"] == 5 and r["titulos"] == 1
    e = conciliacao.extrato()
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
