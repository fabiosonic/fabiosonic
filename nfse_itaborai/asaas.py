"""Integração opcional com o Asaas (boleto + PIX com baixa automática).

Docs: https://docs.asaas.com — autenticação pelo cabeçalho 'access_token'.
Cada título vira uma cobrança 'UNDEFINED' (o cliente escolhe boleto ou PIX na fatura),
com multa/juros configurados. A baixa é feita consultando o status (sem precisar de webhook,
já que o sistema roda no computador do escritório).
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.request

from . import clientes, config

URL_PRODUCAO = "https://api.asaas.com/v3"
URL_SANDBOX = "https://api-sandbox.asaas.com/v3"
PAGOS = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}


class ErroAsaas(Exception):
    pass


def _base(cfg: dict) -> str:
    return cfg["cobranca"].get("asaas_url") or (URL_SANDBOX if cfg["cobranca"]["asaas_sandbox"] else URL_PRODUCAO)


def _req(metodo: str, caminho: str, corpo: dict | None = None, cfg: dict | None = None) -> dict:
    cfg = cfg or config.carregar()
    chave = cfg["cobranca"].get("asaas_api_key")
    if not chave:
        raise ErroAsaas("Chave da API do Asaas não configurada.")
    req = urllib.request.Request(_base(cfg) + caminho, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"access_token": chave, "Content-Type": "application/json",
                                          "User-Agent": "emissor-nfse-itaborai"})
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl.create_default_context()) as r:
            return json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            erros = json.loads(e.read().decode()).get("errors", [])
            msg = "; ".join(x.get("description", "") for x in erros) or f"HTTP {e.code}"
        except ValueError:
            msg = f"HTTP {e.code}"
        raise ErroAsaas(msg) from e


def cliente_id(cpf_cnpj: str, cfg: dict | None = None) -> str:
    doc = clientes._digitos(cpf_cnpj)
    achados = _req("GET", f"/customers?cpfCnpj={doc}", cfg=cfg).get("data", [])
    if achados:
        return achados[0]["id"]
    c = clientes.obter(doc) or {"razao_social": doc, "endereco": {}}
    e = c.get("endereco", {})
    novo = {"name": c["razao_social"], "cpfCnpj": doc, "email": c.get("email") or None,
            "mobilePhone": c.get("telefone") or None, "postalCode": e.get("cep") or None,
            "addressNumber": e.get("numero") or None, "notificationDisabled": True}
    return _req("POST", "/customers", {k: v for k, v in novo.items() if v is not None}, cfg=cfg)["id"]


def criar_cobranca(titulo: dict, cfg: dict | None = None) -> dict:
    cfg = cfg or config.carregar()
    cob = cfg["cobranca"]
    p = _req("POST", "/payments", {
        "customer": cliente_id(titulo["cpf_cnpj"], cfg), "billingType": "UNDEFINED",
        "value": titulo["valor_cent"] / 100, "dueDate": titulo["vencimento"],
        "description": f"{titulo['descricao']} - competência {titulo['competencia']}"[:500],
        "externalReference": f"titulo-{titulo['id']}",
        "fine": {"value": cob["multa_pct"]}, "interest": {"value": cob["juros_mes_pct"]},
    }, cfg=cfg)
    pix = {}
    try:
        pix = _req("GET", f"/payments/{p['id']}/pixQrCode", cfg=cfg)
    except ErroAsaas:
        pass
    linha = {}
    try:
        linha = _req("GET", f"/payments/{p['id']}/identificationField", cfg=cfg)
    except ErroAsaas:
        pass
    return {"asaas_id": p["id"], "cobranca_link": p.get("invoiceUrl", ""), "boleto_url": p.get("bankSlipUrl") or "",
            "pix_copia_cola": pix.get("payload", ""), "linha_digitavel": linha.get("identificationField", "")}


def consultar(asaas_id: str, cfg: dict | None = None) -> dict:
    p = _req("GET", f"/payments/{asaas_id}", cfg=cfg)
    return {"status": p.get("status", ""), "pago": p.get("status") in PAGOS,
            "data_pagamento": p.get("clientPaymentDate") or p.get("paymentDate") or "",
            "valor_pago": p.get("value", 0)}


def url_boleto(asaas_id: str, cfg: dict | None = None) -> str:
    """Link do PDF do boleto (bankSlipUrl) de uma cobrança já criada."""
    return _req("GET", f"/payments/{asaas_id}", cfg=cfg).get("bankSlipUrl") or ""


def baixar_pdf(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "emissor-nfse-itaborai"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ssl.create_default_context()) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        raise ErroAsaas(f"PDF do boleto: HTTP {e.code}") from e
    if not dados.startswith(b"%PDF"):
        raise ErroAsaas("O Asaas não devolveu um PDF (boleto ainda não registrado?).")
    return dados


def cancelar(asaas_id: str, cfg: dict | None = None) -> None:
    _req("DELETE", f"/payments/{asaas_id}", cfg=cfg)
