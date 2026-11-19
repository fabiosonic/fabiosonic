"""Interface comum dos conectores de captura.

Um conector representa UMA fonte (SEFAZ, Ambiente Nacional, pasta do emissor,
fornecedor comercial). O núcleo (``moxml.motor``) conversa apenas com esta
interface, de modo que novas UFs e provedores entram sem alterar o núcleo.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class Capacidade(StrEnum):
    LISTAR = "LISTAR"  # descobrir chaves/documentos de um período
    RECUPERAR_XML = "RECUPERAR_XML"  # obter XML integral a partir da chave
    RECUPERAR_EVENTOS = "RECUPERAR_EVENTOS"
    SITUACAO = "SITUACAO"  # situação/protocolo (NÃO é XML integral)
    IMPORTAR = "IMPORTAR"  # importação de arquivos já existentes


class StatusFonte(StrEnum):
    DISPONIVEL = "DISPONIVEL"  # documentado e configurado
    INDISPONIVEL = "INDISPONIVEL"  # fonte não oferece para UF/modelo
    NAO_CONFIGURADO = "NAO_CONFIGURADO"  # falta certificado/credencial/ativação
    BLOQUEADO = "BLOQUEADO"  # bloqueio temporário (limite/consumo indevido)
    NAO_COMPROVADO = "NAO_COMPROVADO"  # documentado mas sem teste real


@dataclass
class Disponibilidade:
    status: StatusFonte
    motivo: str = ""
    evidencia: str = ""

    @property
    def ok(self) -> bool:
        return self.status in (StatusFonte.DISPONIVEL, StatusFonte.NAO_COMPROVADO)


@dataclass
class Limites:
    requisicoes_por_minuto: float | None = None
    janela_retroativa_dias: int | None = None
    itens_por_pagina: int | None = None
    observacoes: str = ""


@dataclass
class DocumentoDescoberto:
    chave: str
    origem: str
    data_emissao: datetime | None = None
    xml: bytes | None = None  # quando a listagem já entrega o documento (ex.: DistDFe procNFe)
    ref_fonte: str | None = None  # identificador da fonte (ex.: id na API comercial)
    tipo: str = "NFE"  # NFE | EVENTO | INUTILIZACAO | RESUMO


@dataclass
class EventoRecuperado:
    xml: bytes
    origem: str
    chave: str | None = None
    tp_evento: str | None = None
    sequencia: int | None = None
    protocolo: str | None = None


@dataclass
class XmlRecuperado:
    xml: bytes  # nfeProc (preferencial) ou NFe sem protocolo
    origem: str
    protocolo: str | None = None
    eventos: list[EventoRecuperado] = field(default_factory=list)
    bruto: bytes | None = None  # resposta original da fonte (evidência)


@dataclass
class Situacao:
    """Resultado de consulta de situação. Não contém o XML integral da nota."""

    chave: str
    cstat: str
    xmotivo: str
    situacao: str  # AUTORIZADA|CANCELADA|DENEGADA|INEXISTENTE|INDETERMINADA
    prot_nfe: bytes | None = None
    eventos: list[EventoRecuperado] = field(default_factory=list)


@dataclass
class ResultadoSync:
    descobertos: int = 0
    recuperados: int = 0
    erros: list[str] = field(default_factory=list)


class FonteSemDados(Exception):
    """A fonte respondeu corretamente, mas não possui o documento (ex.: chave não encontrada)."""


@dataclass
class ContextoCaptura:
    empresa_id: int | None
    cnpj: str
    uf: str
    modelo: str
    ambiente: int = 1
    obter_certificado: Callable[[], object] | None = None  # devolve CertificadoA1 sob demanda
    cliente_soap: Callable[[], object] | None = None  # devolve ClienteSoap (mTLS com o A1 do emitente)
    cliente_http: Callable[[], object] | None = None  # devolve httpx.Client (mTLS) para portais oficiais
    ler_checkpoint: Callable[[str], str | None] = lambda _k: None
    gravar_checkpoint: Callable[[str, str], None] = lambda _k, _v: None
    log: Callable[[str, str], None] = lambda _n, _m: None
    inicio: datetime | None = None
    fim: datetime | None = None


class Conector(ABC):
    nome: str = ""
    descricao: str = ""
    oficial: bool = True
    comercial: bool = False
    capacidades: frozenset[Capacidade] = frozenset()

    @abstractmethod
    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        """Cobertura teórica (documental) para UF/modelo."""

    def verificar_disponibilidade(self, ctx: ContextoCaptura) -> Disponibilidade:
        return self.suporta(ctx.uf, ctx.modelo)

    def autenticar(self, ctx: ContextoCaptura) -> None:  # noqa: B027 - opcional
        """Prepara credenciais (ex.: carrega A1). Lança exceção se impossível."""

    def listar_documentos(self, ctx: ContextoCaptura) -> Iterator[DocumentoDescoberto]:
        raise NotImplementedError(f"{self.nome} não lista documentos")

    def recuperar_xml(self, ctx: ContextoCaptura, chave: str, ref_fonte: str | None = None) -> XmlRecuperado:
        raise NotImplementedError(f"{self.nome} não recupera XML")

    def recuperar_eventos(self, ctx: ContextoCaptura, chave: str) -> list[EventoRecuperado]:
        raise NotImplementedError(f"{self.nome} não recupera eventos")

    def consultar_situacao(self, ctx: ContextoCaptura, chave: str) -> Situacao:
        raise NotImplementedError(f"{self.nome} não consulta situação")

    def sincronizar(self, ctx: ContextoCaptura) -> ResultadoSync:
        """Fluxo padrão: listar e, quando o item não vier com XML, recuperar pela chave."""
        r = ResultadoSync()
        for d in self.listar_documentos(ctx):
            r.descobertos += 1
            if d.xml is None and Capacidade.RECUPERAR_XML in self.capacidades:
                try:
                    self.recuperar_xml(ctx, d.chave, d.ref_fonte)
                    r.recuperados += 1
                except Exception as e:  # noqa: BLE001
                    r.erros.append(f"{d.chave}: {e}")
        return r

    def consultar_limites(self) -> Limites:
        return Limites()

    def descrever(self) -> dict:
        return {
            "nome": self.nome, "descricao": self.descricao, "oficial": self.oficial,
            "comercial": self.comercial, "capacidades": sorted(c.value for c in self.capacidades),
            "limites": self.consultar_limites().__dict__,
        }
