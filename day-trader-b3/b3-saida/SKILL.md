---
name: b3-saida
description: >-
  Planejador de saída para day trade na B3: define stop e alvo ANTES da
  entrada (meio ou mínima da faixa de abertura, preço, percentual ou ATR;
  alvo em múltiplos de R) e o horário de zerar, gravando
  trader-b3/plano.json. Use quando o usuário disser "onde coloco o stop",
  "qual o alvo", "monta o plano do trade", "quanto eu arrisco por ação" ou
  depois que /b3-entrada disparar.
argument-hint: "plan [--stop or-mid|or-low|preco:X|pct:X|atr:K] [--target 2R]"
---

# b3-saida

```bash
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan                          # de trader-b3/entrada.json: or-mid, 2R
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --stop or-low --target 1.5R --write
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --stop atr:1.5 --write
python3 "${CLAUDE_SKILL_DIR}/exit.py" plan --symbol VALE3 --entry 62.10 --setup nivel --stop pct:1 --date 2026-10-23
python3 "${CLAUDE_SKILL_DIR}/exit.py" show
```

- Stop arredondado para baixo no centavo; alvo = entrada + R x risco.
- Recusa stop acima da entrada, alvo abaixo, risco menor que 0,05% do preço
  (dentro do spread) e entrada que não disparou.
- Zerar até: `zerar_min_antes_fechamento` (10) minutos antes do fim da
  negociação — 16h45 ou 17h45. Muitas corretoras zeram day trade
  automaticamente antes do call: confira o horário da sua.
- Risco/retorno abaixo de `min_risco_retorno` gera aviso; `/b3-risco` bloqueia.

Um stop é um plano, não garantia: gap e leilão podem executar pior.
Próximos passos: `/b3-maquina-do-tempo` (simular) e `/b3-orcamento` (quantidade).
