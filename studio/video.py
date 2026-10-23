"""Vídeo com o avatar do perfil: pronúncia, custo estimado e produção."""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

from avatar_contabil import avatar, config, montagem, voz

from .db import Perfil
from .travas import PALAVRAS_POR_SEGUNDO


def _dicionario() -> dict[str, str]:
    arq = config.RAIZ / "config" / "pronuncia.yaml"
    if not arq.exists():
        return {}
    return yaml.safe_load(arq.read_text(encoding="utf-8")) or {}


def para_fala(texto: str, dicionario: dict[str, str] | None = None) -> str:
    """Troca siglas pela forma falada (só no texto enviado à voz)."""
    dic = _dicionario() if dicionario is None else dicionario
    for sigla in sorted(dic, key=len, reverse=True):
        texto = re.sub(rf"(?<![\w-]){re.escape(sigla)}(?![\w-])", dic[sigla], texto)
    return texto


def estimar(cfg: dict, texto: str) -> dict:
    c = cfg["studio"]["custos"]
    segundos = max(1.0, len(texto.split()) / PALAVRAS_POR_SEGUNDO)
    falado = para_fala(texto)
    usd = segundos / 60 * c["avatar_usd_por_minuto"] + len(falado) / 1000 * c["voz_usd_por_1000_caracteres"]
    return {"segundos": round(segundos), "usd": round(usd, 2), "brl": round(usd * c["cambio_brl"], 2)}


def cfg_do_perfil(cfg: dict, perfil: Perfil) -> dict:
    novo = copy.deepcopy(cfg)
    if perfil.heygen_avatar_id:
        novo["avatar"]["heygen_avatar_id"] = perfil.heygen_avatar_id
    if perfil.elevenlabs_voice_id:
        novo["voz"]["elevenlabs_voice_id"] = perfil.elevenlabs_voice_id
    esc = novo["escritorio"]
    logo = str(config.DADOS / perfil.logo) if perfil.logo else ""
    esc.update(nome=perfil.nome, crc=perfil.crc_responsavel, cor_marca=perfil.cor_primaria, logo=logo, fundo="")
    return novo


def produzir(cfg: dict, perfil: Perfil, dados: dict, pasta: Path) -> list[Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    c = cfg_do_perfil(cfg, perfil)
    audio = voz.gerar(c, para_fala(dados["texto_narrado"]), pasta / "narracao.mp3")
    video = avatar.gerar(c, audio, pasta / "avatar.mp4")
    saidas = montagem.montar(c, video, dados["texto_narrado"], dados.get("cta", ""), pasta, destaque=perfil.cor_destaque)
    return [saidas["instagram"], saidas["youtube"]]
