"""Horário comercial dos envios: e-mails e mensagens a clientes e ao dono só saem de segunda a sexta, no horário
configurado (padrão 08:00 às 18:00, horário de Brasília). Fora dele, nada se perde: a régua, a fila do WhatsApp e os
resumos ficam para a próxima rodada do robô dentro do horário. Os testes que o próprio escritório dispara (e-mail de
teste, mensagem de teste) não passam por aqui."""

from __future__ import annotations

import os
from datetime import datetime

from . import config

DIAS = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")


def _cfg(cfg: dict | None) -> dict:
    return (cfg or config.carregar())["cobranca"]


def agora() -> datetime:
    from .emissor import FUSO
    return datetime.now(FUSO).replace(tzinfo=None)


def comercial(em: datetime | None = None, cfg: dict | None = None) -> bool:
    if os.environ.get("NFSE_ENVIO_SEMPRE") == "1":          # testes automáticos
        return True
    c = _cfg(cfg)
    if not c.get("envio_horario_comercial", True):
        return True
    em = em or agora()
    ini, fim = str(c.get("envio_hora_inicio") or "08:00"), str(c.get("envio_hora_fim") or "18:00")
    return em.weekday() < 5 and ini <= em.strftime("%H:%M") < fim


def faixa(cfg: dict | None = None) -> str:
    c = _cfg(cfg)
    return f"de segunda a sexta, das {c.get('envio_hora_inicio') or '08:00'} às {c.get('envio_hora_fim') or '18:00'}"


def motivo(em: datetime | None = None, cfg: dict | None = None) -> str:
    em = em or agora()
    return (f"Fora do horário comercial ({DIAS[em.weekday()]}, {em:%H:%M}): e-mails e mensagens só saem "
            f"{faixa(cfg)}. O robô envia no próximo horário comercial.")
