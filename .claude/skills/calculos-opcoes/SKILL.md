---
name: calculos-opcoes
description: Fórmulas, convenções de sinal/unidade e testes do motor de payoff de opções (src/lib/options/payoff.ts). Use ao alterar cálculos do simulador, das operações prontas ou ao adicionar estratégias.
---

# Cálculos de opções

Documentação: `docs/calculos.md`. Código: `src/lib/options/payoff.ts` (puro, usado no servidor e no cliente).

- Compra = +1, venda = −1; quantidade em unidades; `multiplier` (1 para opções de ações na B3); custos = valor fixo total.
- Fluxo inicial positivo = crédito; negativo = débito.
- Use `Dec` (decimal.js). **Atenção:** `isPos()` é verdadeiro para zero — use `gt(0)`/`lt(0)`.
- Payoff é linear por partes entre strikes; equilíbrios por interpolação exata; extremos avaliados em 0, strikes e pela inclinação para S→∞.
- Toda mudança exige caso em `tests/unit/payoff.test.ts` com valor calculado **à mão** e comentado.
- Não apresente payoff como cotação antes do vencimento, previsão ou garantia; não invente probabilidades.
