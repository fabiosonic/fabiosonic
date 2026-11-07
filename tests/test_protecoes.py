"""Stop loss, take profit, trailing stop, breakeven e o monitor (com corretora falsa)."""
import pytest

from swingbot.monitor import Monitor
from swingbot.protecoes import Protecao, Repositorio, Trailing, avaliar, stop_desejado


def prot(**kw):
    base = dict(ticker="PETR4", quantidade=150, preco_entrada=30.0, stop=28.5)
    base.update(kw)
    return Protecao(**base)


def test_validacoes():
    with pytest.raises(ValueError):
        prot(take_profit=29.0).validar()          # alvo abaixo da entrada
    with pytest.raises(ValueError):
        prot(stop=0).validar()
    with pytest.raises(ValueError):
        prot(trailing=Trailing("atr", 2.0)).validar()   # ATR sem valor
    prot(take_profit=33.0, trailing={"tipo": "pct", "valor": 0.05}).validar()


def test_take_profit_e_stop():
    p = prot(take_profit=33.0)
    assert avaliar(p, 31.0).acao == "MANTER"
    assert avaliar(p, 33.1).acao == "TAKE_PROFIT"
    assert avaliar(prot(), 28.4).acao == "STOP_ATINGIDO"
    # com OCO o alvo já está na Clear: o monitor não vende por conta própria
    assert avaliar(prot(take_profit=33.0, usa_oco=True), 33.5).acao == "MANTER"


def test_trailing_percentual_so_sobe():
    p = prot(trailing=Trailing("pct", 0.05))
    d = avaliar(p, 32.0)                 # máxima 32 -> stop 30,40
    assert d.acao == "NOVO_STOP" and d.novo_stop == 30.40
    p.stop = d.novo_stop
    assert avaliar(p, 31.0).acao == "MANTER"   # preço caiu: stop não desce
    assert stop_desejado(p) == 30.40


def test_trailing_com_ativacao_e_atr():
    p = prot(trailing=Trailing("atr", 2.0, ativacao_pct=0.05, atr=0.5))
    assert avaliar(p, 31.0).acao == "MANTER"            # ganho 3,3% < 5%: ainda não segue
    d = avaliar(p, 32.0)                                # ganho 6,7%: stop = 32 - 2x0,5 = 31
    assert d.acao == "NOVO_STOP" and d.novo_stop == 31.0


def test_breakeven():
    p = prot(breakeven_pct=0.03)
    d = avaliar(p, 31.0)                 # +3,3% -> stop na entrada + 0,2%
    assert d.acao == "NOVO_STOP" and d.novo_stop == 30.06 and "breakeven" in d.motivo


def test_passo_minimo_evita_reenvio_constante():
    p = prot(stop=30.38, trailing=Trailing("pct", 0.05), maior_preco=32.0)
    assert avaliar(p, 32.05).acao == "MANTER"   # novo stop 30,45 é só +0,2%: não reenvia


class ClearFake:
    def __init__(self, oco=False):
        self.chamadas, self.oco = [], oco

    def suporta_oco(self):
        return self.oco

    def cancelar_stops(self, t):
        self.chamadas.append(("cancelar", t))

    def stop_venda(self, t, q, disparo, limite):
        self.chamadas.append(("stop", t, q, disparo, limite))

    def oco_venda(self, t, q, gd, gp, ld, lp):
        self.chamadas.append(("oco", t, q, gd, ld))

    def vender_limitada(self, t, q, p):
        self.chamadas.append(("venda", t, q, p))


def test_monitor_registra_stop_e_faz_trailing(tmp_path):
    repo = Repositorio(tmp_path / "p.json")
    repo.upsert(prot(trailing=Trailing("pct", 0.05)))
    hb = ClearFake()
    m = Monitor(repo, hb, log=lambda *_: None)
    m.ciclo({}, {"PETR4": (150, 30.0)})
    assert ("stop", "PETR4", 100, 28.5, 28.21) in hb.chamadas and ("stop", "PETR4F", 50, 28.5, 28.21) in hb.chamadas
    hb.chamadas.clear()
    m.ciclo({"PETR4": (32.0, 32.0)}, {"PETR4": (150, 30.0)})
    assert hb.chamadas[0] == ("cancelar", "PETR4")
    assert ("stop", "PETR4", 100, 30.4, 30.1) in hb.chamadas
    assert repo.carregar()["PETR4"].stop == 30.4


def test_monitor_take_profit_cancela_stop_e_vende(tmp_path):
    repo = Repositorio(tmp_path / "p.json")
    p = prot(take_profit=33.0)
    p.stop_enviado = True
    repo.salvar({"PETR4": p})
    hb = ClearFake()
    Monitor(repo, hb, log=lambda *_: None).ciclo({"PETR4": (33.2, 33.4)}, {"PETR4": (150, 30.0)})
    assert hb.chamadas[0] == ("cancelar", "PETR4")
    assert ("venda", "PETR4", 100, 33.1) in hb.chamadas
    assert not repo.carregar()["PETR4"].ativa


def test_monitor_usa_oco_quando_calibrado(tmp_path):
    repo = Repositorio(tmp_path / "p.json")
    repo.upsert(prot(quantidade=100, take_profit=33.0, usa_oco=True))
    hb = ClearFake(oco=True)
    Monitor(repo, hb, log=lambda *_: None).ciclo({}, {"PETR4": (100, 30.0)})
    assert ("oco", "PETR4", 100, 33.0, 28.5) in hb.chamadas


def test_monitor_encerra_quando_posicao_zera(tmp_path):
    repo = Repositorio(tmp_path / "p.json")
    p = prot()
    p.stop_enviado = True
    repo.salvar({"PETR4": p})
    Monitor(repo, ClearFake(), log=lambda *_: None).ciclo({}, {})
    assert not repo.carregar()["PETR4"].ativa


def test_simulacao_nao_envia_nem_grava(tmp_path):
    repo = Repositorio(tmp_path / "p.json")
    repo.upsert(prot(take_profit=33.0))
    eventos = Monitor(repo, None, log=lambda *_: None).ciclo({"PETR4": (33.5, 33.5)})
    assert eventos and repo.carregar()["PETR4"].ativa
