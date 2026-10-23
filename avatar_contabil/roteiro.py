"""Etapas 2 e 3: triagem das pautas e roteiro com o Claude."""
from __future__ import annotations

import json

from . import config
from .modelos import Pauta, Roteiro, Triagem

SISTEMA = """Você é roteirista de vídeos curtos de um escritório de contabilidade brasileiro.
O vídeo é falado por um avatar de IA do contador responsável e um contador humano revisa \
o roteiro antes de publicar.

Regras que não podem ser quebradas:
- Afirme apenas o que está na pauta recebida. Se faltar dado (data, alíquota, número da norma), \
não invente: escreva de forma genérica e registre a dúvida em pontos_a_verificar.
- Publicidade sóbria e informativa, conforme o Código de Ética do contador (NBC PG 01): \
nada de promessa de resultado, economia garantida, sensacionalismo, comparação com concorrentes \
ou incentivo a evasão fiscal.
- Linguagem simples, em português do Brasil, falando direto com o empresário ("você").
- Não dê consultoria individual; termine reforçando que cada caso precisa de análise."""


def _cliente():
    import anthropic

    return anthropic.Anthropic()


def _chamar(cfg: dict, prompt: str, formato, esforco: str):
    resp = _cliente().beta.messages.parse(
        model=cfg["roteiro"]["modelo"],
        max_tokens=16000,
        system=SISTEMA,
        messages=[{"role": "user", "content": prompt}],
        output_format=formato,
        output_config={"effort": esforco},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("O modelo recusou a solicitação; revise a pauta manualmente.")
    return resp.parsed_output


def triar(cfg: dict, pautas: list[Pauta]) -> list[tuple[Pauta, int, str]]:
    """Dá nota às pautas e devolve as melhores, em ordem decrescente."""
    if not pautas:
        return []
    opc = cfg["roteiro"]
    if config.dry_run():
        return [(p, 8, "modo de teste") for p in pautas[: opc["roteiros_por_execucao"]]]

    lista = "\n".join(f"[{i}] {p.titulo} — {p.resumo}" for i, p in enumerate(pautas))
    prompt = (
        f"Público do escritório: {opc['publico']}.\n"
        "Dê uma nota de 0 a 10 para cada pauta, considerando impacto prático no bolso ou nas "
        "obrigações desse público, urgência (prazo, mudança de regra) e potencial de virar um "
        "vídeo curto claro. Pautas repetidas, de opinião política ou sem efeito prático recebem nota baixa.\n\n"
        f"Pautas:\n{lista}"
    )
    triagem: Triagem = _chamar(cfg, prompt, Triagem, "low")
    escolhidas = [
        (pautas[a.indice], a.nota, a.motivo)
        for a in sorted(triagem.avaliacoes, key=lambda a: a.nota, reverse=True)
        if 0 <= a.indice < len(pautas) and a.nota >= opc["nota_minima"]
    ]
    return escolhidas[: opc["roteiros_por_execucao"]]


def escrever(cfg: dict, pauta: Pauta) -> Roteiro:
    opc = cfg["roteiro"]
    esc = cfg["escritorio"]
    if config.dry_run():
        return _roteiro_exemplo(pauta, esc)

    palavras = int(opc["duracao_segundos"] * 2.5)  # ~150 palavras por minuto
    prompt = (
        f"Escreva o roteiro de um vídeo vertical de cerca de {opc['duracao_segundos']} segundos "
        f"(no máximo {palavras} palavras em texto_narrado) para {opc['publico']}.\n"
        "Estrutura: gancho forte nos 3 primeiros segundos, explicação do que mudou e do que a "
        "pessoa precisa fazer, e uma pergunta no final para gerar comentários.\n"
        f"O CTA (só Instagram) convida a falar com o {esc['nome']} pelo WhatsApp.\n"
        "Escreva números por extenso quando ficar mais natural para a fala.\n\n"
        f"Pauta:\n{json.dumps(pauta.model_dump(), ensure_ascii=False, indent=2)}"
    )
    return _chamar(cfg, prompt, Roteiro, "high")


def _roteiro_exemplo(pauta: Pauta, esc: dict) -> Roteiro:
    gancho = "Sua empresa pode ser afetada por essa mudança e você talvez nem saiba."
    corpo = f"{pauta.titulo}. {pauta.resumo} Vale conferir agora como isso se aplica ao seu negócio."
    pergunta = "Você já sabia disso? Conta aqui nos comentários."
    return Roteiro(
        titulo=pauta.titulo[:70].strip(),
        gancho=gancho,
        corpo=corpo,
        pergunta_final=pergunta,
        cta=f"Fale com o {esc['nome']} pelo WhatsApp do perfil.",
        texto_narrado=f"{gancho} {corpo} {pergunta}",
        base_legal=[],
        pontos_a_verificar=["Roteiro de exemplo gerado em modo de teste."],
        legenda_post=pauta.titulo,
        hashtags=["contabilidade", "impostos", "empresas"],
    )
