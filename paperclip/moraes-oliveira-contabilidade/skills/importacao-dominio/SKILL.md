---
name: importacao-dominio
description: >
  Padrões para gerar arquivos de importação (lançamentos contábeis, notas, folha) para o sistema
  contábil do escritório (Domínio ou outro), a partir de planilhas, OFX e XMLs. Use quando uma tarefa
  terminar em "importar no sistema".
---

# Importação para o sistema contábil

O layout exato depende da configuração do sistema do escritório. O **engenheiro-automacao** mantém
os layouts aprovados em `references/` desta skill. Enquanto não houver layout aprovado, entregue uma
planilha padronizada (abaixo), e não um arquivo de importação.

## Planilha padrão de lançamentos

| Data | Conta débito | Conta crédito | Valor | Código histórico | Complemento | Documento | Centro de custo |

## Regras

- Valores com 2 casas decimais e ponto ou vírgula conforme o layout. Datas em DD/MM/AAAA.
- Contas pelo **código reduzido** do plano do cliente; conta inexistente = pendência, nunca crie conta.
- Um lote por cliente e competência, com totais de débito e crédito iguais.
- Gere também um resumo de conferência (quantidade de lançamentos e total) para o humano validar após importar.
- A importação no sistema é feita **por humano**. O agente só gera o arquivo.
