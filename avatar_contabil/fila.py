"""Etapa 4: fila de aprovação humana. Cada vídeo é um JSON em data/fila/."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config
from .modelos import Pauta, Roteiro

PENDENTE = "pendente_revisao"
APROVADO = "aprovado"
REJEITADO = "rejeitado"
PRODUZIDO = "produzido"
PUBLICADO = "publicado"


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _arquivo(item_id: str) -> Path:
    return config.pasta("fila") / f"{item_id}.json"


def salvar(item: dict) -> None:
    _arquivo(item["id"]).write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar(item_id: str) -> dict:
    arq = _arquivo(item_id)
    if not arq.exists():
        raise KeyError(f"Item {item_id} não está na fila.")
    return json.loads(arq.read_text(encoding="utf-8"))


def listar(status: str | None = None) -> list[dict]:
    itens = [json.loads(a.read_text(encoding="utf-8")) for a in sorted(config.pasta("fila").glob("*.json"))]
    return [i for i in itens if status is None or i["status"] == status]


def adicionar(pauta: Pauta, roteiro: Roteiro, nota: int, motivo: str, alertas: list[str]) -> dict:
    item = {
        "id": f"{datetime.now():%Y%m%d}-{pauta.id}",
        "status": PENDENTE,
        "criado_em": _agora(),
        "nota": nota,
        "motivo_nota": motivo,
        "alertas_travas": alertas,
        "pauta": pauta.model_dump(),
        "roteiro": roteiro.model_dump(),
        "arquivos": {},
        "publicacoes": {},
        "historico": [{"quando": _agora(), "evento": "roteiro criado"}],
    }
    salvar(item)
    return item


def mudar_status(item: dict, novo: str, evento: str) -> dict:
    item["status"] = novo
    item["historico"].append({"quando": _agora(), "evento": evento})
    salvar(item)
    return item


def aprovar(item_id: str, revisor: str) -> dict:
    item = carregar(item_id)
    if item["status"] != PENDENTE:
        raise ValueError(f"Só é possível aprovar itens pendentes (status atual: {item['status']}).")
    if item["alertas_travas"]:
        raise ValueError("Roteiro com alertas das travas. Edite o JSON, remova o problema e rode `revalidar`.")
    item["revisor"] = revisor
    return mudar_status(item, APROVADO, f"aprovado por {revisor}")


def rejeitar(item_id: str, motivo: str) -> dict:
    item = carregar(item_id)
    return mudar_status(item, REJEITADO, f"rejeitado: {motivo}")
