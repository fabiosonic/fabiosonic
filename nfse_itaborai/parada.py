"""Pedido de parada do robô (usado pela atualização do sistema).

A atualização grava dados_locais/parar_robo na pasta do sistema; o robô (da tela ou do Agendador do Windows)
confere o pedido antes de cada empresa, de cada etapa e de cada título, e para num ponto seguro — nunca no meio
do registro de um boleto ou da emissão de uma nota (o que poderia gerar boleto ou nota em dobro).
O pedido vence sozinho em 15 minutos e é apagado quando o sistema abre de novo.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from . import emissor

VALIDADE_SEG = 15 * 60


class RoboParado(Exception):
    """O robô parou num ponto seguro porque a atualização pediu."""


def _arquivo() -> Path:
    return Path(emissor.BASE) / "dados_locais" / "parar_robo"


def pedir() -> None:
    a = _arquivo()
    a.parent.mkdir(parents=True, exist_ok=True)
    a.write_text(str(time.time()), encoding="utf-8")


def liberar() -> None:
    try:
        _arquivo().unlink()
    except OSError:
        pass


def pedida() -> bool:
    try:
        return time.time() - _arquivo().stat().st_mtime < VALIDADE_SEG
    except OSError:
        return False


def conferir() -> None:
    """Chamado nos pontos seguros do robô."""
    if pedida():
        raise RoboParado("Robô parado para a atualização do sistema.")


def pid_vivo(pid: int) -> bool:
    """O processo ainda existe? (no Windows sem os.kill, que lá encerraria o processo)."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    if os.name == "nt":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        try:
            codigo = ctypes.c_ulong()
            return bool(k.GetExitCodeProcess(h, ctypes.byref(codigo))) and codigo.value == 259   # STILL_ACTIVE
        finally:
            k.CloseHandle(h)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
