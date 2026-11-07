---
name: conciliacao-bancaria
description: >
  Procedimento de conciliação bancária mensal (OFX/CSV/PDF x razão contábil), regras de
  classificação por histórico e tratamento de pendências. Use no fechamento contábil mensal.
---

# Conciliação bancária

1. Confirme que o extrato cobre o mês inteiro (saldo inicial = saldo final do mês anterior no razão).
2. Faça o casamento automático por data, valor e documento (tolerância de data de ±3 dias para compensação).
3. Classifique os não conciliados pelas regras de histórico (ex.: "TARIFA" → despesas bancárias; "PIX RECEBIDO" + CNPJ de cliente → clientes).
4. Sem documento ou sem regra: lance em **conta transitória** e abra pendência para o cliente explicar.
5. Saída: relatório com o saldo do extrato, o saldo contábil, a diferença (deve ser zero), os itens em transitória e as novas regras sugeridas.
6. Gere o lote de importação de lançamentos no layout do sistema contábil (skill importacao-dominio).

## Pontos de atenção

- Transferências entre contas do mesmo titular: não são receita.
- Empréstimos e financiamentos: separe principal e juros.
- Retiradas de sócio: identifique se é pró-labore, distribuição de lucros ou adiantamento. Nunca classifique como despesa operacional.
