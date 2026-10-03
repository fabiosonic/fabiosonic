"""Extrato do Inter pela API: baixa, concilia, não duplica (nem com OFX) e continua de onde parou."""

from datetime import date

import pytest

from nfse_itaborai import config, conciliacao, db, financeiro, importacao, inter
from nfse_itaborai.tela import tratar
from test_boletos import FakeInter, banco  # noqa: F401  (fixture)
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)

HOJE = date(2026, 10, 20)


def _tr(i, data, valor, op="C", titulo="Pix recebido", desc=""):
    return {"idTransacao": f"id-{i}", "dataTransacao": data, "tipoOperacao": op, "valor": valor,
            "titulo": titulo, "descricao": desc}


def test_extrato_baixa_e_concilia(banco):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "374,40", vencimento="2026-10-15", emitir_nfse=False)
    FakeInter.transacoes = [_tr(1, "2026-10-16", "374.40", desc=f"PIX RECEBIDO T{tid} RPS CONSULTORIA"),
                            _tr(2, "2026-10-17", "52.90", "D", "Pagamento", "TARIFA PACOTE")]
    r = importacao.importar_extrato_inter(em=HOJE)
    assert r["lancamentos"] == 2 and r["novos"] == 2 and r["titulos"] == 1 and r["despesas"] == 1
    assert financeiro.obter_titulo(tid)["status"] == "pago"
    movs = db.linhas("SELECT * FROM movimentos ORDER BY data")
    assert [m["valor_cent"] for m in movs] == [37440, -5290] and movs[0]["fitid"] == "inter:id-1"
    # de novo: nada duplica
    assert importacao.importar_extrato_inter(em=HOJE)["novos"] == 0
    assert config.carregar()["financeiro"]["extrato_inter_ate"] == "2026-10-20"


def test_continua_de_onde_parou_e_pagina(banco):  # noqa: F811
    FakeInter.transacoes = [_tr(i, "2026-10-05", f"{10 + i}.00", "D", desc=f"DEB {i}") for i in range(60)]
    config.salvar({"automacao": {"despesas_do_extrato": False}})
    r = importacao.importar_extrato_inter(em=HOJE)
    assert r["novos"] == 60                                     # duas páginas de 50
    assert r["periodo"] == "2026-09-21 a 2026-10-20"
    importacao.importar_extrato_inter(em=date(2026, 10, 25))
    ultima = FakeInter.consultas_extrato[-1]
    assert ultima["dataInicio"] == ["2026-10-17"] and ultima["dataFim"] == ["2026-10-25"]


def test_periodo_longo_em_consultas_de_30_dias(banco):  # noqa: F811
    importacao.importar_extrato_inter(dias=90, em=HOJE)
    assert len(FakeInter.consultas_extrato) == 3


def test_api_e_ofx_nao_duplicam(banco):  # noqa: F811
    config.salvar({"automacao": {"despesas_do_extrato": False}})
    FakeInter.transacoes = [_tr(1, "2026-10-16", "100.00", "D", desc="BOLETO X"),
                            _tr(2, "2026-10-16", "100.00", "D", desc="BOLETO Y")]
    importacao.importar_extrato_inter(em=HOJE)
    ofx = ("<OFX><BANKTRANLIST><STMTTRN><DTPOSTED>20261016<TRNAMT>-100.00<FITID>A1<MEMO>BOLETO X</STMTTRN>"
           "<STMTTRN><DTPOSTED>20261016<TRNAMT>-100.00<FITID>A2<MEMO>BOLETO Y</STMTTRN>"
           "<STMTTRN><DTPOSTED>20261016<TRNAMT>-100.00<FITID>A3<MEMO>BOLETO Z</STMTTRN></BANKTRANLIST></OFX>")
    r = conciliacao.importar(ofx)
    assert r["novos"] == 1                                      # só o terceiro débito igual é novo
    assert len(db.linhas("SELECT * FROM movimentos")) == 3


def test_integracao_sem_escopo_de_extrato(banco):  # noqa: F811
    FakeInter.extrato_liberado = False
    with pytest.raises(inter.ErroInter, match="Consultar extrato e saldo"):
        importacao.importar_extrato_inter(em=HOJE)
    # boletos continuam funcionando (token de cobrança separado)
    assert inter.testar()["ok"]


def test_rota_e_robo(banco):  # noqa: F811
    FakeInter.transacoes = [_tr(1, inter._hoje().isoformat(), "10.00", "D", desc="TARIFA")]
    assert tratar("conciliacao/inter", {"dias": 5})["novos"] == 1
    from nfse_itaborai import automacao
    res = automacao.rodar(forcar=True)
    assert "extrato_inter" in res and not str(res["extrato_inter"]).startswith("erro")
