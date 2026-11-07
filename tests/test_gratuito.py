"""Modo 100% gratuito: analista por regras, Ollama/compatível e carteiras via notícias."""
import json
from types import SimpleNamespace

from painel import analista_regras, ia, noticias

CTX = {
    "mercado": {"ibov_acima_mm200": False, "ibov_dist_mm200": -0.07, "cdi_aa": 0.137, "ibov_12m": 0.13},
    "carteira": {"posicoes": [{"ticker": "WEGE3", "stop_enviado": False}], "kill_switch": False, "risco_aberto_pct": 0.01},
    "scanner_oportunidades": [
        {"ticker": "BRAP4", "direcao": "Compra", "setup": "MACD cruzamento", "gatilho": "MACD cruzou", "entrada": 19.15,
         "stop": 17.85, "risco_pct": 0.068, "saida": "cruzamento inverso", "acima_mm200": True,
         "evidencia": {"excesso_cdi_aa": 0.077, "metade1": 0.156, "metade2": -0.001}},
        {"ticker": "PETR4", "direcao": "Compra", "setup": "IFR2", "gatilho": "IFR2 < 10", "entrada": 45.3, "stop": 41.0,
         "risco_pct": 0.09, "saida": "x", "acima_mm200": True, "evidencia": {"excesso_cdi_aa": -0.014}},
    ],
    "ranking_resumido": [
        {"ticker": "VALE3", "preco": 64.04, "top_dividendos": True, "alerta_dy": False, "dy_12m": 0.088, "vol_anual": 0.28},
        {"ticker": "CYRE3", "preco": 19.3, "top_dividendos": True, "alerta_dy": True, "dy_12m": 0.14, "vol_anual": 0.6},
    ],
    "consenso_top": [{"ticker": "VALE3", "recomendacao": "Compra", "nota_media": 2.4, "upside": 0.35, "analistas": 10,
                      "alvo_medio": 86.6}],
    "alertas": [{"ticker": "PETR4", "nivel": "SAIR", "sinais": ["MACD caindo", "abaixo da MME21"]}],
}


def test_analista_por_regras():
    a = analista_regras.analisar(CTX)
    assert a["regime"] == "baixa" and "Defensiva" in a["postura_recomendada"]
    tick = [o["ticker"] for o in a["oportunidades"]]
    assert "BRAP4" in tick and "VALE3" in tick
    assert "PETR4" not in tick          # setup com evidência negativa fica de fora
    assert "CYRE3" not in tick          # armadilha de dividendos fica de fora
    assert any("PETR4" in x and "reversão" in x for x in a["alertas_carteira"])
    assert any("WEGE3" in x and "sem stop" in x for x in a["alertas_carteira"])
    assert any("CYRE3" in r for r in a["riscos"])


def test_assistente_por_regras_responde_sobre_ticker():
    r = analista_regras.responder("O que acha de VALE3?", CTX)
    assert "VALE3" in r and "consenso Compra" in r


def _cfg(provedor):
    return SimpleNamespace(provedor=provedor, ollama_url="http://localhost:11434", ollama_modelo="qwen2.5:7b",
                           compat_url="https://x/v1", compat_modelo="m", compat_variavel_chave="IA_API_KEY",
                           orcamento_mensal_usd=0.0, modelo_analise="", modelo_chat="")


def test_provedor_regras_nao_chama_rede(monkeypatch, tmp_path):
    monkeypatch.setattr(ia, "_cfg_ia", lambda: (_cfg("regras"), tmp_path))
    monkeypatch.setattr(ia, "_post_json", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria chamar")))
    a = ia.analisar(CTX)
    assert a["custo_usd"] == 0.0 and "regras" in a["modelo"]


def test_ollama_refina_analise(monkeypatch, tmp_path):
    monkeypatch.setattr(ia, "_cfg_ia", lambda: (_cfg("ollama"), tmp_path))
    chamadas = {}

    def falso(url, corpo, cab=None, timeout=180):
        chamadas["url"], chamadas["corpo"] = url, corpo
        resp = {"resumo_mercado": "ok", "regime": "baixa", "postura_recomendada": "p", "oportunidades": [],
                "alertas_carteira": [], "riscos": []}
        return {"message": {"content": "```json\n" + json.dumps(resp) + "\n```"}}

    monkeypatch.setattr(ia, "_post_json", falso)
    a = ia.analisar(CTX)
    assert chamadas["url"].endswith("/api/chat") and chamadas["corpo"]["format"]["type"] == "object"
    assert a["resumo_mercado"] == "ok" and "Ollama" in a["modelo"] and a["custo_usd"] == 0.0


def test_ia_local_falhando_cai_para_regras(monkeypatch, tmp_path):
    monkeypatch.setattr(ia, "_cfg_ia", lambda: (_cfg("ollama"), tmp_path))
    monkeypatch.setattr(ia, "_post_json", lambda *a, **k: {"message": {"content": "não sei responder em JSON"}})
    a = ia.analisar(CTX)
    assert a["oportunidades"] and any("IA local indisponível" in r for r in a["riscos"])


def test_compativel_exige_chave(monkeypatch, tmp_path):
    monkeypatch.setattr(ia, "_cfg_ia", lambda: (_cfg("compativel"), tmp_path))
    monkeypatch.delenv("IA_API_KEY", raising=False)
    a = ia.analisar(CTX)                      # sem chave: análise por regras, sem erro
    assert any("IA_API_KEY" in r for r in a["riscos"])


def test_extracao_de_tickers_e_casas():
    html = "<html><nav>PETR4 VALE3</nav><p>A carteira tem ITUB4, BBAS3 e ITUB4.</p><script>WEGE3</script></html>"
    texto = noticias.texto_da_pagina(html)
    assert "PETR4" not in texto and "WEGE3" not in texto
    assert noticias.tickers_do_texto(texto, {"ITUB4"}) == {"ITUB4": 2}   # BBAS3 fora do universo e citado 1x
    assert noticias._casa_do_titulo("BTG revela 10 ações para novembro") == "BTG Pactual"
    assert noticias._casa_do_titulo("Quer dividendos? XP revela suas 11 ações") == "XP"
    assert noticias._casa_do_titulo("Ibovespa sobe com exterior") is None


def test_carteiras_recomendadas_sem_rede(monkeypatch):
    materias = [{"titulo": "BTG revela carteira de novembro", "fonte": "InfoMoney", "link": "L1", "data": "Tue, 03 Nov 2026"},
                {"titulo": "Carteiras recomendadas de novembro", "fonte": "ADVFN", "link": "L2", "data": "Tue, 03 Nov 2026"},
                {"titulo": "FIIs recomendados para novembro", "fonte": "X", "link": "L3", "data": ""}]
    monkeypatch.setattr(noticias, "google_noticias", lambda q, n=10: materias)
    monkeypatch.setattr(noticias, "decodificar", lambda link: f"https://site/{link}")
    paginas = {"https://site/L1": "<p>PETR4 VALE3</p>", "https://site/L2": "<p>PETR4 WEGE3</p>"}
    monkeypatch.setattr(noticias, "_baixar", lambda url, timeout=20: paginas[url])
    import datetime as dt
    r = noticias.carteiras_recomendadas({"PETR4", "VALE3", "WEGE3"}, dt.date(2026, 11, 7), log=lambda *_: None)
    assert [c["casa"] for c in r["casas"]] == ["BTG Pactual", "Consolidado (ADVFN)"]
    top = r["mais_citados"][0]
    assert top["ticker"] == "PETR4" and top["casas"] == 1 and top["materias"] == 2
    assert r["custo_usd"] == 0.0
