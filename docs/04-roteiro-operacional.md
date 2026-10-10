# Roteiro Operacional: rotina do BPO Financeiro

## Implantação (primeiras 2 semanas do cliente)
- [ ] Contrato assinado e taxa de implantação recebida.
- [ ] Lista de todas as contas bancárias, maquininhas e carteiras digitais da empresa (Anexo I do contrato).
- [ ] Perfil de **operador** (agendar sem aprovar) e/ou perfil de consulta em cada banco.
- [ ] Separar as contas pessoais dos sócios: retiradas passam a ser feitas como pró-labore ou distribuição de lucros, em data fixa.
- [ ] Carregar 3 a 6 meses de extratos no Painel e classificar os lançamentos pendentes. As regras ficam salvas para os meses seguintes.
- [ ] Combinar o canal de envio dos boletos (e-mail ou pasta compartilhada exclusiva do cliente).
- [ ] Agendar a primeira reunião de resultado.

## Rotina diária (15 a 30 minutos por cliente)
- [ ] Baixar os extratos (OFX) e conferir as entradas do dia.
- [ ] Agendar os pagamentos que vencem nos próximos 2 dias úteis e avisar o cliente para aprovar.
- [ ] Registrar os recebimentos e identificar os clientes inadimplentes (plano Gestão ou superior).

## Rotina semanal
- [ ] Projeção de caixa das próximas 4 semanas e aviso ao cliente sobre qualquer dia com saldo previsto negativo.
- [ ] Cobrança dos títulos vencidos (plano Gestão ou superior).

## Fechamento mensal (até o dia 10)
1. Carregar todos os extratos do mês no Painel (`app/index.html`).
2. Zerar os lançamentos "a classificar". Pergunte ao cliente o que não for possível identificar.
3. Conferir se o **saldo final do extrato** bate com o saldo do banco em todas as contas.
4. Revisar os alertas: retiradas maiores que o resultado, mês negativo, juros e tarifas, peso da folha.
5. Salvar o PDF ("Imprimir / salvar PDF") e o CSV dos lançamentos. O CSV alimenta a contabilidade e reduz o retrabalho no fechamento contábil.
6. Escrever 3 recomendações objetivas no e-mail de envio, por exemplo: "renegociar a taxa da maquininha", "fixar o pró-labore em R$ X".
7. Fazer a reunião (mensal ou trimestral, conforme o plano).

## Padrão de qualidade
| Indicador | Meta |
|-----------|------|
| Relatório entregue até o dia 10 | 100% dos clientes |
| Lançamentos a classificar no fechamento | 0 |
| Pagamento perdido por falha do escritório | 0 |
| Diferença entre o saldo do extrato e o saldo do banco | R$ 0,00 |

## Segurança
- Senhas guardadas em gerenciador de senhas, com acesso individual por analista, nunca em planilha.
- Escritório sem poder de aprovação de pagamentos (contrato, cláusula 3).
- Extratos em pasta por cliente, com acesso restrito, apagados conforme o prazo do contrato.
