---
name: b3-boleta
description: >-
  Boleta e diário de decisões para a B3: mostra cada ordem aprovada pelo
  b3-risco como boleta em português com o passo a passo para digitar no home
  broker (ordem + OCO de stop e alvo), registra o SIM explícito do usuário
  para uma boleta por vez, o envio, as execuções (carteira e
  execucoes.csv para o IR) e monta a ordem de zerar. Nunca envia ordem
  sozinha. Use quando o usuário disser "manda a ordem", "mostra a boleta",
  "sim", "executou a 58,57", "zera PETR4" ou "o que eu fiz hoje".
argument-hint: "show | approve --index N --reply \"sim\" | result | fill | zerar | log"
---

# b3-boleta

Esta skill não fala com corretora. O usuário digita a ordem no home broker
(ou MetaTrader 5, Profit etc.) depois do sim. Comece pela conta simulada da
corretora (`"simulacao": true` no config).

```bash
python3 "${CLAUDE_SKILL_DIR}/ticket.py" show
python3 "${CLAUDE_SKILL_DIR}/ticket.py" approve --index 1 --reply "<resposta do usuário, palavra por palavra>"
python3 "${CLAUDE_SKILL_DIR}/ticket.py" result --index 1 --status enviada --id 123456
python3 "${CLAUDE_SKILL_DIR}/ticket.py" fill --codigo PETR4 --lado compra --qtd 200 --preco 58.57 --custos 3.51
python3 "${CLAUDE_SKILL_DIR}/ticket.py" zerar --symbol PETR4 --write   # depois /b3-risco e show/approve
python3 "${CLAUDE_SKILL_DIR}/ticket.py" log
```

## Regras inegociáveis

1. Mostre a boleta com `show` e PERGUNTE. Só chame `approve` com a resposta
   literal do usuário em `--reply`. Nunca escreva "sim" por ele.
2. Uma boleta por sim. "Sim para todas", "ok", "pode ser", um sim com
   ressalva, com outro ativo ou outra quantidade são recusados pela ferramenta:
   não contorne.
3. Só boleta PRONTA (aprovada pelo `/b3-risco` hoje, idêntica) pode ser aprovada.
4. Registre o resultado e as execuções que o usuário informar; `fill` atualiza
   trader-b3/carteira.json e acrescenta trader-b3/execucoes.csv, base do
   `/b3-fiscal`.

Não é recomendação de investimento.
