# Portal M&O: lacunas de conciliação bancária frente ao mercado

> Data: 07/11/2026. Compara as funções divulgadas pelos conciliadores do mercado (Ottimizza MAR.IA/LUZ.IA,
> Kobana, Kamino, Equals, Alterdata eEscriture/Concilia Fácil, Calima, Senior, Omie) com o que já existe
> nos módulos do Portal M&O. **Fonte das funções de mercado:** sites e centrais de ajuda dos próprios
> fornecedores e o B2B Stack. São alegações de fornecedor e não foram testadas.

## 1. O que o Portal M&O já tem (por branch)

| Módulo | Branch | Funções de conciliação já entregues |
|---|---|---|
| `mo_dominio ofx` | `ccr-c017300d-athtiq` | OFX → TXT para o Domínio; de-para por texto/regex e sentido D/C; a primeira regra que casa vence; o que não casa vai para a transitória + `pendencias.csv`; descarta FITID duplicado e valor zero; resumo do movimento × saldo final do OFX |
| `mo_openfinance` | `ccr-9d3366df-e5sxyy` | Extrato via Open Finance (TecnoSpeed/Pluggy); gravação idempotente; exclusão na origem vira estorno; classificação por CPF/CNPJ da contraparte (conta própria, sócio, cliente/fornecedor); desdobramento do boleto (juros, multa, desconto); fechamento só em D+7; link de consentimento por WhatsApp; fatura de cartão de crédito na fase 4; MCP na fase 5 |
| Painel Financeiro (BPO) | `ccr-891ac829-bi1anz` | OFX e CSV, várias contas e meses, deduplicação, classificação por histórico com "lembrar regra", transferências neutras, DRE gerencial, alertas |
| Monitor de Obrigações | `ccr-80dc22dc-51a6xx` | Obrigação DOC_EXTRATOS, baixa automática quando o extrato chega ao Drive, cobrança do cliente, trilha de `Evento` |
| Estudo Portal × Domínio | `ccr-7e424757-epryy7` | *Planejado:* conciliação tripla Portal × Domínio × ADN/SEFAZ e aceite "saldo do banco no balancete = saldo do extrato" |

## 2. Funções do mercado que o Portal ainda não tem

Prioridade: **A** = alto ganho, já com base pronta no Portal; **B** = alto ganho, exige módulo novo; **C** = desejável.

| # | Função | Quem oferece | Situação no Portal | Prioridade |
|---|---|---|---|---|
| 1 | **Conciliar extrato × razão contábil já escriturado**: aponta diferenças, agrupa o que foi conciliado e lista as divergências | Ottimizza MAR.IA | Só **gera** lançamentos. Não confere o razão do Domínio contra o extrato (a conciliação tripla está só no estudo) | **A** |
| 2 | **Extrato em PDF** (e XLSX/XLS) como entrada | Ottimizza (pdf, ofx, xlsx, xls), Alterdata eEscriture, Calima Pro, Escritório Inteligente | Aceita só OFX/CSV | **A** |
| 3 | **Conciliação de clientes e fornecedores** (contas a receber/pagar × baixas no banco) | Ottimizza LUZ.IA, Kobana | Não existe. O risco de duplicar receita fiscal × financeiro já está apontado no estudo | **A** |
| 4 | **Casamento N:1 e 1:N** (um PIX quitando várias notas, um pagamento em lote com vários títulos) | Ottimizza ("agrupa lançamentos"), Kobana (pagamento parcial). A Omie **não** tem, então é um diferencial | O casamento é 1:1 por regra de texto/CNPJ | **A** |
| 5 | **Tolerância de data e valor** no casamento (D±n, diferença de centavos e tarifas) | Senior (data + valor ou documento + valor), AntecipaFácil (tolerâncias e janelas) | Casamento exato, ou só por texto | **B** |
| 6 | **Conciliação de cartões/adquirência**: venda × repasse da adquirente × crédito no banco; MDR contratado × cobrado; cancelamentos, chargeback, antecipação | Equals (dois assistentes de IA: divergências do dia e taxa contratada × cobrada), Concil, Conciliadora, Confere, Sitef; a Questor usa a Equals | Só a fatura de cartão de crédito da própria empresa (fase 4). Não trata a adquirência | **B** |
| 7 | **Retorno CNAB 240/400 e conciliação de cobranças emitidas** (boleto e boleto híbrido com PIX, baixa automática, pagamento parcial) | Kobana | Não lê CNAB | **B** |
| 8 | **Painel "divergências do dia"** por analista e empresa, com ação em um clique | Equals, Ottimizza (status por agente) | As pendências saem em CSV. O painel de pendências (`ccr-98ea483b`) não tem categoria de conciliação | **A** |
| 9 | **Cliente responde a pendência no portal**: "o que é este PIX?", com anexo de comprovante ou nota | BPOs/Nibo (portal do cliente; função de anexo não confirmada) | O portal cobra o cliente, mas ele não consegue **responder** o item | **A** |
| 10 | **Sugestão com IA e grau de confiança** (o analista aceita, e a sugestão vira regra) | Ottimizza, Kobana ("IA nativa") | Decisão de projeto: **não adivinhar**. A sugestão manteria isso, porque ninguém lança sem aprovação | **B** |
| 11 | **Detecção de erros e fraudes**: duplicidade entre contas, fornecedor novo, valor fora do padrão, pagamento em fim de semana, PIX para CPF de sócio | Kamino ("Detecção de Erros e Fraudes") | Só duplicidade por FITID; o sócio vira pendência | **B** |
| 12 | **Relatório formal de conciliação** em PDF por conta e mês (saldo do extrato, saldo contábil, itens em aberto, responsável e data), como papel de trabalho e evidência (ITG 2000, NBC TA 500) | BlackLine / Oracle ARC (enterprise); Kobana exporta CSV/PDF/OFX | Só o resumo no terminal e o `Evento` | **A** |
| 13 | **Continuidade do extrato**: buraco de datas, saldo inicial ≠ saldo final anterior, conta sem extrato no mês | Comum nos ERPs | Não é verificado | **A** |
| 14 | **Receita × documentos fiscais**: crédito recebido × NF-e/NFS-e emitida (CNPJ do tomador e valor); alerta de **omissão de receita** e de nota não recebida | Não encontrado pronto no mercado. É **diferencial** com peças que o Portal já tem (XML em `mo_dominio matriz`) | As peças existem, mas não estão ligadas | **A** |
| 15 | **Assistente conversacional** ("saldo e pendências da empresa X") | Ottimizza (bot com escalonamento humano), TecnoSpeed (MCP) | Previsto na fase 5 do Open Finance | **C** |
| 16 | **Exportação multiformato** (CSV/PDF/OFX além do TXT do Domínio) | Kobana | Só TXT | **C** |

## 3. Pontos de atenção técnico-contábeis

- **Competência × caixa (NBC TG Estrutura Conceitual / CPC 00):** nas itens 3 e 14, o crédito no banco
  **baixa** o contas a receber gerado pela nota e **não cria receita**. O casamento tem de procurar o título
  em aberto antes de cair na regra de receita.
- **Split payment (LC 214/2025):** a partir da implantação do recolhimento na liquidação, o crédito chega
  líquido de IBS/CBS. Os itens 4, 5 e 14 precisam aceitar a diferença "valor da nota − tributo retido no split"
  como casamento válido e lançar o tributo na conta própria.
- **Cartões (item 6):** a receita bruta é a venda e o MDR é despesa financeira. Conciliar só o crédito líquido
  subavalia a receita, o que distorce a base do Simples e do Presumido.
- **LGPD:** PDF e comprovantes do cliente (itens 2 e 9) contêm dados de terceiros. O processamento deve ficar
  no ambiente do escritório, ou com operador sob DPA, como já previsto no plano de Open Finance.

## 4. Sequência sugerida

1. **Onda 1 (com base pronta):** 13 continuidade → 1 extrato × razão → 12 relatório de conciliação → 8 painel.
2. **Onda 2:** 2 leitor de PDF/XLSX → 9 resposta do cliente → 4 casamento N:1 → 3 clientes/fornecedores → 14 receita × notas.
3. **Onda 3:** 5 tolerâncias → 10 sugestões com IA → 11 alertas de fraude → 7 CNAB → 6 cartões (ou integração com Equals/Concil em vez de construir).

## Fontes

- [Ottimizza – funcionalidades MAR.IA/LUZ.IA](https://ajuda.ottimizza.com.br/books/ia-ottimizza/page/funcionalidades-maria/export/pdf)
- [Kobana – conciliação bancária](https://www.kobana.com.br/en/features/bank-reconciliation/) e [recebíveis](https://www.kobana.com.br/en/features/receivables/)
- [B2B Stack – Kamino](https://www.b2bstack.com.br/product/kamino/funcionalidades)
- [Jornal Contábil – plataforma de conciliação de cartões (Equals)](https://jornalcontabil.com.br/noticia/plataforma-de-conciliacao-de-cartoes/)
- [Questor – conciliação de cartão](https://docs.questor.com.br/Produtos/GestãoContábilCloud/Contabilidade/conciliacao-cartao)
- [Alterdata – eEscriture (PDF)](https://ajuda.alterdata.com.br/prosoftcontabil/c1686-importacao-excel-do-eescriture-198914741.html) e [Concilia Fácil](https://ajuda.alterdata.com.br/bdcc/concilia-facil-tudo-que-voce-precisa-saber-sobre-a-conciliacao-automatica-de-lancamentos-224467529.html)
- [Senior – extrato e conciliação](https://documentacao.senior.com.br/gestaoempresarialerp/5.10.3/manual-processos/financas/gestao-de-tesouraria/extrato-e-conciliacao-bancaria.htm)
- [Omie – perguntas frequentes da conciliação](https://ajuda.omie.com.br/pt-BR/articles/6812438-perguntas-frequentes-conciliacao-bancaria)
- [Calima – importação de extrato OFX/PDF](https://ajuda.calimaerp.com/pt/article/como-realizar-a-importacao-de-extrato-formato-ofxpdf-no-modulo-contabil-703n6y/)
