# Plano de Negócios: BPO Financeiro no escritório contábil

> **Diagnóstico.** A contabilidade tradicional virou commodity, disputada pelo preço com as contabilidades online.
> O empresário de pequena empresa, porém, tem uma dor que ninguém resolve bem: **ele não sabe se está
> ganhando dinheiro**. Paga as contas pelo celular, mistura conta pessoal com a da empresa e só descobre o
> problema quando falta caixa.
>
> **A proposta:** o escritório passa a cuidar da rotina financeira do cliente (contas a pagar, contas a
> receber, conciliação) e entrega todo mês um **relatório gerencial** com DRE, fluxo de caixa, ponto de equilíbrio e
> alertas. É receita **recorrente**, sem exposição fiscal e sem disputa com o Fisco, e aproveita o que o
> escritório já faz bem: organizar e interpretar números.

## 1. Por que BPO financeiro

| Critério | BPO financeiro |
|----------|----------------|
| Risco fiscal | Nenhum: é gestão, não envolve pedido nem tese perante o Fisco |
| Tipo de receita | Mensalidade recorrente (previsível) |
| Ticket | R$ 690 a R$ 2.900/mês por cliente, em geral 2 a 4 vezes o honorário contábil |
| Público | A sua própria carteira (venda para quem já confia em você) |
| Sinergia | A conciliação diária deixa a contabilidade praticamente pronta e reduz o retrabalho no fechamento |
| Retenção | Alta: o cliente passa a depender do relatório para decidir |
| Escala | O Painel Financeiro (pasta `app/`) transforma extrato em DRE em minutos |

## 2. Portfólio e preços (referência; ajuste à sua região)

| Plano | Para quem | O que inclui | Preço/mês |
|-------|-----------|--------------|-----------|
| **Essencial** | Até 150 lançamentos/mês, 1 conta | Conciliação e categorização, DRE gerencial e fluxo de caixa mensal, reunião trimestral | **R$ 690** |
| **Gestão** | Até 400 lançamentos, até 3 contas | Essencial + contas a pagar (agendamento), contas a receber e cobrança, reunião mensal | **R$ 1.490** |
| **Completo** | Até 1.000 lançamentos | Gestão + emissão de boletos e notas, orçamento anual, metas e indicadores, reunião mensal com sócios | **R$ 2.900** |

- **Implantação:** uma mensalidade, cobrada uma vez (cadastro, plano de contas, regras de categorização, acesso aos bancos).
- **Excedente:** R$ 1,50 por lançamento acima da faixa.
- **Reajuste:** anual, pelo IPCA.

## 3. Serviços complementares (sem risco fiscal)

1. **Diagnóstico financeiro avulso** (R$ 900 a R$ 2.500): 6 meses de extratos no Painel, relatório e reunião.
   É a porta de entrada: a maioria dos clientes fecha o BPO depois de ver o relatório.
2. **Adequação à Reforma Tributária** (projeto fixo): revisão de cadastro de produtos e serviços, preparação do ERP
   para IBS/CBS, impacto em preço e fluxo de caixa. É adequação operacional, não recuperação de tributos.
3. **Orçamento e precificação** (projeto): formação de preço, margem de contribuição e metas de venda.
4. **IRPF dos sócios** (sazonal): cliente de BPO já tem o pró-labore e as retiradas organizados.

## 4. Projeção de 12 meses (cenário conservador)

| Mês | Clientes BPO | Ticket médio | Receita recorrente/mês |
|-----|--------------|--------------|------------------------|
| 3 | 3 | R$ 1.100 | R$ 3.300 |
| 6 | 7 | R$ 1.200 | R$ 8.400 |
| 9 | 11 | R$ 1.250 | R$ 13.750 |
| 12 | 15 | R$ 1.300 | **R$ 19.500** |

Mais as implantações (cerca de R$ 18 mil no ano) e os diagnósticos avulsos (cerca de R$ 12 mil no ano).

**Custos incrementais:** um analista financeiro a partir do 4º ou 5º cliente (≈ R$ 5.500/mês com encargos; atende 12 a 15
clientes com o Painel), mais um sistema financeiro, se o cliente não tiver um (R$ 0 a R$ 300/mês).
**Margem esperada ao fim do ano:** 55% a 65% sobre a receita recorrente.

## 5. Plano de 90 dias

**Semanas 1 e 2: preparar a casa**
- [ ] Definir os planos e preços (tabela acima).
- [ ] Revisar o modelo de contrato (`03-modelo-contrato-bpo.md`) com o jurídico.
- [ ] Testar o Painel com os extratos de 2 ou 3 clientes de confiança.
- [ ] Montar o relatório-modelo com a sua marca (o PDF do Painel).

**Semanas 3 a 6: primeiros clientes (carteira)**
- [ ] Escolher 20 clientes com perfil (faturamento acima de R$ 40 mil/mês, sócio sem controle financeiro, reclamação de caixa).
- [ ] Oferecer o **diagnóstico financeiro** (pago ou como cortesia para os 5 primeiros).
- [ ] Apresentar o relatório e propor o BPO (roteiro em `02-playbook-comercial.md`).
- [ ] Meta: 3 contratos.

**Semanas 7 a 12: rotina e escala**
- [ ] Seguir a rotina operacional (`04-roteiro-operacional.md`).
- [ ] Pedir indicação a cada cliente satisfeito.
- [ ] Contratar o analista quando houver 4 ou 5 clientes.
- [ ] Meta: 7 clientes até o 6º mês.

## 6. Cuidados que protegem o escritório

- **Dinheiro do cliente:** o escritório **agenda** e o cliente **aprova** os pagamentos no banco. Use o perfil de
  operador sem poder de autorização. Nunca use senha de sócio.
- **Contrato escrito** com escopo, limites de lançamentos, prazos e responsabilidades (NBC PG 01, Código de Ética).
- **LGPD (Lei 13.709/2018):** o Painel processa os extratos localmente, no navegador. Defina no contrato a guarda e a
  eliminação de dados.
- **Relatório gerencial ≠ demonstração contábil:** deixe claro no relatório que ele é baseado em movimentação bancária (regime de caixa).
- **Publicidade:** informativa e sóbria, sem promessa de resultado.
