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
   - informe as credenciais do **Banco Inter**, a chave PIX, o e-mail (SMTP) e o e-mail que recebe o
     **resumo diário**.
4. Em **Recorrência**, marque "Repetir todo mês" nos clientes mensais.

### Python instalado sozinho

`INSTALAR.bat` e `INICIAR.bat` procuram o Python 3.10+ (no PATH, no lançador `py` ou na pasta do usuário). Se não
houver, instalam o Python 3.12 **automaticamente, só para o usuário** (sem pedir administrador): primeiro pelo
`winget` do Windows e, se ele não existir, baixando o instalador oficial de python.org. Depois instalam os
componentes (`lxml` e `cryptography`). Não é preciso baixar nem configurar nada à mão.

### Sem janela preta

O sistema e o robô rodam **escondidos**. O atalho "Sistema Financeiro NFS-e" (área de trabalho e inicialização
do Windows) chama `SISTEMA.vbs`, que abre o navegador sem janela; se o sistema já estiver aberto, só abre o
navegador de novo. O robô agendado (de hora em hora) também roda sem janela. Para fechar, use **Encerrar o
sistema** no menu. O registro do que aconteceria na janela fica em `dados\tela.log` e `dados\robo.log`.
Para ver a janela (diagnóstico), rode `INICIAR.bat` direto.

Para desligar a automação, use `DESINSTALAR_AUTOMACAO.bat`. Seus dados são mantidos.

## Atualizar de uma versão anterior

**Pelo botão (recomendado, a partir da 3.2.0):** em **Configurações › Atualizar o sistema**, selecione o ZIP da
versão nova. O sistema faz backup de todas as empresas, troca **só os arquivos do programa** (dados, senhas,
certificados, notas e `.env` ficam intactos), guarda uma cópia da versão anterior (dá para voltar pelo mesmo
cartão) e reabre sozinho. Se o robô estiver rodando naquele momento, ele pede para tentar em alguns minutos.

**Manualmente:**

1. Feche o sistema antigo (janela preta ou botão "Encerrar o sistema"), se estiver aberto.
2. Descompacte o pacote novo **por cima da mesma pasta** de antes. Assim o banco de dados (`dados\sistema.db`),
   os clientes e as empresas continuam lá.
3. Abra pelo `INICIAR.bat` (uma vez) ou pelo atalho. A cada abertura ele:
   - se esta mesma versão já estiver aberta, só abre o navegador (não abre outra cópia);
   - encerra telas de versões antigas ou de outras pastas que tenham ficado abertas;
   - aponta o robô agendado, a inicialização com o Windows e o atalho da área de trabalho para a pasta
     dele, rodando sem janela;
   - se a porta 8765 continuar ocupada, abre em outra porta livre.
4. A versão aparece no canto inferior do menu (ex.: v3.2.0).
5. Se a versão nova foi para outra pasta, o painel mostra "Versão anterior encontrada" (há também o botão em
   Configurações › Versão anterior).
   - O que é trazido: e-mail de envio, Banco Inter, chave PIX, e-mail do dono, certificado (copiado para dentro da
     empresa), clientes que faltam, o financeiro (se o atual estiver vazio), a numeração (pelo maior valor) e as
     outras empresas.
   - Só entra o que estiver vazio aqui; o que você já preencheu na versão nova prevalece.
   - A produção nunca é ligada por cópia.
   - A pasta antiga não é alterada.

**Cores:** o botão "Tema" no menu alterna entre automático (segue o Windows), claro e escuro. A escolha fica
guardada no navegador.

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
| **Configurações** | Robô, emissão (Itaboraí/Nacional), Banco Inter, chave PIX, multa e juros, régua, e-mail (SMTP) e categorias de despesa. |

**O que o robô faz sozinho, a cada hora** (vem ligado; cada item pode ser desligado em Configurações):

| Etapa | Automação |
|---|---|
| XML das notas | Lê a pasta de XML: atualiza clientes; notas emitidas **fora do sistema** (Nitrus, portal) viram contas a receber; cliente com nota de mesmo valor em 3 dos últimos 4 meses vira **contrato detectado**. |
| Recorrência | Gera os títulos dos contratos confirmados (contrato detectado só cobra depois de confirmado, em um clique). |
| NFS-e | Emite as notas pendentes (só em produção). Falha de rede volta para a fila; recusa da prefeitura vai para revisão. Cada título é reservado antes do envio, o que impede emissão em dobro. |
| Cobrança | Registra o boleto com PIX no Inter, salva o PDF e roda a régua: e-mail automático com o PDF anexado e fila de WhatsApp com a mensagem pronta (um clique). |
| Baixas | Banco Inter (consulta de cada boleto pela API) e **extratos .ofx que aparecerem na pasta Downloads**, importados sozinhos. |
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
6. dá baixa nos boletos pagos, consultando o Inter;
7. roda a régua de cobrança.

Cada etapa é independente: um erro em uma não para as outras e fica registrado no log. Notas de teste e notas
com erro nunca entram na régua.

**Meios de cobrança**
- **Banco Inter** (padrão): boleto com QR Code PIX registrado direto na conta do escritório pela API de Cobrança
  v3 do Inter, sem nenhum intermediário. A baixa é automática.
- **PIX copia e cola próprio**: sem tarifa. O identificador do título vai no PIX e a baixa sai pela conciliação
  do extrato. Também é o que o sistema usa enquanto o Inter não estiver configurado.

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

## Relatórios contábeis e autonomia

- **Relatórios** (todos com "Imprimir / PDF" no layout contábil, com cabeçalho da empresa):
  - Indicadores: ponto de equilíbrio, inadimplência de 90 dias, atraso médio ponderado, concentração de clientes,
    clientes sem faturamento recente.
  - DRE: no padrão da Lei 6.404/76, art. 187, adaptada ao Simples. Mostra receita bruta, deduções, receita
    líquida, despesas por grupo, resultado operacional, despesas financeiras e resultado líquido, com 12 meses,
    total e análise vertical. Valores negativos entre parênteses. O DAS pago e lançado como despesa não é deduzido
    de novo.
  - Fluxo de caixa: realizado pelo caixa e projetado. Atrasos acima de 60 dias ficam fora da projeção; sem
    despesas lançadas, usa a média de 3 meses.
  - Livro caixa, inadimplência por faixa, análise por cliente e fechamento mensal.
- **Checklist de implantação e saúde:** aparece no painel e diz o que falta configurar ou corrigir, com o link para
  resolver.
- **Fechamento mensal automático:** no dia configurado o robô gera o relatório gerencial do mês anterior, salva em
  `Downloads\Relatorios financeiros` e envia ao dono por e-mail.

## Importar clientes dos XML

1. Coloque os XML (ou ZIP) das notas já emitidas na pasta **IMPORTAR XML**, dentro da pasta do sistema. Pode
   misturar notas de várias empresas. O `IMPORTAR_CLIENTES.bat` abre essa pasta.
2. No sistema, em **Clientes › Importar clientes dos XML**:
   - as notas aparecem agrupadas pela empresa que as emitiu (CNPJ do prestador);
   - para cada grupo aparecem a empresa de destino, quantos clientes são novos e os **padrões para emitir a nota**
     detectados nos XML: item da LC 116, desdobro, NBS, alíquota, descrição e IBS/CBS;
   - revise os padrões e clique em **Importar**.
3. Regras da importação:
   - os clientes só entram na empresa que emitiu as notas, nunca em outra;
   - se o prestador ainda não estiver cadastrado, o link "Cadastrar esta empresa" abre o cadastro já preenchido.
4. Depois de importados, os arquivos vão para `IMPORTAR XML\importados\<CNPJ>`. Essa passa a ser a pasta de
   XML daquela empresa para o robô (notas emitidas fora do sistema e contratos detectados).
5. O robô também importa sozinho os clientes das notas novas que aparecerem na pasta, cada uma na sua empresa.
   Os padrões da nota só mudam quando você confirma na tela.

## 13º honorário

Com a opção ligada (Configurações › 13º honorário), o robô cobra o honorário mensal de cada contrato ativo em
parcelas: por padrão, **50% com vencimento em 30/11 e 50% em 20/12**. Percentuais, datas, descrição e emissão de
NFS-e são ajustáveis, e as parcelas somam 100%. Cada parcela vira uma conta a receber com NFS-e e boleto e
entra na régua de cobrança. A parcela de novembro é gerada em novembro e a de dezembro em dezembro, sem
duplicar. Se o sistema ficar parado até depois do vencimento de uma parcela, ela não é criada já vencida.

## Cobrança recorrente dos atrasados

Além das etapas fixas da régua, o título em atraso é cobrado de novo periodicamente até ser pago: a partir de
**N dias** do vencimento original (padrão 5), repete **a cada X dias** (padrão 7). As duas opções ficam em
Configurações › Cobrança.

## Várias empresas

O sistema atende quantas empresas você quiser: a Moraes & Oliveira e as empresas para as quais você emite nota e
controla o financeiro.

- **Trocar ou cadastrar:** clique no nome da empresa, no topo do menu. Na nova empresa informe razão social, CNPJ
  (validado), inscrição municipal, canal da NFS-e (Itaboraí ou Nacional) e município.
- **Tudo separado:** cada empresa tem o seu `.env` (credenciais), banco de dados, clientes, contas a receber e a
  pagar, configurações, numeração de RPS/DPS, notas emitidas, boletos e relatórios. A empresa original continua na
  pasta do sistema, sem mover nada; as novas ficam em `empresas/<CNPJ>/`.
- **Configuração pela tela:** em Configurações, os cartões "Empresa emissora e credenciais" e "Serviços
  (atividades) da empresa" valem para a empresa em uso. O checklist do painel avisa enquanto o serviço padrão de uma empresa nova
  não for revisado.
- **Robô:** a cada execução processa todas as empresas, uma de cada vez, cada uma com seus dados. A tela pode
  estar aberta em qualquer empresa enquanto isso.
- **Nada é compartilhado entre empresas:**
  - certificado A1 e arquivos `.crt`/`.key` do Inter são enviados pelo botão em Configurações e ficam guardados
    só na pasta da empresa (`dados/certificados`); um arquivo fora dela é recusado;
  - o mesmo certificado, chave PIX, credencial do Inter ou e-mail de envio não pode ser cadastrado em duas
    empresas;
  - empresas adicionais nunca herdam variáveis do computador;
  - o acesso ao banco (token) é sempre separado por empresa.
- **Proteções:**
  - a nota sai com o município de prestação da empresa emissora;
  - cada empresa tem a própria pasta de extratos;
  - o sistema memoriza a conta bancária do primeiro extrato e ignora extratos de outra conta, para que um
    extrato nunca seja conciliado na empresa errada.


## Faturamento, regra da NFS-e e recorrência

- **Regra geral da NFS-e** (Configurações › Emissão › "Lançamento de serviços / emissão de NFS-e"):
  emitir na geração do contas a receber; emitir ao efetuar a baixa (pagamento confirmado pelo Inter, extrato
  ou baixa manual); apenas lançar o contas a receber sem NFS-e; ou não emitir e não lançar (recorrência parada).
- **Regra do cliente:** na aba Recorrência cada cliente pode ter regra própria; quando diferente da geral, a do
  cliente vale primeiro (na emissão manual, no lote, na recorrência e no 13º).
- **Emitir nota:** mostra a regra que será aplicada ao cliente escolhido e pergunta só "Gerar cobrança"
  (boleto/PIX + régua). Sem cobrança, o valor conta como faturado, mas não entra em "a receber", atraso, régua
  ou boletos (aba "Sem cobrança" em Contas a receber). Notas emitidas fora do sistema (importadas dos XML)
  também entram como faturamento sem cobrança. Só é "a receber" (e entra em atraso, inadimplência, régua e
  previsão de caixa) o título com cobrança de fato gerada: boleto registrado no Inter ou PIX.
- **Contas a receber › Mais:** "Tirar da cobrança (manter a nota)" cancela o boleto e tira da régua sem mexer na
  NFS-e; "Gerar cobrança" faz o caminho inverso. "Cancelar título" com nota emitida pergunta se é só para tirar
  da cobrança ou se é para cancelar a NFS-e na prefeitura (com justificativa e confirmação).
- **Aba Recorrência:** todos os clientes, já com o valor da última nota, dia de vencimento, serviço, regra da
  nota e cobrança, editáveis na própria linha. Marque "Repetir todo mês" para o cliente entrar no faturamento
  mensal; quem não estiver marcado nunca é cobrado. "Mais" abre início, fim, reajuste e descrição.

## Regras fiscais (regra geral e por tomador)

Em **Configurações › Regras fiscais** fica a regra geral da empresa: regime (MEI, Simples, Lucro Presumido,
Lucro Real), apuração no Simples, regime especial, ISS retido e alíquota, retenções federais (IRRF, PIS, COFINS,
CSLL, INSS) e IBS/CBS. Ao emitir (e no cadastro do cliente) o sistema pergunta **"Usar regra geral"** ou
**"Regra específica deste tomador"**; a específica fica guardada só naquele tomador e vale primeiro nas próximas
notas dele. Retenções de até R$ 10,00 são dispensadas automaticamente. A regra do tomador também cobre situação do ISS (imune, exportação,
não incidência), exigibilidade suspensa, benefício municipal, ISS retido pelo intermediário, CST de PIS/COFINS,
órgão público e destinatário diferente. Na emissão, **Mais campos da nota** traz local da prestação, código
municipal, descontos, dedução/redução, obra, evento, pedido, ART/RRT, imóvel (CIB), reembolso/repasse, NFS-e
referenciada, intermediário e substituição (também pelo botão **Substituir** em Notas emitidas). A tela mostra **só os campos
que o regime da empresa e o caso exigem**: MEI quase nada; Simples só ISS retido e INSS; Presumido/Real as
retenções federais, PIS/COFINS e IBS/CBS. Obra só para serviços do item 7, evento para itens de eventos,
dedução para itens 7, 9 e 12, substituição só no canal nacional; campos que dependem de outro aparecem quando
ele é preenchido. Campo escondido não é enviado.

**Leitura das notas antigas (IMPORTAR XML):** além de clientes e serviços, o leitor tira das notas o regime da
empresa (MEI, Simples, Presumido ou Real — este pelas alíquotas de PIS/COFINS), apuração no Simples, regime
especial, forma da carga aproximada, PIS/COFINS próprio e IBS/CBS (tributação regular, diferimento, crédito
presumido) para completar a **regra geral** (só o que estiver vazio, uma única vez). De cada tomador, pela nota mais
recente, lê ISS retido (e por quem), alíquota, retenções de IRRF/PIS/COFINS/CSLL/INSS em %, imunidade,
exportação, ISS suspenso, benefício municipal, CST de PIS/COFINS, consumo pessoal, órgão público e destinatário;
quem difere da regra geral ganha **regra específica** — tomador que já tem regra gravada não é alterado. Detalhes por regime em
`docs/NFSE_NACIONAL_CAMPOS_POR_REGIME.md`.

## Notas emitidas

Aba **Notas emitidas**: todas as NFS-e (do sistema e importadas dos XML), abrindo na competência atual.
Filtros: competência (ou "Todas as competências"), situação (emitidas, canceladas, testes de homologação),
serviço e busca por cliente, CNPJ ou número. Totais de notas e valor emitido. **Cancelar NFS-e** pede
justificativa (mín. 15 caracteres) e confirmação, envia ao canal em que a nota saiu (Itaboraí ou Nacional) e
cancela também a conta a receber e o boleto. Conta já paga exige estorno antes; nota importada (emitida fora do
sistema) é cancelada no portal em que foi emitida.

## Backup e restauração

Em Configurações › "Backup e restauração":

- **O que entra:** tudo da empresa — banco (cópia consistente), clientes, configurações, serviços, numeração,
  credenciais (.env), certificados e os XML das notas. Um .zip por empresa, em `dados/backup` da própria empresa.
- **Automático:** o robô faz um por dia (guarda os 30 últimos). "Fazer backup agora" faz na hora.
- **Cópia extra:** informe uma segunda pasta (pendrive, HD externo, pasta sincronizada com a nuvem); cada backup
  é copiado também para lá, numa subpasta com o CNPJ da empresa.
- **Restaurar:** pela lista (botão Restaurar) ou "Restaurar de um arquivo…" (computador novo: se a empresa do
  backup ainda não existir, ela é cadastrada). Proteções: antes de restaurar faz backup do estado atual; backup
  de uma empresa nunca é restaurado em outra; a numeração do RPS/DPS nunca volta atrás; o ambiente
  (homologação/produção) não muda; .zip com caminhos fora do padrão é recusado.

## Serviços (atividades) de cada empresa

Uma empresa pode prestar mais de uma atividade (ex.: contabilidade, consultoria, treinamento), cada uma com o
próprio item da LC 116, desdobro nacional, NBS, CNAE, alíquota do ISS, tributação, IBS/CBS e descrição da nota.

- **Cadastro manual:** Configurações › "Serviços (atividades) da empresa": novo, editar, tornar padrão, excluir.
  O serviço antigo (`servico_padrao.json`) vira automaticamente o primeiro serviço e o padrão do catálogo.
- **Pela importação das notas:** ao ler a pasta `IMPORTAR XML`, cada atividade distinta das notas (mesmo
  desdobro/item e NBS) aparece separada, com nome sugerido e códigos detectados; marque as que devem ser
  cadastradas. Cada cliente fica ligado à atividade que mais aparece nas notas dele (serviço habitual).
- **Na emissão:** Emitir nota, Emitir em lote, título avulso e contratos têm o seletor de serviço. Ao escolher o
  cliente, o serviço habitual dele vem selecionado e a descrição acompanha o serviço. Os contratos e o 13º
  honorário usam o serviço do contrato (ou o habitual do cliente) na emissão automática.

## Sem dependência de terceiros

O sistema conversa **somente** com os canais oficiais:
- a Prefeitura de Itaboraí (NFS-e municipal);
- o Sefin/ADN (NFS-e Nacional);
- o Banco Inter (boletos e PIX);
- o servidor de e-mail do próprio escritório.

Nenhum sistema de cobrança, WhatsApp por API ou consulta de cadastro de terceiros é usado. O ACBr serviu só
de referência de leiaute, e nada dele é executado.

Ideias estudadas nos sistemas de mercado e reproduzidas com código próprio:

| Ideia | Inspirada em | Como ficou aqui |
|---|---|---|
| Régua de cobrança antes e depois do vencimento | Asaas, Conta Azul, Omie | Dias configuráveis (-3, 0, +1, +5, +15, +30), e-mail com PDF e fila de WhatsApp |
| Recorrência com reajuste anual | sistemas de assinatura e de escritório contábil | Contratos com mês e % de reajuste, títulos gerados no dia configurado |
| Detecção de contratos pelo histórico | Nibo, Acessórias | Mesmo valor em 3 dos últimos 4 meses vira contrato sugerido |
| Conciliação bancária automática | Conta Azul, Granatum | OFX da pasta, casamento por txid, nome/CNPJ e valor, e despesas classificadas por regra |
| Multa e juros pro rata | boletos bancários | 2% + 1% a.m. calculados no dia, também na mensagem de cobrança |
| Score de pagador e aging | ERPs financeiros | Pontuação por atraso médio e títulos vencidos; faixas de vencimento |
| DRE e fluxo de caixa com DAS estimado | Nibo, Conta Azul | Alíquota efetiva do Anexo III pelo RBT12, com ISS fixo fora do DAS |
| Resumo diário para o dono | Omie, Nibo | E-mail com recebidos, atrasos, NFS-e com erro e contratos a confirmar |
| Robô que trabalha sozinho | todos | Rotina a cada hora com trava contra execução dupla e backup diário |

## Boletos (Banco Inter)

Os boletos são registrados **direto no Banco Inter**, pela API oficial de Cobrança (v3), com autenticação pelo
certificado da integração. Não há nenhum sistema de cobrança intermediário.

**Como configurar (uma vez):**
1. No Internet Banking PJ do Inter, acesse **Soluções para sua empresa › Nova integração** e marque os escopos de
   emissão, cancelamento e consulta de boletos.
2. Baixe o **certificado (.crt)** e a **chave (.key)** e guarde-os numa pasta do computador.
3. Em **Configurações › Cobrança**: escolha "Inter: boleto + PIX" e informe client_id, client_secret e o caminho
   do .crt e do .key. Salve e clique em **Testar conexão com o Inter**.

**Depois disso, sem nenhuma ação manual:**
- **registro:** cada título com NFS-e válida vira um boleto com PIX, com a multa e os juros configurados e o
  vencimento do contrato;
- **pasta:** o **PDF** é salvo em `Downloads\Boletos\AAAA-MM\<vencimento> - <cliente> - titulo N.pdf`. Ao lado
  dele fica um **.txt** com a linha digitável e o PIX copia e cola;
- **envio ao cliente:** o e-mail da régua e o botão **Cobrar** vão com o PDF anexado, a linha digitável e o PIX.
  No WhatsApp, um clique abre a conversa com a linha digitável e o PIX; o PDF fica na pasta para anexar;
- **baixa:** o robô consulta o Inter e baixa os boletos pagos, com a data e o valor recebidos;
- **cancelamento:** cancelar um título (ou a NFS-e dele) cancela também o boleto no banco;
- **na tela Contas a receber:** o botão **⬇ PDFs dos boletos** salva os que faltam e abre a pasta. Em cada
  título, o botão **Boleto PDF** abre o boleto.

O Inter exige endereço completo do pagador, incluindo cidade e UF. A cidade é preenchida pelo código IBGE (a
tabela dos municípios da carteira vem no sistema) ou digitada no campo Cidade do cadastro. Se faltar algum dado, aquele boleto aparece no log do robô e os demais seguem normalmente.

O Inter não gera página pública de pagamento: o que vai ao cliente é o PDF, a linha digitável e o PIX.

## Emissão pelo Emissor Nacional (nfse.gov.br)

Em **Configurações › Emissão da NFS-e** você escolhe o canal:

| Canal | Por onde sai | Credencial | Numeração |
|---|---|---|---|
| **Itaboraí** (padrão) | webservice da prefeitura (provedor CTA 2.00) | chave privada no `.env` | RPS (`ITABORAI_PROXIMO_RPS`) |
| **Nacional** | Sefin Nacional / ADN (Sistema Nacional NFS-e, leiaute v1.01) | certificado digital **A1 (.pfx)** do escritório e a senha dele | DPS, com série própria (padrão 900) e contador separado |

### Extrato do Banco Inter pela API (conciliação sem arquivo)

Com o Inter configurado, o robô baixa o extrato da conta direto do banco (API Banking v2,
`/banking/v2/extrato/completo`) de hora em hora, continua de onde parou e concilia sozinho, como no OFX.
Na tela **Conciliação** há o botão **Baixar extrato agora** (últimos 7, 30, 60 ou 90 dias).
- A integração do Inter precisa da permissão **"Consultar extrato e saldo"** (escopo `extrato.read`). O token do
  extrato é separado: sem essa permissão, os boletos continuam funcionando e o robô avisa uma vez por dia.
- Não duplica: o mesmo lançamento baixado de novo é ignorado, e o que já entrou por OFX não é repetido pela API
  (nem o contrário).

### Segurança

- **Senhas protegidas no disco:** senha do e-mail, do certificado, segredo da API do Inter, senha do backup e
  a chave do webservice (.env) ficam cifradas — no Windows pela DPAPI do usuário (só o mesmo usuário, no mesmo
  computador, abre). Senhas antigas em texto são protegidas automaticamente ao abrir o sistema.
- **Backup com senha** (Configurações › Backup): o arquivo vira `.protegido`, cifrado com AES-256-GCM (chave
  derivada da senha por scrypt). Só esse backup leva as senhas da empresa, para restaurar em outro computador
  já funcionando. **Sem a senha o backup não abre — anote-a em local seguro.**
- **PIN de acesso** (Configurações › Acesso à tela): 4 a 8 números, guardado só como hash; bloqueia a tela ao
  abrir e após o tempo sem uso escolhido; 5 erros seguidos travam novas tentativas por 5 minutos. O robô
  agendado continua rodando normalmente.

### Validação com credenciais reais (menu Validação)

Antes de ligar a produção, o menu **Validação** testa cada integração com os dados verdadeiros da empresa e
grava o resultado (data, aprovado/falhou e detalhes):

| Teste | O que faz |
|---|---|
| E-mail (SMTP) | envia um e-mail de teste |
| Certificado A1 e Sefin | confere titular, CNPJ e validade e conecta ao ADN |
| Itaboraí | emite um RPS em **homologação** e cancela a nota (não usa a numeração real) |
| NFS-e Nacional | emite uma DPS na **Produção Restrita** com número próprio e cancela |
| Banco Inter | autentica e consulta; no **sandbox** também cria e cancela um boleto de R$ 2,50 |
| Backup | gera o backup e confere o .zip, o manifesto e a integridade do banco |

Integrações não configuradas aparecem como "Não configurado". Nenhum teste usa o ambiente de produção.

### Regras do Manual do Webservice de Itaboraí (versão 2026 — XML a partir de 28/09/2026)

O XSD novo publicado pela prefeitura é idêntico ao que já usamos; o que muda são as **regras de negócio**,
aplicadas automaticamente pelo sistema (`nfse_itaborai/itaborai_regras.py`):

| Situação | TipoDeTributacao | ISS retido / responsável | Alíquota |
|---|---|---|---|
| MEI (qualquer item) ou prestador imune | **2** Isento/Imune | não / prestador | não informa |
| Simples Nacional (padrão) | **4** | não / prestador | **alíquota efetiva do DAS (2% a 5%)**; no item **17.19** não destaca alíquota nem ISS |
| Simples com ISS retido pelo tomador em Itaboraí | **5** Retido no Município | sim / tomador | efetiva |
| Simples com ISS retido fora | **1** | sim / tomador | efetiva |
| Lucro Presumido/Real | **0** Tributado no Município | não / prestador | da Tabela de Atividades |
| Presumido/Real com retenção em Itaboraí | **5** | sim / tomador | da Tabela de Atividades |
| Item da lista do art. 3º da LC 116 prestado fora (ex.: 7.02, 7.05, 12.xx) | **1** | conforme a regra | — |
| Exigibilidade suspensa | **3** | — | — |

- **Retenção obrigatória (tipo 5) para:** Prefeitura de Itaboraí, fundos municipais, COMDIT, Banco do Brasil e
  Caixa — o sistema força a retenção mesmo que o cadastro diga o contrário e avisa na tela. A **Petrobras**
  é emitida pelas regras normais: o próprio webservice ajusta quando o item prevê retenção.
- **Deduções** só com **Código da Obra** (6 caracteres) e limitadas a **40%** do valor da nota.
- **Imóvel (IBS/CBS)** obrigatório para os Indicadores de Operação 020101, 020201, 020202, 020301 e 020401
  (exceto nos desdobros dispensados pelo manual). **Evento** obrigatório para os desdobros 12.xx listados.
- **Tomador pessoa jurídica:** tipo de logradouro, logradouro, bairro, município e UF obrigatórios.
- **CodigoTributacaoMunicipio** "não se aplica em Itaboraí": vai sempre vazio.
- **IncentivoFiscalImunidade:** 1 incentivo fiscal, 2 não, **3 imunidade/isenção** (Configurações › Regras fiscais).

Esses erros são apontados **antes** do envio, com a explicação em português, para a nota não ser recusada.

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

São 219 testes, que cobrem o emissor (municipal e nacional), o financeiro e as automações:
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
- os boletos contra uma **API do Inter simulada com TLS mútuo**: token, campos do boleto, PDF e .txt na pasta,
  anexo no e-mail, baixa automática, cancelamento e cadastro incompleto;
- a tela.

## Limitações conhecidas

- **Situação Tributária / Tipo de Retenção de PIS/COFINS/CSLL (Nota Técnica 005):** o XSD atual não tem
  esses campos. Notas **sem retenção federal**, que é o caso normal de um prestador do Simples Nacional, não
  são afetadas. Se uma nota com retenção de PIS/COFINS/CSLL for rejeitada, o erro da prefeitura aparece na
  tela e em `retorno.xml`.
- O grupo opcional `ImovelIBSCBS` (endereço do imóvel) e o grupo `Evento` do XSD ainda não são gerados.
- Erros de rejeição: o formato foi reproduzido do ACBr, e o retorno bruto fica sempre salvo em `retorno.xml`.
