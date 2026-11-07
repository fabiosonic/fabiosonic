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


def test_custo_e_orcamento(tmp_path, monkeypatch):
    # Opus 5.5: US$ 4 / 20 por milhão; 5.000 tokens de entrada + 4.000 de saída = US$ 0,10
    assert ia.custo("claude-opus-5-5", 5000, 4000) == pytest.approx(0.10)
    assert ia.custo("claude-haiku-5-5", 5000, 4000) == pytest.approx(0.0025)
    assert ia.custo("claude-opus-5-5", 0, 0, buscas=3) == pytest.approx(0.03)
    arq = tmp_path / "uso.json"
    monkeypatch.setattr(ia, "_arq_uso", lambda: arq)
    uso = SimpleNamespace(input_tokens=5000, output_tokens=4000, cache_creation_input_tokens=0,
                          cache_read_input_tokens=0, server_tool_use=SimpleNamespace(web_search_requests=2))
    assert ia.registrar_uso("chat_web", SimpleNamespace(usage=uso, model="claude-opus-5-5")) == pytest.approx(0.12)
    u = ia.uso_mes()
    assert u["gasto_usd"] == pytest.approx(0.12) and u["por_tipo"]["chat_web"]["chamadas"] == 1
    cfg = SimpleNamespace(orcamento_mensal_usd=0.10, modelo_analise="claude-opus-5-5", modelo_chat="claude-opus-5-5")
    monkeypatch.setattr(ia, "_cfg_ia", lambda: (cfg, tmp_path))
    with pytest.raises(ia.IAIndisponivel, match="Orçamento"):
        ia.analisar({})


def test_haiku_sem_fallback_no_servidor():
    assert ia._opcoes_modelo("claude-haiku-5-5") == {}
    assert ia._opcoes_modelo("claude-sonnet-5-5")["fallbacks"] == "default"
