"""Regras de status de um conteúdo (quem pode mudar para onde)."""
from __future__ import annotations

import secrets
from datetime import timedelta

from .db import Conteudo, Perfil, agora

RASCUNHO = "rascunho"
REVISAO = "revisao_tecnica"
CLIENTE = "aguardando_cliente"
AJUSTE = "ajuste_solicitado"
APROVADO = "aprovado"
PRODUZINDO = "produzindo"
PRODUZIDO = "produzido"
AGENDADO = "agendado"
PUBLICADO = "publicado"
ERRO = "erro_producao"

ROTULOS = {
    RASCUNHO: "Rascunho",
    REVISAO: "Em revisão técnica",
    CLIENTE: "Aguardando cliente",
    AJUSTE: "Ajuste solicitado",
    APROVADO: "Aprovado",
    PRODUZINDO: "Produzindo",
    PRODUZIDO: "Pronto para publicar",
    AGENDADO: "Agendado",
    PUBLICADO: "Publicado",
    ERRO: "Erro na produção",
}
ORDEM = list(ROTULOS)
EDITAVEIS = {RASCUNHO, REVISAO, AJUSTE}


class FluxoInvalido(ValueError):
    pass


def _exigir(c: Conteudo, *permitidos: str) -> None:
    if c.status not in permitidos:
        raise FluxoInvalido(f"Ação não permitida no status '{ROTULOS.get(c.status, c.status)}'.")


def enviar_revisao(c: Conteudo) -> None:
    _exigir(c, RASCUNHO, AJUSTE)
    if c.j("alertas"):
        raise FluxoInvalido("Resolva os alertas das travas antes de enviar para revisão.")
    c.status = REVISAO


def aprovar_tecnico(c: Conteudo, perfil: Perfil, revisor: str, crc: str, dias_link: int) -> None:
    _exigir(c, REVISAO)
    if not crc.strip():
        raise FluxoInvalido("A revisão técnica exige um usuário com CRC cadastrado.")
    if c.j("alertas"):
        raise FluxoInvalido("Há alertas das travas pendentes.")
    c.revisor = f"{revisor} ({crc})"
    if perfil.tipo == "escritorio":
        c.status = APROVADO
    else:
        c.status = CLIENTE
        c.token_cliente = secrets.token_urlsafe(32)
        c.token_expira = agora() + timedelta(days=dias_link)


def token_valido(c: Conteudo) -> bool:
    return bool(c.token_cliente) and c.status == CLIENTE and c.token_expira is not None and c.token_expira > agora()


def cliente_aprova(c: Conteudo) -> None:
    if not token_valido(c):
        raise FluxoInvalido("Link expirado ou já utilizado.")
    c.status = APROVADO
    c.aprovado_cliente_em = agora()
    c.token_cliente = ""


def cliente_pede_ajuste(c: Conteudo, comentario: str) -> None:
    if not token_valido(c):
        raise FluxoInvalido("Link expirado ou já utilizado.")
    if not comentario.strip():
        raise FluxoInvalido("Descreva o ajuste desejado.")
    c.status = AJUSTE
    c.comentario_cliente = comentario.strip()
    c.token_cliente = ""


def voltar_rascunho(c: Conteudo) -> None:
    _exigir(c, REVISAO, AJUSTE, ERRO)
    c.status = RASCUNHO


def iniciar_producao(c: Conteudo, perfil: Perfil) -> None:
    _exigir(c, APROVADO, ERRO)
    if c.formato == "video" and not perfil.avatar_liberado:
        raise FluxoInvalido("Anexe o termo de consentimento do clone no perfil antes de produzir vídeos.")
    c.status = PRODUZINDO
    c.erro = ""


def agendar(c: Conteudo) -> None:
    _exigir(c, PRODUZIDO)
    c.status = AGENDADO


def desagendar(c: Conteudo) -> None:
    _exigir(c, AGENDADO)
    c.status = PRODUZIDO


def marcar_publicado(c: Conteudo) -> None:
    _exigir(c, PRODUZIDO, AGENDADO)
    c.status = PUBLICADO
