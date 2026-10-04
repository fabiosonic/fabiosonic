"""Regressões da revisão de código do QA (v3.6.1): recorrência × avulso no mesmo mês, saldo do parcial sem NFS-e,
falha ao gerar boleto não tira o título da régua, migração de início não puxa recorrência futura."""

from datetime import date

import pytest

from nfse_itaborai import cobranca, config, db, emissor, financeiro, inter
from nfse_itaborai.tela import tratar
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _contrato(**k):
    c = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "dia_vencimento": 10,
                                    "inicio": "2026-10", "descricao": "HONORARIOS CONTABEIS MENSAIS", **k})
    with db.conexao() as con:
        con.execute("UPDATE contratos SET confirmado=1")
    return c


def test_avulso_no_mesmo_mes_nao_quebra_nem_e_adotado_como_honorario(base):  # noqa: F811
    _contrato()
    extra = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "150", "HONORÁRIOS - ALTERAÇÃO CONTRATUAL", vencimento="2026-10-20",
                                    competencia="2026-10", emitir_nfse=False)
    novos = financeiro.gerar_titulos("2026-10", date(2026, 10, 4))
    assert len(novos) == 1 and financeiro.obter_titulo(novos[0])["valor_cent"] == 50000      # o honorário do mês saiu
    assert financeiro.obter_titulo(extra)["contrato_id"] is None                              # o avulso continua avulso
    # outro avulso do mês depois que o título da recorrência existe: nada quebra, nada é gerado de novo
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-10-10",
                            competencia="2026-10", emitir_nfse=False)
    assert financeiro.gerar_titulos("2026-10", date(2026, 10, 5)) == []
    assert db.linhas("SELECT COUNT(*) n FROM titulos WHERE competencia='2026-10'")[0]["n"] == 3


def test_honorario_pago_a_mao_e_adotado_mesmo_com_acento_e_ponto(base):  # noqa: F811
    k = _contrato()
    pago = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "500", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-10-01",
                                   competencia="2026-10", emitir_nfse=False, cobrar=False)
    financeiro.baixar(pago, "2026-10-01", "500", "pix")
    assert financeiro.gerar_titulos("2026-10", date(2026, 10, 4)) == []
    assert financeiro.obter_titulo(pago)["contrato_id"] == k["id"]
    assert financeiro._mesmo_honorario("HONORÁRIOS CONTABEIS MENSAIS.", "HONORARIOS CONTABEIS MENSAIS")
    assert not financeiro._mesmo_honorario("HONORÁRIOS - ALTERAÇÃO CONTRATUAL", "HONORARIOS CONTABEIS MENSAIS")


def test_saldo_do_parcial_segue_a_regra_sem_nfse(base, monkeypatch):  # noqa: F811
    monkeypatch.setattr(emissor, "em_producao", lambda: True)
    emitidas = []
    monkeypatch.setattr(financeiro, "emitir_nfse_titulo", lambda tid, url=None: emitidas.append(tid) or
                        {"sucesso": True, "erros": [], "titulo": financeiro.obter_titulo(tid)})
    monkeypatch.setattr(financeiro, "hoje", lambda: date(2026, 10, 5))
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1000", vencimento="2026-10-10", emitir_nfse=False)   # "só lançar"
    financeiro.baixar(tid, "2026-10-05", "600", "pix", parcial="cobrar")
    saldo = financeiro.obter_titulo(financeiro.obter_titulo(tid)["saldo_titulo_id"])
    assert saldo["nfse_status"] == "nao_emitir" and saldo["nota_cent"] == 0
    financeiro.baixar(saldo["id"], "2026-10-09", "400", "pix")
    assert emitidas == []                                                    # nenhuma nota em nenhum dos dois


def test_falha_ao_gerar_boleto_mantem_a_cobranca_sem_boleto(base, monkeypatch):  # noqa: F811
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "400", "HONORÁRIOS CONTABEIS MENSAIS.", vencimento="2026-07-15",
                                  emitir_nfse=True, apos_pagamento=True)
    financeiro.atualizar_titulo(tid, boleto_situacao="dispensado", pix_copia_cola="", linha_digitavel="", banco_id="")
    config.salvar({"cobranca": {"provedor": "inter"}, "empresa": {"pix_chave": ""}})
    monkeypatch.setattr(inter, "configurado", lambda cfg=None: False)      # Inter não configurado, sem chave PIX
    r = tratar("titulo/gerar_cobranca", {"id": tid})
    assert r.get("erro") and "não gerado" in r["erro"]
    t = financeiro.obter_titulo(tid)
    assert t["boleto_situacao"] == "dispensado" and t["cobranca_erro"]       # continua na régua, com o motivo
    assert tid in [x["id"] for x in db.linhas("SELECT id FROM titulos WHERE " + financeiro.SQL_COBRADO)]
    monkeypatch.setattr(inter, "configurado", lambda cfg=None: True)
    monkeypatch.setattr(inter, "criar_cobranca", lambda t, cfg=None, espera=0, atualizado=None:
                        {"banco_id": "cod-1", "linha_digitavel": "0779", "pix_copia_cola": "000201", "nosso_numero": "1"})
    monkeypatch.setattr(cobranca, "salvar_boleto", lambda tid, cfg=None, refazer=False: "")
    t = tratar("titulo/gerar_cobranca", {"id": tid})
    assert t["banco_id"] == "cod-1" and t["boleto_situacao"] == "" and t["cobranca_erro"] == ""


@pytest.mark.parametrize("inicio,esperado", [("2026-03", "2026-10"), ("2026-11", "2026-10"), ("2027-01", "2027-01")])
def test_migracao_de_inicio_nao_puxa_recorrencia_futura(base, monkeypatch, inicio, esperado):  # noqa: F811
    k = financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "500", "dia_vencimento": 10, "inicio": inicio})
    monkeypatch.setattr(config, "CNPJ_REGRA_BAIXA", {config._cnpj_da_pasta()})
    with db.conexao() as con:
        con.execute("PRAGMA user_version=3")
        db._migrar(con)
    assert db.linhas("SELECT inicio FROM contratos WHERE id=?", (k["id"],))[0]["inicio"] == esperado
