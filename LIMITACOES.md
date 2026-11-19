# Limitações e pendências

Situação em 19/11/2026. O sistema **não é declarado operacional** para nenhuma UF/modelo, porque ainda não houve recuperação real de XML autorizado com certificado de cliente.

## Bloqueios que dependem do escritório

| # | Pendência | Dependência | Como resolver |
|---|---|---|---|
| B1 | Teste real NF-e 55 RJ | certificado A1 autorizado + 1 chave real conhecida | `moxml teste-real` (TESTES.md) |
| B2 | Teste real NFC-e 65 RJ | idem, com NFC-e. Avaliado **separadamente** do 55 | idem |
| B3 | Estrutura do formulário do Portal DF-e SVRS e existência de CAPTCHA/gov.br | A1 autorizado | `windows\diagnostico.bat <id_empresa>` grava a estrutura (sem valores) em `evidencias\` |
| B4 | Google Drive | credencial (conta de serviço ou OAuth) + id da pasta "MORAES & OLIVEIRA CONTABILIDADE" | MANUAL_INSTALACAO.md §5 |
| B5 | Cadeia ICP-Brasil para TLS do SVRS, se o Windows não a reconhecer | download no ITI | SEGURANCA.md / `MOXML_CA_BUNDLE` |
| B6 | Conector comercial (API Simples) | contrato, chave da conta e análise de LGPD | permanece **desligado** |

## Riscos técnicos conhecidos

1. **Concatenação da chave na rejeição 562 é "opcional" no MOC.** Se a SVRS não a fizer, a descoberta por numeração fica IMPOSSÍVEL PELO MÉTODO. O sistema detecta e registra isso (`DescobertaImpossivel`) e passa a depender de chaves vindas de outras fontes (pasta do emissor, cadastro manual).
2. **Portal SVRS pode exigir CAPTCHA ou login gov.br.** Nesse caso o download automático é IMPOSSÍVEL PELO MÉTODO (o sistema não contorna). Restariam:
   - (a) a pasta do emissor do cliente;
   - (b) o conector comercial opcional;
   - (c) a descoberta J04/562, que continua entregando chave, situação, protocolo e eventos, e permite cobrar do cliente os XMLs faltantes com precisão.
3. **Limites de consulta da SVRS não são publicados em números.** Os valores locais (30/min nos webservices, 12/min no portal) são conservadores. Com cerca de 110 empresas e alto volume de NFC-e, calibrar após o teste real. O bloqueio automático por 656 é de 1 h.
4. **Retroatividade:** chaves com AAMM superior a 6 meses podem ser recusadas (J02k/526). A recuperação histórica pela SEFAZ fica limitada a cerca de 6 meses. Para períodos anteriores, só a pasta do emissor.
5. **Disponibilidade defasada:** relatos de fornecedores indicam latência de dias para algumas fontes do RJ. O sistema re-tenta pendências a cada 6 h, sem limite de dias.
6. **Validação XSD:** feita com o pacote oficial PL_010g. Divergências viram **aviso** (não rejeição), porque XMLs autorizados podem ter sido validados por pacote de outra versão (ex.: grupos da Reforma Tributária). A integridade é garantida pela verificação criptográfica da assinatura.
7. **Assinatura:** confere DigestValue e SignatureValue. **Não** valida a cadeia ICP-Brasil do certificado do emitente nem o `digVal`/assinatura do protocolo.
8. **Eventos via SAE-SP** vêm sem `retEvento` (formato simplificado da NT). Ficam com o protocolo informado, marcados como evento sem protocolo completo.
9. **Domínio:** a importação direta não foi validada. Entrega-se um pacote de XMLs originais para a rotina de importação do Escrita Fiscal. Validar o procedimento com a equipe (pasta plana por modelo, empresa identificada pelo CNPJ do XML) e ajustar a estrutura se necessário.
10. **Ambiente de desenvolvimento:** os testes rodaram em Linux com Python 3.14.6. **Não foram executados em Windows** nem com PostgreSQL real. Os scripts `.bat`/PowerShell foram revisados, mas não executados. Primeira instalação assistida recomendada (PLANO_IMPLANTACAO.md).
11. **SQLite com paralelismo 4:** adequado para homologação. Para 110 empresas em produção, recomenda-se PostgreSQL.
12. **Inutilizações:** só são conhecidas quando o XML `procInutNFe` chega pela pasta do emissor. Não há serviço oficial de consulta de inutilizações por faixa.
13. **Portal SEFAZ-RJ** bloqueou o IP do ambiente de nuvem usado no desenvolvimento. As informações do manual RJ foram lidas por cópia pública e devem ser reconferidas a partir do escritório.

## Fora do escopo desta entrega

- Integração direta (API) com o Domínio.
- UFs além de RJ (SP: conector SAE pronto, não testado).
- Uso de autXML e do Fisco Fácil: **vetados** pelo escritório.
