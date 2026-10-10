# Roteiro Operacional: execução de um caso de recuperação

> Confirme sempre o caminho atual dos serviços nos portais: menus e nomes mudam com frequência.

## 1. Coleta (D+0 a D+5)
- [ ] Procuração eletrônica no e-CAC e acesso ao Portal do Simples Nacional.
- [ ] XMLs de **saída** (NF-e e NFC-e) dos últimos 60 meses, incluindo os eventos de cancelamento.
  Fontes: ERP/PDV do cliente, portal da SEFAZ estadual, sistema fiscal do escritório.
- [ ] Extratos do PGDAS-D do período, que mostram o RBT12 de cada mês e se houve segregação.

## 2. Diagnóstico (D+5 a D+7)
- [ ] Abrir `app/index.html`, carregar os XMLs e informar o RBT12 dos meses sem histórico.
- [ ] Revisar os **principais produtos**: confirmar NCM e eventuais "Ex" da TIPI (atenção a mudanças de NCM em 2017 e 2022).
- [ ] Conferir NCMs com o XML de **entrada** (CST PIS/COFINS 02/04 do fornecedor é forte indício de monofásico).
- [ ] Excluir meses em que o cliente já segregava as receitas.
- [ ] Salvar o PDF e o CSV como papéis de trabalho.

## 3. Retificação (PIS/COFINS no DAS)
- [ ] No PGDAS-D, retificar cada competência segregando a receita de revenda de mercadorias
  "com tributação monofásica" de PIS/COFINS e, quando aplicável, "com substituição tributária" de ICMS.
- [ ] A retificação gera o valor pago a maior por competência.

## 4. Pedido
- [ ] **Restituição:** serviço de pedido eletrônico de restituição no Portal do Simples Nacional, por competência.
  O valor é corrigido pela Selic.
- [ ] **Compensação:** alternativa para abater débitos futuros do próprio Simples, quando for mais vantajosa ao cliente.
- [ ] **ICMS:** a parcela de ICMS do DAS segue o rito do estado (pedido à SEFAZ). Verifique a regulamentação estadual.
- [ ] Mantenha uma planilha de controle com competência, valor, número do pedido, data, situação e data do crédito.

## 5. Daqui pra frente
- [ ] Parametrizar o sistema fiscal para segregar automaticamente por NCM/CSOSN todo mês.
- [ ] Mostrar ao cliente a economia mensal e usar isso para propor revisão de honorários e serviços consultivos.

## 6. Faturamento
- [ ] Acompanhar o crédito da restituição e emitir a NFS-e do honorário de êxito na data contratual.
