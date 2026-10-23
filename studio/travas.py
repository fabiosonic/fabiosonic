"""Travas éticas e técnicas aplicadas a todo conteúdo antes da revisão."""
from __future__ import annotations

import re

from .db import Perfil

PALAVRAS_POR_SEGUNDO = 2.5


def _texto(dados: dict) -> str:
    partes = [dados.get(k, "") for k in ("titulo", "gancho", "legenda", "cta", "texto_narrado")]
    partes += [f"{s.get('titulo', '')} {s.get('texto', '')}" for s in dados.get("slides", [])]
    return " ".join(partes).lower()


def validar(cfg: dict, perfil: Perfil, formato: str, dados: dict) -> list[str]:
    alertas = []
    texto = _texto(dados)
    for termo in cfg["travas"]["termos_proibidos"] + perfil.termos_proibidos():
        if re.search(rf"\b{re.escape(termo.lower())}\b", texto):
            alertas.append(f"Termo proibido: '{termo}'")

    if formato == "video":
        palavras = len(dados.get("texto_narrado", "").split())
        if palavras == 0:
            alertas.append("Vídeo sem texto narrado.")
        elif palavras > 140:
            alertas.append(f"Texto narrado longo ({palavras} palavras, ~{palavras / PALAVRAS_POR_SEGUNDO:.0f}s). Máximo 140.")
    else:
        slides = dados.get("slides", [])
        if not slides:
            alertas.append("Nenhum slide para gerar a imagem.")
        if formato == "carrossel" and not 2 <= len(slides) <= 10:
            alertas.append("O Instagram aceita carrossel de 2 a 10 imagens.")
        for i, s in enumerate(slides, 1):
            if len(s.get("texto", "").split()) > 45:
                alertas.append(f"Slide {i} com texto longo demais para leitura (máx. 45 palavras).")
    if len(dados.get("legenda", "")) > 2000:
        alertas.append("Legenda acima de 2.000 caracteres (limite do Instagram é 2.200 com os avisos).")
    return alertas


def legenda_final(cfg: dict, perfil: Perfil, dados: dict, com_cta: bool = True) -> str:
    tr = cfg["travas"]
    partes = [dados.get("legenda", "").strip(), ""]
    if com_cta and dados.get("cta"):
        cta = dados["cta"]
        numero = re.sub(r"\D", "", perfil.whatsapp)
        if numero:
            cta += f" https://wa.me/{numero}"
        partes += [cta, ""]
    partes.append(tr["aviso_tecnico"])
    if dados.get("texto_narrado"):
        partes.append(tr["aviso_ia"])
    if perfil.crc_responsavel:
        partes.append(f"{perfil.nome} · {perfil.crc_responsavel}")
    tags = " ".join("#" + re.sub(r"\s+", "", h.lstrip("#")) for h in dados.get("hashtags", []))
    if tags:
        partes += ["", tags]
    return "\n".join(partes).strip()
