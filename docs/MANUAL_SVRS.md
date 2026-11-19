# Programa que funciona com a SVRS (RJ) — NF-e 55 e NFC-e 65 de saída

O RJ é autorizado pela **SEFAZ Virtual do RS (SVRS)**. Este é o caminho da SEFAZ que entrega o
**XML completo** das notas de saída, para os **dois modelos**, usando o certificado A1 do emitente.

## O que é usado da SVRS

| Etapa | Serviço SVRS | O que entrega | Tipo |
|---|---|---|---|
| Descoberta | **NFeConsultaProtocolo 4.00** (`nfe.svrs.rs.gov.br` / `nfce.svrs.rs.gov.br`) | quais notas existem, situação, protocolo, **cancelamentos/CC-e** e numeração faltante | webservice (mTLS) |
| XML completo | **Portal DF-e SVRS — `DownloadXMLDFe`** (`dfe-portal.svrs.rs.gov.br`) | o `nfeProc` autorizado completo (55 e 65), por chave ou série/número | portal web (certificado) |

> **Importante:** não existe webservice da SEFAZ que devolva o XML completo da nota de saída ao
> emitente (a Distribuição DFe responde cStat 641; o SAE é só de SP). Por isso o XML íntegro vem do
> **Portal DF-e SVRS**. O programa **não burla CAPTCHA**: se o portal exigir "Não sou robô", ele
> para e registra isso — e o `svrs` abaixo detecta essa condição antes de qualquer tentativa.

## Verificar a SVRS com um certificado real (um comando)

No computador do escritório, com a empresa e o certificado A1 já cadastrados pelo painel:

```bat
set MOXML_HOME=%PROGRAMDATA%\MO-XML-Captador
backend\.venv\Scripts\python -m moxml svrs --empresa 1
```

O comando faz, para 55 e 65, e grava a evidência em `evidencias\svrs-<data>.json`:
1. verifica se o Portal DF-e SVRS está disponível para o modelo;
2. **inspeciona o formulário do portal e detecta se há CAPTCHA** (sem baixar nada);
3. baixa o XML completo de uma chave conhecida (a chave semente da série, ou `--chave <CHAVE>`),
   validando assinatura, chave e protocolo.

Leitura do resultado:
- `portal_captcha: false` e `download.ok: true` → **a captura automática pela SVRS funciona** para aquele modelo.
- `portal_captcha: true` → o portal exige interação humana: a captura 100% automática pela SVRS **não** é possível para aquele modelo (limitação do Fisco, não do programa).

## Operação contínua (depois de confirmado)

Nada muda no uso: o serviço já roda sozinho nos horários configurados usando exatamente estes
serviços da SVRS. Para disparar manualmente uma empresa:

```bat
backend\.venv\Scripts\python -m moxml capturar --empresa 1 --modelo 55 --modelo 65
```

Fluxo por empresa/modelo: **consulta SVRS** descobre as chaves e a situação → **Portal DF-e SVRS**
baixa o XML completo → validação → gravação (`1-CLIENTES\CLIENTES ATIVOS\...`) → auditoria de
numeração → Google Drive → pacote para o Domínio.

## Teste de aceitação (evidência por modelo)

```bat
backend\.venv\Scripts\python -m moxml teste-real --empresa 1 --chave <CHAVE_55_CONHECIDA> --autorizado-por "Nome / cargo"
backend\.venv\Scripts\python -m moxml teste-real --empresa 1 --chave <CHAVE_65_CONHECIDA> --autorizado-por "Nome / cargo"
```

Avalia os 10 critérios da seção 17 e grava `evidencias\teste_real_<cnpj>_<modelo>_<data>.json`.
Só então o modelo é declarado operacional pela SVRS.
