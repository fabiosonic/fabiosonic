# Pesquisa 03 — Vídeo com avatar de IA / clone digital

**Data da coleta:** 23/10/2026
**Escopo:** HeyGen, Synthesia, Argil, Captions/Mirage, D-ID, Colossyan, DeepBrain AI (AI Studios) e, como componente de voz, ElevenLabs.
**Método:** só informação pública (sites oficiais, páginas de preço, documentação de API, central de ajuda, reviews em Trustpilot/Capterra/Gartner e artigos de terceiros). Nenhuma área logada foi acessada e nenhum código foi copiado ou descompilado.
**Objetivo de produto:** extrair ideias para um produto voltado a escritórios de contabilidade brasileiros que querem vídeos curtos (30 a 90 s, verticais) com o clone do sócio.

> **Como ler a confiança dos dados**
> - **[oficial]**: página do fornecedor (preço, docs ou help center) lida nesta coleta.
> - **[3º]**: fonte secundária (blog comparativo, agregador). Vários desses blogs são de **concorrentes** (Creatify, Argil, Anam), então podem puxar a sardinha para o próprio lado.
> - **[não verificado]**: conhecimento geral do mercado que não consegui confirmar numa página atual. Trate como hipótese.
> - Preços em **USD**, sem impostos. Quando converto para reais, uso **R$ 5,50/US$**, uma premissa minha e não uma cotação verificada. Para assinatura de software estrangeiro paga com cartão brasileiro, some IOF (3,5% em 2025; confirme a alíquota vigente).

---

## 1. Resumo executivo

- **O mercado se dividiu em três grupos:**
  - **Corporativo/L&D** (Synthesia, Colossyan, DeepBrain): treinamento, SCORM, governança, SSO.
  - **Creator/marketing de vídeo curto** (Argil, Captions/Mirage): vertical, legenda animada, b-roll automático, "gêmeo" gravado em segundos.
  - **Plataforma generalista + API** (HeyGen, D-ID): amplitude de recursos, API por uso, avatar interativo.
- **Criar um clone ficou barato e rápido.** Captions diz precisar de cerca de 10 s de vídeo e HeyGen fala em 15 a 30 s no Avatar V (a documentação de API da própria HeyGen ainda cita cerca de 2 min de footage de treino). Synthesia pede de 1 a 5 min. Argil **descontinuou o avatar a partir de vídeo na API** e só aceita avatar por foto.
- **A verificação de consentimento por vídeo virou padrão.** A pessoa grava na webcam uma frase de autorização, e a plataforma confere se o rosto bate com o do material de treino. Mas os avatares feitos **a partir de foto** costumam passar sem checagem de consentimento: a HeyGen diz isso explicitamente na API.
- **O preço por minuto varia mais de 10 vezes** entre motores. Na API da HeyGen, o Avatar III com Digital Twin custa US$ 0,60/min e o Avatar V custa US$ 7,20/min. O Mirage Avatar X (Captions) custa US$ 9/min.
- **A rotulagem de IA ganhou peso regulatório.** O Art. 50 do AI Act europeu passou a valer para quem implanta sistemas em 02/08/2026. A Synthesia aplica C2PA automaticamente em todos os planos. No Brasil, o PL 2338/2023 tramitava sem vigência confirmada nesta coleta.
- **Português do Brasil:** todos dizem suportar, mas **não encontrei nenhum teste independente** de sotaque ou prosódia em pt-BR. É a maior lacuna desta pesquisa. A recomendação é fazer um teste cego com o mesmo roteiro contábil, com termos como "DCTFWeb", "eSocial" e "pró-labore".

---

## 2. Fichas por ferramenta

### 2.1 HeyGen

**Público e proposta.** Plataforma generalista de vídeo com avatar para marketing, vendas, social e treinamento. Promete "clone seu rosto e sua voz e gere vídeo em 175+ idiomas", com uma API madura para automação.

**Funcionalidades**
- **Clone (Digital Twin):**
  - O marketing fala em 15 a 30 s de gravação no Avatar V, com o twin pronto em 10 a 20 min [oficial: blog]. A documentação de API diz que o footage de treino "normalmente tem cerca de 2 minutos" [oficial: docs]. As duas fontes da HeyGen divergem entre si.
  - **Consentimento:**
    - Um vídeo separado com menos de 35 s, no qual a pessoa lê uma frase do tipo "I, [nome], autorizo a HeyGen a usar minha imagem…". A frase pode ser traduzida, e a validação é semântica.
    - Rosto único, igual ao do footage, e áudio claro.
    - Três níveis: Nível 1, webcam via link hospedado que expira em 24 h; Nível 2, upload de vídeo pré-gravado, só Enterprise; Nível 3, dispensa mediante contrato de indenização, só Enterprise.
    - Na API: `POST /v3/avatars/{group_id}/consent` e status `pending`, `accepted` ou `rejected`. **Não há webhook de consentimento** [oficial: docs].
  - **Photo Avatar:** sem etapa de consentimento e sem registro. A responsabilidade fica com o cliente [oficial: docs].
- **Avatares prontos:** 500+ no plano gratuito e 700+ nos pagos, com 500 "looks" por avatar [oficial: preço].
- **Voz e idiomas:** 30+ idiomas no Free e 175+ nos pagos. Clonagem de voz em todos os planos, e o Free inclui 1 clone. TTS próprio ("HeyGen Voice", modelo Starfish) e integração com ElevenLabs [não verificado]. Para pt-BR há promessa de lip-sync e clone nativos [oficial: páginas pt-BR], mas não achei teste independente.
- **Sincronia labial:** motores Avatar III (legado, barato), Avatar IV (foto e twin, mais expressivo) e Avatar V (o mais realista em 2026).
- **Editor e templates:** AI Studio baseado em cenas, templates, Brand Kit/Brand System (Business+), Video Agent (prompt para vídeo) e "Avatar Shots — Cinematic".
- **Legendas, b-roll e música:** legendas automáticas e biblioteca de mídia [não verificado em detalhe]. AI Clipping (cortes de highlights) e remoção de palavras de preenchimento aparecem na tabela de API [oficial].
- **Vertical:** sim, 9:16 [não verificado na página; prática padrão da ferramenta].
- **Tradução e dublagem:** Video Translation em três modos (só áudio, lip-sync rápido e lip-sync precisão), com modo Proofread em todos os planos pagos [oficial].
- **Tempo real:** LiveAvatar (antes Interactive Avatar), com planos e preço separados da API [oficial: help].
- **API:**
  - Carteira pré-paga em USD. Chave de API debita a carteira, OAuth debita os créditos do plano web [3º].
  - Créditos PAYG expiram em 12 meses. Concorrência de 10 vídeos no plano de API e 20 no Enterprise, com 429 e `Retry-After` acima do limite [oficial, atualizado em 19/10/2026].
  - Endpoints principais: geração de vídeo com avatar, tradução, criação de avatar e consentimento (v3), TTS e webhooks de treino (`instant_avatar`) [oficial: docs].
  - Os planos legados API Pro e API Scale foram descontinuados para novos clientes.
  - **No Avatar IV e no Avatar V não existe 4K nativo via API**: o arquivo vem em 4K, mas o avatar é renderizado em 1080p e esticado [oficial].
- **Integrações:** Zapier, Canva, HubSpot e outras (Business+) [não verificado individualmente]. SCORM no Business.
- **Segurança e ética:**
  - Consentimento por vídeo e remoção de semelhança a pedido da pessoa clonada. Vídeos já exportados não são apagados.
  - Vídeos privados por padrão e dados usados para treinar modelos só com consentimento.
  - Política de moderação existe, mas sem detalhe público lido.
  - A HeyGen *recomenda* rótulo visível de IA e aviso falado, mas **não encontrei menção a C2PA ou marca d'água automática** nos planos pagos [oficial: blog de 20/10/2026].

**Fluxo do usuário:** cadastro, com Free de 3 vídeos/mês de até 1 min e marca d'água → criar avatar (gravar footage e consentimento na webcam) → espera de 10 a 20 min → escolher template ou cena em branco → colar roteiro e escolher voz (clonada) → gerar → exportar MP4 ou link.

**Diferenciais:** a maior amplitude de recursos do mercado (twin, foto, tradução, Video Agent, Live) e uma API por uso com tabela de preço pública e detalhada, incluindo o Avatar III barato para volume.

**Preços (página oficial, 23/10/2026)**

| Plano | Mensal | Créditos/mês | Destaques |
|---|---|---|---|
| Free | US$ 0 | — | 3 vídeos/mês, 1 min, marca d'água, 1 avatar, 1 clone de voz |
| Creator | US$ 29 (US$ 24 no anual) | 600 | até 30 min, 1080p, sem marca d'água |
| Pro | a partir de US$ 49 | 1.000 (escala até 100 mil por US$ 4.300) | 4K, Cinematic Avatars |
| Business | US$ 149 + US$ 20/assento | 1.500 | 5+ avatares, SSO, Brand Kit, SCORM |
| Enterprise | sob consulta | sob uso | sem limite de duração |

- **No Studio**, um blog de terceiros diz que o Avatar IV consome 20 créditos/min, e as páginas de integração Seedance da própria HeyGen dizem que o Avatar V consome 48 créditos/min. Não confirmei na página de preço. Top-up no Business: US$ 0,05/crédito [3º].
- **API (help center oficial, atualizado em 19/10/2026), preço por minuto, cobrado por segundo:**
  - Avatar V, Digital Twin: **US$ 7,20**
  - Avatar IV: Photo **US$ 2,31**, Digital Twin e Studio **US$ 4,83**
  - Avatar III: Digital Twin **US$ 0,60**, Studio e Photo **US$ 0,99**
  - Video Agent: US$ 5,82
  - Tradução: só áudio US$ 0,57, lip-sync rápido US$ 0,81, lip-sync precisão US$ 1,50
  - TTS Starfish: US$ 0,12/min. Voz instantânea: US$ 15 por 1 milhão de caracteres
  - Criação de avatar: Digital Twin **US$ 2,13 por chamada**, Photo US$ 1,32

**Pontos fracos e reclamações** (Trustpilot, 2025–2026)
- O modelo de créditos é opaco: o usuário não sabe quanto cada motor consome.
- Créditos são debitados mesmo quando a geração falha.
- Renovações automáticas e recusa de reembolso.
- Suporte lento, que responde com template.
- Mudanças de preço frequentes, com uma reestruturação em meados de 2026 segundo um blog de terceiros.
- Diferença de qualidade grande entre motores, e o motor bom é caro.

**Ideias para o produto contábil**
1. Mostrar **o custo em reais antes de gerar**, por vídeo e não por crédito, e **não cobrar falha** de geração.
2. Usar um motor barato (do tipo Avatar III) para rascunho e pré-visualização, e o motor premium só no render final.
3. Copiar o fluxo de consentimento em 3 níveis, mas **com registro de consentimento também para avatar por foto**.
4. Usar o modo "Proofread" (revisão do roteiro traduzido) como etapa obrigatória de revisão do roteiro pelo sócio.

---

### 2.2 Synthesia

**Público e proposta.** Corporativo: treinamento, onboarding, comunicação interna e L&D. O argumento é segurança, governança e escala multilíngue. É a mais "enterprise" do grupo.

**Funcionalidades**
- **Clone (Personal Avatar):**
  - Por webcam, no app, ou por upload de vídeo pré-gravado: tomada contínua de **1 a 5 min**, uma só pessoa em primeiro plano [oficial: help].
  - Exige **gravação de consentimento** antes do processamento. O processamento leva cerca de 1 dia útil pela help center, ou de 1 a 5 dias úteis para Studio Avatar com footage próprio.
  - O "Studio Avatar" é feito em estúdio e com tela verde. O Photo Avatar exige foto e vídeo de consentimento ao vivo, e a submissão é rejeitada se o rosto não bater [oficial: help].
  - Usa verificação biométrica por fornecedor terceiro (AWS) e trata os dados como biométricos sob GDPR e BIPA [3º: resumo da política].
  - Avatares pessoais: 5 no Pro e ilimitados no Enterprise.
- **Avatares prontos:** 9 no Basic, 125+ no Starter, 180+ no Pro e 240+ no Enterprise. Há avatares "Express-2" e Studio com microexpressões [3º].
- **Voz e idiomas:** 140+ idiomas no Enterprise e dublagem para 70+ idiomas nos planos self-serve. Português (Brasil) está entre as vozes [não verificado: teste de qualidade]. Os reviews no Capterra elogiam o multilíngue, mas reclamam de **falta de controle de cadência da fala**.
- **Editor e templates:** editor tipo slides, importação de PowerPoint, templates, AI Video Assistant (documento ou URL para vídeo), Brand Kit (Enterprise), colaboração em tempo real (Enterprise) e páginas de vídeo com a marca.
- **Legendas, b-roll e música:** legendas automáticas (SRT) e biblioteca de mídia. O b-roll automático é menos voltado a redes sociais [não verificado em detalhe].
- **Vertical:** suporta 9:16 [não verificado na página atual].
- **Tradução e dublagem:** dublagem com clone da voz original; lip-sync dobra o consumo de créditos; glossário personalizado; edição do transcript [oficial].
- **Tempo real:** Interactive Avatars API (avatar com streaming, sem arquivo de vídeo) a US$ 0,10/min só o avatar e US$ 0,20/min com o stack completo (voz, LLM e LiveKit), este último "em breve". Também vende "roleplay" e "survey avatars" [oficial].
- **API:**
  - **Video API:** assíncrona, com polling ou webhook ao concluir; templates com variáveis; tradução e dublagem.
  - **Upload API v2:** imagem, vídeo e áudio próprios.
  - **Billing API:** saldo de créditos.
  - Interactive Avatars API e servidor **MCP** documentado.
  - Os planos Starter e Pro incluem até **360 min/ano de API, debitados da cota do plano** [oficial].
- **Integrações:** exportação SCORM (Enterprise), LMS, PowerPoint e Zapier [não verificado individualmente]. SSO/SAML no Enterprise.
- **Segurança e ética:**
  - **C2PA automático** em vídeos gerados ou editados e Content Credentials no player.
  - **Rótulos visíveis de IA opcionais** em todos os planos.
  - Marca d'água visível no plano Free.
  - Apoio ao Código de Prática da UE de marcação de conteúdo de IA (junho de 2026).
  - Moderação de conteúdo antes da renderização, com fila mais rápida no Enterprise [oficial].
  - Reviews relatam bloqueios por moderação excessiva em conteúdo inofensivo.

**Fluxo do usuário:** cadastro no Basic (500 créditos e 10 min/mês grátis) → escolher template ou "AI Video Assistant" → escolher avatar e voz → escrever ou colar roteiro por cena → gerar (passa pela moderação) → compartilhar link (Basic) ou baixar MP4 (Starter+). O avatar pessoal é uma etapa paralela com consentimento e revisão de cerca de 1 dia útil.

**Diferenciais:** governança (C2PA, moderação, SSO, SOC 2 [não verificado nesta coleta]), multilíngue forte, foco em treinamento com interatividade e quizzes, API mais o MCP e **10 minutos grátis por mês em todos os planos**.

**Preços (página oficial, 23/10/2026)**

| Plano | Mensal | Anual (por mês) | Créditos | Observação |
|---|---|---|---|---|
| Basic | US$ 0 | — | 500/mês (cerca de 10 min) | marca d'água, sem download |
| Starter | US$ 29 | US$ 18 | 1.250/mês | download, sem logo |
| Pro | US$ 89 | US$ 64 | 6.000/mês | 5 avatares pessoais, vídeos interativos |
| Enterprise | sob consulta | — | custom | minutos ilimitados, 140+ idiomas |

- **Consumo:** **100 créditos por minuto de vídeo**; dublagem a 40 créditos/min sem lip-sync ou 80 com lip-sync; só os segundos regenerados são cobrados quando se edita um trecho.
- **API (rate card):** dublagem a US$ 0,40/min só voz ou US$ 0,80/min com lip-sync; Interactive Avatars a US$ 0,10 ou 0,20/min. A geração de vídeo pela API consome os créditos do plano.
- **Custo por minuto (meu cálculo):** Starter mensal ≈ US$ 2,32/min; Pro anual ≈ US$ 1,07/min, fora os 10 min grátis.
- A página tem inconsistências entre os cartões de preço e as tabelas, por isso convém confirmar com a Synthesia.

**Pontos fracos e reclamações** (Capterra 4,6 com 314 reviews; a maioria é de 2023–2025)
- Caro para pequenas empresas.
- Avatar pessoal rejeitado por questões de iluminação.
- Pouco controle de entonação e cadência; expressões às vezes "robóticas".
- A API exigia plano mais caro.
- Moderação bloqueando conteúdo inofensivo.
- Pouco orientada a vídeo curto e social.

**Ideias para o produto contábil**
1. **C2PA e rótulo "Conteúdo gerado com IA" por padrão.** É um diferencial ético importante para o setor contábil, que tem responsabilidade profissional e código de ética do CFC.
2. **Cobrar só o trecho regenerado.** O sócio corrige uma frase e não paga o vídeo inteiro de novo.
3. Uma franquia mensal gratuita pequena, no estilo dos "10 min grátis", para reter o escritório mesmo em meses fracos.
4. Glossário personalizado de pronúncia ("CNPJ", "Simples Nacional", "IRPF", "MEI").

---

### 2.3 Argil (argil.ai)

**Público e proposta.** Creators, coaches e marcas pessoais que querem **postar todo dia** vídeos curtos com o próprio clone: "Create videos every day". Foco em vídeo social vertical com edição automática. Em 2026 passou a se posicionar como uma "plataforma de produção de vídeo" mais ampla, com o fluxo "Director", workspace de equipe, conectores para vários provedores de IA e um plano "Studio" de serviço feito para o cliente.

**Funcionalidades**
- **Clone:**
  - No app, historicamente: gravação curta (1 a 5 min de dataset) mais um **vídeo de consentimento de até 30 s** [oficial: docs, página de endpoint descontinuado].
  - **Na API, a criação por vídeo foi descontinuada**: `POST /avatars` com `type: "VIDEO"` retorna 400 e manda usar `type: "IMAGE"`, ou seja, avatar a partir de uma foto [oficial: docs].
  - A Kompozy (3º) descreve o fluxo do app como "gravação curta mais vídeo de consentimento".
- **Avatares prontos:** 100+ avatares Argil, com royalty de 20 créditos por vídeo via API nos avatares v1. Avatares próprios não pagam royalty. Também há "AI influencers" e "Argil Fictions".
- **Voz:** clone de voz a partir de áudio (`POST /voices`), "ProVoices" e **integração com ElevenLabs**: se você conectar a conta ElevenLabs, a voz sai grátis na API [oficial]. Idiomas: não confirmei a lista; a voz e o idioma dependem em boa parte do ElevenLabs [não verificado para pt-BR].
- **Sincronia labial e corpo:** o diferencial citado é a **edição de linguagem corporal, gestos e ângulos de câmera** [3º e página de preço antiga].
- **Edição:** edição automática com **b-roll** (imagem de IA ou vídeo de banco), legendas com estilos (endpoint `subtitles.list` e exportação), música, ganchos ("hook framing") e templates.
- **Vertical:** formato nativo, já que o foco é TikTok, Reels e Shorts.
- **Tradução:** existe [não verificado em detalhe].
- **Tempo real:** não encontrei.
- **API** [oficial: docs.argil.ai]:
  - Vídeos: `videos.list`, `videos.create`, `videos.get`, `videos.delete`, **`videos.estimate`** (estima o custo em créditos antes de renderizar) e `videos.render`.
  - Avatares: `avatars.list`, `avatars.get`, `avatars.create` (IMAGE).
  - Vozes: `voices.list`, `voices.get`, `voices.create` e `voices.sync` (sincroniza vozes de provedores conectados).
  - Assets e legendas.
  - **Webhooks** com CRUD e eventos `video.generation.success`/`failed` e `avatar.training.success`/`failed`.
  - Spec OpenAPI pública. **Limites de requisição não documentados** nas páginas lidas.
- **Integrações:** ElevenLabs; conectores de provedores de IA (pela interface do site).
- **Segurança:** vídeo de consentimento (histórico) e cobrança só em regiões selecionadas, "para evitar fraude". Não achei política pública de rótulo de IA ou C2PA.

**Fluxo do usuário:** cadastro (trial de 5 dias segundo o blog de fev/2026) → criar avatar → escrever ou gerar roteiro → escolher estilo de edição (legendas, b-roll, gestos) → renderizar → baixar vertical.

**Diferenciais:** foi a mais orientada a "vídeo curto social com clone"; tem API com **estimativa de custo** e webhooks completos; aceita ElevenLabs próprio (BYO voice); e controla gestos e linguagem corporal.

**Preços:** **confusos e mudando.**
- A página `/pricing` atual carrega os planos via JavaScript (Pro, Business, Studio e Enterprise, com seletor de créditos mensais e cobrança em EUR) e não exibiu valores na coleta.
- O blog da Argil (09/02/2026) cita **Pro US$ 25/mês** e **Business US$ 50/mês**.
- Snippets da página antiga citam **Classic US$ 39/mês (25 "video credits", cerca de 25 min)**, **Pro US$ 149 (cerca de 100 min)** e **Scale US$ 499 (cerca de 300 min)**.
- **API [oficial]:** vídeo a **160 créditos/min**, voz a 20 créditos/min, b-roll de 10 (imagem de IA) ou 20 (stock) créditos por b-roll. O próprio exemplo da documentação tem erro de conta.
- Enterprise acima de 60 mil créditos/mês. Créditos do plano não acumulam; créditos PAYG não expiram.
- **Não consegui confirmar o preço atual por crédito.**

**Pontos fracos**
- Planos e unidades de crédito mudam com frequência (Kompozy).
- Unidades conflitantes entre fontes.
- Fim do avatar por vídeo na API, o que reduz o realismo para quem automatiza.
- Fraca em distribuição: não publica nem agenda nas redes.
- Sem tempo real.
- Pouca informação sobre pt-BR.

**Ideias para o produto contábil**
1. Endpoint e botão **"estimar custo"** antes de renderizar.
2. **Webhooks para treino e para render**, para avisar no WhatsApp: "seu clone está pronto" e "seu vídeo está pronto".
3. Edição automática com b-roll e legenda com estilos voltados a redes sociais. Para contabilidade, o b-roll seria de telas como Receita, eSocial e calendário fiscal, e de gráficos.
4. **BYO ElevenLabs** (o cliente traz a própria voz) para reduzir custo e dar qualidade de voz em pt-BR.

---

### 2.4 Captions / Mirage

**Público e proposta.** Começou como app mobile de legendas automáticas e virou um "estúdio de vídeo com IA" para creators e social. "Mirage" é a marca dos modelos fundacionais (Mirage Avatar X) e da API (mirage.app / captions.ai). Promete um **AI Twin criado com cerca de 10 s de vídeo**, ou até com selfie.

**Funcionalidades**
- **Clone (AI Twin):** cerca de 10 s de footage, lendo um script no app ou na web. Aceita footage existente, gravação nova ou selfie; vídeo dá o melhor resultado. Sobre consentimento, diz que o twin é "feito da sua gravação, com sua permissão explícita, para seu uso" [oficial]. **Não achei descrição de verificação de identidade.**
- **Avatares prontos:** "AI Creators/Actors" (atores de IA) para UGC e anúncios.
- **Voz e idiomas:** o Mirage Avatar X gera áudio, vídeo e movimento juntos. Há tradução e dublagem automática ("AI Dubbing") [oficial: a página fala em tradução e legendas; o número de idiomas e o suporte a pt-BR não foram confirmados]. Existe página da ferramenta em português ("gêmeo de IA").
- **Sincronia labial:** modelo próprio. Diz preservar a identidade melhor que modelos baseados só em imagem.
- **Editor:** editor por chat ("Edit with AI"), estilos de AI Edit, **correção de contato visual**, cortes de vídeo longo para clipes, b-roll customizado, música, efeitos e imagens (plano Max).
- **Legendas:** a origem do produto; vários templates de legenda animada.
- **Vertical:** sim, vertical e horizontal.
- **Tempo real:** não encontrei.
- **API (Mirage)** [oficial: help/docs/api/pricing, 2026]:
  - Add Captions a **US$ 0,15/min**, arredondado para o minuto seguinte.
  - **Mirage Avatar X** (vídeo ou imagem mais áudio, gerando vídeo) a **US$ 0,15/s ≈ US$ 9/min**, em blocos de 6 s. Uma versão anterior da página citava "Mirage Video 1" a US$ 0,175/s.
  - Endpoints, webhooks e limites não foram lidos nesta coleta.
- **Integrações:** exportação direta para as plataformas sociais [oficial: genérico].
- **Segurança:** "não é deepfake: é seu próprio twin". Enterprise com "training data exclusion" (seus dados fora do treino). Sem política pública de C2PA ou rótulo encontrada.

**Fluxo do usuário:** baixar o app (iOS ou Android) ou abrir a web → gravar 10 s lendo o script → digitar o roteiro → gerar → aplicar estilo de AI Edit e legendas → exportar para TikTok, Reels ou Shorts.

**Diferenciais:** o menor atrito para criar o clone, um editor social completo (legenda, contato visual, cortes) e um modelo próprio que gera voz e rosto juntos.

**Preços (página oficial, valores de iOS)**

| Plano | Mensal | Créditos/mês |
|---|---|---|
| Free | US$ 0 | — |
| Max | US$ 24,99 | 500 |
| Frontier 1x / 2x / 4x | US$ 69,99 / 139,99 / 279,99 | 1.400 / 2.800 / 5.600 |
| Enterprise | sob consulta | custom |

- Créditos acumulam até 3 vezes a franquia mensal.
- **Não encontrei quantos créditos um minuto de AI Twin consome no app.**
- API: Mirage Avatar X a US$ 9/min.

**Pontos fracos** (Trustpilot: nota 1,5 no CA com 96 reviews e 4 no DK com 227 reviews, snapshots de datas diferentes)
- A migração para "Mirage" desagradou assinantes antigos, que perderam o acesso fácil ao produto de legendas que já pagavam.
- Suporte descrito como "buraco negro".
- Pedidos de reembolso.
- API cara por minuto.
- Pouca transparência sobre consentimento e verificação.

**Ideias para o produto contábil**
1. **Onboarding do clone em menos de 1 minuto pelo celular**, porque o sócio não vai a estúdio.
2. **Correção de contato visual** e legendas animadas como padrão.
3. "Cortes" automáticos de uma live ou reunião do sócio para gerar vários vídeos curtos.

---

### 2.5 D-ID

**Público e proposta.** Pioneira em "foto falante". Hoje vende a Creative Reality Studio (vídeo com avatar), **Visual AI Agents** (avatares conversacionais em tempo real para atendimento e vendas) e uma API para desenvolvedores. É forte em **tempo real e em ser embutida em produtos de terceiros**.

**Funcionalidades**
- **Clone:**
  - **Express Avatar:** cerca de 1 min de vídeo, segundo a cobertura do lançamento em 2024.
  - **Premium+ Avatar:** alguns minutos de vídeo; pode incluir mãos e tronco. Lançado em out/2024 (TechCrunch) e documentado em docs.d-id.com.
  - **Consentimento:** a API emite um "consent challenge" com um roteiro que a pessoa lê em vídeo e que **expira em 30 min** [oficial: docs, via busca].
  - **Os números de footage são de 2024. Não confirmei os requisitos de 2026.**
- **Avatares prontos:** cerca de 25 humanos segundo a Creatify (concorrente) e 100+ no Lite segundo a Toolsurf. Há divergência.
- **Voz e idiomas:** TTS de terceiros (Microsoft, ElevenLabs) e clonagem de voz [não verificado em 2026]. Mais de 100 idiomas declarados [não verificado].
- **Tipos de avatar no SDK:** Talks (V2, foto, WebRTC), Clips (V3, apresentador pré-pronto) e **Expressives (V4, streaming LiveKit, com microfone e "fluent mode")** [oficial: docs do SDK].
- **Editor:** simples. Há plugins para Canva e PowerPoint [não verificado em 2026].
- **Legendas, b-roll e vertical:** básicos [não verificado].
- **Tradução:** existe tradução de vídeo [não verificado em 2026].
- **Tempo real:** **sim, o ponto forte.** Agents SDK (`@d-id/client-sdk`), streams e base de conhecimento.
- **API:**
  - Endpoints `/talks`, `/clips`, `/agents`, streams e traduções. Webhook informado no corpo da requisição [3º].
  - **Limites não publicados.** Usuários relatam erro 429 ao criar streams sem intervalo de cerca de 3 s.
  - A API compartilha o saldo de minutos com o Studio. Os minutos são arredondados para blocos de **15 s** e não acumulam.
- **Segurança:** consentimento por desafio com roteiro e marca d'água nos planos baratos (tela cheia no Trial, logo no Lite e marca "AI" genérica no Pro, segundo terceiros). O CEO declara a intenção de não permitir uso enganoso.

**Fluxo do usuário:** cadastro (trial de 14 dias com marca d'água) → escolher foto, avatar ou criar um Express → digitar texto ou subir áudio → gerar → baixar. Para os Agents: criar o agente, subir a base de conhecimento e embutir o widget no site.

**Diferenciais:** tempo real, SDK para embutir, preço de entrada baixo e animação de foto.

**Preços (Toolsurf, out/2026, que diz refletir o publicado pela D-ID; a página oficial é renderizada em JS e não pôde ser lida)**

| Studio | Mensal | Anual | Minutos/mês | Licença e marca d'água |
|---|---|---|---|---|
| Lite | US$ 5,90 | US$ 56/ano | 10 | pessoal, logo D-ID |
| Pro | US$ 29 | US$ 191/ano | 15 | comercial, marca "AI" |
| Advanced | US$ 196 | US$ 1.293/ano | 100 | comercial, logo próprio |

| API | Mensal | Vídeo (min) | Streaming (min) | Marca d'água |
|---|---|---|---|---|
| Build | US$ 14,40 | 16 | 32 | D-ID |
| Launch | US$ 35 | 45 | 90 | não informado |
| Scale | US$ 138,60 | 200 | 400 | logo próprio |

Custo efetivo por minuto, meu cálculo com uso integral: Build ≈ US$ 0,90, Launch ≈ US$ 0,78 e Scale ≈ US$ 0,69.

**Pontos fracos:** realismo inferior ao de HeyGen e Synthesia nos avatares de foto; marca d'água até em planos pagos; minutos que não acumulam; limites de API não publicados; informação pública dispersa e desatualizada.

**Ideias para o produto contábil**
1. **Agente em tempo real com o rosto do sócio no site do escritório**, para triagem do tipo "abrir empresa, MEI, IR". É uma fase 2 do produto.
2. Fazer o consentimento por **desafio com roteiro e código que expira**, como antifraude.

---

### 2.6 Colossyan

**Público e proposta.** Treinamento corporativo e L&D. Converte documentos e PPT em vídeo, cria cenários de conversa e vídeos interativos e exporta SCORM. Concorre de frente com a Synthesia, por um preço menor.

**Funcionalidades**
- **Clone:** "Instant Avatars" (15 no Starter e 20 no Professional) e "Studio custom avatars" como add-on de **US$ 1.000/ano**. Também é possível criar Instant Avatars e clones de voz pela API [oficial]. **Não achei os requisitos de footage nem o fluxo de consentimento.**
- **Avatares prontos:** 300+ avatares e 700+ vozes.
- **Idiomas:** 120+, com 15 a 20 traduções automáticas por mês nos planos self-serve [oficial]. pt-BR declarado, sem teste encontrado.
- **Motores:** "NEO" e "NEO2". O NEO2 é o mais realista, com franquia bem menor: 0,5 min no Starter e 10 min no Professional.
- **Editor:** cenas, conversa entre múltiplos avatares, imagens de IA, branching e quizzes (vídeo interativo), templates e Brand Kit.
- **Vertical:** [não verificado].
- **Tempo real:** não encontrei. O foco é interatividade com branching.
- **API:** REST com bearer token, `POST .../video-generation-jobs` e campo `webhook` na criação [oficial: docs e página de integração]. 360 min/ano no Professional, embora o alinhamento da tabela seja ambíguo.
- **Integrações:** LMS via SCORM, YouTube e Uqualio.
- **Segurança:** SOC 2 Type II, SSO e residência de dados na UE ou nos EUA (Enterprise). Marca d'água no plano gratuito.

**Fluxo do usuário:** cadastro grátis, sem cartão → "doc/PPT para vídeo" ou template → escolher avatar e voz → gerar → exportar MP4 ou SCORM.

**Diferenciais:** custo-benefício em L&D, SCORM, vídeos interativos e 3 clones de voz já no plano gratuito.

**Preços (página oficial, 23/10/2026)**
- **Starter:** grátis. 20 min NEO e 0,5 min NEO2 por mês, 15 avatares instantâneos e marca d'água.
- **Professional:** **US$ 59/mês no anual**, sem preço mensal publicado. 30 min NEO e 10 min NEO2, 20 avatares, sem marca d'água e até 3 editores (US$ 30 por editor extra).
- **Enterprise:** sob consulta.
- **Add-on:** 600 min NEO2 por US$ 1.500/ano.
- **Custo efetivo:** cerca de US$ 1,97/min no NEO e US$ 5,90/min no NEO2 (Professional anual), ou cerca de US$ 2,50/min no NEO2 com o add-on.

**Pontos fracos:** foco em treinamento e não em social; franquia baixa no motor realista; poucas reviews recentes lidas nesta coleta. Pela mídia especializada, os avatares ficam um pouco atrás da HeyGen em naturalidade [não verificado].

**Ideias para o produto contábil:** vídeo "interativo" com escolha do tipo "Você é MEI? Clique aqui", para onboarding de clientes do escritório, e a conversão de documentos em vídeo (circular de prazos fiscais virando vídeo).

---

### 2.7 DeepBrain AI (AI Studios)

**Público e proposta.** Empresa coreana. Vende vídeo com avatar (AI Studios), "AI Humans" para quiosques, bancos e TV (inclusive âncoras de telejornal) e Interactive Avatar. Foco corporativo e asiático, com uma base self-serve.

**Funcionalidades**
- **Clone:** "Custom avatar" feito de vídeo gravado por você, por webcam segundo terceiros, e Photo Avatar. Avatares personalizados: 1 no Free, 3 no Personal, 5 no Team e ilimitados no Enterprise. **Bloqueio automático de avatares parecidos com celebridades** [oficial: help]. **Não achei requisitos de footage nem fluxo de consentimento.**
- **Idiomas:** 150+ idiomas e sotaques de voz e dublagem para 73 idiomas, com lip-sync, nos planos pagos [oficial].
- **Editor:** templates, roteiro com ChatGPT, URL ou documento para vídeo, SRT, "generative credits" para imagem e vídeo por prompt.
- **Vertical:** [não verificado].
- **Tempo real:** Interactive Avatar com plano próprio: Free com 2 créditos e sessões de 10 min; Standard por **US$ 99/mês** com 100 créditos, LLM e TTS embutidos e 20 usuários simultâneos [oficial].
- **API:** associada ao **Enterprise** [3º: G2, Tavus]. No Interactive Standard há "acesso a sessões via API" [oficial]. Sem preço por minuto público.
- **Segurança:** bloqueio de celebridades; SAML/SSO no Enterprise.

**Fluxo do usuário:** cadastro grátis (3 vídeos/mês de 1 min em 720p) → template → avatar e voz → roteiro → exportar.

**Diferenciais:** **vídeos ilimitados** nos planos pagos (cobra por assento e não por minuto), dublagem generosa (120 min/mês no Personal) e 3 clones já no Personal.

**Preços (página oficial, aistudios.com, 23/10/2026)**
- **Free:** US$ 0.
- **Personal:** **US$ 24/mês**. Vídeos ilimitados de até 30 min, 1080p, 3 avatares personalizados e 120 min de dublagem.
- **Team:** **US$ 55 por assento/mês**. Até 60 min por vídeo, 4K e 5 avatares.
- **Enterprise:** sob consulta. Um comparativo de terceiros cita a partir de US$ 10 mil/ano.
- O anual tem 20% de desconto, mas o valor não aparece na página. Outras fontes citam US$ 29 e US$ 69, possivelmente o preço mensal sem desconto.

**Pontos fracos:** Trustpilot 3/5 com 228 reviews, quase todas de 2023, sobre clareza de pagamento e complexidade; Gartner 3,7 com 7 avaliações, citando processamento lento, configurações de câmera e recorte ruins na criação do avatar próprio e falta de pré-visualização; API só no Enterprise.

**Ideias para o produto contábil:** **preço fixo por escritório com vídeos ilimitados**, que é o modelo mais fácil de vender para contador; **pré-visualização** barata antes do render; e bloquear clones de pessoas públicas.

---

### 2.8 ElevenLabs (componente de voz)

**Papel:** a melhor opção de clone de voz e TTS multilíngue. Funciona como camada de voz das outras plataformas: Argil integra de forma nativa, e HeyGen e D-ID usam ou já usaram vozes ElevenLabs [não verificado em 2026].

- **Clonagem:**
  - **Instant Voice Cloning** a partir do plano Starter (cerca de 1 min de áudio [não verificado em 2026]).
  - **Professional Voice Cloning** a partir do Creator (1 clone; 3 no Scale; 10 no Business). Usa mais áudio de treino (dezenas de minutos recomendados) e **verificação de que a voz é sua** por leitura de "voice captcha" [não verificado em 2026].
- **pt-BR:** os modelos multilíngues suportam português e são o padrão de mercado em naturalidade [não verificado com teste cego].
- **Preços (página oficial, 23/10/2026):**

| Plano | Mensal | Créditos | TTS aproximado | Minuto extra | Clone |
|---|---|---|---|---|---|
| Free | US$ 0 | 10 mil | ~10 min | — | não comercial |
| Starter | US$ 6 | 30 mil | ~30 min | ~US$ 0,20 | instantâneo |
| Creator | US$ 22 | 121 mil | ~121 min | ~US$ 0,18 | 1 profissional |
| Pro | US$ 99 | 600 mil | ~600 min | ~US$ 0,17 | 1 profissional |
| Scale | US$ 299 | 1,8 mi | ~1.800 min | ~US$ 0,17 | 3 profissionais |
| Business | US$ 990 | 6 mi | ~6.000 min | ~US$ 0,17 | 10 profissionais |

- 1 crédito equivale a 1 caractere no TTS padrão; alguns modelos de API cobram de 0,5 a 1 crédito por caractere.
- **45 s de fala (cerca de 650 a 750 caracteres) custam cerca de US$ 0,13 a 0,15.**
- **Ideia para o produto:** separar a **voz (ElevenLabs PVC)** do **rosto (motor de avatar)**. A voz é o que o cliente do escritório reconhece primeiro, e o PVC em pt-BR tende a soar melhor que o TTS embutido dos geradores de avatar. Também permite trocar de fornecedor de vídeo sem perder a voz.

---

## 3. Matriz de funcionalidades

Legenda: ✅ = sim, confirmado em fonte oficial ou fonte confiável · ❌ = não oferece, ou não encontrei nenhum indício · ? = não consegui verificar · (3º) = só fonte de terceiros.

| Funcionalidade | HeyGen | Synthesia | Argil | Captions/Mirage | D-ID | Colossyan | DeepBrain | ElevenLabs |
|---|---|---|---|---|---|---|---|---|
| Clone por vídeo (twin) | ✅ | ✅ | ✅ no app; ❌ na API (descontinuado) | ✅ | ✅ | ✅ | ✅ | n/a |
| Clone por foto | ✅ | ✅ | ✅ | ✅ (selfie) | ✅ | ? | ✅ | n/a |
| Footage mínimo declarado | 15–30 s (mkt) / ~2 min (docs) | 1–5 min | 1–5 min (histórico) | ~10 s | ~1 min Express (2024) | ? | ? | ~1 min de áudio (IVC) ? |
| Vídeo de consentimento obrigatório | ✅ | ✅ | ✅ (histórico) | ? | ✅ | ? | ? | ✅ (PVC) ? |
| Consentimento via API | ✅ | ? | ❌ (removido) | ? | ✅ | ? | ? | ? |
| Avatares prontos (quantidade) | 700+ | 240+ | 100+ | ✅ (atores) | ✅ (~25–100+) | 300+ | ✅ | n/a |
| Clone de voz | ✅ | ✅ | ✅ + ElevenLabs | ✅ | ✅ (3º) | ✅ | ✅ | ✅ |
| pt-BR declarado | ✅ | ✅ | ? | ? | ✅ (3º) | ✅ | ✅ | ✅ |
| Qualidade pt-BR testada de forma independente | ? | ? | ? | ? | ? | ? | ? | ? |
| Controle de gestos e corpo | ? | ? | ✅ | ? | ? | ? | ? | n/a |
| Editor com templates | ✅ | ✅ | ✅ | ✅ | ✅ (simples) | ✅ | ✅ | n/a |
| Legendas automáticas | ✅ | ✅ | ✅ | ✅ (forte) | ? | ✅ | ✅ | n/a |
| B-roll automático | ? | ? | ✅ | ✅ | ? | ? | ✅ (generativo) | n/a |
| Formato vertical 9:16 | ✅ | ✅ | ✅ | ✅ | ? | ? | ? | n/a |
| Tradução/dublagem com lip-sync | ✅ | ✅ | ? | ✅ | ? | ✅ | ✅ | ✅ (só áudio) |
| Avatar interativo/tempo real | ✅ (LiveAvatar) | ✅ | ❌ | ❌ | ✅ (forte) | ❌ (branching) | ✅ | ✅ (agentes de voz) ? |
| API pública self-serve | ✅ | ✅ (cota) | ✅ | ✅ | ✅ | ✅ (Pro) | ❌ (Enterprise) | ✅ |
| Webhooks | ✅ | ✅ | ✅ | ? | ✅ (3º) | ✅ | ? | ✅ ? |
| Estimativa de custo via API | ❌ ? | ✅ (Billing API, saldo) | ✅ (`estimate`) | ❌ ? | ❌ ? | ? | ? | ? |
| Limites de API documentados | ✅ (10 simultâneos) | ✅ (página da Video API) | ? | ? | ❌ | ? | ? | ✅ ? |
| SCORM/LMS | ✅ (Business) | ✅ | ❌ | ❌ | ❌ | ✅ | ✅ | n/a |
| SSO/SAML | ✅ | ✅ | ✅ (Enterprise) | ? | ? | ✅ | ✅ | ? |
| C2PA/Content Credentials automático | ? | ✅ | ? | ? | ? | ? | ? | ? |
| Rótulo visível de IA embutido | ❌ (só recomenda) | ✅ (opcional) | ? | ? | ✅ (marca "AI" no Pro) | ? | ? | n/a |
| Marca d'água no plano gratuito | ✅ | ✅ | ? | ? | ✅ | ✅ | ? | n/a |
| Bloqueio de celebridades e pessoas públicas | ? | ✅ (moderação) | ? | ? | ? | ? | ✅ | ? |
| Remoção do clone a pedido | ✅ | ? | ? | ? | ? | ? | ? | ? |
| Vídeos ilimitados a preço fixo | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | n/a |

---

## 4. Custo estimado de um vídeo de 45 segundos

Premissas: vídeo de 45 s com clone próprio (twin), sem tradução e com uso integral da franquia do plano. É o custo **marginal** por vídeo. A conversão usa R$ 5,50/US$ (premissa) e não inclui IOF. "Plano" significa o produto web; "API" significa o uso programático.

| Ferramenta / modo | Base de cálculo | US$ por vídeo de 45 s | R$ aprox. | Confiança |
|---|---|---|---|---|
| HeyGen API — Avatar III Digital Twin | US$ 0,60/min | **0,45** | 2,50 | oficial (19/10/2026) |
| HeyGen API — Avatar IV Digital Twin | US$ 4,83/min | **3,62** | 19,90 | oficial |
| HeyGen API — Avatar V Digital Twin | US$ 7,20/min | **5,40** | 29,70 | oficial |
| HeyGen API — criação do twin (uma vez) | US$ 2,13/chamada | (2,13 único) | 11,70 | oficial |
| HeyGen Studio — Creator (Avatar IV, se 20 cr/min) | US$ 29 ÷ 600 cr × 15 cr | ~0,73 | ~4,00 | 3º (consumo por min não confirmado) |
| Synthesia — Starter mensal | US$ 29 ÷ 1.250 cr × 75 cr | **1,74** | 9,60 | oficial (100 cr/min) |
| Synthesia — Pro anual | US$ 64 ÷ 6.000 cr × 75 cr | **0,80** | 4,40 | oficial |
| Synthesia — dentro dos 10 min grátis/mês | — | 0 (até ~13 vídeos/mês) | 0 | oficial |
| Argil — plano antigo Classic (25 min por US$ 39) | US$ 1,56/min | ~1,17 | ~6,40 | 3º e snippet antigo; plano mudou |
| Argil — API (120 cr de vídeo + 15 cr de voz) | preço do crédito não confirmado | **?** (~1,2–3,3) | ? | API oficial; preço do crédito desconhecido |
| Captions/Mirage — API Avatar X | US$ 0,15/s, blocos de 6 s → 48 s | **7,20** | 39,60 | oficial |
| Captions — app (plano Max) | créditos por minuto não publicados | ? | ? | — |
| D-ID — Studio Pro (marca "AI") | US$ 29 ÷ 15 min | 1,45 | 8,00 | 3º (out/2026) |
| D-ID — API Launch | US$ 35 ÷ 45 min | **0,58** | 3,20 | 3º (out/2026) |
| D-ID — API Scale (logo próprio) | US$ 138,60 ÷ 200 min | 0,52 | 2,90 | 3º |
| Colossyan — Professional anual, NEO | US$ 59 ÷ 30 min | 1,48 | 8,10 | oficial |
| Colossyan — Professional anual, NEO2 | US$ 59 ÷ 10 min | 4,43 | 24,40 | oficial |
| DeepBrain — Personal (vídeos ilimitados) | US$ 24/mês fixo | ~0 marginal (US$ 0,24 se forem 100 vídeos/mês) | ~1,30 | oficial (pode haver uso justo não lido) |
| **+ voz ElevenLabs** (se usada à parte) | ~US$ 0,17–0,20/min | +0,13–0,15 | +0,80 | oficial |

**Leitura:** para automação por API com clone realista, o menor custo confirmado é o **HeyGen Avatar III** (US$ 0,45, com qualidade inferior), seguido de **D-ID** (cerca de US$ 0,55, com realismo menor e informação de terceiros). Na faixa "realismo alto", Avatar IV custa US$ 3,62, Avatar V US$ 5,40 e Mirage US$ 7,20. Para uso manual (sócio ou equipe no app), **Synthesia Pro anual** (US$ 0,80, mais os 10 min grátis) e **DeepBrain Personal** (preço fixo) são os mais baratos por vídeo. Mas a Synthesia não é otimizada para social, e a DeepBrain tem reviews fracas.

---

## 5. Padrões de mercado e lacunas (síntese para o produto)

**As 10 funcionalidades mais valiosas desta frente**
1. Clone em segundos, pelo celular (Captions, HeyGen Avatar V).
2. Consentimento por vídeo com verificação de que o rosto é o mesmo e uma frase lida (HeyGen, Synthesia, D-ID).
3. Clone de voz separado e de alta qualidade, com a opção de trazer a própria conta ElevenLabs (Argil).
4. Edição automática para vídeo curto: legenda animada, b-roll, ganchos, vertical e contato visual (Argil, Captions).
5. Tradução e dublagem com lip-sync e revisão do roteiro traduzido (HeyGen Proofread, Synthesia com glossário).
6. API assíncrona com webhooks de treino e de render (Argil, HeyGen, Synthesia).
7. Estimativa de custo antes de renderizar (Argil `videos.estimate`).
8. Cobrar só o trecho regenerado (Synthesia).
9. C2PA e rótulo de IA automáticos (Synthesia).
10. Avatar interativo em tempo real para o site (D-ID, HeyGen LiveAvatar, Synthesia, DeepBrain).

**Os 5 principais pontos fracos do mercado**
1. **Preço opaco em créditos**: unidades mudam, o consumo por motor não aparece e a geração que falha é cobrada (HeyGen, Argil, D-ID).
2. **Suporte e cobrança ruins**: renovações não autorizadas, reembolsos recusados e migrações forçadas (Trustpilot de HeyGen, Captions e DeepBrain).
3. **Qualidade em pt-BR não comprovada**: não há benchmark independente, e há pouco controle de cadência e pronúncia de termos técnicos.
4. **Consentimento frágil no avatar por foto e pouca rotulagem de IA**: só a Synthesia aplica C2PA por padrão.
5. **Foco desalinhado com o pequeno escritório**: as ferramentas corporativas são caras e pesadas (Synthesia, Colossyan), e as de creator são instáveis e não conhecem o contexto contábil e fiscal.

**Oportunidade específica para escritórios de contabilidade**
- **Pauta pronta:** calendário fiscal brasileiro (DAS, DCTFWeb, IRPF, eSocial, Reforma Tributária com IBS e CBS) gerando roteiros semanais. O sócio só aprova.
- **Compliance contábil embutido:**
  - Checagem do roteiro contra promessas proibidas pelo Código de Ética do contador (NBC PG 01). É preciso confirmar com o CFC as regras vigentes de publicidade.
  - Rótulo "conteúdo gerado com IA".
  - Termo de autorização de uso de imagem e voz alinhado à LGPD, com dado biométrico tratado como **dado pessoal sensível** (art. 5º, II, e art. 11). Já existe um rascunho em `docs/termo_autorizacao_imagem_voz.md`.
- **Arquitetura de custo:** voz por ElevenLabs PVC e rosto por um motor barato para rascunho (do tipo Avatar III ou D-ID), com motor premium opcional. Preço fixo mensal por escritório, cobrado em reais com nota fiscal brasileira, que nenhuma das ferramentas internacionais emite.
- **Distribuição:** entrega pelo WhatsApp ("seu vídeo está pronto, aprova?") e publicação em Instagram e LinkedIn. Argil e a maioria dos concorrentes não publicam nas redes.

---

## 6. O que não consegui verificar

- **Qualidade real em pt-BR** (sotaque, prosódia, pronúncia de siglas) em todas as ferramentas. Recomendo um teste cego próprio com 3 roteiros contábeis.
- **Preços atuais da Argil** (página em JS, cobrança em EUR e unidades de crédito conflitantes) e o preço do crédito para a API.
- **Preços oficiais da D-ID** (a página oficial é renderizada em JS). Usei a Toolsurf (out/2026) e cruzei com outros terceiros.
- **Créditos por minuto do AI Twin no app Captions** e no HeyGen Studio, por motor.
- **Requisitos de footage e consentimento** de Colossyan, DeepBrain e D-ID em 2026 (os dados da D-ID são de 2024).
- **C2PA e rótulo de IA** em HeyGen, Argil, Captions, D-ID, Colossyan e DeepBrain: não encontrei nem a confirmação nem a negação.
- Limites de requisição de Argil, Mirage e D-ID.
- O status atual do PL 2338/2023 (marco legal de IA no Brasil) e das regras do CFC para publicidade com IA.
- A cotação do dólar: R$ 5,50 é premissa.

---

## 7. Fontes

**HeyGen**
- Preços: https://www.heygen.com/pricing
- API pricing (help center, atualizado em 19/10/2026): https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained
- Consentimento de avatar (API): https://developers.heygen.com/docs/avatar-consent
- Consentimento e controles de marca (blog, 20/10/2026): https://www.heygen.com/blog/ai-avatar-consent-brand-controls
- Como criar digital twin: https://www.heygen.com/blog/how-to-create-digital-twin-avatar
- Avatar V / Seedance: https://www.heygen.com/blog/introducing-seedance-2-and-heygen
- Trustpilot: https://www.trustpilot.com/review/heygen.com?page=2
- Creatify (3º, concorrente): https://creatify.ai/blog/heygen-pricing-(2026)-plans-and-what-you-ll-actually-pay
- Anam (3º, concorrente): https://anam.ai/blog/heygen-pricing

**Synthesia**
- Preços (inclui rate card da API): https://www.synthesia.io/pricing
- API docs: https://docs.synthesia.io/reference/introduction
- Personal avatar: https://help.synthesia.io/en/articles/9453224-how-do-i-create-my-personal-avatar
- Footage pré-gravado: https://help.synthesia.io/en/articles/9776564-how-do-i-create-a-personal-avatar-using-pre-recorded-footage
- Studio avatar: https://help.synthesia.io/en/articles/8438686-how-do-i-create-a-studio-avatar
- Moderação de Photo Avatar: https://help.synthesia.io/en/articles/13846500-photo-avatars-content-moderation
- C2PA e rótulos de IA: https://www.synthesia.io/updates/stay-compliant-with-content-credentials-and-ai-labels
- Código de prática da UE: https://www.synthesia.io/post/supporting-the-european-code-of-practice-on-ai-generated-content
- Capterra: https://www.capterra.com/p/198045/Synthesia/reviews/
- Termos e privacidade (resumo de 3º): https://conductatlas.com/platform/synthesia/synthesia-terms-of-service/custom-avatar-consent-requirement/

**Argil**
- Preços: https://www.argil.ai/pricing
- API pricing: https://docs.argil.ai/resources/api-pricings.md
- Índice da API: https://docs.argil.ai/llms.txt
- Avatar por vídeo (descontinuado): https://docs.argil.ai/api-reference/endpoint/avatars.create.video.md
- Blog de preços (09/02/2026): https://www.argil.ai/blog/how-do-leading-ai-avatar-services-compare-on-pricing-in-2026
- Review Kompozy (3º): https://kompozy.io/reviews/argil

**Captions / Mirage**
- Preços: https://www.captions.ai/pricing
- API pricing: https://captions.ai/help/docs/api/pricing.md e https://help.mirage.app/docs/api/pricing
- AI Twin: https://www.captions.ai/features/create-ai-twin
- Trustpilot: https://ca.trustpilot.com/review/captions.ai e https://dk.trustpilot.com/review/captions.ai?page=8

**D-ID**
- Preços (JS, não lido): https://www.d-id.com/pricing/ (Studio: /pricing/studio/, API: /pricing/api/)
- Toolsurf (3º, out/2026): https://www.toolsurf.com/d-id-pricing-2026/
- Premium+ Avatars: https://docs.d-id.com/reference/premium-avatars-overview
- Agents SDK: https://docs.d-id.com/reference/agents-sdk-overview
- TechCrunch (31/10/2024): https://techcrunch.com/2024/10/31/d-id-launches-new-high-quality-avatars-capable-of-real-time-conversations
- Fórum (limites e 429): https://docs.d-id.com/discuss/66543b88c039a3000f82b7d3

**Colossyan**
- Preços: https://www.colossyan.com/pricing
- API: https://www.colossyan.com/features/api/ e https://docs.colossyan.com/

**DeepBrain AI / AI Studios**
- Preços: https://aistudios.com/pricing
- Celebridades: https://help.deepbrain.io/en/articles/10347478-can-i-create-a-custom-avatar-of-a-celebrity
- Custom avatars: https://help.deepbrain.io/en/articles/10348432-what-are-custom-avatars
- Trustpilot: https://au.trustpilot.com/review/deepbrain.io?page=9
- Gartner: https://www.gartner.com/reviews/product/deepbrain-ai-studios
- Tavus (3º, concorrente): https://www.tavus.io/blog/deepbrain-ai-review-is-it-worth-it-enterprise-video
- Pricingsaas (2026 Q2): https://pricingsaas.com/companies/deepbrain/diffs/2026Q2

**ElevenLabs**
- Preços: https://elevenlabs.io/pricing

**Contexto regulatório**
- C2PA: https://c2pa.org/a-new-implementation-guide-for-content-credentials/
- Limitações do C2PA (3º, abr/2026): https://www.trustinsights.ai/blog/2026/04/ai-watermarks/
