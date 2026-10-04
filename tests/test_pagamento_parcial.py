"""Pagamento parcial: o escritório decide se a diferença é desconto ou nova conta a receber (com boleto próprio)."""

from datetime import date

import pytest

from nfse_itaborai import cobranca, conciliacao, config, db, emissor, financeiro, relatorios
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


@pytest.fixture
def notas(monkeypatch):
    emitidas = []

    def emitir(tid, url=None):
        t = financeiro.obter_titulo(tid)
        emitidas.append((tid, financeiro.valor_da_nota(t)))
        financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero=f"2026{tid:06d}")
        return {"sucesso": True, "erros": [], "titulo": financeiro.obter_titulo(tid)}
    monkeypatch.setattr(emissor, "em_producao", lambda: True)
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", emitir)
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 5))
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    return emitidas


def _titulo(valor="1000", venc="2026-10-10"):
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], valor, "HONORARIOS", vencimento=venc, emitir_nfse=False)
    financeiro.atualizar_titulo(tid, nfse_status="apos_pagamento", pix_copia_cola="000201x")
    return tid


def test_parcial_fica_aguardando_decisao_e_a_nota_espera(base, notas):  # noqa: F811
    tid = _titulo()
    r = financeiro.baixar(tid, "2026-10-05", "600", "pix")
    assert r["parcial"] and "faltaram R$ 400,00" in r["aviso"]
    t = financeiro.obter_titulo(tid)
    assert (t["status"], t["parcial_status"], t["parcial_dif_cent"], t["nfse_status"]) == ("pago", "pendente", 40000, "apos_pagamento")
    assert notas == []                                                    # nota só depois da decisão
    assert relatorios.painel()["parciais_pendentes"] == 1


def test_decidir_cobrar_nota_so_do_pago_e_o_resto_na_nota_do_saldo(base, notas):  # noqa: F811
    tid = _titulo()
    financeiro.baixar(tid, "2026-10-05", "600", "pix")
    r = financeiro.decidir_parcial(tid, "cobrar")
    novo = financeiro.obter_titulo(r["saldo_titulo_id"])
    assert (novo["valor_cent"], novo["vencimento"], novo["nfse_status"], novo["cobrar"]) == (40000, "2026-10-10", "apos_pagamento", 1)
    assert novo["descricao"].startswith("SALDO DO PAGAMENTO PARCIAL") and financeiro.valor_da_nota(novo) == 40000
    assert notas == [(tid, 60000)]                                        # nota só do valor pago
    assert financeiro.obter_titulo(tid)["parcial_status"] == "cobrar"
    texto = cobranca.mensagem_pagamento(financeiro.obter_titulo(tid), config.carregar())[1]
    assert "saldo de R$ 400,00" in texto and "10/10/2026" in texto
    with pytest.raises(ValueError):
        financeiro.decidir_parcial(tid, "desconto")                       # decisão é uma vez só
    financeiro.baixar(novo["id"], "2026-10-09", "400", "pix")             # saldo pago: nota do restante
    assert notas == [(tid, 60000), (novo["id"], 40000)]


def test_saldo_so_de_multa_e_juros_nao_tem_nota(base, notas):  # noqa: F811
    tid = _titulo(venc="2026-09-10")                                      # devido 1.000 + 20 + 8,33
    financeiro.baixar(tid, "2026-10-05", "1000", "pix", parcial="cobrar")
    novo = financeiro.obter_titulo(financeiro.obter_titulo(tid)["saldo_titulo_id"])
    assert novo["valor_cent"] == 2833 and novo["nfse_status"] == "nao_emitir" and notas == [(tid, 100000)]


def test_decidir_desconto_reduz_a_nota(base, notas):  # noqa: F811
    tid = _titulo()
    financeiro.baixar(tid, "2026-10-05", "900", "dinheiro", parcial="desconto")   # já decidido na baixa manual
    t = financeiro.obter_titulo(tid)
    assert (t["parcial_status"], t["desconto_cent"]) == ("desconto", 10000) and notas == [(tid, 90000)]   # só o pago
    assert not db.linhas("SELECT 1 FROM titulos WHERE descricao LIKE 'SALDO%'")


def test_perdoar_so_multa_e_juros_nao_mexe_na_nota(base, notas):  # noqa: F811
    tid = _titulo(venc="2026-09-10")                                      # vencido: devido 1.000 + 20 + 8,33
    financeiro.baixar(tid, "2026-10-05", "1000", "pix", parcial="desconto")
    t = financeiro.obter_titulo(tid)
    assert t["parcial_dif_cent"] == 2833 and t["desconto_cent"] == 0 and notas == [(tid, 100000)]


def test_pagamento_cheio_nao_e_parcial(base, notas):  # noqa: F811
    tid = _titulo()
    r = financeiro.baixar(tid, "2026-10-05", "1000", "pix")
    assert not r.get("parcial") and financeiro.obter_titulo(tid)["parcial_status"] == "" and notas == [(tid, 100000)]


def test_extrato_com_valor_menor_vira_parcial(base, notas):  # noqa: F811
    tid = _titulo()
    with db.conexao() as con:
        con.execute("INSERT INTO movimentos (data, descricao, valor_cent, fitid, importado_em) VALUES (?,?,?,?,?)",
                    ("2026-10-05", f"PIX RECEBIDO T{tid}", 70000, "m1", "2026-10-05 10:00:00"))
    mid = db.linhas("SELECT id FROM movimentos")[0]["id"]
    conciliacao.vincular(mid, tid)
    assert financeiro.obter_titulo(tid)["parcial_status"] == "pendente"


def test_estorno_desfaz_o_parcial_e_cancela_o_saldo(base, notas):  # noqa: F811
    tid = _titulo()
    financeiro.baixar(tid, "2026-10-05", "600", "pix", parcial="cobrar")
    saldo = financeiro.obter_titulo(tid)["saldo_titulo_id"]
    financeiro.estornar(tid)
    t = financeiro.obter_titulo(tid)
    assert (t["status"], t["parcial_status"], t["saldo_titulo_id"]) == ("aberto", "", 0)
    assert financeiro.obter_titulo(saldo)["status"] == "cancelado"
