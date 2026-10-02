"""DRE estruturada, indicadores, livro caixa e fluxo de caixa mensal."""

from datetime import date

from nfse_itaborai import config, contabil, financeiro
from test_emissor import Simulador, ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, CLI_B, base  # noqa: F401  (fixture)

EM = date(2026, 10, 2)


def _conta(d, nome):
    return next(l for l in d["linhas"] if l["conta"] == nome)


def _cenario():
    config.salvar({"financeiro": {"aliquota_simples_pct": 6.0, "iss_fixo": False}})
    t1 = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "1000", vencimento="2026-09-10", competencia="2026-09", emitir_nfse=False)
    financeiro.criar_titulo(CLI_B["cpf_cnpj"], "500", vencimento="2026-09-20", competencia="2026-09", emitir_nfse=False)
    financeiro.baixar(t1, "2026-09-12", "1000")
    for desc, cat, val, venc in [("Aluguel sala", "Aluguel", "300", "2026-09-05"), ("Folha setembro", "Folha", "400", "2026-09-05"),
                                 ("DAS 08/2026", "Impostos", "90", "2026-09-20"), ("Tarifa pacote", "Bancárias", "10", "2026-09-30")]:
        did = financeiro.salvar_despesa({"descricao": desc, "valor": val, "vencimento": venc, "categoria": cat})
        financeiro.pagar_despesa(did, venc)


def test_dre_estrutura_sem_dupla_deducao_do_das(base):  # noqa: F811
    _cenario()
    d = contabil.dre(2026, EM)
    set_ = lambda nome: _conta(d, nome)["valores"][8]  # noqa: E731
    assert set_("RECEITA OPERACIONAL BRUTA") == 150000
    assert set_("Simples Nacional (DAS estimado)") == -9000            # 6% sobre 1.500,00 (sem histórico)
    assert set_("(=) RECEITA OPERACIONAL LÍQUIDA") == 141000
    assert set_("(−) DESPESAS COM PESSOAL") == -40000 and set_("(−) DESPESAS DE OCUPAÇÃO") == -30000
    assert not any(l["conta"] == "(−) DESPESAS TRIBUTÁRIAS" for l in d["linhas"])   # DAS pago não volta como despesa
    assert set_("(=) RESULTADO OPERACIONAL") == 71000
    assert set_("(−) DESPESAS FINANCEIRAS") == -1000
    assert set_("(=) RESULTADO LÍQUIDO DO PERÍODO") == 70000
    assert d["resumo"]["margem_liquida"] == 46.7 and _conta(d, "(=) RECEITA OPERACIONAL LÍQUIDA")["av"] == 94.0
    assert [l["conta"] for l in d["linhas"]][-1] == "(=) RESULTADO LÍQUIDO DO PERÍODO"


def test_iss_fixo_mensal_deduzido_quando_nao_ha_lancamento(base):  # noqa: F811
    _cenario()
    config.salvar({"financeiro": {"iss_fixo_mensal": "120,00"}})
    d = contabil.dre(2026, EM)
    assert _conta(d, "ISS")["valores"][8] == -12000 and _conta(d, "ISS")["valores"][9] == 0   # sem receita, sem ISS


def test_livro_caixa_cronologico_com_saldo(base):  # noqa: F811
    _cenario()
    lc = contabil.livro_caixa("2026-09-01", "2026-09-30")
    assert [m["data"] for m in lc["movimentos"]] == sorted(m["data"] for m in lc["movimentos"])
    assert lc["entradas"] == 100000 and lc["saidas"] == 80000 and lc["saldo"] == 20000
    assert lc["movimentos"][-1]["saldo"] == 20000


def test_fluxo_mensal_realizado_e_projetado(base):  # noqa: F811
    _cenario()
    financeiro.salvar_contrato({"cpf_cnpj": CLI_A["cpf_cnpj"], "valor": "1000", "inicio": "2026-11", "dia_vencimento": 10})
    f = {x["mes"]: x for x in contabil.fluxo_mensal(EM)}
    assert f["2026-09"]["tipo"] == "realizado" and f["2026-09"]["entradas"] == 100000 and f["2026-09"]["saidas"] == 80000
    assert f["2026-10"]["tipo"] == "atual" and f["2026-10"]["entradas"] == 50000      # vencido há 12 dias ainda entra
    assert f["2026-11"]["tipo"] == "projetado" and f["2026-11"]["entradas"] == 100000
    assert f["2026-11"]["saidas_estimadas"] and f["2026-11"]["saidas"] > 0             # média dos meses realizados


def test_indicadores(base):  # noqa: F811
    _cenario()
    i = contabil.indicadores(EM)
    assert i["faturamento_12m"] == 150000 and i["clientes_ativos"] == 2
    assert i["recebido_em_dia_pct"] == 0.0 and i["atraso_medio_ponderado"] == 2.0
    assert i["top_clientes"][0]["pct"] == 66.7 and i["clientes_classe_a"] == 2
    assert i["inadimplencia_90d"] == 33.3
