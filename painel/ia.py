"""Analista de IA do painel (Claude).

- analisar(): leitura de mercado + ideias de operação em JSON estruturado,
  baseadas SOMENTE nos dados quantitativos do painel e na evidência dos estudos.
- conversar(): assistente para perguntas livres, com pesquisa web opcional (notícias).

Requer credencial da Anthropic (ANTHROPIC_API_KEY ou `ant auth login`).
"""
from __future__ import annotations

import json

MODELO = "claude-opus-5-5"
BETAS = ["server-side-fallback-2026-07-01"]   # se o modelo recusar, a API refaz em um modelo alternativo

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


def analisar(contexto: dict) -> dict:
    anthropic, cli = _cliente()
    try:
        r = cli.beta.messages.create(
            model=MODELO,
            max_tokens=16000,
            betas=BETAS,
            fallbacks="default",
            system=SISTEMA,
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": ESQUEMA}},
            messages=[{"role": "user", "content": _dados(contexto) + (
                "\n\nFaça a análise do dia: leitura do mercado, alertas sobre a carteira e até 5 oportunidades "
                "com o melhor equilíbrio entre evidência histórica e risco. Use as oportunidades do scanner e a "
                "carteira-alvo de dividendos como ponto de partida.")}],
        )
    except Exception as e:  # noqa: BLE001 - convertido em mensagem para a interface
        raise _erro_amigavel(anthropic, e) from e
    if r.stop_reason == "refusal":
        raise IAIndisponivel("A IA recusou esta solicitação.")
    if r.stop_reason == "max_tokens":
        raise IAIndisponivel("Resposta truncada; tente novamente.")
    dados = json.loads(_texto(r))
    dados["modelo"] = r.model
    return dados


def conversar(pergunta: str, historico: list[dict], contexto: dict, pesquisar_web: bool = False) -> dict:
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
            r = cli.beta.messages.create(model=MODELO, max_tokens=16000, betas=BETAS, fallbacks="default",
                                         system=SISTEMA + "\nResponda em até 250 palavras, com tópicos quando útil."
                                         + (" Cite as fontes das notícias." if pesquisar_web else ""),
                                         output_config={"effort": "medium"}, messages=mensagens, **extra)
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
    return {"resposta": _texto(r), "fontes": fontes, "modelo": r.model}
