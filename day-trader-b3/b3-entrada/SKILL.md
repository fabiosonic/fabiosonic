---
name: b3-entrada
description: >-
  Cronômetro de entrada para ações da B3. Acompanha um setup candle a candle
  (rompimento da faixa de abertura ou fechamento acima de um nível) e diz o
  momento de entrar, respeitando a janela de novas entradas do pregão.
  Grava trader-b3/entrada.json quando dispara. Use quando o usuário disser
  "quando eu entro em PETR4", "avisa quando romper", "acompanha o ORB",
  "já rompeu a máxima?" ou depois do /b3-scanner.
argument-hint: "check|watch|watchlist PETR4 [--setup orb|nivel]"
---

# b3-entrada

Diz a hora de entrar, não se deve entrar. Só posição comprada. Nunca envia ordem.

```bash
python3 "${CLAUDE_SKILL_DIR}/entry.py" check PETR4                  # ORB de 15 min, candles de 5 min
python3 "${CLAUDE_SKILL_DIR}/entry.py" check PETR4 --write          # grava trader-b3/entrada.json se disparou
python3 "${CLAUDE_SKILL_DIR}/entry.py" check VALE3 --setup nivel --nivel 62.40
python3 "${CLAUDE_SKILL_DIR}/entry.py" check PETR4 --min-volume-x 1.5
python3 "${CLAUDE_SKILL_DIR}/entry.py" watch PETR4 --every 30 --write   # uma linha por candle fechado
python3 "${CLAUDE_SKILL_DIR}/entry.py" watchlist                     # todos os hits do scanner
```

Status: `disparou` (saída 0), `aguardando`, `expirado` (sem sinal até o limite
de novas entradas) ou `sem-dados` (sem pregão ou o Yahoo não mandou candles).

Regras: só conta candle COMPLETO na grade de 5 minutos; o sinal é o
fechamento acima da máxima da faixa (pavio não conta). Hora do sinal = fim do
candle. Janela de novas entradas (config): de `sem_entradas_antes` (10h15) até
`sem_entradas_ultimos_min` (40) minutos antes do fim da negociação — 16h15 ou
17h15 conforme o horário da B3.

Dados do Yahoo podem atrasar: confirme o preço no home broker antes de agir.
Próximo passo: `/b3-saida` para definir stop e alvo antes de entrar.
