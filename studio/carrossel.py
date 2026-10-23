"""Desenha posts e carrosséis (1080x1350) com a marca do perfil."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .db import Perfil

LARG, ALT = 1080, 1350
MARGEM = 90
FONTES = Path("/usr/share/fonts/truetype/dejavu")


def _fonte(tamanho: int, negrito: bool = False):
    arq = FONTES / ("DejaVuSans-Bold.ttf" if negrito else "DejaVuSans.ttf")
    try:
        return ImageFont.truetype(str(arq), tamanho)
    except OSError:
        return ImageFont.load_default(tamanho)


def _quebrar(draw: ImageDraw.ImageDraw, texto: str, fonte, largura: int) -> list[str]:
    linhas, atual = [], ""
    for palavra in texto.split():
        teste = f"{atual} {palavra}".strip()
        if draw.textlength(teste, font=fonte) <= largura:
            atual = teste
        else:
            if atual:
                linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)
    return linhas


def _bloco(draw, texto: str, y: int, tamanho: int, cor: str, negrito: bool, minimo: int = 34, altura_max: int = 700) -> int:
    """Escreve o texto quebrando linhas e reduzindo a fonte até caber; devolve o y final."""
    while True:
        fonte = _fonte(tamanho, negrito)
        linhas = _quebrar(draw, texto, fonte, LARG - 2 * MARGEM)
        altura = len(linhas) * int(tamanho * 1.25)
        if altura <= altura_max or tamanho <= minimo:
            break
        tamanho -= 4
    for linha in linhas:
        draw.text((MARGEM, y), linha, font=fonte, fill=cor)
        y += int(tamanho * 1.25)
    return y


def _contraste(hex_cor: str) -> str:
    r, g, b = (int(hex_cor[i:i + 2], 16) for i in (1, 3, 5))
    return "#111111" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#FFFFFF"


def _rodape(draw, perfil: Perfil, cor: str, pagina: str) -> None:
    texto = perfil.nome + (f" · {perfil.crc_responsavel}" if perfil.crc_responsavel else "")
    for tamanho in range(30, 19, -2):  # diminui a fonte antes de cortar, para o CRC continuar visível
        fonte = _fonte(tamanho)
        largura_pag = draw.textlength(pagina, font=fonte) if pagina else 0
        limite = LARG - 2 * MARGEM - largura_pag - 30
        if draw.textlength(texto, font=fonte) <= limite:
            break
    if draw.textlength(texto, font=fonte) > limite:
        # corta o nome, nunca o CRC
        fim = f" · {perfil.crc_responsavel}" if perfil.crc_responsavel else ""
        nome = perfil.nome
        while nome and draw.textlength(nome + "…" + fim, font=fonte) > limite:
            nome = nome[:-1]
        texto = (nome.rstrip() + "…" + fim) if nome else fim.lstrip(" ·")
    draw.text((MARGEM, ALT - 90), texto, font=fonte, fill=cor)
    if pagina:
        draw.text((LARG - MARGEM - largura_pag, ALT - 90), pagina, font=fonte, fill=cor)


def _logo(img: Image.Image, perfil: Perfil, raiz: Path) -> None:
    if not perfil.logo:
        return
    arq = raiz / perfil.logo
    if not arq.exists():
        return
    try:
        logo = Image.open(arq).convert("RGBA")
    except OSError:
        return  # arquivo de logo inválido: segue sem logo
    logo.thumbnail((200, 120))
    img.paste(logo, (LARG - MARGEM - logo.width, MARGEM - 20), logo)


def desenhar(perfil: Perfil, slides: list[dict], destino: Path, raiz: Path) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    arquivos = []
    total = len(slides)
    for i, slide in enumerate(slides):
        capa = i == 0
        fundo = perfil.cor_primaria if capa or i == total - 1 and total > 1 else perfil.cor_secundaria
        texto_cor = _contraste(fundo)
        img = Image.new("RGB", (LARG, ALT), fundo)
        draw = ImageDraw.Draw(img)
        draw.rectangle([MARGEM, MARGEM + 130, MARGEM + 140, MARGEM + 142], fill=perfil.cor_destaque)
        y = MARGEM + 190
        if capa:
            y = _bloco(draw, slide.get("titulo", ""), y, 92, texto_cor, True, altura_max=620)
            _bloco(draw, slide.get("texto", ""), y + 40, 46, texto_cor, False, altura_max=360)
        else:
            if total > 1:
                draw.text((MARGEM, MARGEM + 20), f"{i + 1:02d}", font=_fonte(64, True), fill=perfil.cor_destaque)
            y = _bloco(draw, slide.get("titulo", ""), y, 68, texto_cor, True, altura_max=330)
            _bloco(draw, slide.get("texto", ""), y + 40, 46, texto_cor, False, altura_max=600)
        _logo(img, perfil, raiz)
        _rodape(draw, perfil, texto_cor, f"{i + 1}/{total}" if total > 1 else "")
        arq = destino / f"slide_{i + 1:02d}.png"
        img.save(arq, optimize=True)
        arquivos.append(arq)
    return arquivos
