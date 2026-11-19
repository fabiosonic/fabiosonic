"""SEFAZ/portal falsos (httpx.MockTransport) que reproduzem as regras documentadas.

- NFeConsultaProtocolo: J03 (217), J04 (562 com [chNFe:...] se ``concatena_chave``), J05 (561), J06 (613),
  retorno 100/101 com protNFe e procEventoNFe.
- Portal SVRS DownloadXMLDFe: GET com formulário (token oculto + campo de chave), POST devolve o XML;
  opção ``captcha`` simula desafio humano.
- SAE-NFC-e (SP): listagem com paginação (cStat 101 / dhEmisUltNfce) e download.
- Injeção de falhas: rede, timeout, resposta inválida, 656.
"""

from __future__ import annotations

import base64
import gzip
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from lxml import etree

from moxml.fiscal import chave as chv

from . import gerador

NS = "http://www.portalfiscal.inf.br/nfe"
SOAP12 = "http://www.w3.org/2003/05/soap-envelope"


@dataclass
class NotaLab:
    chave: str
    cnpj: str
    modelo: str
    serie: int
    numero: int
    emissao: datetime
    xml_proc: bytes
    xml_nfe: bytes
    prot: bytes
    eventos: list[bytes] = field(default_factory=list)
    cancelada: bool = False


@dataclass
class Emissor:
    cnpj: str
    razao: str
    uf: str
    chave_priv: object
    cert: object
    pfx: bytes


class Laboratorio:
    def __init__(self, concatena_chave: bool = True, captcha: bool = False, limite_sae: int = 2000):
        self.notas: dict[str, NotaLab] = {}
        self.emissores: dict[str, Emissor] = {}
        self.concatena_chave = concatena_chave
        self.captcha = captcha
        self.limite_sae = limite_sae
        self.falhas_rede = 0
        self.timeouts = 0
        self.respostas_invalidas = 0
        self.consumo_indevido = False
        self.chamadas: list[str] = []

    # ------------------------------------------------------------------ dados
    def emissor(self, cnpj: str, razao: str, uf: str = "RJ", dias_validade: int = 365) -> Emissor:
        if cnpj not in self.emissores:
            pfx, k, c = gerador.gerar_certificado_teste(cnpj, razao, dias_validade)
            self.emissores[cnpj] = Emissor(cnpj, razao, uf, k, c, pfx)
        return self.emissores[cnpj]

    def emitir(self, cnpj: str, modelo: str, serie: int, numero: int, emissao: datetime,
               valor: Decimal | None = None, tp_emis: int = 1) -> NotaLab:
        e = self.emissores[cnpj]
        valor = valor if valor is not None else Decimal(random.randint(1000, 500000)) / 100
        ch, proc, prot = gerador.gerar_nfe(cnpj, e.razao, e.uf, modelo, serie, numero, emissao, e.chave_priv, e.cert,
                                           valor=valor, tp_emis=tp_emis)
        _, nfe, _ = gerador.gerar_nfe(cnpj, e.razao, e.uf, modelo, serie, numero, emissao, e.chave_priv, e.cert,
                                      valor=valor, cnf=ch[35:43], protocolo=False, tp_emis=tp_emis)
        n = NotaLab(ch, cnpj, modelo, serie, numero, emissao, proc, nfe, prot)
        self.notas[ch] = n
        return n

    def cancelar(self, chave: str, quando: datetime | None = None) -> bytes:
        n = self.notas[chave]
        e = self.emissores[n.cnpj]
        ev = gerador.gerar_evento_cancelamento(chave, n.cnpj, quando or n.emissao + timedelta(minutes=10), e.chave_priv, e.cert)
        n.eventos.append(ev)
        n.cancelada = True
        return ev

    def carta_correcao(self, chave: str, seq: int = 1) -> bytes:
        n = self.notas[chave]
        e = self.emissores[n.cnpj]
        ev = gerador.gerar_evento_cancelamento(chave, n.cnpj, n.emissao + timedelta(hours=2), e.chave_priv, e.cert,
                                               tp_evento="110110", seq=seq)
        n.eventos.append(ev)
        return ev

    def popular(self, cnpj: str, razao: str, modelo: str, serie: int, inicio: int, qtd: int, base: datetime,
                pular: set[int] = frozenset(), cancelar: set[int] = frozenset()) -> list[NotaLab]:
        self.emissor(cnpj, razao)
        out = []
        for i in range(qtd):
            num = inicio + i
            if num in pular:
                continue
            n = self.emitir(cnpj, modelo, serie, num, base + timedelta(hours=i))
            if num in cancelar:
                self.cancelar(n.chave)
            out.append(n)
        return out

    def por_numero(self, cnpj: str, modelo: str, serie: int, numero: int) -> NotaLab | None:
        for n in self.notas.values():
            if (n.cnpj, n.modelo, n.serie, n.numero) == (cnpj, modelo, serie, numero):
                return n
        return None

    # ------------------------------------------------------------------ transporte
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self._tratar)

    def _tratar(self, req: httpx.Request) -> httpx.Response:
        self.chamadas.append(f"{req.method} {req.url.path}")
        if self.falhas_rede > 0:
            self.falhas_rede -= 1
            raise httpx.ConnectError("falha de rede simulada", request=req)
        if self.timeouts > 0:
            self.timeouts -= 1
            raise httpx.ReadTimeout("timeout simulado", request=req)
        if self.respostas_invalidas > 0:
            self.respostas_invalidas -= 1
            return httpx.Response(200, content=b"<html>erro interno</html>")
        p = req.url.path.lower()
        if "downloadxmldfe" in p:
            return self._portal(req)
        corpo = etree.fromstring(req.content)
        msg = next(el for el in corpo.iter() if isinstance(el.tag, str) and etree.QName(el).namespace == NS)
        nome = etree.QName(msg).localname
        if self.consumo_indevido:
            return self._soap(f'<retConsSitNFe xmlns="{NS}" versao="4.00"><tpAmb>1</tpAmb><verAplic>LAB</verAplic>'
                              f"<cStat>656</cStat><xMotivo>Rejeição: Consumo Indevido</xMotivo><cUF>33</cUF></retConsSitNFe>")
        if nome == "consSitNFe":
            return self._consulta(msg)
        if nome == "distDFeInt":
            return self._distdfe(msg)
        if nome == "nfceListagemChaves":
            return self._sae_lista(msg)
        if nome == "nfceDownloadXML":
            return self._sae_download(msg)
        return httpx.Response(500, content=b"servico nao simulado")

    def _soap(self, conteudo: str) -> httpx.Response:
        env = (f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="{SOAP12}"><soap:Body>'
               f'<nfeResultMsg xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/X">{conteudo}</nfeResultMsg>'
               f"</soap:Body></soap:Envelope>")
        return httpx.Response(200, content=env.encode(), headers={"content-type": "application/soap+xml"})

    def _consulta(self, msg) -> httpx.Response:
        ch = msg.findtext(f"{{{NS}}}chNFe")
        ck = chv.analisar(ch)
        nota = self.por_numero(ck.cnpj, ck.modelo, ck.serie, ck.numero)

        def ret(cstat: str, motivo: str, extra: str = "") -> httpx.Response:
            return self._soap(f'<retConsSitNFe xmlns="{NS}" versao="4.00"><tpAmb>1</tpAmb><verAplic>SVRS-LAB</verAplic>'
                              f"<cStat>{cstat}</cStat><xMotivo>{motivo}</xMotivo><cUF>{ch[:2]}</cUF>"
                              f"<dhRecbto>{datetime.now(UTC).isoformat()}</dhRecbto><chNFe>{ch}</chNFe>{extra}</retConsSitNFe>")
        if nota is None:
            return ret("217", "Rejeição: NF-e não consta na base de dados da SEFAZ")
        if ch[35:43] != nota.chave[35:43]:
            sufixo = f" [chNFe:{nota.chave}]" if self.concatena_chave else ""
            return ret("562", "Rejeição: Código Numérico informado na Chave de Acesso difere do Código Numérico da NF-e" + sufixo)
        if ch[2:6] != nota.chave[2:6]:
            return ret("561", "Rejeição: Mês de Emissão informado na Chave de Acesso difere do Mês de Emissão da NF-e")
        if ch != nota.chave:
            return ret("613", "Rejeição: Chave de Acesso difere da existente em BD")
        prot = nota.prot.decode()
        evs = "".join(etree.tostring(etree.fromstring(e), encoding="unicode") for e in nota.eventos)
        if nota.cancelada:
            return ret("101", "Cancelamento de NF-e homologado", prot + evs)
        return ret("100", "Autorizado o uso da NF-e", prot + evs)

    def _distdfe(self, msg) -> httpx.Response:
        ch = msg.findtext(f".//{{{NS}}}consChNFe/{{{NS}}}chNFe")
        n = self.notas.get(ch) if ch else None
        base = (f'<retDistDFeInt xmlns="{NS}" versao="1.01"><tpAmb>1</tpAmb><verAplic>AN-LAB</verAplic>'
                f"<dhResp>{datetime.now(UTC).isoformat()}</dhResp><ultNSU>0</ultNSU><maxNSU>0</maxNSU>")
        if n is None or n.modelo != "55":  # AN distribui apenas NF-e 55
            return self._soap(base + "<cStat>137</cStat><xMotivo>Nenhum documento localizado</xMotivo></retDistDFeInt>")

        def zipar(xml: bytes) -> str:
            return base64.b64encode(gzip.compress(xml)).decode()
        itens = f'<docZip NSU="000000000000001" schema="procNFe_v4.00.xsd">{zipar(n.xml_proc)}</docZip>'
        for e in n.eventos:
            itens += f'<docZip NSU="000000000000002" schema="procEventoNFe_v1.00.xsd">{zipar(e)}</docZip>'
        return self._soap(base + f"<cStat>138</cStat><xMotivo>Documento localizado</xMotivo>"
                                 f"<loteDistDFeInt>{itens}</loteDistDFeInt></retDistDFeInt>")

    def _sae_lista(self, msg) -> httpx.Response:
        ini = datetime.fromisoformat(msg.findtext(f"{{{NS}}}dataHoraInicial"))
        fim_t = msg.findtext(f"{{{NS}}}dataHoraFinal")
        fim = datetime.fromisoformat(fim_t) if fim_t else datetime.max
        notas = sorted((n for n in self.notas.values() if n.modelo == "65" and chv.analisar(n.chave).uf == "SP"
                        and ini <= n.emissao.replace(tzinfo=None) <= fim), key=lambda n: n.emissao)
        base = f'<retNfceListagemChaves xmlns="{NS}" versao="1.00"><tpAmb>1</tpAmb><verAplic>SP-LAB</verAplic>' \
               f"<dhReq>{datetime.now():%Y-%m-%dT%H:%M:%S}</dhReq>"
        if not notas:
            return self._soap(base + "<cStat>107</cStat><xMotivo>Sem registros</xMotivo></retNfceListagemChaves>")
        pag = notas[: self.limite_sae]
        cstat = "101" if len(notas) > self.limite_sae else "100"
        chaves = "".join(f"<chNFCe>{n.chave}</chNFCe>" for n in pag)
        ult = f"<dhEmisUltNfce>{pag[-1].emissao:%Y-%m-%dT%H:%M:%S}</dhEmisUltNfce>" if cstat == "101" else ""
        return self._soap(base + f"<cStat>{cstat}</cStat><xMotivo>ok</xMotivo>{chaves}{ult}</retNfceListagemChaves>")

    def _sae_download(self, msg) -> httpx.Response:
        ch = msg.findtext(f"{{{NS}}}chNFCe")
        n = self.notas.get(ch)
        base = f'<retNfceDownloadXML xmlns="{NS}" versao="1.00"><tpAmb>1</tpAmb><verAplic>SP-LAB</verAplic>' \
               f"<dhReq>{datetime.now():%Y-%m-%dT%H:%M:%S}</dhReq>"
        if n is None:
            return self._soap(base + "<cStat>205</cStat><xMotivo>Chave não encontrada</xMotivo></retNfceDownloadXML>")
        nfe = etree.tostring(etree.fromstring(n.xml_nfe), encoding="unicode")
        nprot = etree.fromstring(n.prot).findtext(f".//{{{NS}}}nProt")
        evs = ""
        for e in n.eventos:
            el = etree.fromstring(e)
            evs += (f'<procEventoNFe versao="1.00"><dhInc>{n.emissao.isoformat()}</dhInc><nProt>1</nProt>'
                    + etree.tostring(el.find(f"{{{NS}}}evento"), encoding="unicode") + "</procEventoNFe>")
        return self._soap(base + f'<cStat>200</cStat><xMotivo>ok</xMotivo><proc><nfeProc versao="4.00">'
                                 f"<dhInc>{n.emissao.isoformat()}</dhInc><nProt>{nprot}</nProt>{nfe}</nfeProc>{evs}</proc>"
                                 "</retNfceDownloadXML>")

    def _portal(self, req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            cap = '<div class="g-recaptcha" data-sitekey="x"></div>' if self.captcha else ""
            html = ('<html><body><form method="post" action="/NFCESSL/DownloadXMLDFe/Baixar">'
                    '<input type="hidden" name="__RequestVerificationToken" value="tok123"/>'
                    '<input type="text" name="ChaveAcessoDfe" maxlength="44"/>' + cap +
                    '<button type="submit">Baixar</button></form></body></html>')
            return httpx.Response(200, content=html.encode(), headers={"content-type": "text/html"})
        dados = dict(x.split("=", 1) for x in req.content.decode().split("&"))
        if dados.get("__RequestVerificationToken") != "tok123":
            return httpx.Response(400, content=b"token invalido")
        n = self.notas.get(dados.get("ChaveAcessoDfe", ""))
        if n is None:
            return httpx.Response(200, content="<html><p>Documento não encontrado</p></html>".encode(),
                                  headers={"content-type": "text/html"})
        return httpx.Response(200, content=n.xml_proc, headers={"content-type": "application/xml"})
