"""Chamada única ao Claude com saída estruturada (JSON validado por schema)."""
from __future__ import annotations

import json

MODELO_PADRAO = "claude-opus-5-5"


class Recusa(RuntimeError):
    pass


def perguntar(sistema: str, usuario: str, schema: dict, modelo: str = MODELO_PADRAO, max_tokens: int = 16000) -> dict:
    """Envia `usuario` ao modelo e devolve um dict que obedece a `schema`."""
    import anthropic  # import tardio: os comandos que não usam IA rodam sem a lib

    cliente = anthropic.Anthropic()
    resposta = cliente.beta.messages.create(
        model=modelo,
        max_tokens=max_tokens,
        system=sistema,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": schema}},
        # se o modelo principal recusar, a API reexecuta no modelo de reserva
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": usuario}],
    )
    if resposta.stop_reason == "refusal":
        raise Recusa("O modelo recusou o pedido.")
    if resposta.stop_reason == "max_tokens":
        raise RuntimeError("Resposta cortada por max_tokens.")
    texto = "".join(b.text for b in resposta.content if b.type == "text")
    return json.loads(texto)


def objeto(propriedades: dict) -> dict:
    """Atalho para schema de objeto estrito (todos os campos obrigatórios)."""
    return {"type": "object", "properties": propriedades, "required": list(propriedades), "additionalProperties": False}


TXT = {"type": "string"}


def lista(item: dict) -> dict:
    return {"type": "array", "items": item}
