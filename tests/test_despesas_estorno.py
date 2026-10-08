"""Contas a pagar: estorno do pagamento, data de início das despesas do extrato e débito nunca vira despesa em dobro."""

import pytest

from nfse_itaborai import conciliacao, config, db, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import base  # noqa: F401  (fixture)


def _deb(data, valor, fit, desc="SEGURADORA"):
    return {"data": data, "valor_cent": -valor, "descricao": desc, "fitid": fit}


def test_estornar_pagamento_de_despesa_manual_e_do_extrato(base):  # noqa: F811
    did = financeiro.salvar_despesa({"descricao": "ALUGUEL", "valor": "1500", "vencimento": "2026-10-05"})
    financeiro.pagar_despesa(did, "2026-10-05")
    assert financeiro.estornar_despesa(did) == {"ok": True, "extrato": False}
    d = db.linhas("SELECT * FROM despesas WHERE id=?", (did,))[0]
    assert d["status"] == "aberto" and not d["data_pagamento"]
    with pytest.raises(ValueError, match="Só despesa paga"):
        financeiro.estornar_despesa(did)
    conciliacao.importar("", [_deb("2026-10-06", 117271, "inter:9")])
    m = db.linhas("SELECT * FROM movimentos WHERE fitid='inter:9'")[0]
    assert m["despesa_id"]
    assert financeiro.estornar_despesa(m["despesa_id"])["extrato"]
    m = db.linhas("SELECT * FROM movimentos WHERE fitid='inter:9'")[0]
    assert m["despesa_id"] is None and m["manual"] == 1
    conciliacao.conciliar()                                   # o débito não vira despesa de novo sozinho
    assert db.linhas("SELECT despesa_id FROM movimentos WHERE fitid='inter:9'")[0]["despesa_id"] is None
    assert any(x["fitid"] == "inter:9" for x in conciliacao.nao_conciliados())


def test_debito_antes_da_data_inicial_nao_vira_despesa(base):  # noqa: F811
    config.salvar({"financeiro": {"despesas_desde": "2026-10-01"}})
    conciliacao.importar("", [_deb("2026-09-20", 5000, "a1", "TARIFA"), _deb("2026-10-02", 6000, "a2", "TARIFA")])
    ds = [d["vencimento"] for d in financeiro.listar_despesas()]
    assert ds == ["2026-10-02"]
    antigo = db.linhas("SELECT * FROM movimentos WHERE fitid='a1'")[0]
    assert antigo["classificacao"] == "anterior" and not any(x["fitid"] == "a1" for x in conciliacao.nao_conciliados())


def test_mesmo_debito_conciliado_duas_vezes_nao_duplica(base, monkeypatch):  # noqa: F811
    conciliacao.importar("", [])
    with db.conexao() as con:
        con.execute("INSERT INTO movimentos (data, valor_cent, descricao, fitid, importado_em) VALUES (?,?,?,?,?)",
                    ("2026-10-03", -35702, "DEBITO DE IOF", "x1", db.agora()))
    real = db.linhas
    def ve_duas_vezes(sql, p=()):
        r = real(sql, p)
        if "FROM movimentos WHERE titulo_id IS NULL AND despesa_id IS NULL" in sql:
            return r + r                                       # simula duas rotinas lendo o mesmo débito
        return r
    monkeypatch.setattr(db, "linhas", ve_duas_vezes)
    conciliacao.conciliar()
    monkeypatch.setattr(db, "linhas", real)
    vivas = [d for d in financeiro.listar_despesas() if d["descricao"] == "DEBITO DE IOF"]
    assert len(vivas) == 1


def test_debito_do_banco_baixa_conta_a_pagar_escolhida(base):  # noqa: F811
    config.salvar({"automacao": {"despesas_do_extrato": False}})
    luz = financeiro.salvar_despesa({"descricao": "ENEL energia", "fornecedor": "ENEL", "valor": "75", "vencimento": "2026-10-10"})
    sci = financeiro.salvar_despesa({"descricao": "SCI SISTEMA", "valor": "1000", "vencimento": "2026-10-15"})
    conciliacao.importar("", [_deb("2026-10-12", 7690, "e1", "PAGAMENTO CONVENIO ENEL")])   # pago com juros
    m = db.linhas("SELECT * FROM movimentos WHERE fitid='e1'")[0]
    assert m["despesa_id"] is None
    lista = conciliacao.despesas_para_vincular("", 7690)
    assert [d["id"] for d in lista][:2] == [luz, sci]                      # mais perto do valor primeiro
    assert [d["id"] for d in conciliacao.despesas_para_vincular("enel")] == [luz]
    r = conciliacao.vincular_despesa(m["id"], luz)
    assert r["diferenca_cent"] == 190
    d = db.linhas("SELECT * FROM despesas WHERE id=?", (luz,))[0]
    assert d["status"] == "pago" and d["data_pagamento"] == "2026-10-12" and d["valor_cent"] == 7690
    assert db.linhas("SELECT despesa_id FROM movimentos WHERE id=?", (m["id"],))[0]["despesa_id"] == luz
    assert all(x["id"] != luz for x in conciliacao.despesas_para_vincular())


def test_despesa_automatica_do_extrato_vira_a_conta_a_pagar(base):  # noqa: F811
    sci = financeiro.salvar_despesa({"descricao": "SCI SISTEMA", "valor": "1000", "vencimento": "2026-10-15"})
    conciliacao.importar("", [_deb("2026-10-16", 102000, "s1", "PIX SCI")])   # valor diferente: vira despesa automática
    m = db.linhas("SELECT * FROM movimentos WHERE fitid='s1'")[0]
    auto = m["despesa_id"]
    assert auto and auto != sci
    r = conciliacao.vincular_despesa(m["id"], sci)
    assert r["despesa_automatica_cancelada"]
    assert db.linhas("SELECT status FROM despesas WHERE id=?", (auto,))[0]["status"] == "cancelado"
    assert [d["descricao"] for d in financeiro.listar_despesas()] == ["SCI SISTEMA"]
    outra = financeiro.salvar_despesa({"descricao": "OUTRA", "valor": "10", "vencimento": "2026-10-15"})
    with pytest.raises(ValueError, match="Estorne"):
        conciliacao.vincular_despesa(m["id"], outra)


def test_sugestao_de_conta_a_pagar_no_debito_pendente(base):  # noqa: F811
    config.salvar({"automacao": {"despesas_do_extrato": False}})
    a = financeiro.salvar_despesa({"descricao": "ALUGUEL", "valor": "1500", "vencimento": "2026-10-05"})
    b = financeiro.salvar_despesa({"descricao": "CONDOMINIO", "valor": "1500", "vencimento": "2026-10-05"})
    conciliacao.importar("", [_deb("2026-10-05", 150000, "k1", "PIX ENVIADO")])   # dois de mesmo valor: não adivinha
    p = next(x for x in conciliacao.nao_conciliados() if x["fitid"] == "k1")
    assert {s["id"] for s in p["sugestoes"]} == {a, b} and all(s["despesa"] for s in p["sugestoes"])
