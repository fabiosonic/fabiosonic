# Emissor de NFS-e — Prefeitura de Itaboraí/RJ (webservice)

Converte RPS em NFS-e pelo webservice da prefeitura (`https://prefeituradeitaborai.online/wsnfse/`),
com tela de emissão local, linha de comando, cancelamento e as críticas da Reforma Tributária
publicadas na página **Manuais & Tabelas** do portal.

Não depende de nenhuma biblioteca externa: precisa só de Python 3.10 ou superior.

## De onde vem o layout

A prefeitura usa o sistema Prefeitur@Rápida (provedor **CTA, versão 2.00**). O layout foi reproduzido da
implementação de código aberto do Projeto ACBr (`Fontes/ACBrDFe/ACBrNFSeX/Provedores/CTA.*`), que está em
produção em vários emissores do mercado. Ela inclui a correção de **29/09/2026 (ACBR-9690)**, feita depois que
o XSD de Itaboraí rejeitou o RPS: `CodigoNbs` e `CodigoLsnDesdobro` passaram a vir antes de
`ClassificacaoCNAE`.

| Item | Como funciona |
|---|---|
| Transporte | `POST` `multipart/form-data`, com o XML enviado como arquivo |
| Autenticação | sem certificado digital; `ChaveSeguranca` = Base64(SHA-256 em hexadecimal minúsculo de `CNPJ + Chave Privada + DataEmissao`) |
| Ambiente | mesma URL para os dois; `<Producao>2</Producao>` = produção, `1` = homologação |
| Itens | até 5 itens por RPS (`Servico1` a `Servico5`), descrição de até 60 caracteres |
| Cancelamento | `CancelaNfse`, com Base64(SHA-1) na chave de segurança |

## Instalação (Windows)

1. Instale o Python (python.org) e marque "Add Python to PATH".
2. Copie esta pasta para o computador.
3. Copie `.env.exemplo` para `.env` e preencha:
   - `ITABORAI_CHAVE`: no portal NFS-e, menu **Chave Privada Webservice**;
   - `ITABORAI_PROXIMO_RPS`: o próximo número da sequência de RPS da empresa.

   O arquivo `.env` guarda a chave e **nunca** vai para o Git (está no `.gitignore`).
4. Dê dois cliques em `iniciar_tela.bat`. A tela abre em `http://127.0.0.1:8765`.

## Uso

**Pela tela:** preencha o tomador e os itens e clique em **Conferir XML**. Depois use
**Emitir em homologação** e, por fim, **Emitir em PRODUÇÃO**. Item, NBS, desdobro, CNAE e alíquota vêm
pré-preenchidos de `exemplos/padrao_prestador.json`, configurado com os dados da Moraes & Oliveira:
17.19 / NBS 113022100 / desdobro 171901 / CNAE 6920601.

**Pela linha de comando:**

```
python -m nfse_itaborai conferir exemplos\rps_exemplo.json      # valida e mostra o XML, não envia
python -m nfse_itaborai emitir   exemplos\rps_exemplo.json      # envia em homologação
python -m nfse_itaborai emitir   exemplos\rps_exemplo.json --producao
python -m nfse_itaborai cancelar 202600099003740 "Valor informado incorretamente" --producao
```

Cada envio grava em `saida\AAAA-MM\RPS_<n>\`:
- `envio.xml`;
- `retorno.xml`;
- `NFSe_<numero>.xml`;
- `resumo.json`.

O número do RPS só avança quando ele vira NFS-e. Se o RPS for rejeitado, o mesmo número é reaproveitado
na correção.

## Trava de produção

A prefeitura avisa: **depois que a emissão pelo webservice começa, não é mais possível emitir notas
manualmente, e isso é irreversível.** Por isso a produção só funciona quando três condições são atendidas:
1. `ITABORAI_AMBIENTE=producao` no `.env`;
2. `ITABORAI_CIENTE_IRREVERSIVEL=SIM` no `.env`;
3. `--producao` na linha de comando, ou o botão vermelho com confirmação na tela.

## Críticas feitas antes do envio

| Regra | Vigência | Fonte |
|---|---|---|
| NBS obrigatório (9 dígitos), de acordo com a Tabela 116 × NBS | 01/01/2026 | página Manuais & Tabelas |
| Desdobro obrigatório (6 dígitos), compatível com o item da LC 116 | 01/01/2026 | Lista de Serviços Nacional |
| Desdobros 141403 e 141404 exigem o código da obra cadastrada | 01/06/2026 | Nota Técnica 004 |
| Retenção de PIS/COFINS/CSLL gera alerta (Situação Tributária / Tipo de Retenção) | 01/06/2026 | Nota Técnica 005 |
| Item 03.01 gera alerta para conferir o NBS atualizado | 01/05/2026 | Nota Técnica 006 |
| Limites do layout: 5 itens, descrição de 60 caracteres, observações de 190, alíquota de no máximo 5% (LC 116/2003, art. 8º, II) | — | layout CTA |

## Testes

```
pip install pytest
python -m pytest
```

São 23 testes, que cobrem:
- a ordem e o conteúdo de cada campo do XML;
- a chave de segurança;
- os cálculos (base, ISS, líquido pela fórmula ABRASF, carga tributária);
- todas as críticas;
- a emissão e o cancelamento de ponta a ponta contra um **webservice simulado**, que recebe o multipart e
  recalcula a chave de segurança;
- a rejeição sem consumir o número do RPS;
- a trava de produção;
- a tela.

## Limitações conhecidas

- **IBS/CBS (Nota Técnica 003)** e **Situação Tributária / Tipo de Retenção de PIS/COFINS/CSLL (Nota Técnica
  005):** o layout público do provedor ainda não traz esses campos. Notas **sem retenção federal**, que é o
  caso normal de um prestador do Simples Nacional, saem normalmente. Se uma nota com retenção de
  PIS/COFINS/CSLL for rejeitada, o erro da prefeitura aparece na tela e em `retorno.xml`. Basta enviar o PDF
  das Notas Técnicas 003 e 005 para incluir esses campos.
- O formato exato da resposta foi reproduzido da leitura que o ACBr faz do retorno, e o leitor aceita as
  variações conhecidas: XML, XML escapado ou texto puro. O retorno bruto fica sempre salvo em `retorno.xml`.
