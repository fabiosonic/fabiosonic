# Estudo técnico: API de Extrato Open Finance da TecnoSpeed (PlugBank)

> Levantamento feito em 22/10/2026 com base em três fontes oficiais:
> - página comercial: https://tecnospeed.com.br/plugbank/api-open-finance/
> - central de ajuda, categoria "Extrato OpenFinance" (10 artigos, o mais recente atualizado em 15/10/2026)
> - especificação OpenAPI da API de Pagamentos: https://docs.pagamentobancario.com.br/api.json (tag `statementOpenfinance`)
>
> Onde a página comercial diverge da documentação técnica, vale a documentação técnica.

---

## 1. O que é, em uma frase

É um módulo da **API de Pagamentos da TecnoSpeed** que entrega, em JSON padronizado, as **transações de conta corrente e de cartão de crédito** dos clientes do ERP. A TecnoSpeed coleta esses dados como participante já credenciada no Open Finance Brasil. A software house (SH) não precisa se credenciar no Banco Central, contratar VAN nem pedir carta à gerência do banco.

Pontos que importam para a decisão:

| Aspecto | Situação |
|---|---|
| Modelo | REST/HTTPS, assíncrono (protocolo → consulta) e webhooks |
| Escopo | **Leitura**: extrato BANK, extrato CREDIT_CARD, saldo e lista de cartões. Não inicia pagamentos nem Pix. |
| Cobertura | 136 instituições: 128 para PF e **68 para PJ** (artigo de 15/10/2026). A página comercial ainda fala em 47 e em "+35"; a lista de bancos atualizada fica na central de ajuda. |
| Fora do escopo | DDA, que é produto separado. Fintechs fora do Open Finance, como a Asaas. |
| Volume | Até 100 mil movimentações por consulta, desde que estejam disponíveis no Open Finance |
| Contrato | Contrato comercial próprio, separado da API de Pagamentos. O preço não é público. |
| Ambientes | Homologação `https://staging.pagamentobancario.com.br/api/v1/` e produção `https://api.pagamentobancario.com.br/api/v1/` |
| Webhooks | **Só em produção** |

---

## 2. Arquitetura e entidades

```
Software House (cnpjsh + tokensh)
 └── Pagador / payer (CPF/CNPJ do cliente do escritório)   ← statementActived: true
      └── Conta / account (accountHash)                   ← statementActived: true
           ├── Conector Open Finance (openfinanceId)       ← criado pelo openfinanceLink
           ├── Protocolos de extrato (uniqueId)            ← BANK ou CREDIT_CARD
           │     └── Transações (transactionId)           ← credit[] / debit[]
           ├── Cartões (cardNumber = 4 últimos dígitos)
           └── Saldo em tempo real (cache de 6 h)
```

Na nossa operação, os termos correspondem a:
- **SH**: o escritório ou o sistema, com credencial única.
- **Pagador**: cada empresa cliente, identificada pelo CNPJ.
- **Conta**: cada conta bancária ou cartão da empresa cliente.

### Autenticação (headers em toda chamada)

| Header | Conteúdo |
|---|---|
| `cnpjsh` | CNPJ da software house contratante |
| `tokensh` | Token obtido em https://conta.tecnospeed.com.br ("Ver meu token") |
| `payercpfcnpj` | CPF/CNPJ do pagador (em todas as rotas, exceto a de criação do payer) |
| `User-Agent` | Obrigatório |
| `Content-Type` | `application/json` |

O OAuth 2.0, o FAPI e o mTLS ficam entre a TecnoSpeed e os bancos. Do nosso lado, a autenticação é feita só por headers estáticos. Por isso o `tokensh` precisa ser tratado como segredo: cofre ou variável de ambiente, nunca no repositório.

---

## 3. Fluxo ponta a ponta

```
1. POST /payer            {"statementActived": true, ...}      (ou PUT /payer para ativar)
2. POST /account          [{"bankCode": "...", "statementActived": true, ...}]
      → resposta traz openfinanceLink
3. Cliente abre o openfinanceLink → aceita os termos → escolhe banco (PF/PJ)
      → é redirecionado ao internet banking/app → autoriza
      → conector criado; GET /account/:accountHash passa a trazer openfinanceId
      → webhook STATEMENT_OPENFINANCE (conexão ATIVA)
4. Aguardar a sincronização inicial: 6 a 24 h, dependendo do banco
5. POST /statement/openfinance {accountHash, dateStart, dateEnd, statementType}
      → 201 {"uniqueId": "...", "status": "PROCESSING"}
6. Webhook STATEMENT_OPENFINANCE_PROCESSED  (ou polling)
7. GET /statement/openfinance/{uniqueId}[/paginated]
      → status SUCCESS | FAILED; transaction{credit,debit}; transactionDuplicated{...}
8. Importar no ERP, conciliar e contabilizar
9. Manutenção contínua:
      - webhook STATEMENT_OPENFINANCE_REVOKED  → conexão INATIVA (pedir nova autorização)
      - eventos transaction_deleted / transactions_updated (reprocessamento)
```

### 3.1 Cadastro (passos 1 e 2)

```json
POST /payer
{
  "name": "EMPRESA CLIENTE LTDA",
  "cpfCnpj": "01001001000113",
  "neighborhood": "CENTRO", "addressNumber": "100",
  "zipcode": "24800000", "state": "RJ", "city": "ITABORAI",
  "statementActived": true
}
```

```json
POST /account          (o corpo é um ARRAY)
[{ "bankCode": "001", "agency": "1111", "accountNumber": "0001", "statementActived": true }]

→ { "accounts": [{ "accountHash": "gDyriq_q39", ...,
                   "openfinanceLink": "https://staging.pagamentobancario.com.br/gui/7e23..." }] }
```

- O `openfinanceLink` é a tela white-label de consentimento. Pode ser mandado por WhatsApp ou e-mail ao cliente, ou embutido no portal.
- Uma conta aceita **um conector** só. Se o processo for repetido, aparece a mensagem "conta vinculada".
- Atenção: o `enum` de `bankCode` em `/account` lista os bancos de *pagamento* (CNAB/webservice). A central de ajuda diz que, para o extrato Open Finance, o cadastro aceita os códigos da lista de instituições Open Finance. Instituições de pagamento sem COMPE usam um código do conector (9xx). Esse ponto deve ser validado no sandbox.

### 3.2 Gerar protocolo (passo 5)

```json
POST /statement/openfinance
{
  "accountHash": "gDyriq_q39",
  "dateStart": "2026-10-01",
  "dateEnd": "2026-10-21",
  "statementType": "BANK"            // ou "CREDIT_CARD" + "cardNumber": "5817"
}
// alternativa: "today": true (somente o dia)
```

**Limite de requisições:** 1 protocolo **bem-sucedido** a cada 6 horas por `accountHash` + `statementType`, com contador zerado às 00h. Na prática, são no máximo **4 extratos por dia por conta** e por tipo. O limite reflete créditos mensais junto ao Open Finance, e estourá-lo derruba a operação inteira, não só a consulta.

### 3.3 Consultar o resultado (passo 7)

| Rota | Uso | Limites |
|---|---|---|
| `GET /statement/openfinance/{uniqueId}` | Resultado completo de um protocolo | 3 req/min, cache de 1 h |
| `GET /statement/openfinance/{uniqueId}/paginated?page=&pageLimit=` | Mesmo resultado, paginado (máximo de 50) | idem |
| `GET /statement/openfinance?dateStart=&dateEnd=&page=` | Lista dos protocolos recentes, para recuperar `uniqueId` perdidos | 3 req/min, cache de 1 h |
| `GET /statement/transactions/openfinance?accountHash=&dateStart=&dateEnd=&statementType=&cursor=` | **Todas as transações já coletadas**, sem depender de protocolo. Padrão: últimos 7 dias. | máximo de 50 por página; use `cursor` |
| `GET /statement/credit-card/openfinance?accountHash=` | Cartões da conta: `cardNumber`, adicionais e limites | — |
| `GET /balance/openfinance/realtime?accountHash=` | Saldo: `balance`, `updateDateTime`, `nextUpdate` | cache de 6 h |
| `GET /statement/billing/openfinance` | Bilhetagem (pagadores e contas ativas, extratos, transações) | — |

Para sincronização incremental, a rota `/statement/transactions/openfinance` com **cursor** é a mais adequada. Ela não repete nem pula transações quando chegam dados novos durante a navegação, e o tempo de resposta é estável.

---

## 4. Modelo de dados da transação

Campos comuns (BANK e CREDIT_CARD):

| Campo | Observação para o ERP |
|---|---|
| `transactionId` | **Chave de idempotência.** Estável entre consultas. O `fitid` vem sempre `null`. |
| `transactionType` | `credit` / `debit`. O `amount` é **sempre positivo**, e o sinal vem deste campo. |
| `amount` | String decimal com 2 casas. Converter para `Decimal`, nunca para `float`. |
| `date` | **Data de lançamento** (postagem), em YYYY-MM-DD no fuso de Brasília. Não é a data da operação. |
| `description`, `name`, `category`, `code` | `code` é a categoria normalizada (ex.: `DIGITALSERVICES`). É útil como sinal para classificação, mas não substitui o plano de contas. |
| `sequence` | Ordem dentro da lista credit/debit daquele extrato |
| `currencyCode` | ISO 4217 |

Somente em **BANK**:
- `paymentMethod` (PIX, TED, BOLETO, DEBIT_CARD), `paymentName`, `referenceNumber`
- `participantPayer` / `participantReceiver`: nome, agência, conta, COMPE, ISPB e **documento (CPF/CNPJ)**. É o campo mais valioso para conciliação automática, porque permite casar por CNPJ da contraparte.
- Dados de boleto: `paymentBarcode`, `paymentDigitableLine`, `paymentBaseAmount`, `paymentDiscountAmount`, `paymentInterestAmount`, `paymentPenaltyAmount`. Com eles dá para separar automaticamente principal, desconto, juros e multa.

Somente em **CREDIT_CARD**:
- `creditCardNumber` (4 dígitos, inclusive de cartão adicional)
- `creditCardBill`: `dueDate`, `totalAmount`, `minimumPaymentAmount`, `financeCharges[]` (IOF, juros e outros), `allowsInstallments`
- `creditCardMerchant`: **CNPJ e CNAE do estabelecimento**, `category`
- Parcelamento: `creditCardInstallmentNumber`, `creditCardTotalInstallments`, `creditCardTotalAmount`
- `creditCardAmountInAccountCurrency` (compras em moeda estrangeira)

No protocolo:
- `transaction{credit[],debit[]}` traz transações **novas**.
- `transactionDuplicated{...}` traz transações do período que **já tinham vindo** em protocolos anteriores, com o mesmo `transactionId`. Não importar de novo.
- `totalCredit` / `totalDebit` incluem as duplicadas. Por isso só servem para conferir o protocolo, não para somar ao que já foi importado.

---

## 5. Regras operacionais que mudam o desenho do sistema

### 5.1 Saldo e extrato estão separados desde 12/08/2026
- O bloco `balance.inicial/final` dentro do extrato **não é mais atualizado** e **sai em 02/12/2026**. Quem ainda o ler terá quebra.
- O saldo vem de `GET /balance/openfinance/realtime`. A próxima consulta deve ser agendada pelo `nextUpdate`, não por intervalo fixo.
- **Não conciliar transações contra o saldo instantâneo.** O banco publica o saldo mais rápido que as transações, então a diferença é de propagação e não indica erro. Alertas do tipo "saldo do extrato ≠ saldo do banco" precisam de tolerância temporal, ou devem ser feitos só em períodos já fechados.

### 5.2 Transações podem sumir e voltar com outro ID
- Alguns bancos retiram transações por 1 a 3 dias úteis, principalmente em fins de semana, feriados e instabilidades, e depois as republicam com **novo `transactionId`**.
- A TecnoSpeed envia `transaction_deleted` com `statement_id` e `transaction_ids`, e depois `transactions_updated` com os novos IDs. O protocolo fica numa fila de reprocessamento diário por **até 7 dias**. A partir do 8º dia, só gerando um novo protocolo.
- Para receber esses eventos, é preciso assinar `STATEMENT_OPENFINANCE_UPDATED`, conforme o artigo. Esse evento ainda não aparece no enum do `POST /notification` da spec e deve ser confirmado com o suporte.
- **Consequência contábil:** só **consolidar ou fechar** o período depois de vencida a janela de reprocessamento, ou seja, alguns dias úteis após o fim do mês. Se a transação já foi contabilizada e chega `transaction_deleted`, **estornar** o lançamento em vez de apagar, para manter a trilha de auditoria.

### 5.3 Latência inicial
- Depois da autorização, contas, saldos, transações e faturas levam de **6 a 24 h** para aparecer. O onboarding do cliente precisa avisar isso, para o "não veio nada" não virar chamado.

### 5.4 Data de lançamento × data da transação
- O campo `date` é sempre a **data de lançamento**. Bradesco, Itaú e Santander podem lançar com D+1 ou mais.
- Para a conciliação bancária, essa é a data correta, porque é quando o saldo muda. Para competência (seção 6), use o documento de origem (NF, boleto, fatura), não o extrato.

---

## 6. Leitura contábil e tributária

### 6.1 Fundamentos
- **ITG 2000 (R1)**, escrituração contábil: o extrato via Open Finance é documento de suporte da conta Bancos. O ERP deve guardar o JSON original (`transactionId`, `uniqueId` do protocolo, data de coleta) como evidência, com retenção compatível com os prazos de guarda fiscal.
- **NBC TG 03 (R3) / CPC 03 (R2)**, Demonstração dos Fluxos de Caixa: o extrato é base de **caixa**. `paymentMethod`, `category` e a contraparte ajudam a classificar o fluxo em operacional, investimento ou financiamento.
- **Regime de competência (NBC TG Estrutura Conceitual / CPC 00 R2)**: o extrato só confirma a **liquidação**. Receitas e despesas são reconhecidas pelo fato gerador, ou seja, pela NF ou pelo contrato. O desenho recomendado é **casar o extrato com títulos a receber e a pagar** (baixa), e não lançar resultado direto do extrato, exceto para itens que só existem nele: tarifas, IOF, rendimentos e juros de cheque especial.

### 6.2 Regras de classificação que a API permite automatizar

| Sinal na API | Tratamento sugerido |
|---|---|
| `participantPayer.documentNumber` = CNPJ de cliente cadastrado | Baixa de duplicata a receber (D Bancos / C Clientes) |
| `participantReceiver.documentNumber` = CNPJ de fornecedor | Baixa de fornecedor (D Fornecedores / C Bancos) |
| Contraparte com o **mesmo CNPJ** do pagador | Transferência entre contas próprias: neutralizar e não gerar resultado |
| Contraparte com CPF de sócio | Pró-labore, distribuição de lucros, AFAC ou mútuo. **Exige revisão humana**, porque o efeito tributário muda (INSS sobre pró-labore; isenção de lucros só com escrituração que a sustente). |
| Boleto com `paymentInterestAmount` / `paymentPenaltyAmount` | Separar juros e multa de mora em **despesa financeira** |
| Boleto com `paymentDiscountAmount` | **Desconto obtido**, que é receita financeira. No Lucro Real não cumulativo, há PIS/COFINS sobre receitas financeiras de 0,65% e 4% (Decreto 8.426/2015). |
| `category`/`code` de tarifa ou IOF | Despesas bancárias / IOF |
| Rendimento de aplicação | Receita financeira, com IRRF na fonte como antecipação compensável |

### 6.3 Cartão de crédito corporativo
- A compra no cartão é **despesa ou ativo na data da compra** (competência), contra **Cartão de crédito a pagar** (passivo circulante). O pagamento da fatura é que baixa o passivo pela conta Bancos. Não se deve lançar a fatura inteira como "despesa diversa" no vencimento.
- Compra parcelada: com `creditCardTotalAmount` e o total de parcelas, o passivo pelo valor total pode ser reconhecido na compra, se essa for a política contábil adotada. Isso evita reconhecer a despesa parcela a parcela, o que distorce a competência.
- `creditCardMerchant.cpfCnpj` + `cnae` ajudam a cobrar a **NF de cada compra**. Sem documento fiscal, a despesa fica frágil para dedutibilidade no Lucro Real e para créditos de PIS/COFINS (e de IBS/CBS a partir da transição da Reforma Tributária, cujo crédito depende de documento fiscal idôneo).
- `financeCharges` (IOF, juros rotativos) vão para despesa financeira ou IOF, separados do principal.

### 6.4 Regulação, sigilo e LGPD
- O compartilhamento é **por consentimento do titular** no ambiente do banco, dentro das regras do Open Finance Brasil (Resolução Conjunta CMN/BCB nº 1/2020 e normas posteriores). Isso dá base para afastar o sigilo bancário da LC 105/2001, que permite a quebra com consentimento expresso.
- O escritório passa a tratar **dados pessoais de terceiros** que aparecem nas contrapartes (nome e CPF). É preciso uma base legal na LGPD (execução de contrato / obrigação legal-regulatória da escrituração), a cláusula no contrato de prestação de serviços e controle de acesso por cliente.
- O consentimento expira ou pode ser revogado: o evento `STATEMENT_OPENFINANCE_REVOKED` deve gerar tarefa para pedir nova autorização ao cliente.

---

## 7. Desenho de integração recomendado (para o sistema do escritório)

### 7.1 Tabelas mínimas

```
of_conta        (empresa_id, account_hash, bank_code, openfinance_id, status[PENDENTE|ATIVA|INATIVA],
                 link_consentimento, ativada_em, revogada_em)
of_protocolo    (unique_id, account_hash, tipo[BANK|CREDIT_CARD], card_number, date_start, date_end,
                 status[PROCESSING|SUCCESS|FAILED], reason, solicitado_em, proximo_permitido_em)
of_transacao    (transaction_id PK, account_hash, protocolo_unique_id, tipo, natureza[credit|debit],
                 valor NUMERIC(15,2), data_lancamento, descricao, categoria, documento_contraparte,
                 payload_json, situacao[ATIVA|EXCLUIDA_ORIGEM], conciliada_em, lancamento_id)
of_saldo        (account_hash, saldo, consultado_em, next_update)
of_evento       (id, tipo, payload_json, recebido_em, processado_em)   -- idempotência de webhooks
```

### 7.2 Regras de implementação
1. **Idempotência por `transactionId`**: `INSERT ... ON CONFLICT DO NOTHING`. Ignorar `transactionDuplicated`.
2. **Agendador ciente do limite**: guardar `proximo_permitido_em = solicitado_em + 6h` por conta e tipo, e nunca disparar antes disso. Uma rotina útil é **1 protocolo de manhã** (D-3 até hoje, para capturar lançamentos tardios) e **1 no fim do dia**.
3. **Webhook primeiro, polling como reserva**: ao receber `STATEMENT_OPENFINANCE_PROCESSED`, buscar o protocolo. Protocolos em `PROCESSING` há mais de X horas são varridos pela listagem, respeitando 3 req/min.
4. **Paginação por cursor** em `/statement/transactions/openfinance` para a carga inicial e para ressincronizar.
5. **`transaction_deleted`**: marcar a transação como `EXCLUIDA_ORIGEM`. Se já estiver conciliada, gerar **estorno** e uma pendência. **`transactions_updated`**: ressincronizar pelo `statement_id`.
6. **Fechamento mensal**: travar a competência só depois de D+7 corridos do último dia do mês, por causa da janela de reprocessamento.
7. **Saldo**: guardar e exibir com "atualizado em …". Usar só como indicador, nunca como trava de conciliação.
8. **Dinheiro em `Decimal`**, datas sem conversão de fuso (já vêm no fuso de Brasília), e `amount` com sinal derivado de `transactionType`.
9. **Segredos**: `TECNOSPEED_CNPJ_SH`, `TECNOSPEED_TOKEN_SH` e `TECNOSPEED_AMBIENTE` em variáveis de ambiente.
10. **Erros mapeáveis para o usuário**: 401 "Payer não encontrado", 401 "Software House/Payer sem autorização para a função Extrato via Open Finance", 404 "conta não encontrada", 422 `internalCode 3001` ("Ative o Extrato Open Finance para ser utilizado por essa conta"), 422 `4001` (header obrigatório ausente), 422 `4002` (cursor inválido).

### 7.3 Esqueleto de cliente (Python, sem dependências externas)

```python
import json, os, urllib.request
from decimal import Decimal

BASES = {"homologacao": "https://staging.pagamentobancario.com.br/api/v1",
         "producao": "https://api.pagamentobancario.com.br/api/v1"}

class TecnospeedOpenFinance:
    def __init__(self, cnpj_sh=None, token_sh=None, ambiente=None):
        self.base = BASES[ambiente or os.environ.get("TECNOSPEED_AMBIENTE", "homologacao")]
        self.cnpj_sh = cnpj_sh or os.environ["TECNOSPEED_CNPJ_SH"]
        self.token_sh = token_sh or os.environ["TECNOSPEED_TOKEN_SH"]

    def _req(self, metodo, caminho, pagador=None, corpo=None):
        headers = {"cnpjsh": self.cnpj_sh, "tokensh": self.token_sh,
                   "User-Agent": "mo-contabil/1.0", "Content-Type": "application/json"}
        if pagador:
            headers["payercpfcnpj"] = pagador
        dados = json.dumps(corpo).encode() if corpo is not None else None
        req = urllib.request.Request(self.base + caminho, data=dados, headers=headers, method=metodo)
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read() or b"null")

    def gerar_protocolo(self, pagador, account_hash, inicio, fim, tipo="BANK", cartao=None):
        corpo = {"accountHash": account_hash, "dateStart": inicio, "dateEnd": fim, "statementType": tipo}
        if tipo == "CREDIT_CARD":
            corpo["cardNumber"] = cartao
        return self._req("POST", "/statement/openfinance", pagador, corpo)

    def protocolo(self, pagador, unique_id):
        return self._req("GET", f"/statement/openfinance/{unique_id}", pagador)

    def saldo(self, pagador, account_hash):
        return self._req("GET", f"/balance/openfinance/realtime?accountHash={account_hash}", pagador)

def transacoes_novas(resposta_protocolo):
    """Achata credit/debit em lançamentos com sinal, ignorando transactionDuplicated."""
    t = resposta_protocolo.get("transaction") or {}
    for natureza in ("credit", "debit"):
        for item in t.get(natureza) or []:
            valor = Decimal(item["amount"])
            yield {**item, "valor": valor if natureza == "credit" else -valor}
```

---

## 8. Riscos e pontos a validar com a TecnoSpeed antes de contratar

1. **Preço e modelo de cobrança**: por pagador ativo, por conta ou por protocolo. A rota de bilhetagem sugere cobrança por pagador ou conta ativa.
2. **Créditos mensais**: qual é o teto por conta e o que acontece ao atingi-lo, além do limite de 6 h.
3. **Evento `STATEMENT_OPENFINANCE_UPDATED`**: está citado no guia de reprocessamento, mas falta no enum da spec do webhook.
4. **Cobertura PJ real** dos bancos da carteira de clientes. O cruzamento deve ser feito com a lista de 68 instituições PJ (Itaú Emps, BB, Bradesco, Santander, Caixa, Sicoob, Sicredi, Inter, C6, BTG, Nubank, Stone, Cielo, Mercado Pago, PagBank, InfinitePay etc.).
5. **Prazo de validade do consentimento** e renovação: impacta a rotina de atendimento.
6. **Histórico inicial disponível** (quantos meses para trás) por instituição.
7. **Retenção dos dados** na TecnoSpeed e papel de controlador ou operador na LGPD, para constar no contrato e no DPA.
8. **Sandbox**: se o `openfinanceLink` de homologação tem banco simulado para testes de ponta a ponta.

---

## 9. Comparativo com o fluxo atual (OFX manual)

| Critério | OFX/CSV enviado pelo cliente | Open Finance TecnoSpeed |
|---|---|---|
| Esforço do cliente | Mensal e recorrente | Uma autorização (renovada quando expira) |
| Atraso | Dias ou semanas | Até 4 coletas/dia, com latência do banco de horas a 1-3 dias úteis |
| Identificador | FITID, que varia por banco | `transactionId` estável, com deduplicação nativa |
| Contraparte (CPF/CNPJ) | Raramente | Sim, em BANK |
| Detalhe de boleto (juros/multa/desconto) | Não | Sim |
| Cartão de crédito | PDF da fatura | JSON com fatura, parcelas e CNPJ/CNAE do estabelecimento |
| Custo | Zero de software, alto de operação | Contrato TecnoSpeed |
| Risco | Arquivo errado ou incompleto | Transações removidas e republicadas, revogação de consentimento |

**Conclusão:** para um escritório que faz BPO financeiro e conciliação de muitas empresas, a API resolve o maior gargalo operacional, que é obter o extrato. Os dados de contraparte e de boleto permitem automatizar baixas e separar encargos com uma qualidade que o OFX não oferece. Os cuidados obrigatórios são idempotência por `transactionId`, tratamento de exclusão e reprocessamento, fechamento só após a janela de 7 dias e não usar o saldo instantâneo como trava de conciliação.
