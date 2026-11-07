"""Modo real com uma corretora falsa: valida reconciliação e proteção por stop."""
from swingbot import executor
from swingbot.carteira import Carteira
from swingbot.modelos import COMPRAR, VENDER, Ordem, Posicao


class CorretoraFake:
    def __init__(self):
        self.chamadas = []

    def cancelar_stops(self, t):
        self.chamadas.append(("cancelar", t))
        return 0

    def stop_venda(self, t, q, disparo, limite):
        self.chamadas.append(("stop", t, q, disparo, limite))

    def vender_limitada(self, t, q, p):
        self.chamadas.append(("venda", t, q, p))

    def comprar_limitada(self, t, q, p):
        self.chamadas.append(("compra", t, q, p))


def log(_):
    pass


def test_compra_executada_recebe_stop(cfg):
    cart = Carteira(5000)
    cart.pendentes = [Ordem(COMPRAR, "PETR4", 130, 30.0, 28.0, "entrada", "2024-01-01", 34.0, "2024-01-02")]
    bloq = executor.reconciliar(cart, {"PETR4": (130, 29.9)}, "2024-01-02", ["PETR4"], log)
    assert not bloq and cart.posicoes["PETR4"].quantidade == 130
    fake = CorretoraFake()
    executor.proteger(cart, fake, cfg, log)
    stops = [c for c in fake.chamadas if c[0] == "stop"]
    assert stops == [("stop", "PETR4", 100, 28.0, 27.72), ("stop", "PETR4F", 30, 28.0, 27.72)]
    assert cart.posicoes["PETR4"].stop_enviado


def test_stop_executado_na_corretora_baixa_posicao():
    cart = Carteira(5000)
    cart.posicoes["VALE3"] = Posicao("VALE3", 50, 60.0, 57.0, 66.0, "2024-01-02", True)
    executor.reconciliar(cart, {}, "2024-01-10", ["VALE3"], log)
    assert "VALE3" not in cart.posicoes
    assert cart.operacoes[-1].origem == "stop" and cart.operacoes[-1].estimado


def test_posicao_manual_bloqueia_ativo():
    cart = Carteira(5000)
    bloq = executor.reconciliar(cart, {"ITUB4": (200, 30.0)}, "2024-01-10", ["ITUB4"], log)
    assert bloq == {"ITUB4"} and not cart.posicoes


def test_venda_cancela_stop_antes(cfg):
    cart = Carteira(5000)
    cart.posicoes["VALE3"] = Posicao("VALE3", 150, 60.0, 57.0, 66.0, "2024-01-02", True)
    fake = CorretoraFake()
    executor.executar_ordens(cart, [Ordem(VENDER, "VALE3", 150, 65.0, None, "alvo", "2024-01-09")],
                             fake, "2024-01-10", log)
    assert fake.chamadas[0] == ("cancelar", "VALE3")
    assert ("venda", "VALE3", 100, 65.0) in fake.chamadas and ("venda", "VALE3F", 50, 65.0) in fake.chamadas
    # venda executou
    executor.reconciliar(cart, {}, "2024-01-10", ["VALE3"], log)
    assert "VALE3" not in cart.posicoes and cart.operacoes[-1].origem == "alvo"


def test_seletores_pendentes_bloqueiam_modo_real():
    from swingbot.corretoras.clear_homebroker import carregar_seletores, numero_br, pendencias
    assert pendencias(carregar_seletores("config/seletores_clear.yaml"))
    assert numero_br("R$ 1.234,56") == 1234.56 and numero_br("300") == 300
