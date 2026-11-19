"""Transporte SOAP 1.2 sobre HTTPS com certificado de cliente (mTLS).

- Envelope no padrão do MOC (nfeDadosMsg no Body, sem cabeçalho nfeCabecMsg na 4.00).
- Timeout, retentativas com backoff exponencial apenas para falhas de rede/HTTP 5xx.
- Rejeições de negócio (cStat) NUNCA são retentadas automaticamente aqui.
- Limitador de taxa por host (token bucket) + bloqueios temporários (ex.: cStat 656).
- Registro das requisições/respostas (sem dados do certificado) para auditoria.
"""

from __future__ import annotations

import logging
import ssl
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx
from lxml import etree

from .catalogo import Servico

log = logging.getLogger("moxml.sefaz")

SOAP12 = "http://www.w3.org/2003/05/soap-envelope"


class ErroTransporte(RuntimeError):
    pass


class ErroRede(ErroTransporte):
    pass


class RespostaInvalida(ErroTransporte):
    pass


class LimiteExcedido(ErroTransporte):
    """Limite local atingido ou fonte sinalizou consumo indevido; aguardar ``ate``."""

    def __init__(self, msg: str, ate: float):
        super().__init__(msg)
        self.ate = ate


@dataclass
class LimitadorTaxa:
    """Token bucket por chave (host). Thread-safe."""

    por_minuto: dict[str, float] = field(default_factory=dict)
    padrao_por_minuto: float = 20.0
    _estado: dict[str, tuple[float, float]] = field(default_factory=dict)
    _bloqueios: dict[str, tuple[float, str]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    relogio: Callable[[], float] = time.monotonic
    dormir: Callable[[float], None] = time.sleep
    espera_maxima: float = 10.0

    def bloquear(self, chave: str, segundos: float, motivo: str) -> None:
        with self._lock:
            self._bloqueios[chave] = (self.relogio() + segundos, motivo)

    def bloqueio(self, chave: str) -> tuple[float, str] | None:
        with self._lock:
            b = self._bloqueios.get(chave)
            if b and b[0] > self.relogio():
                return b
            self._bloqueios.pop(chave, None)
            return None

    def adquirir(self, chave: str) -> None:
        b = self.bloqueio(chave)
        if b:
            raise LimiteExcedido(f"bloqueado até {b[0] - self.relogio():.0f}s: {b[1]}", b[0])
        taxa = self.por_minuto.get(chave, self.padrao_por_minuto) / 60.0
        capacidade = max(1.0, taxa * 60.0 / 4)
        while True:
            with self._lock:
                agora = self.relogio()
                tokens, ultimo = self._estado.get(chave, (capacidade, agora))
                tokens = min(capacidade, tokens + (agora - ultimo) * taxa)
                if tokens >= 1:
                    self._estado[chave] = (tokens - 1, agora)
                    return
                espera = (1 - tokens) / taxa
                self._estado[chave] = (tokens, agora)
            if espera > self.espera_maxima:
                raise LimiteExcedido(f"limite local de {taxa * 60:.0f}/min para {chave}", self.relogio() + espera)
            self.dormir(espera)


def envelope(servico: Servico, conteudo: str) -> bytes:
    """Monta o envelope SOAP 1.2. ``conteudo`` é o XML da mensagem sem declaração."""
    ns = servico.namespace_wsdl
    corpo = f'<nfeDadosMsg xmlns="{ns}">{conteudo}</nfeDadosMsg>'
    if servico.wrapper:
        corpo = f'<{servico.wrapper} xmlns="{ns}">{corpo}</{servico.wrapper}>'
    env = (
        '<?xml version="1.0" encoding="utf-8"?>'
        f'<soap12:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap12="{SOAP12}">'
        f"<soap12:Body>{corpo}</soap12:Body></soap12:Envelope>"
    )
    return env.encode("utf-8")


_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def extrair_retorno(resposta: bytes) -> etree._Element:
    """Retorna o primeiro elemento do namespace da NF-e dentro do Body (ex.: retConsSitNFe)."""
    try:
        raiz = etree.fromstring(resposta, _PARSER)
    except etree.XMLSyntaxError as e:
        raise RespostaInvalida(f"resposta não é XML: {e}") from None
    body = raiz.find(f"{{{SOAP12}}}Body")
    if body is None:
        body = raiz.find("{http://schemas.xmlsoap.org/soap/envelope/}Body")
    if body is None:
        raise RespostaInvalida("resposta sem SOAP Body")
    fault = body.find(f"{{{SOAP12}}}Fault")
    if fault is not None:
        raise RespostaInvalida("SOAP Fault: " + " ".join(fault.itertext()).strip()[:500])
    for el in body.iter():
        if isinstance(el.tag, str) and etree.QName(el).namespace == "http://www.portalfiscal.inf.br/nfe":
            return el
    raise RespostaInvalida("resposta sem elemento do namespace da NF-e")


class ClienteSoap:
    """Cliente SOAP com mTLS. ``transport`` permite injetar httpx.MockTransport (testes/simulado)."""

    def __init__(
        self,
        contexto_ssl: ssl.SSLContext | None,
        timeout: float = 30.0,
        retentativas: int = 3,
        limitador: LimitadorTaxa | None = None,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        registrar: Callable[[str, bytes, bytes | None, str | None], None] | None = None,
    ):
        if transport is None and contexto_ssl is None:
            raise ValueError("contexto SSL com certificado de cliente é obrigatório")
        if contexto_ssl is not None and (contexto_ssl.verify_mode != ssl.CERT_REQUIRED or not contexto_ssl.check_hostname):
            raise ValueError("verificação TLS do servidor não pode ser desabilitada")
        self._cliente = httpx.Client(verify=contexto_ssl if transport is None else True, timeout=timeout,
                                     transport=transport, http2=False)
        self.retentativas = max(1, retentativas)
        self.limitador = limitador or LimitadorTaxa()
        self.dormir = dormir
        self.registrar = registrar

    def fechar(self) -> None:
        self._cliente.close()

    def enviar(self, servico: Servico, conteudo: str) -> etree._Element:
        corpo = envelope(servico, conteudo)
        host = urlparse(servico.url).netloc
        headers = {"Content-Type": f'application/soap+xml; charset=utf-8; action="{servico.action}"'}
        ultimo_erro: Exception | None = None
        for tentativa in range(1, self.retentativas + 1):
            self.limitador.adquirir(host)
            try:
                r = self._cliente.post(servico.url, content=corpo, headers=headers)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
                ultimo_erro = ErroRede(f"{type(e).__name__}: {e}")
                log.warning("falha de rede em %s (tentativa %d/%d): %s", servico.nome, tentativa, self.retentativas, e)
            else:
                if self.registrar:
                    self.registrar(servico.nome, corpo, r.content, None)
                if r.status_code >= 500 and r.status_code != 500:
                    ultimo_erro = ErroRede(f"HTTP {r.status_code}")
                elif r.status_code == 429:
                    self.limitador.bloquear(host, 60, "HTTP 429 da fonte")
                    raise LimiteExcedido("HTTP 429 recebido da fonte", time.monotonic() + 60)
                elif r.status_code >= 400 and r.status_code != 500:
                    raise ErroTransporte(f"HTTP {r.status_code}: {r.text[:300]}")
                else:
                    # HTTP 500 pode conter SOAP Fault: extrair_retorno levanta RespostaInvalida
                    return extrair_retorno(r.content)
            if tentativa < self.retentativas:
                self.dormir(min(60.0, 2 ** tentativa))
        assert ultimo_erro is not None
        if self.registrar:
            self.registrar(servico.nome, corpo, None, str(ultimo_erro))
        raise ultimo_erro
