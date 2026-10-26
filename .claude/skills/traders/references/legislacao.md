# Referências legais — Renda Variável PF

| Tema | Norma | Ponto-chave |
|---|---|---|
| Alíquotas e isenção de R$ 20 mil em ações | Lei 11.033/2004, arts. 2º e 3º | 15% (comum), 20% (day trade); isenção para vendas de ações à vista ≤ R$ 20 mil/mês |
| FII | Lei 8.668/1993, art. 18; Lei 11.033/2004, art. 3º, III | Ganho na alienação de cotas: 20%; rendimentos distribuídos isentos para PF quando atendidos os requisitos (cotas em bolsa, ≥ 100 cotistas, PF < 10% das cotas — redação da Lei 14.754/2023) |
| Regulamento operacional | IN RFB 1.585/2015 (arts. 47 a 70) | Custo médio, apuração mensal, compensação de perdas, IRRF 0,005% e 1% |
| Day trade — definição | IN RFB 1.585/2015, art. 65, §1º | Compra e venda do mesmo ativo, no mesmo dia, na mesma corretora |
| Retenção mínima | IN RFB 1.585/2015 | Dispensa de retenção do IRRF 0,005% quando ≤ R$ 1,00 |
| Recolhimento | Código DARF 6015 | Vencimento no último dia útil do mês subsequente |
| DARF mínimo | Lei 9.430/1996, art. 68 | Valor < R$ 10,00 acumula para períodos seguintes |
| Acréscimos moratórios | Lei 9.430/1996, art. 61 | 0,33% ao dia (máx. 20%) + Selic |
| Aplicações no exterior | Lei 14.754/2023 | 15% anual na DIRPF a partir de 2024; inclui cripto no exterior |
| Criptoativos — obrigações acessórias | IN RFB 1.888/2019 | Declaração mensal quando operar fora de exchange nacional acima de R$ 30 mil |
| Dividendos (a partir de 2026) | Lei 15.270/2025 | IRRF 10% sobre o excedente a R$ 50 mil/mês por fonte; IRPFM para renda > R$ 600 mil/ano |
| Ganho de capital (bens/cripto nacional) | Lei 8.981/1995, art. 21 (red. Lei 13.259/2016) | 15% a 22,5% progressivo |

## Notas de interpretação

- **Prejuízo em mês isento**: a Receita (Perguntas e Respostas IRPF) admite a
  compensação de perdas em operações com ações apuradas em meses cujas vendas
  ficaram dentro do limite de isenção.
- **Compensação de IRRF de day trade**: o IRRF de 1% é dedutível do imposto
  devido no mês e nos meses seguintes; o script trata IRRF em um único saldo
  — se o cliente tiver posição relevante, confira a segregação exigida na
  ficha da DIRPF.
- **FII**: perdas na alienação de cotas de FII só compensam ganhos em FII; o
  script mantém um saldo de prejuízo único para FII (ST e DT), como na ficha
  "Operações — Fundos de Investimento Imobiliário" da DIRPF.
- **MP 1.303/2025** (que propunha alíquota unificada de 17,5% e apuração
  trimestral) **perdeu a eficácia** sem conversão em lei; as regras acima
  continuam vigentes. Monitore novas propostas de reforma da tributação de
  aplicações financeiras.
