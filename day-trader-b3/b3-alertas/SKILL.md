---
name: b3-alertas
description: >-
  Alertas de preço e relógio da B3: diz se o pregão está aberto (pré-abertura,
  negociação, call de fechamento, feriado) com a janela de entradas e o
  horário de zerar, busca cotações para trader-b3/precos.json e dispara
  alertas de preço acima/abaixo, abertura e hora de zerar, inclusive os de
  stop e alvo do plano. Use quando o usuário disser "a bolsa está aberta?",
  "me avisa se PETR4 passar de 60", "cria alertas do plano", "cotação de
  VALE3" ou "confere os alertas".
argument-hint: "clock | quote PETR4,VALE3 | add PETR4 acima 59.17 | from-plan | check"
---

# b3-alertas

```bash
python3 "${CLAUDE_SKILL_DIR}/alerts.py" clock
python3 "${CLAUDE_SKILL_DIR}/alerts.py" quote PETR4,VALE3
python3 "${CLAUDE_SKILL_DIR}/alerts.py" add PETR4 acima 59.17 --nota "alvo"
python3 "${CLAUDE_SKILL_DIR}/alerts.py" add PETR4 zerar
python3 "${CLAUDE_SKILL_DIR}/alerts.py" from-plan       # stop, alvo e zerar do plano
python3 "${CLAUDE_SKILL_DIR}/alerts.py" check           # cada alerta toca uma vez por dia
python3 "${CLAUDE_SKILL_DIR}/alerts.py" list
python3 "${CLAUDE_SKILL_DIR}/alerts.py" reset
```

Para acompanhar durante o pregão, rode `check` em intervalo (por exemplo
`/loop 2m` chamando esta skill). Preços do Yahoo podem atrasar até 15
minutos: confirme na corretora antes de agir. Um alerta não executa nada.
