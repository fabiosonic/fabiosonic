"""Operações compartilhadas entre o aplicativo web e o piloto automático."""
from __future__ import annotations

import secrets
from pathlib import Path

from PIL import Image

from avatar_contabil import config

from . import carrossel, fluxo, ia, travas
from .db import Conteudo, Pauta, Perfil, agora, registrar

FORMATOS_TODOS = {"post": "Post (imagem única)", "carrossel": "Carrossel", "video": "Vídeo com avatar"}


def cfg() -> dict:
    return config.carregar()


def formatos_ativos() -> dict[str, str]:
    """Formatos ligados em studio.formatos (por padrão, só post e carrossel)."""
    ativos = cfg()["studio"].get("formatos", ["post", "carrossel"])
    return {k: v for k, v in FORMATOS_TODOS.items() if k in ativos}


def pasta_studio(*partes: str) -> Path:
    p = config.DADOS.joinpath("studio", *partes)
    p.mkdir(parents=True, exist_ok=True)
    return p


def rel(caminho: Path) -> str:
    return caminho.resolve().relative_to(config.DADOS.resolve()).as_posix()


def atualizar_previa(c: Conteudo, perfil: Perfil) -> None:
    """Redesenha as imagens do post/carrossel para revisão e aprovação."""
    if c.formato == "video":
        return
    destino = pasta_studio("conteudos", str(c.id), "previa")
    for antigo in destino.glob("*.png"):
        antigo.unlink()
    arquivos = carrossel.desenhar(perfil, c.j("dados").get("slides", []), destino, config.DADOS)
    c.guardar("arquivos", [rel(a) for a in arquivos])


def aplicar_travas(c: Conteudo, perfil: Perfil) -> None:
    c.guardar("alertas", travas.validar(cfg(), perfil, c.formato, c.j("dados")))


def avaliar(c: Conteudo, perfil: Perfil) -> None:
    c.guardar("nota", ia.avaliar(perfil, c.formato, c.j("dados")))


def criar_conteudo(s, perfil: Perfil, pauta: Pauta, formato: str, estilo: str, instrucao: str, usuario: str,
                   base: dict | None = None, automatico: bool = False) -> Conteudo:
    gerado = ia.gerar(perfil, pauta, formato, estilo, instrucao, base=base)
    c = Conteudo(perfil_id=perfil.id, pauta_id=pauta.id, formato=formato, estilo=estilo, automatico=automatico)
    c.guardar("dados", gerado.model_dump())
    s.add(c)
    s.flush()
    aplicar_travas(c, perfil)
    avaliar(c, perfil)
    atualizar_previa(c, perfil)
    origem = " (réplica)" if base else " (piloto automático)" if automatico else ""
    registrar(s, c.id, usuario, "criado", f"{FORMATOS_TODOS[formato]} · {ia.ESTILOS.get(estilo, '')[:40]}{origem}")
    return c


def produzir_imagens(s, c: Conteudo, perfil: Perfil, usuario: str) -> None:
    """Gera as imagens finais em JPEG (o Instagram não aceita PNG) e libera o link público das mídias.

    Se houver data planejada e o Instagram do perfil estiver conectado, o conteúdo já fica agendado.
    """
    destino = pasta_studio("conteudos", str(c.id), "final")
    for antigo in destino.glob("*"):
        antigo.unlink()
    finais = []
    for i, a in enumerate(c.j("arquivos"), 1):
        jpg = destino / f"imagem_{i:02d}.jpg"
        Image.open(config.DADOS / a).convert("RGB").save(jpg, "JPEG", quality=92, optimize=True)
        finais.append(rel(jpg))
    c.guardar("arquivos", finais)
    c.midia_token = c.midia_token or secrets.token_urlsafe(24)
    c.status, c.erro, c.atualizado_em = fluxo.PRODUZIDO, "", agora()
    registrar(s, c.id, usuario, "imagens finais geradas")
    if c.agendado_para and perfil.instagram_conectado:
        fluxo.agendar(c)
        registrar(s, c.id, usuario, "publicação automática agendada", c.agendado_para.strftime("%d/%m/%Y %H:%M"))


def apos_aprovacao(s, c: Conteudo, perfil: Perfil, usuario: str) -> None:
    """Quando o conteúdo de imagem fica aprovado, produz na hora (é instantâneo e não tem custo)."""
    if c.status == fluxo.APROVADO and c.formato != "video":
        fluxo.iniciar_producao(c, perfil)
        try:
            produzir_imagens(s, c, perfil, usuario)
        except Exception as e:  # mantém o conteúdo aprovado, com o erro visível
            c.status, c.erro = fluxo.ERRO, str(e)[:2000]
            registrar(s, c.id, usuario, "erro na produção", str(e)[:500])
