"""Legendas ASS (1080x1920) com destaque palavra por palavra (karaokê), sincronizadas por proporção de caracteres."""
from __future__ import annotations

import re
from pathlib import Path

CABECALHO = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Fala,DejaVu Sans,78,{destaque},&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,6,0,2,80,80,620,1
Style: CTA,DejaVu Sans,58,&H00FFFFFF,&H00FFFFFF,&H00000000,&HB4000000,-1,0,0,0,100,100,0,0,3,18,0,8,90,90,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _tempo(s: float) -> str:
    cs = int(round(s * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6000)
    seg, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{seg:02}.{cs:02}"


def cor_ass(hex_cor: str) -> str:
    """#RRGGBB -> &H00BBGGRR (formato de cor do ASS)."""
    h = hex_cor.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def _karaoke(bloco: str, duracao: float) -> str:
    """Cada palavra acende (cor de destaque) no seu tempo, proporcional ao tamanho."""
    palavras = bloco.split()
    total = sum(len(p) for p in palavras) or 1
    cs = [max(1, round(duracao * 100 * len(p) / total)) for p in palavras]
    return " ".join(f"{{\\k{c}}}{_texto(p).upper()}" for c, p in zip(cs, palavras))


def _texto(t: str) -> str:
    return t.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def blocos(texto: str, max_palavras: int = 5) -> list[str]:
    """Quebra o texto em blocos curtos, respeitando o fim das frases."""
    saida = []
    for frase in re.split(r"(?<=[.!?])\s+", texto.strip()):
        palavras = frase.split()
        saida += [" ".join(palavras[i:i + max_palavras]) for i in range(0, len(palavras), max_palavras)]
    return [b for b in saida if b]


def eventos_fala(texto: str, duracao: float) -> list[tuple[float, float, str]]:
    partes = blocos(texto)
    total = sum(len(p) for p in partes) or 1
    saida, t = [], 0.0
    for parte in partes:
        fim = t + duracao * len(parte) / total
        saida.append((t, fim, parte))
        t = fim
    return saida


def gerar_ass(
    texto: str, duracao: float, destino: Path, cta: str = "", segundos_cta: float = 4.0, destaque: str = "#FFD60A"
) -> Path:
    linhas = [
        f"Dialogue: 0,{_tempo(i)},{_tempo(f)},Fala,,0,0,0,,{_karaoke(p, f - i)}"
        for i, f, p in eventos_fala(texto, duracao)
    ]
    if cta:
        linhas.append(f"Dialogue: 1,{_tempo(max(0.0, duracao - segundos_cta))},{_tempo(duracao)},CTA,,0,0,0,,{_texto(cta)}")
    destino.write_text(CABECALHO.replace("{destaque}", cor_ass(destaque)) + "\n".join(linhas) + "\n", encoding="utf-8")
    return destino
