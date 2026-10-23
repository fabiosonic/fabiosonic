# Pesquisa 02: agendamento e gestão de redes sociais com IA

**Escopo:** benchmark de funcionalidades a partir de informação pública (sites oficiais, páginas de preço, centrais de ajuda, documentação, reviews de terceiros e artigos).
**Data da coleta:** 23/10/2026.
**Método:** leitura de páginas públicas e buscas na web. Não acessamos áreas logadas, não testamos nenhum produto e não lemos código-fonte.
**Ferramentas:** mLabs, Etus (hoje Gerenciador de Redes Sociais KingHost), Metricool, Buffer, SocialBee, FeedHive, Later e Postiz.

> **Como ler este documento.** "Verificado" significa que a informação está numa página oficial lida em 23/10/2026. "Terceiros" significa artigo de review, blog de concorrente ou agregador. Esses blogs costumam ter viés comercial. "?" significa que não encontramos a informação ou que ela é ambígua. Todos os preços estão sem impostos e podem mudar. Os fluxos de onboarding vêm das centrais de ajuda e de artigos, sem teste prático.

---

## 1. Resumo executivo

- **No Brasil, o padrão é cobrar por marca ou perfil, com usuários ilimitados.** É o modelo da mLabs (R$ 29,90 por marca/mês no anual via Pix) e da Etus/KingHost (a partir de R$ 15,90/mês). Fora do Brasil, o preço é por canal (Buffer), por "brand" (Metricool) ou por pacote de perfis (SocialBee, Later, FeedHive, Postiz).
- **A aprovação pelo cliente é o recurso decisivo para quem atende clientes.** A mLabs é a única que manda o post para aprovação **direto no WhatsApp**. O Metricool tem um portal de revisão sem login, com regra de quórum. O Postiz usa um link público de preview com comentários, mas não tem status de "aprovado" que bloqueie a publicação. A aprovação do Buffer é só interna (fica no plano Team).
- **WhatsApp:** só a mLabs (mLabs Chat, com inbox e automações via WhatsApp Business API, cobrado à parte) trata o WhatsApp como canal de atendimento. As estrangeiras ignoram o WhatsApp, ou no máximo mandam um lembrete para publicação manual (SocialBee, via "Universal Posting" no app).
- **IA:** todas geram legenda. Os diferenciais são outros. O FeedHive dá uma **nota de 0 a 100 de previsão de engajamento antes de publicar**. O SocialBee monta a **estratégia inteira a partir da URL do site**. A mLabs tem **análise de concorrentes e de mercado com IA**. Metricool, Buffer, FeedHive, Postiz e mLabs já expõem **servidores MCP** para agentes como Claude e ChatGPT.
- **Reclamação nº 1 do mercado:** post agendado que não sai (falha silenciosa) e contas que desconectam e pedem reautenticação. Aparece em Later, FeedHive, Metricool e Etus. Em seguida vêm cobrança e renovação automática (Metricool, mLabs no Reclame Aqui) e preço que escala mal com muitos clientes pequenos (Buffer, mLabs).
- **Postiz** é código aberto (AGPL-3.0), tem cerca de 37,6 mil estrelas no GitHub e uma API pública REST simples (`Authorization: <api-key>`, `POST /public/v1/posts`, `POST /public/v1/upload`). É uma boa opção como **motor de publicação** por trás de um produto próprio. A licença AGPL e os limites de taxa (30 a 100 req/h, conforme a página) pesam no desenho da solução.

---

## 2. Matriz de funcionalidades

Legenda: ✅ = disponível (pode depender do plano); ❌ = não disponível ou não encontrado em fonte oficial; ? = não verificado ou ambíguo; 💲 = add-on pago à parte.

| Funcionalidade | mLabs | Etus/KingHost | Metricool | Buffer | SocialBee | FeedHive | Later | Postiz |
|---|---|---|---|---|---|---|---|---|
| Calendário visual | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Fila / slots recorrentes | ? | ? | ✅ (listas automáticas) | ✅ (queue) | ✅ (categorias) | ✅ (posting plans) | ? | ✅ (sets / find-slot) |
| Reciclagem de conteúdo evergreen | ❌ | ❌ | ✅ (templates recorrentes) | ❌ | ✅ (forte) | ✅ | ❌ | ✅ (repeated posts) |
| Instagram (feed, Reels, Stories) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Facebook | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| LinkedIn | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| TikTok | ✅ | ? | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| YouTube | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Google Business Profile | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ? | ✅ |
| Threads / Bluesky | ? / ❌ | ❌ | ✅ / ✅ | ✅ / ✅ | ✅ / ✅ | ✅ / ? | ✅ / ❌ | ✅ / ✅ |
| X/Twitter | 💲 (10 posts/mês grátis) | ✅ | 💲 | ✅ | ✅ | ✅ | ❌ | ✅ |
| WhatsApp (canal de atendimento) | 💲 (mLabs Chat) | ❌ | ❌ | ❌ | ❌ (só lembrete pelo app) | ❌ | ❌ | ❌ |
| IA: legenda / texto | ✅ | ✅ (Hal-2) | ✅ (créditos) | ✅ | ✅ | ✅ (créditos) | ✅ (créditos) | ✅ |
| IA: ideias / estratégia | ? | ✅ (personas) | ✅ | ✅ | ✅ (Copilot a partir da URL) | ✅ | ✅ | ✅ (Smart Agent) |
| IA: imagem / vídeo | ❌ (usa Canva) | ✅ (imagens) | ? | ❌ | ✅ | ✅ (imagem) | ? | ✅ (imagem, vídeo, clipping) |
| Melhor horário | ✅ | ? | ✅ | ? | ? | ✅ (smart scheduling) | ✅ | ✅ (find-slot) |
| Score / previsão do post | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (0 a 100) | ❌ | ❌ |
| Aprovação interna | ✅ | ✅ | ✅ (Advanced) | ✅ (Team) | ✅ (Accelerate+) | ✅ | ✅ (Growth+) | ⚠️ informal |
| Aprovação do cliente sem login | ✅ (e-mail, link, WhatsApp) | ? | ✅ (portal, quórum) | ❌ | ✅ | ? | ✅ (Growth+) | ✅ (link público, só comentário) |
| Workflow de produção (briefing → aprovação) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ (workflows) | ❌ | ❌ |
| Inbox: comentários e DMs | 💲 (R$ 19,90/perfil) | ✅ (Plano Completo) | ✅ | ✅ (comentários) | ✅ | ✅ | ✅ (Growth+) | ❌ |
| Automação de DM / comentário | 💲 | ❌ | ✅ (Flows) | ❌ | ❌ | ? | ❌ | ❌ |
| Analytics / relatórios PDF | ✅ | ✅ | ✅ (PDF/PPT) | ✅ | ✅ | ✅ | ✅ | ✅ (básico) |
| Relatório agendado ou white label | ✅ (portal white label) | ✅ (mensal) | ✅ (Looker Studio) | ✅ (Team, com marca) | ✅ (Pro) | ? | ✅ (Scale) | ❌ |
| Análise de concorrentes | ✅ | ⚠️ limitada | ✅ (até 100) | ❌ | ❌ | ❌ | ✅ (Scale) | ❌ |
| Ads (gestão ou relatório pago) | ✅ | ✅ (impulsionar) | ✅ (Meta, Google, TikTok) | ❌ | ❌ | ❌ | ✅ (Meta Ads, Scale) | ❌ |
| Link na bio | ? | ❌ | ✅ (Smartlinks) | ✅ (Start Page) | ❌ | ❌ (só encurtador) | ✅ (Linkin.bio, forte) | ❌ |
| Multi-cliente (workspaces / marcas) | ✅ | ✅ | ✅ | ✅ (channel groups) | ✅ (workspaces) | ✅ (workspaces) | ✅ (social sets) | ✅ (customers) |
| Usuários ilimitados | ✅ | ✅ | ? | ✅ (Team) | ❌ | ❌ | ❌ | ✅ (Team+) |
| Integração com Canva | ✅ | ? | ✅ | ✅ | ✅ | ? | ✅ | ✅ |
| API pública | ❌ (não encontrada) | ❌ | ✅ (Advanced) | ✅ | ❌ | ✅ (REST) | ? | ✅ (REST, OAuth) |
| MCP / agentes de IA | ✅ (mcp.mlabs.io) | ❌ | ✅ | ✅ | ? | ✅ (MCP, CLI) | ? | ✅ (MCP, CLI) |
| Webhooks | ? | ❌ | ? | ? | ? | ✅ | ? | ✅ |
| App mobile nativo | ✅ | ✅ (instável) | ✅ | ✅ | ✅ | ❌ | ✅ | ? |
| Interface em PT-BR | ✅ | ✅ | ✅ | ? | ? | ? | ? | ✅ (i18n) |
| Plano grátis | ❌ (trial de 7 dias) | ❌ (trial de 14 dias) | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ (self-host) |
| Código aberto / self-host | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ (AGPL-3.0) |

---

## 3. Fichas por ferramenta

### 3.1 mLabs (mlabs.com.br), Brasil

**Público e proposta de valor.** Agências, empresas, franquias e creators. A empresa diz atender "150 mil agências, empresas e franquias" e cita casos com 80 clientes numa agência e 650 franqueados. A proposta é concentrar num único painel em português o agendamento, os relatórios, a análise de concorrentes e o fluxo de criação e aprovação.

**Funcionalidades**
- **Calendário e agendamento:** posts em vários formatos e em várias redes ao mesmo tempo. Reels com publicação automática. Configurações nativas por rede, grupos de hashtags salvos, encurtador de links e assinatura.
- **Canais:** Instagram, Facebook, LinkedIn, TikTok, YouTube, X/Twitter (10 posts grátis por mês, depois créditos), Pinterest e Google Meu Negócio. O blog também cita Telegram e WhatsApp.
- **IA:** legendas com variações por rede, cada uma aprovada ou reprovada pelo usuário. Também oferece insights de performance, card de análise comparativa, melhores dias e horários e "análise de mercado" (exclusiva). Há um MCP em mcp.mlabs.io, sem documentação pública detalhada.
- **Aprovação e colaboração:** o módulo **Workflow** cria demandas com perfil, canais, prazo, briefing e arquivos. Cada demanda tem até 2 aprovadores internos e até 2 externos, e passa pelas etapas briefing → texto → imagem → aprovação do cliente → agendamento. O botão "Enviar para Aprovação" manda o post **por e-mail, por link ou direto para o WhatsApp**. O cliente vê o post no formato final e pede ajustes. Depois de aprovado, o post é agendado sozinho. Todas as versões ficam no histórico.
- **Inbox e DMs:** o **mLabs Chat** junta DMs, comentários e menções de Instagram, Facebook, TikTok e **WhatsApp**. Tem banco de respostas e automações por gatilho (comentário, curtida, mensagem). O WhatsApp exige Meta Business e um número que não esteja ativo no app do WhatsApp. Custa R$ 19,90/mês por perfil.
- **Analytics e relatórios:** relatórios de crescimento, alcance, engajamento, conteúdo ou personalizados, orgânicos e de Ads. Download em PDF, link compartilhável, envio agendado e **Portal do Cliente white label**. O **mLabs Analytics** tem dashboards arrastáveis com GA, Google Ads, Meta Ads, Instagram e YouTube.
- **Concorrentes:** até 5 por canal, com comparação direta de seguidores e "Share of Engagement". Também compara frequência, formatos e hashtags.
- **Link na bio:** não encontramos menção.
- **Multi-cliente:** cada "marca" corresponde a um cliente, com 1 perfil por rede. Usuários ilimitados com permissões por app. Gerente de conta a partir de 10 marcas.
- **Integrações:** Canva nativo, Google Analytics e Ads, Meta Ads e MCP. **Não encontramos API pública documentada.**
- **App mobile:** iOS e Android.

**Fluxo do cadastro ao primeiro post** (segundo o blog oficial "Como usar a mLabs")
1. Criar a conta com Facebook ou e-mail. O trial de 7 dias não pede cartão.
2. Em Dashboard, clicar no card da rede, depois em "Adicionar", e autorizar.
3. (Opcional) Em "Gerenciar usuários", convidar a equipe e definir permissões.
4. (Opcional) Criar uma demanda no Workflow.
5. Em "Agendar post", criar a arte no Canva integrado.
6. Escolher perfil e canais, escrever o texto (com IA, se quiser), definir hashtags, data e hora.
7. Ajustar as configurações específicas de cada rede.
8. "Enviar para Aprovação" (WhatsApp, e-mail ou link) ou agendar direto.
9. Acompanhar no Calendário.

**Diferenciais:** aprovação via WhatsApp; Workflow com briefing; análise de concorrentes; portal white label; tudo em PT-BR; Pix com desconto; usuários ilimitados; WhatsApp no inbox.

**Planos e preços** (mlabs.com.br/planos e home, coletados em 23/10/2026)
- Um único plano completo, cobrado **por marca**. "A partir de R$ 29,90/mês por marca" no anual à vista via Pix.
- O anual tem 40% de desconto. Há desconto progressivo a partir de 5 e de 10 marcas, e até 15% a mais no Pix.
- O Inbox/Chat com WhatsApp é add-on de R$ 19,90/mês por perfil. Créditos do X são cobrados à parte.
- Trial de 7 dias sem cartão. Um resultado de busca falava em 30 dias, mas a página de planos diz 7.
- A calculadora não mostrou valores para várias marcas no texto extraído. Os valores exatos não foram verificados.

**Pontos fracos e reclamações**
- **Reclame Aqui** (01/01 a 30/06/2026, via resultado de busca): nota 7,8/10, 28 reclamações, 72,7% resolvidas e 8 dias de tempo médio de resposta. Temas: suporte técnico lento comparado ao comercial, cobrança após o trial e problemas de acesso.
- **Terceiros** (Manyfesto, out/2026; Nação Digital, jul/2026): preço por marca pesa para quem tem muitos clientes pequenos; excesso de módulos e curva de aprendizado; a ferramenta entra "depois que a peça está pronta"; integração limitada com Pinterest e Threads; exportação de relatórios pouco flexível.
- **Capterra:** 4,7 em 63 reviews. Elogios ao UX. Críticas pontuais à integração com o Instagram e à demora em mostrar resultados.
- **Histórico:** o Tecnoblog noticiou a suspensão pelo Facebook de cerca de 39 milhões de posts de clientes da mLabs, ligada ao agendamento de Stories com login. É um risco de plataforma que vale para todo o setor.

**Ideias para o produto contábil:** aprovação por WhatsApp com 1 clique; Workflow com briefing e etapas; portal do cliente com a marca do escritório; relatório mensal agendado; preço por cliente com desconto progressivo; pagamento via Pix.

---

### 3.2 Etus, hoje Gerenciador de Redes Sociais KingHost (Brasil)

**Situação.** A Locaweb comprou a Etus em 2020 por R$ 18,95 milhões. Na época, a plataforma tinha cerca de 100 mil marcas. Hoje o produto é vendido como **"Gerenciador de Redes Sociais KingHost"** (king.host/gerenciador-de-redes-sociais, login em social.kinghost.com.br). O domínio etus.com.br pertence a outra empresa, a ETUS Media Holding, que não tem relação com a ferramenta.

**Público e proposta de valor.** Agências, empresas e criadores que querem agendar e medir de forma simples e barata. Vem integrado à hospedagem da KingHost e da Locaweb.

**Funcionalidades**
- **Agendamento:** calendário e timeline, texto diferente por rede, imagens, vídeos, Stories, GIFs e álbuns. Marca d'água automática com logo. Pausar e reativar publicações.
- **Canais:** Instagram, Facebook, LinkedIn, YouTube, X/Twitter, Pinterest, Google Meu Negócio e Tumblr (fontes Locaweb e B2B Stack). A KingHost só diz "todas as redes". Terceiros apontam suporte limitado a TikTok e às redes mais novas.
- **IA:** o assistente **Hal-2** gera textos, imagens e **personas de público**.
- **Aprovação:** Workflow com etapas de criação, revisão, aprovação e publicação, histórico de alterações e permissões por usuário. Um blog de terceiros (Manyfesto) classifica a aprovação do cliente como "parcial/básica".
- **Inbox:** o "SAC" responde comentários e DMs com 1 clique (Plano Completo).
- **Analytics:** relatórios de engajamento, crescimento e alcance, relatório mensal automático e resultado de anúncios. Compartilha por link ou PDF. Um usuário reclamou do limite de cerca de 3 meses por relatório.
- **Ads:** impulsionamento de posts de Facebook e Instagram já no agendamento, com orçamento, período e público.
- **Multi-cliente:** cada "perfil" é um cliente (1 IG, 1 FB, 1 X etc.). Usuários ilimitados.
- **App:** iOS e Android segundo a B2B Stack. A KingHost só cita o app geral da empresa.
- **Link na bio, API, WhatsApp:** não encontrados.

**Fluxo do cadastro ao primeiro post:** na Locaweb, a contratação passa pelo Criador de Sites. O cliente escolhe o plano, a periodicidade (trimestral ou anual) e o número de perfis, faz login Locaweb, paga (boleto por padrão) e finaliza. Depois adiciona o perfil, conecta as redes e agenda. Na KingHost, a página tem trial de 14 dias. Não detalhamos o fluxo da KingHost.

**Diferenciais:** o menor preço de entrada no Brasil; usuários ilimitados; impulsionamento no momento do agendamento; vem junto com a hospedagem.

**Planos e preços**
- KingHost (página oficial, 23/10/2026): "a partir de **R$ 15,90/mês**", com trial de 14 dias. Os planos não aparecem detalhados.
- Locaweb (página do produto Etus via resultado de busca, sem data): Plano Agendamento e **Plano Completo a R$ 29,90 por perfil/mês**.
- Um blog antigo (cerca de 2021) dava R$ 18,90/mês. O GetApp mostra R$ 6,24, sem explicação, e não é confiável.
- **Não conseguimos confirmar uma tabela de preços atual.**

**Pontos fracos:** instabilidade e bugs, principalmente no app; post agendado não publicado; Instagram desconecta com frequência; e-mails caindo no spam (B2B Stack, 4,0/5 em 3 reviews). Menos recursos avançados que mLabs e Metricool, e roadmap incerto depois de duas trocas de marca (Nação Digital, 2026). O suporte é dividido entre Locaweb (cobrança) e KingHost (uso).

**Ideias para o produto contábil:** marca d'água automática com o logo do cliente; IA que gera personas a partir do segmento da PME; impulsionamento dentro do fluxo de agendamento; preço de entrada baixo para o escritório que está começando.

---

### 3.3 Metricool (metricool.com)

**Público e proposta de valor.** Social media managers, agências e PMEs. A empresa diz ter mais de 4 milhões de usuários. A proposta é juntar planejamento, analytics orgânico e pago, inbox e relatórios num painel com plano grátis.

**Funcionalidades**
- **Agendamento:** calendário drag-and-drop com preview por rede, melhor horário, sugestão de hashtags, listas automáticas de conteúdo, posts recorrentes via templates e biblioteca de mídia.
- **Canais:** Instagram, Facebook, TikTok, YouTube, Threads, X (add-on), LinkedIn (fora do plano Free), Pinterest, Bluesky, Twitch e Google Business Profile. **Sem WhatsApp.**
- **IA:** assistente de ideias e rascunhos, com créditos por marca/mês (Free 5, Starter 20, Advanced 35). Análise com IA nos relatórios. **MCP oficial** e conectores para Claude e ChatGPT.
- **Aprovação** (Advanced e Custom): o post vai para revisão em vez de ser agendado. O revisor pode ser colaborador ou e-mail externo. O **revisor externo acessa um portal sem login** que reúne todos os posts dele daquela marca. Uma rejeição bloqueia a publicação. Com vários revisores, vale um **quórum de aprovações**. Na rejeição, o autor recebe e-mail com a nota. O calendário marca aprovado em verde e rejeitado em vermelho. Há aprovação, rejeição e envio em lote.
- **Inbox:** mensagens, comentários e avaliações do Google, com filtros e permissões (total, só leitura ou nenhuma). TikTok, LinkedIn, GBP e YouTube não entram com DMs. **Flows** automatizam respostas de DM.
- **Analytics:** dashboards, concorrentes (5 no Free, até 100 nos pagos), relatórios automáticos em PDF/PPT com envio mensal, templates personalizados, conector Looker Studio e Hashtag Tracker.
- **Ads:** cria, analisa e ajusta campanhas de Google, Meta e TikTok Ads.
- **Link na bio:** Smartlinks, com várias páginas e cliques em tempo real.
- **Multi-cliente:** "brand" = cliente. Colaborador com acesso a uma única marca. Papéis personalizados.
- **Integrações:** API, Zapier e Make (no Advanced), Looker Studio, Canva e MCP.
- **App mobile:** iOS e Android.

**Fluxo do cadastro ao primeiro post** (padrão descrito na central de ajuda, não testado): cadastro grátis → criar a marca → conectar as redes → Planejamento → criar post → escolher a rede, o texto com IA e a mídia → escolher horário (sugere os melhores) → agendar, ou "Enviar para revisão" nos planos Advanced.

**Diferenciais:** plano grátis útil; analytics orgânico e pago no mesmo lugar; portal de aprovação sem login com quórum; Flows de DM; Looker Studio; MCP; preço por faixa de marcas, barato para agências.

**Planos e preços** (metricool.com/pricing, 23/10/2026, sem IVA)
| Plano | Mensal | Anual (por mês) | Marcas |
|---|---|---|---|
| Free | US$ 0 | US$ 0 | 1 (20 posts/mês) |
| Starter | a partir de US$ 25 (€ 20) | a partir de US$ 20 (€ 16) | 5 ou 10 (10 = US$ 45 mensal / US$ 36 anual) |
| Advanced | a partir de US$ 67 (€ 54) | a partir de US$ 53 (€ 43) | 15 / 25 / 50 (50 = US$ 210 mensal / US$ 159 anual) |
| Custom | sob consulta | sob consulta | ilimitado |

X/Twitter é add-on. A aprovação, a API e o Looker Studio só existem a partir do Advanced.

**Pontos fracos:** reclamações de **cobrança, renovação automática e reembolso** no Trustpilot; interface carregada; suporte lento em cobrança; contas desconectando; posts duplicados ou que não saem (terceiros, 2026). O plano grátis não inclui X nem LinkedIn. Comunidade em PT-BR menor (Nação Digital).

**Ideias para o produto contábil:** portal de aprovação sem login com quórum (sócio e gerente do cliente); preço por faixa de clientes; analytics orgânico e pago lado a lado; automação de DM ("digite IRPF para receber o checklist").

---

### 3.4 Buffer (buffer.com)

**Público e proposta de valor.** Criadores, pequenos negócios e times pequenos. O site mostra cerca de 301 mil usuários ativos por mês e 84 mil clientes. A proposta é a interface mais simples do mercado, com preço por canal e plano grátis.

**Funcionalidades**
- **Agendamento:** fila (queue) com horários fixos, calendário, ideias com tags, threads, primeiro comentário, capa de vídeo, grupos de canais, notas e extensão de navegador.
- **Canais:** Instagram, Facebook, TikTok, LinkedIn, X, YouTube, Threads, Pinterest, GBP, Bluesky, Mastodon e Substack (novo). Perfis pessoais de Instagram e grupos de Facebook só recebem lembrete.
- **IA:** AI Assistant para gerar, refinar, criar ideias e adaptar o post por rede. Sugestões de resposta com IA (5 por semana no Free). **MCP e API** para Claude e ChatGPT.
- **Aprovação:** só no Team. O papel "Needs Approval" cria rascunho e pede aprovação, e Owner ou Full Access aprovam (também pelo app). A aprovação vale até para posts criados via API. **Não há aprovação de cliente externo sem login.**
- **Inbox (Community):** comentários de várias contas, respostas salvas e respostas sugeridas por IA. Terceiros consideram fraco para DMs.
- **Analytics:** histórico de 30 dias no Free e ilimitado nos pagos. Relatórios, UTMs e relatórios com marca (Team).
- **Link na bio:** Start Page.
- **Integrações:** Canva, Google Drive, Dropbox, Unsplash, Zapier, OneDrive e API (1 a 5 chaves; 100 req/15 min; 250 a 500/dia; 3.000 a 15.000/mês).
- **App mobile:** iOS e Android.

**Fluxo do cadastro ao primeiro post:** cadastro grátis → conectar até 3 canais → definir horários da fila → escrever o post (com IA, se quiser) → "Add to Queue" ou escolher data e hora.

**Diferenciais:** curva de aprendizado quase zero; plano grátis; API pública com limites documentados; preço linear por canal; desconto de 50% para ONGs.

**Planos e preços** (buffer.com/pricing, 23/10/2026)
- **Free:** US$ 0, 3 canais, 10 posts por canal, 1 usuário.
- **Essentials:** US$ 5/canal/mês, 1 usuário, analytics avançado.
- **Team:** US$ 10/canal/mês, usuários ilimitados, aprovação, permissões e relatórios com marca.
- O desconto do anual aparece de forma inconsistente na página ("2 meses grátis", "20%" e US$ 60/ano = 12 × 5). Trial de 14 dias. Canais acima de 10 saem mais baratos.

**Pontos fracos:** custo sobe linearmente com o número de canais (um escritório com 30 clientes × 3 redes no Team pagaria cerca de US$ 900/mês sem desconto de volume); sem social listening nem concorrentes; analytics raso; sem aprovação externa; sem WhatsApp.

**Ideias para o produto contábil:** fila com horários pré-definidos por cliente; aprovação obrigatória também via API; respostas sugeridas por IA no inbox; UX minimalista para o assistente do escritório.

---

### 3.5 SocialBee (socialbee.com)

**Público e proposta de valor.** Solopreneurs, PMEs e agências. A proposta é planejamento por **categorias de conteúdo** com reciclagem evergreen e um copiloto de IA que monta a estratégia.

**Funcionalidades**
- **Agendamento:** categorias de conteúdo (10, 50 ou ilimitadas) com cronograma por categoria, reciclagem evergreen, RSS (10, 30 ou ilimitado), editor em massa e organizador de hashtags.
- **Canais:** publicação direta em Facebook, Instagram, Threads, LinkedIn, X, Pinterest, TikTok, YouTube, GBP e Bluesky. O "Universal Posting", pelo app mobile, manda lembrete para Facebook Groups, **WhatsApp**, Telegram, Mastodon e Quora, mas a publicação é manual.
- **IA:** o **AI Copilot** monta a estratégia a partir da **URL do site** ou de um questionário. Ele recomenda redes, organiza categorias, cria o cronograma e gera posts editáveis. Geração de conteúdo ilimitada.
- **Aprovação:** fluxo de aprovação a partir do Accelerate e notas internas no Pro. Clientes podem revisar e aprovar. Os workspaces separam os clientes.
- **Inbox:** comentários, menções e DMs (DMs só de FB e IG). YouTube só comentários.
- **Analytics:** 3 meses no Bootstrap e 2 anos nos demais. Relatórios PDF com marca no Pro.
- **Integrações:** Canva, Unsplash e GIPHY. **API pública não encontrada.**
- **App mobile:** sim (Universal Posting).
- **Serviço:** o ConciergeBee é uma agência interna que opera a conta.

**Fluxo do cadastro ao primeiro post:** trial → conectar as redes → o Copilot pergunta a URL ou aplica o questionário → gera categorias, cronograma e posts → revisar e editar → os posts entram na fila por categoria.

**Diferenciais:** reciclagem por categoria; estratégia completa gerada a partir da URL; serviço feito por terceiros (concierge).

**Planos e preços** (socialbee.com/pricing, 23/10/2026; a página exibia um cupom válido "até 10 de junho", o que sugere conteúdo desatualizado)
| Plano | Mensal | Anual (por mês) | Perfis | Workspaces | Usuários/workspace |
|---|---|---|---|---|---|
| Bootstrap | US$ 29 | US$ 24 | 5 | 1 | 1 |
| Accelerate | US$ 49 | US$ 40 | 10 | 1 | 1 |
| Pro | US$ 99 | US$ 82 | 25 | 5 | 3 |
| Pro50 | US$ 179 | US$ 149 | 50 | 10 | 5 |
| Pro100 | US$ 329 | US$ 274 | 100 | 20 | 5 |
| Pro150 | US$ 449 | US$ 374 | 150 | 30 | 5 |

Add-ons: +1 usuário US$ 10/mês; +1 workspace US$ 10/mês; +5 perfis US$ 15/mês. **Sem plano grátis.**

**Pontos fracos:** curva de aprendizado e onboarding pouco claro; suporte que não entende problemas complexos; preços e comunicação inconsistentes; analytics fraco; só 1 usuário nos planos baratos (Capterra 4,4 em 39 reviews; G2 cerca de 4,7 em cerca de 478 reviews).

**Ideias para o produto contábil:** categorias fixas para contabilidade (prazos fiscais, dicas, institucional, datas comemorativas, legislação) com reciclagem; onboarding em que a IA lê o site ou Instagram do cliente e gera um mês de posts; opção de serviço "feito para você".

---

### 3.6 FeedHive (feedhive.com)

**Público e proposta de valor.** Criadores e marketers, com foco em IA e automação. A proposta é escrever com IA, prever o desempenho e automatizar o pipeline de conteúdo.

**Funcionalidades**
- **Agendamento:** smart scheduling, posting plans, threads, primeiro comentário, **variáveis** em templates, rótulos e templates. Janela de agendamento de 14 dias no Creator e de 60 dias no Brand.
- **Canais:** Facebook, Instagram, YouTube, X, TikTok, LinkedIn, Pinterest, GBP e Threads. Bluesky e Mastodon ficam fora do Creator.
- **IA:** agente de escrita, geração de imagem e de hashtags e **previsão de desempenho**. A previsão é uma nota de 0 a 100 da probabilidade de taxa de engajamento alta, calculada com histórico, horário e tipo de conteúdo. Funciona com créditos (2,5 mil a 100 mil por mês).
- **Automação:** construtor visual de **workflows**, **post conditions** (publicação condicional por regra), sugestão de posts para reciclar e webhooks.
- **Aprovação:** rascunhos com comentários e aprovação. Terceiros consideram leve para agências.
- **Inbox:** Social Inbox, sem detalhes.
- **Analytics:** stats por post. LinkDrip faz encurtamento e rastreio de links, mas **não há link na bio**.
- **API e agentes:** **REST API**, **MCP**, **CLI**, skill para Claude Code e OpenClaw, Zapier e Make.
- **App mobile:** não tem app nativo.

**Fluxo do cadastro ao primeiro post:** trial de 7 dias → conectar as redes → escrever com o agente de IA → ver a nota prevista → ajustar → agendar no smart slot.

**Diferenciais:** nota prevista antes de publicar; publicação condicional e workflows; preparado para agentes (MCP, CLI, API).

**Planos e preços** (feedhive.com/pricing, 23/10/2026)
| Plano | Mensal | Anual | Contas | Workspaces | Créditos IA/mês | Posts agendados |
|---|---|---|---|---|---|---|
| Creator | US$ 15 | US$ 180/ano | 4 | ? | 2,5 mil | 30 |
| Brand | US$ 22 | US$ 264/ano | 10 | 5 | 10 mil | 500 |
| Business | US$ 69 | US$ 828/ano | 100 | 50 | 50 mil | ilimitado |
| Agency | US$ 239 | US$ 2.868/ano | 500 | 100 | 100 mil | ilimitado |

O texto da página traz os preços anuais iguais a 12 × o mensal, apesar de anunciar "até 30% de economia". Pode ser erro na extração do texto. A distribuição de recursos por plano não ficou legível.

**Pontos fracos:** posts de Instagram que falham sem aviso ou com erro incompreensível; suporte lento; reembolso difícil; sem app; limites do Creator; aprovação fraca para agências (agregador socialk.it, jun/2026). Os reviews do Capterra (4,9 em 85) são quase todos de 2022.

**Ideias para o produto contábil:** nota prevista e checklist antes de publicar; regras de publicação ("só publique se o post anterior teve X de engajamento", "pause na semana do IRPF"); variáveis em templates ({{nome_cliente}}, {{cidade}}, {{prazo_DAS}}) para gerar um post igual para dezenas de PMEs.

---

### 3.7 Later (later.com)

**Público e proposta de valor.** Marcas visuais, creators e social media de Instagram e TikTok, além de marketing de influência. A proposta é o planejador visual (grid) com o Linkin.bio, que serve como vitrine de cliques e vendas.

**Funcionalidades**
- **Agendamento:** calendário visual, preview do grid do feed, áudio de Reels e smart scheduling (Growth+). Limite de 30 posts por perfil/mês no Starter e 180 no Growth.
- **Canais:** Instagram, Facebook, Threads, Pinterest, TikTok, LinkedIn, YouTube e Snapchat. **Sem X e sem WhatsApp.**
- **IA:** legendas e conteúdo por créditos (5, 50 ou 100 por mês, mais US$ 3,75 por 100 créditos). Melhor horário por perfil no Starter e multiperfil nos outros planos.
- **Aprovação:** fluxos internos e **externos**, comentários em posts e compartilhamento de calendário (Growth+). Não detalhamos como funciona a aprovação externa.
- **Inbox:** conversas de IG, FB e TikTok (Growth+).
- **Analytics:** de 3 meses a 2 anos. Analytics personalizado e de Meta Ads só no Scale. Benchmarking de concorrentes, saúde da marca e menções no Scale.
- **Link na bio:** Linkin.bio em todos os planos, com analytics. A empresa fala em mais de 1 bilhão de transações rastreadas.
- **Outros:** coleta de UGC, plataforma de influenciadores (self-serve ou serviço completo).
- **API:** não verificado. **App mobile:** sim, segundo o conhecimento geral do mercado, mas não verificamos nesta coleta.

**Fluxo do cadastro ao primeiro post:** trial de 14 dias → conectar o Instagram e as demais redes → subir mídia para a biblioteca → arrastar a mídia para o calendário e o grid → legenda com IA → agendar.

**Diferenciais:** preview do grid; Linkin.bio maduro; ecossistema de influenciadores e UGC.

**Planos e preços** (later.com/pricing, 23/10/2026, cobrança anual; a página não mostrou o preço mensal)
| Plano | Preço/mês (anual) | Social sets (perfis) | Usuários | Posts | Créditos IA |
|---|---|---|---|---|---|
| Starter | US$ 18,75 | 1 (8) | 1 | 30 por perfil/mês | 5 |
| Growth | US$ 37,50 | 2 (16) | 2 | 180 por perfil/mês | 50 |
| Scale | US$ 82,50 | 6 (48) | 4 | ilimitado | 100 |

Social set extra: US$ 11,25/mês. Usuário extra: US$ 3,75/mês.

**Pontos fracos:** posts de Instagram que não publicam; tokens que desconectam com frequência; limites de posts; IA por créditos; recursos-chave só nos planos mais caros (Capterra 4,4 em 398 reviews, mar/2026). Um blog concorrente cita **1,3/5 no Trustpilot**, número que não verificamos. Fraco para LinkedIn/B2B. Poucos usuários por plano.

**Ideias para o produto contábil:** página de link na bio por cliente com botões prontos ("Abrir empresa", "Falar no WhatsApp", "Enviar documentos", "Agendar reunião") e analytics de cliques; preview do grid para o cliente aprovar o "visual do mês".

---

### 3.8 Postiz (postiz.com, código aberto)

**Público e proposta de valor.** Agências, criadores e desenvolvedores que querem uma ferramenta **de código aberto e self-hostável** com API, MCP e IA. O repositório gitroomhq/postiz-app tem cerca de 37,6 mil estrelas e 7,3 mil forks (página do GitHub, 23/10/2026) e usa licença **AGPL-3.0**.

**Funcionalidades**
- **Agendamento:** calendário (dia, semana, mês), cross-posting, posts repetidos, comentários e "delays" no post, sets (pré-configurações), assinaturas, auto-post via RSS, "Plugs" internos e globais (automação por engajamento, como repostar ou comentar automaticamente), editor de imagens e rascunhos.
- **Canais:** cerca de 30, entre eles X, LinkedIn (perfil e página), Instagram (inclusive standalone), Facebook, TikTok, YouTube, Threads, Pinterest, Reddit, Discord, Slack, Telegram, Bluesky, Mastodon, GBP, WordPress, Medium, Dev.to, Hashnode, Nostr, VK, Dribbble, Farcaster, Lemmy e Tumblr. **WhatsApp não aparece na lista.**
- **IA:** copilot de texto, Smart Agent, imagens (100 a 500 por mês), vídeos (3 a 60 por mês) e **clipping de vídeo** (60 a 600 min por mês). No self-host, o usuário traz a própria chave de OpenAI ou de outro provedor.
- **Aprovação:** cada post tem um **link público de preview** com caixa de comentários. O cliente não precisa de conta e não vê o resto da organização. **Limitações:** o link não tem senha e **não existe status de "aprovado"** que bloqueie a publicação. Quem move o rascunho para agendado é o operador.
- **Multi-cliente:** "customer groups" agrupam os canais de um cliente e filtram o calendário. Membros ilimitados a partir do Team.
- **Inbox:** não tem (só comentários internos).
- **Analytics:** por plataforma e por post (também via API).
- **Integrações:** API pública, OAuth2 para apps de terceiros, webhooks (evento "publicado"), **MCP**, **CLI** e n8n/Make (comunidade).
- **App mobile:** não verificado.

**Fluxo do cadastro ao primeiro post (cloud):** trial de 7 dias → "Add channel" (OAuth com a rede) → criar post no calendário → escolher os canais, o texto (copilot) e a mídia → configurações por rede → "Add to calendar". No **self-host**, antes de tudo é preciso subir Docker com PostgreSQL, Redis, storage e Temporal, e **registrar e aprovar seus próprios apps** em Meta, Google e TikTok, o que pode levar semanas.

**Diferenciais:** código aberto e self-hostável; muitos canais; API, OAuth, MCP, CLI e webhooks; preço por canal sem limite de posts; clipping de vídeo com IA.

**Planos e preços (cloud)** (postiz.com/pricing, 23/10/2026)
| Plano | Mensal | Anual (por mês) | Canais | Membros |
|---|---|---|---|---|
| Standard | US$ 29 | US$ 23 | 5 | não |
| Team | US$ 39 | US$ 31 | 10 | ilimitado |
| Pro | US$ 49 | US$ 39 | 30 | ilimitado |
| Ultimate | US$ 99 | US$ 79 | 100 | ilimitado |

Posts ilimitados e trial de 7 dias. O self-host é gratuito (AGPL). O Postiz vende serviço pago de aprovação de apps nas redes.

**Pontos fracos:** deploy via Docker trabalhoso; aprovação de apps nas redes demorada no self-host; faltam fluxos em lote; preço dos planos altos (resumo PostPlanify, mai/2026); sem inbox; aprovação sem trava; o upgrade de versão às vezes muda o schema do banco (v2.25.0).

#### 3.8.1 API pública do Postiz (para integração)

Fontes: docs.postiz.com/public-api, /public-api/posts/create, /public-api/uploads/*, /oauth, /llms.txt e /general/automations/webhooks (lidas em 23/10/2026).

**Base URL**
- Cloud: `https://api.postiz.com/public/v1`
- Self-hosted: `https://{seu-dominio}/api/public/v1`
- Há especificação OpenAPI em `docs.postiz.com/public-api/openapi.json`.

**Autenticação**
- **API key:** fica em Settings → Developers. Vai no header `Authorization: <api-key>`, **sem o prefixo "Bearer"**.
- **OAuth2**, para um app agir em nome de outros usuários do Postiz:
  - Registrar o app em Settings → Developers → Apps. O Client ID tem prefixo `pca_` e o Client Secret `pcs_`. O secret aparece uma única vez e pode ser rotacionado.
  - Autorizar: `https://platform.postiz.com/oauth/authorize?client_id=...&response_type=code&state=...`
  - Trocar o código: `POST https://api.postiz.com/oauth/token`, com JSON `{grant_type, code, client_id, client_secret}`. Retorna `access_token` (`pos_...`), `token_type: bearer`, `id` (organização) e `cus` (cliente Stripe).
  - O código expira em 10 minutos e é de uso único. **O token não expira.** O usuário revoga em Settings → Approved Apps. Apagar o app revoga todos os tokens.
  - **Scopes não são documentados.**

**Endpoints principais** (lista da documentação)
- **Integrações:** `GET /integrations` (lista canais), `GET /integrations/groups` (customers), connect (OAuth de canal), settings/tools, trigger, delete, is-connected, me e `GET /find-slot/{integrationId}` (próximo horário livre).
- **Posts:** `GET /posts` (lista), `POST /posts` (cria), delete, delete-by-group, missing-content, update-release-id, change-status e settings.
- **Mídia:** `POST /upload` (multipart), `POST /upload-from-url`, `GET /media/{id}/status` e list-media.
- **Analytics:** por plataforma e por post. **Notificações:** lista.
- **Vídeo IA:** generate e function. **Clipping:** create, get e list.

**Criar post: `POST /posts`**
```json
{
  "type": "schedule",               // "now" | "schedule" | "draft"
  "date": "2026-11-03T13:00:00.000Z", // UTC ISO 8601 (use sufixo Z)
  "shortLink": false,
  "tags": [],                        // obrigatório (pode ser vazio); itens {value,label}
  "posts": [
    {
      "integration": { "id": "<id-do-canal>" },
      "group": "<opcional: id para agrupar posts relacionados>",
      "value": [
        { "content": "Texto do post", "image": [ { "id": "<id-midia>", "path": "<url-midia>" } ] }
      ],
      "settings": { "__type": "instagram", "post_type": "post" }
    }
  ]
}
```
- Um item em `posts` por canal, o que permite **vários canais numa única chamada**.
- `settings.__type` é obrigatório. Cada plataforma pede campos próprios: YouTube exige `title` e `type`; Reddit exige `subreddit`; TikTok exige `content_posting_method` (`DIRECT_POST` publica, `UPLOAD` só manda para o inbox do app); GBP aceita `topicType` e CTA.
- Threads, Mastodon, Bluesky, Telegram, Nostr e VK só pedem `__type`.
- `type: "draft"` cria rascunho, o que é útil para mandar ao preview de aprovação.
- Campos opcionais `order` e `inter` (intervalo) não têm documentação.
- **Resposta:** `[{ "postId": "...", "integration": "..." }]`.
- Existe um assistente que gera o payload: `https://platform.postiz.com/modal/dark/all`.

**Enviar mídia**
- `POST /upload`: multipart com campo `file` e `adjust` opcional (`"true"` redimensiona e transcodifica em segundo plano).
- MIME aceitos: jpeg, png, gif, webp, avif, bmp, tiff e mp4. **PDF não é aceito.** O conteúdo real do arquivo é validado, não só a extensão.
- `POST /upload-from-url`: JSON `{ "url": "https://...", "adjust": false }`. A URL precisa ser pública, HTTPS e sem autenticação. A proteção SSRF bloqueia IPs privados (no self-host, `DISABLE_SSRF_PROTECTION` desliga). URLs assinadas podem expirar antes de o Postiz buscar o arquivo.
- Com `adjust: true`, o vídeo vai para 1080 px no lado menor (máximo 1920 px), em H.264/AAC MP4. Consultar `GET /media/{id}/status` até `ready`.
- A resposta traz `id`, `path` e `status`, e esses valores vão no array `image` do post. Fazer o upload antes evita o erro 413 (corpo de `/posts` acima de 50 MB com base64).

**Limites de taxa: a documentação se contradiz**
- A página de introdução diz que **só a criação de post é limitada**: 90 req/h no self-host padrão e 100 req/h no cloud. O valor é global para a instância, não depende do plano, e no self-host o `API_LIMIT` muda o número.
- As páginas dos endpoints de criar post, upload e upload-from-url dizem **30 req/h**.
- **Desenhar para o pior caso (30/h)** e agrupar vários posts por chamada.

**Erros:** 400 (corpo inválido), 401 (sem header), 403 (recurso de outro dono), 404, 413 (mais de 50 MB), 429 (limite de taxa) e 5xx (retry com backoff). Num DELETE, 404 significa que o recurso já foi apagado. Alguns 500 também significam isso (bug conhecido).

**Webhooks:** o único evento documentado é "post publicado", com escopo para todos os canais ou só alguns. O payload não é documentado (use "Send Test"). No cloud, a quantidade de webhooks depende do plano. No self-host não há limite.

**MCP e CLI:** disponíveis (docs /mcp/* e /cli/*), com ferramentas para posts, integrações, analytics, upload e clipping.

**Implicações para nós**
1. **AGPL-3.0:** se modificarmos o Postiz e o oferecermos como serviço, precisamos disponibilizar o código modificado. Usar o Postiz **sem modificar**, como serviço separado acessado pela API, reduz esse risco. Validar com um jurídico.
2. Cada canal de cada cliente do escritório vira uma "integration". Os "customers" do Postiz espelham os clientes do escritório.
3. Para o cliente conectar a própria rede sem acessar o Postiz, usar o endpoint "Connect Channel (OAuth)". Falta confirmar o comportamento exato.
4. Com o limite de 30 a 100 criações por hora, agendar o mês de 50 clientes exige usar lotes (vários `posts[]` por chamada) e fila no nosso backend.
5. A aprovação com bloqueio precisa ser implementada do nosso lado: o post fica em `draft` e só muda para `schedule` depois do "aprovado".

**Ideias para o produto contábil:** usar o Postiz como motor de publicação self-hosted e construir por cima a UX contábil, a aprovação com trava e o WhatsApp; aproveitar o `find-slot` para distribuir posts de dezenas de clientes; usar webhook de "publicado" para avisar o cliente no WhatsApp.

---

## 4. Diferenciais que mais importam para escritórios contábeis

| Necessidade do escritório | Melhor referência hoje | Lacuna do mercado |
|---|---|---|
| Aprovar o post do cliente PME (que só usa WhatsApp) | mLabs (envio para o WhatsApp) | Ninguém deixa aprovar **dentro** do WhatsApp com botões "Aprovar / Ajustar" |
| Gerar posts iguais para 40 clientes com personalização | FeedHive (variáveis), SocialBee (categorias) | Não há biblioteca de conteúdo setorial (fiscal e contábil BR) com calendário tributário |
| Calendário editorial com datas fiscais (DAS, IRPF, DCTFWeb, eSocial, 13º) | mLabs (calendário de marketing genérico) | Ninguém integra o calendário fiscal brasileiro |
| Compliance (CFC / Código de Ética, LGPD) | nenhuma | Ninguém revisa a peça antes de publicar (promessa de resultado, preço, captação indevida) |
| Relatório mensal simples para o empresário | mLabs (portal white label), Metricool | Relatórios feitos para social media, não para o dono de PME |
| Preço com dezenas de clientes pequenos | Metricool (faixas), Postiz (por canal) | Preço por marca (mLabs) ou por canal (Buffer) cresce rápido |
| Atendimento (DM e WhatsApp) | mLabs Chat | O inbox não junta as dúvidas do cliente final com a contabilidade |

---

## 5. Ideias a incorporar no produto novo (consolidado)

1. **Aprovação via WhatsApp com trava.** O post vai para o WhatsApp do cliente com preview e botões "Aprovar", "Pedir ajuste" e "Reprovar". Sem aprovação, o post não sai, ao contrário do Postiz. Inspiração: mLabs para o canal e Metricool para o quórum e a trava.
2. **Portal do cliente sem login com a marca do escritório**, que agrupa todos os posts pendentes. Inspiração: Metricool e mLabs.
3. **Biblioteca de conteúdo contábil com variáveis:** {{razao_social}}, {{segmento}}, {{cidade}}, {{prazo}}. Gera o mesmo tema para N clientes com um clique, e a IA adapta ao segmento de cada PME. Inspiração: FeedHive e SocialBee.
4. **Calendário fiscal brasileiro embutido** (vencimentos, campanhas como IRPF e MEI), com sugestão automática de pautas.
5. **Copilot de onboarding:** a IA lê o site ou Instagram do cliente e gera personas, categorias e um mês de posts. Inspiração: SocialBee e o Hal-2 da Etus.
6. **Score pré-publicação** com previsão de engajamento e **checagem de compliance CFC/LGPD**. Inspiração: FeedHive, com a compliance como diferencial próprio.
7. **Reciclagem evergreen por categoria** (dicas fiscais recorrentes). Inspiração: SocialBee.
8. **Relatório mensal automático** em linguagem de empresário, enviado por WhatsApp ou e-mail. Inspiração: mLabs e Metricool.
9. **Link na bio por cliente** com botões contábeis e analytics. Inspiração: Later e Metricool.
10. **Automação de DM e comentário** (palavra-chave → material ou WhatsApp do escritório). Inspiração: Metricool Flows e mLabs Chat.
11. **Dois modos no mesmo painel:** "Meu escritório" (o próprio marketing) e "Meus clientes" (operação multi-cliente com customers/workspaces).
12. **Preço por faixa de clientes**, usuários ilimitados e Pix. Inspiração: Metricool, mLabs e Etus.
13. **Monitor de saúde das conexões:** alerta proativo de token expirado e de post que falhou, com reenvio. Ataca a principal dor do mercado.
14. **Motor de publicação:** Postiz self-hosted via API (rascunho → aprovação → schedule), com fila e lotes para respeitar o limite de taxa.
15. **MCP/API própria** para que o escritório opere por agentes (Claude, ChatGPT), seguindo Buffer, Metricool, FeedHive e Postiz.

---

## 6. Limitações desta pesquisa

- Nenhum produto foi testado. Os fluxos de onboarding vêm da documentação e de artigos.
- Não conseguimos acessar diretamente Reclame Aqui, Capterra, G2 nem Trustpilot (erro 403). Os números dessas fontes vêm de trechos de resultados de busca e de agregadores, alguns deles blogs de concorrentes, como PostPlanify e socialk.it.
- **Etus/KingHost:** não há tabela de preços pública e atual. A lista de recursos mistura páginas da Locaweb (sem data) e da KingHost.
- **mLabs:** a calculadora de preço não expôs valores para várias marcas no texto extraído. Não há API pública documentada. O MCP não está documentado publicamente.
- **FeedHive:** a grade de recursos por plano não ficou legível no texto extraído.
- **Later:** não verificamos API, app mobile nem o funcionamento detalhado da aprovação externa.
- **SocialBee:** a página de preços exibia uma promoção vencida, então os valores podem estar desatualizados.
- **Postiz:** a documentação se contradiz sobre os limites de taxa, e o payload dos webhooks e os scopes de OAuth não estão documentados.
- Não conseguimos consultar a API do GitHub nesta sessão (acesso restrito). Os números de estrelas e forks vêm da página web do repositório.

---

## 7. Fontes

**mLabs**
- https://www.mlabs.com.br/
- https://www.mlabs.com.br/planos
- https://www.mlabs.com.br/inteligencia-artificial
- https://www.mlabs.com.br/blog/como-usar-mlabs/
- https://www.mlabs.com.br/blog/mlabs-chat/
- https://www.mlabs.com.br/en/products/chat
- https://ajuda.mlabs.com.br/en/articles/14640042-discover-mlabs-chat
- https://ajuda.mlabs.com.br/en/articles/14667308-how-to-manage-whatsapp-in-mlabs-chat
- https://www.reclameaqui.com.br/empresa/mlabs_184276/lista-reclamacoes
- https://www.reclameaqui.com.br/mlabs_184276/suporte-tecnico-demorado-e-ineficiente-da-mlabs_GyT_xkV3MNmiNJQs/
- https://www.capterra.com/p/191356/mLabs/reviews/
- https://tecnoblog.net/noticias/facebook-suspende-39-milhoes-de-posts-de-clientes-da-mlabs-socia-da-stone/
- https://manyfesto.app/blog/alternativas-ao-mlabs

**Etus / KingHost**
- https://king.host/etus-agora-e-kinghost
- https://king.host/gerenciador-de-redes-sociais
- https://www.locaweb.com.br/etus/
- https://www.locaweb.com.br/ajuda/?p=25641
- https://www.locaweb.com.br/ajuda/wiki/o-que-e-a-etus/
- https://www.b2bstack.com.br/product/etus
- https://startupi.com.br/?p=191702
- https://www.getapp.com/marketing-software/a/etus/

**Metricool**
- https://metricool.com/
- https://metricool.com/pricing/
- https://help.metricool.com/en/article/how-to-send-posts-for-review-with-metricools-approval-system-1hlft5g/
- https://help.metricool.com/inbox-manager-how-to-manage-messages-and-comments-from-metricool-s9zze
- https://www.trustpilot.com/review/metricool.com
- https://postplanify.com/metricool-reviews
- https://ainfluencer.com/metricool/

**Buffer**
- https://buffer.com/
- https://buffer.com/pricing
- https://support.buffer.com/articles/managing-and-approving-draft-posts-57li7M8tDA
- https://socialk.it/en/reviews/buffer
- https://www.capterra.ca/reviews/143492/buffer

**SocialBee**
- https://socialbee.com/
- https://socialbee.com/pricing/
- https://www.capterra.com/p/210359/SocialBee/reviews/
- https://g2.com/products/socialbee/reviews
- https://ainfluencer.com/socialbee/

**FeedHive**
- https://www.feedhive.com/
- https://www.feedhive.com/pricing
- https://www.feedhive.com/user-guide/how-engagement-prediction-works
- https://socialk.it/en/reviews/feedhive
- https://www.capterra.com/p/240356/FeedHive/reviews/
- https://marcandrews.com/feedhive-review-2026

**Later**
- https://later.com/
- https://later.com/pricing/
- https://capterra.com/p/152254/Later/reviews/
- https://postplanify.com/later-reviews

**Postiz**
- https://postiz.com/pricing
- https://github.com/gitroomhq/postiz-app
- https://docs.postiz.com/public-api
- https://docs.postiz.com/public-api/posts/create
- https://docs.postiz.com/public-api/uploads/upload-file
- https://docs.postiz.com/public-api/uploads/upload-from-url
- https://docs.postiz.com/public-api/integrations/find-slot
- https://docs.postiz.com/oauth
- https://docs.postiz.com/general/automations/webhooks
- https://docs.postiz.com/general/approvals
- https://docs.postiz.com/llms.txt
- https://postplanify.com/postiz-reviews
- https://dupple.com/reviews/postiz
- https://newreleases.io/project/github/gitroomhq/postiz-app/release/v2.25.0

**Comparativos gerais**
- https://nacao.digital/blog/melhores-ferramentas-social-media/ (jul/2026, atualizado em 14/10/2026)
