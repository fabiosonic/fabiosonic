# mo-openfinance

Extrato bancário e de cartão via **Open Finance** → banco local idempotente → **TXT de lançamentos para o Domínio**.

Construído seguindo o método do [REA – Reverse Engineer Anything](https://github.com/morluto/rea), em duas etapas:
1. **Entender o recurso com evidências.** Ver `docs/estudo-openfinance-tecnospeed.md` (API oficial) e
   `docs/rea-openfinance-tecnospeed-arquitetura.md` (a TecnoSpeed usa a Pluggy por trás).
2. **Construir uma versão própria**: este pacote, com provedores TecnoSpeed e Pluggy intercambiáveis.

Só biblioteca padrão do Python (3.9+).

## O que o pacote garante
- **Sem duplicidade**: chave por id da transação, e o `transactionDuplicated` da TecnoSpeed é ignorado.
- **Limite de 6 h por conta e tipo** respeitado (créditos mensais do Open Finance), com o contador zerando às 00h.
- **Exclusão na origem** (`transaction_deleted` / `transactions/deleted`) nunca apaga: se a transação já foi
  contabilizada, gera **estorno** no próximo arquivo.
- **Data de lançamento** como data contábil do banco. Competência continua vindo da NF.
- **Classificação por CPF/CNPJ da contraparte**: transferência entre contas próprias, sócio (sempre
  pendência), cliente ou fornecedor cadastrado, regras de texto e, por último, conta transitória com pendência.
- **Boleto desdobrado**: principal, juros, multa e desconto obtido, só quando a soma fecha com o débito.
- **Fechamento da competência** liberado só 7 dias após o fim do mês (janela de reprocessamento).

## Uso
```bash
python -m mo_openfinance demo                       # roda offline com exemplos/openfinance
python -m mo_openfinance importar-protocolo --db of.db --json resposta.json
python -m mo_openfinance webhook --db of.db --json evento.json
python -m mo_openfinance exportar --db of.db --config exemplos/openfinance/config_empresa.json \
    --saida lancamentos.txt --pendencias pendencias.csv --competencia 2026-10
# online (TecnoSpeed): TECNOSPEED_CNPJ_SH, TECNOSPEED_TOKEN_SH, TECNOSPEED_AMBIENTE=homologacao
python -m mo_openfinance sincronizar --db of.db --pagadores exemplos/openfinance/pagadores.json
python -m unittest discover -s tests -v
```

O TXT sai no mesmo formato do importador OFX (`data;debito;credito;valor;historico;complemento`, `;`,
vírgula decimal, cp1252). Cadastre esse leiaute de importação no Domínio uma vez.

## A validar antes de produção
- Provedor Pluggy: campos mapeados pela documentação pública. Conferir no sandbox (sinal de `amount`,
  `paymentData`, `boletoMetadata`, `creditCardMetadata`).
- Webhooks TecnoSpeed só funcionam em produção. Em homologação, use `sincronizar`, que consulta os protocolos pendentes.
- O endpoint HTTP que recebe os webhooks deve validar a origem (headers configurados em `POST /notification`)
  antes de chamar `processar_webhook`.
