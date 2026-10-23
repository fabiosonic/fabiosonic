"""Etapa 6 das travas: validação de texto, limite diário e registro de publicações."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from . import config
from .modelos import Roteiro

LOG = "publicacoes.jsonl"


def validar_roteiro(cfg: dict, roteiro: Roteiro) -> list[str]:
    """Devolve a lista de problemas encontrados (vazia = ok)."""
    alertas = []
    texto = " ".join([roteiro.titulo, roteiro.texto_narrado, roteiro.cta, roteiro.legenda_post]).lower()
    for termo in cfg["travas"]["termos_proibidos"]:
        if re.search(rf"\b{re.escape(termo.lower())}\b", texto):
            alertas.append(f"termo proibido: '{termo}'")

    limite = int(cfg["roteiro"]["duracao_segundos"] * 2.5 * 1.3)
    palavras = len(roteiro.texto_narrado.split())
    if palavras > limite:
        alertas.append(f"texto narrado longo demais ({palavras} palavras, limite {limite})")
    if not roteiro.texto_narrado.strip():
        alertas.append("texto narrado vazio")
    return alertas


def legenda_final(cfg: dict, roteiro: Roteiro, com_cta: bool) -> str:
    esc, tr = cfg["escritorio"], cfg["travas"]
    partes = [roteiro.legenda_post, ""]
    if com_cta:
        partes += [f"{roteiro.cta} {esc['whatsapp']}", ""]
    partes += [
        tr["aviso_tecnico"],
        tr["aviso_ia"],
        f"{esc['nome']} · {esc['crc']}",
        "",
        " ".join("#" + h.lstrip("#").replace(" ", "") for h in roteiro.hashtags),
    ]
    return "\n".join(partes).strip()


def publicados_hoje() -> int:
    arq = config.DADOS / LOG
    if not arq.exists():
        return 0
    hoje = date.today().isoformat()
    ids = {
        reg["id"]
        for reg in map(json.loads, arq.read_text(encoding="utf-8").splitlines())
        if reg["quando"].startswith(hoje) and reg.get("ok")
    }
    return len(ids)


def pode_publicar(cfg: dict) -> bool:
    return publicados_hoje() < cfg["publicacao"]["limite_diario"]


def registrar(item_id: str, rede: str, ok: bool, detalhe: str) -> None:
    config.DADOS.mkdir(parents=True, exist_ok=True)
    reg = {"quando": datetime.now().isoformat(timespec="seconds"), "id": item_id, "rede": rede, "ok": ok, "detalhe": detalhe}
    with open(config.DADOS / LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(reg, ensure_ascii=False) + "\n")
