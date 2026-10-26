---
name: b3-fiscal
description: >-
  Ponte fiscal do day-trader-b3: lê as execuções registradas pela b3-boleta,
  separa day trade de operação comum (mesmo ativo comprado e vendido no mesmo
  dia, lote e fracionário juntos), rateia custos e exporta no layout da skill
  traders, rodando a apuração mensal de IR (20% day trade, 15% comum, IRRF,
  compensação de prejuízos, DARF 6015). Use quando o usuário disser "quanto
  de imposto deu meu day trade", "gera o DARF", "apura o IR do mês" ou
  "exporta minhas operações para o contador".
argument-hint: "exportar | apurar [--prejuizo-dt R$] [--irrf-anterior R$]"
---

# b3-fiscal

```bash
python3 "${CLAUDE_SKILL_DIR}/fiscal.py" exportar     # -> trader-b3/operacoes_ir.csv
python3 "${CLAUDE_SKILL_DIR}/fiscal.py" apurar       # exporta e roda a skill traders
python3 "${CLAUDE_SKILL_DIR}/fiscal.py" apurar --prejuizo-dt 350.20 --prejuizo-comum 0 --irrf-anterior 1.10
```

- Base legal da separação: IN RFB 1.585/2015, art. 65, §1º (mesmo ativo,
  mesmo dia, mesma corretora). Premissa: um arquivo = uma corretora.
- Final 11 (unit, ETF, FII) exige `"tipos"` no config: FII tem alíquota de
  20% e prejuízo segregado; ETF e BDR não têm a isenção de R$ 20 mil.
- A apuração usa `apuracao_mensal.py` da skill `traders` (procura em
  `TRADERS_APURACAO`, `.claude/skills/traders/` do repositório e
  `~/.claude/skills/traders/`). Sem ela, entregue o CSV e indique `/traders`.

Antes de emitir DARF, confira com as notas de corretagem: os custos
registrados à mão podem diferir dos cobrados. Apresente a memória de cálculo,
o DARF (código 6015, vencimento no último dia útil do mês seguinte) e os
saldos de prejuízo e IRRF a transportar.
