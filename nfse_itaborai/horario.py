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


def horas(cfg: dict | None = None) -> tuple[str, str]:
    """Faixa configurada (padrão 08:00–18:00); valor vazio ou inválido volta ao padrão."""
    import re
    c = _cfg(cfg)
    ini, fim = str(c.get("envio_hora_inicio") or ""), str(c.get("envio_hora_fim") or "")
    ok = lambda h: bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", h))  # noqa: E731
    if not (ok(ini) and ok(fim) and ini < fim):
        ini, fim = "08:00", "18:00"
    return ini, fim


def comercial(em: datetime | None = None, cfg: dict | None = None) -> bool:
    """Regra fixa do escritório: NUNCA fim de semana, e só dentro da faixa de horas. Não há opção para desligar —
    a antiga 'envio_horario_comercial' é ignorada (uma configuração desligada chegou a mandar cobrança num domingo)."""
    if os.environ.get("NFSE_ENVIO_SEMPRE") == "1":          # só os testes automáticos
        return True
    em = em or agora()
    ini, fim = horas(cfg)
    return em.weekday() < 5 and ini <= em.strftime("%H:%M") < fim


def faixa(cfg: dict | None = None) -> str:
    ini, fim = horas(cfg)
    return f"de segunda a sexta, das {ini} às {fim}"


def motivo(em: datetime | None = None, cfg: dict | None = None) -> str:
    em = em or agora()
    return (f"Fora do horário comercial ({DIAS[em.weekday()]}, {em:%H:%M}): e-mails e mensagens só saem "
            f"{faixa(cfg)}. O robô envia no próximo horário comercial.")
