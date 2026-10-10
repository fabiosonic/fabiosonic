# Playbook Comercial: Recuperação de Créditos do Simples Nacional

## Público ideal (ordem de prioridade)

1. Farmácias e drogarias (medicamentos + higiene, com crédito alto)
2. Perfumarias e lojas de cosméticos
3. Autopeças, oficinas com venda de peças, lojas de pneus
4. Distribuidoras de bebidas, conveniências, mercados e padarias (água, refrigerante, cerveja)
5. Postos de combustíveis (no Simples)
6. Qualquer comércio que venda mercadoria com ICMS-ST (CSOSN 500)

**Desqualifique** quem fatura acima do limite do Simples, quem não é do Anexo I e quem já segregava corretamente.

## Funil

```
Carteira / indicação  →  Pedido dos XMLs  →  Radar (diagnóstico)  →  Reunião com relatório  →  Contrato de êxito  →  Execução  →  Upsell
```

Meta de conversão de referência: 10 diagnósticos → 6 reuniões → 4 contratos.

## Scripts

### WhatsApp para cliente da carteira

> Olá, {nome}! Revisando a parte fiscal da {empresa}, encontramos indícios de que, nos últimos anos,
> parte dos impostos foi paga a maior no Simples, em produtos que já têm o PIS/COFINS e/ou o ICMS
> recolhidos pelo fabricante. Fizemos uma estimativa preliminar e queremos te apresentar em 20 minutos.
> Você só paga se o valor for efetivamente recuperado. Pode ser {dia} às {hora}?

### WhatsApp para prospect (não cliente)

> Olá, {nome}, tudo bem? Sou {seu nome}, contador(a) da {escritório}. Fazemos um diagnóstico gratuito para
> {farmácias/autopeças/...} no Simples Nacional, que identifica impostos pagos a maior nos últimos 5 anos
> (PIS/COFINS monofásico e ICMS-ST). O processamento é sigiloso e você só paga sobre o que recuperar.
> Posso te explicar como funciona?

### Reunião (20 minutos)

1. **Contexto (2 min):** "Alguns produtos já têm imposto recolhido pela indústria. No Simples, a receita
   deles precisa ser informada separadamente; quando não é, o imposto é pago duas vezes."
2. **Números (5 min):** mostre o relatório do Radar, com o crédito total, os meses e os principais produtos.
3. **Como funciona (5 min):** retificação do PGDAS-D, pedido de restituição/compensação, prazos.
4. **Proposta (5 min):** X% do valor efetivamente restituído ou compensado. Sem valor recuperado, não há cobrança.
5. **Fechamento (3 min):** "Começamos já, porque a cada mês que passa um mês antigo prescreve."

### Objeções

| Objeção | Resposta |
|---------|----------|
| "Isso dá problema com a Receita?" | É um direito previsto na LC 123/2006, feito pelo procedimento oficial do Portal do Simples. Não é planejamento agressivo nem tese judicial. |
| "Meu contador não fazia isso?" | (Cliente de outro escritório) Não critique o colega: "É um ponto técnico que muitas vezes passa; o importante é que dá para corrigir." |
| "Por que só agora?" (cliente seu) | Seja transparente: "Implantamos uma ferramenta de auditoria eletrônica de XML e passamos a revisar toda a carteira." Corrija a segregação imediatamente. |
| "20% é caro." | "Sem o trabalho, o valor é zero e continua prescrevendo. Você só paga sobre o que entrar." |
| "E se a Receita negar?" | "Aí você não paga nada. O risco do trabalho é nosso." |

## Indicadores semanais

- Diagnósticos rodados · Reuniões feitas · Contratos assinados · R$ em pedidos protocolados · R$ efetivamente recebidos
