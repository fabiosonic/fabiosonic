# Leiaute de importação de lançamentos contábeis — formato TXT usado pelo escritório

**Status:** aprovado como leiaute oficial pelo usuário em 07/10/2026 (decisão registrada na sessão),
com base em arquivos que o escritório JÁ importou com sucesso no Domínio
(`Dominio-<empresa>-<banco>-<conta>.txt`, Google Drive do escritório, 09/2026).

## Registro (uma linha por lançamento; separador `;`; fim de linha CRLF; texto ASCII)

| # | Campo | Formato | Exemplo |
|---|---|---|---|
| 1 | Data | `DD/MM/AAAA` | `31/01/2026` |
| 2 | Conta débito | código **reduzido** do plano de contas do Domínio | `862` |
| 3 | Conta crédito | código **reduzido** | `865` |
| 4 | Valor | decimal com vírgula, sem separador de milhar, 2 casas | `5000,00` |
| 5 | Histórico | maiúsculas, sem acento, sem `;` nem quebra de linha | `RENDIMENTO DE APLICACAO - BANCO ...` |
| 6 | Constante | `1` (como nos arquivos importados) | `1` |
| 7–12 | vazios | — | `;;;;;;` |

Linha completa: `31/01/2026;862;865;5000,00;HISTORICO;1;;;;;;`

## Como o sistema usa

- Só gera o arquivo a partir de lote **APROVADO** (humano ou aprovação por exceção, se habilitada
  para `lancamento_contabil`).
- Um arquivo por lote: `Dominio-<codigo>-<apelido>-<banco>-<conta>-<competencia>-<lote>.txt`, na pasta
  `pastas.importacao_dominio` (simulação: `dados/_STAGING/IMPORTACAO_DOMINIO`). Nunca sobrescreve.
- A importação dentro do Domínio é feita pela pessoa em *Utilitários > Importação* (o Domínio não
  tem API); depois, `auditar-dominio` confere o que entrou.
- Mudou o formato no Domínio? Atualize este documento e o teste `tests/test_exportador_dominio.py`.
