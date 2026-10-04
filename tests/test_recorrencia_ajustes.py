"""Recorrência: mês de início e final, acréscimos e descontos (únicos ou recorrentes) somados ao título do mês."""

from datetime import date

import pytest

from nfse_itaborai import db, financeiro
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _contrato(**k):
    return financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "dia_vencimento": 10,
                                       "inicio": "2026-09", "descricao": "HONORARIOS CONTABEIS", **k})


def _titulo(comp):
    r = db.linhas("SELECT * FROM titulos WHERE competencia=?", (comp,))
    return r[0] if r else None


def test_acrescimo_unico_e_desconto_recorrente(base):  # noqa: F811
    k = _contrato()
    financeiro.salvar_ajuste({"contrato_id": k["id"], "tipo": "acrescimo", "descricao": "Alteração contratual",
                              "valor": "300,00", "unico": True, "inicio": "2026-10"})
    financeiro.salvar_ajuste({"contrato_id": k["id"], "tipo": "desconto", "descricao": "Desconto parceria",
                              "valor": "100,00", "unico": False, "inicio": "2026-10", "fim": "2026-11"})
    for comp in ("2026-09", "2026-10", "2026-11", "2026-12"):
        financeiro.gerar_titulos(comp, date(2026, 9, 1))
    assert _titulo("2026-09")["valor_cent"] == 100000 and _titulo("2026-09")["descricao"] == "HONORARIOS CONTABEIS"
    t = _titulo("2026-10")
    assert t["valor_cent"] == 120000                                     # 1.000 + 300 − 100
    assert "Alteração contratual R$ 300,00" in t["descricao"] and "- Desconto parceria R$ 100,00" in t["descricao"]
    assert _titulo("2026-11")["valor_cent"] == 90000                     # só o desconto (até 11/2026)
    assert _titulo("2026-12")["valor_cent"] == 100000


def test_desconto_que_zera_nao_gera_titulo(base):  # noqa: F811
    k = _contrato()
    financeiro.salvar_ajuste({"contrato_id": k["id"], "tipo": "desconto", "descricao": "Cortesia", "valor": "1000",
                              "unico": True, "inicio": "2026-10"})
    assert financeiro.gerar_titulos("2026-10", date(2026, 10, 1)) == []


@pytest.mark.parametrize("d,erro", [({"tipo": "x"}, "acréscimo ou desconto"), ({"descricao": ""}, "descrição"),
                                    ({"valor": "0"}, "maior que zero"), ({"inicio": ""}, "início"),
                                    ({"unico": False, "fim": "2026-01"}, "antes do início")])
def test_validacoes_do_ajuste(base, d, erro):  # noqa: F811
    k = _contrato()
    with pytest.raises(ValueError, match=erro):
        financeiro.salvar_ajuste({"contrato_id": k["id"], "tipo": "acrescimo", "descricao": "X", "valor": "10",
                                  "unico": True, "inicio": "2026-10", **d})


def test_inicio_e_fim_pela_tela_de_recorrencia(base):  # noqa: F811
    k = _contrato()
    financeiro.salvar_recorrencia([{"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor_cent": 100000, "dia_vencimento": 10,
                                    "repetir": True, "inicio": "2026-11", "fim": "2027-01"}])
    for comp in ("2026-10", "2026-11", "2027-01", "2027-02"):
        financeiro.gerar_titulos(comp, date(2026, 10, 1))
    assert [_titulo(c) is not None for c in ("2026-10", "2026-11", "2027-01", "2027-02")] == [False, True, True, False]
    with pytest.raises(ValueError, match="antes do mês de início"):
        financeiro.salvar_recorrencia([{"id": k["id"], "cpf_cnpj": CLI_A["cpf_cnpj"], "valor_cent": 100000,
                                        "dia_vencimento": 10, "repetir": True, "inicio": "2026-11", "fim": "2026-10"}])
    linha = next(l for l in financeiro.lista_recorrencia() if l.get("id") == k["id"])
    assert (linha["inicio"], linha["fim"]) == ("2026-11", "2027-01")
