"""Conector oficial: Serviços de Apoio à Escrituração da NFC-e (SAE-NFC-e).

Hoje publicado apenas pela SEFAZ-SP (NT "Serviços de Apoio à Escrituração da NFC-e" v1.00).
Para o RJ, ``suporta`` devolve INDISPONIVEL com o motivo documentado. Se a SVRS/SEFAZ-RJ
publicar serviço equivalente, basta incluir a UF no catálogo (sem alterar este código).

Regras (NT SAE v1.00): CNPJ do e-CNPJ é o filtro; até 2000 chaves por chamada (cStat 101 →
paginar por dhEmisUltNfce); janela máxima de 100 dias (104/207); limite por IP (656).
O retorno do download traz um nfeProc SIMPLIFICADO (dhInc, nProt, NFe) — sem protNFe — e
procEventoNFe simplificados; o motor completa o protocolo pela consulta de situação.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta

from lxml import etree

from ..fiscal import chave as chv
from ..fiscal.xmlfiscal import NS
from ..sefaz import catalogo
from ..sefaz.transporte import ClienteSoap, LimiteExcedido
from .base import (
    Capacidade, Conector, ContextoCaptura, Disponibilidade, DocumentoDescoberto, EventoRecuperado, FonteSemDados,
    Limites, StatusFonte, XmlRecuperado,
)

JANELA_DIAS = 100


def _t(el, tag):
    r = el.find(f".//{{{NS}}}{tag}")
    return r.text.strip() if r is not None and r.text else None


class SefazSaeConector(Conector):
    nome = "sefaz_sae_nfce"
    descricao = "SAE-NFC-e (NFCeListagemChaves + NFCeDownloadXML) — publicado apenas pela SEFAZ-SP."
    oficial = True
    capacidades = frozenset({Capacidade.LISTAR, Capacidade.RECUPERAR_XML, Capacidade.RECUPERAR_EVENTOS})

    def __init__(self, catalogo_extra: str | None = None):
        self.extra = catalogo_extra

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        if modelo != "65":
            return Disponibilidade(StatusFonte.INDISPONIVEL, "SAE atende somente NFC-e (modelo 65)")
        try:
            catalogo.servico("NFCeListagemChaves", uf, "65", 1, self.extra)
        except catalogo.ServicoIndisponivel as e:
            return Disponibilidade(StatusFonte.INDISPONIVEL, str(e))
        return Disponibilidade(StatusFonte.NAO_COMPROVADO, "NT SAE-NFC-e publicada; sem teste com A1 autorizado",
                               "SAE-NFC-e v1.0.0 (SEFAZ-SP)")

    def consultar_limites(self) -> Limites:
        return Limites(requisicoes_por_minuto=10, janela_retroativa_dias=JANELA_DIAS, itens_por_pagina=2000,
                       observacoes="Limite por IP não publicado numericamente; 656 bloqueia por 1h.")

    def _cli(self, ctx: ContextoCaptura) -> ClienteSoap:
        if not ctx.cliente_soap:
            raise RuntimeError("cliente SOAP não configurado")
        return ctx.cliente_soap()  # type: ignore[return-value]

    def _enviar(self, ctx: ContextoCaptura, nome: str, conteudo: str):
        srv = catalogo.servico(nome, ctx.uf, "65", ctx.ambiente, self.extra)
        ret = self._cli(ctx).enviar(srv, conteudo.format(v=srv.versao))
        if _t(ret, "cStat") == "656":
            self._cli(ctx).limitador.bloquear(f"{self.nome}:{ctx.cnpj}", 3600, "656 consumo indevido")
            raise LimiteExcedido("SAE: consumo indevido (656)", 0)
        return ret

    def listar_documentos(self, ctx: ContextoCaptura) -> Iterator[DocumentoDescoberto]:
        agora = datetime.now()
        inicio = max(ctx.inicio or agora - timedelta(days=JANELA_DIAS - 1), agora - timedelta(days=JANELA_DIAS - 1))
        fim = ctx.fim
        while True:
            fim_tag = f"<dataHoraFinal>{fim:%Y-%m-%dT%H:%M}</dataHoraFinal>" if fim else ""
            ret = self._enviar(ctx, "NFCeListagemChaves",
                               f'<nfceListagemChaves versao="{{v}}" xmlns="{NS}"><tpAmb>{ctx.ambiente}</tpAmb>'
                               f"<dataHoraInicial>{inicio:%Y-%m-%dT%H:%M}</dataHoraInicial>{fim_tag}</nfceListagemChaves>")
            cstat = _t(ret, "cStat")
            if cstat == "107":
                return
            if cstat not in ("100", "101"):
                raise RuntimeError(f"SAE listagem: {cstat} {_t(ret, 'xMotivo')}")
            for el in ret.findall(f"{{{NS}}}chNFCe"):
                if chv.valida(el.text or ""):
                    yield DocumentoDescoberto(chave=el.text.strip(), origem=self.nome)
            if cstat == "100":
                return
            prox = _t(ret, "dhEmisUltNfce")
            if not prox:
                return
            novo = datetime.fromisoformat(prox[:16])
            if novo <= inicio:  # proteção contra laço: período mínimo de 1 minuto
                novo = inicio + timedelta(minutes=1)
            inicio = novo

    def recuperar_xml(self, ctx: ContextoCaptura, chave: str, ref_fonte: str | None = None) -> XmlRecuperado:
        ck = chv.analisar(chave)
        ret = self._enviar(ctx, "NFCeDownloadXML",
                           f'<nfceDownloadXML versao="{{v}}" xmlns="{NS}"><tpAmb>{ctx.ambiente}</tpAmb>'
                           f"<chNFCe>{ck.chave}</chNFCe></nfceDownloadXML>")
        cstat = _t(ret, "cStat")
        if cstat == "205":
            raise FonteSemDados("SAE: chave não encontrada (205)")
        if cstat != "200":
            raise RuntimeError(f"SAE download: {cstat} {_t(ret, 'xMotivo')}")
        proc = ret.find(f"{{{NS}}}proc")
        nfe_proc = proc.find(f"{{{NS}}}nfeProc") if proc is not None else None
        nfe = nfe_proc.find(f"{{{NS}}}NFe") if nfe_proc is not None else None
        if nfe is None:
            raise FonteSemDados("SAE: resposta 200 sem NFe")
        eventos = []
        for pe in proc.findall(f"{{{NS}}}procEventoNFe"):
            ev = pe.find(f"{{{NS}}}evento")
            if ev is not None:
                eventos.append(EventoRecuperado(xml=etree.tostring(ev, encoding="utf-8"), origem=self.nome,
                                                chave=_t(ev, "chNFe"), tp_evento=_t(ev, "tpEvento"),
                                                sequencia=int(_t(ev, "nSeqEvento") or 1), protocolo=_t(pe, "nProt")))
        return XmlRecuperado(xml=etree.tostring(nfe, encoding="utf-8"), origem=self.nome,
                             protocolo=_t(nfe_proc, "nProt"), eventos=eventos,
                             bruto=etree.tostring(ret, encoding="utf-8"))

    def recuperar_eventos(self, ctx: ContextoCaptura, chave: str) -> list[EventoRecuperado]:
        return self.recuperar_xml(ctx, chave).eventos
