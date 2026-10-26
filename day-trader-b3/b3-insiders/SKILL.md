---
name: b3-insiders
description: >-
  Monitor de negociações de administradores e controladores de companhias da
  B3 (formulário de Valores Mobiliários Negociados e Detidos, art. 11 da
  Resolução CVM 44): compras e vendas à vista de diretores, conselheiros,
  órgãos estatutários e controladores por mês e por cargo, e ranking das
  maiores compras ou vendas líquidas do mês. Equivalente brasileiro do
  "Pelosi tracker". Use quando o usuário disser "os diretores estão comprando
  PETR4?", "o controlador vendeu?", "quem está comprando a própria ação",
  "ranking de insiders" ou "movimentação de administradores".
argument-hint: "PETR4[,VALE3] [--meses 3] [--detalhe] | --ranking [--vendas]"
---

# b3-insiders

```bash
python3 "${CLAUDE_SKILL_DIR}/insiders.py" PETR4,WEGE3
python3 "${CLAUDE_SKILL_DIR}/insiders.py" WEGE3 --meses 6 --detalhe
python3 "${CLAUDE_SKILL_DIR}/insiders.py" --ranking
python3 "${CLAUDE_SKILL_DIR}/insiders.py" --ranking --vendas --top 20
python3 "${CLAUDE_SKILL_DIR}/insiders.py" PETR4 --novos     # só meses ainda não vistos
```

Conta só compra e venda à vista de ações da própria companhia; planos de
remuneração, subscrição, doação, empréstimo e bonificação ficam de fora. A
classe do ticker (3 = ON, 4 = PN) vem primeiro.

Limites que precisam ir na resposta: o formulário é mensal e entregue até 10
dias depois do mês; é consolidado por cargo (não traz nomes); venda de
controlador pode ser oferta, reorganização ou necessidade de caixa. Mostra o
passado, não é informação privilegiada e não é sinal de compra ou venda.
