"""Boletos (com QR Code PIX) direto pela API de Cobrança v3 do Banco Inter — sem intermediário.

Credenciais: no Internet Banking PJ do Inter › Soluções para sua empresa › Nova Integração (escopos
"boleto-cobranca.read" e "boleto-cobranca.write") gera-se client_id, client_secret e o par certificado (.crt)
+ chave (.key). A comunicação é HTTPS com autenticação mútua usando esse certificado.

Fluxo (https://developers.inter.co/references/cobranca-bolepix):
- token OAuth2: POST /oauth/v2/token (client_credentials), válido por 1 hora;
- emitir: POST /cobranca/v3/cobrancas → {"codigoSolicitacao"} (o banco processa e registra o boleto);
- consultar: GET /cobranca/v3/cobrancas/{codigoSolicitacao} → cobranca.situacao, boleto.linhaDigitavel, pix.pixCopiaECola;
- PDF: GET /cobranca/v3/cobrancas/{codigoSolicitacao}/pdf → {"pdf": base64};
- cancelar: POST /cobranca/v3/cobrancas/{codigoSolicitacao}/cancelar {"motivoCancelamento"}.

Extrato (API Banking v2, escopo "extrato.read" — marcar "Consultar extrato e saldo" na integração):
- GET /banking/v2/extrato/completo?dataInicio&dataFim&pagina&tamanhoPagina → transacoes[] com idTransacao,
  dataTransacao, tipoOperacao (C crédito / D débito), valor, titulo e descricao. O token do extrato é pedido
  separado, para que uma integração só de boletos continue funcionando.
"""

from __future__ import annotations

import base64
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime

from . import clientes, config, emissor

URL_PRODUCAO = "https://cdpj.partners.bancointer.com.br"
URL_SANDBOX = "https://cdpj-sandbox.partners.uatinter.co"
ESCOPO = "boleto-cobranca.read boleto-cobranca.write"
ESCOPO_EXTRATO = "extrato.read"
DIAS_POR_CONSULTA = 30
PAGOS = {"RECEBIDO", "MARCADO_RECEBIDO"}
BAIXADOS = {"CANCELADO", "EXPIRADO"}

# Municípios da carteira (código IBGE → nome). O Inter exige o nome da cidade do pagador; para outros
# municípios, preencha o campo Cidade no cadastro do cliente.
MUNICIPIOS = {
    "3300209": "Araruama", "3301702": "Duque de Caxias", "3301900": "Itaboraí", "3302700": "Maricá",
    "3303302": "Niterói", "3303906": "Petrópolis", "3304557": "Rio de Janeiro", "3304904": "São Gonçalo",
    "3305505": "Saquarema", "3305752": "Tanguá", "3538006": "Pindamonhangaba", "4314902": "Porto Alegre",
}

_TOKEN: dict = {}


def _hoje() -> date:
    return datetime.now(emissor.FUSO).date()


class ErroInter(RuntimeError):
    pass


# ---------------------------------------------------------------- configuração e conexão

def _cfg(cfg: dict | None) -> dict:
    return (cfg or config.carregar())["cobranca"]


def configurado(cfg: dict | None = None) -> bool:
    c = _cfg(cfg)
    return bool(c.get("inter_client_id") and c.get("inter_client_secret") and c.get("inter_certificado")
                and c.get("inter_chave"))


def _base(c: dict) -> str:
    return c.get("inter_url") or (URL_SANDBOX if c.get("inter_sandbox") else URL_PRODUCAO)


def _arquivo(caminho: str, rotulo: str) -> str:
    try:
        return str(emissor.arquivo_da_empresa(caminho, f"{rotulo} do Inter"))
    except emissor.ErroConfiguracao as ex:
        raise ErroInter(str(ex)) from ex


def _contexto(c: dict) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if c.get("inter_ca"):  # só para testes (servidor local com certificado próprio)
        ctx.load_verify_locations(c["inter_ca"])
    try:
        ctx.load_cert_chain(_arquivo(c.get("inter_certificado"), "certificado (.crt)"),
                            _arquivo(c.get("inter_chave"), "arquivo de chave (.key)"))
    except ssl.SSLError as ex:
        raise ErroInter(f"Certificado/chave do Inter inválidos: {ex}") from ex
    return ctx


def _http(metodo: str, url: str, c: dict, dados: bytes | None, cab: dict) -> dict:
    req = urllib.request.Request(url, data=dados, method=metodo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=60, context=_contexto(c)) as r:
            texto = r.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as e:
        corpo = e.read().decode("utf-8", "replace")
        try:
            js = json.loads(corpo)
            msg = js.get("detail") or js.get("title") or js.get("message") or corpo
            violacoes = [f"{v.get('propriedade', '')}: {v.get('razao', '')}" for v in js.get("violacoes", []) or []]
            if violacoes:
                msg += " (" + "; ".join(violacoes) + ")"
        except ValueError:
            msg = corpo[:300] or f"HTTP {e.code}"
        raise ErroInter(f"Inter: {msg}") from e
    try:
        return json.loads(texto)
    except ValueError:
        return {}


def token(cfg: dict | None = None, escopo: str = ESCOPO) -> str:
    c = _cfg(cfg)
    if not configurado(cfg):
        raise ErroInter("Banco Inter não configurado: informe client_id, client_secret, certificado (.crt) e "
                        "chave (.key) em Configurações › Cobrança.")
    chave = (str(emissor.raiz()), _base(c), c["inter_client_id"], escopo)  # nunca reaproveitado entre empresas
    t = _TOKEN.get(chave)
    if t and t[1] > time.time() + 60:
        return t[0]
    corpo = urllib.parse.urlencode({"client_id": c["inter_client_id"], "client_secret": c["inter_client_secret"],
                                    "scope": escopo, "grant_type": "client_credentials"}).encode()
    js = _http("POST", _base(c) + "/oauth/v2/token", c, corpo, {"Content-Type": "application/x-www-form-urlencoded"})
    if not js.get("access_token"):
        raise ErroInter("Inter não devolveu o token de acesso.")
    _TOKEN[chave] = (js["access_token"], time.time() + int(js.get("expires_in", 3600)))
    return js["access_token"]


def _api(metodo: str, caminho: str, corpo: dict | None = None, cfg: dict | None = None) -> dict:
    c = _cfg(cfg)
    cab = {"Authorization": f"Bearer {token(cfg)}", "Content-Type": "application/json"}
    if c.get("inter_conta"):
        cab["x-conta-corrente"] = clientes._digitos(c["inter_conta"])
    dados = json.dumps(corpo).encode() if corpo is not None else None
    return _http(metodo, _base(c) + "/cobranca/v3" + caminho, c, dados, cab)


# ---------------------------------------------------------------- pagador

def cidade(cli: dict) -> str:
    e = cli.get("endereco", {})
    if e.get("cidade"):
        return e["cidade"]
    cod = clientes._digitos(e.get("codigo_municipio"))
    if cod in MUNICIPIOS:
        return MUNICIPIOS[cod]
    return ""


def pagador(cpf_cnpj: str) -> dict:
    cli = clientes.obter(cpf_cnpj) or {}
    doc = clientes._digitos(cpf_cnpj)
    e = cli.get("endereco", {})
    nome_cidade = cidade(cli)
    faltando = [r for r, v in (("endereço", e.get("logradouro")), ("CEP", clientes._digitos(e.get("cep"))),
                               ("UF", e.get("uf")), ("cidade", nome_cidade)) if not v]
    if not cli or faltando:
        raise ErroInter(f"Cadastro do cliente {cli.get('razao_social', doc)} incompleto para boleto: "
                        + ", ".join(faltando or ["cliente não cadastrado"]) + ".")
    p = {"cpfCnpj": doc, "tipoPessoa": "FISICA" if len(doc) == 11 else "JURIDICA",
         "nome": cli["razao_social"][:100],
         "endereco": " ".join(x for x in (e.get("tipo_logradouro"), e.get("logradouro")) if x)[:90],
         "numero": str(e.get("numero") or "S/N")[:10], "complemento": (e.get("complemento") or "")[:30],
         "bairro": (e.get("bairro") or "")[:60], "cidade": nome_cidade[:60], "uf": e["uf"].upper(),
         "cep": clientes._digitos(e["cep"])}
    email = (cli.get("email") or "").split(";")[0].split(",")[0].strip()
    if "@" in email:
        p["email"] = email[:50]
    fone = clientes._digitos(cli.get("telefone"))
    if fone.startswith("55") and len(fone) > 11:
        fone = fone[2:]
    if len(fone) in (10, 11):
        p["ddd"], p["telefone"] = fone[:2], fone[2:]
    return {k: v for k, v in p.items() if v != ""}


# ---------------------------------------------------------------- operações

def criar_cobranca(titulo: dict, cfg: dict | None = None, espera: float = 8.0) -> dict:
    """Registra o boleto (com PIX) do título no Inter e devolve os campos para gravar no título."""
    cfg = cfg or config.carregar()
    c = cfg["cobranca"]
    valor = titulo["valor_cent"] / 100
    if valor < 2.5:
        raise ErroInter("O Inter só emite boleto a partir de R$ 2,50.")
    venc = max(date.fromisoformat(titulo["vencimento"]), _hoje())
    corpo = {
        "seuNumero": f"T{titulo['id']}"[:15], "valorNominal": round(valor, 2), "dataVencimento": venc.isoformat(),
        "numDiasAgenda": max(0, min(60, int(c.get("inter_dias_agenda", 60)))),
        "pagador": pagador(titulo["cpf_cnpj"]),
        "mensagem": {"linha1": f"{titulo['descricao']}"[:78],
                     "linha2": f"Competência {titulo['competencia'][5:]}/{titulo['competencia'][:4]}"[:78]},
    }
    if float(c.get("multa_pct") or 0) > 0:
        corpo["multa"] = {"codigo": "PERCENTUAL", "taxa": float(c["multa_pct"])}
    if float(c.get("juros_mes_pct") or 0) > 0:
        corpo["mora"] = {"codigo": "TAXAMENSAL", "taxa": float(c["juros_mes_pct"])}
    cod = _api("POST", "/cobrancas", corpo, cfg).get("codigoSolicitacao")
    if not cod:
        raise ErroInter("Inter não devolveu o código da cobrança.")
    out = {"banco_id": cod, "linha_digitavel": "", "pix_copia_cola": "", "nosso_numero": ""}
    limite = time.time() + espera
    while True:  # o registro é assíncrono: aguarda alguns segundos pela linha digitável e pelo PIX
        d = consultar(cod, cfg)
        out.update({k: d[k] for k in ("linha_digitavel", "pix_copia_cola", "nosso_numero") if d[k]})
        if out["linha_digitavel"] or d["situacao"] == "FALHA_EMISSAO" or time.time() >= limite:
            break
        time.sleep(1)
    return out


def consultar(codigo: str, cfg: dict | None = None) -> dict:
    js = _api("GET", f"/cobrancas/{codigo}", cfg=cfg)
    cob, bol, pix = js.get("cobranca", {}), js.get("boleto", {}) or {}, js.get("pix", {}) or {}
    situacao = cob.get("situacao", "")
    return {"situacao": situacao, "pago": situacao in PAGOS, "baixado": situacao in BAIXADOS,
            "data_pagamento": cob.get("dataSituacao", "") if situacao in PAGOS else "",
            "valor_pago": cob.get("valorTotalRecebido") or cob.get("valorNominal") or 0,
            "linha_digitavel": bol.get("linhaDigitavel", ""), "nosso_numero": bol.get("nossoNumero", ""),
            "pix_copia_cola": pix.get("pixCopiaECola", "")}


def pdf(codigo: str, cfg: dict | None = None) -> bytes:
    js = _api("GET", f"/cobrancas/{codigo}/pdf", cfg=cfg)
    dados = base64.b64decode(js.get("pdf", "") or b"")
    if not dados.startswith(b"%PDF"):
        raise ErroInter("O Inter ainda não liberou o PDF deste boleto (registro em processamento).")
    return dados


def cancelar(codigo: str, motivo: str = "Cancelado pelo emissor", cfg: dict | None = None) -> None:
    _api("POST", f"/cobrancas/{codigo}/cancelar", {"motivoCancelamento": (motivo or "Cancelado")[:50]}, cfg)


def testar(cfg: dict | None = None) -> dict:
    """Obtém um token e lista as cobranças de hoje: confirma certificado, credenciais e escopos."""
    token(cfg)
    hoje = _hoje().isoformat()
    _api("GET", f"/cobrancas?dataInicial={hoje}&dataFinal={hoje}&itensPorPagina=1", cfg=cfg)
    c = _cfg(cfg)
    return {"ok": True, "mensagem": f"Conexão com o Banco Inter OK ({'sandbox' if c.get('inter_sandbox') else 'produção'})."}


# ---------------------------------------------------------------- extrato (conciliação automática)

def _sem_escopo(ex: Exception) -> bool:
    t = str(ex).lower()
    return any(x in t for x in ("scope", "escopo", "forbidden", "403", "unauthorized", "401"))


def extrato(inicio: date, fim: date, cfg: dict | None = None) -> list[dict]:
    """Lançamentos da conta no período, no mesmo formato do OFX (data, valor_cent, descricao, fitid)."""
    from datetime import timedelta
    c = _cfg(cfg)
    try:
        tk = token(cfg, ESCOPO_EXTRATO)
    except ErroInter as ex:
        if _sem_escopo(ex):
            raise ErroInter("A integração do Inter não tem permissão de extrato: no Internet Banking PJ, edite a "
                            "integração e marque \"Consultar extrato e saldo\" (escopo extrato.read).") from ex
        raise
    cab = {"Authorization": f"Bearer {tk}"}
    if c.get("inter_conta"):
        cab["x-conta-corrente"] = clientes._digitos(c["inter_conta"])
    movs, ini = [], inicio
    while ini <= fim:
        ate = min(fim, ini + timedelta(days=DIAS_POR_CONSULTA - 1))
        pagina, total = 0, 1
        while pagina < total:
            q = urllib.parse.urlencode({"dataInicio": ini.isoformat(), "dataFim": ate.isoformat(),
                                        "pagina": pagina, "tamanhoPagina": 50})
            js = _http("GET", f"{_base(c)}/banking/v2/extrato/completo?{q}", c, None, cab)
            for t in js.get("transacoes") or []:
                valor = round(float(str(t.get("valor") or 0).replace(",", ".")) * 100)
                if not valor:
                    continue
                sinal = -1 if str(t.get("tipoOperacao", "")).upper().startswith("D") else 1
                data = str(t.get("dataTransacao") or t.get("dataEntrada") or t.get("dataInclusao") or "")[:10]
                desc = " ".join(x for x in (str(t.get("titulo") or "").strip(), str(t.get("descricao") or "").strip()) if x)
                ident = t.get("idTransacao") or f"{data}-{sinal * valor}-{desc}"[:100]
                movs.append({"data": data, "valor_cent": sinal * abs(valor), "descricao": desc[:250],
                             "fitid": f"inter:{ident}"})
            total = int(js.get("totalPaginas") or 1)
            pagina += 1
        ini = ate + timedelta(days=1)
    return movs

