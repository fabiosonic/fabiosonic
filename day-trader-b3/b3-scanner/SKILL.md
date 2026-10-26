---
name: b3-scanner
description: >-
  Scanner de gráficos da B3. Monta o universo a partir da carteira teórica de
  um índice (IBRA, IBXX, IBOV, SMLL), roda o scan diário de fechamentos
  (rompimento de 20 pregões, bandeira de alta, retomada da média de 20,
  sobrevendido e repique pelo IFR; e os espelhos de venda para swing
  vendido) e o scan intradiário de rompimento da
  faixa de abertura (ORB) em candles de 5 minutos, gravando
  trader-b3/watchlist.json para b3-noticias e b3-entrada. Use quando o
  usuário disser "escaneia a bolsa", "procura setups", "o que está rompendo",
  "ações sobrevendidas", "monta minha watchlist", "ORB de hoje" ou no começo
  do pregão.
argument-hint: "[universo | diario | orb] [--at HH:MM]"
---

# b3-scanner

Primeiro passo do day trade na B3. Lê gráficos gratuitos e lista os que batem
uma regra. Uma lista de gráficos não é recomendação de compra, e um setup não
é previsão: a maioria de quem faz day trade perde dinheiro.

`${CLAUDE_SKILL_DIR}` é a pasta desta skill.

```bash
python3 "${CLAUDE_SKILL_DIR}/scan.py" universo                  # IBRA -> trader-b3/universo.txt
python3 "${CLAUDE_SKILL_DIR}/scan.py" universo --indice IBXX    # IBrX-100
python3 "${CLAUDE_SKILL_DIR}/scan.py" diario                    # antes das 10h -> trader-b3/watchlist.json
python3 "${CLAUDE_SKILL_DIR}/scan.py" diario --symbols PETR4,VALE3,ITUB4
python3 "${CLAUDE_SKILL_DIR}/scan.py" diario --lado venda          # setups de venda (swing vendido)
python3 "${CLAUDE_SKILL_DIR}/scan.py" orb                       # depois das 10h20
python3 "${CLAUDE_SKILL_DIR}/scan.py" orb --at 10:45 --json
```

Opções: `--min-preco` (R$ 1), `--min-volume-fin` (diário: média de 20
pregões, padrão R$ 5 milhões), `--or-minutes 15`, `--limit N`,
`--now "AAAA-MM-DD HH:MM"` (Brasília), `--offline PASTA`, `--no-write`,
`--show N`, `--json`. Saída 0 quando achou algo.

## Regras

Diário (só pregões completos): `rompimento_20d`, `bandeira_alta` (alta > 10%
entre 15 e 5 pregões atrás e faixa dos últimos 5 fechamentos < 5%),
`retomou_mm20`, `sobrevendido` (IFR14 < 30), `repique` (IFR de ontem < 30 e
fechamento acima do de ontem). De venda: `perdeu_20d`, `bandeira_baixa`,
`perdeu_mm20`, `sobrecomprado` (IFR14 > 70), `repique_baixa`. Cada hit traz
`lados` (compra/venda); `--lado` filtra.

ORB: faixa = máxima e mínima dos primeiros 15 minutos (10h00, 10h05, 10h10).
Sinal = primeiro candle completo depois da faixa que FECHA acima da máxima.

## Horários

Pregão do mercado à vista: 10h00 até 16h55 enquanto os EUA estão no horário de
verão; 10h00 até 17h55 no resto do ano (desde 03/11/2026, Ofício B3
050/2026-VNC). Feriados de 2026 conferidos com o Ofício 041/2026-VNC.

## Como apresentar

Mostre a contagem (lidos, ilíquidos, analisados), os sinais com preço e setup,
e lembre que a lista não é recomendação. Próximo passo: `/b3-noticias` para a
watchlist, `/b3-entrada` para day trade ou `/b3-swing plano` para swing.
