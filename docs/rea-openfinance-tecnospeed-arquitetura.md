# REA × Open Finance TecnoSpeed: arquitetura observada

> Complementa `docs/estudo-openfinance-tecnospeed.md`.
> Ferramenta de referência: [REA – Reverse Engineer Anything](https://github.com/morluto/rea), um MCP para análise de apps, binários e sites.
> Data da observação: 22/10/2026.

## 1. Escopo e limites éticos/legais

A análise foi **passiva** e ficou restrita ao que os servidores da TecnoSpeed entregam publicamente a qualquer navegador:

- o HTML/JS da tela de consentimento de **exemplo** publicada na própria documentação (`https://staging.pagamentobancario.com.br/gui/7e23a377f1264936a19c4689c7bffa0c`);
- a especificação OpenAPI pública (`https://docs.pagamentobancario.com.br/api.json`);
- os artigos públicos da central de ajuda.

**Não foi feito**: login, chamada às APIs internas `/gui/api/*`, geração de connect token, captura de tráfego de cliente real, nem qualquer tentativa de contornar autenticação. Isso segue o próprio `DISCLAIMER.md` do REA (uso para interoperabilidade e estudo, sem burlar controles de acesso nem copiar código proprietário).

O lado servidor da TecnoSpeed não é observável por engenharia reversa, e é ali que ficam a integração com os bancos, as credenciais e a regulação. O que se consegue é entender **a arquitetura e o fornecedor por trás do produto**, e é isso que importa para a decisão de negócio.

## 2. Principal achado: a TecnoSpeed revende a Pluggy

A tela `openfinanceLink` carrega o widget oficial da **Pluggy**:

```html
<script src="https://cdn.pluggy.ai/pluggy-connect/latest/pluggy-connect.js"></script>
```

```js
const res = await fetch("/gui/api/connect-token", { method: "POST" });   // backend TS gera connect token Pluggy
const { accessToken } = await res.json();
const pluggyConnect = new PluggyConnect({
  connectToken: accessToken,
  includeSandbox: PLUGGY_SANDBOX,
  onSuccess: (payload) => { const id = payload?.item?.id; ... }       // item da Pluggy
});
...
fetch(`/gui/api/v/${ref}/openfinance-id`, { method: "PUT",
  body: JSON.stringify({ openfinanceId: itemId, hasError, errorMessage }) });
```

Ou seja, o **`openfinanceId` da TecnoSpeed é o `item.id` da Pluggy**. Outros sinais confirmam isso:

| Sinal no produto TecnoSpeed | Correspondência na Pluggy |
|---|---|
| "item de conexão (/openfinanceId)" no artigo de latência | `Item` = conexão de um usuário com uma instituição |
| Códigos 9xx para instituições sem COMPE | IDs de `Connector` da Pluggy |
| Erros `INVALID_CREDENTIALS`, `ALREADY_LOGGED_IN`, `CONNECTION_ERROR` tratados na página | Códigos de erro de item da Pluggy |
| Eventos `transaction_deleted` / `transactions_updated` | Webhooks `transactions/deleted` / `transactions/updated` da Pluggy |
| `category` em inglês ("Digital services") e `code` derivado | Categorização automática de transações da Pluggy |
| Cache de 6 h e "créditos mensais" | Limites de sincronização e de consumo do plano do agregador |

### Fluxo real (reconstruído)

```
Cliente → openfinanceLink (TecnoSpeed /gui/{ref})
   1. GET  /gui/api/config                 → { pluggySandbox }
   2. GET  /gui/api/v/{ref}/validate       → { isAbleToConnect, isAlreadyConnected, reason }
   3. GET  /gui/api/v/{ref}/info           → banco/agência/conta exibidos na tela
   4. POST /gui/api/connect-token          → backend TecnoSpeed pede connect token à Pluggy
   5. Widget Pluggy Connect → cliente escolhe o banco → redirect ao app do banco → consentimento
   6. onSuccess(item) → PUT /gui/api/v/{ref}/openfinance-id { openfinanceId: item.id }
   7. Backend TecnoSpeed consulta a Pluggy (accounts/transactions/balance),
      normaliza para o JSON "padrão API de Extratos VAN" e expõe em /statement/openfinance
   8. Telemetria: POST /gui/api/log (com chaves sensíveis mascaradas no cliente)
```

Observação de segurança: a página monta `innerHTML` com `bank`, `agency` e `accountNumber` vindos da API. É um risco baixo de XSS, porque os dados são cadastrados pela própria software house. Fica anotado como boa prática a não repetir no nosso sistema: usar `textContent`.

## 3. O que isso significa para o escritório

**O valor da TecnoSpeed está na conveniência, não na tecnologia proprietária.** Ela agrega:
1. contrato e faturamento únicos, junto com a API de Pagamentos, DDA e VAN;
2. normalização no mesmo JSON do extrato VAN/OFX (uma integração só);
3. deduplicação por protocolo (`transactionDuplicated`), bilhetagem por pagador e suporte em português.

**Alternativa a avaliar: contratar a Pluggy diretamente.** Ela tem API pública, SDKs (Node e Python), sandbox e o mesmo widget.

| Critério | TecnoSpeed (revenda) | Pluggy direto |
|---|---|---|
| Camadas | ERP → TecnoSpeed → Pluggy → bancos | ERP → Pluggy → bancos |
| Latência extra | Cache e limite de 6 h da TecnoSpeed, além da sincronização da Pluggy | Só a sincronização da Pluggy |
| Dados | Normalizados e com alguns campos achatados | Modelo completo (accounts, transactions, investments, loans, identity) |
| Esforço de integração | Menor se já usa a API de Pagamentos/VAN da TecnoSpeed | Maior: o escritório implementa normalização, deduplicação e bilhetagem |
| Custo | Margem da revenda (preço não público) | Plano do agregador (consultar) |
| Dependência | Duas empresas na cadeia | Uma |
| Credenciamento no BCB | Não precisa | Não precisa (o agregador cobre) |

**Recomendação:** pedir cotação às duas.
- Se o volume for pequeno ou médio e o escritório já usar TecnoSpeed para boletos e pagamentos, a revenda compensa pela simplicidade.
- Com muitas empresas no BPO financeiro, ou necessidade de dados além do extrato (investimentos, empréstimos, identidade/CNPJ do titular), contratar direto tende a sair mais barato e mais rico.

O desenho de dados do estudo anterior (idempotência por ID de transação, tratamento de exclusões, fechamento após a janela de reprocessamento) vale para os dois caminhos. Para trocar de fornecedor sem reescrever o sistema, convém um **adaptador** com interface única (`ProvedorOpenFinance`).

## 4. Como reproduzir com o REA na sua máquina

O ambiente desta sessão bloqueou a execução do pacote npm `rea-agents`. Na sua máquina (Node ≥ 22.19), rode:

```bash
npx rea-agents setup                     # registra o MCP do REA no Claude Code e reinicie o agente

# análise estática do HTML/JS público da tela de consentimento
mkdir alvo && curl -sL -o alvo/index.html \
  https://staging.pagamentobancario.com.br/gui/7e23a377f1264936a19c4689c7bffa0c
npx -y rea-agents@latest analyze-javascript-application "$PWD/alvo" --json
```

Para observação no navegador (guia `docs/browser-observation.md` do REA), use **apenas** o link de consentimento de uma conta **sua**, em homologação. Peça ao agente:

> "Com o REA, observe a página de consentimento do meu openfinanceLink de homologação, liste scripts, requisições de rede e fornecedores terceiros, sem enviar credenciais."

Não use o REA em links de clientes, em produção, nem para chamar as rotas internas `/gui/api/*` fora do fluxo normal da página.

## Fontes
- https://github.com/morluto/rea (README e DISCLAIMER)
- https://staging.pagamentobancario.com.br/gui/7e23a377f1264936a19c4689c7bffa0c (exemplo público da documentação TecnoSpeed)
- https://docs.pagamentobancario.com.br/api.json
- https://docs.pluggy.ai/docs/webhooks · https://docs.pluggy.ai/docs/authentication
