# Sistemas de controle de obrigações acessórias e gestão de processos para escritórios contábeis: engenharia reversa funcional (2025-2026)

> Pesquisa feita em outubro de 2026 com fontes públicas: sites dos fornecedores, centrais de ajuda, documentação de API, e-books de suporte e Reclame Aqui.
> Nenhum sistema foi acessado com login. Quando algo é **inferência** e não está escrito na fonte, o texto diz isso.
> As URLs estão no fim de cada seção e na lista consolidada (seção 12).

---

## 1. Sumário executivo

- O mercado tem dois tipos de produto:
  1. **"Hubs de obrigações" independentes de ERP**: Acessórias, Nibo Obrigações e Omie.G-Click.
  2. **Módulos de processos acoplados ao ERP contábil**: Domínio Processos / Onvio Processos (ex-Gestta, da Thomson Reuters), Questor Zen/Quiu e Alterdata eContador/eTarefas.
- **Todos usam o mesmo modelo central**:
  - `Empresa (cliente)` → `perfil/regime` → `obrigação (modelo com regra de prazo)` → `entrega/tarefa por competência` → `documento anexo` → `envio ao cliente` → `protocolo de ciência`.
- **A detecção automática de entrega é sempre indireta.** Nenhum dos sistemas analisados confirma a entrega consultando o e-CAC.
  - O FAQ oficial do Gestta diz textualmente "Não" à pergunta sobre verificar DCTF no e-CAC.
  - A "entrega" é dada como feita quando aparece um **documento comprobatório** (guia, recibo, relatório) que o sistema consegue **casar** com uma tarefa pendente pelo trio **(identificador do cliente + tipo de obrigação + competência)**.
- **Mecanismos de casamento encontrados:**
  1. Integração direta com o ERP contábil (concluir no Domínio conclui no Processos; Contmatic, Contabit e Consisa empurram PDFs ao e-Contínuo; Jettax empurra guias apuradas).
  2. Leitura do conteúdo do PDF por **templates/âncoras**:
     - Nibo "robôs";
     - G-Click "ValidaPDF";
     - Domínio "Express + Templates de Documento";
     - Acessórias "e-Contínuo + base de conhecimento homologada".
  3. **Padrão no nome do arquivo** (G-Click "Anexo por nome").
  4. **Pasta monitorada** por um agente desktop (Nibo Assistente, G-Click InNubem, que também aceita Google Drive, Domínio Express "pasta local" e e-Contínuo).
  5. **Upload por API** (`POST https://api.acessorias.com/econtinuo`).
  6. **OCR** para PDFs-imagem. Já existe no Domínio Express, no G-Click desde 01/2025 e no e-Contínuo OCR com "Processamento Avançado" desde 07/2026.
- **Oportunidade clara para um sistema próprio:**
  - Usar o **Integra Contador (SERPRO)** para confirmar entrega e pagamento de verdade: recibos de PGDAS-D e DCTFWeb, Caixa Postal etc.
  - Os concorrentes só exploram isso de forma lateral: Nibo "Radar e-CAC" e G-Click + "Consulta eCAC", ambos voltados a pendências e não à baixa de entrega.

---

## 2. Seleção dos sistemas (6+1) e justificativa

Não existe dado público e auditável de *market share* nesse nicho. A seleção abaixo combina quatro critérios:

- presença comercial e integrações cruzadas;
- base declarada de clientes;
- vínculo a ERPs contábeis grandes;
- volume de documentação pública.

| # | Sistema | Fornecedor | Por que entrou |
|---|---|---|---|
| 1 | **Acessórias** | Acessórias Soluções Inteligentes Ltda (BH/MG, CNPJ 39.768.096/0001-78) | Referência do nicho "controle de obrigações". Parceiro do Clube + Fenacon. Integrações nativas com Contmatic, Contabit, Consisa, Jettax, Digisac e Komunic. API REST e **servidor MCP** públicos. |
| 2 | **Domínio Processos / ONVIO Processos (ex-Gestta)** | Thomson Reuters | O Domínio é um dos ERPs contábeis mais usados no Brasil. A TR comprou o Gestta e o integrou ao Domínio. Em 2025-2026 a central de suporte usa o nome "Domínio Processos". |
| 3 | **Nibo Obrigações / Obrigações Plus** | Nibo | Declara "+15 mil clientes". Robôs de leitura configuráveis pelo usuário, recálculo de DAS/DARF e Radar e-CAC. |
| 4 | **Omie.G-Click** | Omie (comprou a G-Click em 2021, que tinha 26 mil usuários) | Documentação mais detalhada do mercado: perfis E/OU/Exceto, ValidaPDF, validação por nome, robô InNubem. Integra com Fortes, Questor, Alterdata, SCI e Onvio. |
| 5 | **Questor Zen + Quiu** | Questor Sistemas | ERP contábil grande. O robô Quiu executa rotinas e dá "baixa" publicando no portal Zen. Documentação pública rasa. |
| 6 | **Alterdata eContador / eTarefas** | Alterdata (Pack) | ERP grande, com portal do cliente e eTarefas. Usa a API Integra Contador do SERPRO no Pack. |
| +1 | **Jettax 360** (complementar) | Jettax | Não controla obrigações. **Apura e gera guias** e as **empurra** para Acessórias e G-Click, inclusive guias recalculadas. Vale estudar como "fonte de documentos". |

Ficaram de fora, com o motivo:

- **SIEG**: captura de XML/NF-e, integra com Jettax; não é controle de obrigações.
- **Fortes, Contmatic, SCI, Contabit, Consisa**: são ERPs que *alimentam* os hubs.
- **Veri, Contaí, Contabilizei**: são escritórios ou produtos B2C.

---

## 3. Acessórias (acessorias.com)

### 3.1 Modelo de dados (inferido da API pública `api.acessorias.com/documentation`)

Entidades e endpoints:

- `Companies`, `Contacts`, `Tags`, `Users`, `Departments` (com hierarquia `IDPai`), `Groups` (grupos de empresas);
- `Matrices` (modelos de processo), `Processes`, `Requests` (solicitações);
- `Deliveries` (entregas/prazos), `Invoices`;
- `e-Contínuo` (upload para o robô) e `MCP`.

**Empresa** tem os campos: `Identificador` (CNPJ/CPF), `Razao`, `Fantasia`, `Status`, `UF`, `ClienteDesde/Ate`, `Honorario`, `Regime`, `GrupoDeEmpresas`, `InscricoesEstaduais[]`, `ContatosNaEmpresa[]` e `Departamentos[]`. Cada item de `Departamentos[]` traz o responsável (`RespNome/RespEmail`). A lista `Obrigacoes[]` traz contadores `Entregues/Atrasadas/Proximos30D/Futuras30+`.

**Entrega (Delivery)** tem os campos:

- `Nome`, `EntCompetencia`;
- `EntDtPrazo` (prazo técnico) e `EntDtAtraso` (prazo legal);
- `EntDtEntrega`, `EntMulta` (S/N);
- `Status` ("Ent. antecipada", "Pendente", "Atrasada!", "Entrega justificada");
- `EntGuiaLida` (o cliente leu?), `EntLastDH`;
- `Config` com: `Tipo` (O = obrigação / T = tarefa), `DptoID`, `RespPrazo` (dono do prazo) e `RespEntrega` (quem entregou).

Os filtros da API são `situation=pending,read,delivered` e `DtLastDH`, que permite sincronização incremental. O limite é de 100 requisições por minuto, com janela deslizante.

**Identificadores do cliente aceitos pelo robô** (5 ao todo): CNPJ, CPF, Inscrição Estadual, CEI e CAEPF. Também existem "Outros Identificadores" transferíveis entre empresas.

### 3.2 Geração da agenda

- **Regimes tributários** são pacotes de obrigações que **substituem** as obrigações da empresa.
  - Exemplo: trocar Simples por Presumido troca o conjunto inteiro.
- **Grupos de obrigações** apenas **adicionam** obrigações.
  - Servem para a "linha de produção" em que cada departamento acrescenta o seu grupo.
- Os pacotes são organizados por departamento.
- Cada obrigação tem:
  - **prazo legal**;
  - **prazo técnico**, definido em "dias antes", em **dias úteis ou corridos**;
  - regra para **prazo fixo que cai em dia não útil**: antes sempre antecipava, hoje há outras opções;
  - flag **"Sábado é útil?"**, usada por exemplo na folha;
  - opção "Caso não tenha demanda na competência" (ex.: "Ignorar");
  - **tempo previsto de execução**, usado no Método APLA para custo e lucratividade.
- Prazos técnicos e legais podem ser **editados por entrega**, com log, e **alterados em massa** pela Lista de Entregas.
- Um **processo** (matriz de passos) pode **criar obrigações**. Assim o e-Contínuo dá baixa em passos do processo, e o percentual de evolução fica visível ao cliente.
- Processos recorrentes podem rodar em dias do mês, dias da semana ou de segunda a sexta.

### 3.3 Como identifica que a obrigação foi entregue

1. **Baixa manual**: "entrega rápida", entrega informando protocolo/anexo ou **entrega justificada**.
2. **Robô e-Contínuo**:
   - É um agente instalado no Windows com estrutura de pastas locais (`Download`, `Upload/nProcessado`, `Upload/nIdentificados`, `Upload/ignorados`) e backup local.
   - Lê o PDF e identifica:
     - **tipo de documento + código** (ex.: GPS com código de pagamento);
     - **identificador do cliente** (os 5 tipos acima);
     - **competência**.
   - Depois **procura uma entrega pendente** com essa combinação e dá a baixa.
   - A resposta da API mostra o algoritmo:
     - Sucesso: `"Entrega processada com sucesso! [GPS - Guia da Previdência Social]"` com `pathFolder: "13/Geral/GUIAS/GPS/2022/01/Pessoal/2022-01-GPSMensalpdf.pdf"`, ou seja, `{empresa}/Geral/GUIAS/{tipo}/{ano}/{mês}/{departamento}/{arquivo}`.
     - Falha: `"Entrega [GPS para 30.637.209/0001-21] inexistente [Comp. 01/2022]"`, ou seja, o sistema achou tipo, CNPJ e competência, mas não havia prazo correspondente.
   - **Base de conhecimento por layout**: layouts novos (ex.: documentos identificados por CEI) passam por **"chamado de homologação"** no time da Acessórias. Os templates são mantidos pelo fornecedor, não pelo usuário.
   - **Multipages** (desde 2021): divide um PDF com várias guias, página a página. Exige mesmo tipo, código e competência, e no máximo uma página por cliente.
   - **e-Contínuo OCR** (2026): processa PDFs-imagem. O "Processamento Avançado" amplia e reprocessa campos pequenos (ex.: ISS em DAM/DAMSP). A fonte cita uma **"validação de autenticidade dos documentos"**, sem detalhar.
   - Uma obrigação pode **exigir baixa pelo robô**, e há permissão específica para desfazê-la.
3. **Integrações push**:
   - Contmatic, Contabit e Consisa sincronizam PDFs gerados no ERP para o e-Contínuo, com logs de documentos "a homologar".
   - Jettax envia as guias apuradas: DAS, DAS-MEI, Difal, ICMS-ST, ISS, DCTFWeb e também o DAS recalculado.
4. **API**: `POST /econtinuo` (multipart `arquivo`) processa qualquer PDF enviado por script. Isso permite integrar com o Google Drive por fora do produto.

### 3.4 Documentos, portal, envio e protocolo

- **E-mail** com remetente configurável e variáveis de template. Há **envio agrupado**: o "grupo de obrigações" só dispara quando todas as entregas do grupo estiverem prontas.
- **Protocolo Digital**: registra **data, hora e IP** de quando o cliente abriu o anexo. O relatório "PDF relação com comentários" serve como prova inclusive judicial.
- **Lembrete de guias não lidas**: e-mail automático X dias antes do vencimento, com prefixo do assunto personalizável.
- **Protocolo Físico** para entrega em papel (pacote do "boy").
- **Área VIP (web) e App personalizado**: calendário de guias, solicitações, formulários flexíveis que podem abrir processos, upload de **comprovante de pagamento** pelo cliente (2026) e NPS.
- **GED / AC Docs** (com status Pendente/Vencido/Recebido/Validado).
- **Komunic**: atendimento por WhatsApp com chatbot, filas e grupos, e notificações também por WhatsApp. Também há integração com Digisac.
- **AC Notifica** e **AC Certifica**: réguas de renovação de certificado.
- **Google Drive**: não há integração nativa citada na central de ajuda (130 artigos verificados). O backup é em estrutura de pastas local.

### 3.5 Alertas, painéis e KPIs

- **Tela de Insights**: dashboard flexível com indicadores por departamento, por colaborador ou numéricos.
  - O "Indicador clássico" traz: Docs não lidos, Semana, Prazo Técnico vencido, Atraso Legal, **Atraso com Multa**, Mês Atual, Próximos 30 dias e NPS.
- **Análise de Performance** (06/2026), por analista e por departamento:
  - % cumprimento de prazos;
  - % entregas antecipadas;
  - atrasos legais, justificados e sem justificativa;
  - **% de entregas que geraram multa**.
- **Método APLA**: custo por minuto do colaborador, lucratividade por cliente e capacidade produtiva.
- Segurança: MFA obrigatório desde 03/2026.

### 3.6 Preço e diferenciais

- **Preço**: não é público; contratação via demonstração. O Reclame Aqui tem queixas sobre reajuste de pacote.
- **Diferenciais**:
  - baixa automática com cinco identificadores;
  - protocolo com IP;
  - indicador de multas;
  - API e MCP abertos;
  - Komunic.

### 3.7 Pontos fracos

- **Reclame Aqui** (01-06/2026): nota 6,4/10 ("Regular"), 29 reclamações, 61,9% resolvidas, resposta média em 4 dias e 20 horas. Os temas foram:
  - mudança contratual unilateral;
  - dificuldade para cancelar;
  - reajuste de pacote.
- **Limitações vistas na documentação**:
  - novos layouts dependem de **homologação pelo fornecedor**, por chamado;
  - o OCR "não garante 100%";
  - o e-Contínuo roda em desktop;
  - não há conector nativo com Google Drive.

**Fontes:**
- https://acessorias.com/site/
- https://acessorias.com/site/integracoes/
- https://acessorias.com/site/e-continuo-automacao-inteligente-para-escritorios-contabeis/
- https://api.acessorias.com/documentation
- https://app.acessorias.com/sysajuda.php: artigos p=3, 42, 43, 44, 45, 61, 62, 70, 82, 84, 96, 99, 100, 111, 127, 144, 153, 195, 216, 248, 354, 585, 586, 591
- https://www.reclameaqui.com.br/empresa/acessorias-com/lista-reclamacoes
- https://fenacon.org.br/noticias/acessorias-e-o-novo-parceiro-do-clube-fenacon/

---

## 4. Domínio Processos / ONVIO Processos (ex-Gestta), da Thomson Reuters

### 4.1 Modelo de dados

- **Cliente**: importado do Domínio Contábil, já **com o regime tributário**. Não dá para cadastrar cliente direto, porque o vínculo é obrigatório com o Domínio.
- **Departamento**: cada funcionário fica vinculado aos departamentos de cada cliente, e a responsabilidade é atribuída automaticamente.
- **Usuários de cliente** recebem as notificações.
- **Agrupadores de clientes** funcionam como filtros. **Agrupadores de tarefas** definem pacotes.
- **Tarefa recorrente** tem os campos:
  - Nome;
  - **Concluir automaticamente** (quando todos os documentos estiverem anexados);
  - Esfera (Federal/Estadual/Municipal);
  - Frequência (diária, semanal, decendial, mensal, bimestral, trimestral, semestral, anual);
  - **Data Legal** (dia, ou dia/mês para anuais) e flag "Dia útil" (ex.: 5º dia útil);
  - **Postergar** quando cai em fim de semana ou feriado;
  - **Data Meta** (−N dias, opcionalmente úteis);
  - **Competência** (−1/0/+1 em relação ao mês de vencimento);
  - Departamento;
  - **Pontuação** (peso do cliente);
  - "Gerando multa" (flag de risco);
  - Notificar cliente via e-mail/WhatsApp;
  - checklist de atividades (com ou sem documento).
- **Ordem de Serviço** e **Fluxo de tarefas**: workflows não recorrentes a partir de templates.
- Também há **Certidões (CND)/Certificados** e **Apontamento de horas**.

### 4.2 Geração da agenda

- As tarefas do mês seguinte são geradas automaticamente **no dia 20** de cada mês. O dia é configurável.
  - Exemplo: no dia 20/09 são geradas as tarefas que vencem em outubro.
- Na geração manual, escolhe-se o **mês de vencimento**, não o de competência.
- **Tarefas geradas não podem ser editadas**: é preciso excluir, ajustar e gerar de novo.
- **Feriados** são cadastrados pelo escritório, com flag de recorrência anual.
- Há pacotes padrão de tarefas por regime.
- **Obrigações novas da legislação não são propagadas automaticamente** para a base. O escritório configura e distribui (FAQ Gestta).

### 4.3 Como identifica a entrega

1. **Integração Domínio → Processos**, a mais forte:
   - Ao concluir uma atividade no Domínio (cálculo da folha, apuração, geração do DAS etc.), a tarefa correspondente é concluída. Se houver documento, ele é anexado e enviado ao cliente.
   - Existe uma "Lista de atividades integradas".
   - Tarefas sem anexo só concluem pelo Domínio.
   - Uma tarefa com checklist só é concluída quando **todas** as etapas fecham.
   - A integração depende do **Agente de Comunicação**, que precisa estar verde e em execução, e de credenciais Onvio atualizadas. Se a senha muda, a falha é silenciosa.
2. **Express**, para upload em lote:
   - Lê **PDF (texto e imagem), XLS/XLSX e TXT**. Word não é aceito.
   - Busca as tarefas que batem com o documento:
     - card **verde**: uma tarefa encontrada;
     - card **amarelo**: mais de uma tarefa, o usuário escolhe;
     - "Tarefas NÃO encontradas" mostra o motivo, e o usuário pode editar e vincular manualmente.
   - Há opção de **pasta local monitorada**.
   - Em 2021 o FAQ dizia "apenas PDFs legíveis (copiáveis)". A versão atual já faz OCR.
   - Segundo fonte de terceiros, lê o **CNPJ e a data** e "bloqueia erros de envio", avisando quando o documento não bate com a tarefa.
3. **Templates de Documento**, usados para documentos gerados fora do Domínio (FGTS Digital, DCTFWeb, e-CAC):
   - **Regras de conteúdo**: palavras fixas que identificam o tipo, como "FGTS" ou "Guia de Recolhimento", "DARF" ou "DCTFWeb".
   - **Formato de data**: `DD/MM/AAAA`, `MMMM/AAAA`, `MM/AAAA` ou `AAAA`.
   - **"Validar pela Competência"**: ligar para documentos mensais e desligar para anuais ou avulsos.
   - Opção "Não confirmar quando validado com sucesso", que conclui e envia ao cliente sem intervenção.
   - Pasta de destino no Portal do Cliente.
   - "Enviar data de vencimento para o Portal".
   - Botão para testar com PDF real ("Subir Modelo e Salvar").
4. **Não consulta o e-CAC** (FAQ Gestta, pergunta 32).

### 4.4 Documentos, portal e envio

- **ONVIO Portal do Cliente**: ao concluir a tarefa, o arquivo vai para a pasta configurada. A estrutura padrão é por departamento (ex.: Fiscal > DAS).
  - Se o cliente não tem cadastro no portal, recebe um link direto por e-mail.
- **Templates de e-mail/WhatsApp** com variáveis (`${cliente}`, `${dataDeCompetencia}`, `${dataDeVencimentoDoDocumento}`).
  - Há "Cobrança de documentos" recorrente, configurável a cada N dias até o cliente enviar.
  - Folha e anexos podem ir **em lote** num único e-mail.
- **WhatsApp** só via **Domínio Messenger**, com QR Code conectado. O chat da tarefa mostra pendente, enviado, entregue e **baixado pelo cliente**.
- Ciência: a tarefa registra quando o cliente baixou o documento. O dashboard mostra tarefas "concluídas com documento não baixado" sujeitas a multa.

### 4.5 Alertas, painéis e KPIs

O dashboard muda conforme o perfil (Administrador, Gerente ou Usuário).

- **Prioridade**: Gerando multas, Atrasadas (passaram da meta) e Pendentes de aprovação.
- **Falhas de envio** (e-mail, Portal, WhatsApp).
- **Vencendo hoje**.
- **Sujeitas a multa**, para hoje e para os próximos 5 dias, incluindo as concluídas mas não baixadas pelo cliente.
- Indicadores por departamento: concluídas × metas, impedidas.
- Relatórios customizáveis, com exportação para Excel.
- Apontamento de tempo.

### 4.6 Preço e diferenciais

- **Preço**: módulo pago à parte, só para contratos **Plus e Premium** do Domínio (Start não tem acesso). O valor depende do número de usuários e do pacote; não há tabela pública.
- **Diferencial**: conclusão automática a partir do próprio ERP, o que nenhum hub independente consegue com o Domínio.

### 4.7 Pontos fracos

- Fica **preso ao ecossistema Domínio**:
  - o cliente precisa existir no Domínio;
  - a integração é "exclusiva da parceria";
  - não há documentação pública de API.
- Dependência do Agente de Comunicação e de credenciais.
- Tarefas geradas não são editáveis.
- Reclame Aqui (2023): dificuldade de **distinguir filiais com o mesmo nome** depois da integração.

**Fontes:**
- FAQ Gestta Processos integrado ao Contábil: https://images.engage.es-pt.thomsonreuters.com/Web/LALEYSAEIMPRESORA/%7Bfa3be1a4-eadc-479b-a994-f9e425ce049d%7D_TAX_PROF_BR_PDF_PERGUNTAS_E_RESPOSTAS_Base.pdf
- https://suporte.dominioatendimento.com/ctsfiles/ebookonvioprocessos.pdf?id=9426860&ds=centralSolucao
- https://suporte.dominioatendimento.com/ctsfiles/ebook_gestta_processos_ok1.pdf?id=9420151&ds=centralSolucao
- Central de Soluções: https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=8221 (manual), 7452 (templates), 9146 (Express), 12190 (Data Legal/Meta/Competência), 7487 (criar tarefas), 7517 (feriados), 7526 (dashboard), 11568 (WhatsApp), 7516 (templates de e-mail), 12159 (tarefa não concluída), 12304 (integração com Portal)
- https://andersonhernandes.com.br/gesta-o-que-e-como-funciona/
- https://www.reclameaqui.com.br/thomson-reuters/onvio-processos-identificacao-de-empresas_VNKHTtxNpf8x_7yC/
- https://www.dominiosistemas.com.br/blog/thomson-reuters-adquire-gestta/

---

## 5. Nibo Obrigações / Obrigações Plus

### 5.1 Modelo de dados

- **Escritório**: CNPJ, CRC, logo e sistema contábil, usado para exportar arquivos.
- **Usuários** com perfil Administrador ou Personalizado.
- **Clientes**: código, nome, CPF/CNPJ, CEI, CAEPF, IE, IM e contatos/destinatários.
- **Obrigação** tem os campos:
  - Nome, **Departamento**, **Apelido** (até 6 caracteres);
  - **Tipo**:
    - **Pagamento**: sempre enviado e vai para "Documentos a pagar" no portal;
    - **Declaração**: só arquivado na nuvem;
    - **Cadastral**: decidido no protocolo;
  - "Entrega somente física";
  - **Controle de vencimento**:
    - Frequência: decendial, quinzenal, mensal, bimestral, trimestral, quadrimestral, semestral ou anual;
    - **Meses de deslocamento** (0 = mesmo mês da competência, 1 = mês seguinte);
    - **Dia do vencimento**;
    - **Data não útil**: corridos sem alterar, corridos antecipando, corridos atrasando, ou dias úteis;
    - **Sábado é útil?**;
    - **Meta interna** (N dias úteis antes);
  - **Simular vencimento**;
  - Observação padrão;
  - Permissão por contato do cliente.
- **Novo vencimento pontual** por competência, sem mudar a regra.
- Há também **Protocolo**, **Robô** (com versões) e **Tarefas e Processos** (outro módulo).

### 5.2 Geração da agenda

- As obrigações federais padrão já vêm configuradas com recorrência e vencimento. O escritório adiciona as municipais e estaduais.
- O calendário pode ser visto por **Vencimento** ou por **Meta interna**.
- A documentação consultada não descreve regras automáticas por regime tributário; o vínculo entre cliente e obrigação é feito no próprio cadastro.

### 5.3 Como identifica a entrega

O Nibo exige **conferência humana**, mas a pré-preenche por robô.

- **Formas de entrada**:
  - arrastar o PDF;
  - **Nibo Impressora** (impressora virtual);
  - **Nibo Assistente**: agente Windows que **monitora pastas e subpastas** e envia arquivos novos para a Conferência. Rejeita arquivos anteriores à data de início do monitoramento. Pode tratar .txt/.rec de DCTF, DIRF e SPED. Não roda em Windows Server.
- **Robô padrão**: o fornecedor mantém uma lista de layouts suportados.
- **Robô personalizado**, criado pelo usuário num assistente:
  1. sobe-se um PDF de exemplo;
  2. marca-se o trecho fixo que identifica o documento (título ou cabeçalho);
  3. marca-se a posição de **cliente** (CNPJ/CPF preferencialmente, depois CEI, CAEPF ou IE; **só o nome não serve**), **competência**, **vencimento** e **valor** (última página);
  4. testa-se com arquivos de outros clientes.
  - Há **versões** do robô para quando o layout muda.
  - Para DCTFWeb, informam-se os **códigos de receita** (ex.: 0561, 0588) para separar IRRF de outras obrigações.
- A **Tela de Conferência** mostra os campos Cliente, Obrigação, Competência, Vencimento e Valor. Quando todos ficam verdes, o usuário clica em **Protocolar / Protocolar todos**.
  - Se o vínculo entre cliente e obrigação não existe, o sistema oferece criá-lo na hora.

### 5.4 Envio, portal e ciência

- **Tipo de entrega**:
  - **Digital**: e-mail + Nibo Empresa/portal;
  - **Arquivo Online**: só arquiva;
  - **Física**: baixa manual.
- **Protocolos**: para cada documento, mostra destinatários, quem recebeu, **quem abriu o e-mail** e **quem visualizou no portal**. A **baixa da visualização é automática** quando o cliente abre.
- **Recálculo automático de guias**:
  - Para DAS, DAS-MEI, DARF Sicalc e DCTFWeb (parcelamentos não).
  - Depois do vencimento, o próprio cliente recalcula no portal.
  - Usa o **certificado A1 do escritório com procurações**.
  - Valida se o **valor principal** é igual ao original e usa **OCR** para bloquear DARF com vários tributos.
  - Mostra se a guia foi **paga**, o que indica consulta à Receita.
- **WhatsApp oficial**, MeuApp (white-label) e **Radar e-CAC** (pagamentos, pendências e parcelamentos).

### 5.5 KPIs e relatórios

- **Produtividade**: no prazo × atrasado, por escritório, departamento e usuário.
- **Relatório Completo**.
- **Mapa de pendências** com 3 dimensões: Meta interna, Vencimento e **Visualização pelo cliente**. Permite baixa justificada em lote.
- **Auditoria**: Protocoladas, Protocoladas e não visualizadas, Concluídas.
- Exportação em XLSX, CSV ou PDF.
- A documentação consultada não cita métrica explícita de multa.

### 5.6 Preço e pontos fracos

- **Preço**: não há tabela pública. Um site concorrente cita "a partir de R$ 64/CNPJ/mês"; o dado não foi verificado e pode ser de outro módulo. Há promoções ("Black Nibo", "cobrimos a concorrência").
- **Reclame Aqui** (07/2025 a 06/2026): 53 reclamações, 90,6% respondidas, 65% resolvidas. Os temas foram:
  - emissão de NF, com um caso de cerca de 10 dias sem emitir;
  - conciliação em lote;
  - cobrança indevida após carência.
- **Limitações vistas na documentação**:
  - documento identificado só pelo nome do cliente não é reconhecido;
  - mudança de layout exige editar o robô;
  - o Assistente não roda em Windows Server e precisa de exceção no antivírus.

**Fontes:**
- https://ajuda.nibo.com.br/pt-BR/articles/7157220-introducao-ao-nibo-obrigacoes
- https://ajuda.nibo.com.br/pt-BR/articles/7174334-lista-de-obrigacoes
- https://ajuda.nibo.com.br/pt-BR/articles/7873582-robos-personalizados
- https://ajuda.nibo.com.br/pt-BR/articles/9853878-tela-de-conferencia
- https://ajuda.nibo.com.br/pt-BR/articles/8212592-recalculo-automatico
- https://ajuda.nibo.com.br/pt-BR/articles/8178973-relatorios-do-nibo-obrigacoes
- https://intercom.help/niboajuda/pt-BR/articles/8417298-nibo-assistente
- https://www.nibo.com.br/obrigacoes-plus/
- https://conteudo.nibo.com.br/nibo-obrigacoes-plus
- https://www.reclameaqui.com.br/empresa/nibo/lista-reclamacoes/
- https://www.planilhadefluxo.com.br/alternativa/nibo

---

## 6. Omie.G-Click

### 6.1 Modelo de dados

- **Obrigação**: assistente em 3 passos (dados e datas → atividades → **perfil**).
- **Atividades** por obrigação, de tipos como checklist, anexo, "Anexo por nome" e e-mail programado.
- **Perfil do cliente** é formado por "particularidades": tributação, Matriz/Filial, natureza (Imune/Isenta) e outras.
- **Perfil da obrigação** combina particularidades com lógica **E / OU / Exceto**.
  - Exemplo da DCTF: Matriz E (Imune OU Isenta OU Presumido OU Real), Exceto Simples.
- **Responsáveis**: fixo, fixo por cliente, por **cargo sugerido** ou exclusivo.
- **Obrigações esporádicas**, como parcelamentos, com "complemento".
- **Mapa de Obrigações** e **Auditoria de obrigação**.
- **Solicitações**: pré-tarefas externas.
- **Feriados**: os nacionais são mantidos pela Omie; os estaduais e municipais são cadastrados manualmente.
- **API** (ID e segredo de cliente).

### 6.2 Geração da agenda

- **Três datas**, calculadas nesta ordem: **Vencimento → Meta → Ação**.
  - **Vencimento**: dia fixo, com **antecipar** ou **postergar**; ou "X dias úteis", com ou sem sábado.
  - **Meta**: N dias úteis ou corridos antes do vencimento.
  - **Ação**: N dias antes da meta. É o dia de começar a tarefa.
- **Geração automática** é disparada quando o usuário conclui, avança de competência, dispensa ou bloqueia uma tarefa.
  - Mantém um horizonte à frente: mensal = 3 competências; trimestral, semestral e anual = 1; semanal ≈ 7-9; diária ≈ 45.
  - Preenche lacunas de competência.
  - Clientes inativos ou suspensos ficam de fora.
- Mudança de perfil exige gerar ou excluir tarefas. Salvar a regra padrão desfaz as datas personalizadas.

### 6.3 Como identifica a entrega

1. **ValidaPDF** (validação por conteúdo). O modelo é criado sobre um PDF de referência e marca 3 campos:
   - **Campo 1**: palavra-chave ou **código de arrecadação** que identifica a obrigação (ex.: "FGTS", "5856");
   - **Campo 2**: **inscrição do cliente** (CNPJ, CPF, IE) ou um "campo adicional" do cadastro;
   - **Campo 3**: **competência**, com a ordem de mês e ano definida.
   - O modelo é vinculado à obrigação e à atividade.
   - **"Busca em múltiplas linhas"**, para holerites: usa o campo 1 como âncora e exige deslocamento constante de linhas.
   - Erros tratados: "Cliente não corresponde", "Campo adicional não configurado", "Competência não corresponde".
   - PDFs-imagem são aceitos a partir de 16/01/2025.
2. **Anexo por NOME**, para arquivos não-PDF, criptografados ou com texto protegido (ex.: ISS de São Paulo):
   - O usuário mapeia no nome do arquivo os trechos **Cliente** (Inscrição, Código no Sistema ou Apelido) e **Competência** (dia, mês e ano separados, com formato).
   - Pode haver um trecho **coringa**.
   - A validação é **por posição e número de caracteres** (ex.: "01" e não "1").
3. **Robô InNubem**: agente Windows 10/11 que monitora uma pasta **local, de rede ou virtual, como o Google Drive**.
   - Detecta arquivos adicionados, renomeados, restaurados ou movidos, inclusive em subpastas.
   - Mantém fila offline e tenta reconectar até 15 vezes.
   - Valida por **Alias, nome ou ValidaPDF**, busca a tarefa, anexa e conclui.
   - O log mostra o link da tarefa ou o motivo da falha, com botão "Reenviar".
   - Desde 07/2026 permite filtrar por extensão.
4. **Integrações com ERPs e portais**: Onvio Gestão, Alterdata eContador, Questor Zen e-Doc, Fortes Conecta e SCI Report.
   - O robô procura o documento no **portal do cliente do ERP**, que funciona como diretório, anexa e baixa a atividade ("baixa em lote").
   - Jettax 360 empurra os PDFs gerados.
5. **Consulta eCAC** (parceiro):
   - Consulta pendências a cada 15 dias, emite CND e controla procurações.
   - Gera **solicitações externas** no G-Click. A conversão em tarefa é manual.
   - Não é usada para dar baixa em entregas.

### 6.4 Envio e ciência

- E-mail com o anexo da tarefa.
- O "e-mail automático na data de ação" é **só texto**; segundo a Omie, ele não deve servir para enviar arquivos.
- Link seguro para o **cliente enviar documentos**.
- **Visão do Cliente**: portal web e mobile com a marca do escritório.
- WhatsApp via parceiros (Digisac, WhatsContábil, Zappy, Onecode). Segundo a Digisac, a **confirmação de leitura volta para a tarefa**.

### 6.5 KPIs

- Dashboard mensal de tarefas concluídas por usuário, com filtros por departamento, cliente e status.
- Kanban.
- Auditoria por obrigação.

### 6.6 Preço e pontos fracos

- **Preço** (página da Omie, 2026): **a partir de R$ 100/mês para 1 usuário**; acima de 3 usuários, **R$ 50 por usuário**. Treinamento é cobrado à parte. É o único preço público entre os sistemas analisados.
- **Limitações vistas na documentação**:
  - feriados estaduais e municipais são manuais;
  - a validação por nome é rígida, por posição;
  - InNubem só roda em Windows;
  - a integração com eContador "pode ficar fora por tempo indeterminado";
  - não há protocolo nativo de ciência com IP comparável ao da Acessórias.
- Não foi encontrada página de reclamações específica no Reclame Aqui.

**Fontes:**
- https://ajuda.omie.com.br/pt-BR/collections/19642309-omie-g-click-obrigacoes
- https://ajuda.omie.com.br/pt-BR/articles/15205190-omie-g-click-validapdf-anexo-com-validacao-de-dados
- https://ajuda.omie.com.br/pt-BR/articles/15205216-omie-g-click-anexo-com-validacao-de-arquivos-via-nome
- https://ajuda.omie.com.br/pt-BR/articles/15210134-omie-g-click-obrigacoes-sobre-as-datas-e-como-configura-las
- https://ajuda.omie.com.br/pt-BR/articles/15209390-omie-g-click-obrigacao-como-alterar-o-perfil-e-definir-os-clientes
- https://ajuda.omie.com.br/pt-BR/articles/15206078-omie-g-click-geracao-automatica-de-tarefas-de-obrigacao
- https://ajuda.omie.com.br/pt-BR/articles/15206277-omie-g-click-robo-innubem-para-upload-automatico-de-arquivos
- https://ajuda.omie.com.br/pt-BR/articles/15206279-omie-g-click-integrando-com-o-consulta-ecac
- https://ajuda.omie.com.br/pt-BR/articles/15209392-omie-g-click-como-funcionam-as-integracoes-da-g-click
- https://ajuda.omie.com.br/pt-BR/articles/15206228-omie-g-click-realizando-o-cadastro-de-feriados
- https://ajuda.omie.com.br/pt-BR/articles/15212607-omie-g-click-obrigacao-envio-de-e-mail-automatico-na-data-de-acao-da-tarefa
- https://ajuda.omie.com.br/pt-BR/collections/19642324-omie-g-click-integracoes-api
- https://www.omie.com.br/gclick/
- https://digisac.com.br/integracoes/g-click/
- https://startupi.com.br/omie-adquire-startup-que-oferece-ferramenta-web-de-gestao-para-escritorios-de-contabilidade/

---

## 7. Questor Zen + Quiu (informação pública limitada)

- **Zen** é a plataforma do escritório e do cliente, com estes módulos:
  - **e-Doc**: troca de documentos com **rastreamento de protocolo e controle de expiração**;
  - **Q-Colabore**: documentos trabalhistas;
  - **Monitor de CND**;
  - **receptor de Caixa Postal e-CAC/SEFAZ**;
  - Q-Net (escritório virtual do cliente);
  - CRM.
- **Quiu** é um executor de rotinas agendadas 24/7: importação de arquivos fiscais, cálculo da folha, conciliação, apuração, Simples, férias.
  - O fluxo "começa na execução da tarefa e termina na baixa", e a baixa acontece quando o documento é **publicado no portal Zen e enviado ao cliente**.
  - Ou seja, a detecção é **integração nativa com o ERP Questor**, sem leitura de PDF de terceiros.
- **Preço**: não é público.
- **Avaliações**: o perfil B2B Stack do Quiu tem 0 avaliações.
- **Ponto fraco**: depende do ERP Questor, e a documentação pública sobre agenda e regras de prazo é escassa.
- Também se integra ao G-Click (Questor Zen e-Doc).

**Fontes:**
- https://www.b2bstack.com.br/product/quiu
- https://www.b2bstack.com.br/product/questor-zen
- https://ajuda.omie.com.br/pt-BR/articles/15211106-omie-g-click-integracao-com-questor-zen-e-doc-versao-1

---

## 8. Alterdata eContador / eTarefas (Pack)

- **eContador** é o portal e app (Android/iOS) entre escritório e cliente.
  - Atendimentos e documentos.
  - **Integração de guias e relatórios gerados no Fiscal, Contábil e DP**.
  - Rotinas de DP para o cliente: lançamentos da folha, pré-admissão, férias, pré-demissão.
  - Controle de CND (automático e manual).
  - Modalidade "só contador", para clientes que não usam o portal.
- **eTarefas**: controla envio e entrega da documentação, com visões de **atrasadas, recebidas e concluídas**.
- A detecção é **nativa do ERP**: o documento gerado no Pack é publicado no eContador.
- O Pack usa a **API Integra Contador (SERPRO)**, por exemplo para o Simples Nacional. É o caminho para consultar e transmitir direto na Receita.
- **Preço**: não é público.
- **Ponto fraco**: preso ao Pack. A integração com terceiros (ex.: G-Click) é instável segundo a própria Omie.

**Fontes:**
- https://ajuda.alterdata.com.br/packupbase/tema-econtador/econtador-voce-conhece
- https://ajuda.alterdata.com.br/alterdatapackup/sobre-o-econtador-242505346.html
- https://ajuda.alterdata.com.br/x/1DnMDg
- https://ajuda.omie.com.br/pt-BR/articles/15211546-omie-g-click-integrando-com-o-alterdata-econtador

---

## 9. Jettax 360 (complementar: fonte de guias)

- Apura e gera **DAS, DAS-MEI, Difal, ICMS-ST, ISS e DCTFWeb**.
- **Empurra o PDF** para Acessórias e G-Click, autenticando com ID e segredo da API. Também reenvia o **DAS recalculado**.
- Integra com SIEG (captura de XML) e Contmatic G5.
- Interessa porque mostra o padrão **"gerou a guia → documento chega ao hub → hub dá baixa"**, sem upload humano.

**Fontes:**
- https://jettax360-help.freshdesk.com/support/solutions/articles/151000220541-integrac%C3%A3o-omie-g-click
- https://acessorias.com/site/integracoes/
- https://www.jettax.com.br/blog/como-habilitar-a-integracao-com-o-erp-dominio/

---

## 10. Análise transversal

### 10.1 Modelo de dados de referência (síntese dos concorrentes)

```
Escritorio ─┬─ Usuario (perfil: admin/gerente/operacional; departamentos; cargo; custo/minuto)
            ├─ Departamento (hierárquico) 
            ├─ Feriado (nacional | estadual(UF) | municipal(IBGE); recorrente)
            ├─ ModeloObrigacao (nome, apelido, esfera, departamento, tipo{pagamento|declaração|cadastral|tarefa},
            │     frequência, regra_vencimento{dia_fixo|n-ésimo_dia_útil, mês_deslocamento, competência_offset},
            │     regra_não_útil{antecipa|posterga|mantém}, sábado_útil, meta{-N, úteis|corridos}, ação{-N},
            │     gera_multa, exige_baixa_robô, envia_cliente, agrupamento_envio, tempo_previsto, templates_reconhecimento[])
            ├─ PerfilRegra (ModeloObrigacao × expressão E/OU/EXCETO sobre atributos do cliente)
            ├─ PacoteRegime / GrupoObrigacoes (substitui vs. adiciona)
            └─ Cliente (CNPJ/CPF, IE[], IM, CEI, CAEPF, regime, matriz/filial, natureza, UF, município, tags, grupo,
                  honorário, status) ─┬─ ResponsavelPorDepartamento
                                      ├─ Contato (e-mail, WhatsApp, permissões por obrigação)
                                      └─ Entrega/Tarefa (modelo, competência, dt_ação, dt_meta, dt_vencimento,
                                            status{pendente|entregue_antecipada|no_prazo|atrasada|justificada|dispensada},
                                            multa{S/N, valor}, resp_prazo, resp_entrega, dt_entrega, origem_baixa
                                            {manual|robô|integração|api}) ─┬─ Documento (hash, path, tipo, valor, vencimento,
                                                                           │     dados_extraídos, confiança)
                                                                           └─ Envio/Protocolo (canal, enviado_em,
                                                                                 entregue_em, aberto_em, IP, user-agent,
                                                                                 lembretes[], pago_em)
```

### 10.2 Geração de agenda: regras comuns a todos

1. **Obrigação-modelo com regra de data** (todos):
   - vencimento por dia fixo ou n-ésimo dia útil;
   - deslocamento de mês;
   - competência relativa (−1/0/+1);
   - tratamento de dia não útil (antecipa/posterga);
   - "sábado é útil";
   - meta interna em dias úteis ou corridos;
   - data de ação (G-Click).
2. **Associação cliente↔obrigação**, de três formas:
   - por **pacote de regime** (Acessórias substitui; Domínio importa o regime do ERP);
   - por **grupos aditivos** (Acessórias);
   - por **expressão de perfil E/OU/Exceto** (G-Click, a mais expressiva).
3. **Materialização antecipada**:
   - Domínio: dia 20 do mês anterior;
   - G-Click: horizonte rolante, 3 competências para mensais;
   - Acessórias: prazos por competência.
4. **Feriados**:
   - os nacionais são mantidos pelo fornecedor (G-Click);
   - os estaduais e municipais **ficam a cargo do escritório em todos**.
   - É uma lacuna recorrente.
5. **Mudança de legislação** não é propagada automaticamente (FAQ Gestta). O escritório reconfigura.

### 10.3 Como se detecta a entrega (o ponto central)

| Mecanismo | Quem usa | Como funciona | Fragilidade |
|---|---|---|---|
| **Integração ERP → hub** | Domínio Processos (atividade concluída no Domínio), Questor Quiu → Zen, Alterdata Pack → eContador, Contmatic/Contabit/Consisa → e-Contínuo, Jettax → Acessórias/G-Click | O ERP sabe o que gerou (empresa, competência, atividade) e notifica o hub com o PDF | Depende de agente e credenciais; amarra ao fornecedor |
| **Leitura do conteúdo do PDF por template** | Nibo (robô padrão e personalizado), G-Click ValidaPDF, Domínio Express + Templates, Acessórias e-Contínuo | 1) classifica o tipo por **âncora textual ou código de receita**; 2) extrai o **identificador** (CNPJ/CPF/IE/CEI/CAEPF); 3) extrai a **competência** (formato configurado); 4) opcionalmente vencimento e valor; 5) **casa com a entrega pendente** (cliente + obrigação + competência); 6) se houver ambiguidade, fila de conferência (verde/amarelo/não encontrado) | Layout muda e o template quebra; PDF-imagem exige OCR; guias com várias empresas ou páginas exigem split (Multipages) |
| **Padrão no nome do arquivo** | G-Click "Anexo por nome" | Posições fixas no nome para cliente e competência | Rígido; depende da disciplina de quem salva |
| **Pasta monitorada (agente desktop)** | Nibo Assistente, G-Click InNubem (inclusive Google Drive), Domínio Express pasta local, e-Contínuo | Watcher de sistema de arquivos com fila offline e logs | Só Windows; antivírus; sem Windows Server (Nibo) |
| **API de upload** | Acessórias `POST /econtinuo` | Qualquer script envia o PDF e recebe o resultado do casamento | Precisa de integração própria |
| **Consulta a órgãos públicos** | Nibo (status de pagamento no recálculo, Radar e-CAC), G-Click + Consulta eCAC (pendências) | Certificado A1 com procuração ou Integra Contador | **Ninguém usa isso para dar baixa da declaração entregue** (o FAQ Gestta confirma que não consulta o e-CAC) |
| **Baixa manual / justificada** | Todos | Status "Entrega justificada" (Acessórias), baixa justificada em lote (Nibo) | — |

**Pipeline consolidado** (o que o sistema próprio deve replicar):

`ingestão (pasta, Drive, e-mail, API, ERP)` → `hash e deduplicação` → `extração de texto (pdftotext) ou OCR` → `classificação do tipo (âncoras, códigos de receita, regex)` → `extração de identificador, competência, vencimento, valor e código de barras` → `split multipágina` → `casamento com entrega pendente` → `confiança alta: baixa automática + renomeação + arquivo em {cliente}/{depto}/{tipo}/{ano}/{mês}` / `confiança baixa: fila de conferência` → `envio ao cliente (e-mail, WhatsApp, portal)` → `protocolo de ciência (abertura, IP, download)` → `lembretes de não lidos` → `(opcional) confirmação no governo: recibo, pagamento`.

### 10.4 Comunicação e protocolo

- Os canais são e-mail (todos), portal ou app com a marca do escritório (todos) e WhatsApp:
  - nativo: Acessórias Komunic, Nibo, Domínio Messenger;
  - via parceiros: G-Click.
- **Ciência**:
  - Acessórias: data, hora e **IP** de abertura, com relatório de prova;
  - Nibo: abriu o e-mail, visualizou no portal, baixa automática da visualização;
  - Domínio: o documento foi baixado, status pendente/enviado/entregue no WhatsApp;
  - G-Click: confirmação de leitura via Digisac.
- **Lembretes de guia não lida antes do vencimento**: Acessórias.
- **Envio agrupado** (um e-mail com várias guias): Acessórias e Domínio.
- **Cobrança de documentos do cliente**: Domínio (a cada N dias), G-Click (link seguro) e Acessórias (solicitações e formulários).

### 10.5 KPIs mais usados

- Pendentes hoje, na semana, no mês e nos próximos 30 dias.
- Atrasadas em relação à meta interna (prazo técnico) e ao vencimento legal (atraso legal).
- **Atraso com multa** e **% de entregas que geraram multa** (Acessórias 2026; Domínio "Gerando multas" e "Sujeitas a multa").
- % no prazo, % antecipadas, atrasos justificados e sem justificativa, por analista e por departamento.
- Documentos enviados e não lidos/baixados pelo cliente; mapa de pendências por visualização (Nibo).
- Falhas de envio por canal (Domínio).
- Tempo e custo por cliente e lucratividade (Acessórias APLA, apontamentos do Domínio).

---

## 11. Tabela comparativa final

| Critério | Acessórias | Domínio/Onvio Processos (ex-Gestta) | Nibo Obrigações | Omie.G-Click | Questor Zen/Quiu | Alterdata eContador |
|---|---|---|---|---|---|---|
| Independente de ERP | Sim | Não (exige Domínio Plus ou Premium) | Sim | Sim | Não | Não |
| Associação cliente↔obrigação | Regime (substitui) + grupos (adiciona) | Regime importado do ERP + pacotes | Manual + padrões | **Perfil E/OU/Exceto** | ERP | ERP |
| Regras de prazo | Legal + técnico (úteis/corridos), não útil, sábado útil | Data Legal/Meta/Competência ±1, dia útil, postergar | Vencimento, meta, deslocamento, 4 regras de não útil, sábado | Vencimento → Meta → Ação, antecipa/posterga, úteis + sábado | n/d | n/d |
| Feriados locais | Sim (cálculo em dias úteis) | Cadastro manual | n/d | Nacionais pela Omie; locais manuais | n/d | n/d |
| Leitura de PDF | **e-Contínuo**: layouts homologados pelo fornecedor, 5 identificadores, Multipages, OCR 2026 | **Express + Templates** (regras de conteúdo + formato de data), PDF-imagem, XLS e TXT | **Robôs** padrão e criados pelo usuário (âncora + campos) | **ValidaPDF** (palavra-chave + inscrição + competência), OCR desde 2025 | Não (nativo do ERP) | Não (nativo do ERP) |
| Nome do arquivo | n/d | n/d | Renomeia | **Sim** (por posição) | — | — |
| Pasta monitorada | e-Contínuo (desktop) | Express pasta local | Nibo Assistente (Windows) | InNubem (local, rede, **Google Drive**) | — | — |
| Integração ERP | Contmatic, Contabit, Consisa, Jettax | **Domínio** (conclusão automática) | Exporta para o sistema contábil | Onvio, Alterdata, Questor, Fortes, SCI, Jettax | Questor | Pack |
| Consulta e-CAC | Não | **Não** (FAQ) | Radar e-CAC + status de pagamento no recálculo | Via parceiro (pendências) | Caixa Postal | Integra Contador (no Pack) |
| API pública | **REST + MCP** | Não | n/d | Sim (ID e segredo) | n/d | n/d |
| Protocolo de ciência | **Data, hora e IP** + relatório de prova + lembrete de não lida | Download registrado; status de entrega no WhatsApp | Abriu e-mail / visualizou portal | Leitura via Digisac | Protocolo e-Doc | eTarefas (recebidas) |
| WhatsApp | Komunic (nativo) + Digisac | Domínio Messenger | Oficial | Parceiros | n/d | n/d |
| KPI de multa | **Sim** (% multas, atraso com multa) | **Sim** (gerando e sujeitas a multa) | Indireto | Não | n/d | n/d |
| Recálculo de guia | Via Jettax | Não | **Sim** (DAS, DARF, DCTFWeb) | Não | Não | n/d |
| Preço público | Não | Não (add-on por usuários) | Não | **R$ 100 (1 usuário); R$ 50 por usuário acima de 3** | Não | Não |
| Reclame Aqui | 6,4/10, 61,9% resolvidas (1º sem. 2026) | Caso de filiais com o mesmo nome | 65% resolvidas (jul/25-jun/26) | n/d | n/d | n/d |

n/d = não documentado nas fontes públicas consultadas.

---

## 12. Requisitos que um sistema próprio deve ter (lista priorizada)

### P0: indispensáveis para o MVP

1. **Cadastro de clientes** com todos os identificadores: CNPJ (raiz e filiais), CPF, IE por UF, IM, CEI/CNO, CAEPF, regime, matriz/filial, natureza, UF e município (código IBGE). Também tags e responsável por departamento.
   - Deve distinguir filiais com a mesma razão social. Isso evita a falha relatada no Onvio.
2. **Catálogo de obrigações-modelo** com:
   - esfera, departamento e tipo (pagamento / declaração / cadastral / tarefa interna);
   - frequência;
   - **regra de vencimento** (dia fixo ou n-ésimo dia útil, deslocamento de mês, competência relativa);
   - **dia não útil** (antecipa, posterga ou mantém) e **sábado útil**;
   - **meta interna** e **data de ação** em dias úteis ou corridos;
   - flag **gera multa**;
   - botão **simular vencimento**.
3. **Motor de aplicabilidade por perfil** com **E / OU / Exceto** sobre atributos do cliente, mais **pacotes por regime** (substituem) e **grupos aditivos**.
4. **Calendário de feriados** nacional, estadual por UF e municipal por IBGE, aplicado ao cliente conforme o município do estabelecimento. Deve vir pré-carregado, o que nenhum concorrente faz para feriados locais.
5. **Materialização automática das entregas** com horizonte rolante (ex.: 3 competências), recálculo quando muda o perfil, o feriado ou a regra, e preservação de exceções pontuais com log.
6. **Ingestão de documentos** por quatro portas:
   - upload em lote (arrastar);
   - **pasta monitorada no Google Drive** (API Drive com watch ou polling; sem agente Windows);
   - caixa de e-mail;
   - **API REST**.
   - Com **hash SHA-256** para evitar duplicidade.
7. **Motor de reconhecimento de PDF**:
   - extração de texto com **OCR de fallback**;
   - **classificador por âncoras e códigos de receita** (ex.: 5856, 0561, 1082) e por regex;
   - extração de **CNPJ/CPF/IE/CEI/CAEPF**, **competência** (múltiplos formatos de data), **vencimento**, **valor** e **linha digitável / código de barras**;
   - **split multipágina** quando há uma guia por página ou por cliente.
8. **Casamento automático com a entrega pendente** (cliente + obrigação + competência), com score de confiança:
   - confiança alta: **baixa automática**, renomeação padronizada e arquivamento em `{cliente}/{departamento}/{obrigação}/{AAAA}/{MM}/`, inclusive no Google Drive;
   - confiança baixa ou ambiguidade: **fila de conferência** com estados verde, amarelo e "não encontrado + motivo";
   - erros explícitos no estilo Acessórias: "Entrega [X para CNPJ] inexistente [Comp. MM/AAAA]".
9. **Templates de reconhecimento editáveis pelo próprio escritório** (como Nibo e G-Click), versionados e testáveis com PDF de amostra. Isso evita depender de "homologação" do fornecedor, como na Acessórias.
10. **Status de entrega**: pendente, entregue antecipada, no prazo, atrasada, justificada, dispensada. Registrar **origem da baixa** (manual, robô, integração, API) e **quem** a fez.

### P1: diferenciais de valor imediato

11. **Envio ao cliente** por e-mail (remetente do responsável, templates com variáveis) e **WhatsApp** (API oficial), com **envio agrupado** quando o pacote da competência fica completo.
12. **Protocolo de ciência com valor de prova**: link rastreável por destinatário, data e hora de entrega, abertura e download, IP e user-agent, e relatório PDF de protocolo.
13. **Lembretes automáticos**: guia não lida X dias antes do vencimento e cobrança recorrente de documentos pendentes do cliente.
14. **Portal ou app do cliente** com a marca do escritório: calendário de guias, documentos, **upload do comprovante de pagamento** e solicitações.
15. **Dashboard e KPIs**:
    - pendentes hoje, semana, mês e próximos 30 dias;
    - atraso em relação à meta e ao legal;
    - **atraso com multa e % de multas**;
    - % no prazo e % antecipadas por analista e departamento;
    - documentos enviados e não lidos;
    - falhas de envio por canal.
16. **Logs de auditoria** de toda alteração de prazo, status, regra e cadastro, e **MFA**.

### P2: vantagens competitivas reais (onde os concorrentes falham)

17. **Confirmação de entrega na fonte oficial via Integra Contador (SERPRO)** e e-CAC por procuração:
    - consultar **recibo do PGDAS-D**, **DCTFWeb** e demais declarações disponíveis e dar baixa com o **número do recibo**;
    - consultar **pagamento** do DAS/DARF e marcar "paga";
    - ler a **Caixa Postal**.
    - Nenhum concorrente usa isso para dar a baixa.
18. **Conector ERP** para o sistema contábil usado pelo escritório (ex.: Domínio): ler as atividades concluídas ou a pasta de saída de guias.
19. **Recálculo de guias vencidas** (DAS e DARF Sicalc) com validação do valor principal (modelo Nibo).
20. **Atualização regulatória assistida**: quando surge uma obrigação nova, o sistema sugere a regra e a lista de clientes afetados pelo perfil, e o escritório aprova.

### P3: gestão e escala

21. Processos e workflows não recorrentes (abertura e alteração de empresa) com passos bloqueantes e criação de obrigações a partir de passos.
22. Apontamento de tempo e **custo e lucratividade por cliente** (modelo APLA).
23. **API pública e servidor MCP** para automações e agentes de IA (padrão já adotado pela Acessórias).
24. Gestão de certificados digitais, procurações e CNDs com réguas de vencimento.

---

## 13. Lista consolidada de fontes

**Acessórias**
- https://acessorias.com/site/
- https://acessorias.com/site/integracoes/
- https://acessorias.com/site/categoria-de-funcionalidade/automacao-de-entregas/
- https://acessorias.com/site/funcionalidade/gestao-de-prazo-das-entregas/
- https://acessorias.com/site/e-continuo-automacao-inteligente-para-escritorios-contabeis/
- https://api.acessorias.com/documentation
- Central de ajuda (index): https://app.acessorias.com/sysajuda.php
- Artigos da central de ajuda (todos no formato https://app.acessorias.com/sysajuda.php?p=N):
  - p=3 (indicador clássico)
  - p=42 (grupos de obrigações)
  - p=43 (lembrete de não lidas)
  - p=44 (baixa por CEI)
  - p=45 (protocolo com IP)
  - p=61 (protocolo físico)
  - p=62 (edição de prazos)
  - p=70 (Multipages)
  - p=82 (obrigações via processos)
  - p=96 (configuração de prazos)
  - p=99 (pastas do e-Contínuo)
  - p=111 (5 identificadores)
  - p=127 (entrega justificada)
  - p=144 (envio agrupado)
  - p=153 (APLA)
  - p=195 (Contmatic)
  - p=216 (Contabit)
  - p=248 (Consisa)
  - p=555 (MFA)
  - p=585 (Performance)
  - p=586 (atualizações 2026)
  - p=591 (OCR)
- https://www.reclameaqui.com.br/empresa/acessorias-com/lista-reclamacoes
- https://fenacon.org.br/noticias/acessorias-e-o-novo-parceiro-do-clube-fenacon/

**Thomson Reuters (Domínio/Onvio Processos/Gestta)**
- https://images.engage.es-pt.thomsonreuters.com/Web/LALEYSAEIMPRESORA/%7Bfa3be1a4-eadc-479b-a994-f9e425ce049d%7D_TAX_PROF_BR_PDF_PERGUNTAS_E_RESPOSTAS_Base.pdf
- https://suporte.dominioatendimento.com/ctsfiles/ebookonvioprocessos.pdf?id=9426860&ds=centralSolucao
- https://suporte.dominioatendimento.com/ctsfiles/ebook_gestta_processos_ok1.pdf?id=9420151&ds=centralSolucao
- Central de Soluções (todos no formato https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=N): códigos 8221, 7452, 9146, 12190, 7487, 7517, 7526, 11568, 7516, 12159, 12304
- https://www.gestta.com.br/integracao-gestta-e-solucoes-dominio/
- https://www.dominiosistemas.com.br/blog/thomson-reuters-adquire-gestta/
- https://andersonhernandes.com.br/gesta-o-que-e-como-funciona/
- https://www.reclameaqui.com.br/thomson-reuters/onvio-processos-identificacao-de-empresas_VNKHTtxNpf8x_7yC/
- https://dominio.robolabs.digital/

**Nibo**
- https://ajuda.nibo.com.br/pt-BR/articles/7157220-introducao-ao-nibo-obrigacoes
- https://ajuda.nibo.com.br/pt-BR/articles/7174334-lista-de-obrigacoes
- https://ajuda.nibo.com.br/pt-BR/articles/7873582-robos-personalizados
- https://ajuda.nibo.com.br/pt-BR/articles/9853878-tela-de-conferencia
- https://ajuda.nibo.com.br/pt-BR/articles/8212592-recalculo-automatico
- https://ajuda.nibo.com.br/pt-BR/articles/8178973-relatorios-do-nibo-obrigacoes
- https://intercom.help/niboajuda/pt-BR/articles/8417298-nibo-assistente
- https://www.nibo.com.br/obrigacoes-plus/
- https://conteudo.nibo.com.br/nibo-obrigacoes-plus
- https://www.reclameaqui.com.br/empresa/nibo/lista-reclamacoes/
- https://www.planilhadefluxo.com.br/alternativa/nibo

**Omie.G-Click**
- https://www.omie.com.br/gclick/
- https://ajuda.omie.com.br/pt-BR/collections/19642309-omie-g-click-obrigacoes
- https://ajuda.omie.com.br/pt-BR/collections/19642324-omie-g-click-integracoes-api
- Artigos individuais citados na seção 6
- https://digisac.com.br/integracoes/g-click/
- https://startupi.com.br/omie-adquire-startup-que-oferece-ferramenta-web-de-gestao-para-escritorios-de-contabilidade/

**Questor, Alterdata, Jettax, SERPRO**
- https://www.b2bstack.com.br/product/quiu
- https://www.b2bstack.com.br/product/questor-zen
- https://ajuda.alterdata.com.br/packupbase/tema-econtador/econtador-voce-conhece
- https://ajuda.alterdata.com.br/x/1DnMDg
- https://jettax360-help.freshdesk.com/support/solutions/articles/151000220541-integrac%C3%A3o-omie-g-click
- https://jornalcontabil.com.br/noticia/integra-contador-oferece-27-servicos-e-ficara-apta-a-partir-de-outubro/
- https://fenacon.org.br/noticias/integra-contador-ja-esta-disponivel/
