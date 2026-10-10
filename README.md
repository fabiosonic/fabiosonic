# Painel Financeiro: BPO financeiro para o escritório contábil

Projeto completo para o escritório gerar receita recorrente com **BPO financeiro**: cuidar da rotina financeira
dos clientes e entregar todo mês um relatório gerencial (DRE, fluxo de caixa, ponto de equilíbrio e alertas).
Sem exposição fiscal: é gestão, não envolve pedidos ao Fisco.

## O que tem aqui

| Pasta/arquivo | Conteúdo |
|---------------|----------|
| `app/` | **Painel Financeiro**: lê extratos OFX/CSV, categoriza os lançamentos e gera DRE gerencial, fluxo de caixa e alertas |
| `docs/01-plano-de-negocios.md` | Proposta, planos e preços, projeção de 12 meses e plano de 90 dias |
| `docs/02-playbook-comercial.md` | Cliente ideal, funil, scripts de WhatsApp e reunião, respostas a objeções |
| `docs/03-modelo-contrato-bpo.md` | Modelo de contrato de BPO (sem poder de aprovação de pagamentos e com cláusula LGPD) |
| `docs/04-roteiro-operacional.md` | Implantação, rotina diária, semanal e mensal, padrão de qualidade e segurança |
| `exemplos/extratos/` | Extratos fictícios de uma padaria (OFX e CSV) para testar |

## Como usar o Painel (sem instalar nada)

1. Abra `app/index.html` no Chrome ou Edge (duplo clique).
2. Preencha o nome do escritório e do cliente.
3. Selecione os extratos (OFX ou CSV) de todas as contas, de um ou vários meses.
4. Classifique os lançamentos marcados em amarelo. Com a opção "lembrar" marcada, a regra vale para os próximos meses.
5. Clique em **Imprimir / salvar PDF** para gerar o relatório do cliente e em **Exportar lançamentos** para alimentar a contabilidade.

Os arquivos são processados **no próprio navegador**: nenhum dado bancário é enviado à internet.

### O que o Painel faz
- Lê OFX (Itaú, Bradesco, BB, Caixa, Santander, Inter, etc.) e CSV em formato brasileiro, inclusive com colunas separadas de crédito e débito.
- Junta várias contas e meses, ignorando lançamentos duplicados.
- Classifica automaticamente por histórico (maquininhas, PIX, DAS, folha, aluguel, energia, tarifas, empréstimos, etc.) e trata transferências entre contas como neutras.
- Monta o DRE gerencial mensal: receita, impostos, fornecedores, despesas, resultado operacional, margem, movimentos não operacionais e geração de caixa.
- Calcula indicadores: margem de contribuição, ponto de equilíbrio e peso da folha e dos juros.
- Gera alertas para a reunião: retiradas maiores que o lucro, mês negativo, juros e tarifas altos, lançamentos pendentes.

## Para desenvolvedores

```bash
npm test            # testes automatizados (Node 18 ou superior, sem dependências)
npm run exemplos    # regenera os extratos de exemplo
```

Para publicar online (ex.: GitHub Pages), basta servir a pasta `app/`.
