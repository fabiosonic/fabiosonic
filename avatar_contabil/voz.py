"""Etapa 5: narração com a voz clonada no ElevenLabs."""
from __future__ import annotations

from pathlib import Path

import requests

from . import config, midia

URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"


def gerar(cfg: dict, texto: str, destino: Path) -> Path:
    if config.dry_run():
        return _voz_exemplo(texto, destino)

    opc = cfg["voz"]
    if not opc.get("elevenlabs_voice_id"):
        raise RuntimeError("Defina voz.elevenlabs_voice_id em config/config.yaml.")
    resp = requests.post(
        URL.format(voice_id=opc["elevenlabs_voice_id"]),
        headers={"xi-api-key": config.segredo("ELEVENLABS_API_KEY"), "accept": "audio/mpeg"},
        json={
            "text": texto,
            "model_id": opc.get("modelo", "eleven_multilingual_v2"),
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8, "style": 0.2},
        },
        timeout=180,
    )
    resp.raise_for_status()
    destino.write_bytes(resp.content)
    _verificar(texto, destino)
    return destino


def _verificar(texto: str, audio: Path) -> None:
    """Confere se a duração do áudio é coerente com o tamanho do texto."""
    esperado = len(texto.split()) / 2.5
    real = midia.duracao(audio)
    if not (0.5 * esperado <= real <= 1.8 * esperado):
        raise RuntimeError(f"Áudio com duração suspeita ({real:.1f}s; esperado ~{esperado:.1f}s). Gere de novo.")


def _voz_exemplo(texto: str, destino: Path) -> Path:
    segundos = max(3.0, len(texto.split()) / 2.5)
    midia.rodar([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=220:duration={segundos:.2f}",
        "-af", "volume=0.05", "-c:a", "libmp3lame", "-b:a", "128k", str(destino),
    ])
    return destino
