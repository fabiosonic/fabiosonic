from swingbot import backtest, motor
from swingbot.carteira import Carteira
from swingbot.estrategia import TendenciaMM
from swingbot.modelos import COMPRAR, VENDER, Ordem
from swingbot.simulador import executar_dia


def test_backtest_gera_trade_lucrativo(cfg, tendencia):
    res = backtest.rodar(cfg, {"TEST3": tendencia})
    assert res.trades, "a tendência de alta deveria gerar ao menos um trade"
    m = backtest.metricas(res, cfg.risco.capital_teste)
    assert m["patrimonio_final"] > cfg.risco.capital_teste
    # nunca usa mais que o capital de teste
    assert min(v for _, v in res.patrimonio) > 0


def test_risco_por_trade_respeitado(cfg, tendencia):
    res = backtest.rodar(cfg, {"TEST3": tendencia})
    for t in res.trades:
        if t["motivo"] == "stop":
            assert t["resultado"] > -cfg.risco.capital_teste * cfg.risco.risco_por_operacao * 1.6


def test_saida_nao_gera_day_trade(cfg, tendencia):
    from swingbot.modelos import Posicao
    cart = Carteira(5000)
    cart.posicoes["TEST3"] = Posicao("TEST3", 100, 20.0, 10.0, 21.0, "2023-02-01")  # alvo já atingido
    data_ref = "2023-01-31"
    hist = {"TEST3": tendencia}
    ordens, avisos = motor.planejar(cfg, TendenciaMM(cfg.estrategia), cart, hist, data_ref, "2023-02-01")
    assert not [o for o in ordens if o.acao == VENDER]
    assert any("day trade" in a for a in avisos)


def test_simulador_compra_e_stop_com_gap():
    cart = Carteira(10000)
    cart.pendentes = [Ordem(COMPRAR, "X", 100, 20.0, 19.0, "entrada", "2024-01-01", alvo=22.0)]
    executar_dia(cart, {"X": {"open": 19.8, "high": 20.5, "low": 19.5, "close": 20.2}}, "2024-01-02")
    assert cart.posicoes["X"].preco_medio == 19.8
    executar_dia(cart, {"X": {"open": 18.0, "high": 18.5, "low": 17.5, "close": 18.2}}, "2024-01-03")
    assert "X" not in cart.posicoes
    assert cart.trades[-1]["preco_saida"] == 18.0   # gap: executa na abertura
    assert cart.trades[-1]["motivo"] == "stop"


def test_compra_nao_executa_se_abrir_acima():
    cart = Carteira(10000)
    cart.pendentes = [Ordem(COMPRAR, "X", 100, 20.0, 19.0, "entrada", "2024-01-01", alvo=22.0)]
    executar_dia(cart, {"X": {"open": 20.5, "high": 21.0, "low": 20.1, "close": 20.8}}, "2024-01-02")
    assert not cart.posicoes and cart.caixa == 10000


def test_kill_switch_bloqueia_entradas(cfg, tendencia):
    cart = Carteira(5000)
    cart.caixa = 4000  # -20%
    ordens, avisos = motor.planejar(cfg, TendenciaMM(cfg.estrategia), cart, {"TEST3": tendencia},
                                    tendencia.index[-1].date().isoformat())
    assert not [o for o in ordens if o.acao == COMPRAR]
    assert any("KILL SWITCH" in a for a in avisos)


def test_estado_persistente(tmp_path):
    cart = Carteira(5000, 0.0003)
    cart.comprar("2024-01-02", "X", 10, 20.0, 19.0, 22.0)
    cart.salvar(tmp_path / "c.json")
    outra = Carteira.carregar_ou_criar(tmp_path / "c.json", 1, 0)
    assert outra.posicoes["X"].quantidade == 10 and outra.caixa == cart.caixa
