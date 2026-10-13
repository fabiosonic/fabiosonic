# Parecer do Gestor de Qualidade: `mo_obrigacoes`

**Data:** 13/10/2026 · **Escopo:** engenharia do código (correção, segurança, robustez, usabilidade e testes). O mérito legal dos prazos em `catalogo.py` está fora do escopo e é revisado em paralelo pelo gestor contábil.
**Base auditada:** commit `ee6b4e0`, revalidado sobre `4813cee` (que inclui a revisão do catálogo feita em paralelo), Python 3.13, FastAPI 0.143, Starlette 1.6, SQLAlchemy 2.1, pypdf 6.17.
**Linha de base:** `python3 -m pytest -q -p no:warnings` → **23 passed**. A demonstração (`python3 -m mo_obrigacoes demo` com banco e Drive em `/tmp`) roda sem erro: 12 arquivos, 10 baixas, 1 não identificado e 1 divergente.

## Sumário executivo

O desenho do sistema é bom: catálogo declarativo, pontuação com fila de revisão, conferência de CNPJ e trilha de auditoria. O ponto fraco é a **sincronização com o Drive**, que é o coração do produto. Ela **perde arquivos sem avisar** e **não desfaz baixas** quando o comprovante some ou muda. As duas falhas produzem o pior erro possível num escritório contábil: a obrigação aparece como *entregue* sem ter sido, ou fica *pendente* e o cliente é cobrado por algo que já depositou.

No painel, a autenticação **libera tudo quando falta a senha** (e o serviço sobe em `0.0.0.0`). Também não há proteção **CSRF** nem contra **open redirect**. Na rotina de alertas, **um único e-mail inválido faz o worker reenviar todas as cobranças a cada 15 minutos**.

Todos os achados Crítico e Alto foram **reproduzidos** com scripts fora do repositório. As correções propostas no plano foram **prototipadas numa cópia** do código: a suíte original continua passando e 35 testes novos também (**58 passed**). Os patches do apêndice aplicam sem conflito sobre `4813cee`, e lá a suíte inteira dá **66 passed** (inclui os 8 testes da revisão do catálogo).

| Severidade | Qtde | Itens |
|---|---|---|
| Crítico | 4 | C1 a C4 |
| Alto | 8 | A1 a A8 |
| Médio | 12 | M1 a M12 |
| Baixo | 15 | B1 a B15 |

---

## CRÍTICO

### C1. A varredura incremental perde arquivos: data antiga, arquivo movido ou restaurado
- **Onde:** `mo_obrigacoes/monitor.py:113-121`, `mo_obrigacoes/drive/google.py:189-191`, `mo_obrigacoes/drive/local.py:274-276`
- **Descrição:** a varredura incremental usa como marca d'água o maior `modifiedTime` já visto (`EstadoSync.ultimo_modificado`) e descarta todo arquivo com `modifiedTime <= marca`. Três situações escapam desse filtro:
  - o Drive **não altera `modifiedTime` quando o arquivo é movido** entre pastas;
  - o *Google Drive para computador* e cópias com `cp -p` **preservam a data original** do arquivo;
  - um arquivo restaurado da lixeira volta com a data antiga.
- **Cenários de falha:**
  1. O cliente digitaliza o extrato em 20/09 e só o sobe pelo Drive para computador em 10/10. O arquivo nunca é lido, a tarefa fica pendente e o cliente recebe cobrança de um documento que já depositou.
  2. A equipe segue a orientação da tela ("CNPJ de outra empresa: mova o arquivo para a pasta correta") e move o arquivo. A empresa de destino nunca o enxerga e a baixa não acontece.
- **Evidência (reproduzida):** script `r_mon.py` com `LocalDriveClient` e `os.utime` para 20 dias atrás. Saída `sync2 (arquivo com mtime antigo): 0 lidos; DOC_EXTRATOS: pendente`. Com um serviço Google simulado, um arquivo movido para B com `modifiedTime` 01/10, quando a marca d'água de B é 05/10, resulta em listagem `[]`.
- **Correção:** a implementação Google **já percorre a árvore inteira** a cada ciclo, porque o filtro é aplicado depois de listar, então remover o filtro não custa nenhuma chamada a mais à API. A proposta:
  - listar sem filtro de data;
  - comparar cada arquivo com os `Documento` já gravados para a empresa (id, md5, `modifiedTime` e caminho);
  - processar só os novos ou alterados.

  Pacote B, item B-1.

### C2. A baixa automática continua valendo depois que o comprovante é apagado, substituído, reclassificado ou movido
- **Onde:** `monitor.py:161-189`, ou seja, `doc.tarefa_id = None` nas linhas 166, 175 e 182 sem reabrir a tarefa. Não existe detecção de arquivo removido. `classificar_manual`, em `monitor.py:201-225`, tem o mesmo problema.
- **Descrição:** quando o documento deixa de comprovar a tarefa, o vínculo é apagado, mas a tarefa **continua "entregue"** e fica sem nenhum comprovante. Um arquivo apagado ou enviado à lixeira nunca é detectado: `trashed = false` simplesmente o omite da listagem.
- **Cenários de falha:**
  1. A equipe salva por engano o DAS de agosto na pasta de setembro e depois troca o arquivo, ou o apaga. A tarefa de setembro segue "entregue" e a guia não é paga, o que gera multa e juros.
  2. O PGDAS é substituído por outro conteúdo e o documento vira "não identificado", mas a tarefa segue baixada.
  3. Na reclassificação manual de um documento já ligado a DAS 08 para DAS 09, as duas tarefas ficam baixadas.
- **Evidência (reproduzida):** `sync5 completo apos apagar das.pdf: DAS A = entregue` e `sync7 conteudo trocado: doc nao_identificado tarefa_id None | PGDAS A ainda: entregue docs ligados: 0`.
- **Correção:**
  - função `reabrir_baixa_automatica()`, que reabre a tarefa só se `origem_baixa == "drive"` e não restar outro documento válido ligado a ela. Baixas manuais e dispensas não são tocadas;
  - marcar como `removido` os documentos que sumiram da pasta, com proteção contra pasta esvaziada em massa;
  - chamar a reabertura em toda troca de vínculo.

  Pacote B, itens B-2 e B-3.

### C3. O painel sem `MO_ADMIN_PASSWORD` fica aberto para qualquer um, inclusive pela internet
- **Onde:** `web/app.py:62-65`, `config.py:32` (senha padrão `""`), `cli.py:158` (`--host 0.0.0.0`), `docker-compose.yml` (`ports: 8000:8000`)
- **Descrição:** sem senha, `usuario_atual` devolve `"admin"` para **qualquer** requisição. O controle *falha aberto*: basta esquecer a variável no `.env`, ou um erro de digitação no nome dela, para expor o sistema.
- **Cenário de falha:** em produção, o `.env` é copiado sem a senha. Qualquer pessoa na rede (ou na internet, se a porta estiver publicada) consegue:
  - listar CNPJ/CPF, e-mails e WhatsApp de todos os clientes (`/api/tarefas`, `/empresas`), o que é dado pessoal sob a LGPD;
  - dar baixa ou dispensar obrigações;
  - disparar e-mails de cobrança a todos os clientes (`POST /acoes/alertas`).
- **Evidência (reproduzida):** com `admin_password=""`, `GET /api/tarefas` retorna 200 e `POST /acoes/alertas` retorna 303, ambos sem credenciais.
- **Correção:** falhar fechado. Sem senha, aceitar só conexões da própria máquina (`127.0.0.1`/`::1`, que mantém a demonstração funcionando) e devolver **503** para o resto. Pacote A, item A-1.

### C4. Um e-mail inválido faz o worker reenviar resumos e cobranças a cada 15 minutos
- **Onde:** `alertas.py:61-66`, onde exceções do SMTP propagam, e `cli.py:106-116`, onde `ultimo_alerta` só é marcado se tudo der certo e um erro na sincronização também pula os alertas.
- **Descrição:** uma `SMTPRecipientsRefused`, causada por um único endereço inválido, interrompe `executar_alertas`. A transação é desfeita, inclusive o registro `ultimo_alerta_em` das cobranças que **já foram enviadas**. O worker não marca o dia como concluído e repete tudo no ciclo seguinte.
- **Cenário de falha:** o e-mail do cliente 0002 está errado. A cada 15 minutos o gestor, cada responsável e os clientes processados antes de 0002 recebem tudo de novo. São cerca de 68 e-mails por dia por destinatário, e o domínio do escritório acaba em listas de bloqueio.
- **Evidência (reproduzida):** `r_alert.py`. Rodadas 1 e 2 falharam com `SMTPRecipientsRefused`, cada uma enviando `g@x`, carla, ana e financeiro@0001, e no final `ultimo_alerta_em gravado? False`.
- **Correção:**
  - `Notificador.email` captura `SMTPException`/`OSError`, registra no log e devolve `False`;
  - o worker marca o dia **antes** de enviar e isola agenda/sync de alertas em blocos `try` separados.

  Pacotes D-1 e D-3.

---

## ALTO

### A1. Nenhum POST tem proteção CSRF
- **Onde:** todas as rotas `@app.post` de `web/app.py` (linhas 183, 250, 267, 308, 347, 369, 375, 406, 411, 419)
- **Descrição:** o navegador reenvia automaticamente as credenciais HTTP Basic em formulários enviados de outro site, e não há token nem conferência de `Origin`/`Referer`.
- **Cenário de falha:** um funcionário logado abre uma página maliciosa, ou um e-mail com HTML. A página envia `POST /tarefas/{id}/acao acao=baixa` em série e "baixa" obrigações não entregues, ou troca o e-mail de cobrança de um cliente em `/empresas/salvar`, ou dispara cobranças.
- **Evidência (reproduzida):** POST com `Origin: https://site-malicioso.example` retornou **303 "Baixa manual registrada"**.
- **Correção:** em toda requisição POST, se houver `Origin` (ou `Referer`) e o host for diferente de `Host`, devolver **403**. Pacote A, item A-2.
  - **Nota de implantação:** atrás de proxy reverso é preciso preservar o `Host`. No nginx, isso é `proxy_set_header Host $host`.

### A2. Open redirect no campo `voltar`
- **Onde:** `web/app.py:310`, `318` e `329`, além de `_voltar`, linha 108
- **Descrição:** a checagem `startswith("/")` aceita `//evil.example`. Pior: na ação "dispensar" sem justificativa, `voltar` é usado na linha 318 **antes** de qualquer checagem, e então `https://evil.example` também passa.
- **Cenário de falha:** um link ou formulário de phishing leva a equipe a uma página falsa de login com a URL do domínio do escritório.
- **Evidência (reproduzida):** `Location: //evil.example/phish?...` e `Location: https://evil.example/login?...`.
- **Correção:** `_destino_seguro()`, que aceita só caminho interno (começa com `/`, mas não com `//` nem `/\`), aplicado dentro de `_voltar` e logo no início de `tarefa_acao`. Pacote A, item A-3.

### A3. Uma falha temporária de download vira classificação errada permanente
- **Onde:** `drive/base.py:72-76`, onde a exceção é engolida e devolve `""`, e `monitor.py:148`
- **Descrição:** num 403 `rateLimitExceeded`, num 5xx ou num timeout, o texto chega vazio e o arquivo é classificado **só pelo nome**. Como o md5 e a data são gravados, o arquivo **nunca é relido**.
- **Cenário de falha:** `DAS 09-2026.pdf` contém na verdade o **recibo do PGDAS-D**. Com o download falhando, ele vira "DAS", a guia aparece paga e o PGDAS fica pendente para sempre.
- **Evidência (reproduzida):** `r_falha.py`. O resultado foi `doc DAS classificado | DAS: entregue PGDAS_D: pendente`, e a sincronização seguinte, já com a API funcionando, leu `0 lidos; doc continua DAS`.
- **Correção:** `ler_texto` passa a lançar `ErroLeitura` (Pacote E). O monitor lê o texto **antes** de gravar qualquer dado e, se der erro, não grava nada e tenta de novo no próximo ciclo (Pacote B).

### A4. Fuso horário: comprovante salvo à noite no dia do vencimento vira "entregue com atraso"
- **Onde:** `drive/google.py:138-141`, onde `_dt` devolve UTC sem fuso, e `monitor.py:60`, onde `quando.date() <= vencimento` compara a data UTC com o vencimento local
- **Descrição:** um arquivo salvo depois das 21h em Brasília tem data UTC do dia seguinte. Além disso, a baixa manual usa `datetime.now()` (hora local), enquanto o Drive usa UTC, e as duas aparecem misturadas na mesma coluna.
- **Cenário de falha:** o PGDAS vence em 20/10 e o recibo é salvo às 21:30 de 20/10. A tarefa vira **"entregue com atraso"** e prejudica o indicador de pontualidade do responsável.
- **Evidência (reproduzida):** `baixa as 21:30 BRT do dia do vencimento -> entregue_atraso 2026-10-21 00:30:00`.
- **Correção:** `_dt` converte para `America/Sao_Paulo` antes de remover o fuso (Pacote E, item E-1). O fallback `datetime.utcnow()` do monitor vira `datetime.now()` (Pacote B).

### A5. Um documento antigo no Drive gera a agenda inteira daquela competência
- **Onde:** `monitor.py:191-198` (`gerar_agenda(self.sessao, competencia, [emp])`) e `monitor.py:210-212`
- **Descrição:** ao achar um comprovante de uma competência sem tarefa, o monitor gera **todas** as tarefas da empresa naquela competência. Todas nascem pendentes e já vencidas.
- **Cenário de falha:** a primeira varredura completa encontra o histórico de 2019 a 2025 de cada cliente. Surgem centenas de "atrasadas" falsas no painel e nos e-mails, e a **cobrança automática ao cliente** pede extratos e XML de 2024.
- **Evidência (reproduzida):** um único DAS 03/2024 criou **8 tarefas**, 7 delas pendentes: `PGDAS_D, DCTFWEB, DARF_DCTFWEB, PROLABORE, ESOCIAL, DOC_EXTRATOS, DOC_NOTAS_FISCAIS`.
- **Correção:** criar **só a tarefa da obrigação do documento**, com a função `tarefa_da_competencia()`. Pacote B, item B-4.

### A6. A competência deduzida só pela data do arquivo gera baixa automática
- **Onde:** `classificador.py:286-295` (última opção, `data_arquivo`) e `monitor.py:173-189`
- **Descrição:** quando não há competência no texto, no nome nem na pasta, o classificador supõe "mês anterior à data do arquivo" e o monitor **dá baixa** com base nesse palpite.
- **Cenário de falha:** o DAS de **agosto**, pago com atraso, é salvo em outubro na raiz da pasta. A baixa vai para **setembro**, e o DAS de setembro, que não foi pago, some do radar.
- **Evidência (reproduzida):** `DAS sem competencia: ('DAS', 60, '2026-09', 'data_arquivo')`, e a tarefa recebe baixa.
- **Correção:** o documento vai para "Para revisar", com a sugestão preenchida e sem baixa automática. Pacote B, item B-5.

### A7. O regex de competência pega datas de emissão, transmissão, vencimento, quantidades e endereços
- **Onde:** `classificador.py:90-96` e `119-139`
- **Descrição e evidência (reproduzidas com `r_class.py`):**

  | Texto | Esperado | Obtido |
  |---|---|---|
  | `Data da transmissão: 15/10/2026 … Período de apuração: 2026-09` | 2026-09 | **2026-10** |
  | `Recibo … Data de transmissão 14/10/2026 10:31` (sem rótulo) | sem competência | **2026-10** (`_RE_ANO_MES` casa "2026 10" da hora) |
  | `Exercício 2026 Ano-calendário 2025` (anual) | 2025-12 | **2026-12** |
  | XML NF-e com `<qCom>12.2000</qCom>` antes de `<dhEmi>2026-09…` | 2026-09 | **2000-12** |
  | `Rua do Mar 2026` | sem competência | **2026-03** |

- **Correção:** Pacote C:
  - `_RE_MES_ANO` não casa dentro de datas `dd/mm/aaaa`;
  - `_RE_ANO_MES` não aceita espaço como separador;
  - no XML, `dhEmi`/`dEmi`/`dCompet` têm prioridade;
  - ano-calendário tem prioridade sobre exercício;
  - mês abreviado ("mar", "set") só vale com separador (`set/2026`);
  - `período`/`referência` com data completa usam o mês da data.

### A8. Nenhuma chamada à API do Google tem retry com backoff
- **Onde:** `drive/google.py:168` (`execute()`), `220` (`next_chunk()`), `230` e `237`
- **Descrição:** os erros 429, 403 `userRateLimitExceeded` e 5xx são esperados em produção e o Google recomenda backoff exponencial. Sem isso, a varredura de uma empresa aborta por qualquer soluço da API, e o download cai em A3.
- **Evidência:** inspeção de código. Não foi reproduzido contra a API real.
- **Correção:** `execute(num_retries=5)` e `next_chunk(num_retries=5)`. A biblioteca `googleapiclient` já implementa o backoff exponencial. Pacote E, item E-2.

---

## MÉDIO

### M1. Injeção na query do Drive pelo `drive_folder_id`
- **Onde:** `drive/google.py:162` e `226`. O valor vem do formulário (`web/app.py:205`) ou do CSV de importação (`cli.py:68`).
- **Descrição:** `pai_id`/`pasta_id` entram sem escape em `q="'...' in parents"`. O nome da pasta é escapado corretamente na linha 224, mas o ID não.
- **Evidência (reproduzida):** com `drive_folder_id = abc' in parents or 'root`, a query fica `'abc' in parents or 'root' in parents and trashed = false`. A empresa passa a "enxergar" arquivos de outra pasta: vazamento entre clientes e baixas erradas. Exige usuário autenticado ou o CSRF de A1.
- **Correção:** `validar_id()` aceita só `[A-Za-z0-9_-]+` no cliente Google (E-3), e o painel valida o formato no cadastro (A-6).

### M2. Competência sem validação: erro 500 e tarefas-lixo ("2026-13", "2026-9")
- **Onde:** `web/app.py:86-89` (`_competencia` só confere o tamanho e o hífen), `352`, `408`, e `monitor.py:201`
- **Evidência (reproduzida):**
  - `GET /?competencia=abcd-ef` → **500**;
  - `POST /acoes/agenda competencia=2026-13` → **42 tarefas criadas** na competência 13;
  - classificar um documento com `2026-9` cria a tarefa "2026-9", duplicada da "2026-09".
- **Correção:** regex `^\d{4}-(0[1-9]|1[0-2])$` no painel (A-4) e em `classificar_manual` (B-6).

### M3. O nome do arquivo sozinho dá baixa, inclusive com "das" usado como preposição
- **Onde:** `classificador.py:244-251`; o padrão de nome do DAS em `catalogo.py:61` casa "das" como palavra solta
- **Evidência (reproduzida):** `Comprovante das despesas.pdf` digitalizado na pasta Fiscal é classificado como `('DAS', 60, '2026-09', 'pasta')` e recebe baixa.
- **Correção no escopo deste plano (C-4):** sem texto, o nome só vale 50 pontos se a competência vier do nome ou da pasta. Caso contrário vale 35 e o arquivo vai para revisão.
- **Recomendação ao revisor do catálogo (fora deste plano):** restringir o padrão de nome do DAS, por exemplo exigindo que "das" esteja no início do nome ou seguido de mês ou ano.

### M4. O STARTTLS do SMTP não valida o certificado do servidor
- **Onde:** `alertas.py:62` (`s.starttls()` sem `context`). No Python, `smtplib` usa então `ssl._create_stdlib_context()`, que **não verifica o certificado**.
- **Cenário de falha:** um MITM na rede captura a senha de app do Gmail/Workspace e lê as cobranças, que contêm dados de clientes.
- **Correção:** `s.starttls(context=ssl.create_default_context())`. Pacote D, item D-2.

### M5. A sincronização inteira roda numa única transação
- **Onde:** `monitor.py:84-102` e `cli.py:88-90`
- **Descrição:** com SQLite compartilhado entre os containers `web` e `worker`, a trava de escrita fica presa durante toda a varredura e os POST do painel falham com "database is locked". No PostgreSQL, um `DataError` numa empresa (nome com mais de 400 caracteres, por exemplo) aborta a transação e **todas as empresas seguintes falham**. Uma queda no meio perde tudo.
- **Evidência:** análise de código, não reproduzido.
- **Correção:** `commit()` por empresa e `rollback()` no erro. Pacote B, item B-7.

### M6. As ações de tarefa ignoram o status atual
- **Onde:** `web/app.py:313-326`
- **Evidência (reproduzida):**
  - "dispensar" numa tarefa já entregue sobrescreve o status e a data de entrega, perdendo a evidência;
  - "Baixar" numa tarefa concluída mostra "Baixa manual registrada" sem ter feito nada.
- **Correção:** Pacote A, item A-5.

### M7. Salvar a empresa apaga as personalizações `ajuste`/`regra`; id inexistente gera 500
- **Onde:** `web/app.py:187` e `212-225`
- **Evidência (reproduzida):** `{"ICMS": {"dia": 9, "ajuste": "posterga"}}` vira `{"ICMS": {"dia": 9}}` depois de salvar, e o prazo do ICMS muda sem ninguém perceber. Um POST com `id=999` retorna 500.
- **Correção:** Pacote A, item A-6.

### M8. `/api/docs`, `/redoc` e `/openapi.json` são públicos, sem senha
- **Onde:** `web/app.py:124`
- **Evidência (reproduzida):** 200 sem credenciais. Expõe o mapa completo da API.
- **Correção:** `docs_url=None, redoc_url=None, openapi_url=None`. Pacote A, item A-7.

### M9. A auditoria registra um único usuário, "admin"
- **Onde:** `web/app.py:62-71` e `Evento.usuario`
- **Descrição:** o HTTP Basic com credencial compartilhada impede saber quem baixou, dispensou ou reabriu uma tarefa. A documentação promete esse controle em `implantacao.md` §7. Também não há limite de tentativas de login.
- **Correção:** evolução de produto. Usuários individuais (tabela `Usuario`, com senha em hash) ou SSO Google Workspace, mais limite de tentativas no proxy. **Opcional**, fora do plano mecânico.

### M10. PDF malicioso pode travar o worker
- **Onde:** `requirements.txt:6` (`pypdf>=4.0` permite versões com CVEs de DoS, como loop infinito e *decompression bomb*, corrigidos na série 6.x) e `drive/base.py:93-106` (sem limite de tempo)
- **Descrição:** o PDF é enviado pelo cliente, e um travamento derruba o monitoramento de **toda** a carteira.
- **Correção:** fixar `pypdf>=6.1,<7` (E-4). Extração em subprocesso com timeout é **opcional**.

### M11. A varredura recursiva lista todas as pastas de todas as empresas a cada ciclo
- **Onde:** `drive/google.py:174-205`
- **Descrição:** a estrutura padrão tem cerca de 62 pastas por empresa e por ano. Com 300 empresas e 5 anos, são aproximadamente 93 mil chamadas `files.list` por ciclo, e o intervalo de 15 minutos fica inviável. O filtro por data não reduz esse custo, porque é aplicado depois da listagem.
- **Correção (opcional, evolução):** usar a **Changes API** (`changes.getStartPageToken` / `changes.list`) com o token salvo por drive. Já prevista em `arquitetura.md` §4.7.

### M12. "Verificar Google Drive agora" e "Reprocessar pasta" rodam dentro da requisição HTTP
- **Onde:** `web/app.py:267-276` e `411-417`
- **Descrição:** com muitas empresas, a requisição estoura o tempo limite do proxy. Se roda junto com o worker, os dois podem inserir o mesmo `drive_file_id` e causar `IntegrityError`, resultando em 500.
- **Correção (opcional):** enfileirar o pedido (gravar um "pedido de sync" que o worker atende) ou usar um lock por empresa. Com o commit por empresa do item B-7, o impacto diminui.

---

## BAIXO

| # | Onde | Achado | Evidência | Correção |
|---|---|---|---|---|
| B1 | `monitor.py:122` | `arquivos_vistos` soma o total acumulado de **todas** as empresas já processadas | Reproduzido: a empresa B, sem arquivos, ficou com 1 | Pacote B, item B-1 (contagem por empresa) |
| B2 | `web/app.py:238` e `empresa.html:19` | N+1: `t.documentos` carregado de forma preguiçosa em cada célula da matriz | Medido: 62 queries com 4 competências (cerca de 170 com 12) | `selectinload(Tarefa.documentos)`, item A-8 |
| B3 | `painel.html:10`, `eventos.html:4`, `app.py:314`, `monitor.py:120/143` | Horários em UTC na tela misturados com horário local (baixa manual) | Inspeção | Opcional: filtro Jinja `local()` para exibir em Brasília |
| B4 | `app.py:301, 342, 443` | Limites silenciosos (1000 tarefas, 500 documentos, 5000 na API) sem aviso nem paginação | Inspeção | Opcional: aviso "mostrando N de M" |
| B5 | `painel.html:9`, `empresa.html:8` | "Enviar alertas" manda e-mails **aos clientes** sem confirmação | Inspeção | `onsubmit=confirm(...)`, item A-9 |
| B6 | `relatorios.py:86-93` | CSV sujeito a *formula injection* (`=`, `+`, `-`, `@` no início de razão social ou observação) | Inspeção | Opcional: prefixar `'` |
| B7 | `app.py:104` e `base.html:15` | `?msg=` refletido (escapado, então sem XSS, mas permite *content spoofing* em links de phishing) | Inspeção | Opcional: códigos de mensagem em vez de texto livre |
| B8 | `models.py:218-226` | Nome (400) e caminho (800) sem truncamento: `DataError` no PostgreSQL | Inspeção | Opcional: truncar em `processar_arquivo` |
| B9 | `alertas.py:211` | Cliente só com WhatsApp nunca é cobrado (o webhook só sai junto com o e-mail) | Inspeção | Opcional |
| B10 | `calendario.py:22` | `FERIADOS_EXTRAS` não é carregado de nenhuma configuração, embora a documentação mande "incluir" feriados municipais | Inspeção | Opcional: ler `MO_FERIADOS_EXTRAS=AAAA-MM-DD,...` |
| B11 | `app.py:229` e `agenda.py:90-100` | Mudar o perfil da empresa (ex.: deixou de ter empregados) não remove tarefas pendentes futuras que deixaram de se aplicar | Inspeção | Opcional |
| B12 | `drive/local.py:270-284` | Lê o arquivo inteiro para calcular o md5 e segue symlinks para fora da raiz (o download é bloqueado, a leitura do md5 não) | Reproduzido: symlink listado | Ignorar symlinks na listagem, item E-5 |
| B13 | `painel.html` | Empresas com erro de varredura (`EstadoSync.ultimo_erro`) só aparecem na tela da própria empresa | Inspeção | Opcional: cartão "Empresas com erro no Drive" |
| B14 | `alertas.py:68-78` | O webhook aceita `http://` e envia CNPJ e WhatsApp a terceiros (Z-API, Twilio) | Inspeção | Exigir `https://` e documentar o operador de dados (LGPD) |
| B15 | `relatorios.py:33` e `models.py:195` | "Vencem em N dias" usa 3 fixo, enquanto o rótulo mostra `MO_DIAS_ALERTA_VENCIMENTO` | Inspeção | Opcional: passar `dias_alerta` |

## Verificado e sem problema

- **XSS:** o `Jinja2Templates` do Starlette usa `select_autoescape`, então o *autoescape* está ligado para `.html`; confirmado com `templates.env.autoescape`. Nomes de arquivo enviados pelo cliente saem escapados. Os e-mails usam `html.escape` em todos os campos variáveis. Links `href` vêm do Drive (`webViewLink`) ou de `Path.as_uri()`, sem possibilidade de `javascript:` controlado pelo cliente.
- **Escape do nome da pasta** em `garantir_pasta` (`\` e `'`): correto conforme a documentação da Drive API. Só o ID ficou sem tratamento (M1).
- **Path traversal no `LocalDriveClient`:** `_resolver` usa `resolve()` e confere a raiz. `../`, `A/../../` e `/etc` foram bloqueados (reproduzido).
- **Comparação de senha:** `secrets.compare_digest`.
- **Segredos:** `.env`, `credenciais/` e `service-account*.json` estão no `.gitignore`.
- **Redirect com `/\`:** o Starlette codifica a barra invertida como `%5C`.

## LGPD (resumo)

- **Dados pessoais tratados:** CPF de clientes pessoa física, e-mail e WhatsApp de clientes, e-mail de quem enviou cada arquivo e e-mails da equipe.
- **Recomendações:**
  - corrigir C3, A1 e M4;
  - exigir HTTPS (o painel não deve ser publicado sem TLS);
  - definir prazo de retenção para `eventos` e `documentos.detalhes`;
  - registrar Z-API/Twilio como operadores no contrato;
  - incluir no texto da cobrança um canal para o cliente pedir para não receber mensagens.
- O banco realmente não guarda o conteúdo dos documentos, só metadados e CNPJs encontrados, como afirma a documentação.

## Lacunas de teste (antes deste parecer)

Os 23 testes cobrem o caminho feliz. Não havia teste para:
- autenticação sem senha, CSRF e open redirect;
- validação de competência;
- sync incremental com data antiga ou arquivo movido;
- arquivo apagado ou substituído;
- reclassificação e falha de download;
- fuso horário;
- regex de competência com datas que não são a competência;
- falha de SMTP;
- retries e escape de ID na API do Google.

O plano adiciona 35 testes que cobrem todos esses pontos.

---

# Apêndice: patches validados

Aplicados juntos sobre `ee6b4e0`, resultam em **58 passed** (23 originais e 35 novos). Sobre `4813cee`, com a revisão do catálogo, resultam em **66 passed**. Cada patch passa em `git apply --check` isoladamente. **Ordem:** E antes de B, porque B importa `ErroLeitura`. A, C e D são independentes.


## Patch do Pacote E (drive/base.py, drive/google.py, tests/test_google_drive.py)

```diff
--- a/mo_obrigacoes/drive/base.py
+++ b/mo_obrigacoes/drive/base.py
@@ -28,6 +28,10 @@
     enviado_por: str = ""
 
 
+class ErroLeitura(Exception):
+    """Falha (possivelmente temporária) ao baixar o arquivo: o monitor deve tentar de novo na próxima varredura."""
+
+
 class DriveClient(ABC):
     @abstractmethod
     def listar_arquivos(self, pasta_id: str, modificado_apos: datetime | None = None) -> Iterator[ArquivoDrive]:
@@ -48,7 +52,7 @@
             dados = self.baixar(arquivo)
         except Exception as exc:  # noqa: BLE001
             log.warning("Falha ao baixar %s: %s", arquivo.nome, exc)
-            return ""
+            raise ErroLeitura(f"falha ao baixar '{arquivo.nome}': {exc}") from exc
         return extrair_texto(dados, arquivo.nome, arquivo.mime_type)
 
 
--- a/mo_obrigacoes/drive/google.py
+++ b/mo_obrigacoes/drive/google.py
@@ -11,9 +11,11 @@
 from __future__ import annotations
 
 import io
+import re
 from collections import deque
 from datetime import datetime
 from typing import Iterator
+from zoneinfo import ZoneInfo
 
 from .base import ArquivoDrive, DriveClient
 
@@ -23,6 +25,18 @@
     "application/vnd.google-apps.document": "text/plain",
     "application/vnd.google-apps.spreadsheet": "text/csv",
 }
+FUSO_ESCRITORIO = ZoneInfo("America/Sao_Paulo")
+TENTATIVAS = 5  # novas tentativas com espera exponencial em 429/5xx (googleapiclient)
+_RE_ID = re.compile(r"[A-Za-z0-9_-]+")
+
+
+def validar_id(valor: str) -> str:
+    """IDs do Drive têm só letras, números, '_' e '-'. Impede injeção na query (q=...)."""
+    if not _RE_ID.fullmatch(valor or ""):
+        raise ValueError(f"ID de pasta do Drive inválido: {valor!r}")
+    return valor
+
+
 CAMPOS = (
     "nextPageToken, files(id, name, mimeType, size, md5Checksum, createdTime, modifiedTime, "
     "webViewLink, lastModifyingUser(emailAddress, displayName), owners(emailAddress))"
@@ -32,7 +46,8 @@
 def _dt(valor: str | None) -> datetime | None:
     if not valor:
         return None
-    return datetime.fromisoformat(valor.replace("Z", "+00:00")).replace(tzinfo=None)
+    # converte para o horário de Brasília (sem tzinfo): a data de entrega é comparada com o vencimento local
+    return datetime.fromisoformat(valor.replace("Z", "+00:00")).astimezone(FUSO_ESCRITORIO).replace(tzinfo=None)
 
 
 class GoogleDriveClient(DriveClient):
@@ -53,13 +68,13 @@
         token = None
         while True:
             resp = self.servico.files().list(
-                q=f"'{pasta_id}' in parents and trashed = false",
+                q=f"'{validar_id(pasta_id)}' in parents and trashed = false",
                 fields=CAMPOS,
                 pageSize=1000,
                 pageToken=token,
                 supportsAllDrives=True,
                 includeItemsFromAllDrives=True,
-            ).execute()
+            ).execute(num_retries=TENTATIVAS)
             yield from resp.get("files", [])
             token = resp.get("nextPageToken")
             if not token:
@@ -111,22 +126,22 @@
         down = MediaIoBaseDownload(buf, req)
         concluido = False
         while not concluido:
-            _, concluido = down.next_chunk()
+            _, concluido = down.next_chunk(num_retries=TENTATIVAS)
         return buf.getvalue()
 
     def garantir_pasta(self, nome: str, pai_id: str) -> str:
         nome_q = nome.replace("\\", "\\\\").replace("'", "\\'")
         resp = self.servico.files().list(
-            q=f"'{pai_id}' in parents and name = '{nome_q}' and mimeType = '{PASTA}' and trashed = false",
+            q=f"'{validar_id(pai_id)}' in parents and name = '{nome_q}' and mimeType = '{PASTA}' and trashed = false",
             fields="files(id)",
             supportsAllDrives=True,
             includeItemsFromAllDrives=True,
-        ).execute()
+        ).execute(num_retries=TENTATIVAS)
         if resp.get("files"):
             return resp["files"][0]["id"]
         criada = self.servico.files().create(
             body={"name": nome, "mimeType": PASTA, "parents": [pai_id]},
             fields="id",
             supportsAllDrives=True,
-        ).execute()
+        ).execute(num_retries=TENTATIVAS)
         return criada["id"]
--- a/tests/test_google_drive.py
+++ b/tests/test_google_drive.py
@@ -20,7 +20,7 @@
     def __init__(self, r):
         self.r = r
 
-    def execute(self):
+    def execute(self, num_retries=0):
         return self.r
 
 
```

## Patch do Pacote B (monitor.py)

```diff
--- a/mo_obrigacoes/monitor.py
+++ b/mo_obrigacoes/monitor.py
@@ -10,15 +10,17 @@
 from __future__ import annotations
 
 import logging
+import re
 from dataclasses import dataclass, field
 from datetime import datetime
 
-from sqlalchemy import select
+from sqlalchemy import func, select
 from sqlalchemy.orm import Session
 
-from .agenda import gerar_agenda, obrigacao_aplicavel
+from .agenda import obrigacao_aplicavel, ocorre_na_competencia, regra_efetiva
+from .calendario import calcular_vencimento
 from .classificador import Regra, classificar
-from .drive.base import ArquivoDrive, DriveClient
+from .drive.base import ArquivoDrive, DriveClient, ErroLeitura
 from .models import (
     STATUS_ENTREGUE,
     STATUS_ENTREGUE_ATRASO,
@@ -32,6 +34,8 @@
 )
 
 log = logging.getLogger(__name__)
+RE_COMPETENCIA = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
+SITUACOES_COM_TAREFA = ("classificado", "manual")
 
 
 @dataclass
@@ -69,6 +73,39 @@
     return True
 
 
+def reabrir_baixa_automatica(sessao: Session, tarefa: Tarefa | None, motivo: str) -> bool:
+    """Desfaz a baixa automática (origem 'drive') quando o comprovante deixou de valer
+    (arquivo apagado, movido para outra empresa ou reclassificado). Baixa manual e dispensa não são tocadas."""
+    if tarefa is None or tarefa.origem_baixa != "drive" or tarefa.status not in (STATUS_ENTREGUE, STATUS_ENTREGUE_ATRASO):
+        return False
+    sessao.flush()
+    outros = sessao.scalar(select(func.count(Documento.id)).where(
+        Documento.tarefa_id == tarefa.id, Documento.situacao.in_(SITUACOES_COM_TAREFA)))
+    if outros:
+        return False
+    tarefa.status, tarefa.data_entrega, tarefa.origem_baixa = STATUS_PENDENTE, None, ""
+    sessao.add(Evento(tipo="reabertura_automatica", empresa_id=tarefa.empresa_id, tarefa_id=tarefa.id,
+                      mensagem=f"{tarefa.obrigacao.codigo} {tarefa.competencia}: {motivo}"))
+    return True
+
+
+def tarefa_da_competencia(sessao: Session, emp: Empresa, ob: Obrigacao, competencia: str,
+                          mesmo_fora_do_perfil: bool = False) -> Tarefa | None:
+    """Localiza a tarefa; se não existir, cria SÓ ela (nunca a agenda inteira da competência)."""
+    stmt = select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
+                                Tarefa.competencia == competencia)
+    tarefa = sessao.scalar(stmt)
+    if tarefa is not None:
+        return tarefa
+    if not mesmo_fora_do_perfil and not (obrigacao_aplicavel(emp, ob) and ocorre_na_competencia(ob, competencia)):
+        return None
+    tarefa = Tarefa(empresa_id=emp.id, obrigacao_id=ob.id, competencia=competencia,
+                    vencimento=calcular_vencimento(regra_efetiva(emp, ob), competencia, ob.periodicidade))
+    sessao.add(tarefa)
+    sessao.flush()
+    return tarefa
+
+
 class Monitor:
     def __init__(self, sessao: Session, drive: DriveClient):
         self.sessao = sessao
@@ -83,6 +120,7 @@
     # ------------------------------------------------------------------
     def sincronizar(self, empresas: list[Empresa] | None = None, completo: bool = False) -> ResumoSync:
         resumo = ResumoSync()
+        self.sessao.commit()  # grava o que o chamador já tinha pendente: o rollback de uma empresa não pode apagá-lo
         if empresas is None:
             empresas = list(self.sessao.scalars(
                 select(Empresa).where(Empresa.ativa.is_(True), Empresa.drive_folder_id != "")))
@@ -90,10 +128,13 @@
             resumo.empresas += 1
             try:
                 self.sincronizar_empresa(emp, resumo, completo)
+                self.sessao.commit()  # grava empresa a empresa: libera o banco e não perde o que já foi feito
             except Exception as exc:  # noqa: BLE001 - uma empresa com erro não interrompe as demais
                 log.exception("Erro ao sincronizar %s", emp.codigo)
+                self.sessao.rollback()
                 resumo.erros.append(f"{emp.codigo}: {exc}")
                 self._estado(emp).ultimo_erro = str(exc)[:2000]
+                self.sessao.commit()
         self.sessao.add(Evento(tipo="sync", mensagem=(
             f"{resumo.empresas} empresa(s), {resumo.arquivos_lidos} arquivo(s) lido(s), "
             f"{resumo.baixas} baixa(s), {resumo.nao_identificados} não identificado(s), "
@@ -109,27 +150,64 @@
         return est
 
     def sincronizar_empresa(self, emp: Empresa, resumo: ResumoSync, completo: bool = False) -> None:
+        """Lista a pasta inteira (sem filtro por data: arquivos movidos ou com data antiga também contam),
+        processa o que é novo ou mudou e trata os arquivos que sumiram da pasta."""
         est = self._estado(emp)
-        desde = None if completo else est.ultimo_modificado
+        conhecidos = {d.drive_file_id: d for d in self.sessao.scalars(
+            select(Documento).where(Documento.empresa_id == emp.id))}
+        vistos: set[str] = set()
         maior = est.ultimo_modificado
-        for arq in self.drive.listar_arquivos(emp.drive_folder_id, desde):
-            resumo.arquivos_lidos += 1
-            self.processar_arquivo(emp, arq, resumo, forcar=completo)
+        lidos = 0
+        for arq in self.drive.listar_arquivos(emp.drive_folder_id, None):
+            vistos.add(arq.id)
             if arq.modificado_em and (maior is None or arq.modificado_em > maior):
                 maior = arq.modificado_em
+            doc = conhecidos.get(arq.id)
+            if not completo and doc is not None and self._inalterado(doc, arq):
+                continue
+            lidos += 1
+            self.processar_arquivo(emp, arq, resumo, forcar=completo)
+        resumo.arquivos_lidos += lidos
+        sumidos = [d for i, d in conhecidos.items() if i not in vistos and d.situacao != "removido"]
+        if not vistos and len(sumidos) > 3:
+            # pasta vazia de repente (permissão retirada?): não desfaz baixas em massa
+            est.ultimo_erro = f"Pasta sem nenhum arquivo, mas {len(sumidos)} documento(s) registrados: verifique o compartilhamento"
+        else:
+            for doc in sumidos:
+                self._marcar_removido(doc)
+            est.ultimo_erro = ""
         est.ultima_varredura = datetime.utcnow()
         est.ultimo_modificado = maior
-        est.arquivos_vistos = (est.arquivos_vistos or 0) + resumo.arquivos_lidos
-        est.ultimo_erro = ""
+        est.arquivos_vistos = len(vistos)
+
+    @staticmethod
+    def _inalterado(doc: Documento, arq: ArquivoDrive) -> bool:
+        return (doc.situacao != "removido" and doc.md5 == arq.md5 and doc.modificado_drive_em == arq.modificado_em
+                and doc.caminho == arq.caminho)
+
+    def _marcar_removido(self, doc: Documento) -> None:
+        tarefa = doc.tarefa
+        doc.situacao, doc.tarefa = "removido", None
+        self.sessao.add(Evento(tipo="documento_removido", empresa_id=doc.empresa_id,
+                               mensagem=f"'{doc.nome}' não está mais na pasta do Drive"))
+        reabrir_baixa_automatica(self.sessao, tarefa, f"comprovante '{doc.nome}' removido do Drive")
 
     # ------------------------------------------------------------------
     def processar_arquivo(self, emp: Empresa, arq: ArquivoDrive, resumo: ResumoSync | None = None,
-                          forcar: bool = False) -> Documento:
+                          forcar: bool = False) -> Documento | None:
         resumo = resumo or ResumoSync()
         doc = self.sessao.scalar(select(Documento).where(Documento.drive_file_id == arq.id))
-        if not forcar and doc is not None and doc.md5 == arq.md5 and doc.modificado_drive_em == arq.modificado_em \
-                and doc.empresa_id == emp.id:
+        if not forcar and doc is not None and self._inalterado(doc, arq) and doc.empresa_id == emp.id:
             return doc  # nada mudou
+        manual = doc is not None and doc.situacao == "manual"
+        texto = ""
+        if not manual:
+            try:
+                texto = self.drive.ler_texto(arq)  # lê ANTES de alterar o registro: em falha, tenta de novo depois
+            except ErroLeitura as exc:
+                resumo.erros.append(f"{emp.codigo}: {exc}")
+                return doc
+        tarefa_anterior = doc.tarefa if doc is not None else None
         novo = doc is None
         if novo:
             doc = Documento(drive_file_id=arq.id, nome=arq.nome)
@@ -142,10 +220,9 @@
         doc.enviado_por = arq.enviado_por
         doc.processado_em = datetime.utcnow()
 
-        if doc.situacao == "manual":  # classificação feita por pessoa prevalece
+        if manual:  # classificação feita por pessoa prevalece
             return doc
 
-        texto = self.drive.ler_texto(arq)
         res = classificar(self.regras, arq.nome, texto, arq.caminho, arq.criado_em or arq.modificado_em)
         doc.obrigacao_codigo = res.codigo or ""
         doc.competencia = res.competencia or ""
@@ -163,63 +240,54 @@
             outro = next((self.empresas_por_raiz[c[:8]] for c in res.cnpjs if c[:8] in self.empresas_por_raiz), None)
             if outro is not None:
                 doc.situacao = "divergente"
-                doc.tarefa_id = None
+                self._desvincular(doc, tarefa_anterior, None)
                 doc.detalhes["empresa_sugerida"] = f"{outro.codigo} - {outro.razao_social}"
                 resumo.divergentes += 1
                 self.sessao.add(Evento(tipo="documento_divergente", empresa_id=emp.id, mensagem=(
                     f"'{arq.nome}' está na pasta de {emp.codigo} mas pertence a {outro.codigo}")))
                 return doc
 
-        if not res.identificado or not res.competencia:
+        # competência deduzida só pela data do arquivo é palpite: vai para revisão, sem baixa automática
+        if not res.identificado or not res.competencia or res.origem_competencia == "data_arquivo":
             doc.situacao = "nao_identificado"
-            doc.tarefa_id = None
+            self._desvincular(doc, tarefa_anterior, None)
             resumo.nao_identificados += 1
             return doc
 
-        tarefa = self._tarefa_para(emp, self.por_codigo[res.codigo], res.competencia)
+        tarefa = tarefa_da_competencia(self.sessao, emp, self.por_codigo[res.codigo], res.competencia)
         if tarefa is None:
             doc.situacao = "sem_tarefa"
-            doc.tarefa_id = None
+            self._desvincular(doc, tarefa_anterior, None)
             return doc
 
         doc.situacao = "classificado"
-        doc.tarefa = tarefa
-        if dar_baixa(self.sessao, tarefa, arq.criado_em or arq.modificado_em or datetime.utcnow(), "drive"):
+        self._desvincular(doc, tarefa_anterior, tarefa)
+        if dar_baixa(self.sessao, tarefa, arq.criado_em or arq.modificado_em or datetime.now(), "drive"):
             resumo.baixas += 1
         return doc
 
-    def _tarefa_para(self, emp: Empresa, ob: Obrigacao, competencia: str) -> Tarefa | None:
-        stmt = select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
-                                    Tarefa.competencia == competencia)
-        tarefa = self.sessao.scalar(stmt)
-        if tarefa is None and obrigacao_aplicavel(emp, ob):
-            gerar_agenda(self.sessao, competencia, [emp])
-            tarefa = self.sessao.scalar(stmt)
-        return tarefa
+    def _desvincular(self, doc: Documento, anterior: Tarefa | None, nova: Tarefa | None) -> None:
+        """Liga o documento à nova tarefa e, se ele comprovava outra, desfaz aquela baixa automática."""
+        doc.tarefa = nova
+        if anterior is not None and anterior is not nova:
+            reabrir_baixa_automatica(self.sessao, anterior, f"comprovante '{doc.nome}' foi reclassificado ou movido")
 
 
 def classificar_manual(sessao: Session, doc: Documento, codigo: str, competencia: str, usuario: str) -> Tarefa | None:
     """Classificação feita pela equipe na tela 'Documentos não identificados'."""
+    if not RE_COMPETENCIA.fullmatch(competencia or ""):
+        raise ValueError("competência inválida (use AAAA-MM)")
     ob = sessao.scalar(select(Obrigacao).where(Obrigacao.codigo == codigo))
     if ob is None or doc.empresa is None:
         raise ValueError("obrigação ou empresa inválida")
+    anterior = doc.tarefa
     doc.obrigacao_codigo, doc.competencia, doc.situacao, doc.confianca = codigo, competencia, "manual", 100
-    stmt = select(Tarefa).where(Tarefa.empresa_id == doc.empresa_id, Tarefa.obrigacao_id == ob.id,
-                                Tarefa.competencia == competencia)
-    tarefa = sessao.scalar(stmt)
-    if tarefa is None:
-        gerar_agenda(sessao, competencia, [doc.empresa], usuario)
-        tarefa = sessao.scalar(stmt)
-    if tarefa is None:  # obrigação fora do perfil: cria mesmo assim, pois a pessoa confirmou
-        from .agenda import regra_efetiva
-        from .calendario import calcular_vencimento
-
-        tarefa = Tarefa(empresa_id=doc.empresa_id, obrigacao_id=ob.id, competencia=competencia,
-                        vencimento=calcular_vencimento(regra_efetiva(doc.empresa, ob), competencia, ob.periodicidade))
-        sessao.add(tarefa)
-        sessao.flush()
+    # obrigação fora do perfil: cria mesmo assim, pois a pessoa confirmou
+    tarefa = tarefa_da_competencia(sessao, doc.empresa, ob, competencia, mesmo_fora_do_perfil=True)
     doc.tarefa = tarefa
-    dar_baixa(sessao, tarefa, doc.criado_drive_em or datetime.utcnow(), "manual", usuario)
+    if anterior is not None and anterior is not tarefa:
+        reabrir_baixa_automatica(sessao, anterior, f"'{doc.nome}' reclassificado manualmente")
+    dar_baixa(sessao, tarefa, doc.criado_drive_em or datetime.now(), "manual", usuario)
     sessao.add(Evento(tipo="classificacao_manual", usuario=usuario, empresa_id=doc.empresa_id,
                       tarefa_id=tarefa.id, mensagem=f"'{doc.nome}' classificado como {codigo} {competencia}"))
     return tarefa
```

## Patch do Pacote C (classificador.py)

```diff
--- a/mo_obrigacoes/classificador.py
+++ b/mo_obrigacoes/classificador.py
@@ -85,15 +85,30 @@
     re.IGNORECASE,
 )
 _RE_ROTULO_DATA = re.compile(
-    r"(?:per[ií]odo de apura[cç][aã]o|compet[eê]ncia)\s*[:\-]?\s*\d{1,2}/(\d{1,2})/(\d{4})", re.IGNORECASE
+    r"(?:per[ií]odo de apura[cç][aã]o|compet[eê]ncia|per[ií]odo|refer[eê]ncia)\s*[:\-]?\s*\d{1,2}/(\d{1,2})/(\d{4})",
+    re.IGNORECASE,
 )
-_RE_ANO_CALENDARIO = re.compile(r"(?:ano[- ]calend[aá]rio|exerc[ií]cio|ano[- ]base)\s*[:\-]?\s*(\d{4})", re.IGNORECASE)
-_RE_MES_ANO = re.compile(r"(?<!\d)(0?[1-9]|1[0-2])\s*[/\-_. ]\s*(20\d{2})(?!\d)")
-_RE_ANO_MES = re.compile(r"(?<!\d)(20\d{2})\s*[/\-_. ]?\s*(0[1-9]|1[0-2])(?!\d)")
+_RE_ANO_CALENDARIO = re.compile(r"(?:ano[- ]calend[aá]rio|ano[- ]base)\s*[:\-]?\s*(\d{4})", re.IGNORECASE)
+_RE_EXERCICIO = re.compile(r"exerc[ií]cio\s*[:\-]?\s*(\d{4})", re.IGNORECASE)
+_RE_XML_DATA = re.compile(r"<(?:dhEmi|dEmi|dhCompet|dCompet)>\s*(\d{4})-(\d{2})")
+_RE_MES_ANO = re.compile(r"(?<![\d/.\-])(0?[1-9]|1[0-2])\s*[/\-_. ]\s*(20\d{2})(?!\d)")
+_RE_ANO_MES = re.compile(r"(?<![\d/])(20\d{2})[/\-_.]?(0[1-9]|1[0-2])(?!\d)")
+_MESES_COMPLETOS = [m for m in MESES if len(m) > 3]
+_MESES_ABREV = [m for m in MESES if len(m) == 3]
 _RE_MES_EXTENSO = re.compile(
-    r"\b(" + "|".join(sorted(MESES, key=len, reverse=True)) + r")\b\s*(?:de\s*|/|-|_|\.)?\s*(20\d{2})",
+    r"\b(" + "|".join(sorted(_MESES_COMPLETOS, key=len, reverse=True)) + r")\b\s*(?:de\s*|/|-|_|\.)?\s*(20\d{2})"
+    r"|\b(" + "|".join(_MESES_ABREV) + r")\s*[/\-_.]\s*(20\d{2})",
     re.IGNORECASE,
 )
+
+
+def _mes_extenso(m: re.Match) -> tuple[int, int]:
+    """(ano, mes) de um match de _RE_MES_EXTENSO (nome completo ou abreviado)."""
+    nome = m.group(1) or m.group(3)
+    ano = m.group(2) or m.group(4)
+    return int(ano), MESES[nome.lower()]
+
+
 _RE_TRIMESTRE = re.compile(r"(?<!\d)([1-4])\s*[ºo°]?\s*(?:tri(?:mestre)?|T)\s*[/\-_ ]?\s*(?:de\s*)?(20\d{2})", re.IGNORECASE)
 
 
@@ -109,9 +124,14 @@
         return None
     t = sem_acento(texto)
     if periodicidade == "anual":
-        m = _RE_ANO_CALENDARIO.search(t)
+        m = _RE_ANO_CALENDARIO.search(t) or _RE_EXERCICIO.search(t)
         if m:
             return _valida(int(m.group(1)), 12)
+    m = _RE_XML_DATA.search(t)
+    if m:
+        c = _valida(int(m.group(1)), int(m.group(2)))
+        if c:
+            return _ajustar(c, periodicidade)
     if periodicidade == "trimestral":
         m = _RE_TRIMESTRE.search(t)
         if m:
@@ -124,7 +144,7 @@
                 return _ajustar(c, periodicidade)
     m = _RE_MES_EXTENSO.search(t)
     if m:
-        c = _valida(int(m.group(2)), MESES[m.group(1).lower()])
+        c = _valida(*_mes_extenso(m))
         if c:
             return _ajustar(c, periodicidade)
     m = _RE_MES_ANO.search(t)
@@ -164,9 +184,9 @@
                 m = re.match(r"\s*(0?[1-9]|1[0-2])(?!\d)", partes[i + 1])
                 if m:
                     return _ajustar(competencia_str(ano, int(m.group(1))), periodicidade)
-                m = _RE_MES_EXTENSO.search(partes[i + 1] + f" {ano}")
+                m = _RE_MES_EXTENSO.search(partes[i + 1] + f"/{ano}")
                 if m:
-                    return _ajustar(competencia_str(ano, MESES[m.group(1).lower()]), periodicidade)
+                    return _ajustar(competencia_str(*_mes_extenso(m)), periodicidade)
     if ano and periodicidade == "anual":
         return competencia_str(ano, 12)
     return None
@@ -247,8 +267,10 @@
         elif texto.strip() and (conteudo or obrig):
             # há texto legível e ele não confirma a obrigação: o nome sozinho não basta
             pontos += 35
+        elif extrair_competencia(nome, regra.periodicidade) or competencia_por_caminho(caminho, regra.periodicidade):
+            pontos += 50  # PDF digitalizado (imagem) ou sem texto: vale o nome, se a competência vier do nome ou da pasta
         else:
-            pontos += 50  # PDF digitalizado (imagem) ou formato sem texto: vale o nome
+            pontos += 35  # sem texto e sem competência ("Comprovante das despesas.pdf" solto): só sugere
         motivos.append("nome do arquivo")
 
     pastas = rec.get("pastas", [])
```

## Patch do Pacote A (web/app.py e templates)

```diff
--- a/mo_obrigacoes/web/app.py
+++ b/mo_obrigacoes/web/app.py
@@ -1,10 +1,12 @@
 """Painel web (FastAPI + Jinja2)."""
 from __future__ import annotations
 
+import re
 import secrets
 from contextlib import asynccontextmanager
 from datetime import date, datetime, timedelta
 from pathlib import Path
+from urllib.parse import quote, urlsplit
 
 from fastapi import Depends, FastAPI, Form, HTTPException, Request
 from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
@@ -12,7 +14,7 @@
 from fastapi.staticfiles import StaticFiles
 from fastapi.templating import Jinja2Templates
 from sqlalchemy import func, select
-from sqlalchemy.orm import Session, joinedload
+from sqlalchemy.orm import Session, joinedload, selectinload
 
 from .. import agenda as agenda_mod
 from ..alertas import executar_alertas
@@ -59,10 +61,31 @@
 ]
 
 
-def usuario_atual(cred: HTTPBasicCredentials | None = Depends(seguranca)) -> str:
+RE_COMPETENCIA = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
+RE_ID_DRIVE = re.compile(r"[A-Za-z0-9_-]{10,}")
+HOSTS_LOCAIS = {"127.0.0.1", "::1", "localhost", "testclient"}
+
+
+def _verificar_origem(request: Request) -> None:
+    """Proteção CSRF: o navegador reenvia o login HTTP Basic em formulários vindos de outros sites.
+    POST só é aceito se Origin (ou, na falta dele, Referer) for o próprio painel."""
+    if request.method != "POST":
+        return
+    origem = request.headers.get("origin") or request.headers.get("referer")
+    if not origem:
+        return  # clientes que não são navegadores (curl, scripts)
+    if urlsplit(origem).netloc != request.headers.get("host", ""):
+        raise HTTPException(403, "Requisição de outra origem bloqueada")
+
+
+def usuario_atual(request: Request, cred: HTTPBasicCredentials | None = Depends(seguranca)) -> str:
     cfg = get_config()
+    _verificar_origem(request)
     if not cfg.admin_password:
-        return "admin"  # modo desenvolvimento: defina MO_ADMIN_PASSWORD em produção
+        # sem senha só funciona na própria máquina (modo desenvolvimento/demonstração)
+        if request.client is not None and request.client.host in HOSTS_LOCAIS:
+            return "admin"
+        raise HTTPException(503, "Painel bloqueado: defina MO_ADMIN_PASSWORD no .env")
     if cred is None or not (
         secrets.compare_digest(cred.username.encode(), cfg.admin_user.encode())
         and secrets.compare_digest(cred.password.encode(), cfg.admin_password.encode())
@@ -83,8 +106,12 @@
         s.close()
 
 
+def _competencia_valida(valor: str | None) -> bool:
+    return bool(valor) and RE_COMPETENCIA.fullmatch(valor) is not None
+
+
 def _competencia(valor: str | None) -> str:
-    if valor and len(valor) == 7 and valor[4] == "-":
+    if _competencia_valida(valor):
         return valor
     return competencia_anterior()
 
@@ -105,10 +132,16 @@
     return templates.TemplateResponse(request, nome, ctx)
 
 
+def _destino_seguro(url: str, padrao: str = "/") -> str:
+    """Só aceita caminho interno ("/tarefas?..."). Bloqueia "//site", "/\\site", "https://site" (open redirect)."""
+    if not url or not url.startswith("/") or url.startswith("//") or url.startswith("/\\"):
+        return padrao
+    return url
+
+
 def _voltar(url: str, msg: str) -> RedirectResponse:
+    url = _destino_seguro(url)
     sep = "&" if "?" in url else "?"
-    from urllib.parse import quote
-
     return RedirectResponse(f"{url}{sep}msg={quote(msg)}", status_code=303)
 
 
@@ -121,7 +154,8 @@
             sess.commit()
         yield
 
-    app = FastAPI(title="Moraes e Oliveira - Monitor de Obrigações", docs_url="/api/docs", lifespan=ciclo_de_vida)
+    app = FastAPI(title="Moraes e Oliveira - Monitor de Obrigações", docs_url=None, redoc_url=None,
+                  openapi_url=None, lifespan=ciclo_de_vida)
     app.mount("/static", StaticFiles(directory=str(AQUI / "static")), name="static")
 
     @app.get("/saude")
@@ -183,8 +217,10 @@
     @app.post("/empresas/salvar")
     async def empresa_salvar(request: Request, db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
         f = await request.form()
-        emp_id = f.get("id")
-        emp = db.get(Empresa, int(emp_id)) if emp_id else Empresa()
+        emp_id = f.get("id", "")
+        if emp_id and not emp_id.isdigit():
+            raise HTTPException(400, "id inválido")
+        emp = (db.get(Empresa, int(emp_id)) or _404()) if emp_id else Empresa()
         cnpj = so_digitos(f.get("cnpj", ""))
         if not (cnpj_valido(cnpj) or cpf_valido(cnpj)):
             return _voltar(f"/empresas/{emp_id}/editar" if emp_id else "/empresas/nova", "CNPJ/CPF inválido")
@@ -202,16 +238,24 @@
         emp.municipio = f.get("municipio", "").strip()
         emp.email_cliente = f.get("email_cliente", "").strip()
         emp.whatsapp_cliente = f.get("whatsapp_cliente", "").strip()
-        emp.drive_folder_id = extrair_id_pasta(f.get("drive_folder_id", ""))
+        pasta = extrair_id_pasta(f.get("drive_folder_id", ""))
+        if pasta and get_config().drive_backend == "google" and not RE_ID_DRIVE.fullmatch(pasta):
+            return _voltar(f"/empresas/{emp_id}/editar" if emp_id else "/empresas/nova",
+                           "Pasta do Drive inválida: cole a URL da pasta ou o ID")
+        if f.get("regime", "SIMPLES") not in REGIMES:
+            return _voltar(f"/empresas/{emp_id}/editar" if emp_id else "/empresas/nova", "Regime inválido")
+        emp.drive_folder_id = pasta
         emp.ativa = f.get("ativa") == "on"
         for flag, _ in FLAGS_EMPRESA:
             setattr(emp, flag, f.get(flag) == "on")
         for campo in ("resp_fiscal_id", "resp_contabil_id", "resp_pessoal_id"):
             v = f.get(campo)
-            setattr(emp, campo, int(v) if v else None)
+            setattr(emp, campo, int(v) if v and v.isdigit() else None)
+        anteriores = emp.personalizacoes or {}
         pers = {}
         for o in db.scalars(select(Obrigacao)):
-            regra = {}
+            # preserva chaves que o formulário não mostra ("ajuste", "regra")
+            regra = {k: v for k, v in anteriores.get(o.codigo, {}).items() if k not in ("ignorar", "incluir", "dia")}
             modo = f.get(f"pers_{o.codigo}", "")
             if modo == "ignorar":
                 regra["ignorar"] = True
@@ -235,7 +279,7 @@
     def empresa_detalhe(empresa_id: int, request: Request, db: Session = Depends(get_db),
                         usuario: str = Depends(usuario_atual)):
         emp = db.get(Empresa, empresa_id) or _404()
-        tarefas = list(db.scalars(select(Tarefa).options(joinedload(Tarefa.obrigacao))
+        tarefas = list(db.scalars(select(Tarefa).options(joinedload(Tarefa.obrigacao), selectinload(Tarefa.documentos))
                                   .where(Tarefa.empresa_id == emp.id)
                                   .order_by(Tarefa.competencia.desc(), Tarefa.vencimento)).unique())
         comps = sorted({t.competencia for t in tarefas}, reverse=True)[:12]
@@ -310,9 +354,14 @@
                     voltar: str = Form("/tarefas"), db: Session = Depends(get_db),
                     usuario: str = Depends(usuario_atual)):
         t = db.get(Tarefa, tarefa_id) or _404()
+        voltar = _destino_seguro(voltar, "/tarefas")
         if acao == "baixa":
-            dar_baixa(db, t, datetime.now(), "manual", usuario, observacao)
-            msg = "Baixa manual registrada"
+            ok = dar_baixa(db, t, datetime.now(), "manual", usuario, observacao)
+            msg = "Baixa manual registrada" if ok else "A tarefa já estava concluída"
+        elif acao == "dispensar" and t.status != STATUS_PENDENTE:
+            msg = "Só é possível dispensar tarefa pendente"
+        elif acao == "reabrir" and t.status == STATUS_PENDENTE:
+            msg = "A tarefa já está pendente"
         elif acao == "dispensar":
             if not observacao.strip():
                 return _voltar(voltar, "Informe a justificativa para dispensar (ex.: sem movimento)")
@@ -326,8 +375,6 @@
             msg = "Tarefa reaberta"
         else:
             raise HTTPException(400, "ação inválida")
-        if not voltar.startswith("/"):
-            voltar = "/tarefas"
         return _voltar(voltar, msg)
 
     # ------------------------------------------------------------- Documentos
@@ -348,8 +395,9 @@
     def documento_classificar(doc_id: int, codigo: str = Form(...), competencia: str = Form(...),
                               db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
         doc = db.get(Documento, doc_id) or _404()
+        if not _competencia_valida(competencia):
+            return _voltar("/documentos", "Competência inválida: use AAAA-MM (ex.: 2026-09)")
         try:
-            parse_competencia(competencia)
             classificar_manual(db, doc, codigo, competencia, usuario)
         except (ValueError, IndexError) as exc:
             return _voltar("/documentos", f"Erro: {exc}")
@@ -405,6 +453,8 @@
     # ------------------------------------------------------------- Ações
     @app.post("/acoes/agenda")
     def acao_agenda(competencia: str = Form(...), db: Session = Depends(get_db), usuario: str = Depends(usuario_atual)):
+        if not _competencia_valida(competencia):
+            return _voltar("/", "Competência inválida: use AAAA-MM")
         r = agenda_mod.gerar_agenda(db, _competencia(competencia), usuario=usuario)
         return _voltar(f"/?competencia={r['competencia']}", f"Agenda {r['competencia']}: {r['tarefas_criadas']} tarefa(s) criada(s)")
 
--- a/mo_obrigacoes/web/templates/painel.html
+++ b/mo_obrigacoes/web/templates/painel.html
@@ -6,7 +6,7 @@
 <div class="acoes">
 <form class="inline" method="post" action="/acoes/agenda"><input type="hidden" name="competencia" value="{{ comp }}"><button>Gerar agenda de {{ formatar_competencia(comp) }}</button></form>
 <form class="inline" method="post" action="/acoes/sincronizar"><button class="sec">Verificar Google Drive agora</button></form>
-<form class="inline" method="post" action="/acoes/alertas"><button class="sec">Enviar alertas</button></form>
+<form class="inline" method="post" action="/acoes/alertas" onsubmit="return confirm('Enviar agora os e-mails de alerta para a equipe e as cobranças aos clientes?')"><button class="sec">Enviar alertas</button></form>
 <span class="muted" style="align-self:center">Última varredura do Drive: {{ ultima_sync.strftime('%d/%m/%Y %H:%M') ~ ' UTC' if ultima_sync else 'nunca' }}</span>
 </div>
 {% set g = r.geral %}
--- a/mo_obrigacoes/web/templates/empresa.html
+++ b/mo_obrigacoes/web/templates/empresa.html
@@ -5,7 +5,7 @@
 <p class="muted">{{ emp.cnpj_formatado }} · {{ REGIMES.get(emp.regime) }} · {{ emp.municipio }}{{ '/' ~ emp.uf if emp.uf }}
 {% if emp.drive_folder_id and not emp.drive_folder_id.startswith('local') and '/' not in emp.drive_folder_id %} · <a target="_blank" href="https://drive.google.com/drive/folders/{{ emp.drive_folder_id }}">Abrir pasta no Drive</a>{% endif %}</p>
 <div class="acoes"><a class="btn" href="/empresas/{{ emp.id }}/editar">Editar cadastro</a>
-<form class="inline" method="post" action="/empresas/{{ emp.id }}/sincronizar"><button class="sec">Reprocessar pasta do Drive</button></form>
+<form class="inline" method="post" action="/empresas/{{ emp.id }}/sincronizar" onsubmit="return confirm('Reprocessar todos os arquivos da pasta desta empresa? Pode levar alguns minutos.')"><button class="sec">Reprocessar pasta do Drive</button></form>
 <form class="inline" method="post" action="/empresas/{{ emp.id }}/criar-pastas"><input name="ano" size="5" value="{{ hoje.year }}"><button class="sec">Criar estrutura de pastas</button></form>
 <a class="btn sec" href="/tarefas?empresa_id={{ emp.id }}">Ver agenda completa</a></div>
 <div class="cards"><div class="card"><div class="n">{{ kpi.total }}</div><div class="l">Tarefas</div></div>
```

## Patch do Pacote D (alertas.py e cli.py)

```diff
--- a/mo_obrigacoes/alertas.py
+++ b/mo_obrigacoes/alertas.py
@@ -4,6 +4,7 @@
 import json
 import logging
 import smtplib
+import ssl
 import urllib.request
 from collections import defaultdict
 from dataclasses import dataclass, field
@@ -58,11 +59,17 @@
         em["Subject"] = msg.assunto
         em.set_content("Este e-mail requer um leitor compatível com HTML.")
         em.add_alternative(msg.html, subtype="html")
-        with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30) as s:
-            s.starttls()
-            if self.cfg.smtp_user:
-                s.login(self.cfg.smtp_user, self.cfg.smtp_password)
-            s.send_message(em)
+        try:
+            with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port, timeout=30) as s:
+                s.starttls(context=ssl.create_default_context())  # valida o certificado do servidor SMTP
+                if self.cfg.smtp_user:
+                    s.login(self.cfg.smtp_user, self.cfg.smtp_password)
+                s.send_message(em)
+        except (smtplib.SMTPException, OSError) as exc:
+            # um endereço ruim não pode derrubar a rotina inteira (e fazê-la reenviar tudo a cada ciclo)
+            log.warning("Falha ao enviar e-mail para %s: %s", destinatarios, exc)
+            self.enviadas.remove(msg)
+            return False
         return True
 
     def webhook(self, evento: str, dados: dict) -> bool:
--- a/mo_obrigacoes/cli.py
+++ b/mo_obrigacoes/cli.py
@@ -109,11 +109,14 @@
                 gerar_agenda(s, competencia_anterior(agora.date()))
                 gerar_agenda(s, competencia_str(agora.year, agora.month))
             cmd_sync(argparse.Namespace(completo=False))
-            if agora.hour >= args.hora_alertas and ultimo_alerta != agora.date():
-                cmd_alertas(None)
-                ultimo_alerta = agora.date()
         except Exception:  # noqa: BLE001
-            log.exception("Falha no ciclo do worker")
+            log.exception("Falha na agenda/sincronização do worker")
+        if agora.hour >= args.hora_alertas and ultimo_alerta != agora.date():
+            ultimo_alerta = agora.date()  # marca ANTES: uma falha não pode reenviar e-mails a cada ciclo
+            try:
+                cmd_alertas(None)
+            except Exception:  # noqa: BLE001
+                log.exception("Falha ao enviar alertas (não será repetido hoje)")
         if args.uma_vez:
             break
         time.sleep(cfg.sync_interval_minutes * 60)
```

## Pacote T: testes novos (arquivos completos)

### tests/test_correcoes_drive.py

```python
"""Pacote E: cliente do Google Drive (injeção na query, novas tentativas, fuso) e falha de leitura."""
import pytest

from mo_obrigacoes.drive.base import ArquivoDrive, DriveClient, ErroLeitura
from mo_obrigacoes.drive.google import GoogleDriveClient

CHAMADAS = []


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self, num_retries=0):
        CHAMADAS.append(num_retries)
        return self.r


class _Files:
    def list(self, q, **_):
        return _Req({"files": []})

    def create(self, **_):
        return _Req({"id": "nova"})


class _Servico:
    def files(self):
        return _Files()


def test_id_de_pasta_com_aspas_e_recusado():
    c = GoogleDriveClient("", servico=_Servico())
    with pytest.raises(ValueError):
        list(c.listar_arquivos("abc' in parents or 'root"))
    with pytest.raises(ValueError):
        c.garantir_pasta("2026", "x' or name contains 'a")


def test_chamadas_com_novas_tentativas():
    CHAMADAS.clear()
    c = GoogleDriveClient("", servico=_Servico())
    list(c.listar_arquivos("raiz_123"))
    c.garantir_pasta("2026", "raiz_123")
    assert CHAMADAS and all(n >= 3 for n in CHAMADAS)


def test_falha_de_download_vira_erro_leitura():
    class Quebrado(DriveClient):
        def listar_arquivos(self, pasta_id, modificado_apos=None):
            return iter(())

        def baixar(self, arquivo):
            raise RuntimeError("403 rateLimitExceeded")

        def garantir_pasta(self, nome, pai_id):
            return ""

    with pytest.raises(ErroLeitura):
        Quebrado().ler_texto(ArquivoDrive(id="1", nome="a.pdf", mime_type="application/pdf", caminho="a.pdf"))
```

### tests/test_correcoes_monitor.py

```python
"""Pacote B: varredura do Drive, reprocessamento e baixas."""
import os
import shutil
import time
from datetime import datetime

from sqlalchemy import func, select

from mo_obrigacoes.agenda import gerar_agenda
from mo_obrigacoes.demo import fmt, gerar_cnpj
from mo_obrigacoes.drive.base import ErroLeitura
from mo_obrigacoes.drive.local import LocalDriveClient
from mo_obrigacoes.models import Documento, Empresa, EstadoSync, Obrigacao, Tarefa
from mo_obrigacoes.monitor import Monitor, classificar_manual
from mo_obrigacoes.pdfsimples import gerar_pdf

FISCAL = "2026/09 - Setembro/01 - Fiscal/"


def _emp(s, codigo, base):
    e = Empresa(codigo=codigo, razao_social=f"{codigo} LTDA", cnpj=gerar_cnpj(base), regime="SIMPLES",
                drive_folder_id=codigo)
    s.add(e)
    s.flush()
    return e


def _pdf(raiz, emp, rel, linhas, mtime=None):
    p = raiz / emp.drive_folder_id / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gerar_pdf(linhas))
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


def _das(emp, comp="09/2026"):
    return ["Documento de Arrecadacao do Simples Nacional", f"CNPJ {fmt(emp.cnpj)}", f"Periodo de Apuracao: {comp}"]


def _tarefa(s, emp, codigo, comp="2026-09"):
    ob = s.scalar(select(Obrigacao).where(Obrigacao.codigo == codigo))
    return s.scalar(select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
                                         Tarefa.competencia == comp))


def _cenario(s, tmp_path):
    a = _emp(s, "A", "55666777")
    gerar_agenda(s, "2026-09")
    raiz = tmp_path / "drive"
    return a, raiz, LocalDriveClient(raiz)


def test_arquivo_com_data_antiga_depositado_depois_e_lido(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    _pdf(raiz, a, "2026/09 - Setembro/04 - Documentos do Cliente/extrato.pdf",
         ["Extrato de conta corrente", "Saldo anterior 1,00", "Periodo: 09/2026"], mtime=time.time() - 20 * 86400)
    assert Monitor(s, drive).sincronizar().arquivos_lidos == 1
    assert _tarefa(s, a, "DOC_EXTRATOS").status != "pendente"


def test_arquivo_apagado_reabre_baixa_automatica(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    p = _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status != "pendente"
    p.unlink()
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert s.scalar(select(Documento).where(Documento.nome == "das.pdf")).situacao == "removido"


def test_conteudo_trocado_reabre_tarefa_anterior(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    p = _pdf(raiz, a, FISCAL + "guia.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    time.sleep(1.1)
    p.write_bytes(gerar_pdf(_das(a, "08/2026")))  # a pessoa trocou pelo DAS de agosto
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert _tarefa(s, a, "DAS", "2026-08").status != "pendente"


def test_divergente_movido_sai_da_fila(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    b = _emp(s, "B", "55666888")
    gerar_agenda(s, "2026-09")
    _pdf(raiz, a, FISCAL + "guia de B.pdf", _das(b))
    assert Monitor(s, drive).sincronizar().divergentes == 1
    destino = raiz / "B" / FISCAL / "guia de B.pdf"
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(raiz / "A" / FISCAL / "guia de B.pdf", destino)
    Monitor(s, drive).sincronizar()
    assert _tarefa(s, b, "DAS").status != "pendente"
    assert s.scalar(select(func.count(Documento.id)).where(Documento.situacao == "divergente")) == 0


def test_documento_antigo_nao_cria_agenda_inteira(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, "2024/03 - Marco/01 - Fiscal/das.pdf", _das(a, "03/2024"))
    Monitor(s, drive).sincronizar()
    comps = s.scalars(select(Tarefa).where(Tarefa.competencia == "2024-03")).all()
    assert [t.obrigacao.codigo for t in comps] == ["DAS"]


def test_competencia_so_pela_data_do_arquivo_vai_para_revisao(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, "guia.pdf", ["Documento de Arrecadacao do Simples Nacional", f"CNPJ {fmt(a.cnpj)}"])
    Monitor(s, drive).sincronizar()
    assert s.scalar(select(Documento)).situacao == "nao_identificado"
    assert all(t.status == "pendente" for t in a.tarefas)


def test_falha_temporaria_de_download_e_tentada_de_novo(s, tmp_path):
    a, raiz, _ = _cenario(s, tmp_path)

    class Instavel(LocalDriveClient):
        falhar = True

        def baixar(self, arq):
            if self.falhar:
                raise RuntimeError("503 backendError")
            return super().baixar(arq)

    drive = Instavel(raiz)
    _pdf(raiz, a, FISCAL + "DAS 09-2026.pdf", ["Programa Gerador do Documento de Arrecadacao do Simples Nacional",
                                               "Recibo de Entrega da Apuracao", f"CNPJ {fmt(a.cnpj)}", "PA 09/2026"])
    r = Monitor(s, drive).sincronizar()
    assert r.erros and _tarefa(s, a, "DAS").status == "pendente"
    drive.falhar = False
    Monitor(s, drive).sincronizar()
    assert s.scalar(select(Documento)).obrigacao_codigo == "PGDAS_D"
    assert _tarefa(s, a, "DAS").status == "pendente" and _tarefa(s, a, "PGDAS_D").status != "pendente"


def test_arquivos_vistos_por_empresa(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    b = _emp(s, "B", "55666888")
    _pdf(raiz, a, FISCAL + "das.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    vistos = {e.empresa_id: e.arquivos_vistos for e in s.scalars(select(EstadoSync))}
    assert vistos == {a.id: 1, b.id: 0}


def test_classificacao_manual_valida_e_reabre_anterior(s, tmp_path):
    a, raiz, drive = _cenario(s, tmp_path)
    _pdf(raiz, a, FISCAL + "guia.pdf", _das(a))
    Monitor(s, drive).sincronizar()
    doc = s.scalar(select(Documento))
    try:
        classificar_manual(s, doc, "DAS", "2026-9", "ana")
        assert False, "deveria recusar competência inválida"
    except ValueError:
        pass
    classificar_manual(s, doc, "DAS", "2026-08", "ana")
    assert _tarefa(s, a, "DAS").status == "pendente"
    assert _tarefa(s, a, "DAS", "2026-08").status != "pendente"


def test_baixa_usa_horario_de_brasilia():
    from mo_obrigacoes.drive.google import _dt

    # 21:30 de 20/10 em Brasília = 00:30Z de 21/10
    assert _dt("2026-10-21T00:30:00.000Z") == datetime(2026, 10, 20, 21, 30)
```

### tests/test_correcoes_classificador.py

```python
"""Pacote C: extração de competência e falsos positivos."""
from datetime import datetime

import pytest

from mo_obrigacoes.catalogo import CATALOGO
from mo_obrigacoes.classificador import Regra, classificar, competencia_por_caminho, extrair_competencia

REGRAS = [Regra(c["codigo"], c.get("periodicidade", "mensal"), c["departamento"], c["reconhecimento"]) for c in CATALOGO]


@pytest.mark.parametrize("texto, esperado", [
    ("Recibo\nData da transmissão: 15/10/2026\nPeríodo de apuração: 2026-09", "2026-09"),
    ("Recibo de Entrega da DCTFWeb\nData de transmissão 14/10/2026 10:31", None),
    ("Extrato\nPeríodo: 01/09/2026 a 30/09/2026", "2026-09"),
    ("Referência: 01/09/2026", "2026-09"),
    ("<det><prod><qCom>12.2000</qCom></prod></det><ide><dhEmi>2026-09-15T10:00:00-03:00</dhEmi></ide>", "2026-09"),
    ("Endereço: Rua do Mar 2026, Centro", None),
    ("DAS set/2026.pdf", "2026-09"),
    ("Holerite SET-2026", "2026-09"),
    ("Competência: setembro de 2026", "2026-09"),
])
def test_competencia_mensal(texto, esperado):
    assert extrair_competencia(texto) == esperado


def test_exercicio_nao_vence_ano_calendario():
    assert extrair_competencia("Exercício 2026 Ano-calendário 2025", "anual") == "2025-12"
    assert extrair_competencia("Demonstrações do exercício 2025", "anual") == "2025-12"


def test_pasta_com_mes_abreviado():
    assert competencia_por_caminho("2026/Set/01 - Fiscal/x.pdf") == "2026-09"


def test_nome_sem_competencia_nao_identifica_sozinho():
    r = classificar(REGRAS, "Comprovante das despesas.pdf", "", "", datetime(2026, 10, 5))
    assert not r.identificado
    r = classificar(REGRAS, "DAS.pdf", "", "2026/09 - Setembro/01 - Fiscal/DAS.pdf", datetime(2026, 10, 5))
    assert (r.codigo, r.competencia) == ("DAS", "2026-09")  # digitalizado na pasta do mês continua identificado
    r = classificar(REGRAS, "FGTS setembro 2026.pdf", "", "", datetime(2026, 10, 5))
    assert r.codigo == "FGTS_DIGITAL"
```

### tests/test_correcoes_web.py

```python
"""Pacote A: segurança e validações do painel."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from mo_obrigacoes.demo import criar_demo
from mo_obrigacoes.models import Empresa, Tarefa

AUTH = ("admin", "segredo")


@pytest.fixture()
def cliente(s, cfg, tmp_path):
    from mo_obrigacoes.web.app import criar_app

    criar_demo(s, tmp_path / "drive", "2026-09")
    s.commit()
    with TestClient(criar_app(), raise_server_exceptions=False, follow_redirects=False) as c:
        yield c


def _pendente(c):
    return next(t for t in c.get("/api/tarefas?competencia=2026-09", auth=AUTH).json() if t["status"] == "pendente")


def test_sem_senha_bloqueia_acesso_de_fora(cfg):
    from mo_obrigacoes.web.app import criar_app

    cfg.admin_password = ""
    with TestClient(criar_app(), client=("10.0.0.5", 5000)) as c:
        assert c.get("/api/tarefas").status_code == 503
    with TestClient(criar_app()) as c:  # mesma máquina: modo demonstração continua funcionando
        assert c.get("/api/tarefas").status_code == 200


def test_csrf_post_de_outra_origem_bloqueado(cliente):
    t = _pendente(cliente)
    r = cliente.post(f"/tarefas/{t['id']}/acao", data={"acao": "baixa"}, auth=AUTH,
                     headers={"Origin": "https://malicioso.example"})
    assert r.status_code == 403
    r = cliente.post(f"/tarefas/{t['id']}/acao", data={"acao": "baixa"}, auth=AUTH,
                     headers={"Origin": "http://testserver"})
    assert r.status_code == 303


@pytest.mark.parametrize("destino", ["//malicioso.example/x", "https://malicioso.example", "/\\malicioso.example"])
def test_sem_open_redirect(cliente, destino):
    t = _pendente(cliente)
    for dados in ({"acao": "reabrir"}, {"acao": "dispensar"}, {"acao": "baixa"}):
        r = cliente.post(f"/tarefas/{t['id']}/acao", data={**dados, "voltar": destino}, auth=AUTH)
        assert r.headers["location"].startswith("/tarefas?"), r.headers["location"]


def test_competencia_invalida_nao_quebra_nem_cria_tarefas(cliente, s):
    assert cliente.get("/?competencia=abcd-ef", auth=AUTH).status_code == 200
    assert cliente.get("/relatorios?competencia=2026-13", auth=AUTH).status_code == 200
    r = cliente.post("/acoes/agenda", data={"competencia": "2026-13"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]
    assert s.scalar(select(func.count(Tarefa.id)).where(Tarefa.competencia == "2026-13")) == 0
    r = cliente.post("/documentos/1/classificar", data={"codigo": "DAS", "competencia": "2026-9"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]


def test_acoes_respeitam_status_da_tarefa(cliente):
    feita = next(t for t in cliente.get("/api/tarefas", auth=AUTH).json() if t["status"].startswith("entregue"))
    r = cliente.post(f"/tarefas/{feita['id']}/acao", data={"acao": "dispensar", "observacao": "x"}, auth=AUTH)
    assert "pendente" in r.headers["location"]
    r = cliente.post(f"/tarefas/{feita['id']}/acao", data={"acao": "baixa"}, auth=AUTH)
    assert "conclu%C3%ADda" in r.headers["location"]
    status = {t["id"]: t["status"] for t in cliente.get("/api/tarefas", auth=AUTH).json()}
    assert status[feita["id"]] == feita["status"]


def test_salvar_empresa(cliente, s, cfg):
    assert cliente.post("/empresas/salvar", data={"id": "999", "codigo": "x", "razao_social": "y",
                                                  "cnpj": "04.252.011/0001-10"}, auth=AUTH).status_code == 404
    emp = s.scalar(select(Empresa).where(Empresa.codigo == "0001"))
    emp.personalizacoes = {"ICMS": {"dia": 9, "ajuste": "posterga"}}
    s.commit()
    form = {"id": str(emp.id), "codigo": "0001", "razao_social": emp.razao_social, "cnpj": emp.cnpj,
            "regime": "SIMPLES", "dia_ICMS": "10", "ativa": "on"}
    cliente.post("/empresas/salvar", data=form, auth=AUTH)
    s.expire_all()
    assert s.get(Empresa, emp.id).personalizacoes["ICMS"] == {"dia": 10, "ajuste": "posterga"}
    cfg.drive_backend = "google"
    r = cliente.post("/empresas/salvar", data={**form, "drive_folder_id": "abc' in parents or 'x"}, auth=AUTH)
    assert "inv%C3%A1lida" in r.headers["location"]


def test_documentacao_da_api_nao_exposta(cliente):
    assert cliente.get("/api/docs").status_code == 404
    assert cliente.get("/redoc").status_code == 404
    assert cliente.get("/openapi.json").status_code == 404
```

### tests/test_correcoes_alertas.py

```python
"""Pacote D: falha de e-mail não interrompe nem repete a rotina de alertas."""
import smtplib
from datetime import date

from sqlalchemy import select

from mo_obrigacoes.alertas import Notificador, executar_alertas
from mo_obrigacoes.demo import criar_demo
from mo_obrigacoes.models import Empresa, Tarefa


class _SMTPFalso:
    enviados: list[str] = []
    contexto = None

    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        _SMTPFalso.contexto = context

    def login(self, *a):
        pass

    def send_message(self, em):
        if "invalido" in em["To"]:
            raise smtplib.SMTPRecipientsRefused({em["To"]: (550, b"no such user")})
        _SMTPFalso.enviados.append(em["To"])


def test_email_invalido_nao_derruba_alertas(s, cfg, tmp_path, monkeypatch):
    criar_demo(s, tmp_path / "drive", "2026-09")
    s.scalar(select(Empresa).where(Empresa.codigo == "0002")).email_cliente = "invalido@x"
    monkeypatch.setattr(smtplib, "SMTP", _SMTPFalso)
    _SMTPFalso.enviados = []
    cfg.smtp_host = "smtp.exemplo"
    r = executar_alertas(s, Notificador(cfg), hoje=date(2026, 10, 13))
    assert r["cobrancas_cliente"] >= 1
    assert "financeiro@0001.exemplo.com.br" in _SMTPFalso.enviados
    assert _SMTPFalso.contexto is not None and _SMTPFalso.contexto.verify_mode != 0  # certificado validado
    # cobrança bem-sucedida ficou registrada: não repete no mesmo dia
    emp1 = s.scalar(select(Empresa).where(Empresa.codigo == "0001"))
    assert any(t.ultimo_alerta_em for t in s.scalars(select(Tarefa).where(Tarefa.empresa_id == emp1.id)))
```

---

# Verificação final (13/10/2026)

**Escopo:** `git diff e5b3736..HEAD`, com os commits `deadc11` (C), `3c02e9e` e `b14c8cb` (E), `2373687` (A), `027e76b` (D), `b2796b5` (G, vigência) e `686ff78` (B), sobre a revisão contábil `4813cee`. Revisei o diff linha a linha contra os patches do apêndice. Rodei de novo contra o HEAD os scripts de reprodução (`r_mon`, `r_class`, `r_google`, `r_falha`, `r_web`), a suíte e a demonstração.

- **Suíte:** 71 passed.
- **Demonstração:** 12 arquivos, 10 baixas, 1 não identificado, 1 divergente, nenhum erro.
- **Desvios aceitos:**
  - `files().create()` ficou **sem** retry, porque não é idempotente e um retry poderia duplicar a pasta. Está correto.
  - No Pacote A, a validação de regime e de `drive_folder_id` foi movida para antes das atribuições, porque `get_db` faz commit mesmo quando a rota retorna cedo. Melhorou o patch original.
- **Extras do Pacote D (corretos):**
  - o worker gera a agenda das competências anterior, atual e próxima;
  - o CSV está protegido contra injeção de fórmula;
  - o webhook só aceita `https://`;
  - os indicadores usam `MO_DIAS_ALERTA_VENCIMENTO`.

## Status por achado

| Achado | Status | Evidência no HEAD |
|---|---|---|
| C1 Varredura incremental perde arquivos | **Corrigido** | Arquivo com data antiga: 1 lido, `DOC_EXTRATOS` entregue. Arquivo movido A→B: baixa em B e fila de divergentes zerada |
| C2 Baixa permanece sem comprovante | **Corrigido** | Arquivo apagado: DAS volta a `pendente`. Conteúdo trocado: PGDAS volta a `pendente` |
| C3 Painel sem senha aberto | **Corrigido** | Acesso de fora da máquina (`10.0.0.5`) recebe 503; na própria máquina continua funcionando |
| C4 Loop de reenvio de e-mails | **Corrigido** | SMTP falso recusando um destinatário: as cobranças seguintes são enviadas e `ultimo_alerta_em` fica gravado. O worker marca o dia antes de enviar |
| A1 CSRF | **Corrigido** | POST com Origin externo: 403 |
| A2 Open redirect | **Corrigido** | `//`, `https://` e `/\` voltam para `/tarefas` |
| A3 Falha de download | **Corrigido** | Falha 503: nenhum documento gravado. Sincronização seguinte classifica como `PGDAS_D` |
| A4 Fuso horário | **Corrigido** | 21:30 em Brasília no dia do vencimento: `entregue` |
| A5 Agenda inteira de competência antiga | **Corrigido** | DAS de 03/2024 cria só 1 tarefa |
| A6 Baixa por competência palpitada | **Corrigido** | Vai para revisão, testado em `test_competencia_so_pela_data_do_arquivo_vai_para_revisao` |
| A7 Regex de competência | **Corrigido** | Os 6 casos do relatório agora dão o resultado esperado |
| A8 Retry na API Google | **Corrigido** | `num_retries=5` em `list` e `next_chunk`; `create` sem retry de propósito |
| M1 Injeção na query do Drive | **Corrigido** | `validar_id` levanta `ValueError` |
| M2 Competência inválida | **Corrigido** | 200, mensagem de erro, 0 tarefas "2026-13" ou "2026-9" |
| M3 "das" preposição | **Corrigido** | Pelo classificador (pontuação só pelo nome) e pelo novo padrão de nome do DAS (`b2796b5`) |
| M4 STARTTLS sem verificação | **Corrigido** | `ssl.create_default_context()` |
| M5 Transação única | **Corrigido** | Commit e rollback por empresa |
| M6 Ações ignoram status | **Corrigido** | Reproduzido: "dispensar" em tarefa entregue não altera nada |
| M7 Personalizações apagadas, id inexistente 500 | **Corrigido** | `ajuste` preservado; id inexistente dá 404 |
| M8 `/api/docs` público | **Corrigido** | 404 |
| M9 Usuário único na auditoria | Pendente (evolução) | Fora do plano mecânico |
| M10 pypdf | **Parcial** | Versão fixada em `>=6.1,<7`; sem limite de tempo na extração (opcional) |
| M11 Varredura recursiva | Pendente (evolução) | Changes API |
| M12 Sync dentro da requisição | Pendente (opcional) | Mitigado pelo commit por empresa |
| B1 `arquivos_vistos` | **Corrigido** | `{A:1, B:0}` |
| B2 N+1 | **Corrigido** | 62 → 5 queries |
| B5 Confirmações | **Corrigido** | — |
| B6 CSV com fórmula | **Corrigido** | — |
| B12 Symlink | **Corrigido** | — |
| B14 Webhook http | **Corrigido** | — |
| B15 `dias_alerta` | **Corrigido** | — |
| B3, B4, B7, B8, B9, B10, B11, B13 | Pendentes (opcionais) | Sem impacto em correção ou segurança |

## Regressão encontrada na integração

### R1. Banco antigo quebra o worker e a linha de comando: "no such column: obrigacoes.vigente_desde" (ALTO)
- **Onde:**
  - `mo_obrigacoes/catalogo.py:591-597`: a migração `_migrar_vigencia` só roda dentro de `sincronizar_catalogo`;
  - `mo_obrigacoes/cli.py:50, 77, 87, 94, 102`: `cmd_importar`, `cmd_agenda`, `cmd_sync`, `cmd_alertas` e `cmd_worker` chamam só `criar_tabelas()`, que não adiciona colunas;
  - `models.py:165-166`: as colunas novas são lidas em toda consulta de `Obrigacao`.
- **Cenário:** produção já tem `dados/mo_obrigacoes.db` criado pela versão anterior. Depois da atualização, `docker compose up` sobe `web` e `worker` juntos.
  - Se o worker roda antes do painel, ou se o escritório usa só o cron (`sync`/`alertas`) como sugere `implantacao.md` §5, a varredura e os alertas falham sempre com `OperationalError`.
  - Pior: como o worker agora marca o dia antes de enviar (correção de C4), uma falha às 7h **cancela os alertas daquele dia**.
  - Mesmo depois da migração, o worker nunca recarrega o catálogo. A vigência do PIS/COFINS e as regras novas só chegam ao banco quando o painel reinicia.
- **Evidência (reproduzida):** criei o banco com `e5b3736` (`demo`) e rodei os comandos do HEAD. `agenda`, `sync` e `alertas` deram `sqlite3.OperationalError: no such column: obrigacoes.vigente_desde`, e o `worker --uma-vez` registrou "Falha na agenda/sincronização". Só depois de `init` voltou a funcionar.
- **Correção (mecânica, só `mo_obrigacoes/cli.py`):**
  1. Logo depois de `cmd_init`, acrescente:
     ```python
     def _preparar_banco() -> None:
         """Cria tabelas, aplica migrações e carrega o catálogo atual (vigência, regras novas)."""
         criar_tabelas()
         with sessao() as s:
             sincronizar_catalogo(s)
     ```
  2. Em `cmd_importar`, `cmd_agenda`, `cmd_sync`, `cmd_alertas` e `cmd_worker`, troque a linha `criar_tabelas()` por `_preparar_banco()`. `cmd_init` e `cmd_demo` ficam como estão.
  3. Crie o teste `tests/test_migracao_cli.py`, que falha no HEAD e passa com a correção. Prototipado: a suíte vai a **72 passed**.
     ```python
     """Banco criado por versão anterior (sem colunas de vigência) continua funcionando pela linha de comando."""
     from sqlalchemy import text

     from mo_obrigacoes import db as dbmod
     from mo_obrigacoes.cli import main
     from mo_obrigacoes.models import Obrigacao


     def test_cli_migra_banco_antigo(s, cfg):
         s.close()
         with dbmod.get_engine().begin() as con:
             con.execute(text("ALTER TABLE obrigacoes DROP COLUMN vigente_desde"))
             con.execute(text("ALTER TABLE obrigacoes DROP COLUMN vigente_ate"))
         main(["agenda", "--competencia", "2027-01"])  # antes da correção: OperationalError no such column
         s2 = dbmod.nova_sessao()
         pis = s2.query(Obrigacao).filter_by(codigo="PIS_COFINS").one()
         assert pis.vigente_ate == "2026-12"
         s2.close()
     ```

## Outras integrações verificadas, sem defeito

- **Monitor e vigência:** `tarefa_da_competencia` respeita `ocorre_na_competencia`. Um comprovante de PIS/COFINS de 2027-01 vira "sem_tarefa" (fora do perfil) e não cria tarefa. A classificação manual cria a tarefa mesmo assim, de propósito.
- **Competência futura gerada pelo worker e alertas:** essas tarefas vencem nos meses seguintes. O resumo só pega vencimento até hoje + `MO_DIAS_ALERTA_VENCIMENTO`, e a cobrança só pega o que já venceu, então não há alerta nem cobrança antecipados.
- **Fuso:** Drive (Brasília), baixa manual (`datetime.now()` com `TZ=America/Sao_Paulo` no Dockerfile) e Drive local (`fromtimestamp`) agora usam o mesmo referencial.
  - Na primeira varredura depois da atualização, os documentos do Google gravados em UTC são reprocessados uma vez. É inofensivo: `dar_baixa` não altera tarefas já concluídas.
  - Tarefas marcadas "com atraso" pelo bug antigo não são recalculadas. Se necessário, revisar manualmente as entregues entre 21h e 0h do dia do vencimento.
- **Migração em banco novo:** `create_all` já cria as colunas e `_migrar_vigencia` não faz nada.

## Veredito

**Não aprovado para produção enquanto R1 não for corrigido.** É uma alteração pequena e mecânica, só em `cli.py`, mais um teste. Todos os achados Crítico e Alto do parecer estão corrigidos e confirmados por reprodução no HEAD.

Corrigido R1, o sistema está **aprovado para produção**, com estas condições de implantação:
1. `MO_ADMIN_PASSWORD` definida e painel publicado só atrás de HTTPS;
2. proxy reverso repassando o `Host` (no nginx, `proxy_set_header Host $host`), senão a proteção CSRF bloqueia os formulários;
3. depois de atualizar, rodar `python -m mo_obrigacoes init` e uma vez `sync --completo`, e revisar os eventos `reabertura_automatica` e `documento_removido`.

Itens de evolução (M9 usuários individuais, M11 Changes API, M12 sync assíncrona) e os Baixos opcionais podem ficar para o próximo ciclo.
