"""
Provedores de extrato Open Finance com a mesma interface.

- TecnoSpeed (API de Pagamentos, tag statementOpenfinance): fluxo assíncrono por protocolo, limite de 1
  protocolo bem-sucedido a cada 6 h por conta+tipo, dedup nativa (transactionDuplicated).
  Docs: https://docs.pagamentobancario.com.br/#tag/statementOpenfinance
- Pluggy (o agregador que a TecnoSpeed usa por trás, ver docs/rea-openfinance-tecnospeed-arquitetura.md):
  consulta direta de contas e transações do item. Campos mapeados conforme a documentação pública da
  Pluggy; validar no sandbox antes de produção.

Cada provedor expõe `normalizar_*` puro (testável sem rede) e um cliente HTTP fino com urllib.
Segredos sempre por variável de ambiente, nunca em arquivo versionado.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .modelo import Transacao, dec, so_digitos

USER_AGENT = "mo-openfinance/0.1"


class ErroProvedor(Exception):
    def __init__(self, status, mensagem, corpo=None):
        super().__init__(f"{status}: {mensagem}")
        self.status, self.mensagem, self.corpo = status, mensagem, corpo


def _http(metodo, url, headers, corpo=None, timeout=60):
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, headers={"User-Agent": USER_AGENT,
                                                          "Content-Type": "application/json", **headers},
                                 method=metodo)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            bruto = r.read()
            return json.loads(bruto) if bruto else None
    except urllib.error.HTTPError as e:
        try:
            corpo_erro = json.loads(e.read() or b"null")
        except ValueError:
            corpo_erro = None
        msg = (corpo_erro or {}).get("message") if isinstance(corpo_erro, dict) else None
        raise ErroProvedor(e.code, msg or e.reason, corpo_erro) from None


# ----------------------------------------------------------------------------------------------- TecnoSpeed

TECNOSPEED_BASES = {"homologacao": "https://staging.pagamentobancario.com.br/api/v1",
                    "producao": "https://api.pagamentobancario.com.br/api/v1"}


def _participante(p):
    p = p or {}
    doc = (p.get("documentNumber") or {}).get("value")
    return p.get("name") or "", so_digitos(doc)


def normalizar_transacao_tecnospeed(item, conta, tipo_extrato="BANK", protocolo=""):
    """Um item de transaction.credit[]/debit[] (protocolo) ou data.credit[]/debit[] (listagem)."""
    natureza = (item.get("transactionType") or "").lower()
    valor = dec(item["amount"])
    if natureza not in ("credit", "debit"):
        raise ValueError(f"transactionType inesperado: {natureza!r}")
    valor = valor if natureza == "credit" else -valor
    # contraparte: em entrada interessa quem pagou; em saída, quem recebeu
    nome, doc = _participante(item.get("participantPayer") if natureza == "credit" else item.get("participantReceiver"))
    merchant = item.get("creditCardMerchant") or {}
    return Transacao(
        id=str(item["transactionId"]),
        conta=item.get("accountHash") or conta,
        tipo_extrato=tipo_extrato.upper(),
        data=item["date"][:10],
        valor=valor,
        descricao=item.get("description") or "",
        categoria=item.get("category") or "",
        meio=(item.get("paymentMethod") or "").upper(),
        contraparte_nome=nome or item.get("paymentName") or "",
        contraparte_doc=doc,
        referencia=item.get("referenceNumber") or "",
        boleto_principal=dec(item.get("paymentBaseAmount")),
        boleto_juros=dec(item.get("paymentInterestAmount")),
        boleto_multa=dec(item.get("paymentPenaltyAmount")),
        boleto_desconto=dec(item.get("paymentDiscountAmount")),
        cartao_final=item.get("creditCardNumber") or "",
        parcela=item.get("creditCardInstallmentNumber"),
        total_parcelas=item.get("creditCardTotalInstallments"),
        estabelecimento_doc=so_digitos(merchant.get("cpfCnpj")),
        estabelecimento_cnae=merchant.get("cnae") or "",
        origem_protocolo=item.get("statementUniqueId") or protocolo,
        bruto=item,
    )


def normalizar_protocolo_tecnospeed(resposta):
    """GET /statement/openfinance/{uniqueId} → (status, motivo, [Transacao novas]).

    `transactionDuplicated` é ignorado de propósito: são transações já entregues por protocolos anteriores.
    """
    st = resposta.get("statement") or {}
    status = st.get("status")
    if status != "SUCCESS":
        return status, st.get("reason"), []
    tipo = "CREDIT_CARD" if (st.get("type") or "").lower() == "credit_card" else "BANK"
    novas = []
    for natureza in ("credit", "debit"):
        for item in (resposta.get("transaction") or {}).get(natureza) or []:
            novas.append(normalizar_transacao_tecnospeed(item, st.get("accountHash"), tipo, st.get("uniqueId", "")))
    return status, st.get("reason"), novas


class TecnoSpeed:
    nome = "tecnospeed"
    intervalo_protocolo_horas = 6

    def __init__(self, cnpj_sh=None, token_sh=None, ambiente=None):
        self.base = TECNOSPEED_BASES[ambiente or os.environ.get("TECNOSPEED_AMBIENTE", "homologacao")]
        self.cnpj_sh = cnpj_sh or os.environ["TECNOSPEED_CNPJ_SH"]
        self.token_sh = token_sh or os.environ["TECNOSPEED_TOKEN_SH"]

    def _req(self, metodo, caminho, pagador, corpo=None, **query):
        q = {k: v for k, v in query.items() if v is not None}
        url = self.base + caminho + (("?" + urllib.parse.urlencode(q)) if q else "")
        return _http(metodo, url, {"cnpjsh": self.cnpj_sh, "tokensh": self.token_sh, "payercpfcnpj": pagador}, corpo)

    def gerar_protocolo(self, pagador, conta, inicio, fim, tipo="BANK", cartao=None):
        corpo = {"accountHash": conta, "dateStart": inicio, "dateEnd": fim, "statementType": tipo}
        if tipo == "CREDIT_CARD":
            corpo["cardNumber"] = str(cartao).zfill(4)
        return self._req("POST", "/statement/openfinance", pagador, corpo)["uniqueId"]

    def consultar_protocolo(self, pagador, unique_id):
        return normalizar_protocolo_tecnospeed(self._req("GET", f"/statement/openfinance/{unique_id}", pagador))

    def transacoes(self, pagador, conta, inicio, fim, tipo="BANK"):
        """Percorre /statement/transactions/openfinance por cursor (não repete nem pula transações)."""
        cursor = None
        while True:
            try:
                r = self._req("GET", "/statement/transactions/openfinance", pagador, accountHash=conta,
                              dateStart=inicio, dateEnd=fim, statementType=tipo, pageLimit=50, cursor=cursor)
            except ErroProvedor as e:
                if e.status == 404:  # "Nenhuma transação foi encontrada"
                    return
                raise
            for natureza in ("credit", "debit"):
                for item in (r.get("data") or {}).get(natureza) or []:
                    yield normalizar_transacao_tecnospeed(item, conta, tipo)
            cursor = (r.get("meta") or {}).get("nextCursor")
            if not cursor:
                return

    def saldo(self, pagador, conta):
        return self._req("GET", "/balance/openfinance/realtime", pagador, accountHash=conta)


# ----------------------------------------------------------------------------------------------- Pluggy

PLUGGY_BASE = "https://api.pluggy.ai"


def normalizar_transacao_pluggy(item, tipo_extrato="BANK"):
    """Um item de GET /transactions (results[]). Pendentes não chegam aqui (ver Pluggy.transacoes)."""
    valor = abs(dec(item["amount"]))
    if (item.get("type") or "").upper() == "DEBIT":
        valor = -valor
    pd = item.get("paymentData") or {}
    lado = pd.get("payer") if valor > 0 else pd.get("receiver")
    nome, doc = _participante(lado)
    boleto = pd.get("boletoMetadata") or {}
    cc = item.get("creditCardMetadata") or {}
    merchant = item.get("merchant") or {}
    return Transacao(
        id=str(item["id"]),
        conta=item.get("accountId") or "",
        tipo_extrato=tipo_extrato,
        data=(item.get("date") or "")[:10],
        valor=valor,
        descricao=item.get("descriptionRaw") or item.get("description") or "",
        categoria=item.get("category") or "",
        meio=(pd.get("paymentMethod") or "").upper(),
        contraparte_nome=nome,
        contraparte_doc=doc,
        referencia=pd.get("referenceNumber") or "",
        boleto_principal=dec(boleto.get("baseAmount")),
        boleto_juros=dec(boleto.get("interestAmount")),
        boleto_multa=dec(boleto.get("penaltyAmount")),
        boleto_desconto=dec(boleto.get("discountAmount")),
        cartao_final=cc.get("cardNumber") or "",
        parcela=cc.get("installmentNumber"),
        total_parcelas=cc.get("totalInstallments"),
        estabelecimento_doc=so_digitos(merchant.get("cnpj")),
        estabelecimento_cnae=merchant.get("cnae") or "",
        bruto=item,
    )


class Pluggy:
    nome = "pluggy"
    intervalo_protocolo_horas = 0  # sem protocolo: a Pluggy sincroniza o item sozinha

    def __init__(self, client_id=None, client_secret=None, base=PLUGGY_BASE):
        self.base = base
        self.client_id = client_id or os.environ["PLUGGY_CLIENT_ID"]
        self.client_secret = client_secret or os.environ["PLUGGY_CLIENT_SECRET"]
        self._api_key = None

    def _chave(self):
        if not self._api_key:  # a apiKey vale ~2 h; o processo de sincronização é curto
            r = _http("POST", self.base + "/auth", {}, {"clientId": self.client_id, "clientSecret": self.client_secret})
            self._api_key = r["apiKey"]
        return self._api_key

    def _get(self, caminho, **query):
        url = self.base + caminho + "?" + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None})
        return _http("GET", url, {"X-API-KEY": self._chave()})

    def connect_token(self, item_id=None, webhook_url=None):
        """Token de 30 min para abrir o widget Pluggy Connect no portal do cliente."""
        corpo = {k: v for k, v in {"itemId": item_id, "webhookUrl": webhook_url}.items() if v}
        return _http("POST", self.base + "/connect_token", {"X-API-KEY": self._chave()}, corpo)["accessToken"]

    def contas(self, item_id):
        return self._get("/accounts", itemId=item_id)["results"]

    def transacoes(self, pagador, conta, inicio, fim, tipo="BANK"):
        pagina = 1
        while True:
            r = self._get("/transactions", accountId=conta, **{"from": inicio, "to": fim}, pageSize=500, page=pagina)
            for item in r.get("results") or []:
                if (item.get("status") or "POSTED").upper() == "PENDING":
                    continue  # pendente ainda pode mudar de valor/data: só entra quando lançada
                yield normalizar_transacao_pluggy(item, tipo)
            if pagina >= (r.get("totalPages") or 1):
                return
            pagina += 1
