---
name: simples-nacional
description: Apura o DAS do Simples Nacional (alíquota efetiva, anexos, Fator R, sublimites, segregação de receitas monofásicas/ST) e revisa PGDAS-D. Use para cálculo mensal, planejamento de anexo e conferência de guias.
---

# Simples Nacional — apuração

Base legal: LC 123/2006 e Resolução CGSN 140/2018. Confira as tabelas vigentes no Portal do Simples Nacional antes de fechar valores.

## Passo a passo
1. **RBT12:** receita bruta dos 12 meses anteriores ao período de apuração. Para empresa em início de atividade, aplique a proporcionalização (art. 22 da Res. CGSN 140).
2. **Anexo:** pelo CNAE e pela atividade efetivamente exercida.
3. **Fator R** (atividades do Anexo V que podem ir ao III): folha dos 12 meses (salários, pró-labore, INSS patronal e FGTS) ÷ RBT12. Se for **≥ 28%**, aplica-se o Anexo III.
4. **Alíquota efetiva** = (RBT12 × alíquota nominal − parcela a deduzir) ÷ RBT12.
5. **Segregação:** separe as receitas com ICMS-ST, as monofásicas de PIS/Cofins (por NCM), as de exportação e as com ISS retido, e zere a parcela do tributo correspondente.
6. **Sublimite estadual/municipal** (R$ 3,6 milhões): acima dele, ICMS e ISS são recolhidos fora do DAS.
7. Apresente a memória de cálculo em tabela e o valor por tributo (IRPJ, CSLL, Cofins, PIS, CPP, ICMS/ISS).

## Alertas
- Excesso do limite de R$ 4,8 milhões gera exclusão. Verifique a regra dos 20%.
- Débitos em aberto e pendências cadastrais impedem a opção e podem levar à exclusão.
- Na Reforma Tributária, a partir de 2027 o optante pode escolher recolher IBS/CBS por fora do DAS para gerar crédito integral ao cliente PJ (LC 214/2025). Avalie esse cenário para clientes B2B (skill `reforma-tributaria`).
