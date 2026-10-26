---
name: b3-risco
description: >-
  Gestor de risco antes da ordem na B3: confere cada ordem de
  trader-b3/ordens.json contra as regras do config (perda por operação e
  diária, tamanho, posição, caixa, reserva, duplicidade, limite de ordens e
  de operações no dia, stop obrigatório, risco/retorno, janela de horário,
  feriados, lote e fracionário, opções e venda a descoberto) e responde
  APROVADA ou BLOQUEADA. Use quando o usuário disser "confere o risco",
  "posso mandar essa ordem?", "checa a ordem" ou antes do /b3-boleta.
argument-hint: "[--now \"AAAA-MM-DD HH:MM\"] [--json]"
---

# b3-risco

```bash
python3 "${CLAUDE_SKILL_DIR}/check.py"              # grava trader-b3/estado/risco.json
python3 "${CLAUDE_SKILL_DIR}/check.py" --json --no-write
```

- Ordens conferidas em sequência como se cada aprovada fosse executada.
- Lote e fracionário do mesmo ativo somam na perda por operação.
- SAÍDA (venda que só reduz posição) sempre pode sair: só formato, ativo e
  venda a descoberto bloqueiam; o resto vira aviso.
- O veredito guarda a impressão digital de cada ordem: `/b3-boleta` só deixa
  PRONTA a ordem idêntica à aprovada hoje.
- Saída 0 se todas passaram, 1 se alguma foi bloqueada.

Apresente cada ordem com APROVADA ou BLOQUEADA e todos os motivos, sem
suavizar. Nunca sugira mudar o config só para passar uma ordem bloqueada;
se o usuário quiser, ele mesmo edita trader-b3/config.json.
