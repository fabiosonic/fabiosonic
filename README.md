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
2. Dê dois cliques em **`INSTALAR.bat`** (uma única vez). Primeiro ele pede o **serial de liberação** (plano
   mensal ou anual, recebido do fornecedor) e os dados da empresa; depois deixa tudo automático:
   - o robô financeiro roda **de hora em hora** pelo Agendador do Windows, mesmo com o sistema fechado;
   - o sistema **abre sozinho ao ligar o computador**;
   - cria um atalho na área de trabalho.
3. No primeiro acesso, em **Configurações**:
   - informe as credenciais do **Banco Inter**, a chave PIX, o e-mail (SMTP) e o e-mail que recebe o
     **resumo diário**.
4. Em **Recorrência**, marque "Repetir todo mês" nos clientes mensais.

### Python incluído no pacote

O pacote **completo** (`EmissorItaborai_<versão>_completo.zip`, montado por `ferramentas/montar_pacote_windows.py`)
traz a pasta `python\` com o Python 3.12 oficial da Python Software Foundation e os componentes já instalados
(`lxml`, `cryptography`, `playwright`, `pypdf`). Com ela, `INSTALAR.bat` e os demais `.bat` usam esse Python: a
instalação não precisa de internet nem instala nada no Windows. As atualizações pelo botão trocam só o programa e
mantêm a pasta `python\`.

Sem a pasta `python\`, `INSTALAR.bat` e `INICIAR.bat` procuram o Python 3.10+ (no PATH, no lançador `py` ou na pasta do usuário). Se não
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

**Diagnóstico:** `DIAGNOSTICO.bat` mostra versão, Python usado, componentes (lxml, cryptography, pypdf, playwright e
o node.exe do WhatsApp), `.env`, licença, telas abertas e o fim de `dados\tela.log` e `dados\robo.log`, e grava
`diagnostico.txt` (sem senhas). Se a tela não abrir em 40 s, o `INSTALAR.bat` mostra esse mesmo diagnóstico. Os `.bat`
não usam blocos entre parênteses com o caminho do Python, então funcionam em pastas como `Sistema (1)`.

**Uma instalação principal por computador:** o robô agendado, a abertura com o Windows e os atalhos apontam para a
última pasta instalada/aberta pelo `INICIAR.bat`, e telas de outras pastas são fechadas (evita dois robôs da mesma
empresa emitindo em dobro). Para voltar a uma pasta, abra o `INICIAR.bat` dela.

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


**Versão anterior só da mesma empresa.** A opção "Versão anterior encontrada" só oferece e só importa instalações do
**mesmo CNPJ**. A instalação de outra empresa no mesmo computador (por exemplo, a de um cliente do escritório) nunca é
misturada: nem nome, nem credenciais, nem clientes, nem certificado. Se uma versão até a 3.8.3 trouxe dados de outra
empresa, o Painel mostra o aviso **"Esta instalação recebeu dados de outra empresa — Desfazer agora"**: o reparo
**traz de volta os dados desta empresa** (nome, canal, município, PIX, e-mail, banco, regras), buscando-os nesta ordem:
backup anterior à importação, demais backups, outras instalações do mesmo CNPJ no computador, notas autorizadas pela
prefeitura/Sefin para este CNPJ e certificado digital A1 deste CNPJ. Dado que identifica a outra empresa e não tem
fonte desta fica **vazio** (para você preencher), nunca com o da outra. Também tira os clientes e o certificado da
outra empresa e mantém o que foi alterado depois. Antes de trazer uma versão anterior o sistema faz um backup.

**Dados da empresa editáveis e trazidos da última versão.** Em Configurações › Empresa emissora e credenciais todos
os dados da empresa podem ser corrigidos: razão social, CNPJ, inscrições, chave do webservice, Simples, município
(código IBGE), além de PIX, e-mail, banco e certificado nos cartões próprios. O botão **"Trazer os dados da empresa de
uma versão anterior…"** lista as instalações e os backups do **mesmo CNPJ**, da mais recente à mais antiga, sugere a
mais recente que não estava com o nome de outra empresa e mostra só o que está diferente do atual; você marca o que
trazer. Antes de aplicar o sistema faz backup. **Notas emitidas, títulos, faturamento, clientes e numeração nunca são
tocados.** Travas: o CNPJ não pode ser trocado quando a empresa já tem títulos ou notas (misturaria o histórico — para
outra empresa use Empresas › Nova empresa), nem para o CNPJ de outra empresa cadastrada; o próximo RPS/DPS nunca fica
abaixo de um número já usado em produção.

**Nome conferido com o CNPJ.** Se o nome da empresa não tiver nenhuma palavra em comum com a razão social do
certificado digital (ou das notas do Emissor Nacional) deste CNPJ, o Painel avisa e oferece **"Usar …"** com o nome
oficial. A razão social também pode ser corrigida à mão em Configurações › Empresa emissora e credenciais.

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

Item, NBS, desdobro, CNAE, alíquota e IBS/CBS vêm de `servico_padrao.json`, que já vem preenchido para escritório
de contabilidade: 17.19 / NBS 113022100 / desdobro 17.19.01 / CNAE 6920601 / cIndOp 100301 /
cClassTrib 200052 (revise para a atividade da sua empresa). Os códigos de IBS/CBS seguem a **Tabela IBS x CBS** da prefeitura para o item 17.19. O
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
  - Plano de despesas por natureza (CPC 26 / NBC TG 26), na ordem em que aparece na DRE:
    - **Pessoal:** Folha, Pró-labore, Férias e 13º salário, Rescisões, Encargos, INSS patronal, FGTS,
      Vale-transporte, Vale-refeição/alimentação, Plano de saúde, Benefícios, Estagiários, Treinamento e cursos,
      Uniformes e EPI, Confraternizações.
    - **Ocupação:** Aluguel, Condomínio, IPTU, Energia elétrica, Água e esgoto, Telefone e internet, Manutenção e
      conservação, Limpeza, Segurança e monitoramento, Seguros.
    - **Administrativas:** Sistemas, Contador/Assessoria, Serviços de terceiros, Assessoria jurídica, Certificado
      digital, Material, Material de copa e limpeza, Correios e cartório, Viagens e deslocamentos, Combustível,
      Estacionamento e pedágio, Conselhos de classe (CRC), Associações e sindicatos, Assinaturas e publicações,
      Equipamentos de pequeno valor, Doações, Outras.
    - **Comerciais:** Marketing, Propaganda e publicidade, Brindes, Comissões, Representação e eventos.
    - **Tributárias:** Impostos, Taxas, Alvará e taxas municipais, Contribuição sindical patronal, Multas fiscais.
    - **Financeiras:** Bancárias, Tarifas, IOF, Juros, Juros e multas por atraso, Juros de empréstimos, Taxas de cartão.
    - Categorias próprias (Configurações › Financeiro) entram em despesas administrativas. O extrato já classifica
      sozinho os débitos conhecidos (IPTU, CEDAE, CRC, Correios, Unimed, Riocard, Alelo, posto de combustível,
      estacionamento, seguros, juros, multas…), e o escritório completa a regra pela própria escolha.
  - Fluxo de caixa: realizado pelo caixa e projetado. Atrasos acima de 60 dias ficam fora da projeção; sem
    despesas lançadas, usa a média de 3 meses.
  - Livro caixa, inadimplência por faixa, análise por cliente e fechamento mensal.
- **Checklist de implantação e saúde:** aparece no painel e diz o que falta configurar ou corrigir, com o link para
  resolver.
- **Fechamento mensal automático:** no dia configurado o robô gera o relatório gerencial do mês anterior, salva em
  `Downloads\Relatorios financeiros` e envia ao dono por e-mail.

## Importar clientes dos XML

**Jeito mais rápido:** dê dois cliques em **`IMPORTAR_CLIENTES.bat`**, coloque os XML/ZIP na pasta que abrir e tecle
Enter. Ele importa tudo de uma vez (clientes, serviços, empresa, numeração e regras fiscais do regime) e mostra o
resumo do que foi preenchido. Pela tela, o caminho é o abaixo.

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
4. **Serviços completos pelas notas:** cada atividade das notas vira um serviço com item da LC 116, desdobro
   nacional, NBS, código de tributação municipal, alíquota, carga tributária aproximada e o nome que o próprio Emissor
   Nacional dá ao código (ex.: "Psicologia"). Nota sem NBS entra na atividade de mesmo código (não duplica). O serviço
   mais usado vira o **padrão**, e o modelo "Contabilidade" que vem no sistema sai da lista quando a empresa não o usa.
   A alíquota efetiva do Simples informada nas notas passa a ser usada até o sistema ter 12 meses de faturamento.
5. **Cadastro da empresa completado pelas notas:** na importação, o que ainda estiver vazio é preenchido com o que
   as notas emitidas mostram — nome da empresa (e assinatura das mensagens), inscrição municipal e, no Emissor
   Nacional, o código IBGE do município. A numeração continua de onde parou: o próximo RPS/DPS passa a ser o maior
   número já usado + 1 (nunca volta). Nada que já esteja preenchido é trocado.
6. Depois de importados, os arquivos vão para `IMPORTAR XML\importados\<CNPJ>`. Essa passa a ser a pasta de
   XML daquela empresa para o robô (notas emitidas fora do sistema e contratos detectados).
7. O robô também importa sozinho os clientes das notas novas que aparecerem na pasta, cada uma na sua empresa.
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

O sistema atende quantas empresas você quiser: a sua e as empresas para as quais você emite nota e controla o
financeiro (dentro do limite da licença).

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
- **Cada janela é de uma empresa (3.18):** todo pedido da tela leva a empresa daquela janela e fica preso a ela do
  começo ao fim. Se a empresa em uso for trocada em outra janela, a janela antiga é recusada e recarregada — ela
  nunca mostra nem grava dados da outra. Trocar de empresa recarrega a tela inteira (sem listas na memória).
- **XML:** uma nota só entra na empresa cujo CNPJ é o do emissor; nota sem o CNPJ do emissor não entra em
  nenhuma, e empresa sem CNPJ configurado não importa nada.
- **Extratos:** conta já vinculada a outra empresa nunca é conciliada nesta; extrato sem número da conta não é
  importado pelo robô quando há mais de uma empresa (importe pela tela, na empresa certa).
- **Serviço:** empresa nova começa sem serviço cadastrado (o modelo de fábrica é vazio); nunca recebe o serviço da
  primeira empresa.
- **Versão anterior / dados da empresa:** essas telas trabalham só na empresa principal; na outra empresa elas
  recusam, sem mexer em nada.


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

## E-mail e telefone da empresa na nota

Em Configurações › Empresa emissora e credenciais ficam o **e-mail** e o **telefone** da empresa. No Emissor Nacional
eles vão nos campos próprios do prestador (`prest/email` e `prest/fone`) e aparecem no DANFSe. O webservice de
Itaboraí não tem campo de contato do prestador (a prefeitura usa o próprio cadastro): com a opção "incluir e-mail e
telefone nas observações" ligada (padrão), eles vão nas observações da nota. A importação dos XML preenche os dois
quando estiverem vazios.

## Campos fixos das notas do tomador e obrigatórios do Emissor Nacional

- **Campos fixos das notas deste tomador** (Clientes › editar): local da prestação, pedido e item, documento de
  referência, ART/RRT, dedução em %, obra, imóvel, intermediário e comércio exterior (sem o valor na moeda, que é de
  cada nota). Entram sozinhos em toda nota do tomador — manual, em lote, recorrência e robô — e aparecem
  preenchidos em Emitir › Mais campos da nota; o que for digitado na nota vale por cima.
- **Importação dos XML**: preenche esses campos fixos com o que se repete nas notas de cada tomador (só se ele ainda
  não tiver), cadastra clientes do exterior (NIF, país, cidade, código postal; reimportar não duplica), guarda o
  código interno do serviço (`cIntContrib`), a alíquota aplicada (`pAliqAplic`) e o benefício municipal em valor.
- **Obrigatórios condicionais** do leiaute nacional (v1.01) conferidos antes do envio, todos de uma vez e dizendo
  onde preencher: retenção pelo tomador/intermediário, alíquota do ISS retido no Simples, nomes do intermediário e
  do destinatário, país do resultado na exportação, comércio exterior, processo da exigibilidade suspensa, obra,
  evento e IBS/CBS conforme o regime. Detalhes em `docs/NFSE_NACIONAL_CAMPOS_POR_REGIME.md`.

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

### WhatsApp do escritório (automático, sem API oficial)

A cobrança por WhatsApp **sai sozinha**, pelo número do próprio escritório, via **WhatsApp Web** controlado pelo
sistema no computador do escritório. Sem API da Meta, sem intermediário e sem custo por mensagem.

1. **Uma vez só:** em **Configurações › WhatsApp do escritório**, clique em **Conectar (ler QR Code)**. No celular
   do escritório: WhatsApp › **Aparelhos conectados › Conectar um aparelho** e leia o QR Code da janela que abrir.
   A janela fecha sozinha e o envio automático é ligado.
2. Em **Clientes**, marque **"Cobrar por WhatsApp"** nos clientes que devem receber (os que já conversam com o
   escritório). Os demais recebem só o e-mail.
3. Pronto: o robô (de hora em hora), o botão **Rodar régua agora** e o botão **Cobrar** enviam sozinhos, com
   linha digitável, PIX copia e cola e o link do cartão. O navegador trabalha fora da tela (Edge ou Chrome já
   instalados); o computador só precisa estar ligado.

- **Mensagem de teste:** em Configurações › WhatsApp, informe um celular e clique em "Enviar mensagem de teste".
- O que não sai (computador desligado, celular sem internet, sessão desconectada) **fica na fila** da tela
  Cobrança e sai na próxima rodada; número sem WhatsApp vira erro no histórico de cobrança.
- Se a sessão cair (aparelho removido no celular), a tela avisa "não conectado": é só ler o QR Code de novo.
- Cuidados contra bloqueio por spam: só clientes marcados, intervalo aleatório entre mensagens (média de 15 s,
  ajustável) e no máximo 40 por rodada.
- A sessão fica na pasta da empresa (`dados/whatsapp_web`), separada por empresa e **fora dos backups**.
- Sem conexão, ainda dá para enviar manualmente pela tela Cobrança ("Enviar manualmente em sequência").
- O INICIAR.bat instala sozinho o componente necessário (pacote Python `playwright`, que usa o Edge do Windows).
- A API oficial da Meta continua disponível em Configurações, recolhida e desligada.

### Horário comercial dos envios

E-mails e mensagens (régua, botão Cobrar, WhatsApp, resumo diário e fechamento) só saem **de segunda a sexta,
das 08:00 às 18:00** (horário de Brasília). Fora disso nada se perde: o robô envia na primeira rodada dentro do
horário. O horário e a opção ficam em Configurações › Cobrança. Os testes que o escritório dispara (e-mail de
teste, mensagem de teste) não têm restrição. No WhatsApp automático, o **boleto em PDF** vai logo depois da mensagem
(opção em Configurações › WhatsApp).

### Envio automático: boleto, agradecimento e nota fiscal

Tudo segue as opções de Configurações › Cobrança (ligadas por padrão) e o horário comercial:

1. **Boleto ao gerar** — assim que o título tem boleto/PIX, o cliente recebe a cobrança por e-mail e, se estiver
   marcado para WhatsApp, a mensagem com o **boleto em PDF** pelo WhatsApp Web. Depois seguem os lembretes da régua.
   Título já vencido (ex.: importado) recebe uma única cobrança com o valor atualizado.
   Vários títulos do mesmo cliente na mesma rodada vão **num único e-mail**: tabela com vencimento, dias de atraso e
   valor atualizado de cada um, o total, os dados de pagamento (PIX/linha digitável) de cada título e todos os
   boletos em PDF anexados.
2. **Pagamento reconhecido** (extrato do Inter, webhook ou baixa) — mensagem de **agradecimento**.
3. **Nota fiscal** — toda NFS-e emitida vai para o cliente: e-mail com o número, o link oficial, o **PDF da nota**
   (página da prefeitura/Sefin impressa pelo Edge/Chrome do computador) e o XML; no WhatsApp, a mensagem com o PDF.
   Vale também para cliente **sem cobrança** e para nota emitida **antes do pagamento**. Se a nota é emitida após o
   pagamento, a mensagem sai assim que a emissão for concluída. Se o PDF não puder ser gerado (sem internet, página
   da prefeitura fora do ar), a mensagem segue com o link e o XML.
4. **Reenviar** — em **Notas emitidas**, o botão **Enviar ao cliente** reenvia a nota por e-mail na hora e põe na
   fila do WhatsApp (respeita o horário comercial).

Notas e pagamentos anteriores à atualização não recebem mensagem (nada de envio em massa do histórico); para essas,
use o botão **Enviar ao cliente**.

### Régua: antes do vencimento, atrasados e aviso de suspensão

- **Antes do vencimento** (Configurações › Cobrança › "Avisos antes do vencimento", padrão `-3, 0`): boleto assim que
  a cobrança é gerada, lembrete 3 dias antes e "vence hoje". Essas mensagens levam só os títulos no prazo — não cobram
  os atrasados.
- **Atrasados**: se o pagamento não for reconhecido, a **1ª cobrança sai 3 dias após o vencimento** e as seguintes
  **a cada 7 dias**, contadas da última cobrança de atraso do cliente. Cada cobrança leva todos os títulos em atraso
  dele, com multa e juros, numa única mensagem — o cliente nunca recebe duas cobranças de atraso na mesma semana.
- **Aviso de suspensão dos serviços**: quando o débito mais antigo chega a **90 dias** de atraso, o cliente recebe o
  aviso com todos os títulos em aberto, o total atualizado e a data da suspensão (prazo padrão de 10 dias). Sai uma
  vez por débito (no máximo um aviso a cada 30 dias) e substitui a cobrança daquela semana. Pode ser desligado e os
  prazos mudados em Configurações › Cobrança.
- Ao atualizar, a régua antiga (+1, +5, +15, +30 dias) é trocada por esse ciclo automaticamente.

### Aparência dos e-mails (logo e cores de cada empresa)

Em **Configurações › Aparência dos e-mails** cada empresa escolhe a sua logo (PNG, JPG ou WEBP), a cor de
destaque, a cor do cabeçalho/rodapé, o site e uma frase de rodapé. A tela recorta as bordas da imagem, reduz o
tamanho e sugere as cores a partir da própria logo; **Ver como fica** mostra o e-mail e **Enviar um exemplo**
manda um para o escritório conferir no Gmail/celular.

- A logo vai **embutida** no e-mail (imagem `cid:logo`): aparece sem depender de site nem de "baixar imagens".
- Fica em `dados/logo_email.png` **da empresa** (entra no backup; nunca aparece em outra empresa) e **não faz
  parte do programa**: quem compra o sistema começa sem logo (cabeçalho com o nome da empresa) e só troca o
  arquivo pela tela. Nada da marca de um cliente vai no pacote de instalação ou de atualização.
- Todos os e-mails a clientes usam a mesma moldura (boleto, lembrete, vence hoje, atraso, vários títulos,
  agradecimento, nota fiscal e aviso de suspensão), com o botão do WhatsApp do escritório e CNPJ/telefone/e-mail
  no rodapé. Pessoa física e MEI são chamados pelo primeiro nome ("Olá, Bruno!").

### Modelos das mensagens (editáveis)

Em **Mensagens › Modelos das mensagens** dá para editar o assunto e o texto de cada mensagem: boleto, lembrete, vence
hoje, cobrança de atraso (um ou vários títulos), aviso de suspensão, agradecimento e nota fiscal. Campos como
`{cliente}`, `{valor}`, `{vencimento}`, `{atualizado}`, `{dias}`, `{total}` e `{data_suspensao}` são trocados pelos
dados de cada cliente (clique no campo para inserir). A saudação, a lista de títulos, linha digitável, PIX, cartão,
NFS-e e a assinatura continuam automáticos. "Pré-visualizar" mostra o resultado com dados de exemplo; "Restaurar
padrão" volta ao texto do sistema. Campo inexistente (ex.: `{valr}`) é recusado ao salvar. Os modelos são de cada
empresa. Pela API oficial do WhatsApp valem os modelos aprovados na Meta.

### Forçar a emissão da NFS-e (botão "Emitir NFS-e") — só quando algo falhou

A emissão continua **automática**: o pagamento reconhecido (banco Inter, conciliação do extrato ou baixa) emite a
NFS-e na hora e a envia ao cliente; se a prefeitura/Sefin estiver fora do ar, o robô tenta de novo sozinho. O botão
**Emitir NFS-e** aparece na linha do Contas a receber **só quando a nota não saiu**: título **pago** sem nota válida
(também o marcado "Sem NFS-e"), nota **recusada** (erro — o motivo aparece na janela) ou **travada em emissão**.
Títulos em aberto que aguardam o pagamento não mostram o botão. O painel (Saúde do sistema) e a aba "Sem NFS-e"
apontam os pagos há mais de um dia sem nota e as notas recusadas/travadas. Proteções: título com NFS-e válida não emite
outra (para corrigir, substituição em Notas emitidas); título cancelado não emite; "em emissão" exige confirmar no
portal que a nota não saiu (evita duplicidade).

### Proteção contra NFS-e em duplicidade

- **Conferência antes de emitir:** se o cliente já tem nota válida do **mesmo serviço** (mesma descrição) da **mesma
  competência**, ou de **mesmo valor emitida há 10 dias ou menos**, o sistema mostra as notas parecidas e **pergunta se
  está correto** antes de emitir (Emitir nota, Emitir em lote, botão "Emitir NFS-e"): "Sim, emitir", "Não — é
  duplicada" (cancela o lançamento sem emitir) ou "Decidir depois". A mensalidade normal (um mês depois), o 13º e
  serviços com outra descrição não são barrados.
- **No automático** (baixa pelo banco, conciliação, robô) não há a quem perguntar: a nota fica parada como
  **"Possível duplicidade — confirmar"** e o botão "Emitir NFS-e" pede a confirmação. O painel de saúde aponta esses títulos.
- **Resposta perdida:** se a prefeitura/Sefin não responde depois do envio (tempo esgotado), a nota pode ter saído. O
  sistema não reenvia sozinho (antes reenviava e podia sair outra nota): fica "Em emissão — conferir no portal". Falha
  antes do envio (servidor recusou a conexão) continua sendo tentada de novo pelo robô.
- **Nota que existe no portal mas não no sistema:** em Contas a receber › Mais › "Já tem NFS-e emitida (informar o
  número)" grava o número no título, e o sistema nunca emite outra para ele (nada é enviado à prefeitura).

### Estorno de pagamento (ex.: cliente pagou o boleto errado)

Ao estornar a baixa de um título, a NFS-e que ainda não saiu volta a **aguardar o pagamento** quando a regra do título
é emitir na baixa (Configurações › Emissão, ou a regra da recorrência do cliente). Antes ela ficava "Pendente" e o robô
emitiria a nota de um honorário não pago. Nota já emitida não muda (para desfazer, cancele ou substitua a NFS-e). Na
atualização, os títulos que já tinham sido estornados e ficaram "Pendente" são corrigidos sozinhos (só os que tiveram
baixa registrada).

### Recorrência salva gera o título do mês na hora

Ao salvar a recorrência de um cliente (botão "Salvar alterações" ou o cadastro da recorrência), se o mês de início
já chegou e o dia de geração do mês já passou (Configurações › Financeiro, padrão dia 1), o título do mês aparece
**na hora** no Contas a receber, e o robô roda em segundo plano para registrar o boleto/PIX e emitir a NFS-e conforme
a regra. Clientes "a confirmar" (sem "Repetir todo mês") e inícios em meses futuros não geram nada. A rotina rápida
(a cada 15 minutos com o sistema aberto) também gera os títulos da recorrência, sem depender da rodada de hora em
hora. Salvar de novo não duplica o título.

### Recorrência: início, fim, acréscimos e descontos

Cada recorrência tem **mês de início** e **mês final** (opcional): depois do mês final não são gerados novos títulos.
Em **Mais**, a seção *Acréscimos e descontos* lança valores com descrição, **únicos** (só um mês) ou **recorrentes**
(do início ao fim, ou sem fim). Eles são somados ao honorário no título do mês, e a descrição mostra a composição
(ex.: "HONORÁRIOS (honorário R$ 1.000,00; + Alteração contratual R$ 300,00; - Desconto R$ 100,00)").

### Pagamento → nota fiscal na hora

Toda baixa passa pelo mesmo caminho — boleto ou PIX pago no Inter (consulta automática do robô), extrato conciliado,
cartão ou **baixa manual** (botão *Baixar* em Contas a receber): se a NFS-e do título espera o pagamento (regra
"Emitir na baixa") ou ainda não saiu, ela é emitida na hora, em produção, e a tela mostra o número da nota (ou o
motivo, se a prefeitura recusar — o robô tenta de novo). Em homologação a nota fica pendente.

A regra é **por empresa** (Configurações › Emissão). Com **"Emitir quando o cliente pagar"** a nota só sai na baixa do
título, automática (boleto/PIX recebido no Inter, extrato) ou manual. Cada empresa tem a sua regra. Clientes com regra própria na
Recorrência continuam com a deles, e a regra pode ser trocada a qualquer momento em Configurações.

O boleto do Inter é **boleto com PIX**: o PDF traz o código de barras e o QR Code do PIX. Por isso, quando o PDF vai
junto (anexo no e-mail ou documento no WhatsApp automático), o PIX copia e cola não é repetido no texto. Ele continua
quando não há PDF (cobrança só PIX, link manual de WhatsApp) e pode ser religado em Configurações › Cobrança.

### Proteção da tela local

A tela roda em `http://127.0.0.1:porta` e sua API só aceita pedidos vindos da própria tela: um site qualquer aberto no
mesmo computador não consegue comandar o sistema (nem mandar um "pacote de atualização" falso), com ou sem PIN. O pacote
de atualização também é recusado se trouxer caminhos fora da pasta do programa.

### Tela adaptativa

O conteúdo ocupa a largura toda do monitor. Em notebooks e monitores menores (até 1700px) o menu lateral vira só
ícones (o nome aparece ao passar o mouse), as margens diminuem e as tabelas largas encolhem os campos — a Recorrência,
por exemplo, cabe inteira de 1280px para cima, sem rolagem lateral. No celular o menu vai para cima e as tabelas viram
cartões.

### E-mails e WhatsApp dos clientes (planilha)

Em **Clientes › Importar e-mails e WhatsApp (CSV)**, escolha a planilha (colunas CPF/CNPJ, Celular e E-mail, ou a
exportação de contatos com departamentos — vale o contato do Financeiro). Só clientes **já cadastrados** são
atualizados (empresas fora do cadastro aparecem só como aviso); WhatsApp só de celular; e-mails provisórios
("aguardando@…") e do próprio escritório são ignorados. Por padrão só preenche o que está vazio (telefone fixo é trocado
pelo celular); a opção "substituir" troca também os já cadastrados.

### Inadimplência e recorrência

- A aba **Atrasados** mostra também os títulos em cobrança que ainda não têm boleto (com o motivo, se o banco recusou).
- A **inadimplência importada do Nitrus** continua na régua de cobrança **sem gerar boleto** (já vinha sendo cobrada):
  as mensagens levam o PIX da chave do escritório com o valor atualizado. O vencimento original é mantido; boleto só se
  pedir, pelo botão *Gerar boleto* do título.
- As datas de vencimento nunca são prorrogadas pelo sistema.

### Pagamento parcial

Quando o cliente paga menos que o devido (Pix, transferência, extrato ou baixa manual), o título é baixado com o valor
recebido e o sistema **pergunta o que fazer com a diferença** — na própria baixa manual, ou pelo botão *Decidir
diferença* em Contas a receber (o Painel avisa quando há pagamento parcial esperando decisão):

- **Cobrar a diferença**: cria uma nova conta a receber com a diferença, com vencimento em 5 dias e boleto próprio
  (régua de cobrança normal).
- **Conceder desconto**: a diferença é perdoada.

A **NFS-e sai só pelo valor pago** (multa e juros nunca entram na nota). Cobrando a diferença, o restante dos
honorários sai na nota do saldo, quando ele for pago; se faltou só multa e juros, o saldo não tem nota. Enquanto a
decisão não é tomada, a nota e o agradecimento ao cliente aguardam. O estorno desfaz tudo (e cancela o saldo em aberto).

### Um boleto por título (sem custo de boletos novos)

O sistema registra **um único boleto por título** e a régua reenvia sempre esse mesmo boleto — atrasado também: o
banco calcula a multa e os juros no pagamento. Nunca é registrado um boleto novo "recalculado". Se o Inter derrubar o
boleto (passou o prazo de pagamento após o vencimento, em Configurações › Cobrança, máximo de 60 dias), ele também não
é refeito: as mensagens seguintes levam o **PIX da chave do escritório** com o valor atualizado (sem custo), e o
pagamento é baixado pelo extrato.

**Título já vencido** (ex.: inadimplência importada): o banco não aceita vencimento no passado, então o único boleto é
registrado com o **valor atualizado** — original + multa + juros até o dia do registro — e vence em 5 dias
(Configurações › Cobrança). Ele **não** tem nova multa; depois do novo vencimento o banco cobra só juros diários sobre o
valor original (sem juros sobre juros). O boleto traz a composição ("Original R$ … venc. … + multa e juros até …"), e as
telas e mensagens mostram o mesmo valor do boleto. A NFS-e sai pelo valor dos honorários: multa e juros são receita
financeira, fora da base do ISS.

### Datas e meses sempre em português

Os campos de data são digitados no padrão brasileiro (**dd/mm/aaaa**, com máscara e botão de calendário) e os de mês
são escolhidos por extenso (janeiro…dezembro + ano), qualquer que seja o idioma do navegador ou do Windows. Data
impossível (ex.: 31/02) fica marcada em vermelho e não é aceita.

### Licença de uso: serial mensal ou anual

O sistema é liberado por **serial**, emitido pelo fornecedor, em dois planos: **mensal (mensalidade)** ou **anual
(anuidade)**.

- **Na instalação:** o `INSTALAR.bat` pede o serial antes de configurar a empresa (também dá para colar o caminho do
  arquivo `.lic`). Sem serial o sistema não abre: a tela mostra o pedido do serial na primeira abertura. O serial é
  emitido para o **CNPJ da empresa principal** e, numa instalação nova, já grava esse CNPJ.
- **Renovar:** em Configurações › Licença de uso, cole o novo serial `NFSE1-…` ou abra o arquivo `.lic`. O cartão
  mostra o plano (Mensalidade/Anuidade), o licenciado e a validade.
- **Aviso:** 10 dias antes do vencimento o Painel avisa. Depois de vencida, há 5 dias de carência com aviso.
- **Bloqueio:** passada a carência, emissão de notas, cobrança, conciliação e o robô param. Os dados continuam
  guardados; dá para abrir a tela, fazer backup e informar o novo serial, e tudo volta na hora.
- **Proteções:** o serial é assinado digitalmente pelo fornecedor (alterar plano, validade ou CNPJ invalida o serial);
  data do computador atrasada de propósito é detectada; apagar o arquivo de controle não reinicia nada.
- O serial pode limitar a quantidade de empresas da instalação.
- **Avaliação (opcional, fornecedor):** para distribuir com dias de teste sem serial, preencha `"dias_de_teste"` no
  `fornecedor.json` (padrão: 0, serial obrigatório). Nesse arquivo também ficam nome, WhatsApp e e-mail do fornecedor,
  mostrados na tela do serial.

### Importar inadimplência do Nitrus

Em **Contas a receber › Importar do Nitrus**, escolha o PDF do relatório *Inadimplência*. O sistema lê os títulos,
confere com os totais impressos no relatório e mostra, por cliente, o vínculo com o cadastro (pelo código do Nitrus,
CPF/CNPJ ou nome). Quem não tiver cadastro pode ser cadastrado ali, informando o CPF/CNPJ. Cada título entra com o
vencimento original (multa e juros pelo atraso), na régua de cobrança sem boleto, e a **NFS-e só sai quando o cliente
pagar**; título já lançado não repete. A conferência mostra a situação de cada título que já está no sistema (em
cobrança, **fora da cobrança**, pago) e o lançamento **recoloca em cobrança** os que estavam fora — reimportar o
relatório garante que toda a inadimplência esteja lançada e sendo cobrada.

### Filtros por coluna

As listas de Contas a receber, Contas a pagar, Notas emitidas, Clientes, Cobrança e Conciliação têm uma linha de
filtros logo abaixo do cabeçalho: texto livre por coluna (cliente, vencimento, valor, descrição — sem diferenciar
acento ou maiúscula) e lista de opções para Situação, NFS-e, Categoria, Etapa e Status. A linha acima da tabela mostra
quantos itens sobraram e a soma dos valores filtrados; **Limpar filtros** volta tudo. O filtro continua valendo quando
a lista é atualizada (depois de uma baixa ou edição). Os filtros combinam com as abas e com a competência.

### Editar título e refazer o boleto

Em **Contas a receber › Mais › Editar título** mudam valor, vencimento, competência e descrição de um título em
aberto. Se o valor ou o vencimento mudar e o título já tiver boleto, o boleto antigo é **cancelado no Inter** (o
cliente não pode pagar o valor errado), o PDF antigo é descartado e um boleto novo é registrado com os dados
corretos; a próxima cobrança já vai com ele. PIX próprio é regerado; cobrança "sem boleto" continua sem boleto.
Título com NFS-e emitida não muda de valor nem de competência (cancele ou substitua a nota antes, ou use o desconto
na baixa); o vencimento pode mudar.

O **Painel** avisa quando um título em aberto (deste mês em diante) está com valor diferente do que a recorrência dá
hoje (honorário + acréscimos − descontos do mês), com o atalho "aplicar o valor da recorrência e refazer o boleto".

Ao alterar o **valor de uma recorrência** (aba Recorrência, em lote ou pela janela do cliente), o sistema pergunta se
o novo valor vai também aos títulos em aberto já gerados deste mês em diante: cada um é editado e tem o boleto
refeito. Competências passadas e títulos com NFS-e emitida ficam como estão.

### Cobrança jurídica (aba Jurídico)

Quando o escritório decide levar um cliente ao jurídico, em **Contas a receber › Mais › Enviar para o jurídico**
(em qualquer título em aberto do cliente) o sistema:

- **suspende a cobrança na hora**: as mensagens de e-mail e WhatsApp ainda pendentes são canceladas e a régua, a
  cobrança recorrente, o botão "Cobrar" e o robô não mexem mais nesses títulos;
- por padrão envia **todos os títulos em aberto do cliente** (desmarque a opção para enviar só um);
- guarda a data e uma observação (advogado, nº do processo, acordo);
- mantém o valor **registrado e devido**: os títulos saem das abas "A receber" e "Atrasados" e passam para a aba
  **Jurídico**, com multa e juros correndo e o valor atualizado; o Painel mostra o total em cobrança jurídica e a
  inadimplência continua contando esses valores.

O boleto já registrado no banco **não é cancelado**: se o cliente pagar, a baixa cai normalmente (e a NFS-e "após o
pagamento" sai pelo valor pago). A baixa manual também funciona. **Voltar do jurídico** (menu Mais da aba Jurídico)
retoma a cobrança normal.

### Tomador pessoa física só com CPF e nome (Emissor Nacional)

Na DPS do Emissor Nacional o endereço do tomador é **opcional** (grupo `toma/end` com `minOccurs="0"` no XSD v1.01):
basta CPF/CNPJ e nome, como no portal nfse.gov.br. O sistema só exige endereço completo (CEP, código IBGE, UF) no
**webservice de Itaboraí**, cujo manual torna os campos de endereço obrigatórios. No Nacional, endereço preenchido
pela metade (ex.: CEP com 5 dígitos) é apontado para corrigir ou deixar em branco. O nome precisa estar no cadastro
(o portal busca o nome na Receita pelo CPF; o sistema não consulta serviços de terceiros). Se essa nota tiver
cobrança, o boleto do Inter continua exigindo endereço (regra do banco): sem ele a cobrança sai pelo PIX do
escritório e o boleto é registrado quando o endereço for preenchido.

### Importar todos os contatos da planilha (S3D: empresas e contatos)

Clientes › "Importar e-mails e WhatsApp (CSV)" lê a exportação de empresas e contatos (uma linha por contato, com
Departamentos). Para cada cliente **já cadastrado na empresa aberta**: o e-mail/WhatsApp principal vazio é preenchido
com o contato do Financeiro, e **todos os outros e-mails e celulares** da empresa entram como contatos adicionais (que
também recebem as mensagens). Nada que já está no cadastro é apagado nem repetido; trocar o principal só com
"Substituir". Ignorados: e-mails provisórios ("aguardando@…"), do próprio escritório, telefones fixos e de enfeite. Com
várias empresas, importe o mesmo arquivo com cada empresa aberta: cada uma recebe só os contatos dos clientes dela.

### Vários e-mails e WhatsApp por cliente

No cadastro do cliente (Clientes › Editar), além do **e-mail e telefone principais** (os que vão na NFS-e e no
boleto do Inter), há **Outros e-mails** e **Outros WhatsApp que recebem as mensagens** (separados por ponto e
vírgula). Cobranças, boletos, lembretes, notas fiscais, agradecimentos e avisos de suspensão vão para **todos**: por
e-mail numa única mensagem com todos os endereços; pelo WhatsApp do escritório, a mesma mensagem (e o PDF) para cada
número; pela API oficial, um envio por número. O botão "Cobrar" também envia para todos. No "Enviar manualmente em
sequência" (WhatsApp sem conexão) o link abre no número principal. E-mail ou número inválido é recusado ao salvar;
importações de contatos e do Nitrus não apagam os adicionais.

### Mensagens (e-mails e WhatsApp enviados)

A aba **Mensagens** mostra tudo o que o sistema mandou: cobranças, boletos, lembretes, notas fiscais, agradecimentos,
resumos, fechamentos e testes, por e-mail e pelo WhatsApp (WhatsApp Web ou API oficial). Para cada mensagem: data e
hora, canal, cliente e destinatário, tipo, assunto, anexos e situação (**Enviada** ou **Falha**, com o motivo dado
pelo servidor). Os cartões do topo trazem os envios de hoje, a fila do WhatsApp e as falhas dos últimos 7 dias.
Filtros por período, canal e situação (e por coluna). **Ver** abre o texto completo; **Reenviar** remonta a nota
fiscal (PDF/XML) ou a cobrança (valor atualizado) e, nos demais casos, repete o texto. Ao atualizar, o histórico da
régua já enviado entra na aba (sem o texto, que antes não era guardado). Cada empresa vê só as suas mensagens.

### Conciliação: extrato completo

A Conciliação mostra **todo o extrato** importado (entradas e saídas), com o que cada lançamento virou: recebimento
de título, despesa, transferência ou aporte. Pix/TED da própria empresa vira *transferência entre contas*
automaticamente (não é receita nem despesa). Os pendentes podem ser classificados (transferência, aporte do sócio,
outra receita, saída sem despesa) ou lançados como despesa; a classificação vale para os outros da mesma origem.

O extrato do Inter pela API traz **todos** os lançamentos da conta (Pix enviados e recebidos, pagamentos, tarifas).
As saídas viram despesas pagas e as entradas baixam os títulos sozinhas, por isso em "não conciliados" só fica o
que o sistema não reconheceu. O cartão do Inter mostra quantos lançamentos já vieram (entradas e saídas, período), e
o "Extrato da conta" abre no último mês com movimento quando o mês atual ainda não tem lançamentos.

Saídas que viraram **despesa automática** aparecem no Extrato da conta com a classificação ao lado do valor (as que
ficaram em "Outras" são destacadas para revisar). A lista segue as linhas da DRE: despesas com pessoal (Folha,
Pró-labore, Encargos, Benefícios), de ocupação (Aluguel, Energia/Internet, Condomínio), administrativas (Sistemas,
Contador/Assessoria, Serviços de terceiros, Marketing, Material, Outras), tributárias (Impostos, Taxas) e financeiras
(Bancárias, Juros, Tarifas). O grupo **Fora da DRE** (Distribuição de lucros / retirada do sócio, Transferência entre
contas, Saída sem despesa) tira o lançamento das despesas, porque não é custo da empresa. A escolha vale para as outras
da mesma contraparte e vira regra para as próximas. **Desfazer** cancela a despesa automática e devolve o lançamento para "não conciliados";
o robô não a recria.

**Recebimento de título já baixado pelo banco**: quando o boleto foi pago e o Inter já deu a baixa, a entrada do
extrato ("Boleto de cobrança recebido …") é ligada sozinha ao título pago do mesmo cliente e valor. Se houver dúvida,
a sugestão aparece como **✔ Já pago · Cliente**; e em qualquer lançamento a opção **Vincular a um cliente / título…**
abre a busca por cliente (títulos em aberto e pagos sem lançamento). Vincular a um título já pago **não** dá nova
baixa: só registra de onde veio o dinheiro.

### E-mails enviados pelo sistema

| E-mail | Para | Quando |
|---|---|---|
| Lembrete (vence em N dias), Vence hoje, Em atraso | cliente | régua de cobrança e botão "Cobrar" |
| Resumo financeiro | dono do escritório | todo dia (robô) ou "Enviar resumo" |
| Fechamento financeiro do mês | dono do escritório | no dia configurado (padrão: dia 3) |
| Teste de e-mail | quem você indicar | Configurações › E-mail |

Os e-mails de cobrança saem em **HTML formatado** (cabeçalho com a empresa e a etapa, tabela com referência,
competência, vencimento, valor e NFS-e, botão "Pagar com cartão", linha digitável, PIX copia e cola e boleto em
PDF anexo) e com versão em texto simples para leitores que não mostram HTML. Em atraso, mostram o valor
atualizado com multa e juros e o link do cartão passa a cobrar esse valor + a taxa. Nomes em maiúsculas são
ajustados na saudação ("RPS Consultoria e Servicos de Engenharia LTDA").

### Cartão de crédito (InfinitePay) — taxas por conta do cliente

Em **Configurações › Cartão de crédito**, escolha InfinitePay e informe a sua **InfiniteTag** (no app, canto
superior esquerdo, sem o $) e a taxa do crédito à vista do **seu plano** (Perfil › Taxas no app).
**As taxas do cartão ficam sempre por conta do cliente:** a taxa do crédito à vista (e a fixa, se houver) é
somada ao valor do link, e o parcelamento é escolhido pelo cliente na tela da InfinitePay com os juros pagos por ele
— deixe ligado no app "juros do parcelamento por conta do cliente". Os juros do parcelamento não entram como
receita do escritório.
- Cada cobrança leva, além do boleto/PIX do Inter, o link **"Pagar com cartão"** criado pela API da InfinitePay. O
  valor no cartão = honorário + acréscimo calculado para que, descontada a taxa, o escritório receba o honorário
  cheio (Lei 13.455/2017 permite preço diferente conforme o meio de pagamento). A mensagem avisa que pelo boleto
  ou PIX não há acréscimo.
- Quando o pagamento aparecer no app da InfinitePay, clique em **Pago no cartão** no título. Se colar o link do
  comprovante (com `slug` e `transaction_nsu`), o sistema confere o pagamento na InfinitePay antes da baixa.
- Na baixa: título pago pelo valor do cartão, taxa lançada em contas pagas (Bancárias), boleto do Inter cancelado
  e, se a NFS-e ainda não saiu, ela é emitida pelo valor total (o acréscimo integra o preço do serviço e a
  receita bruta do Simples).
- Limites da InfinitePay: a confirmação automática exige webhook num endereço público (o sistema roda no seu
  computador), por isso o clique em "Pago no cartão"; e links não são cancelados pela API — se o cliente pagar
  pelos dois meios, estorne pelo app.

### Copiar a última nota do tomador

Em **Emitir nota**, ao escolher o cliente aparece a **última NFS-e emitida para ele** (número, data, competência,
valor e descrição) com o botão **Copiar dados da última nota**: preenche valor, serviço, descrição e os campos de
"Mais campos da nota" (local, descontos, obra, evento, intermediário…). Campos que valem para uma nota só
(substituição, NFS-e referenciada, documentos de dedução, reembolso e nº do pedido) não são copiados. Em
**Notas emitidas**, o botão **Copiar** de cada linha faz o mesmo a partir de qualquer nota. Confira sempre o
valor e o mês na descrição antes de emitir.

### Casos raros da NFS-e (exterior, dedução por documentos, emissão pelo tomador)

- **Cliente do exterior** (Clientes › "Cliente do exterior"): sem CPF/CNPJ, com NIF (ou o motivo de não ter),
  país, cidade, estado/província e código postal. Na NFS-e Nacional sai com `NIF`/`cNaoNIF` e `endExt`; no
  webservice de Itaboraí, como pede o manual: CPF/CNPJ, IM e IE vazios, `Nif`, `CodigoPais` (BACEN) e
  `CidadeEstrangeiro`. Não gera boleto (o Inter exige CPF/CNPJ): receba por câmbio e dê baixa manual.
- **Exportação de serviço** (Mais campos da nota › Exterior): país da prestação, moeda e valor na moeda,
  modo de prestação, vínculo, mecanismos de apoio, DI/RE e envio ao MDIC (grupo `comExt`). Com Situação do
  ISS = Exportação, o grupo é obrigatório e o sistema confere antes de enviar.
- **Dedução por documentos** (canal nacional): liste as NF-e, NFS-e ou recibos que comprovam a dedução
  (`docDedRed`); a soma vira a dedução da base do ISS.
- **Emissão pelo tomador ou intermediário** (`tpEmit` 2/3, ex.: importação de serviço): o cliente escolhido é o
  prestador do serviço e esta empresa entra como tomadora/intermediária. Essa nota não entra no contas a receber.

### Extrato do Banco Inter pela API (conciliação sem arquivo)

Com o Inter configurado, o robô baixa o extrato da conta direto do banco (API Banking v2,
`/banking/v2/extrato/completo`) **a cada 15 minutos enquanto o sistema está aberto** (intervalo em Configurações ›
Robô, mínimo 5) e de hora em hora pelo agendador do Windows; continua de onde parou e concilia sozinho, como no OFX.
A mesma rotina rápida dá as baixas do Inter, emite as notas dos pagos e envia as notas aos clientes. O cartão do
Inter na Conciliação mostra a última e a próxima busca. Dar baixa, emitir nota ou vincular um lançamento dispara a
rotina na hora.
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

São 266 testes, que cobrem o emissor (municipal e nacional), o financeiro e as automações:
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

**Testes de tela no navegador** (`tests/ui`): sobem o sistema com dados de exemplo e percorrem todas as páginas
em desktop, tema escuro, celular e notebook, acusando erro de JavaScript, erro do servidor, rolagem horizontal
e textos que transbordam. Rodam com `NFSE_TESTE_TELA=1 python -m pytest tests/test_tela_navegador.py`
(precisa de Node.js e de `npm install` em `tests/ui`).

**Teste funcional de ponta a ponta** (`tests/ui/funcional.js` + `tests/ui/servidor_completo.py`): sobe o sistema em
modo de teste com a prefeitura, o Sefin/ADN, o Banco Inter (TLS mútuo) e o e-mail **simulados** e usa a tela como
um usuário, conferindo o resultado de 63 funções: clientes (inclusive do exterior e importação de XML),
serviços, configurações e testes de conexão, emissão em homologação e em produção simulada (Itaboraí e
Nacional), lote, cópia da última nota, cancelamento, substituição, exportação, emissão pelo tomador, contas a
receber (boleto, baixa, estorno, cobrança, PDF, CSV, cancelamentos), recorrência, régua, contas a pagar,
conciliação (OFX, extrato do Inter, vínculo manual), relatórios e fechamento, backup (com senha e restauração),
PIN, multiempresa, validação, atualização e encerramento. Roda junto com a varredura quando
`NFSE_TESTE_TELA=1`.

**Integração contínua:** a cada envio ao GitHub, `.github/workflows/testes.yml` roda todos os testes em Python
3.10 e 3.12 e a varredura de tela no Chromium.

**Código da tela:** `nfse_itaborai/web/js/` em arquivos por assunto (01_base, 02_comum, 03_painel, 04_notas,
05_financeiro, 06_relatorios, 07_cadastros, 08_configuracoes, 09_inicio), carregados em ordem pelo `index.html`.

## Limitações conhecidas

- **Situação Tributária / Tipo de Retenção de PIS/COFINS/CSLL (Nota Técnica 005):** o XSD atual não tem
  esses campos. Notas **sem retenção federal**, que é o caso normal de um prestador do Simples Nacional, não
  são afetadas. Se uma nota com retenção de PIS/COFINS/CSLL for rejeitada, o erro da prefeitura aparece na
  tela e em `retorno.xml`.
- Erros de rejeição: o formato foi reproduzido do ACBr, e o retorno bruto fica sempre salvo em `retorno.xml`.
