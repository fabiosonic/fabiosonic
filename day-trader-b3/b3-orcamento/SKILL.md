---
name: b3-orcamento
description: >-
  Dimensionamento de posição para day trade na B3: calcula quantas ações
  comprar pela perda máxima por operação (com custos de emolumentos e
  corretagem), limite de posição, ordem máxima e caixa, separando lote
  padrão (100) e mercado fracionário (código com F), e grava
  trader-b3/ordens.json. Use quando o usuário disser "quantas ações eu
  compro", "dimensiona a posição", "quanto posso arriscar", "monta a ordem"
  ou depois do /b3-saida.
argument-hint: "[--limit [PREÇO]] [--orcamento R$] [--write]"
---

# b3-orcamento

```bash
python3 "${CLAUDE_SKILL_DIR}/size.py"                    # mostra o cálculo
python3 "${CLAUDE_SKILL_DIR}/size.py" --limit --write    # ordem limitada na entrada do plano
python3 "${CLAUDE_SKILL_DIR}/size.py" --limit 58.60 --orcamento 15000 --write
```

Quantidade = o menor entre perda máxima, posição máxima, ordem máxima e caixa
(veja o cálculo impresso). A perda no stop inclui custos estimados de ida e
volta (`custos_pct`, padrão 0,03%, e `corretagem_por_ordem`). Confira a tabela
vigente de emolumentos da B3 e da sua corretora e ajuste o config.

Lote padrão de 100; a sobra vai para o fracionário (`PETR4F`) se
`permitir_fracionario` for true. Zero ações = recusa com o motivo.

Numa ordem a mercado usa o maior entre a entrada do plano e um preço fresco
(< 15 min) de trader-b3/precos.json. Próximo passo: `/b3-risco`.
