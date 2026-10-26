---
name: b3-analista
description: >-
  Analista de resultados de companhias abertas da B3 a partir das
  demonstrações entregues à CVM (ITR e DFP): receita, EBIT, lucro líquido,
  margens e crescimento contra o mesmo trimestre do ano anterior, derivando o
  4º trimestre (anual menos 9 meses), com link do último ITR. Use quando o
  usuário disser "como foi o resultado da WEG", "receita e lucro de PETR4 por
  trimestre", "margem do Itaú", "a empresa está crescendo?" ou antes de operar
  perto da divulgação de resultados.
argument-hint: "PETR4[,VALE3] [--trimestres 6] [--individual]"
---

# b3-analista

```bash
python3 "${CLAUDE_SKILL_DIR}/facts.py" PETR4
python3 "${CLAUDE_SKILL_DIR}/facts.py" WEGE3,ITUB4 --trimestres 8
python3 "${CLAUDE_SKILL_DIR}/facts.py" PETR4 --individual --json --write
```

- DRE consolidada (`--individual` para a individual). Conta 3.01 = receita
  (em bancos, receitas da intermediação financeira); EBIT = "Resultado Antes
  do Resultado Financeiro e dos Tributos" (não existe em bancos e
  seguradoras); lucro = "Lucro/Prejuízo Consolidado do Período".
- Vale a versão mais recente de cada documento (reapresentações substituem).
- Primeira execução baixa cerca de 65 MB da CVM; depois usa o cache de 24 h
  em trader-b3/cache/cvm.

Apresente a tabela em R$ milhões, aponte tendência de margem e crescimento, e
diga a data do último ITR entregue. Dado contábil não é recomendação; para
análise de qualidade de lucro, olhe notas explicativas e itens não recorrentes.
