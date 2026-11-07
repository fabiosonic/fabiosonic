"""Painel: fila de ordens, IA (com cliente falso) e endpoints principais."""
import json
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from painel import dados_painel as dp  # noqa: E402
from painel import ia  # noqa: E402


@pytest.fixture
def fila_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(dp, "_arq_fila", lambda: tmp_path / "fila.json")
    return tmp_path / "fila.json"


def test_fila_valida_e_remove(fila_tmp):
    item = dp.adicionar_fila({"ticker": "petr4", "lado": "c", "quantidade": 10, "preco": 30})
    assert item["ticker"] == "PETR4" and item["lado"] == "C" and item["status"] == "aguardando robô"
    with pytest.raises(ValueError):
        dp.adicionar_fila({"ticker": "PETR4", "lado": "C", "quantidade": 0, "preco": 30})
    with pytest.raises(ValueError):
        dp.adicionar_fila({"ticker": "PETR4", "lado": "C", "quantidade": 5, "preco": 30, "tipo": "stop"})
    assert dp.remover_fila(item["id"]) and dp.fila() == []


class _Fake:
    def __init__(self, resposta):
        self.kwargs = None
        self.resposta = resposta
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.kwargs = kwargs
        return self.resposta


def test_ia_analisar_usa_saida_estruturada(monkeypatch):
    conteudo = {"resumo_mercado": "x", "regime": "baixa", "postura_recomendada": "cautela", "oportunidades": [],
                "alertas_carteira": [], "riscos": ["r"]}
    fake = _Fake(SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                                 content=[SimpleNamespace(type="text", text=json.dumps(conteudo))]))
    monkeypatch.setattr(ia, "_cliente", lambda: (None, fake))
    out = ia.analisar({"mercado": {}})
    assert out["regime"] == "baixa" and out["modelo"] == "claude-opus-5-5"
    k = fake.kwargs
    assert k["model"] == "claude-opus-5-5" and k["fallbacks"] == "default"
    assert k["output_config"]["format"]["type"] == "json_schema"
    assert "<dados>" in k["messages"][0]["content"]


def test_ia_recusa_vira_erro_amigavel(monkeypatch):
    fake = _Fake(SimpleNamespace(stop_reason="refusal", model="m", content=[]))
    monkeypatch.setattr(ia, "_cliente", lambda: (None, fake))
    with pytest.raises(ia.IAIndisponivel):
        ia.analisar({})


def test_endpoints_basicos():
    if not dp.PESQ.exists():
        pytest.skip("sem dados de pesquisa baixados")
    from painel.servidor import app
    c = TestClient(app)
    assert c.get("/").status_code == 200
    r = c.get("/api/resumo").json()
    assert "patrimonio" in r and "mercado" in r
    rk = c.get("/api/ranking").json()
    assert len(rk["carteiras_alvo"]["dividendos"]) == 10
    assert c.get("/api/grafico/NAOEXISTE").status_code == 404
    assert c.get("/api/rebalanceamento?estrategia=xyz").status_code == 400
