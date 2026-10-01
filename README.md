# Emissor de NFS-e — Prefeitura de Itaboraí/RJ (webservice)

Converte RPS em NFS-e pelo webservice da prefeitura (`https://prefeituradeitaborai.online/wsnfse/`),
com tela de emissão local, linha de comando, cancelamento e as críticas da Reforma Tributária
publicadas na página **Manuais & Tabelas** do portal.

Precisa de Python 3.10 ou superior. Recomenda-se instalar `lxml` (`pip install lxml`): com ele, cada RPS é
validado contra o XSD oficial da prefeitura antes do envio.

## De onde vem o layout

A prefeitura usa o sistema Prefeitur@Rápida (provedor **CTA, versão 2.00**).

- **Estrutura do XML:** segue o **XSD oficial** da prefeitura (`schemas/webserviceNFSe.xsd`, de
  `prefeituradeitaborai.online/wsnfse/webserviceNFSe.xsd`), inclusive o bloco `InformacoesIBSCBS`.
- **Transporte, autenticação e cancelamento:** seguem a implementação de código aberto do Projeto ACBr
  (`Fontes/ACBrDFe/ACBrNFSeX/Provedores/CTA.*`).
- **Formatos conferidos com uma nota real:** desdobro `17.19.01`, `ResponsavelRecolhimento` e alíquota zero
  no Simples sem retenção foram conferidos com o retorno real da NFS-e 3385 (08/2026), aceita pelo webservice.
  O leitor de respostas é testado com esse retorno, anonimizado em `tests/dados/`.

| Item | Como funciona |
|---|---|
| Transporte | `POST` `multipart/form-data`, com o XML enviado como arquivo |
| Autenticação | sem certificado digital; `ChaveSeguranca` = Base64(SHA-256 em hexadecimal minúsculo de `CNPJ + Chave Privada + DataEmissao`) |
| Ambiente | mesma URL para os dois; `<Producao>2</Producao>` = produção, `1` = homologação |
| Itens | até 5 itens por RPS (`Servico1` a `Servico5`), descrição de até 190 caracteres |
| Cancelamento | `CancelaNfse`, com Base64(SHA-1) na chave de segurança |

## Início rápido (Windows)

1. Descompacte o pacote numa pasta, por exemplo `C:\EmissorItaborai`.
2. Dê dois cliques em **`TESTE_HOMOLOGACAO.bat`**. Ele envia um RPS de teste em homologação, sem validade
   fiscal, e grava o resultado em `resultado_teste.txt`.
3. Para usar no dia a dia, dê dois cliques em **`INICIAR.bat`**. Ele instala o que faltar e abre a tela de
   emissão.

## Instalação (Windows)

1. Instale o Python (python.org) e marque "Add Python to PATH".
2. Copie esta pasta para o computador.
3. Dê dois cliques em `configurar.bat` e responda às perguntas:
   - a **Chave Privada Webservice**, que fica no portal NFS-e, menu "Chave Privada Webservice";
   - o **próximo número de RPS** da empresa.

   O programa cria o arquivo `.env` na pasta. Esse arquivo guarda a chave e **nunca** vai para o Git (está no
   `.gitignore`). Também é possível criá-lo à mão, copiando `.env.exemplo`.
4. Dê dois cliques em `iniciar_tela.bat`. A tela abre em `http://127.0.0.1:8765`.

## Uso

**Pela tela:** preencha o tomador e os itens e clique em **Conferir XML**. Depois use
**Emitir em homologação** e, por fim, **Emitir em PRODUÇÃO**.

Item, NBS, desdobro, CNAE, alíquota e IBS/CBS vêm pré-preenchidos de `exemplos/padrao_prestador.json`, com os
dados da Moraes & Oliveira: 17.19 / NBS 113022100 / desdobro 17.19.01 / CNAE 6920601 / cIndOp 100301 /
cClassTrib 000001. Os códigos de IBS/CBS são os mesmos da NFS-e de 08/2026 da empresa.

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

## Validar o XML no portal da prefeitura

Antes do primeiro envio, confira o XML no **validador da prefeitura**:
https://prefeituradeitaborai.online/engine8.php?m=modnfse_pref_nfe_rps_pre_validar

1. Gere o XML sem enviar nada:
   `python -m nfse_itaborai conferir exemplos\rps_exemplo.json > rps.xml`
   Pela tela, o botão **Conferir XML** mostra o mesmo conteúdo.
2. Cole o conteúdo de `rps.xml` no validador.

O arquivo `exemplos/xml_para_validar.xml` já vem pronto para esse teste e passa no XSD oficial. Ele usa uma
chave fictícia, o que não afeta a validação de estrutura (XSD).

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
| IBS/CBS obrigatório: Indicador da Operação (cIndOp) e Classificação Tributária (cClassTrib) | 01/06/2026 | Nota Técnica 003 / Tabela IBS x CBS |
| Simples Nacional com ISS retido exige a alíquota efetiva do PGDAS-D | — | LC 123/2006, art. 21, § 4º |
| Limites do XSD: 5 itens, descrição de 190 caracteres, observações de 190, tamanhos de tomador e endereço; alíquota de no máximo 5% | — | XSD oficial; LC 116/2003, art. 8º, II |
| Validação completa contra o XSD oficial (com `lxml` instalado) | — | `schemas/webserviceNFSe.xsd` |

## Testes

```
pip install pytest lxml
python -m pytest
```

São 27 testes, que cobrem:
- a ordem e o conteúdo de cada campo do XML, além da validação contra o XSD oficial;
- a leitura do retorno real do webservice;
- a chave de segurança;
- os cálculos (base, ISS, líquido pela fórmula ABRASF, carga tributária);
- todas as críticas;
- a emissão e o cancelamento de ponta a ponta contra um **webservice simulado**, que recebe o multipart e
  recalcula a chave de segurança;
- a rejeição sem consumir o número do RPS;
- a trava de produção;
- a tela.

## Limitações conhecidas

- **Situação Tributária / Tipo de Retenção de PIS/COFINS/CSLL (Nota Técnica 005):** o XSD atual não tem
  esses campos. Notas **sem retenção federal**, que é o caso normal de um prestador do Simples Nacional, não
  são afetadas. Se uma nota com retenção de PIS/COFINS/CSLL for rejeitada, o erro da prefeitura aparece na
  tela e em `retorno.xml`.
- O grupo opcional `ImovelIBSCBS` (endereço do imóvel) e o grupo `Evento` do XSD ainda não são gerados.
- Erros de rejeição: o formato foi reproduzido do ACBr, e o retorno bruto fica sempre salvo em `retorno.xml`.
