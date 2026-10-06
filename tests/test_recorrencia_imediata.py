"""Recorrência salva na tela: o título do mês aparece no Contas a receber na hora, sem esperar o robô."""

from datetime import date

from nfse_itaborai import automacao, config, db, financeiro
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)


def _titulos(doc):
    return db.linhas("SELECT * FROM titulos WHERE cpf_cnpj=? AND contrato_id IS NOT NULL", (doc,))


def test_cliente_novo_na_recorrencia_gera_o_titulo_do_mes_ao_salvar(base, monkeypatch):  # noqa: F811
    """Caso real: cliente cadastrado em 06/10/2026 com início em outubro/2026 e vencimento dia 5."""
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 6))
    r = tratar("recorrencia/salvar", {"linhas": [{"cpf_cnpj": CLI_A["cpf_cnpj"], "repetir": True, "valor": "500,00",
                                                  "inicio": "2026-10", "dia_vencimento": 5, "cobrar": True}]})
    assert len(r["gerados"]) == 1
    t = _titulos(CLI_A["cpf_cnpj"])
    assert [(x["competencia"], x["valor_cent"], x["vencimento"]) for x in t] == [("2026-10", 50000, "2026-10-05")]
    tratar("recorrencia/salvar", {"linhas": [{"id": t[0]["contrato_id"], "repetir": True, "valor": "500,00"}]})
    assert len(_titulos(CLI_A["cpf_cnpj"])) == 1                    # salvar de novo não duplica


def test_a_confirmar_inicio_futuro_e_antes_do_dia_de_geracao_nao_geram(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 6))
    tratar("recorrencia/salvar", {"linhas": [
        {"cpf_cnpj": CLI_A["cpf_cnpj"], "repetir": False, "valor": "500", "inicio": "2026-10"},
        {"cpf_cnpj": CLI_B["cpf_cnpj"], "repetir": True, "valor": "300", "inicio": "2026-11"}]})
    assert not _titulos(CLI_A["cpf_cnpj"]) and not _titulos(CLI_B["cpf_cnpj"])
    config.salvar({"financeiro": {"dia_geracao": 10}})
    k = tratar("contrato/salvar", {"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "inicio": "2026-10", "confirmado": True})
    assert k["gerados"] == [] and not _titulos(CLI_A["cpf_cnpj"])   # dia 6 < dia 10 de geração: espera o robô


def test_rotina_rapida_tambem_gera_a_recorrencia(base, monkeypatch):  # noqa: F811
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "inicio": "2026-10", "confirmado": True})
    automacao._rodar_pagamentos(date(2026, 10, 6))
    assert [x["competencia"] for x in _titulos(CLI_A["cpf_cnpj"])] == ["2026-10"]
