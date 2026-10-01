"""Comunicação com o webservice da Prefeitura de Itaboraí (POST multipart/form-data)."""

from __future__ import annotations

import html
import re
import secrets
import ssl
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

URL_WEBSERVICE = "https://prefeituradeitaborai.online/wsnfse/"
TIMEOUT = 60


@dataclass
class NotaEmitida:
    numero_nfse: str = ""
    data_emissao: str = ""
    codigo_verificacao: str = ""
    link: str = ""
    numero_rps: str = ""
    xml: str = ""


@dataclass
class Resposta:
    sucesso: bool
    xml_enviado: str
    xml_retorno: str
    status_http: int = 0
    erros: list[str] = field(default_factory=list)
    notas: list[NotaEmitida] = field(default_factory=list)
    situacao: str = ""
    alertas: list[str] = field(default_factory=list)
    pasta: str = ""


def montar_multipart(xml: str, nome_arquivo: str) -> tuple[bytes, str]:
    """Mesmo envelope do ACBr (TACBrNFSeXWebserviceMulti2)."""
    fronteira = "----=_Part_3_" + secrets.token_hex(4).upper()
    corpo = (f"--{fronteira}\r\n"
             f"Content-Type: text/xml; charset=Cp1252; name={nome_arquivo}\r\n"
             "Content-Transfer-Encoding: binary\r\n"
             f'Content-Disposition: form-data; name="{nome_arquivo}"; filename="{nome_arquivo}"\r\n'
             "\r\n"
             f"{xml}\r\n"
             f"--{fronteira}--\r\n")
    return corpo.encode("cp1252", "replace"), f'multipart/form-data; boundary="{fronteira}"'


def postar(xml: str, nome_arquivo: str, url: str = URL_WEBSERVICE, timeout: int = TIMEOUT) -> tuple[int, str]:
    corpo, content_type = montar_multipart(xml, nome_arquivo)
    req = urllib.request.Request(url, data=corpo, method="POST",
                                 headers={"Content-Type": content_type})
    contexto = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=contexto) as r:
            bruto, status, charset = r.read(), r.status, r.headers.get_content_charset()
    except urllib.error.HTTPError as e:
        bruto, status, charset = e.read(), e.code, e.headers.get_content_charset()
    for cod in filter(None, (charset, "utf-8", "cp1252")):
        try:
            return status, bruto.decode(cod)
        except (UnicodeDecodeError, LookupError):
            continue
    return status, bruto.decode("latin-1")


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filho(no: ET.Element, *nomes: str) -> str:
    alvo = {n.lower() for n in nomes}
    for f in no.iter():
        if _local(f.tag).lower() in alvo and (f.text or "").strip():
            return f.text.strip()
    return ""


def _preparar(xml_retorno: str) -> ET.Element | None:
    t = xml_retorno.strip()
    if "</" not in t and not t.endswith("/>"):
        return None  # resposta em texto puro = mensagem de erro
    t = re.sub(r"^<\?xml[^>]*\?>", "", t).strip()
    try:
        raiz = ET.fromstring(t)
    except ET.ParseError:
        try:
            raiz = ET.fromstring(re.sub(r"^<\?xml[^>]*\?>", "", html.unescape(t)).strip())
        except ET.ParseError:
            return None
    # XML devolvido "escapado" dentro de um elemento-envelope
    if len(raiz) == 0 and "<" in (raiz.text or ""):
        interno = re.sub(r"^<\?xml[^>]*\?>", "", raiz.text.strip()).strip()
        try:
            return ET.fromstring(interno)
        except ET.ParseError:
            return raiz
    return raiz


def interpretar_emissao(xml_enviado: str, status: int, xml_retorno: str) -> Resposta:
    resp = Resposta(sucesso=False, xml_enviado=xml_enviado, xml_retorno=xml_retorno, status_http=status)
    raiz = _preparar(xml_retorno)
    if raiz is None:
        resp.erros.append(xml_retorno.strip() or f"Resposta vazia do webservice (HTTP {status}).")
        return resp

    for no in raiz.iter():
        if _local(no.tag).lower() in ("mensagem", "listadeerros") and len(no) == 0 and (no.text or "").strip():
            resp.erros.append(no.text.strip())
        elif _local(no.tag).lower() in ("mensagem", "listadeerros") and len(no) > 0:
            texto = " | ".join(t.strip() for t in no.itertext() if t.strip())
            if texto:
                resp.erros.append(texto)

    for no in raiz.iter():
        if _local(no.tag) == "Nfse":
            nota = NotaEmitida(
                numero_nfse=_filho(no, "NumeroNFSe"),
                data_emissao=_filho(no, "DataEmissaoNFSe"),
                codigo_verificacao=_filho(no, "CodigoVerificacao"),
                link=_filho(no, "LinkNFSe").replace("&amp;", "&"),
                xml=ET.tostring(no, encoding="unicode"),
            )
            ident = next((f for f in no.iter() if _local(f.tag) == "IdentificacaoRps"), None)
            if ident is not None:
                nota.numero_rps = _filho(ident, "Numero")
            resp.notas.append(nota)

    if not resp.erros:
        resp.situacao = _filho(raiz, "EstadoDoRPS")
    resp.sucesso = not resp.erros and bool(resp.notas)
    if not resp.erros and not resp.notas:
        resp.erros.append("O webservice não devolveu erro nem NFS-e. Consulte o RPS no portal antes de reenviar.")
    return resp


def interpretar_cancelamento(xml_enviado: str, status: int, xml_retorno: str) -> Resposta:
    resp = Resposta(sucesso=False, xml_enviado=xml_enviado, xml_retorno=xml_retorno, status_http=status)
    raiz = _preparar(xml_retorno)
    if raiz is None:
        resp.erros.append(xml_retorno.strip() or f"Resposta vazia do webservice (HTTP {status}).")
        return resp
    for no in raiz.iter():
        if _local(no.tag).lower() in ("mensagem", "listadeerros"):
            texto = " | ".join(t.strip() for t in no.itertext() if t.strip())
            if texto:
                resp.erros.append(texto)
    resp.situacao = _filho(raiz, "situacao_descricao_nfse")
    resp.notas.append(NotaEmitida(numero_nfse=_filho(raiz, "numero_nfse"),
                                  link=_filho(raiz, "link_nfse").replace("&amp;", "&"),
                                  codigo_verificacao=_filho(raiz, "cod_verificador_autenticidade")))
    resp.sucesso = not resp.erros
    return resp
