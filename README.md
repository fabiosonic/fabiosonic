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
2. Dê dois cliques em **`INSTALAR.bat`** (uma única vez). Ele deixa tudo automático:
   - o robô financeiro roda **de hora em hora** pelo Agendador do Windows, mesmo com o sistema fechado;
   - o sistema **abre sozinho ao ligar o computador**;
   - cria um atalho na área de trabalho.
3. No primeiro acesso, em **Configurações**:
   - informe a chave PIX, o e-mail (SMTP) e o e-mail que recebe o **resumo diário**;
   - opcionalmente, configure o WhatsApp automático (Z-API ou Evolution API).
4. Em **Contratos**, clique em **Confirmar todos** os contratos que o robô detectou nas suas notas.

Para desligar a automação, use `DESINSTALAR_AUTOMACAO.bat`. Seus dados são mantidos.

## O sistema

| Menu | O que faz |
|---|---|
| **Painel** | Mostra os indicadores principais: faturado, recebido, a receber, em atraso, % de inadimplência, MRR, a pagar e RBT12 com a alíquota estimada do DAS. Também traz o gráfico de 12 meses, os alertas, os maiores devedores e os vencimentos da semana. |
| **Emitir nota** | Escolha o cliente e o valor e clique em emitir. A nota já gera a conta a receber, com PIX ou boleto, e entra na régua de cobrança. |
| **Emitir em lote** | Marque os clientes; o valor vem da última nota. |
| **Contas a receber** | Filtros: a receber, atrasados, pagos, sem NFS-e e cancelados. Mostra o valor atualizado com multa e juros. Ações: baixar, cobrar (e-mail ou WhatsApp), emitir NFS-e, cancelar (cancela também a NFS-e na prefeitura) e estornar. Exporta para CSV. |
| **Contratos** | Honorários recorrentes, com dia de vencimento, vigência, reajuste anual automático (% e mês) e NFS-e automática. O botão **Criar a partir do histórico** monta a carteira inteira em um clique, com o valor da última nota de cada cliente. |
| **Cobrança** | Régua automática, por padrão em −3, 0, +1, +5, +15 e +30 dias. O e-mail sai sozinho. O WhatsApp fica numa fila: um clique abre a conversa com a mensagem pronta. Também mostra o histórico de envios. |
| **Contas a pagar** | Despesas por categoria, com lançamento recorrente todo mês. |
| **Conciliação** | Importa o extrato OFX do banco. Os recebimentos casam pelo identificador do PIX, pelo nome ou CNPJ do cliente ou pelo valor, e a baixa é automática. Se o mesmo cliente tem vários títulos de mesmo valor, quita o mais antigo. Os pagamentos casam com as contas a pagar. |
| **Relatórios** | Aging de inadimplência, ranking por cliente com score de pagamento (0–100), fluxo de caixa projetado para 90 dias, DRE gerencial mensal e log do sistema. |
| **Configurações** | Robô, chave PIX, Asaas, multa e juros, régua, e-mail (SMTP) e categorias de despesa. |

**O que o robô faz sozinho, a cada hora** (vem ligado; cada item pode ser desligado em Configurações):

| Etapa | Automação |
|---|---|
| XML das notas | Lê a pasta de XML: atualiza clientes; notas emitidas **fora do sistema** (Nitrus, portal) viram contas a receber; cliente com nota de mesmo valor em 3 dos últimos 4 meses vira **contrato detectado**. |
| Contatos | Completa e-mail e telefone dos clientes pela Receita (BrasilAPI). |
| Recorrência | Gera os títulos dos contratos confirmados (contrato detectado só cobra depois de confirmado, em um clique). |
| NFS-e | Emite as notas pendentes (só em produção). Falha de rede volta para a fila; recusa da prefeitura vai para revisão. Cada título é reservado antes do envio, o que impede emissão em dobro. |
| Cobrança | Cria o PIX/boleto e roda a régua por e-mail e WhatsApp (automático com Z-API ou Evolution). |
| Baixas | Asaas (consulta de status) e **extratos .ofx que aparecerem na pasta Downloads**, importados sozinhos. |
| Despesas | Débitos do extrato sem conta a pagar viram despesa paga, classificada por regra ("DAS" vai para Impostos, "TARIFA" para Bancárias...). |
| Resumo | E-mail diário para você: recebidos, atrasos, NFS-e com erro e contratos a confirmar. |
| Segurança | Backup diário do banco e trava para nunca rodar dois robôs ao mesmo tempo. |

**Robô financeiro** (Configurações > Robô ligado). Roda ao abrir o sistema, a cada hora e todo dia pelo
agendador. Em ordem, ele:
1. faz o backup;
2. lança as despesas recorrentes;
3. gera os títulos dos contratos;
4. **emite as NFS-e** (só em produção);
5. cria o PIX ou o boleto;
6. dá baixa pelo Asaas;
7. roda a régua de cobrança.

Cada etapa é independente: um erro em uma não para as outras e fica registrado no log. Notas de teste e notas
com erro nunca entram na régua.

**Meios de cobrança**
- **PIX copia e cola próprio** (padrão): sem tarifa. O identificador do título vai no PIX e a baixa sai pela
  conciliação do extrato.
- **Asaas**: boleto e PIX com baixa automática. Basta informar a chave da API em Configurações.

**Regras tributárias usadas**
- **DAS estimado:** alíquota efetiva do Anexo III da LC 123/2006 calculada sobre o RBT12 de cada mês. Escritório
  contábil recolhe ISS em valor fixo (art. 18, § 22-A), então a parcela do ISS sai da estimativa.
- **Multa e juros:** 2% de multa e 1% ao mês pro rata dia, configuráveis.
- **Sublimite:** alerta quando o RBT12 passa de 80% do sublimite de R$ 3,6 milhões.

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

Item, NBS, desdobro, CNAE, alíquota e IBS/CBS vêm de `servico_padrao.json`, com os
dados da Moraes & Oliveira: 17.19 / NBS 113022100 / desdobro 17.19.01 / CNAE 6920601 / cIndOp 100301 /
cClassTrib 200052. Os códigos de IBS/CBS seguem a **Tabela IBS x CBS** da prefeitura para o item 17.19. O
cClassTrib 200052 corresponde à redução de 30% para profissões intelectuais (LC 214/2025, art. 127). Outros
serviços devem usar o par cIndOp/cClassTrib que a tabela indica para o respectivo item e NBS.

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

## Emissão pelo Emissor Nacional (nfse.gov.br)

Em **Configurações › Emissão da NFS-e** você escolhe o canal:

| Canal | Por onde sai | Credencial | Numeração |
|---|---|---|---|
| **Itaboraí** (padrão) | webservice da prefeitura (provedor CTA 2.00) | chave privada no `.env` | RPS (`ITABORAI_PROXIMO_RPS`) |
| **Nacional** | Sefin Nacional / ADN (Sistema Nacional NFS-e, leiaute v1.01) | certificado digital **A1 (.pfx)** do escritório e a senha dele | DPS, com série própria (padrão 900) e contador separado |

A escolha vale para tudo: emissão avulsa, emissão em lote, recorrência e robô. O título guarda o canal e a
chave de acesso, e **o cancelamento sempre usa o canal em que a nota saiu** (evento 101101 no nacional).

No canal nacional, o sistema:
1. monta a DPS a partir do mesmo cadastro e do mesmo serviço padrão: cTribNac = desdobro 171901, NBS,
   regime do Simples (ME/EPP, ISS fora do DAS, sociedade de profissionais), pTotTribSN pela alíquota efetiva
   do Anexo III e o grupo IBS/CBS (cIndOp 100301, CST 200, cClassTrib 200052);
2. valida a DPS contra o XSD oficial v1.01 (`schemas/nacional`);
3. assina `infDPS` (XMLDSig, RSA-SHA256, C14N). A assinatura foi conferida com o validador do Java
   (javax.xml.crypto);
4. envia com autenticação mútua TLS, usando o próprio certificado, para
   `sefin.nfse.gov.br/sefinnacional/nfse`. Em homologação o destino é a **Produção Restrita**;
5. guarda o XML da NFS-e, a chave de 50 caracteres e o link da consulta pública em
   `saida/AAAA-MM/DPS_n/`.

Se o Sefin responder que a DPS já existe (E0014), o sistema avança a numeração e reenvia uma vez.

O botão **Testar certificado e conexão** abre o .pfx, mostra titular, CNPJ e validade, e consulta no ADN
o convênio do município. O certificado precisa ser do mesmo CNPJ do prestador.

> **Atenção (tributário):** a emissão pelo Emissor Nacional só é aceita se o município de Itaboraí permitir
> esse emissor para o contribuinte. Itaboraí usa sistema próprio (as notas trazem “Amb. Gerador: Sist.
> Próprio do Município”). Confira o resultado do botão de teste e faça a primeira emissão na Produção
> Restrita. Retenção de PIS/COFINS ainda não é gerada no canal nacional; para esses casos, use o canal
> municipal.

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
pip install pytest lxml cryptography
python -m pytest
```

São 100 testes, que cobrem o emissor (municipal e nacional), o financeiro e as automações:
- a ordem e o conteúdo de cada campo do XML, além da validação contra o XSD oficial;
- a leitura do retorno real do webservice;
- a chave de segurança;
- os cálculos (base, ISS, líquido pela fórmula ABRASF, carga tributária);
- todas as críticas;
- a emissão e o cancelamento de ponta a ponta contra um **webservice simulado**, que recebe o multipart e
  recalcula a chave de segurança;
- a rejeição sem consumir o número do RPS;
- a trava de produção;
- o canal nacional: DPS no XSD v1.01, assinatura, adulteração detectada, certificado com senha errada ou de
  outro CNPJ, e emissão e cancelamento contra um **Sefin simulado com TLS mútuo**;
- a tela.

## Limitações conhecidas

- **Situação Tributária / Tipo de Retenção de PIS/COFINS/CSLL (Nota Técnica 005):** o XSD atual não tem
  esses campos. Notas **sem retenção federal**, que é o caso normal de um prestador do Simples Nacional, não
  são afetadas. Se uma nota com retenção de PIS/COFINS/CSLL for rejeitada, o erro da prefeitura aparece na
  tela e em `retorno.xml`.
- O grupo opcional `ImovelIBSCBS` (endereço do imóvel) e o grupo `Evento` do XSD ainda não são gerados.
- Erros de rejeição: o formato foi reproduzido do ACBr, e o retorno bruto fica sempre salvo em `retorno.xml`.
