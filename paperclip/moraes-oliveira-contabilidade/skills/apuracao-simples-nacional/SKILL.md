---
name: apuracao-simples-nacional
description: >
  Roteiro de apuração mensal do Simples Nacional: RBT12, anexo, Fator R, segregação de receitas
  (monofásico, ST, ISS retido, exportação), alíquota efetiva, sublimite e prévia do PGDAS-D. Use em
  toda apuração de cliente do Simples ou em simulações de enquadramento.
---

# Apuração do Simples Nacional

Base legal: LC 123/2006 e Resolução CGSN 140/2018 (e alterações). Confira a redação vigente.

## Passo a passo

1. **Receita do mês (RPA):** some as notas de saída e de serviço autorizadas, menos cancelamentos e devoluções.
   Regime de caixa ou competência conforme a opção do cliente.
2. **RBT12:** receita bruta dos 12 meses anteriores ao período de apuração. Para empresa em início de atividade, use a proporcionalização legal.
3. **Anexo por atividade (CNAE):** I comércio, II indústria, III, IV ou V serviços.
4. **Fator R** (atividades sujeitas, Anexo V ou III): folha de salários dos 12 meses (incluindo pró-labore,
   INSS patronal e FGTS) ÷ RBT12. Se **≥ 28%**, vai para o Anexo III; se menor, para o Anexo V. Registre o cálculo.
5. **Alíquota efetiva:** (RBT12 × alíquota nominal − parcela a deduzir) ÷ RBT12.
6. **Segregação** (reduz a guia e é o erro mais comum):
   - Produtos **monofásicos** de PIS/Cofins (combustíveis, medicamentos, autopeças, bebidas frias, cosméticos etc. pela NCM):
     zere a parcela de PIS e Cofins.
   - **ICMS-ST** já recolhido: zere a parcela de ICMS.
   - **ISS retido** pelo tomador: informe a retenção.
   - **Exportação:** segregue conforme a regra.
7. **Sublimite** estadual e municipal (R$ 3,6 mi) e teto (R$ 4,8 mi): alerte em caso de proximidade (acima de 80%).
8. **Prévia do PGDAS-D:** monte o quadro por anexo e tributo, com o valor estimado do DAS.

## Alertas obrigatórios no ticket

- Fator R entre 25% e 31%: sugira análise de pró-labore ao consultor-tributario.
- RBT12 acima de 80% do sublimite ou do teto.
- Receita do mês com variação acima de 20% sobre a média trimestral.
- Notas com NCM de monofásico sem segregação nos meses anteriores: possível **crédito para restituição/compensação**.
