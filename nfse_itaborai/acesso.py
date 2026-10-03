"""PIN de acesso à tela do sistema (opcional, vale para todas as empresas deste computador).

O PIN fica guardado só como hash (scrypt com sal) em dados_locais/acesso.json — nunca em texto. Quem entra
recebe um cookie de sessão (HttpOnly, SameSite=Strict) que expira depois de um tempo sem uso. Cinco erros
seguidos bloqueiam novas tentativas por alguns minutos. O robô agendado não depende do PIN.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

from . import emissor, segredos

COOKIE = "nfse_sessao"
MINUTOS_PADRAO = 240
MAX_ERROS, BLOQUEIO_SEG = 5, 300

_SESSOES: dict[str, float] = {}       # token -> último uso (epoch)
_ERROS = {"n": 0, "ate": 0.0}
_TRAVA = threading.Lock()


def _arquivo() -> Path:
    return emissor.BASE / "dados_locais" / "acesso.json"


def _ler() -> dict:
    try:
        return json.loads(_arquivo().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar(d: dict) -> None:
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(d, indent=2), encoding="utf-8")


def ativo() -> bool:
    return bool(_ler().get("pin"))


def minutos() -> int:
    return int(_ler().get("minutos") or MINUTOS_PADRAO)


def valido(token: str | None) -> bool:
    if not ativo():
        return True
    with _TRAVA:
        ult = _SESSOES.get(token or "")
        if not ult or time.time() - ult > minutos() * 60:
            _SESSOES.pop(token or "", None)
            return False
        _SESSOES[token] = time.time()
        return True


def entrar(pin: str) -> str:
    agora = time.time()
    with _TRAVA:
        if _ERROS["ate"] > agora:
            falta = int(_ERROS["ate"] - agora) // 60 + 1
            raise ValueError(f"Muitas tentativas erradas. Aguarde {falta} minuto(s).")
    if not segredos.confere_pin(str(pin or ""), _ler().get("pin", "")):
        with _TRAVA:
            _ERROS["n"] += 1
            if _ERROS["n"] >= MAX_ERROS:
                _ERROS.update(n=0, ate=agora + BLOQUEIO_SEG)
        raise ValueError("PIN incorreto.")
    token = secrets.token_urlsafe(32)
    with _TRAVA:
        _ERROS.update(n=0, ate=0.0)
        _SESSOES[token] = agora
    return token


def sair(token: str | None) -> None:
    with _TRAVA:
        _SESSOES.pop(token or "", None)


def definir(atual: str, novo: str, mins=None) -> dict:
    """Cria, troca ou remove (novo vazio) o PIN. Com PIN já ativo, exige o atual."""
    d = _ler()
    if d.get("pin") and not segredos.confere_pin(str(atual or ""), d["pin"]):
        raise ValueError("PIN atual incorreto.")
    novo = str(novo or "").strip()
    if novo and (not novo.isdigit() or not 4 <= len(novo) <= 8):
        raise ValueError("O PIN deve ter de 4 a 8 números.")
    if novo:
        d["pin"] = segredos.hash_pin(novo)
    else:
        d.pop("pin", None)
    if mins:
        d["minutos"] = max(5, min(1440, int(mins)))
    _gravar(d)
    with _TRAVA:
        _SESSOES.clear()                 # troca de PIN encerra as sessões abertas
    return estado(None)


def estado(token: str | None) -> dict:
    return {"ativo": ativo(), "logado": valido(token), "minutos": minutos()}


def token_do_cookie(cabecalho: str | None) -> str:
    for parte in (cabecalho or "").split(";"):
        k, _, v = parte.strip().partition("=")
        if k == COOKIE:
            return v
    return ""


def cookie(token: str, apagar: bool = False) -> str:
    return f"{COOKIE}={'' if apagar else token}; Path=/; HttpOnly; SameSite=Strict" + ("; Max-Age=0" if apagar else "")
