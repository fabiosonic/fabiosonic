# Relatório de testes reais

**Status em 19/11/2026: NÃO EXECUTADO.**

O ambiente de desenvolvimento não tem nenhum certificado A1 de cliente nem autorização de uso. Por regra do projeto, nenhuma chamada fiscal foi feita, e **nenhuma recuperação real de XML é declarada**.

## Observações reais (sem certificado de cliente)

| Data | Alvo | Observação | Evidência |
|---|---|---|---|
| 19/11/2026 | `https://dfe-portal.svrs.rs.gov.br/NFESSL/DownloadXMLDFe` e `/NFCESSL/DownloadXMLDFe` | Redirecionam para `/Erro/Forbidden`: "Esta consulta exige Certificado Digital emitido por autoridade certificadora (AC) credenciada junto ao ICP-Brasil." | Acesso HTTP direto (página pública) |
| 19/11/2026 | `https://portal.fazenda.rj.gov.br/dfe/` | Bloqueio por reputação de IP (ambiente de nuvem) | Acesso HTTP direto |
| 19/11/2026 | NT SAE-NFC-e (SP) + XSD | Baixados do portal da SEFAZ-SP e arquivados em `backend/moxml/sefaz/schemas/sae/` | — |
| 19/11/2026 | MOC NFeConsultaProtocolo (regras J01 a J06) | Regra J04 com concatenação opcional da chave existente (NT 2010.007) | moc.sped.fazenda.pr.gov.br |

## Roteiro a preencher no piloto (um bloco por modelo)

```
Empresa (CNPJ):            Modelo: 55 | 65          Data:
Autorizado por / termo:
Arquivo de evidência:      evidencias/teste_real_....json
Critério 1  fonte identificada .......... OK/FALHA
Critério 2  acesso autorizado ........... 
Critério 3  autenticação (cStat) ........ 
Critério 4  descoberta J04/562 .......... (OK / IMPOSSIVEL_PELO_METODO)
Critério 5  XML autorizado recuperado ... (portal: CAPTCHA? sim/não)
Critério 6  conteúdo validado ........... (assinatura íntegra?)
Critério 7  armazenado .................. 
Critério 8  repetível ................... 
Critério 9  sem duplicidade ............. 
Critério 10 execução automática ......... 
Conclusão: operacional / não operacional — motivo:
```
