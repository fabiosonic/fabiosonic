# Manual de operação

## Rotina diária (automática)
O serviço executa a captura nos horários de `MOXML_HORARIOS_EXECUCAO` (padrão 07:30, 12:30 e 19:30, horário de Brasília). Se o computador estiver desligado, a execução perdida acontece uma única vez ao religar (tolerância de 6 h). Às 06:50 o sistema confere o vencimento dos certificados.

**O operador confere todo dia, na Visão geral:**
1. **Execuções com erro**: abra em Histórico → detalhes.
2. **XMLs pendentes**: notas que existem na SEFAZ, mas cujo XML integral ainda não foi obtido.
3. **Lacunas**: números sem documento (ver abaixo).
4. **Certificados vencendo**: solicite a renovação ao cliente com 30 dias de antecedência.

## Cadastrar um cliente
1. **Empresas → Nova empresa**: razão social, CNPJ, UF, modelos (55/65) e, se a pasta no Drive tiver nome próprio, o nome exato.
2. Clique na empresa e envie:
   - **Certificado A1** (.pfx), senha, nome do responsável que autorizou e referência do termo. Marque a confirmação de autorização.
   - **XML semente**: o XML mais recente **de cada série** (NF-e e NFC-e; inclua séries de cada caixa/PDV e de contingência).
3. Opcional: em **Configurações → Pastas monitoradas**, cadastre a pasta onde o ERP/PDV do cliente grava os XMLs.
4. Use **Capturar agora** para a primeira execução.

### Modelo de termo de autorização (resumo)
> A empresa ___, CNPJ ___, autoriza MORAES E OLIVEIRA CONTABILIDADE LTDA a utilizar seu certificado digital A1 exclusivamente para consultar e obter, junto aos serviços oficiais da SEFAZ/SVRS, os documentos fiscais eletrônicos por ela emitidos (NF-e/NFC-e) e respectivos eventos, para fins de escrituração contábil e fiscal, com guarda segura do certificado e da senha. Vigência: ___. Local/data/assinatura do responsável legal.

## Recuperação histórica
Em **Capturas → Recuperação histórica**, informe empresa, modelo, série e o número a partir do qual buscar. A SEFAZ pode recusar chaves com mais de cerca de 6 meses (cStat 526). Para períodos mais antigos, importe os XMLs da pasta do emissor:
```
backend\.venv\Scripts\python -m moxml importar "\\servidor\PDV\XML\2025" --empresa 7
```

## Como interpretar as lacunas
| Classificação | O que fazer |
|---|---|
| INUTILIZADA | Nada: a faixa foi inutilizada e homologada. |
| CHAVE_CONHECIDA_XML_PENDENTE | A nota existe; aguardar novas tentativas ou pedir o XML ao cliente. |
| NAO_CONSTA_NA_SEFAZ | A SEFAZ informou que o número não consta. Verificar com o cliente se o número foi pulado, rejeitado ou se falta inutilizar. **Não é, por si, omissão de receita.** |
| LACUNA_NAO_INVESTIGADA | Aguardar a próxima execução (ainda não consultado). |

## Pendências "SEM_FONTE"
A chave é conhecida, mas nenhuma fonte disponível entregou o XML integral (ex.: portal com CAPTCHA). Peça o XML ao cliente ou cadastre a pasta do emissor. O sistema volta a tentar a cada 6 horas.

## Fechamento mensal: Domínio
1. **Integrações → Domínio**: informe ano e mês e clique em **Gerar pacotes do mês**. Os pacotes ficam em `%PROGRAMDATA%\MO-XML-Captador\exportacoes\dominio\<CNPJ>_<AAAA-MM>\`.
2. No Domínio Escrita Fiscal, use a importação de XML de NF-e/NFC-e de saída apontando para `IMPORTAR_DOMINIO\NFE_55`, `IMPORTAR_DOMINIO\NFCE_65` e `IMPORTAR_DOMINIO\EVENTOS`.
3. Confira os totais do Domínio com `conferencia_valores.csv` e os cancelamentos com `relatorio_cancelamentos.csv`.
4. Trate as linhas de `pendencias.csv` antes de encerrar a competência.

Linha de comando: `moxml exportar-dominio --ano 2026 --mes 10 [--empresa N]`.

## Google Drive
Os XMLs são enviados automaticamente após cada captura agendada (se `MOXML_GDRIVE_ATIVO=true`). Em **Integrações → Google Drive**, CONFIRMADO significa id e MD5 devolvidos pela API iguais ao arquivo local. CONFLITO significa que já existia um arquivo diferente com o mesmo nome; o novo foi enviado como `-v2`, sem sobrescrever.

## Ocorrências comuns
| Mensagem | Causa / ação |
|---|---|
| "certificado inapto: fora da validade" | Renovar o A1 do cliente. |
| "senha do certificado incorreta" | Conferir a senha com o cliente. |
| "SEFAZ sinalizou consumo indevido (656)" | O sistema suspende aquele CNPJ por 1 h automaticamente. Se for frequente, reduza os horários de execução. |
| "portal exige CAPTCHA" | O download automático não é possível pelo portal; use a pasta do emissor ou peça o XML. |
| "autorizador respondeu 562 sem concatenar a chave" | A descoberta por numeração não está disponível; dependa de chaves conhecidas ou de XMLs do emissor. |
| "nenhuma série: importe um XML semente" | Envie o XML mais recente de cada série. |
| Falha de TLS no diagnóstico | Configure `MOXML_CA_BUNDLE` (SEGURANCA.md). |
