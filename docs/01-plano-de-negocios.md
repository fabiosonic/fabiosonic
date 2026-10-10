# Plano de Negócios: do escritório "fábrica de guias" ao escritório consultivo

> Diagnóstico: a contabilidade tradicional (folha, fiscal, contábil a honorário fixo baixo) virou
> commodity. Ela é disputada pelo preço com as contabilidades online e tem margem pressionada pelo custo de pessoal.
> A saída não é abandonar a área, e sim **usar a carteira e o conhecimento técnico que você já
> tem para vender serviços de alto valor**, cobrados por resultado ou por recorrência premium.

## 1. As 6 linhas de receita, em ordem de prioridade

| # | Linha de receita | Modelo de cobrança | Ticket típico* | Tempo até o 1º real | Esforço |
|---|------------------|--------------------|----------------|---------------------|---------|
| 1 | **Recuperação de créditos do Simples** (PIS/COFINS monofásico + ICMS-ST) | Êxito: 20% a 30% do recuperado | R$ 3 mil a R$ 30 mil por cliente | 30 a 90 dias | Baixo, com o Radar Tributário |
| 2 | **Diagnóstico e transição da Reforma Tributária** (IBS/CBS, LC 214/2025) | Projeto fixo + mensalidade | R$ 1,5 mil a R$ 8 mil por projeto | 15 a 30 dias | Médio |
| 3 | **BPO financeiro** (contas a pagar/receber, conciliação, fluxo de caixa) | Mensalidade recorrente | R$ 800 a R$ 3.500/mês | 30 dias | Médio (processo) |
| 4 | **Planejamento tributário** (regime ideal, Fator R, pró-labore × distribuição) | Projeto ou % da economia do 1º ano | R$ 1,5 mil a R$ 10 mil | 15 dias | Médio |
| 5 | **Pessoa física de alta renda** (IRPF, ganho de capital, carnê-leão, holding) | Por declaração/projeto | R$ 400 a R$ 15 mil | Sazonal | Baixo/Alto |
| 6 | **Licenciar o Radar para outros escritórios** (white-label) | Assinatura ou % do êxito | R$ 197 a R$ 497/mês por escritório | 60 a 120 dias | Médio |

\* Faixas de referência de mercado; calibre com a sua região e a sua carteira.

### Por que começar pela linha 1

1. **Não exige cliente novo.** A sua carteira de comércio no Simples (farmácias, perfumarias, autopeças,
   mercados, conveniências, distribuidoras de bebidas, postos) já é o público-alvo.
2. **O cliente não tira dinheiro do bolso.** Você só recebe se ele receber. A objeção de preço desaparece.
3. **Gera caixa rápido e prova valor.** Depois de uma restituição, o cliente aceita reajuste de honorário e compra
   as linhas 2, 3 e 4.
4. **Tem prazo.** Com a substituição de PIS/COFINS pela CBS a partir de 2027, a janela de 5 anos de
   recolhimentos indevidos de PIS/COFINS no DAS começa a "fechar" mês a mês. Esse argumento de urgência é legítimo.
5. **É escalável.** O Radar Tributário (pasta `app/`) faz a triagem de anos de XML em segundos.

## 2. Exemplo numérico da linha 1

Uma farmácia no Anexo I com RBT12 de R$ 1,2 milhão (4ª faixa) e 60% da receita em produtos monofásicos:

- Alíquota efetiva: (1.200.000 × 10,7% − 22.500) ÷ 1.200.000 = **8,825%**
- Parcela de PIS + COFINS dentro do DAS: 8,825% × (2,76% + 12,74%) = **1,368% da receita monofásica**
- Receita monofásica/ano: R$ 720 mil, o que dá **≈ R$ 9.850/ano** de PIS/COFINS pago a maior
- Em 5 anos: **≈ R$ 49 mil** (mais Selic), e o ICMS-ST pode somar outro tanto
- **Honorário de êxito (20%): ≈ R$ 9,9 mil**, por um trabalho de poucos dias, além da economia mensal daqui pra frente

Com 10 clientes desse perfil no ano, são aproximadamente **R$ 100 mil de receita extra**.

## 3. Meta financeira de 12 meses (cenário conservador)

| Linha | Premissa | Receita/ano |
|-------|----------|-------------|
| Recuperação de créditos | 12 casos × R$ 6 mil de honorário médio | R$ 72.000 |
| Reforma Tributária | 15 diagnósticos × R$ 2 mil | R$ 30.000 |
| BPO financeiro | 6 clientes × R$ 1.200/mês (média de 6 meses ativos) | R$ 43.200 |
| Planejamento tributário | 8 projetos × R$ 2,5 mil | R$ 20.000 |
| IRPF premium | 40 declarações × R$ 600 | R$ 24.000 |
| **Total adicional** | | **≈ R$ 189.000** |

Custos incrementais: tempo da equipe, 1 assistente de BPO (a partir do 4º cliente), marketing (R$ 500 a R$ 1.500/mês).

## 4. Plano de 90 dias

**Semanas 1 e 2: munição**
- [ ] Listar todos os clientes do Simples com atividade de comércio (CNAE 47xx/45xx/46xx) e CRT 1.
- [ ] Baixar 5 anos de XML de saída de cada um (SEFAZ, portal da NF-e, sistema fiscal ou ERP do cliente).
- [ ] Rodar o **Radar Tributário** e ranquear a carteira por crédito estimado.
- [ ] Conferir no extrato do PGDAS-D se a segregação já é feita (se for, não há crédito).

**Semanas 3 a 6: primeiras vendas (carteira própria)**
- [ ] Reunião com os 10 clientes de maior crédito, levando o relatório impresso (veja `02-playbook-comercial.md`).
- [ ] Assinar contrato de êxito (`03-modelo-contrato-exito.md`).
- [ ] Executar os primeiros casos (`04-roteiro-operacional.md`).
- [ ] Corrigir a segregação daqui pra frente e **renegociar o honorário mensal** (o cliente agora vê o valor).

**Semanas 7 a 12: fora da carteira**
- [ ] Parcerias com representantes de distribuidoras farmacêuticas, de autopeças e de bebidas (indicação remunerada).
- [ ] Oferta "diagnóstico gratuito" para comércios de outros escritórios, com publicidade dentro das regras do CFC.
- [ ] Lançar o pacote **Reforma Tributária 2027** para toda a carteira.
- [ ] Estruturar o BPO financeiro com os clientes que já pedem "ajuda com o caixa".

## 5. Linha 2: produto "Reforma Tributária 2027"

O ano de 2026 é de teste (CBS 0,9% + IBS 0,1% destacados em nota); em 2027 a CBS entra em vigor e
PIS/COFINS são extintos. Empresários estão ansiosos e mal informados, e isso abre espaço para venda consultiva:

- **Diagnóstico (projeto fixo):** impacto na carga, na precificação e nos contratos longos; cadastro de produtos (NCM,
  cClassTrib); prontidão do ERP; para o Simples, simulação da **opção de recolher IBS/CBS fora do DAS**
  (relevante para quem vende B2B, porque transfere crédito ao comprador).
- **Acompanhamento (mensal):** revisão de notas com IBS/CBS, apuração assistida, split payment.

## 6. Linha 3: BPO financeiro (receita recorrente)

- Escopo fechado: contas a pagar/receber, conciliação bancária diária, DRE gerencial e fluxo de caixa mensal.
- Preço por volume de lançamentos (ex.: até 200/mês por R$ 900; até 500/mês por R$ 1.800).
- Margem alta porque se apoia na contabilidade que você já faz (dados conciliados viram contabilidade automática).

## 7. Conformidade (não negocie)

- **Código de Ética (NBC PG 01):** contrato escrito, publicidade sóbria e informativa, sem promessa de resultado
  ("estimativa", nunca "garantia") e sem captação desleal de clientes de colegas.
- **Honorário de êxito:** é lícito, desde que contratado por escrito, com base de cálculo e momento do pagamento definidos.
- **LGPD (Lei 13.709/2018):** o Radar processa os XMLs localmente, no navegador, sem enviar dados a servidores.
  Inclua cláusula de tratamento de dados no contrato.
- **Responsabilidade técnica:** o diagnóstico é triagem. Valide NCM a NCM antes de retificar e guarde os papéis de trabalho.
