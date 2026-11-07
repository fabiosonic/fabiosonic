"""Alertas de reversão de tendência e saída automática no monitor."""
import numpy as np

from swingbot.monitor import Monitor
from swingbot.protecoes import Protecao, Repositorio
from swingbot.reversao import SAIR, avaliar, com_preco_atual
from tests.conftest import barras


def alta_continua():
    rng = np.random.default_rng(1)
    return barras(np.linspace(20, 40, 300) + rng.normal(0, 0.05, 300))


def alta_e_queda_forte():
    p = list(np.linspace(20, 40, 280)) + list(np.linspace(40, 30, 20))   # cai 25% em 20 pregões
    return barras(np.array(p))


def test_tendencia_intacta_nao_alerta():
    d = avaliar(alta_continua())
    assert d.nivel == "OK" and d.pontos == 0


def test_queda_forte_manda_sair():
    d = avaliar(alta_e_queda_forte(), maior_preco=40.0)
    assert d.nivel == SAIR
    assert any("MME21" in s for s in d.sinais) and any("ATR" in s for s in d.sinais)


def test_preco_intradiario_entra_como_candle_de_hoje():
    df = alta_continua()
    hoje = df.index[-1] + np.timedelta64(1, "D")
    novo = com_preco_atual(df, 25.0, hoje)
    assert len(novo) == len(df) + 1 and novo["close"].iloc[-1] == 25.0
    assert avaliar(novo, maior_preco=40.0).nivel == SAIR   # despencou hoje: sair


class ClearFake:
    def __init__(self):
        self.chamadas = []

    def suporta_oco(self):
        return False

    def cancelar_stops(self, t):
        self.chamadas.append(("cancelar", t))

    def stop_venda(self, *a):
        self.chamadas.append(("stop",) + a)

    def vender_limitada(self, t, q, p):
        self.chamadas.append(("venda", t, q, p))


def _repo(tmp_path, na_reversao):
    repo = Repositorio(tmp_path / "p.json")
    p = Protecao("TEST3", 100, 35.0, 20.0, na_reversao=na_reversao, maior_preco=40.0)
    p.stop_enviado = True
    repo.salvar({"TEST3": p})
    return repo


def test_monitor_avisa_sem_vender(tmp_path):
    repo, hb = _repo(tmp_path, "avisar"), ClearFake()
    logs = []
    Monitor(repo, hb, log=logs.append, fonte_diaria=lambda t: alta_e_queda_forte()).ciclo(
        {"TEST3": (30.0, 30.5)}, {"TEST3": (100, 35.0)})
    assert any("REVERSÃO SAIR" in m and "considere sair" in m for m in logs)
    assert not [c for c in hb.chamadas if c[0] == "venda"]
    assert repo.carregar()["TEST3"].ultimo_alerta["nivel"] == SAIR


def test_monitor_vende_na_reversao_quando_configurado(tmp_path):
    repo, hb = _repo(tmp_path, "vender"), ClearFake()
    Monitor(repo, hb, log=lambda *_: None, fonte_diaria=lambda t: alta_e_queda_forte()).ciclo(
        {"TEST3": (30.0, 30.5)}, {"TEST3": (100, 35.0)})
    assert ("venda", "TEST3", 100, 29.91) in hb.chamadas
    assert not repo.carregar()["TEST3"].ativa


def test_alerta_nao_repete_no_mesmo_nivel(tmp_path):
    repo, hb = _repo(tmp_path, "avisar"), ClearFake()
    logs = []
    m = Monitor(repo, hb, log=logs.append, fonte_diaria=lambda t: alta_e_queda_forte(), intervalo_reversao_seg=0)
    m.ciclo({"TEST3": (30.0, 30.5)}, {"TEST3": (100, 35.0)})
    m.ciclo({"TEST3": (30.0, 30.5)}, {"TEST3": (100, 35.0)})
    assert sum("REVERSÃO" in x for x in logs) == 1
