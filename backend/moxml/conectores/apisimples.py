"""Conector E — API Simples (COMERCIAL, OPCIONAL, DESLIGADO POR PADRÃO).

Somente endpoints publicados em https://apisimples.com/documentacao/emitentes (lido em 19/11/2026):
  GET/POST /v1/emitentes, GET/POST /v1/emitentes/{id}            (chave da conta aps_…)
  GET /v1/saida/notas, GET /v1/saida/notas/{id}, GET /v1/saida/notas/{id}/xml,
  POST /v1/saida/sincronizar                                      (chave do emitente apse_…)
Exige contrato, chave de conta e envio do PFX + senha ao fornecedor (avaliar LGPD/sigilo fiscal).
O formato exato do corpo de /xml ("base64") não está detalhado na documentação pública: a
decodificação aceita JSON com campo xml/conteudo/base64 ou corpo base64/XML puro (NÃO COMPROVADO).
"""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable, Iterator

import httpx

from .base import (
    Capacidade, Conector, ContextoCaptura, Disponibilidade, DocumentoDescoberto, FonteSemDados, Limites,
    StatusFonte, XmlRecuperado,
)

COBERTURA_PUBLICADA = {  # https://apisimples.com/cobertura (atualizada 17/11/2026)
    "55": "AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO".split(),
    "65": "AC AL AM AP BA CE DF ES GO MA PA PB PE PI RJ RN RO RR RS SC SE SP TO".split(),
}


def decodificar_xml(resp: httpx.Response) -> bytes:
    ct = resp.headers.get("content-type", "")
    corpo = resp.content.strip()
    if "json" in ct:
        js = resp.json()
        for k in ("xml", "conteudo", "base64", "xml_base64", "data"):
            if isinstance(js, dict) and isinstance(js.get(k), str):
                corpo = js[k].encode().strip()
                break
        else:
            raise FonteSemDados("resposta JSON sem campo de XML reconhecido")
    if corpo.startswith(b"<"):
        return corpo
    try:
        dec = base64.b64decode(corpo, validate=True)
    except binascii.Error as e:
        raise FonteSemDados(f"conteúdo não é XML nem base64: {e}") from None
    if not dec.lstrip().startswith(b"<"):
        raise FonteSemDados("base64 decodificado não é XML")
    return dec


class ApiSimplesConector(Conector):
    nome = "apisimples"
    descricao = "API Simples (fornecedor comercial) — captura de saída por A1 + XML semente por série."
    oficial = False
    comercial = True
    capacidades = frozenset({Capacidade.LISTAR, Capacidade.RECUPERAR_XML})

    def __init__(self, base_url: str, chave_emitente: Callable[[str], str | None], ativo: bool = False,
                 transport: httpx.BaseTransport | None = None, chave_conta: Callable[[], str | None] = lambda: None):
        self.base_url = base_url.rstrip("/")
        self.chave_emitente = chave_emitente
        self.chave_conta = chave_conta
        self.ativo = ativo
        self.transport = transport

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        if uf not in COBERTURA_PUBLICADA.get(modelo, []):
            return Disponibilidade(StatusFonte.INDISPONIVEL, f"cobertura publicada não inclui {uf}/{modelo}")
        if not self.ativo:
            return Disponibilidade(StatusFonte.NAO_CONFIGURADO, "conector comercial desligado (requer contrato e chaves)")
        return Disponibilidade(StatusFonte.NAO_COMPROVADO, "cobertura declarada pelo fornecedor; sem teste com conta real",
                               "apisimples.com/cobertura")

    def verificar_disponibilidade(self, ctx: ContextoCaptura) -> Disponibilidade:
        d = self.suporta(ctx.uf, ctx.modelo)
        if d.ok and not self.chave_emitente(ctx.cnpj):
            return Disponibilidade(StatusFonte.NAO_CONFIGURADO, "chave apse_ do emitente não cadastrada no cofre")
        return d

    def consultar_limites(self) -> Limites:
        return Limites(itens_por_pagina=100, janela_retroativa_dias=60,
                       observacoes="XML semente deve ser dos últimos 60 dias (documentação do fornecedor).")

    def _cliente(self, token: str) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=30, transport=self.transport,
                            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})

    def _token(self, ctx: ContextoCaptura) -> str:
        if not self.ativo:
            raise RuntimeError("conector API Simples desligado")
        t = self.chave_emitente(ctx.cnpj)
        if not t:
            raise RuntimeError("chave do emitente (apse_) ausente")
        return t

    def cadastrar_emitente(self, payload: dict) -> dict:
        """POST /emitentes com a chave da conta. ``payload`` segue o exemplo documentado."""
        t = self.chave_conta()
        if not self.ativo or not t:
            raise RuntimeError("conector desligado ou chave da conta ausente")
        with self._cliente(t) as c:
            r = c.post("/emitentes", json=payload)
            r.raise_for_status()
            return r.json()

    def solicitar_sincronizacao(self, ctx: ContextoCaptura) -> None:
        with self._cliente(self._token(ctx)) as c:
            c.post("/saida/sincronizar").raise_for_status()

    def listar_documentos(self, ctx: ContextoCaptura) -> Iterator[DocumentoDescoberto]:
        from datetime import datetime
        params = {"modelo": ctx.modelo, "xml_disponivel": "true", "ordem": "emissao_desc", "limite": 100}
        if ctx.inicio:
            params["inicio"] = f"{ctx.inicio:%Y-%m-%d}"
        if ctx.fim:
            params["fim"] = f"{ctx.fim:%Y-%m-%d}"
        pagina = 1
        with self._cliente(self._token(ctx)) as c:
            while True:
                r = c.get("/saida/notas", params={**params, "page": pagina})
                if r.status_code == 429:
                    raise RuntimeError("API Simples: limite de requisições (429)")
                r.raise_for_status()
                js = r.json()
                for n in js.get("notas", []):
                    dt = None
                    if n.get("data_emissao"):
                        try:
                            dt = datetime.fromisoformat(n["data_emissao"])
                        except ValueError:
                            dt = None
                    yield DocumentoDescoberto(chave=n["chave"], origem=self.nome, data_emissao=dt, ref_fonte=n.get("id"))
                if not js.get("tem_mais"):
                    break
                pagina += 1

    def recuperar_xml(self, ctx: ContextoCaptura, chave: str, ref_fonte: str | None = None) -> XmlRecuperado:
        with self._cliente(self._token(ctx)) as c:
            if not ref_fonte:
                r = c.get("/saida/notas", params={"chave": chave, "limite": 1})
                r.raise_for_status()
                notas = r.json().get("notas", [])
                if not notas:
                    raise FonteSemDados("nota não encontrada na API Simples")
                ref_fonte = notas[0]["id"]
            r = c.get(f"/saida/notas/{ref_fonte}/xml")
            if r.status_code == 404:
                raise FonteSemDados("XML ainda indisponível no fornecedor")
            r.raise_for_status()
            return XmlRecuperado(xml=decodificar_xml(r), origem=self.nome)
