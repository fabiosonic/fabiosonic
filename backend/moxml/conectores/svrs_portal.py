"""Conector oficial: Portal DF-e SVRS — "Download XML DF-e" com certificado digital.

Evidência (ver REA_FORNECEDORES.md e FONTES_FISCAIS.md):
- Notícia SVRS de 12/02/2019: botão "Download Arquivo da NFC-e" que "permite baixar o arquivo
  XML ... para o usuário apresentando certificado digital desde que esteja relacionado com a NFC-e".
- Em 19/11/2026, ``/NFESSL/DownloadXMLDFe`` e ``/NFCESSL/DownloadXMLDFe`` responderam, sem
  certificado: "Esta consulta exige Certificado Digital emitido por AC credenciada junto ao ICP-Brasil".

Status: NÃO COMPROVADO até teste com A1 autorizado. A estrutura do formulário só é visível com
certificado; por isso o conector lê o formulário em tempo de execução (sem campos fixos inventados)
e PARA se houver CAPTCHA ou qualquer desafio humano — não há tentativa de contorná-lo.
A cada documento é feita no máximo 1 requisição GET + 1 POST (+1 GET de link de download).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin

import httpx

from ..fiscal import chave as chv
from ..sefaz import catalogo
from .base import (
    Capacidade,
    Conector,
    ContextoCaptura,
    Disponibilidade,
    Limites,
    StatusFonte,
    XmlRecuperado,
)

RE_CAPTCHA = re.compile(r"g-recaptcha|h-captcha|hcaptcha|recaptcha|turnstile|data-sitekey|captcha", re.I)
RE_CAMPO_CHAVE = re.compile(r"chave|chnfe|chdfe|chaveacesso|ch_?acesso", re.I)
RE_CAMPO_SERIE = re.compile(r"serie", re.I)
RE_CAMPO_NUMERO = re.compile(r"numero|nnf|num_?doc", re.I)
RE_CAMPO_CNPJ = re.compile(r"cnpj|cpf_?cnpj|emitente", re.I)
RE_CAMPO_MODELO = re.compile(r"modelo|\bmod\b", re.I)


class CaptchaExigido(RuntimeError):
    """O portal exige interação humana: captura automática IMPOSSÍVEL PELO MÉTODO."""


class PortalRecusou(RuntimeError):
    pass


@dataclass
class Formulario:
    action: str = ""
    method: str = "get"
    campos: list[dict] = field(default_factory=list)

    def campo_chave(self) -> str | None:
        for c in self.campos:
            if c.get("type", "text") in ("text", "search", "") and RE_CAMPO_CHAVE.search(c.get("name", "") + c.get("id", "")):
                return c.get("name")
        texto = [c for c in self.campos if c.get("type", "text") in ("text", "search", "") and c.get("name")]
        if len(texto) == 1 and texto[0].get("maxlength") in (None, "44", "54"):
            return texto[0]["name"]
        return None

    def _campo(self, rx: re.Pattern) -> str | None:
        for c in self.campos:
            if c.get("name") and c.get("type", "text") not in ("hidden", "submit", "button") and rx.search(
                    c.get("name", "") + " " + c.get("id", "")):
                return c["name"]
        return None

    def campos_serie_numero(self) -> dict[str, str] | None:
        """Formulário de recuperação por série/número (manual NFC-e SEFAZ-RJ, pergunta 1.43)."""
        serie, numero = self._campo(RE_CAMPO_SERIE), self._campo(RE_CAMPO_NUMERO)
        if not (serie and numero):
            return None
        r = {"serie": serie, "numero": numero}
        for k, rx in (("cnpj", RE_CAMPO_CNPJ), ("modelo", RE_CAMPO_MODELO)):
            n = self._campo(rx)
            if n:
                r[k] = n
        return r


class _LeitorForms(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.forms: list[Formulario] = []
        self.links: list[str] = []
        self.texto: list[str] = []
        self._atual: Formulario | None = None

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        a = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._atual = Formulario(action=a.get("action", ""), method=a.get("method", "get").lower())
            self.forms.append(self._atual)
        elif tag in ("input", "select", "textarea", "button") and self._atual is not None:
            self._atual.campos.append({"tag": tag, "name": a.get("name", ""), "id": a.get("id", ""),
                                       "type": a.get("type", "text").lower(), "value": a.get("value", ""),
                                       "maxlength": a.get("maxlength")})
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag == "form":
            self._atual = None

    def handle_data(self, data):  # noqa: ANN001
        if data.strip():
            self.texto.append(data.strip())


def analisar_html(html: str) -> _LeitorForms:
    p = _LeitorForms()
    p.feed(html)
    return p


def _parece_xml(conteudo: bytes, content_type: str) -> bool:
    inicio = conteudo.lstrip()[:200].lower()
    return "xml" in content_type.lower() or inicio.startswith(b"<?xml") or inicio.startswith(b"<nfeproc")


class SvrsPortalConector(Conector):
    nome = "svrs_portal_download"
    descricao = "Portal DF-e SVRS — Download XML DF-e por chave, com o A1 do emitente (mTLS)."
    oficial = True
    capacidades = frozenset({Capacidade.RECUPERAR_XML})

    def __init__(self, catalogo_extra: str | None = None):
        self.extra = catalogo_extra

    def suporta(self, uf: str, modelo: str) -> Disponibilidade:
        try:
            catalogo.portal("SVRS_DownloadXMLDFe", uf, modelo, 1, self.extra)
        except catalogo.ServicoIndisponivel as e:
            return Disponibilidade(StatusFonte.INDISPONIVEL, str(e))
        return Disponibilidade(StatusFonte.NAO_COMPROVADO,
                               "Página oficial exige certificado ICP-Brasil; fluxo do formulário só observável com A1. "
                               "Interrompe em caso de CAPTCHA.",
                               "Notícia SVRS 12/02/2019; resposta observada em 19/11/2026")

    def consultar_limites(self) -> Limites:
        return Limites(requisicoes_por_minuto=12, observacoes="Limite não publicado; valor conservador local.")

    def _http(self, ctx: ContextoCaptura) -> httpx.Client:
        if not ctx.cliente_http:
            raise RuntimeError("cliente HTTPS com certificado não configurado")
        return ctx.cliente_http()  # type: ignore[return-value]

    def inspecionar(self, ctx: ContextoCaptura) -> dict:
        """Diagnóstico para o relatório REA: estrutura do formulário (nomes/tipos, sem valores)."""
        url = catalogo.portal("SVRS_DownloadXMLDFe", ctx.uf, ctx.modelo, 1, self.extra)
        r = self._http(ctx).get(url, follow_redirects=True)
        p = analisar_html(r.text)
        return {
            "url": url, "url_final": str(r.url), "http": r.status_code,
            "captcha": bool(RE_CAPTCHA.search(r.text)),
            "forms": [{"action": f.action, "method": f.method,
                       "campos": [{k: v for k, v in c.items() if k != "value"} for c in f.campos],
                       "campo_chave_detectado": f.campo_chave(),
                       "campos_serie_numero_detectados": f.campos_serie_numero()} for f in p.forms],
            "mensagens": [t for t in p.texto if len(t) < 200][:40],
        }

    def recuperar_xml(self, ctx: ContextoCaptura, chave: str, ref_fonte: str | None = None) -> XmlRecuperado:
        ck = chv.analisar(chave)
        return self._baixar(ctx, ck.uf, ck.modelo, lambda f: {f.campo_chave(): ck.chave} if f.campo_chave() else None)

    def recuperar_por_numero(self, ctx: ContextoCaptura, serie: int, numero: int) -> XmlRecuperado:
        """Recuperação por série/número (sem conhecer a chave), se o formulário oferecer esses campos."""
        def mapa(f: Formulario) -> dict | None:
            c = f.campos_serie_numero()
            if not c:
                return None
            d = {c["serie"]: str(serie), c["numero"]: str(numero)}
            if "cnpj" in c:
                d[c["cnpj"]] = ctx.cnpj
            if "modelo" in c:
                d[c["modelo"]] = ctx.modelo
            return d
        return self._baixar(ctx, ctx.uf, ctx.modelo, mapa)

    def _baixar(self, ctx: ContextoCaptura, uf: str, modelo: str, mapear) -> XmlRecuperado:  # noqa: ANN001
        if ctx.ambiente != 1:
            raise PortalRecusou("portal de download disponível apenas para produção")
        url = catalogo.portal("SVRS_DownloadXMLDFe", uf, modelo, 1, self.extra)
        cli = self._http(ctx)
        r = cli.get(url, follow_redirects=True)
        if "/Erro/" in str(r.url) or r.status_code >= 400:
            raise PortalRecusou(f"portal recusou o acesso ({r.status_code} {r.url}); certificado não aceito?")
        if RE_CAPTCHA.search(r.text):
            raise CaptchaExigido("portal exige CAPTCHA — captura automática interrompida (não contornamos desafios)")
        p = analisar_html(r.text)
        alvo, valores = next(((f, mapear(f)) for f in p.forms if mapear(f)), (None, None))
        if alvo is None or not valores:
            raise PortalRecusou("formulário com os campos necessários não identificado; rode `moxml diagnostico-svrs`")
        # Somente campos ocultos (ex.: token antifalsificação) + os campos de busca. Nenhum valor é inventado.
        dados = {c["name"]: c["value"] for c in alvo.campos if c["name"] and c["type"] == "hidden"}
        dados.update(valores)
        destino = urljoin(str(r.url), alvo.action or str(r.url))
        resp = cli.post(destino, data=dados, follow_redirects=True) if alvo.method == "post" \
            else cli.get(destino, params=dados, follow_redirects=True)
        if RE_CAPTCHA.search(resp.text[:20000] if not _parece_xml(resp.content, resp.headers.get("content-type", "")) else ""):
            raise CaptchaExigido("portal exige CAPTCHA no envio — interrompido")
        if _parece_xml(resp.content, resp.headers.get("content-type", "")):
            return XmlRecuperado(xml=resp.content, origem=self.nome, bruto=None)
        # Página intermediária com link de download do arquivo
        p2 = analisar_html(resp.text)
        link = next((h for h in p2.links if re.search(r"download|\.xml", h, re.I) and "DownloadXMLDFe" not in h), None)
        if link:
            arq = cli.get(urljoin(str(resp.url), link), follow_redirects=True)
            if _parece_xml(arq.content, arq.headers.get("content-type", "")):
                return XmlRecuperado(xml=arq.content, origem=self.nome)
        msg = " | ".join(t for t in p2.texto if re.search(r"n[ãa]o|erro|inv[áa]lid|permiss|encontrad", t, re.I))[:400]
        raise PortalRecusou(msg or "portal não retornou XML")
