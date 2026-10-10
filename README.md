# Radar Tributário: nova fonte de receita para o escritório contábil

Projeto completo para transformar a carteira do escritório em receita nova, começando pela
**recuperação de créditos do Simples Nacional** (PIS/COFINS monofásico e ICMS-ST), cobrada por êxito.

## O que tem aqui

| Pasta/arquivo | Conteúdo |
|---------------|----------|
| `app/` | **Radar Tributário**: ferramenta que lê XMLs de NF-e/NFC-e e estima o crédito a recuperar, mês a mês |
| `docs/01-plano-de-negocios.md` | 6 linhas de receita priorizadas, exemplo numérico, metas de 12 meses e plano de 90 dias |
| `docs/02-playbook-comercial.md` | Público-alvo, funil, scripts de WhatsApp e reunião, respostas a objeções |
| `docs/03-modelo-contrato-exito.md` | Modelo de contrato com honorários de êxito e cláusula LGPD |
| `docs/04-roteiro-operacional.md` | Passo a passo de execução: coleta, diagnóstico, retificação, pedido e faturamento |
| `exemplos/xml/` | XMLs fictícios de uma farmácia para testar a ferramenta |

## Como usar o Radar (sem instalar nada)

1. Abra `app/index.html` no Chrome ou Edge (duplo clique).
2. Preencha o nome do escritório, o cliente, o % de honorários e o RBT12 padrão.
3. Selecione a pasta com os XMLs de **saída** do cliente (inclua os XMLs de cancelamento).
4. Ajuste o RBT12 dos meses conforme o extrato do PGDAS-D.
5. Clique em **Imprimir / salvar PDF** para gerar o relatório que você leva para a reunião com o cliente.

Os arquivos são processados **no próprio navegador**: nenhum dado do cliente é enviado à internet.

### O que a ferramenta calcula
- Receita de venda por competência (CFOPs de venda; ignora devoluções, notas canceladas e XMLs duplicados).
- Receita de produtos monofásicos por NCM (farmacêuticos, higiene/perfumaria, autopeças, pneus,
  veículos, bebidas frias, combustíveis), com o fundamento legal de cada grupo.
- Receita com ICMS-ST (CSOSN 500, CFOP x405/x656/x667).
- RBT12 a partir dos próprios XMLs (quando há 12 meses anteriores) ou informado manualmente.
- Alíquota efetiva e partilha do Anexo I (LC 123/2006), com o crédito de PIS/COFINS e de ICMS por mês.
- Exclusão das competências prescritas (5 anos, CTN art. 168).
- Honorários de êxito estimados, além de exportação em CSV.

> A tabela de NCMs é de **triagem**. O contador responsável deve validar NCM, Ex-TIPI e as segregações
> já feitas antes de qualquer retificação.

## Para desenvolvedores

```bash
npm test            # testes automatizados (Node 18+ ou superior, sem dependências)
npm run exemplos    # regenera os XMLs de exemplo
```

Para publicar online (ex.: GitHub Pages), basta servir a pasta `app/`.
