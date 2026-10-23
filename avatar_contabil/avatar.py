"""Etapa 6: vídeo do avatar na HeyGen, com fundo verde para recorte."""
from __future__ import annotations

import time
from pathlib import Path

import requests

from . import config, midia

UPLOAD = "https://upload.heygen.com/v1/asset"
GERAR = "https://api.heygen.com/v2/video/generate"
STATUS = "https://api.heygen.com/v1/video_status.get"


def _headers() -> dict:
    return {"X-Api-Key": config.segredo("HEYGEN_API_KEY")}


def gerar(cfg: dict, audio: Path, destino: Path, espera_max: int = 1800) -> Path:
    if config.dry_run():
        return _avatar_exemplo(cfg, audio, destino)

    opc = cfg["avatar"]
    if not opc.get("heygen_avatar_id"):
        raise RuntimeError("Defina avatar.heygen_avatar_id em config/config.yaml.")

    up = requests.post(
        UPLOAD, headers={**_headers(), "Content-Type": "audio/mpeg"}, data=audio.read_bytes(), timeout=180
    )
    up.raise_for_status()
    asset_id = up.json()["data"]["id"]

    corpo = {
        "video_inputs": [{
            "character": {"type": "avatar", "avatar_id": opc["heygen_avatar_id"], "avatar_style": "normal"},
            "voice": {"type": "audio", "audio_asset_id": asset_id},
            "background": {"type": "color", "value": opc.get("cor_chroma", "#00FF00")},
        }],
        "dimension": {"width": opc.get("largura", 720), "height": opc.get("altura", 1280)},
    }
    resp = requests.post(GERAR, headers=_headers(), json=corpo, timeout=60)
    resp.raise_for_status()
    video_id = resp.json()["data"]["video_id"]

    inicio = time.time()
    while time.time() - inicio < espera_max:
        st = requests.get(STATUS, headers=_headers(), params={"video_id": video_id}, timeout=30)
        st.raise_for_status()
        dados = st.json()["data"]
        if dados["status"] == "completed":
            video = requests.get(dados["video_url"], timeout=300)
            video.raise_for_status()
            destino.write_bytes(video.content)
            return destino
        if dados["status"] == "failed":
            raise RuntimeError(f"HeyGen falhou: {dados.get('error')}")
        time.sleep(15)
    raise TimeoutError(f"HeyGen não terminou o vídeo {video_id} em {espera_max}s.")


def _avatar_exemplo(cfg: dict, audio: Path, destino: Path) -> Path:
    """Gera um 'avatar' de mentira: silhueta cinza sobre fundo verde, com o áudio."""
    opc = cfg["avatar"]
    w, h = opc.get("largura", 720), opc.get("altura", 1280)
    verde = opc.get("cor_chroma", "#00FF00").replace("#", "0x")
    seg = midia.duracao(audio)
    midia.rodar([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c={verde}:s={w}x{h}:r=30:d={seg:.2f}",
        "-i", str(audio),
        "-vf", (
            f"drawbox=x={w//2-w//6}:y={h//2-h//10}:w={w//3}:h={h//7}:color=0x777777:t=fill,"
            f"drawbox=x={w//2-w//4}:y={h//2+h//14}:w={w//2}:h={h//2}:color=0x555555:t=fill"
        ),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(destino),
    ])
    return destino
