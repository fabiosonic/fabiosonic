"""Analista de IA do painel (Claude).

- analisar(): leitura de mercado + ideias de operação em JSON estruturado,
  baseadas SOMENTE nos dados quantitativos do painel e na evidência dos estudos.
- conversar(): assistente para perguntas livres, com pesquisa web opcional (notícias).

Requer credencial da Anthropic (ANTHROPIC_API_KEY ou `ant auth login`).
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
MODELO = "claude-opus-5-5"
BETA_FALLBACK = "server-side-fallback-2026-07-01"   # se o modelo recusar, a API refaz em um modelo alternativo
# US$ por milhão de tokens (entrada, saída) — confira a tabela atual em claude.com/pricing
PRECOS = {"claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-haiku-5-5": (0.10, 0.50)}
PRECO_BUSCA_WEB = 0.01   # US$ por pesquisa web (US$ 10 / 1.000)


DESCRICAO_PROVEDOR = {"regras": "Analista por regras (gratuito, local)", "ollama": "Ollama (IA local, gratuita)",
                      "compativel": "API compatível (plano gratuito)", "anthropic": "Claude (pago por uso)"}


def _cfg_ia():
    from swingbot import config as config_mod
    cfg = config_mod.carregar(RAIZ / "config" / "config.yaml")
    return cfg.ia, RAIZ / cfg.pasta_estado


def _opcoes_modelo(modelo: str) -> dict:
    """fallbacks="default" só nos modelos que aceitam (o Haiku não tem fallback no servidor)."""
    if modelo.startswith(("claude-opus", "claude-fable", "claude-sonnet-5-5")):
        return {"betas": [BETA_FALLBACK], "fallbacks": "default"}
    return {}


# ------------------------------------------------------------------------ gasto
def _arq_uso() -> Path:
    return _cfg_ia()[1] / "uso_ia.json"


def custo(modelo: str, entrada: int, saida: int, buscas: int = 0, cache_lido: int = 0) -> float:
    pe, ps = PRECOS.get(modelo.split("@")[0], PRECOS[MODELO])
    return (entrada * pe + cache_lido * pe * 0.1 + saida * ps) / 1e6 + buscas * PRECO_BUSCA_WEB


def registrar_uso(tipo: str, resposta) -> float:
    u = resposta.usage
    stu = getattr(u, "server_tool_use", None)
    buscas = int(getattr(stu, "web_search_requests", 0) or 0) if stu else 0
    entrada = int(getattr(u, "input_tokens", 0) or 0) + int(getattr(u, "cache_creation_input_tokens", 0) or 0)
    lido = int(getattr(u, "cache_read_input_tokens", 0) or 0)
    saida = int(getattr(u, "output_tokens", 0) or 0)
    valor = custo(resposta.model, entrada, saida, buscas, lido)
    arq = _arq_uso()
    arq.parent.mkdir(parents=True, exist_ok=True)
    itens = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    itens.append({"quando": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "tipo": tipo, "modelo": resposta.model,
                  "entrada": entrada + lido, "saida": saida, "buscas": buscas, "custo_usd": round(valor, 4)})
    arq.write_text(json.dumps(itens[-2000:], indent=1, ensure_ascii=False), encoding="utf-8")
    return valor


def uso_mes() -> dict:
    ia_cfg, _ = _cfg_ia()
    arq = _arq_uso()
    itens = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    mes = dt.date.today().strftime("%Y-%m")
    do_mes = [i for i in itens if i["quando"].startswith(mes)]
    por_tipo: dict[str, dict] = {}
    for i in do_mes:
        t = por_tipo.setdefault(i["tipo"], {"chamadas": 0, "custo_usd": 0.0})
        t["chamadas"] += 1
        t["custo_usd"] = round(t["custo_usd"] + i["custo_usd"], 4)
    total = round(sum(i["custo_usd"] for i in do_mes), 4)
    return {"mes": mes, "gasto_usd": total, "orcamento_usd": ia_cfg.orcamento_mensal_usd,
            "provedor": ia_cfg.provedor, "gratuito": ia_cfg.provedor != "anthropic",
            "descricao": DESCRICAO_PROVEDOR.get(ia_cfg.provedor, ia_cfg.provedor),
            "chamadas": len(do_mes), "por_tipo": por_tipo, "modelo_analise": ia_cfg.modelo_analise,
            "modelo_chat": ia_cfg.modelo_chat, "ultimas": do_mes[-10:]}


def _checar_orcamento() -> None:
    u = uso_mes()
    if u["gasto_usd"] >= u["orcamento_usd"]:
        raise IAIndisponivel(f"Provedor pago bloqueado: gasto do mês US$ {u['gasto_usd']:.2f} de US$ {u['orcamento_usd']:.2f} "
                             "permitidos. Use um provedor gratuito (ia.provedor: regras, ollama ou compativel) ou "
                             "aumente 'ia.orcamento_mensal_usd'.")

SISTEMA = """Você é o analista quantitativo de um painel de investimentos em ações da B3, usado por uma
pessoa física que opera pela corretora Clear. Escreva em português do Brasil, de forma direta e técnica.

Regras:
- Baseie-se SOMENTE nos dados fornecidos em <dados> (preços, indicadores, rankings, carteira e a evidência
  histórica dos estudos de 10 anos). Não invente cotações, notícias ou números.
- Leve em conta a evidência dos estudos do próprio painel: setups de swing comprados de tendência (MACD,
  cruzamento de médias, Bollinger rompimento) tiveram desempenho próximo ou acima do CDI com queda menor; todos os
  setups vendidos perderam para o CDI; a carteira de dividendos (top 10 por dividend yield, rebalanceada) foi a
  estratégia mais consistente; momentum foi forte até 2021 e fraco depois. Diga quando uma ideia vai contra essa evidência.
- Toda ideia de operação precisa de entrada, stop, critério de saída e o risco em % até o stop.
- Respeite as regras de risco da carteira (capital de teste, risco por operação, máximo de posições, kill switch).
- Trate tudo como apoio à decisão, nunca como garantia ou recomendação individual. Seja honesto quando não houver
  boa oportunidade: "nenhuma operação" é uma resposta válida."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "resumo_mercado": {"type": "string", "description": "2 a 4 frases sobre o momento do mercado"},
        "regime": {"type": "string", "enum": ["alta", "lateral", "baixa"]},
        "postura_recomendada": {"type": "string", "description": "ex.: exposição reduzida, foco em dividendos"},
        "oportunidades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "direcao": {"type": "string", "enum": ["Compra", "Venda"]},
                    "estrategia": {"type": "string"},
                    "tese": {"type": "string"},
                    "entrada": {"type": "number"},
                    "stop": {"type": "number"},
                    "saida": {"type": "string"},
                    "risco_pct": {"type": "number", "description": "distância até o stop, em fração (0.05 = 5%)"},
                    "confianca": {"type": "string", "enum": ["baixa", "media", "alta"]},
                    "evidencia": {"type": "string", "description": "o que os estudos históricos dizem desse setup"},
                },
                "required": ["ticker", "direcao", "estrategia", "tese", "entrada", "stop", "saida",
                             "risco_pct", "confianca", "evidencia"],
                "additionalProperties": False,
            },
        },
        "alertas_carteira": {"type": "array", "items": {"type": "string"}},
        "riscos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["resumo_mercado", "regime", "postura_recomendada", "oportunidades", "alertas_carteira", "riscos"],
    "additionalProperties": False,
}


class IAIndisponivel(RuntimeError):
    pass


def _cliente():
    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise IAIndisponivel("Instale o SDK: pip install anthropic") from e
    return anthropic, anthropic.Anthropic()


def _erro_amigavel(anthropic, e: Exception) -> IAIndisponivel:
    if "authentication method" in str(e).lower():
        return IAIndisponivel("IA não configurada: defina a variável ANTHROPIC_API_KEY (ou rode `ant auth login`) "
                              "e reinicie o painel.")
    if isinstance(e, anthropic.AuthenticationError):
        return IAIndisponivel("Credencial da Anthropic inválida ou ausente. Defina ANTHROPIC_API_KEY ou rode `ant auth login`.")
    if isinstance(e, anthropic.RateLimitError):
        return IAIndisponivel("Limite de uso da API atingido. Tente novamente em instantes.")
    if isinstance(e, anthropic.APIStatusError):
        return IAIndisponivel(f"Erro da API ({e.status_code}): {e.message}")
    if isinstance(e, anthropic.APIConnectionError):
        return IAIndisponivel("Sem conexão com a API da Anthropic.")
    return IAIndisponivel(str(e))


def _texto(resposta) -> str:
    return "".join(b.text for b in resposta.content if getattr(b, "type", "") == "text")


def _dados(contexto: dict) -> str:
    return "<dados>\n" + json.dumps(contexto, ensure_ascii=False, default=str) + "\n</dados>"


def _analisar_anthropic(contexto: dict) -> dict:
    _checar_orcamento()
    modelo = _cfg_ia()[0].modelo_analise
    anthropic, cli = _cliente()
    try:
        r = cli.beta.messages.create(
            model=modelo,
            max_tokens=16000,
            **_opcoes_modelo(modelo),
            system=SISTEMA,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": ESQUEMA}},
            messages=[{"role": "user", "content": _dados(contexto) + (
                "\n\nFaça a análise do dia: leitura do mercado, alertas sobre a carteira e até 5 oportunidades "
                "com o melhor equilíbrio entre evidência histórica e risco. Use as oportunidades do scanner e a "
                "carteira-alvo de dividendos como ponto de partida.")}],
        )
    except Exception as e:  # noqa: BLE001 - convertido em mensagem para a interface
        raise _erro_amigavel(anthropic, e) from e
    gasto = registrar_uso("analise", r) if hasattr(r, "usage") else 0.0
    if r.stop_reason == "refusal":
        raise IAIndisponivel("A IA recusou esta solicitação.")
    if r.stop_reason == "max_tokens":
        raise IAIndisponivel("Resposta truncada; tente novamente.")
    dados = json.loads(_texto(r))
    dados["modelo"] = r.model
    dados["custo_usd"] = round(gasto, 4)
    return dados


def _conversar_anthropic(pergunta: str, historico: list[dict], contexto: dict, pesquisar_web: bool = False) -> dict:
    _checar_orcamento()
    modelo = _cfg_ia()[0].modelo_chat
    anthropic, cli = _cliente()
    mensagens = [{"role": m["role"], "content": m["content"]} for m in historico[-12:]
                 if m.get("role") in ("user", "assistant") and m.get("content")]
    mensagens.append({"role": "user", "content": _dados(contexto) + "\n\nPergunta: " + pergunta})
    extra = {}
    if pesquisar_web:
        extra["tools"] = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 4,
                           "user_location": {"type": "approximate", "country": "BR"}}]
    try:
        for _ in range(4):  # continua se a pesquisa web pausar o turno
            r = cli.beta.messages.create(model=modelo, max_tokens=16000, **_opcoes_modelo(modelo),
                                         system=SISTEMA + "\nResponda em até 250 palavras, com tópicos quando útil."
                                         + (" Cite as fontes das notícias." if pesquisar_web else ""),
                                         output_config={"effort": "medium"}, messages=mensagens, **extra)
            gasto = registrar_uso("chat_web" if pesquisar_web else "chat", r)
            if r.stop_reason != "pause_turn":
                break
            mensagens.append({"role": "assistant", "content": r.content})
    except Exception as e:  # noqa: BLE001
        raise _erro_amigavel(anthropic, e) from e
    if r.stop_reason == "refusal":
        raise IAIndisponivel("A IA recusou esta solicitação.")
    fontes = []
    for b in r.content:
        for c in getattr(b, "citations", None) or []:
            url = getattr(c, "url", None)
            if url and url not in [f["url"] for f in fontes]:
                fontes.append({"url": url, "titulo": getattr(c, "title", url)})
    return {"resposta": _texto(r), "fontes": fontes, "modelo": r.model, "custo_usd": round(gasto, 4)}


# ------------------------------------------------------------------------ carteiras das casas
CASAS = ("BTG Pactual, XP Investimentos, Itaú BBA, Bradesco BBI, Santander, Safra, Genial, Ágora, Goldman Sachs, "
         "JPMorgan, Morgan Stanley, UBS BB, Bank of America, Citi")

ESQUEMA_CASAS = {
    "type": "object",
    "properties": {
        "mes_referencia": {"type": "string"},
        "casas": {"type": "array", "items": {"type": "object", "properties": {
            "casa": {"type": "string"},
            "carteira": {"type": "string", "description": "nome da carteira, ex.: Top 10 Ações, Dividendos"},
            "ativos": {"type": "array", "items": {"type": "string"}, "description": "tickers da B3 (ex.: PETR4)"},
            "fonte": {"type": "string", "description": "URL da fonte"},
            "data": {"type": "string"}},
            "required": ["casa", "carteira", "ativos", "fonte", "data"], "additionalProperties": False}},
        "mais_citados": {"type": "array", "items": {"type": "object", "properties": {
            "ticker": {"type": "string"}, "casas": {"type": "integer"},
            "nomes_casas": {"type": "array", "items": {"type": "string"}}},
            "required": ["ticker", "casas", "nomes_casas"], "additionalProperties": False}},
        "observacoes": {"type": "string"},
    },
    "required": ["mes_referencia", "casas", "mais_citados", "observacoes"],
    "additionalProperties": False,
}


def _arq_casas() -> Path:
    return _cfg_ia()[1] / "carteiras_casas.json"


def carteiras_casas_cache() -> dict | None:
    arq = _arq_casas()
    return json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else None


def _casas_anthropic() -> dict:
    """1) pesquisa web com fontes; 2) estrutura o resultado em JSON. Resultado fica em cache."""
    _checar_orcamento()
    modelo = _cfg_ia()[0].modelo_analise
    anthropic, cli = _cliente()
    mes = dt.date.today().strftime("%m/%Y")
    pedido = (f"Pesquise na web as carteiras recomendadas de ações brasileiras mais recentes (mês {mes} ou o mais "
              f"recente disponível) destas casas: {CASAS}. Para cada carteira encontrada, informe a casa, o nome da "
              "carteira, os tickers da B3, a data e a URL da fonte. Use somente o que encontrar nas fontes; não invente.")
    mensagens = [{"role": "user", "content": pedido}]
    gasto = 0.0
    try:
        for _ in range(4):
            r = cli.beta.messages.create(
                model=modelo, max_tokens=16000, **_opcoes_modelo(modelo), output_config={"effort": "medium"},
                system="Você é um pesquisador de mercado de capitais brasileiro. Seja factual e cite as fontes.",
                tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 12,
                        "user_location": {"type": "approximate", "country": "BR"}}],
                messages=mensagens)
            gasto += registrar_uso("carteiras_casas", r)
            if r.stop_reason != "pause_turn":
                break
            mensagens.append({"role": "assistant", "content": r.content})
        relatorio = _texto(r)
        fontes = sorted({getattr(c, "url", "") for b in r.content for c in (getattr(b, "citations", None) or [])} - {""})
        r2 = cli.beta.messages.create(
            model=modelo, max_tokens=16000, **_opcoes_modelo(modelo),
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": ESQUEMA_CASAS}},
            messages=[{"role": "user", "content": "Converta o relatório abaixo para o formato pedido. Use apenas "
                       "informações presentes nele; tickers em maiúsculas; 'mais_citados' ordenado pelo número de "
                       f"casas.\n\nFontes citadas: {fontes}\n\n<relatorio>\n{relatorio}\n</relatorio>"}])
        gasto += registrar_uso("carteiras_casas", r2)
    except IAIndisponivel:
        raise
    except Exception as e:  # noqa: BLE001
        raise _erro_amigavel(anthropic, e) from e
    if r2.stop_reason == "refusal":
        raise IAIndisponivel("A IA recusou esta solicitação.")
    dados = json.loads(_texto(r2))
    dados.update({"atualizado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"), "fontes": fontes,
                  "custo_usd": round(gasto, 4), "modelo": r2.model})
    arq = _arq_casas()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return dados


# ======================================================================== provedores gratuitos
def _post_json(url: str, corpo: dict, cabecalhos: dict | None = None, timeout: int = 180) -> dict:
    import urllib.error
    import urllib.request
    req = urllib.request.Request(url, data=json.dumps(corpo).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **(cabecalhos or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise IAIndisponivel(f"Erro {e.code} do provedor de IA: {e.read().decode(errors='ignore')[:200]}") from e
    except urllib.error.URLError as e:
        raise IAIndisponivel(f"Provedor de IA inacessível ({url}): {e.reason}. Se for o Ollama, ele está aberto?") from e


def _llm_gratuito(mensagens: list[dict], esquema: dict | None = None) -> tuple[str, str]:
    """Chama Ollama (local) ou uma API compatível com OpenAI (Groq, OpenRouter, Gemini). Retorna (texto, modelo)."""
    import os
    cfg, _ = _cfg_ia()
    if cfg.provedor == "ollama":
        corpo = {"model": cfg.ollama_modelo, "messages": mensagens, "stream": False, "options": {"temperature": 0.2}}
        if esquema:
            corpo["format"] = esquema
        r = _post_json(cfg.ollama_url.rstrip("/") + "/api/chat", corpo)
        return r["message"]["content"], f"{cfg.ollama_modelo} (Ollama local)"
    chave = os.environ.get(cfg.compat_variavel_chave)
    if not chave:
        raise IAIndisponivel(f"Defina a variável de ambiente {cfg.compat_variavel_chave} com a chave gratuita do provedor.")
    corpo = {"model": cfg.compat_modelo, "messages": mensagens, "temperature": 0.2}
    if esquema:
        corpo["response_format"] = {"type": "json_object"}
    r = _post_json(cfg.compat_url.rstrip("/") + "/chat/completions", corpo, {"Authorization": f"Bearer {chave}"})
    return r["choices"][0]["message"]["content"], cfg.compat_modelo


def _json_da_resposta(texto: str) -> dict:
    texto = texto.strip()
    if texto.startswith("```"):
        texto = texto.strip("`").split("\n", 1)[1] if "\n" in texto else texto
    ini, fim = texto.find("{"), texto.rfind("}")
    return json.loads(texto[ini: fim + 1])


def _contexto_noticias(pergunta: str) -> tuple[str, list[dict]]:
    """Manchetes gratuitas (Google Notícias) para dar contexto atual ao assistente."""
    import re
    from . import noticias
    tickers = sorted(set(re.findall(r"\b[A-Z]{4}(?:3|4|5|6|11)\b", pergunta.upper())))
    consulta = " ".join(tickers) + " ações" if tickers else pergunta[:120]
    try:
        itens = noticias.google_noticias(consulta, 8)
    except Exception:  # noqa: BLE001
        return "", []
    texto = "\n".join(f"- {n['titulo']} ({n['fonte']}, {n['data'][:16] if n.get('data') else ''})" for n in itens)
    return texto, [{"url": n["link"], "titulo": f"{n['fonte']}: {n['titulo']}"} for n in itens]


# ======================================================================== API pública (escolhe o provedor)
def analisar(contexto: dict) -> dict:
    from . import analista_regras
    cfg, _ = _cfg_ia()
    if cfg.provedor == "anthropic":
        return _analisar_anthropic(contexto)
    base = analista_regras.analisar(contexto)
    if cfg.provedor == "regras":
        base["custo_usd"] = 0.0
        return base
    # IA gratuita: parte da análise por regras e refina o texto/ideias, sem inventar números
    pedido = (_dados(contexto) + "\n\nAnálise preliminar calculada por regras (use como base, pode reordenar ou "
              "descartar ideias, nunca invente preços):\n" + json.dumps(base, ensure_ascii=False) +
              "\n\nResponda SOMENTE com um JSON no mesmo formato da análise preliminar, com as chaves: "
              + ", ".join(ESQUEMA["required"]) + ".")
    try:
        texto, modelo = _llm_gratuito([{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}], ESQUEMA)
        dados = _json_da_resposta(texto)
        faltando = [k for k in ESQUEMA["required"] if k not in dados]
        if faltando:
            raise ValueError(f"campos ausentes: {faltando}")
        dados["modelo"], dados["custo_usd"] = modelo, 0.0
        return dados
    except (IAIndisponivel, ValueError, KeyError, json.JSONDecodeError) as e:
        base["riscos"].append(f"IA local indisponível ({e}); análise feita por regras.")
        base["custo_usd"] = 0.0
        return base


def conversar(pergunta: str, historico: list[dict], contexto: dict, pesquisar_web: bool = False) -> dict:
    from . import analista_regras
    cfg, _ = _cfg_ia()
    if cfg.provedor == "anthropic":
        return _conversar_anthropic(pergunta, historico, contexto, pesquisar_web)
    manchetes, fontes = _contexto_noticias(pergunta) if pesquisar_web else ("", [])
    if cfg.provedor == "regras":
        resposta = analista_regras.responder(pergunta, contexto)
        if manchetes:
            resposta += "\n\nNotícias recentes (Google Notícias):\n" + manchetes
        return {"resposta": resposta, "fontes": fontes, "modelo": DESCRICAO_PROVEDOR["regras"], "custo_usd": 0.0}
    msgs = [{"role": "system", "content": SISTEMA + "\nResponda em até 250 palavras."}]
    msgs += [{"role": m["role"], "content": m["content"]} for m in historico[-8:] if m.get("role") in ("user", "assistant")]
    extra = f"\n\nManchetes recentes (cite quando usar):\n{manchetes}" if manchetes else ""
    msgs.append({"role": "user", "content": _dados(contexto) + extra + "\n\nPergunta: " + pergunta})
    texto, modelo = _llm_gratuito(msgs)
    return {"resposta": texto, "fontes": fontes, "modelo": modelo, "custo_usd": 0.0}


def pesquisar_carteiras_casas() -> dict:
    """Gratuito por padrão (Google Notícias + extração). Com provedor anthropic, usa a pesquisa paga."""
    cfg, estado = _cfg_ia()
    if cfg.provedor == "anthropic":
        return _casas_anthropic()
    from . import noticias
    universo = {f.stem for f in (RAIZ / "dados_cache" / "pesquisa").glob("*.csv") if not f.stem.startswith("_")}
    dados = noticias.carteiras_recomendadas(universo or None)
    if not dados["casas"]:
        raise IAIndisponivel("Nenhuma carteira encontrada nas notícias agora. Tente novamente mais tarde.")
    arq = _arq_casas()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(dados, indent=2, ensure_ascii=False), encoding="utf-8")
    return dados
