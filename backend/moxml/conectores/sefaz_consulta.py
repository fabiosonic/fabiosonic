"""Conector oficial: NFeConsultaProtocolo 4.00 (autorizador SVRS para o RJ, modelos 55 e 65).

Duas funções:

1. **Situação e eventos por chave** — retorna protNFe (autorização/denegação) e os
   procEventoNFe vinculados (cancelamento, CC-e etc.). NÃO devolve o XML integral.

2. **Descoberta de chaves por numeração (sem autXML, sem listagem)** — fundamento
   oficial: MOC 7.0, Web Service NFeConsultaProtocolo, regras de validação:
     J03  acesso ao BD pela chave natural CNPJ/CPF emitente + modelo + série + número;
          inexistente → 217.
     J04  cNF da chave consultada difere do existente → 562; "opcionalmente, concatenar na
          mensagem de erro a Chave de Acesso da NF-e existente no BD" quando o CNPJ base do
          certificado de transmissão for o do emitente (NT 2010.007).
     J05  mês divergente → 561.   J06  outra divergência → 613.   J02k > 6 meses → 526.
   Para cada número da série é feita UMA consulta com a chave candidata (campos conhecidos
   pelo XML semente + número). Não há tentativa de adivinhar o cNF: a própria SEFAZ informa a
   chave existente ao emitente. Se o autorizador não concatenar a chave (implementação
   "opcional"), a descoberta é marcada como IMPOSSÍVEL PELO MÉTODO para aquele autorizador.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime

from lxml import etree

from ..fiscal import chave as chv
from ..fiscal.xmlfiscal import NS
from ..sefaz import catalogo
from ..sefaz.transporte import ClienteSoap, LimiteExcedido
from .base import (
    Capacidade, Conector, ContextoCaptura, Disponibilidade, DocumentoDescoberto, EventoRecuperado, Limites,
    Situacao, StatusFonte,
)

RE_CHAVE_MSG = re.compile(r"chNFe\s*:\s*([0-9A-Z]{44})", re.I)
CSTAT_ENCONTRADA = {"100", "101", "110", "150", "151", "155", "301", "302", "303"}
TP_EMIS_ALTERNATIVOS = ("9", "6", "7", "4", "5", "2", "3")  # testados só após cStat 613


class DescobertaImpossivel(RuntimeError):
    """O autorizador não devolve a chave existente na rejeição 562."""


@dataclass
class ResultadoProbe:
    numero: int
    cstat: str
    xmotivo: str
    chave: str | None = None
    situacao: Situacao | None = None


def _txt(el, tag: str) -> str | None:
    r = el.find(f".//{{{NS}}}{tag}")
    return r.text.strip() if r is not None and r.text else None


def _prot_evento(pe) -> str | None:
    ret = pe.find(f"{{{NS}}}retEvento")
    return _txt(ret if ret is not None else pe, "nProt")


def interpretar_ret_cons_sit(ret: etree._Element, chave_consultada: str) -> Situacao:
    cstat = _txt(ret, "cStat") or ""
    xmotivo = _txt(ret, "xMotivo") or ""
    prot = ret.find(f"{{{NS}}}protNFe")
    prot_xml = etree.tostring(prot, encoding="utf-8") if prot is not None else None
    eventos: list[EventoRecuperado] = []
    for pe in ret.findall(f"{{{NS}}}procEventoNFe"):
        raw = etree.tostring(pe, encoding="utf-8")
        if b"xmlns=" not in raw.split(b">", 1)[0]:
            raw = raw.replace(b"<procEventoNFe", f'<procEventoNFe xmlns="{NS}"'.encode(), 1)
        eventos.append(EventoRecuperado(
            xml=raw, origem="sefaz_consulta", chave=_txt(pe, "chNFe"), tp_evento=_txt(pe, "tpEvento"),
            sequencia=int(_txt(pe, "nSeqEvento") or 1), protocolo=_prot_evento(pe),
        ))
    ch = chave_consultada
    if prot is not None and _txt(prot, "chNFe"):
        ch = _txt(prot, "chNFe")  # type: ignore[assignment]
    cstat_prot = _txt(prot, "cStat") if prot is not None else None
    if cstat in ("101", "151", "155") or any(e.tp_evento in ("110111", "110112") for e in eventos):
        sit = "CANCELADA"
    elif cstat in ("110", "301", "302", "303") or cstat_prot in ("110", "301", "302", "303"):
        sit = "DENEGADA"
    elif cstat in ("100", "150"):
        sit = "AUTORIZADA"
    elif cstat == "217":
        sit = "INEXISTENTE"
    else:
        sit = "INDETERMINADA"
    return Situacao(chave=ch, cstat=cstat, xmotivo=xmotivo, situacao=sit, prot_nfe=prot_xml, eventos=eventos)


class SefazConsultaConector(Conector):
    nome = "sefaz_consulta"
    descricao = ("SEFAZ autorizadora — NFeConsultaProtocolo 4.00: situação, protocolo e eventos por chave; "
                 "descoberta de chaves por série/número via regra J04 (cStat 562) com o A1 do emitente.")
    oficial = True
    capacidades = frozenset({Capacidade.SITUACAO, Capacidade.RECUPERAR_EVENTOS, Capacidade.LISTAR})

    def __init__(self, max_falhas_consecutivas: int = 10, catalogo_extra: str | None = None):
        self.max_falhas = max_falhas_consecutivas
        self.extra = catalogo_extra

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        try:
            catalogo.servico("NfeConsultaProtocolo", uf, modelo, 1, self.extra)
        except catalogo.ServicoIndisponivel as e:
            return Disponibilidade(StatusFonte.INDISPONIVEL, str(e))
        return Disponibilidade(
            StatusFonte.NAO_COMPROVADO,
            "Serviço oficial documentado; descoberta J04/562 depende de o autorizador concatenar a chave "
            "(implementação opcional no MOC). Validar com certificado real.",
            "MOC 7.0 — NFeConsultaProtocolo, regras J03–J06",
        )

    def consultar_limites(self) -> Limites:
        return Limites(requisicoes_por_minuto=30, janela_retroativa_dias=180,
                       observacoes="J02k: chave com AAMM > 6 meses pode ser rejeitada (526). cStat 656 bloqueia 1h.")

    # --- situação ---------------------------------------------------------------------
    def _cliente(self, ctx: ContextoCaptura) -> ClienteSoap:
        if not ctx.cliente_soap:
            raise RuntimeError("cliente SOAP não configurado (certificado A1 ausente)")
        return ctx.cliente_soap()  # type: ignore[return-value]

    def consultar_situacao(self, ctx: ContextoCaptura, chave: str) -> Situacao:
        ck = chv.analisar(chave)
        srv = catalogo.servico("NfeConsultaProtocolo", ck.uf, ck.modelo, ctx.ambiente, self.extra)
        msg = (f'<consSitNFe xmlns="{NS}" versao="{srv.versao}"><tpAmb>{ctx.ambiente}</tpAmb>'
               f"<xServ>CONSULTAR</xServ><chNFe>{ck.chave}</chNFe></consSitNFe>")
        cli = self._cliente(ctx)
        bloqueio = cli.limitador.bloqueio(f"{self.nome}:{ctx.cnpj}")
        if bloqueio:
            raise LimiteExcedido(f"consultas suspensas para {ctx.cnpj}: {bloqueio[1]}", bloqueio[0])
        ret = cli.enviar(srv, msg)
        sit = interpretar_ret_cons_sit(ret, ck.chave)
        if sit.cstat == "656":
            cli.limitador.bloquear(f"{self.nome}:{ctx.cnpj}", 3600, "cStat 656 consumo indevido")
            raise LimiteExcedido("SEFAZ sinalizou consumo indevido (656); aguardar 1 hora", 0)
        return sit

    def recuperar_eventos(self, ctx: ContextoCaptura, chave: str) -> list[EventoRecuperado]:
        return self.consultar_situacao(ctx, chave).eventos

    # --- descoberta por numeração -------------------------------------------------------
    def sondar_numero(self, ctx: ContextoCaptura, serie: int, numero: int, ref: datetime) -> ResultadoProbe:
        """Uma consulta por número. Tenta AAMM de referência; em 561 tenta meses vizinhos;
        em 613 tenta tpEmis alternativos (contingência). Nunca varia o cNF."""
        meses = [ref]
        for delta in (-1, 1, -2):
            m = ref.month + delta
            a = ref.year + (m - 1) // 12
            meses.append(ref.replace(year=a, month=(m - 1) % 12 + 1, day=1))
        tentativas: list[tuple[datetime, str]] = [(meses[0], "1")]
        vistos: set[tuple[str, str]] = set()
        ultimo: ResultadoProbe | None = None
        while tentativas:
            dt, tp = tentativas.pop(0)
            if (f"{dt:%y%m}", tp) in vistos:
                continue
            vistos.add((f"{dt:%y%m}", tp))
            candidata = chv.montar_chave(ctx.uf, dt.year, dt.month, ctx.cnpj, ctx.modelo, serie, numero, int(tp), "0" * 8)
            sit = self.consultar_situacao(ctx, candidata)
            ultimo = ResultadoProbe(numero, sit.cstat, sit.xmotivo, situacao=sit)
            if sit.cstat in CSTAT_ENCONTRADA:
                ultimo.chave = sit.chave
                return ultimo
            if sit.cstat == "562":
                m = RE_CHAVE_MSG.search(sit.xmotivo)
                if not m:
                    raise DescobertaImpossivel(
                        "autorizador respondeu 562 sem concatenar a chave existente (MOC J04: opcional)")
                achada = chv.analisar(m.group(1))
                if (achada.cnpj, achada.modelo, achada.serie, achada.numero) != (ctx.cnpj.zfill(14), ctx.modelo, serie, numero):
                    raise DescobertaImpossivel(f"chave devolvida não corresponde ao número consultado: {achada.chave}")
                ultimo.chave = achada.chave
                return ultimo
            if sit.cstat == "561":
                tentativas += [(m_, tp) for m_ in meses[1:]]
                continue
            if sit.cstat == "613":
                tentativas += [(dt, t) for t in TP_EMIS_ALTERNATIVOS]
                continue
            return ultimo  # 217 inexistente, 526 muito antiga, outros
        assert ultimo is not None
        return ultimo

    def descobrir_serie(self, ctx: ContextoCaptura, serie: int, a_partir_de: int,
                        referencia: datetime | None = None, limite: int = 5000) -> Iterator[ResultadoProbe]:
        """Percorre a série a partir de ``a_partir_de`` até ``max_falhas`` inexistências seguidas."""
        ref = referencia or datetime.now()
        falhas = 0
        numero = a_partir_de
        while falhas < self.max_falhas and numero < a_partir_de + limite:
            r = self.sondar_numero(ctx, serie, numero, ref)
            yield r
            if r.chave:
                falhas = 0
                ck = chv.analisar(r.chave)
                ref = ref.replace(year=ck.ano, month=ck.mes, day=1)
            elif r.cstat == "217":
                falhas += 1
            elif r.cstat == "526":
                break
            else:
                falhas += 1
            numero += 1

    def listar_documentos(self, ctx: ContextoCaptura) -> Iterator[DocumentoDescoberto]:
        """Usa checkpoint ``serie:<n>`` = último número identificado. Séries vêm do checkpoint ``series``."""
        series = [int(s) for s in (ctx.ler_checkpoint("series") or "").split(",") if s.strip()]
        for serie in series:
            ult = int(ctx.ler_checkpoint(f"serie:{serie}") or "0")
            for r in self.descobrir_serie(ctx, serie, ult + 1):
                if r.chave:
                    ctx.gravar_checkpoint(f"serie:{serie}", str(r.numero))
                    yield DocumentoDescoberto(chave=r.chave, origem=self.nome)
