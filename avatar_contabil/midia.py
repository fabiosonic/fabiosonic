"""Utilitários de mídia com FFmpeg/FFprobe."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def rodar(cmd: list[str], cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Falha ao executar {cmd[0]}:\n{proc.stderr[-2000:]}")


def duracao(arquivo: Path) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return float(json.loads(proc.stdout)["format"]["duration"])


def tem_audio(arquivo: Path) -> bool:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index", "-of", "csv=p=0", str(arquivo)],
        capture_output=True, text=True, check=True,
    )
    return bool(proc.stdout.strip())
