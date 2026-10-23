"""Etapas 7 e 8: montagem com FFmpeg e geração das versões Instagram e YouTube."""
from __future__ import annotations

from pathlib import Path

from . import legenda, midia

LARGURA, ALTURA = 1080, 1920

def comando(
    avatar: str,
    saida: str,
    legenda_ass: str,
    duracao: float,
    cor_fundo: str = "#0B3D5C",
    fundo: str = "",
    logo: str = "",
    musica: str = "",
    volume_musica: float = 0.08,
    cor_chroma: str = "#00FF00",
) -> list[str]:
    """Monta a linha de comando do FFmpeg. O caminho da legenda é relativo ao cwd."""
    cmd = ["ffmpeg", "-y"]
    if fundo:
        cmd += ["-loop", "1", "-i", fundo]
    else:
        cmd += ["-f", "lavfi", "-i", f"color=c={cor_fundo.replace('#', '0x')}:s={LARGURA}x{ALTURA}:r=30"]
    cmd += ["-i", avatar]
    idx_logo = idx_musica = None
    proximo = 2
    if logo:
        cmd += ["-i", logo]
        idx_logo, proximo = proximo, proximo + 1
    if musica:
        cmd += ["-stream_loop", "-1", "-i", musica]
        idx_musica = proximo

    chroma = cor_chroma.replace("#", "0x")
    filtros = [
        f"[0:v]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,crop={LARGURA}:{ALTURA},setsar=1[bg]",
        f"[1:v]chromakey={chroma}:0.13:0.06,scale={LARGURA}:-2[av]",
        f"[bg][av]overlay=(W-w)/2:H-h:shortest=1,ass={legenda_ass}[v1]",
    ]
    atual = "v1"
    if idx_logo is not None:
        filtros.append(f"[{idx_logo}:v]scale=180:-1[lg]")
        filtros.append(f"[{atual}][lg]overlay=W-w-40:60[v3]")
        atual = "v3"
    if idx_musica is not None:
        filtros.append(f"[{idx_musica}:a]volume={volume_musica}[m]")
        filtros.append("[1:a][m]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]")
        audio = "[a]"
    else:
        audio = "1:a"

    cmd += [
        "-filter_complex", ";".join(filtros),
        "-map", f"[{atual}]", "-map", audio,
        "-t", f"{duracao:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", "-r", "30",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
        saida,
    ]
    return cmd


def montar(cfg: dict, avatar: Path, texto_narrado: str, cta: str, pasta: Path, destaque: str = "#FFD60A") -> dict[str, Path]:
    """Gera <pasta>/instagram.mp4 (com CTA) e <pasta>/youtube.mp4 (sem CTA)."""
    if not midia.tem_audio(avatar):
        raise RuntimeError("O vídeo do avatar veio sem áudio.")
    esc = cfg["escritorio"]
    dur = midia.duracao(avatar)
    legenda.gerar_ass(texto_narrado, dur, pasta / "legenda_instagram.ass", cta=cta, destaque=destaque)
    legenda.gerar_ass(texto_narrado, dur, pasta / "legenda_youtube.ass", destaque=destaque)

    comuns = dict(
        avatar=str(avatar.resolve()),
        duracao=dur,
        cor_fundo=esc.get("cor_marca", "#0B3D5C"),
        fundo=_abs(esc.get("fundo")),
        logo=_abs(esc.get("logo")),
        musica=_abs(esc.get("musica")),
        volume_musica=esc.get("volume_musica", 0.08),
        cor_chroma=cfg["avatar"].get("cor_chroma", "#00FF00"),
    )
    saidas = {"instagram": pasta / "instagram.mp4", "youtube": pasta / "youtube.mp4"}
    midia.rodar(comando(saida=str(saidas["instagram"].resolve()), legenda_ass="legenda_instagram.ass", **comuns), cwd=pasta)
    midia.rodar(comando(saida=str(saidas["youtube"].resolve()), legenda_ass="legenda_youtube.ass", **comuns), cwd=pasta)
    return saidas


def _abs(caminho: str | None) -> str:
    if not caminho:
        return ""
    from .config import RAIZ

    p = Path(caminho)
    p = p if p.is_absolute() else RAIZ / p
    if not p.exists():
        raise FileNotFoundError(f"Arquivo configurado não existe: {p}")
    return str(p)
