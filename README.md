# Manuais de Emissão de Notas Fiscais 2027 — Moraes & Oliveira

Um manual por empresa cliente com notas de saída no portal: códigos atuais x códigos a partir de jan/2027 (cTribNac, NBS, CST IBS/CBS, cClassTrib), inconsistências encontradas, passo a passo de emissão, benefícios fiscais da atividade e guia da Reforma Tributária 2027.

## Arquivos

| Pasta | Conteúdo |
|---|---|
| `tools/` | Extração dos XMLs (`extrair_notas.py`), geração dos manuais (`gerar_manuais.py`) e PDF (`pdf.js`) |
| `dados/` e `manuais/` | **Somente locais** (no `.gitignore`): parecer por empresa (`dados/empresas.py`), notas extraídas, matriz de evidências e os manuais gerados. Dados de clientes não são versionados no GitHub. |

## Como regenerar

```bash
python3 tools/extrair_notas.py <pasta_com_xmls> /tmp/notas.json   # extrai campos dos XMLs
python3 tools/gerar_manuais.py                                     # gera manuais/*.html
node tools/pdf.js                                                  # converte para PDF (Playwright)
```

O parecer de cada empresa (códigos, achados e benefícios) fica em `dados/empresas.py`, que não vai para o repositório.

## Fontes

- LC 214/2025: arts. 127, 129, 130, 251, 252 e 261; Anexos II e III.
- Tabela oficial de CST e cClassTrib do IBS/CBS (Portal Nacional de DF-e, SVRS), consultada em 31/10/2026.
- LC 116/2003, NBS, LC 123/2006 e leiaute da NFS-e Nacional.
