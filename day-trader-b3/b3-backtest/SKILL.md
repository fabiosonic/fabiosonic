---
name: b3-backtest
description: >-
  Backtest de longo prazo e treino do swing trade na B3: baixa o histórico
  diário desde 2000 do IBRA e do Ibovespa (preços ajustados por proventos),
  testa os 10 setups do scanner (5 de compra, 5 de venda) em 1.200
  combinações de entrada, stop, alvo, prazo e filtro com custos,
  escorregamento e aluguel, valida em walk-forward (treina 8 anos, testa nos
  2 seguintes), simula carteira realista com CDI no caixa e grava os
  parâmetros treinados que o b3-swing, o b3-scanner e o b3-risco usam. Use
  quando o usuário disser "faz o backtest", "treina a skill", "otimiza os
  parâmetros", "qual setup funciona", "testa no histórico", "atualiza o
  treino" ou "isso dá dinheiro?".
argument-hint: "baixar | testar --setup X [parâmetros] | otimizar [--write]"
---

# b3-backtest

```bash
python3 "${CLAUDE_SKILL_DIR}/backtest.py" baixar                 # ~150 históricos diários desde 2000 + CDI do BCB
python3 "${CLAUDE_SKILL_DIR}/backtest.py" testar --setup rompimento_20d --entrada abertura --stop atr:3 --alvo 3 --prazo 20
python3 "${CLAUDE_SKILL_DIR}/backtest.py" otimizar               # relatório sem gravar
python3 "${CLAUDE_SKILL_DIR}/backtest.py" otimizar --write       # grava b3-swing/parametros.json e trader-b3/backtest/relatorio.md
```

O universo vem de `trader-b3/universo.txt` (rode `/b3-scanner universo` antes)
ou de `--symbols`. Leva cerca de 2 minutos em 4 núcleos.

## Método (o que dizer ao usuário)

1. Grade por setup: entrada (gatilho, abertura) x stop (swing:3/5/10,
   atr:1.5/2/3) x alvo (1R, 1.5R, 2R, 3R, sem alvo) x prazo (5 a 30 pregões) x
   filtro (nenhum, tendência MM200, regime do Ibovespa, ambos).
2. Custos de 0,03% por perna, 0,05% de escorregamento nas ordens stop,
   aluguel de 2% a.a. no vendido; gap além do stop executa na abertura.
3. Walk-forward: escolhe no treino (8 anos) a combinação de maior t entre as
   com 100+ operações, R médio >= 0,05 e t >= 2, e mede nos 2 anos seguintes.
   Só o resultado fora da amostra conta.
4. Setup ATIVO = o processo deu R médio > 0 e t >= 1,5 fora da amostra. Os
   parâmetros finais vêm dos 10 anos mais recentes.
5. Carteira realista: até 5 posições, risco fixo por operação, sem
   alavancagem, sinais em ordem de menor volatilidade, CDI no caixa livre;
   comparada com CDI e Ibovespa.

`RELATORIO.md` nesta pasta tem o último treino publicado.

## Cuidados obrigatórios na resposta

- Diga que é resultado passado, com viés de sobrevivência (universo = carteira
  atual do índice) e dados gratuitos; não é promessa nem recomendação.
- Mostre sempre a comparação com o CDI e com o padrão anterior, não só o
  melhor número.
- Não troque parâmetros à mão para "melhorar" o resultado olhando o período
  inteiro: isso é excesso de ajuste. Mudanças entram pelo walk-forward.
- Retreine periodicamente (por exemplo a cada 6 meses) com `baixar` +
  `otimizar --write`, e revise o relatório antes de publicar os parâmetros.
