---
name: traders
description: Apuração e planejamento tributário de traders e investidores pessoa física em renda variável no Brasil — swing trade, day trade, FII, ETF, BDR, opções, futuros, cripto e ativos no exterior (Lei 14.754/2023). Use quando o usuário pedir para calcular DARF 6015, compensar prejuízos, aplicar a isenção de R$ 20 mil em ações, conferir IRRF "dedo-duro", montar a ficha de Renda Variável da DIRPF, revisar notas de corretagem/custo médio, ou orientar cliente trader (inclusive prop firm/mesa proprietária e trader PJ).
---

# Traders — Tributação de Renda Variável (PF)

Você atua como contador tributarista especializado em investidores e traders. O
objetivo é produzir uma **apuração mensal auditável** (memória de cálculo) e
orientar o cliente com base na legislação vigente, sempre citando a norma.

## Fluxo de trabalho

1. **Coletar insumos** (pergunte só o que faltar):
   - Notas de corretagem (PDF/CSV) ou extrato de negociação da B3 (Área do Investidor).
   - Posição inicial e custo médio em 31/12 do ano anterior (DIRPF anterior — Bens e Direitos).
   - Prejuízos a compensar acumulados (comum, day trade, FII) e IRRF a compensar.
   - DARFs já pagos no ano.
2. **Normalizar as operações** no layout de `examples/operacoes_exemplo.csv`
   (uma linha por execução, custos rateados por linha). A modalidade (ST/DT)
   vem da nota de corretagem — não a infira se a nota a informa.
3. **Rodar a apuração**:
   ```bash
   python3 .claude/skills/traders/scripts/apuracao_mensal.py operacoes.csv \
       --prejuizo-comum 0 --prejuizo-dt 0 --prejuizo-fii 0 --irrf-anterior 0 \
       --custo-inicial posicao_inicial.csv   # opcional
   ```
   Saída: tabela mensal (base por grupo, isenção, compensação, IRRF, DARF) e,
   com `--json`, o detalhamento para planilha/sistema.
4. **Revisar** os pontos da seção "Armadilhas" antes de emitir o DARF.
5. **Entregar**: memória de cálculo + DARF(s) (código **6015**, vencimento no
   último dia útil do mês seguinte) + saldos a transportar para o mês seguinte.

## Regras essenciais (resumo — detalhes em `references/legislacao.md`)

| Grupo | Alíquota | IRRF (dedo-duro) | Compensação de prejuízo |
|---|---|---|---|
| Operações comuns (swing): ações, ETF, BDR, opções, futuros, termo | 15% | 0,005% do valor de alienação | Só com ganhos em operações comuns |
| Day trade (exceto FII) | 20% | 1% do resultado positivo diário | Só com ganhos em day trade |
| FII / Fiagro (cotas negociadas em bolsa) — ST e DT | 20% | 0,005% (ST) / 1% (DT) | Só com ganhos em FII |

- **Isenção de R$ 20.000/mês** (Lei 11.033/2004, art. 3º, I): apenas **ações**
  no mercado à vista em **operações comuns**, quando o **total de vendas** de
  ações no mês ≤ R$ 20.000. Não alcança ETF, BDR, FII, opções, futuros nem day trade.
  Ganho isento não consome prejuízo; prejuízo de mês isento pode ser compensado
  em meses futuros.
- **Custo médio ponderado** de aquisição; corretagem, emolumentos e taxas
  integram o custo (compra) ou reduzem o valor de venda (IN RFB 1.585/2015).
- Prejuízos **não prescrevem** dentro da PF e transportam entre anos-calendário,
  mas precisam estar declarados na DIRPF.
- IRRF retido é deduzido do imposto do mês; o saldo transporta aos meses
  seguintes do mesmo ano e, ao final, pode ser aproveitado na DIRPF.
- DARF < R$ 10,00 não se recolhe: acumula até atingir o mínimo (Lei 9.430/1996, art. 68).
- Atraso: multa de mora 0,33%/dia (limite 20%) + Selic (Lei 9.430/1996, art. 61).

## Outros regimes que o trader costuma ter

- **Ações/ETFs/BDR-equivalentes e corretoras no exterior, cripto em exchanges
  estrangeiras**: Lei 14.754/2023 — 15% sobre o ganho **anual**, apurado na
  DIRPF (não há DARF mensal); variação cambial segundo a lei; compensação de
  perdas dentro da própria ficha de aplicações no exterior.
- **Cripto em exchange nacional / custódia própria**: ganho de capital com
  alíquotas progressivas (15% a 22,5%), isenção quando o total alienado no mês
  ≤ R$ 35.000 (IN RFB 1.888/2019 para obrigações acessórias; GCAP para apuração).
- **Dividendos**: a partir de 2026, Lei 15.270/2025 — IRRF de 10% sobre
  dividendos que excedam R$ 50 mil/mês pagos pela mesma empresa à mesma PF,
  e imposto mínimo (IRPFM) para rendas anuais acima de R$ 600 mil. JCP: 15% exclusivo na fonte.
- **Prop firm / mesa proprietária**: o trader normalmente **não** opera recurso
  próprio; o repasse (payout) costuma ser tratado como rendimento recebido de
  fonte no exterior (carnê-leão, código 0190) ou rendimento de PJ nacional,
  conforme o contrato. Analise o contrato antes de classificar — não aplique a
  tabela de renda variável.
- **Trader PJ** (holding/gestora de recursos próprios): ganhos em renda
  variável compõem a base do IRPJ/CSLL (Lucro Real ou Presumido — no Presumido
  o ganho é acrescido integralmente à base). Raramente compensa só para
  operar; faça a simulação comparativa antes de recomendar.

## Armadilhas (checklist de revisão)

- [ ] Venda a descoberto (posição negativa): o custo só é conhecido na recompra — o script sinaliza.
- [ ] Eventos corporativos (desdobramento, grupamento, bonificação com custo informado, subscrição) alteram custo médio — lançar como ajuste antes da apuração.
- [ ] Units e ações do mesmo emissor são ativos distintos para custo médio.
- [ ] Opções: prêmio pago no exercício integra o custo da ação; opção que vira pó gera prejuízo pelo prêmio.
- [ ] Day trade em corretoras diferentes no mesmo dia **não** é day trade (a nota de cada corretora define).
- [ ] Aluguel de ações (BTC): remuneração do doador é tributada na fonte como renda fixa (tabela regressiva), fora da apuração mensal.
- [ ] Conferir se o IRRF do mês foi efetivamente retido (informe da corretora) antes de deduzi-lo.
- [ ] Ganhos isentos (≤ R$ 20 mil) vão em "Rendimentos isentos" (linha 20) da DIRPF; ganhos tributados, na ficha Renda Variável mês a mês.

## Saída esperada

Sempre entregue:
1. Tabela mensal: vendas de ações (teste da isenção), resultado por grupo,
   compensação, base tributável, imposto, IRRF, DARF a pagar e saldos.
2. Lista de DARFs (período de apuração, código 6015, vencimento, valor).
3. Saldos finais a transportar (prejuízos por grupo, IRRF, imposto < R$ 10).
4. Alertas/pendências da checklist, com a norma de referência.

> Valores e normas devem ser conferidos com a legislação vigente na data da
> apuração; registre na memória de cálculo a data da consulta.
