# Estudo — Integração automatizada Portal M&O ⇄ Sistema Domínio

**Escritório:** Moraes & Oliveira Contabilidade Ltda (CNPJ 24.875.410/0001-44)
**Responsável técnico:** Fabio Moraes Oliveira — CRC-RJ 118632/O-1
**Data do estudo:** 22/10/2026
**Escopo:** levar automaticamente para o Domínio (Escrita Fiscal, Contabilidade e, quando couber, Folha) os dados que hoje nascem ou passam pelo Portal M&O (`portal.moraeseoliveiracontabil.com.br`), e trazer de volta para o portal o que o Domínio produz (status, apurações, balancetes), sem redigitação e com trilha de auditoria.

---

## Sumário executivo

1. **Não existe um único "botão" de integração.** O Domínio recebe dados por quatro portas oficiais, cada uma boa para um tipo de dado:
   - **Rotinas Automáticas de importação (pasta de XML)** → documentos fiscais (NF-e, NFC-e, CT-e, NFS-e). Já está desenhada e parcialmente operando na carteira (skill `configuracao-importacao-dominio`, `preparar_rotinas.py`).
   - **API Onvio / Domínio (Thomson Reuters)** → envio de XML de documentos fiscais e de **baixas de parcelas** direto da nuvem, com chave de integração por empresa. Exige credenciamento do portal como "ERP parceiro".
   - **Importação Padrão (TXT/leiaute com separador)** → **lançamentos contábeis** (o que vem de extrato bancário, conciliação, provisões, folha consolidada). Não há API pública para lançamento contábil genérico.
   - **Arquivos SPED / relatórios exportados** → caminho de **volta** (Domínio → portal) para conferência.
2. **Recomendação:** arquitetura híbrida em 4 ondas, começando pelo que já funciona e não depende de terceiros:
   - **Onda 1 (fiscal, 3–4 semanas):** o portal passa a gerar a árvore de pastas que a Rotina Automática lê (`<TIPO>\<Código-Apelido>\<MMAAAA>\*.xml`), um agente na máquina `moraes` sincroniza, o Domínio importa sozinho por agendamento. Elimina o passo de descompactar zip.
   - **Onda 2 (contábil-financeiro, 4–6 semanas):** o portal gera o arquivo de lançamentos no leiaute de Importação Padrão a partir do extrato conciliado, com **de-para de plano de contas por empresa** e histórico padronizado (ITG 2000).
   - **Onda 3 (API Onvio, prazo depende da Thomson Reuters):** credenciar o portal como software parceiro; trocar a pasta pela API para documentos e baixas.
   - **Onda 4 (retorno e conferência contínua):** portal lê SPED/relatórios do Domínio e fecha a **conciliação tripla** Portal × Domínio × ADN/SEFAZ por empresa/competência/tipo.
3. **Regra de ouro operacional:** o portal é a **fonte do documento** (XML íntegro, com chave), o Domínio é a **fonte da escrituração**. Nada é digitado no Domínio que tenha XML no portal — nota digitada não tem chave, duplica na próxima importação e esconde a regra de acumulador que falta.

---

## 1. Diagnóstico do cenário atual

### 1.1 O que é o Portal M&O hoje (evidências levantadas)

| Evidência | O que mostra |
|---|---|
| Declarações de faturamento emitidas pelo portal (out/2026) | O portal guarda **NFS-e autorizadas e registradas** nele e **notas importadas do Ambiente de Dados Nacional (ADN) da Receita Federal**; soma faturamento por competência; cruza com **PGDAS-D** em parte dos clientes; emite PDF assinado com **e-CNPJ ICP-Brasil** e código de verificação (`/verificar/<código>`); tem rotina de **"envio mensal automático"**. |
| Pacotes "Fechamento Financeiro — <mês>", "Fluxo de Caixa … fonte: painel ao vivo", "Relatório Gerencial Mensal" | Há um **módulo financeiro** por cliente: extratos de vários bancos, classificação por natureza, DRE gerencial, fluxo de caixa (CPC 03, método direto). |
| Arquivos de lançamentos gerados para um cliente-piloto (`DATA;DEBITO;CREDITO;VALOR;HISTORICO`, contas por código reduzido) e saldo de abertura importado por TXT no Domínio | Já existe, de forma manual/assistida, a geração de **lançamentos contábeis em arquivo** para importar no Domínio. É o embrião da Onda 2. |
| Cabeçalhos HTTP do portal (redirect para `/entrar`, CSP restritiva, HSTS, `X-Frame-Options: DENY`) | Aplicação web própria, autenticada, com postura de segurança boa — dá para expor uma API interna autenticada para o agente de integração. |

### 1.2 Como o Domínio está hoje na carteira

- **Domínio Escrita Fiscal 10.6A** acessado por **GO-Global** ("Acesso Remoto – Domínio Sistemas") na máquina `moraes`; XML de teste em `D:\XML ORIGINAIS`, de produção em `D:\XML NOTAS` (zips por tipo).
- Configurações de importação por regime e **Rotinas Automáticas** desenhadas: uma rotina por tipo de documento, agendamento por grupo de regime, pasta-base `D:\XML NOTAS\_ROTINAS\<TIPO>\<Código-Apelido>\<MMAAAA>`.
- Limitações já mapeadas (Central de Soluções Domínio):
  - a rotina **não lê ZIP** (cód. 5516, P&R 34);
  - só importa **competência atual ou anterior** à data do computador (P&R 26);
  - exige o **Escrita Fiscal aberto** com usuário logado no horário (cód. 4762/4364);
  - a pasta da empresa tem de se chamar exatamente `código-apelido` (cód. 4399/9143).

### 1.3 Onde está o retrabalho hoje

1. Descompactar zips e reorganizar pastas antes da rotina.
2. Notas que o portal já tem (NFS-e emitidas, ADN) sendo baixadas de novo de outras fontes para o Domínio.
3. Extratos bancários classificados no portal e reclassificados/lançados à mão no Domínio.
4. Conferência Portal × Domínio feita olhando dois relatórios.
5. Cadastro de empresa duplicado (código/apelido do Domínio não está no portal — as fichas de cliente registram "Código no Domínio: NÃO ENCONTRADO").

---

## 2. Mapa de dados: o que precisa ir e voltar

### 2.1 Portal → Domínio

| Dado no portal | Destino no Domínio | Canal recomendado | Observação fiscal/contábil |
|---|---|---|---|
| NFS-e **prestadas** (emitidas/registradas no portal; NFS-e Nacional e ABRASF) | Escrita Fiscal — Serviços | Rotina Automática (Onda 1) → API (Onda 3) | Data de escrituração = **competência (`dCompet`)**, não emissão — é o fato gerador do ISS e da receita no Simples/Presumido. ISS retido (`tpRetISSQN`) roteia para acumulador próprio e **sai da base do DAS** (LC 123/2006, art. 18, §4º-A, II). |
| NFS-e **tomadas** (ADN) | Escrita Fiscal — Serviços tomados | idem | Retenções (IRRF, CSRF, INSS, ISS) só se a empresa for fonte pagadora obrigada; tomador optante do Simples **não** retém CSRF (IN SRF 459/2004, art. 3º). |
| NF-e de **entrada** (destinatária) e **saída** | Escrita Fiscal — Entradas/Saídas | idem | Simples: sem crédito de ICMS na entrada (salvo regras próprias); de-para CFOP do fornecedor → CFOP de entrada pelo 1º dígito da UF. |
| NFC-e | Escrita Fiscal — Saídas | idem | Cliente padrão "CONSUMIDOR FINAL" para venda sem CPF. |
| CT-e (empresa tomadora) | Escrita Fiscal — Entradas | idem | Só importa quando `papel = tomador`. |
| Eventos de **cancelamento** | mesma pasta/lote da nota | idem | Sem o evento a nota cancelada vira receita. |
| Extrato bancário conciliado / classificado | **Contabilidade** — lançamentos | Importação Padrão TXT (Onda 2) | Regime de competência (NBC TG Estrutura Conceitual / CPC 00): extrato registra caixa; receita e despesa vêm do documento fiscal/provisão. Lançamento de caixa **baixa** provisão, não cria receita em duplicidade. |
| Contas a pagar/receber com baixa | Contabilidade — baixas de parcelas | API "Baixa de Parcela" (Onda 3) ou TXT (Onda 2) | A baixa só faz sentido se a nota foi importada com parcelas (`Importa parcelas`). |
| Cadastro de clientes/fornecedores | Domínio (criado a partir do XML) | automático no importador | Não há API de cadastro; o importador cria a partir do XML (`Cadastros de clientes e fornecedores`). Conferir município IBGE (NFS-e). |
| Folha consolidada / pró-labore (se o portal tiver) | Contabilidade | TXT | Preferir integração contábil nativa do módulo Folha do Domínio quando a folha é feita no próprio Domínio. |

### 2.2 Domínio → Portal (retorno)

O Domínio **não oferece API pública de leitura**. Caminhos viáveis, em ordem de preferência:

| Dado | Fonte no Domínio | Como chega ao portal |
|---|---|---|
| Status de importação por empresa/tipo | Relatórios individualizados da Rotina Automática (`_ROTINAS\_relatorios\<Código-Apelido>`) + e-mail de aviso | Agente lê a pasta e envia ao portal; e-mail parseado como segundo canal |
| Escrituração fiscal consolidada | **EFD-Contribuições**, **EFD ICMS/IPI**, **EFD-Reinf**, **PGDAS-D** (recibos/extratos) | Upload automático do arquivo SPED gerado → portal faz parse (leiaute oficial e estável) |
| Escrituração contábil | **ECD** (anual) e **balancete/razão** exportados (Gerenciador de Relatórios → Excel/CSV) | Rotina de exportação + agente |
| Plano de contas e códigos reduzidos | Relatório de plano de contas (exportado) | Carga inicial e a cada alteração → alimenta o de-para da Onda 2 |
| Código e apelido da empresa | `Relatórios > Cadastrais > Empresas` | Carga em `carteira.csv` → tabela `empresa` do portal |
| Guias (DAS, DARF, ISS) | PDFs gerados / Onvio Portal do Cliente | Upload para o portal do cliente final |

> Leitura direta do banco do Domínio (ODBC) **não é recomendada**: no modelo de acesso por GO-Global o banco fica no ambiente da Thomson Reuters, o esquema não é documentado nem estável, e uso fora do contrato pode comprometer o suporte. Só considerar com autorização formal da Domínio, somente leitura.

---

## 3. Canais de integração — análise detalhada

### 3.1 Canal A — Pasta de XML + Rotinas Automáticas (file drop)

**Como funciona:** o portal entrega XML soltos (não zip) na estrutura que a rotina espera; o agendamento do Domínio (`Movimentos > Rotinas Automáticas`) importa todas as empresas do grupo.

```
D:\XML NOTAS\_ROTINAS\
  NFE-ENTRADA\<Código-Apelido>\<MMAAAA>\<chave>.xml
  NFE-SAIDA\…   NFCE\…   CTE\…
  NFSE-NACIONAL-PRESTADA\…   NFSE-NACIONAL-TOMADA\…
  NFSE-ABRASF-PRESTADA\…     NFSE-ABRASF-TOMADA\…
  _relatorios\<Código-Apelido>\…   (saída do Domínio)
```

| Prós | Contras |
|---|---|
| Não depende de credenciamento da Thomson Reuters; usa a configuração de importação já testada | Exige máquina com Domínio aberto no horário do agendamento |
| Mesmo resultado do importador manual (mesmos acumuladores, mesmo filtro "somente não importadas") | Só competência atual/anterior; atrasados vão pelo importador manual |
| Idempotente: chave já importada é ignorada pelo Domínio | Depende de um agente local para descer os arquivos do portal |

**Como o portal alimenta a pasta (escolher um):**

1. **Agente de sincronização (recomendado):** serviço Windows leve na máquina `moraes` (Python ou .NET), que a cada X minutos chama `GET /api/integracao/dominio/pendentes` no portal (token de serviço, mTLS opcional), grava os XML na árvore acima, confirma com `POST /api/integracao/dominio/entregues` (hash SHA-256 de cada arquivo) e devolve os relatórios da rotina com `POST /api/integracao/dominio/retorno`.
2. **Google Drive para desktop:** o portal grava a árvore numa pasta do Drive espelhada em `D:`. Mais simples, porém sem confirmação de entrega e com risco de arquivo parcial durante a sincronização (o Domínio pode ler um XML incompleto → "Erro processando arquivo XML").

**Decisão de desenho:** o portal deve gerar a árvore **já com o nome `Código-Apelido` do Domínio** — por isso a Onda 1 começa cadastrando `codigo_dominio` e `apelido_dominio` em cada empresa do portal, a partir do relatório de empresas do Domínio (nunca digitado de memória).

### 3.2 Canal B — API Onvio / Domínio (Thomson Reuters)

**O que é oficialmente oferecido** (Central do Desenvolvedor Domínio; Developer Portal Thomson Reuters — *Onvio BR Accounting API*):

- **API de Documentos:** envio de XML de **NF-e/NFC-e (4.0)**, **CT-e (3.0)**, **CF-e (0.07/0.08)** e **NFS-e** (leiaute ABRASF 1.00 e NFS-e Nacional), em lote, via HTTP POST `multipart/form-data`.
- **API de Baixa de Parcela:** XML proprietário (versão 1.00) com baixas de entradas, saídas e serviços.
- **Consulta de protocolo** do lote (retorno de processamento).
- Recursos REST documentados: `ClientInfoResource`, `IntegrationResource` (ativação da chave) e `InvoiceIntegrationResource` (criação de lote de arquivos).
- **Não há** API pública de lançamento contábil genérico nem de leitura de dados.

**Fluxo (solução Domínio cód. 8476):**

1. O escritório gera a **chave do cliente** no **Onvio Gestão → menu API → aba Chave** (uma por empresa).
2. O software (portal) obtém **token OAuth 2.0** com as credenciais de software house.
3. `GET …/activation/info` com a chave do escritório no header `x-integration-key` → confirma que a chave é da empresa certa (comparar CNPJ antes de seguir).
4. `POST …/activation/enable` (Bearer + chave do escritório) → devolve o **`integrationKey`** definitivo; guardar cifrado por empresa.
5. `POST …/invoice/v3/batches` com o `integrationKey` (não a chave do escritório) + Bearer e os arquivos → devolve o id do lote.
6. Consultar o lote até processado; registrar o protocolo no portal.
7. No escritório, o **Agente de Comunicação** do Domínio precisa estar ativo; os documentos entram na Escrita Fiscal **automaticamente se houver rotina automática**, senão aguardam confirmação manual.

| Prós | Contras |
|---|---|
| Nuvem → nuvem: some o agente de arquivos e a pasta compartilhada | **Credenciamento**: a Thomson Reuters avalia técnica e juridicamente o software antes de liberar credenciais |
| Baixas de parcelas integradas (financeiro → contábil) sem TXT | Sem lançamento contábil genérico e sem leitura de volta |
| Padrão já usado por ERPs de mercado (Conta Azul, Omie, ERPFlex, Market) | Reenvio/correção limitados: correções exigem excluir no Domínio e reenviar |
| Uma chave por empresa: controle granular | Continua dependendo da configuração de importação e das rotinas no Domínio |

**Custo de entrada:** cadastro no Developer Portal, contato com a equipe de parcerias do Contábil Domínio, homologação. Começar o processo **já na Onda 1**, porque o prazo não depende de nós.

### 3.3 Canal C — Importação Padrão (lançamentos contábeis em TXT)

**Para quê:** tudo o que não é documento fiscal — extrato bancário, conciliação, provisões, transferências entre contas, despesas sem nota, ajustes, saldos de abertura (já feito para o cliente-piloto).

**Onde no Domínio:** `Utilitários > Importação > Importação Padrão > Leiaute Domínio Sistemas com Separador` (ou leiaute de lançamentos em lote) → *Arquivo* → **[Importar]** → conferir → **[Gravar]**.

**Requisitos do arquivo gerado pelo portal:**

1. **Plano de contas do Domínio**, por empresa, com código reduzido — o portal mantém a tabela `de_para_conta` (categoria do portal → conta reduzida do Domínio), carregada do relatório de plano de contas exportado.
2. **Histórico** objetivo e rastreável (ITG 2000, item 13: data, conta, histórico, valor, documento): `TIPO - CONTRAPARTE - DOC/ID - BANCO`, ex.: `PIX RECEBIDO - CLIENTE XYZ LTDA - NFS-E 123 - BANCO A`.
3. **Partidas dobradas fechadas** por lote (soma débitos = soma créditos) e por dia.
4. **Lote identificado** (número sequencial + hash do arquivo) para impedir reimportação.
5. **Conta transitória** para itens sem classificação, nunca conta de resultado "genérica" — e o portal bloqueia a geração do arquivo se a transitória passar de um limite.
6. **Não lançar receita pelo extrato** quando a receita já entra pela integração fiscal → o crédito do recebimento vai para **Clientes a receber**, não para Receita (evita a duplicidade já vista em conferência de cliente-piloto, em que a integração fiscal lançou receita que não batia com as NFS-e).

> O leiaute campo a campo deve ser **extraído do próprio Domínio** (ajuda do leiaute na tela de Importação Padrão / Central de Soluções) e versionado no repositório do portal. O CSV já usado (`DATA;DEBITO;CREDITO;VALOR;HISTORICO`) é ponto de partida, não especificação — validar com um arquivo de 3 lançamentos numa empresa de teste antes de produzir em escala.

**Automação:** o arquivo é gerado e entregue pelo mesmo agente do Canal A numa pasta `_LANCAMENTOS\<Código-Apelido>\<MMAAAA>\lote_<n>.txt`. A importação em si pode exigir clique humano (confirmar se a Rotina Automática do Domínio suporta a Importação Padrão de lançamentos na versão 10.6A; se não suportar, a etapa vira uma rotina assistida de 1 clique por empresa, ou RPA — Canal D).

### 3.4 Canal D — RPA (automação de tela)

Automação da interface (computer use, pywinauto/AutoHotkey sobre GO-Global) para o que nenhuma porta oficial cobre (ex.: confirmar Importação Padrão, exportar relatório).

- **Usar só como ponte**, com tarefas curtas e verificáveis (screenshot final + contagem).
- Frágil a mudança de versão, resolução, janelas por cima (já observado com o Telegram), expiração de sessão GO-Global.
- Nunca usar RPA para transmitir declarações (DAS, PGDAS-D, Reinf, DCTFWeb).

### 3.5 Comparativo

| Critério | A — Pasta + Rotina | B — API Onvio | C — TXT lançamentos | D — RPA |
|---|---|---|---|---|
| Documentos fiscais | ✅ | ✅ | — | ⚠️ |
| Baixas/financeiro | — | ✅ | ✅ | ⚠️ |
| Lançamentos contábeis | — | — | ✅ | ⚠️ |
| Retorno Domínio → portal | parcial (relatórios) | parcial (protocolo) | — | ⚠️ |
| Dependência de terceiros | nenhuma | Thomson Reuters | nenhuma | nenhuma |
| Robustez | alta | alta | alta | baixa |
| Prazo | semanas | meses | semanas | dias (mas manutenção contínua) |

---

## 4. Arquitetura proposta

```
┌──────────────────────── Portal M&O (nuvem) ────────────────────────┐
│ Captura: NFS-e emitidas · ADN (NSU) · upload cliente · extratos    │
│      ↓                                                             │
│ Normalização + validação (schema XSD, chave, CNPJ, competência)    │
│      ↓                                                             │
│ Motor de regras: tipo/direção, regime, competência, de-para contas │
│      ↓                                                             │
│ Fila de integração (lotes, estados, hash, idempotência)            │
│      ↓                         ↓                        ↓           │
│ Exportador pasta (A)   Cliente API Onvio (B)   Gerador TXT (C)     │
│ API interna /integracao/dominio (token de serviço)                 │
└──────────────┬──────────────────────┬──────────────────────────────┘
               │ HTTPS                 │ HTTPS (OAuth2)
┌──────────────▼───────────┐   ┌───────▼──────────────────┐
│ Agente M&O (máquina      │   │ Onvio / Domínio (TR)     │
│ moraes, serviço Windows) │   │ Agente de Comunicação    │
│ grava D:\XML NOTAS\…     │   └───────┬──────────────────┘
│ devolve relatórios       │           │
└──────────────┬───────────┘           │
               ▼                       ▼
        Domínio Escrita Fiscal / Contabilidade (Rotinas Automáticas)
               │
               ▼  SPED · relatórios · PDFs de guias
        Agente → Portal: conferência e painel de status
```

### 4.1 Modelo de dados mínimo no portal

| Tabela | Campos-chave |
|---|---|
| `empresa` | `cnpj`, `codigo_dominio`, `apelido_dominio`, `regime` (Simples/Presumido/MEI/Imune/Real) **com vigência** (ex.: Simples até 05/2026, Presumido a partir de 06/2026), `municipio_ibge`, `integration_key_cifrada`, `canal_fiscal` (A/B), `ativa_integracao` |
| `documento_fiscal` | `chave` (única), `tipo` (NFE/NFCE/CTE/NFSE_NAC/NFSE_ABRASF), `direcao` (entrada/saida/prestada/tomada), `empresa_id`, `competencia` (AAAA-MM), `valor_total`, `iss_retido`, `situacao` (autorizada/cancelada/substituida), `xml_sha256`, `origem` (emissao/ADN/upload), `status_integracao`, `lote_id` |
| `lote_integracao` | `id`, `empresa_id`, `canal`, `tipo`, `competencia`, `qtd`, `valor`, `hash`, `protocolo_onvio`, `status`, `criado_em`, `entregue_em`, `importado_em` |
| `de_para_conta` | `empresa_id`, `categoria_portal`, `conta_reduzida_dominio`, `vigencia` |
| `lancamento_contabil` | `empresa_id`, `data`, `debito`, `credito`, `valor`, `historico`, `origem_id` (extrato/linha), `lote_id` |
| `evento_integracao` | log imutável: quem, quando, o quê, antes/depois, mensagem literal do Domínio |

### 4.2 Máquina de estados do documento

`recebido → validado → pronto → entregue (pasta/API) → importado_dominio → conferido`
Desvios: `rejeitado_validacao` (XML inválido, CNPJ fora da carteira, competência fechada), `erro_dominio` (mensagem literal do relatório da rotina, ex.: "Não foi encontrada relação de acumulador…" → abre pendência de **configuração**, nunca de digitação), `aguardando_manual` (competência fora de atual/anterior → importador manual).

### 4.3 Regras que o portal aplica antes de entregar

1. **Empresa da carteira:** CNPJ emitente/destinatário/tomador ∈ `empresa`; senão → `terceiros` (pasta errada).
2. **Direção pelo CNPJ**, não pelo nome do arquivo: emitente = saída/prestada; destinatário/tomador = entrada/tomada. Nota entre dois clientes da carteira vai para **as duas** empresas.
3. **Competência:** NFS-e → `dCompet`; demais → data de emissão. Pasta `MMAAAA` sai daí.
4. **Cancelamento/substituição:** evento junto da nota; NFS-e substituída marca a anterior.
5. **Regime vigente na competência** (tabela com vigência) decide o grupo de agendamento.
6. **Deduplicação por chave** entre fontes (emissão no portal × ADN × upload do cliente) — guarda um XML por chave, preferindo o autorizado oficial.
7. **Validação XSD** do leiaute (NF-e 4.00, CT-e, NFS-e Nacional) — XML que não passa não vai para o Domínio.
8. **Alertas tributários** (não bloqueiam, viram pendência humana): retenção federal destacada em nota de optante do Simples; ISS retido em município diferente; NFC-e sem CPF acima do limite; NF-e com grupo IBS/CBS (Reforma Tributária) — ver §6.

---

## 5. Roadmap de implantação

### Onda 0 — Pré-requisitos (1 semana)

- [ ] Extrair do Domínio o relatório de empresas (código, apelido, CNPJ, regime) → carregar em `empresa` do portal; marcar divergências de regime.
- [ ] Inventário de tipos de documento por empresa (rodar `matriz_regras.py` sobre `D:\XML ORIGINAIS`).
- [ ] Definir a máquina "servidor de rotina" (sempre ligada, Domínio aberto no horário).
- [ ] **Abrir o processo de credenciamento** na Thomson Reuters (Developer Portal + equipe de integração do Contábil) — corre em paralelo.

### Onda 1 — Documentos fiscais por pasta (3–4 semanas)

- [ ] Endpoint `/api/integracao/dominio/pendentes|entregues|retorno` no portal.
- [ ] Exportador que monta a árvore `<TIPO>\<Código-Apelido>\<MMAAAA>` (substitui `preparar_rotinas.py` na origem; o script continua para os zips de outras fontes).
- [ ] Agente Windows com logs, retry exponencial e escrita atômica (grava `.tmp` e renomeia para `.xml` só no fim).
- [ ] Rotinas `IMP XML - *` e agendamentos por regime já previstos na skill, com relatórios individualizados.
- [ ] Piloto com as empresas-modelo de cada regime → grupo completo.
- **Critério de aceite:** para cada empresa/competência, *quantidade e valor* no relatório de Acompanhamentos do Domínio = portal, com zero "não importadas" de configuração.

### Onda 2 — Lançamentos contábeis (4–6 semanas)

- [ ] Carga do plano de contas de cada empresa; tela de de-para no portal (categoria → conta reduzida), com sugestão e aprovação pelo contador.
- [ ] Gerador de lote TXT com validações (partidas fechadas, contas existentes, período aberto, transitória sob limite).
- [ ] Piloto com o cliente que já tem extrato classificado no portal e saldo de abertura implantado no Domínio.
- **Critério de aceite:** saldo da conta banco no balancete do Domínio = saldo do extrato no último dia do mês, por banco (conciliação bancária fechada, sem diferença).

### Onda 3 — API Onvio (após credenciamento)

- [ ] Cliente OAuth2 + ativação de chave por empresa (fluxo §3.2), chaves cifradas (KMS/cofre).
- [ ] Envio de lotes de XML e de baixas; consulta de protocolo; mapeamento dos códigos de retorno para estados do portal.
- [ ] Migração empresa a empresa do canal A para o B (campo `canal_fiscal`), mantendo A como contingência.

### Onda 4 — Retorno e conferência contínua

- [ ] Parse de EFD-Contribuições / EFD ICMS-IPI / PGDAS-D / balancete exportado.
- [ ] **Conciliação tripla** por empresa × competência × tipo: Portal × Domínio × ADN/SEFAZ (quantidade e valor; diferenças listadas por chave).
- [ ] Painel "Integração Domínio" no portal: verde (conferido), amarelo (aguardando), vermelho (erro com a mensagem literal e o link para a solução da Central Domínio).
- [ ] Declaração de faturamento passa a citar também "escriturado no sistema contábil" quando a competência estiver `conferida`.

---

## 6. Pontos tributários e contábeis que a integração precisa respeitar

| Tema | Regra / norma | Impacto no desenho |
|---|---|---|
| Competência do serviço | LC 116/2003 (fato gerador do ISS na prestação); receita bruta do Simples pelo regime de competência ou caixa conforme opção (Res. CGSN 140/2018, art. 16) | Pasta `MMAAAA` e data de escrituração pela `dCompet`; regime de caixa no Simples exige tratamento próprio nos acumuladores/parâmetros |
| ISS retido no Simples | LC 123/2006, art. 18, §4º-A | Acumulador "ISS retido" separado; o portal sinaliza `iss_retido` |
| Retenções federais | Lei 10.833/2003, arts. 30–32; IN SRF 459/2004; IN RFB 1.234/2012 (órgãos públicos) | Optante do Simples prestador: CSRF não retida — nota com retenção vira alerta, não regra de importação |
| Simples × crédito de ICMS | LC 123/2006, art. 23 | Entradas sem crédito (percentual de B.C = 0 no acumulador) |
| Mudança de regime no ano | ex.: cliente que passou do Simples ao Presumido em 06/2026 | `regime` com vigência na tabela `empresa`; a empresa muda de grupo de agendamento a partir da competência certa |
| NFS-e Padrão Nacional e ADN | LC 214/2025 e normas do Comitê Gestor da NFS-e (padrão nacional obrigatório a partir de 2026) | Priorizar o canal NFS-e Nacional; configuração `Código do município = IBGE/RAIS` nos parâmetros do Domínio |
| Reforma Tributária — IBS/CBS | LC 214/2025; 2026 é ano de teste (destaque informativo de CBS 0,9% e IBS 0,1%); NTs da NF-e/NFS-e com grupos IBS/CBS | XML de 2026 trazem os novos grupos: garantir que o Domínio esteja em versão que os leia e que os impostos 183/184 (IBS/CBS) estejam habilitados nos parâmetros quando aplicável (Central Domínio cód. 11230). Monitorar NTs. |
| Escrituração contábil | ITG 2000 (R1) — histórico, documentação suporte, lançamentos em ordem cronológica; NBC TG Estrutura Conceitual (competência) | Histórico padronizado, vínculo lançamento → documento/linha de extrato no portal (trilha de auditoria) |
| Demonstração do fluxo de caixa | NBC TG 03 / CPC 03 (R2) | O painel do portal (método direto) e a contabilidade precisam usar a mesma classificação operacional/investimento/financiamento |
| Guarda de documentos | CTN, arts. 173 e 195, parágrafo único (prazo decadencial) | Portal guarda o XML original + hash por no mínimo 5 anos contados do exercício seguinte; o Domínio não é repositório de XML |
| Proteção de dados | LGPD — Lei 13.709/2018 (base legal: obrigação legal/execução de contrato; art. 46, segurança) | Minimização no agente local, criptografia em trânsito e repouso, logs de acesso |
| Assinatura digital | MP 2.200-2/2001 (ICP-Brasil) | Declarações e lotes podem ser assinados com o e-CNPJ do escritório, como o portal já faz |

---

## 7. Segurança, controles e auditoria

1. **Credenciais:** token de serviço do agente com escopo mínimo e rotação; `integrationKey` do Onvio cifrada por empresa; nada de credencial em planilha — manter senhas de portais governamentais num cofre (ex.: Bitwarden/1Password Business ou o próprio cofre do portal), com acesso por perfil.
2. **Certificados A1** (captura ADN/SEFAZ) no portal com HSM/KMS ou armazenamento cifrado; alerta de vencimento com 30 dias.
3. **Idempotência:** chave do documento única; lote com hash; o agente nunca regrava arquivo existente; o Domínio ignora chave já importada.
4. **Escrita atômica** na pasta da rotina (evita XML pela metade).
5. **Trilha de auditoria:** `evento_integracao` imutável com mensagem literal do Domínio; cada lançamento contábil aponta para sua origem.
6. **Segregação:** quem aprova de-para de contas ≠ quem gera o lote (ou aprovação do contador responsável antes do primeiro lote de cada empresa).
7. **Conciliação como controle-chave:** nenhuma competência é dada como fechada no portal sem a conciliação tripla verde.
8. **Contingência:** se o agente/rotina falhar, o portal oferece o download do zip do mês no leiaute do importador manual (que aceita zip).

---

## 8. Riscos e mitigação

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Domínio fechado no horário do agendamento | média | lotes não importados | máquina dedicada; agente verifica processo do Escrita Fiscal e avisa; relatório "não executou" no portal |
| Configuração de importação incompleta (acumulador) | alta no início | notas não importadas | matriz de regras por empresa antes de ligar a rotina; erro vira pendência de configuração com a mensagem literal |
| Credenciamento Thomson Reuters demorar/negado | média | Onda 3 adiada | Ondas 1–2 não dependem dele; canal A segue como definitivo |
| Mudança de versão do Domínio / leiaute | média | importação quebra | testes de regressão com XML de amostra a cada atualização; leiaute versionado |
| Duplicidade fiscal × financeiro (receita lançada duas vezes) | alta se não desenhado | resultado e tributos errados | regra §3.3 item 6; conciliação Clientes a receber |
| Regime/empresa errados no cadastro | média | escrituração no grupo errado | carga do cadastro a partir do Domínio + vigência de regime |
| XML de terceiros na pasta | média | lançamento em empresa errada | validação por CNPJ antes da entrega |
| Vazamento de dados no agente local | baixa | LGPD | disco cifrado (BitLocker), usuário de serviço, limpeza de XML após importação confirmada (o original fica no portal) |

---

## 9. Indicadores de sucesso

| KPI | Meta após Onda 2 |
|---|---|
| % de documentos fiscais escriturados sem digitação | ≥ 98% |
| Notas "não importadas" por erro de configuração | 0 por empresa estabilizada |
| Tempo entre autorização da nota e escrituração no Domínio | ≤ 24 h (pasta) / ≤ 1 h (API) |
| Competências com conciliação tripla verde no dia 10 do mês seguinte | ≥ 90% da carteira |
| Horas/mês de fechamento fiscal por empresa | redução ≥ 60% |
| Diferença saldo bancário contábil × extrato | R$ 0,00 em 100% das contas integradas |

---

## 10. Próximos passos imediatos

1. **Decidir o canal de entrega da Onda 1** (agente próprio — recomendado — ou Drive para desktop).
2. **Exportar do Domínio** o relatório de empresas e o plano de contas das empresas-piloto.
3. **Abrir o credenciamento** no Developer Portal da Thomson Reuters e falar com a equipe de integração do Contábil Domínio.
4. **Extrair o leiaute oficial** de Importação Padrão de lançamentos na versão 10.6A e testar com 3 lançamentos na empresa-piloto.
5. Especificar e implementar os endpoints `/api/integracao/dominio/*` no portal.

---

## Fontes

- Domínio Sistemas — Central do Desenvolvedor (APIs de Documentos e Baixa de Parcela, leiautes XML): https://www.dominiosistemas.com.br/lp-centraldodesenvolvedor-api/
- Domínio Sistemas — Integração com ERP: https://www.dominiosistemas.com.br/solucoes/integracao-com-erp/
- Thomson Reuters Developer Portal — Onvio BR Accounting API (documentação e recursos REST): https://developerportal.thomsonreuters.com/onvio-br-accounting-api/documents/documentao-api
- Central de Soluções Domínio — Documentação Integração API para ERPs (cód. 8476): https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=8476
- Central de Soluções Domínio — Onvio API (cód. 6927): https://suporte.dominioatendimento.com/central/faces/solucao.html?codigo=6927
- Conta Azul — FAQ conexão Conta Azul × Domínio (chave no Onvio Gestão, fluxo e limitações): https://ajuda.contaazul.com/hc/pt-br/articles/12190143402381
- Omie — Importação de lançamentos no Domínio, leiaute com separador: https://ajuda.omie.com.br/pt-BR/articles/9009287-importando-os-lancamentos-contabeis-no-sistema-dominio-leiaute-com-separador
- Omie — Importação de lançamentos no Domínio, leiaute em lote: https://ajuda.omie.com.br/pt-BR/articles/9001244-importando-os-lancamentos-contabeis-no-sistema-dominio-leiaute-em-lote
- Projeto ACBr — fórum sobre integração com a API Onvio/Domínio: https://www.projetoacbr.com.br/forum/topic/59143-integra%C3%A7%C3%A3o-com-api-da-onviodom%C3%ADnio/
- Base interna: skill `configuracao-importacao-dominio` (Central de Soluções cód. 4399, 4762, 4364, 5516, 9143, 11230, 12427 e demais citados), declarações de faturamento e fechamentos financeiros emitidos pelo Portal M&O.
