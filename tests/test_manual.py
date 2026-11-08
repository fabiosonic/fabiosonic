"""Modo manual: o painel indica, você executa na Clear e registra; o painel acompanha e orienta."""
import pytest

from painel import dados_painel as dp
from swingbot import config as config_mod


@pytest.fixture
def ambiente(tmp_path, monkeypatch):
    cfg = config_mod.carregar("config/config.yaml")
    cfg.pasta_estado = str(tmp_path)
    cfg.modo = "manual"
    monkeypatch.setattr(dp, "_cfg", lambda: cfg)
    monkeypatch.setattr(dp, "RAIZ", tmp_path.parent)
    monkeypatch.setattr(dp, "paineis", lambda: (_ for _ in ()).throw(RuntimeError("sem dados")))
    precos = {}
    monkeypatch.setattr(dp, "precos_atuais", lambda ts: {t: precos[t] for t in ts if t in precos})
    return precos


def test_fluxo_manual_completo(ambiente):
    precos = ambiente
    dp.registrar_compra({"ticker": "petr4", "quantidade": 100, "preco": 40.0, "stop": 38.0, "take_profit": 46.0,
                         "trailing": {"tipo": "pct", "valor": 0.05, "ativacao_pct": 0.03}, "stop_na_clear": True})
    # preço subiu 10%: trailing sugere subir o stop para 44 x 0,95 = 41,80
    precos["PETR4"] = (44.0, 44.0, "teste")
    acoes = dp.acoes_manuais()["acoes"]
    assert acoes[0]["acao"] == "SUBIR_STOP" and acoes[0]["novo_stop"] == 41.8
    dp.ajustar_stop("PETR4", 41.8)                     # você subiu o stop na Clear
    a = dp.acoes_manuais()["acoes"]
    assert [x["veredito"] for x in a] == ["MANTER"]    # nada pendente: instrução clara de manter
    precos["PETR4"] = (46.5, 46.6, "teste")           # bateu o alvo
    assert dp.acoes_manuais()["acoes"][0]["veredito"] == "VENDER"
    trade = dp.registrar_venda({"ticker": "PETR4", "quantidade": 100, "preco": 46.5})
    assert trade["resultado"] > 600                    # (46,5 - 40) x 100 - custos
    assert dp.acoes_manuais()["acompanhando"] == 0


def test_lembra_de_colocar_stop_e_valida(ambiente):
    precos = ambiente
    with pytest.raises(ValueError, match="stop"):
        dp.registrar_compra({"ticker": "VALE3", "quantidade": 10, "preco": 60.0})
    dp.registrar_compra({"ticker": "VALE3", "quantidade": 10, "preco": 60.0, "stop": 55.0, "stop_na_clear": False})
    precos["VALE3"] = (60.5, 60.5, "teste")
    a = dp.acoes_manuais()["acoes"]
    assert a[0]["acao"] == "COLOCAR_STOP" and "55,00" in a[0]["texto"]
    with pytest.raises(ValueError):
        dp.registrar_venda({"ticker": "VALE3", "quantidade": 11, "preco": 61})


def test_compra_adicional_faz_preco_medio(ambiente):
    dp.registrar_compra({"ticker": "ITUB4", "quantidade": 100, "preco": 30.0, "stop": 28.0})
    p = dp.registrar_compra({"ticker": "ITUB4", "quantidade": 100, "preco": 32.0, "stop": 29.0})
    assert p["quantidade"] == 200 and p["preco_entrada"] == 31.0


def test_toda_posicao_tem_veredito_claro(ambiente):
    precos = ambiente
    dp.registrar_compra({"ticker": "BRAP4", "quantidade": 38, "preco": 19.15, "stop": 17.85, "take_profit": 21.75})
    precos["BRAP4"] = (19.25, 19.3, "teste")
    a = dp.acoes_manuais()["acoes"]
    assert a and all(x["veredito"] in ("VENDER", "SUBIR O STOP", "COLOCAR O STOP", "MANTER") for x in a)


def test_uma_linha_por_ativo_com_a_ordem_mais_importante(ambiente):
    precos = ambiente
    dp.registrar_compra({"ticker": "PETR4", "quantidade": 100, "preco": 40.0, "stop": 38.0, "take_profit": 44.5,
                         "stop_na_clear": False})
    precos["PETR4"] = (45.24, 45.3, "teste")           # alvo atingido E sem stop na Clear
    a = dp.acoes_manuais()["acoes"]
    assert len(a) == 1 and a[0]["veredito"] == "VENDER"
    assert "45,24" in a[0]["texto"] and "44,50" in a[0]["texto"]          # formato brasileiro
    assert any("STOP" in c for c in a[0]["complemento"])


def test_vender_nao_vem_com_conselho_de_manter(ambiente):
    itens = [{"ticker": "X", "veredito": "VENDER", "acao": "VENDER", "urgencia": 0, "texto": "Alvo atingido (45.24)"},
             {"ticker": "X", "veredito": "MANTER", "acao": "ATENCAO", "urgencia": 3, "texto": "Mantenha...",
              "sinais": ["abaixo da MME21 (51.31)"]}]
    a = dp._consolidar(itens)
    assert len(a) == 1 and "complemento" not in a[0] and "45,24" in a[0]["texto"]
