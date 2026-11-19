"""Conector oficial: NFeDistribuicaoDFe por CHAVE (consChNFe) — XML completo da NF-e 55 de saída.

Fonte: Ambiente Nacional (webservice SOAP, mTLS com o e-CNPJ do emitente). NT 2014.002.

Fundamento (verificado no código e no fixture do akretion/nfelib e do danimaribeiro/PyTrustNFe):
a consulta `distDFeInt` com `<consChNFe><chNFe>…</chNFe></consChNFe>` retorna, para quem está
vinculado ao documento (o **emitente** está, pelo seu próprio CNPJ — NÃO depende de autXML),
um `loteDistDFeInt` com `docZip` (gzip+base64). Para o emitente consultando a própria NF-e vem
o `procNFe` **completo e autorizado** (além do `resNFe` resumido) e os `procEventoNFe` vinculados.

Vantagens sobre o portal: é 100% webservice, sem CAPTCHA, sem login, sem página.
Limitações (ver LIMITACOES.md): **só NF-e 55** (a NFC-e 65 não é distribuída pelo AN); e a
devolução do `procNFe` completo ao emitente por chave precisa ser confirmada no teste real —
se vier só o `resNFe`, o conector registra a chave/situação e marca a fonte como sem XML integral.
"""

from __future__ import annotations

import base64
import gzip

from lxml import etree

from ..fiscal import chave as chv
from ..fiscal.xmlfiscal import NS
from ..sefaz import catalogo
from ..sefaz.transporte import ClienteSoap, LimiteExcedido
from .base import (
    Capacidade, Conector, ContextoCaptura, Disponibilidade, EventoRecuperado, FonteSemDados, Limites, StatusFonte,
    XmlRecuperado,
)

CSTAT_OK = "138"           # documento localizado
CSTAT_VAZIO = "137"        # nenhum documento localizado
CSTAT_CONSUMO = {"656"}    # consumo indevido


def _txt(el, tag: str) -> str | None:
    r = el.find(f".//{{{NS}}}{tag}")
    return r.text.strip() if r is not None and r.text else None


def descompactar(doczip: str) -> bytes:
    return gzip.decompress(base64.b64decode(doczip))


class DistribuicaoDFeConector(Conector):
    nome = "dist_dfe_chave"
    descricao = ("Ambiente Nacional — NFeDistribuicaoDFe por chave (consChNFe): XML completo da "
                 "NF-e 55 do emitente, por webservice, sem CAPTCHA.")
    oficial = True
    capacidades = frozenset({Capacidade.RECUPERAR_XML, Capacidade.RECUPERAR_EVENTOS})

    def __init__(self, catalogo_extra: str | None = None):
        self.extra = catalogo_extra

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        if modelo != "55":
            return Disponibilidade(StatusFonte.INDISPONIVEL,
                                   "NFeDistribuicaoDFe não distribui NFC-e (65); apenas NF-e (55)")
        try:
            catalogo.servico("NfeDistribuicaoDFe", "AN", "55", 1, self.extra)
        except catalogo.ServicoIndisponivel as e:
            return Disponibilidade(StatusFonte.INDISPONIVEL, str(e))
        return Disponibilidade(
            StatusFonte.NAO_COMPROVADO,
            "Webservice oficial (AN). Devolução do procNFe completo ao emitente por chave a confirmar no teste real.",
            "NT 2014.002; consChNFe (akretion/nfelib, danimaribeiro/PyTrustNFe)")

    def consultar_limites(self) -> Limites:
        return Limites(requisicoes_por_minuto=20, janela_retroativa_dias=90,
                       observacoes="Documentos disponíveis por ~3 meses no AN; 656 = consumo indevido (bloqueio de 1h).")

    def _cli(self, ctx: ContextoCaptura) -> ClienteSoap:
        if not ctx.cliente_soap:
            raise RuntimeError("cliente SOAP não configurado (certificado A1 ausente)")
        return ctx.cliente_soap()  # type: ignore[return-value]

    def _consultar_chave(self, ctx: ContextoCaptura, chave: str):
        ck = chv.analisar(chave)
        srv = catalogo.servico("NfeDistribuicaoDFe", "AN", "55", ctx.ambiente, self.extra)
        cuf = chv.UF_CODIGO[ctx.uf]
        tag_doc = "CNPJ" if len(ctx.cnpj) == 14 else "CPF"
        conteudo = (f'<distDFeInt xmlns="{NS}" versao="{srv.versao}"><tpAmb>{ctx.ambiente}</tpAmb>'
                    f"<cUFAutor>{cuf}</cUFAutor><{tag_doc}>{ctx.cnpj}</{tag_doc}>"
                    f"<consChNFe><chNFe>{ck.chave}</chNFe></consChNFe></distDFeInt>")
        cli = self._cli(ctx)
        bloqueio = cli.limitador.bloqueio(f"{self.nome}:{ctx.cnpj}")
        if bloqueio:
            raise LimiteExcedido(f"distribuição suspensa para {ctx.cnpj}: {bloqueio[1]}", bloqueio[0])
        ret = cli.enviar(srv, conteudo)
        cstat = _txt(ret, "cStat")
        if cstat in CSTAT_CONSUMO:
            cli.limitador.bloquear(f"{self.nome}:{ctx.cnpj}", 3600, "656 consumo indevido (DistDFe)")
            raise LimiteExcedido("DistDFe: consumo indevido (656); aguardar 1 hora", 0)
        return ck, cstat, _txt(ret, "xMotivo") or "", ret

    def _documentos(self, ret: etree._Element) -> list[tuple[str, bytes]]:
        """Retorna (schema, xml) de cada docZip descompactado."""
        out = []
        for dz in ret.findall(f".//{{{NS}}}docZip"):
            if dz.text:
                try:
                    out.append((dz.get("schema", ""), descompactar(dz.text.strip())))
                except (OSError, ValueError):
                    continue
        return out

    def recuperar_xml(self, ctx: ContextoCaptura, chave: str, ref_fonte: str | None = None) -> XmlRecuperado:
        ck, cstat, xmotivo, ret = self._consultar_chave(ctx, chave)
        if cstat == CSTAT_VAZIO:
            raise FonteSemDados(f"DistDFe: nenhum documento para a chave (137 {xmotivo})")
        if cstat != CSTAT_OK:
            raise RuntimeError(f"DistDFe: cStat {cstat} {xmotivo}")
        docs = self._documentos(ret)
        proc = next((xml for sch, xml in docs if "procNFe" in sch or xml.lstrip()[:60].startswith(b"<nfeProc")), None)
        eventos = [EventoRecuperado(xml=xml, origem=self.nome)
                   for sch, xml in docs if "procEvento" in sch or b"procEventoNFe" in xml[:120]]
        if proc is None:
            # Só veio o resumo (resNFe): a fonte não entregou o XML integral ao emitente por esta via.
            raise FonteSemDados("DistDFe retornou apenas o resumo (resNFe), sem o procNFe completo")
        return XmlRecuperado(xml=proc, origem=self.nome, eventos=eventos, bruto=etree.tostring(ret, encoding="utf-8"))

    def recuperar_eventos(self, ctx: ContextoCaptura, chave: str) -> list[EventoRecuperado]:
        try:
            return self.recuperar_xml(ctx, chave).eventos
        except FonteSemDados:
            return []
