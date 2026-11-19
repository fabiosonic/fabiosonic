"""Log central: arquivo rotativo + banco (por execução) + buffer em memória para o painel (tempo real).

Nunca registre senhas, conteúdo de PFX ou tokens: o filtro abaixo mascara padrões comuns.
"""

from __future__ import annotations

import logging
import re
import threading
from collections import deque
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

RE_SEGREDO = re.compile(r"(senha|password|token|apse_|aps_|Bearer)\s*[:=]?\s*\S+", re.I)


def mascarar(msg: str) -> str:
    return RE_SEGREDO.sub(lambda m: m.group(1) + "=***", msg)


class HubLogs:
    def __init__(self, capacidade: int = 2000):
        self._buf: deque[dict] = deque(maxlen=capacidade)
        self._seq = 0
        self._lock = threading.Lock()

    def publicar(self, nivel: str, mensagem: str, execucao_id: int | None = None, empresa: str | None = None) -> dict:
        with self._lock:
            self._seq += 1
            item = {"seq": self._seq, "momento": datetime.now(UTC).isoformat(), "nivel": nivel,
                    "mensagem": mascarar(mensagem), "execucao_id": execucao_id, "empresa": empresa}
            self._buf.append(item)
            return item

    def desde(self, seq: int) -> list[dict]:
        with self._lock:
            return [i for i in self._buf if i["seq"] > seq]


HUB = HubLogs()


class _FiltroSegredos(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mascarar(str(record.msg))
        return True


def configurar_logging(pasta: Path, nivel: int = logging.INFO) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    raiz = logging.getLogger("moxml")
    if any(isinstance(h, RotatingFileHandler) for h in raiz.handlers):
        return
    raiz.setLevel(nivel)
    h = RotatingFileHandler(pasta / "moxml.log", maxBytes=10_000_000, backupCount=20, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    h.addFilter(_FiltroSegredos())
    raiz.addHandler(h)
