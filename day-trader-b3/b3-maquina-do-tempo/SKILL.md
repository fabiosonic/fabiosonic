---
name: b3-maquina-do-tempo
description: >-
  Máquina do tempo para day trade na B3: reproduz o plano (entrada, stop,
  alvo) em 10.000 simulações do resto do pregão montadas com os candles de 5
  minutos dos últimos 60 dias do próprio ativo, e reaplica a mesma regra em
  cada pregão passado. Mostra chance de alvo antes do stop, R médio e um
  veredito. Use quando o usuário disser "simula esse trade", "qual a chance
  de bater o alvo", "backtest do ORB", "vale a pena esse plano?" ou depois do
  /b3-saida.
argument-hint: "run [--replays 10000] [--seed 19] [--ate HH:MM]"
---

# b3-maquina-do-tempo

```bash
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run                    # trader-b3/plano.json
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --write --json     # grava trader-b3/maquina.json
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --ate 16:30 --seed 7 --replays 20000
python3 "${CLAUDE_SKILL_DIR}/timemachine.py" run --symbol PETR4 --date 2026-10-23 \
    --entry 58.57 --stop 58.27 --target 59.17 --entry-time 10:25
```

Algoritmo (o mesmo do day-trader-skill): pool de razões OHLC/fechamento
anterior por posição do candle, sorteio com janela de ±2 posições, stop
testado antes do alvo em cada candle (um candle que toca os dois conta como
stop). Mesma semente e mesmos dados dão o mesmo resultado.

Particularidade da B3: a duração do pregão muda com o horário de verão
americano (83 ou 95 candles de 5 minutos). Com menos de 20 pregões da mesma
duração, usa os de outra duração em posição proporcional e avisa.

Apresente: % alvo primeiro, % stop primeiro, % nenhum, R médio, faixa de
preço no fim, o veredito e o histórico da regra. Sempre diga que simulação
com 60 dias do próprio ativo não é previsão: resultado trimestral, notícia e
leilão podem fazer o que os últimos 60 dias não fizeram.
