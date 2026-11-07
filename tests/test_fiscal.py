import pytest

from swingbot.fiscal import apurar, ticker_base, tipo_ativo, vendas_acoes_no_mes
from swingbot.modelos import Operacao as Op


def test_classificacao():
    assert ticker_base("PETR4F") == "PETR4"
    assert tipo_ativo("PETR4F") == "acao"
    assert tipo_ativo("AAPL34") == "bdr"
    assert tipo_ativo("BOVA11") == "etf"
    assert tipo_ativo("HGLG11", {"HGLG11": "fii"}) == "fii"


def test_isencao_ate_20_mil():
    ops = [Op("2024-03-01", "PETR4", "C", 500, 30.0), Op("2024-03-20", "PETR4", "V", 500, 36.0)]
    m = apurar(ops)[0]
    assert m.vendas_acoes == 18000
    assert m.isento and m.ganho_isento == 3000
    assert m.darf_6015 == 0


def test_tributa_acima_de_20_mil_e_irrf():
    ops = [Op("2024-03-01", "VALE3", "C", 1000, 60.0), Op("2024-03-20", "VALE3", "V", 1000, 65.0)]
    m = apurar(ops)[0]
    assert not m.isento
    assert m.base_comum == 5000
    assert m.irrf_mes == pytest.approx(3.25)          # 0,005% de 65.000
    assert m.darf_6015 == pytest.approx(750 - 3.25)


def test_prejuizo_compensa_mes_seguinte_mesmo_em_mes_isento():
    ops = [
        Op("2024-01-02", "PETR4", "C", 300, 40.0), Op("2024-01-10", "PETR4", "V", 300, 35.0),   # -1500 (isento)
        Op("2024-02-01", "VALE3", "C", 1000, 60.0), Op("2024-02-20", "VALE3", "V", 1000, 63.0),  # +3000
    ]
    jan, fev = apurar(ops)
    assert jan.prejuizo_comum_acumulado == 1500
    assert fev.base_comum == 1500
    assert fev.prejuizo_comum_acumulado == 0


def test_day_trade_separado_e_20_por_cento():
    ops = [Op("2024-05-02", "PETR4", "C", 100, 30.0), Op("2024-05-02", "PETR4", "V", 100, 33.0)]
    m = apurar(ops)[0]
    assert m.resultado_day_trade == 300
    assert m.resultado_comum_acoes == 0
    assert m.irrf_mes == pytest.approx(3.0)            # 1% do ganho diário
    assert m.darf_6015 == pytest.approx(60 - 3)


def test_darf_abaixo_de_10_acumula():
    ops = [Op("2024-06-03", "BOVA11", "C", 10, 100.0), Op("2024-06-20", "BOVA11", "V", 10, 105.0)]
    m = apurar(ops)[0]
    assert m.darf_6015 == 0 and m.valor_acumulado_proximo_mes == pytest.approx(7.5)


def test_custo_medio_e_custos():
    ops = [Op("2024-07-01", "ITUB4", "C", 100, 30.0, custos=1.0),
           Op("2024-07-05", "ITUB4", "C", 100, 32.0, custos=1.0),
           Op("2024-07-30", "ITUB4", "V", 200, 33.0, custos=2.0)]
    m = apurar(ops)[0]
    assert m.resultado_comum_acoes == pytest.approx(6600 - 2 - 6202)


def test_vendas_no_mes():
    ops = [Op("2024-03-20", "PETR4", "V", 100, 30.0), Op("2024-03-21", "BOVA11", "V", 10, 100.0),
           Op("2024-04-01", "PETR4", "V", 100, 30.0)]
    assert vendas_acoes_no_mes(ops, "2024-03") == 3000
