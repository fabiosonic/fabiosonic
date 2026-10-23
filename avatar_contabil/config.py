"""Carrega config/config.yaml e variáveis de ambiente (.env)."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "data"

try:
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
except ImportError:  # python-dotenv é opcional
    pass


def carregar(caminho: str | Path | None = None) -> dict:
    caminho = Path(caminho or os.environ.get("AVATAR_CONFIG", RAIZ / "config" / "config.yaml"))
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def dry_run() -> bool:
    return os.environ.get("DRY_RUN", "1") != "0"


def segredo(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise RuntimeError(f"Variável {nome} não definida. Preencha o arquivo .env (veja .env.example).")
    return valor


def pasta(nome: str) -> Path:
    p = DADOS / nome
    p.mkdir(parents=True, exist_ok=True)
    return p
