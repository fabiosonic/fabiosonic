# 04 — Edição e automação de vídeos curtos (benchmark funcional)

> Pesquisa feita em **23/10/2026** só com informação pública: sites oficiais, páginas de preço, documentação de API, centrais de ajuda, Trustpilot/G2/Capterra e artigos de review. Não acessei áreas logadas nem testei os produtos por dentro.
>
> **Como ler a confiabilidade:** **[O]** = fonte oficial do fornecedor; **[T]** = terceiro (review/blog, muitas vezes de concorrente ou afiliado); **[?]** = não verificado ou fontes divergentes. Preços em USD, salvo indicação. Esses preços mudam com frequência e várias páginas de preço são renderizadas por JavaScript. Por isso parte dos números veio incompleta e está marcada.

---

## 1. Resumo executivo

- O mercado se divide em três arquétipos:
  1. **Clippers de vídeo longo** (Opus Clip, Vizard, Klap): o usuário sobe uma live, podcast ou palestra e recebe de 10 a 30 clipes verticais com legenda e uma nota de "viralidade".
  2. **Editores de vídeo curto já gravado** (Submagic, CapCut): legenda animada, zoom, b-roll, remoção de silêncio e templates.
  3. **Geradores do zero** (AutoShorts.ai e, mais recentemente, Agent Opus, AI Studio do Vizard, Pippit, antigo CapCut Commerce Pro, e AI Actors do Submagic): tema ou roteiro → vídeo com voz sintética ou avatar → postagem automática.
- O núcleo técnico é bem conhecido e reproduzível: transcrição com tempo por palavra, seleção de trechos por LLM, detecção e rastreamento de rosto para recorte 9:16, legenda ASS animada e FFmpeg. O que diferencia os produtos é a **qualidade da seleção** (contexto, gancho e final), o **acabamento das legendas** e a **conveniência da publicação**.
- Reclamações que se repetem no mercado: o corte não entende contexto (corta antes da conclusão), a "virality score" é pouco confiável, o agendador falha, há créditos ou cobrança confusos e é difícil cancelar. Fora isso, os produtos são **genéricos**: não existe nada pensado para conteúdo regulado (contábil/fiscal) nem para checar a exatidão técnica do que é dito.

---

## 2. Ferramentas

### 2.1 Opus Clip (opus.pro)

**Público e proposta.** Criadores, podcasters, agências e marketing B2B que querem transformar vídeo longo em muitos shorts "em 1 clique". O site diz ter "20M+ creators and businesses" [O].

**Funcionalidades**
- **Corte e seleção:**
  - O modelo **ClipAnything** encontra momentos a partir de pistas visuais, de áudio e de sentimento, e não só da transcrição [O].
  - Pelo preço oficial, o plano Free corta só por fala ("spoken words"). O Pro acrescenta objetos visuais, som, emoção e curadoria por gênero [O].
  - Tem **clipping por prompt**: o usuário descreve o momento desejado em linguagem natural [O].
- **Virality Score:**
  - Nota de **0 a 99** com base em quatro dimensões: **Hook** (o começo prende?), **Flow** (a progressão é lógica e o final satisfaz?), **Value** (entrega valor ou emoção?) e **Trend** (está alinhado a tendências?) [O, help.opus.pro].
  - No ClipAnything, também avalia se o clipe é relevante para o prompt.
  - Clipes vêm ordenados pela nota, e o método de ponderação não é divulgado. Só aparece nos planos Starter e Pro [O].
- **Reenquadramento:**
  - O **ReframeAnything** faz 9:16 no Free e Starter, e 9:16, 1:1 e 16:9 no Pro.
  - O **rastreamento de objeto em movimento** fica só no Pro. Dá para indicar manualmente o que deve ser rastreado [O].
- **Legendas:**
  - Automáticas, com ">97% de precisão" segundo o fornecedor, e editáveis [O].
  - Fonte customizada só no Pro (até 2 fontes). Cores por falante aparecem como "coming soon" no Business [O].
- **B-roll:**
  - Starter: 3 imagens de IA e 3 stocks por mês.
  - Pro: 50 imagens de IA por dia, stock ilimitado e **B-roll de vídeo gerado por IA** [O].
- **Templates de marca:** 1 no Free e Starter, até 4 no Pro e custom no Business. Incluem fontes, cores, logo e intro/outro [O].
- **Geração do zero:** o **Agent Opus** recebe prompt, roteiro, outline, URL de blog ou áudio. Sub-agentes cuidam de pesquisa, roteiro, storyboard, voz e edição, e o resultado tem avatar, voz e motion graphics [O páginas /agent; T mer.vin, jul/2026]. Não encontrei data oficial de lançamento.
- **Agendamento:** agendador social e várias contas por plataforma no Pro. O Starter publica em YouTube Shorts, TikTok e Instagram [O].
- **API:**
  - Fluxo:
    1. `POST /api/upload-links` para upload resumível.
    2. `POST /api/clip-projects` com `videoUrl`, curadoria e brand template.
    3. `GET /api/exportable-clips?q=findByProjectId`, com headers `Authorization` e `x-opus-org-id`.
  - Disponível no Pro (Beta) e Business [O].
  - Também tem **servidor MCP** (`api.opus.pro/api/mcp`) e conector para Claude, além de Zapier [O].
- **Colaboração:** team workspace no Pro (2 assentos por pacote, até 4) e assentos ilimitados no Business [O].
- **Idiomas:** cerca de 25, incluindo português [O].
- **Fontes de vídeo:** upload, YouTube, Google Drive, Vimeo, Zoom, Twitch etc. [O].

**Fluxo do usuário:**
1. Colar o link ou subir o arquivo.
2. Escolher modelo, faixa de duração dos clipes, gênero, prompt opcional e template.
3. Esperar o processamento.
4. Ver a lista de clipes ordenada pela nota.
5. Editar no editor (texto, legenda, reframe, b-roll).
6. Exportar ou agendar a postagem.

**Diferenciais:**
- É a marca líder da categoria.
- A seleção é multimodal.
- A virality score é explicada em 4 eixos.
- Tem API, MCP e agente de geração do zero.

**Planos e preços** (fonte: opus.pro/pricing, consultado em 23/10/2026 [O]):
- Free: US$ 0, com marca d'água, export até 1080p e arquivos guardados por 3 dias.
- **Starter: US$ 15/mês.**
- **Pro: US$ 29/mês**, com "até 300 créditos/mês" e storage de 100 GB.
- Business: sob consulta.
- Preço anual e créditos por plano não apareceram na leitura. O site cita 60 min/mês no Free e trial Pro de 7 dias com 90 min. 1 crédito equivale a 1 minuto de vídeo enviado [T eesel].
- Créditos mensais expiram em 60 dias e os anuais em 13 meses [T smartremotegigs] [?].

**Pontos fracos e reclamações** [T eesel, smartremotegigs, Trustpilot]:
- Corta antes do punchline, perde contexto e ironia.
- A nota de viralidade não bate com o desempenho real: clipes com nota baixa às vezes performam melhor.
- Legendas com erro e difíceis de editar.
- O B-roll de IA às vezes insere imagem estática no lugar de vídeo.
- O agendador falha e desconecta contas.
- Processamento trava ou falha "silenciosamente".
- Cobrança depois do cancelamento, cancelamento confuso e suporte automatizado.
- Funções essenciais (B-roll de vídeo, agendador, API) presas no Pro.

**Ideias para o produto contábil:**
- Rubrica de nota explicável em eixos. Para contabilidade, trocar "Trend" por **"Calendário fiscal"** (prazo de IRPF, DCTFWeb, reforma tributária) e acrescentar **"Exatidão técnica"**.
- Clipping por prompt, por exemplo "todos os trechos sobre Simples Nacional".
- Brand template por escritório.
- API e MCP desde o início.

---

### 2.2 Submagic (submagic.co)

**Público e proposta.** Criadores e empresas que já gravam vídeos curtos (talking head) e querem o "acabamento viral": legendas animadas, zooms, b-roll, cortes de silêncio. Também tem Magic Clips para vídeo longo. O site diz ter "4M+ businesses" e nota 4,8 no Trustpilot e 4,9 no G2 [O].

**Funcionalidades** [O, home e pricing]:
- **Legendas:**
  - Em **123 idiomas**, com "99% de precisão" segundo o fornecedor.
  - Estilos de legenda com palavra em destaque e emojis. Templates padrão no Starter e premium no Pro e Business.
  - Templates customizados: 3 no Pro e 10 ou ilimitados no Business (a página se contradiz).
  - **Vocabulário customizado** só no Business. É útil para jargão como "DCTFWeb" ou "eSocial".
- **Magic Clips:** gera vários clipes a partir de um vídeo longo. A página não detalha o critério de seleção.
- **AI Auto Edit / edição por texto:** cortar, aparar e remover silêncio editando a transcrição.
- **Remoção de silêncio e de "bad takes":** a partir do Pro. Na interface, o usuário escolhe a agressividade do corte ("Slower" remove menos) [O, care.submagic.co].
- **Auto-zoom ("Magic Zooms")** e **B-roll automático ("Magic B-rolls")**:
  - B-roll padrão no Starter, stock premium no Pro e "movie clips" no Business.
  - Na API, aparecem como flags booleanas (`magicZooms: true`, `magicBrolls: true`) [O, página /api].
- **Áudio:** música de fundo, efeitos sonoros e **clean audio** (redução de ruído) a partir do Pro.
- **Outros:**
  - **AI Eye Contact** (corrige o olhar para a câmera) e **AI Video Translator**.
  - Auto-descrição para o post e gerador de hook como ferramenta gratuita.
  - **AI Actors Studio**, com vídeos de avatar de IA.
- **Publicação:** agendamento e publicação com analytics. Pro: 1 perfil por rede; Business: 3 perfis.
- **API:**
  - `POST /v1/projects` com `x-api-key` e campos `title`, `language`, `videoUrl`, `templateName`, `dictionary`, `magicZooms`, `magicBrolls` [O].
  - Limite de cerca de 30 projetos por hora [T] [?].
  - Pacotes extras de minutos de API: 250 min por US$ 57, e de 5.000 a 10.000 min por US$ 0,10/min [O].
- **Colaboração:** 1 usuário no Starter, 3 no Pro e ilimitados no Business. Workspace compartilhado [O].

**Fluxo:**
1. Subir o vídeo (até 2, 5 ou 30 min conforme o plano).
2. Escolher idioma e template de legenda.
3. A IA transcreve e aplica os efeitos.
4. Ajustar no editor por texto: remover silêncios, trocar b-roll, mover zoom.
5. Exportar em 1080p, ou 4K 60fps no Business, ou agendar.

**Diferenciais:**
- É a referência em **estética de legenda** e "auto edit" de talking head.
- A API expõe os efeitos como flags simples.
- Tem dicionário customizado.
- Mostra preço em **BRL** (R$ 79, 159 e 279 por mês) [O].

**Planos e preços** (submagic.co/pricing, consultado em 23/10/2026 [O]):

| Plano | Mensal | Anual (por mês) | Créditos | Vídeos | Duração máx. | Export | Usuários |
|---|---|---|---|---|---|---|---|
| Starter | US$ 19 | US$ 12 | 45 | 15 | 2 min | 1080p30 | 1 |
| Pro | US$ 39 | US$ 23 | 120 | 40 | 5 min | 1080p30 (2K em uma tabela) | 3 |
| Business | US$ 69 | US$ 41 | 300 | 100 | 30 min | 4K60 | ilimitado |

O plano Custom inclui SSO. A página oficial tem **inconsistências internas** (minutos de API no Starter, número de templates e logo).

**Pontos fracos** [Trustpilot 2026]:
- Não há período de carência para reembolso.
- Instabilidade em alguns relatos: dessincronia de áudio e vídeo, e eye contact que não funciona.
- Experiência ruim no celular.
- Limite de duração baixo nos planos de entrada, o que torna os Magic Clips pouco úteis para lives longas sem o Business.
- No geral, as avaliações são boas e o suporte é elogiado.

**Ideias para o produto contábil:**
- Dicionário de termos contábeis e fiscais aplicado à transcrição.
- Presets de "auto edit" com flags simples (zoom, b-roll, silêncio).
- Eye contact para o sócio que lê roteiro.
- Preço em reais.

---

### 2.3 CapCut (capcut.com), com Pippit (antigo CapCut Commerce Pro)

**Público e proposta.** Do criador amador ao social media profissional. É um editor completo (mobile, web e desktop) da ByteDance, com muitos recursos de IA e um enorme acervo de templates ligados a tendências do TikTok.

**Funcionalidades:**
- **Corte de vídeo longo:**
  - A ferramenta "Long video to shorts" tem a opção **"AI Highlights"**, que identifica momentos-chave por padrões de fala.
  - Faz 16:9→9:16 com **rastreamento automático do sujeito** e legenda por clipe com destaque de palavras [O, /tools/long-video-to-shorts].
  - Um guia antigo (2024) fala em 60 min/mês de conversão no free e mais 240 no Pro [O, datado] [?].
  - **Não encontrei virality score** documentada.
- **Legendas:** auto captions em vários idiomas, com templates de legenda e karaokê. No free, até ~10 min por vídeo [T vidpros, mai/2026].
- **Edição com IA:**
  - AI Auto-Edit (5 usos/mês no free), remoção de fundo, upscaling e motion/camera tracking (Pro).
  - Redução de ruído, melhoria de voz e remoção de pessoas ou texto (inpainting) [O e T].
- **Voz e avatar:**
  - TTS com várias vozes e avatares no "Video Studio", onde se monta um vídeo a partir de um chat [O].
  - Geração de imagem e vídeo por IA.
- **Templates:** a maior biblioteca do mercado, com templates "de tendência" que se preenchem com mídia própria. Muitos são marcados como Pro e geram marca d'água no free [T].
- **Pippit (antigo CapCut Commerce Pro):** `commercepro.capcut.com` redireciona (301) para `pippit.ai` [verificado].
  - Faz **"Anything to Video"** (link de produto, arquivo ou mídia → vídeos) [O].
  - Tem avatares digitais e **avatar "gêmeo" a partir de foto**, voz customizada, talking photo e roteirista de IA.
  - Inclui templates, **agendamento de posts**, publicação e **analytics** [O]. Não vi preço.
- **Colaboração:** existe plano Team/Teams, por volta de US$ 24,99 por assento [T] [?].
- **API:** **não encontrei API pública** de edição do CapCut para terceiros.

**Fluxo:**
1. Importar a mídia.
2. Usar o editor de timeline, ou um template, ou "long video to shorts".
3. Aplicar auto captions e efeitos.
4. Exportar ou postar no TikTok, onde a integração é nativa.

**Diferenciais:** gratuito ou barato, editor completo, ecossistema TikTok, templates de tendência, desktop potente e avatar gêmeo no Pippit.

**Planos e preços** [T]:
- **Não consegui ler a página oficial de preços.** O preço varia por região, e o Brasil costuma pagar menos [T vidpros].
- Em 2026, os terceiros dizem que o antigo Pro de ~US$ 9,99 virou **Standard** e o novo **Pro custa ~US$ 19,99/mês ou US$ 179,99/ano**, com 1.200 pontos de IA e 1 TB de nuvem. Outra fonte fala em 100 GB [T eesel, bigvu, vidpros] [?].
- Pacotes extras de créditos de IA custam de US$ 4,99 a US$ 19,99 [T].

**Pontos fracos:**
- **Termos de Serviço de 12/06/2025:** licença ampla, perpétua, irrevogável e sem royalties sobre o conteúdo enviado, que pode incluir uso de rosto e voz em material promocional. Isso gerou críticas de juristas sobre LGPD/GDPR [T journalism.co.uk, 2b-advice, techloy].
  - É um **risco relevante para um sócio de escritório que vai clonar rosto e voz**.
- Paywall crescente: recursos que eram grátis viraram Pro, e há marca d'água em templates Pro.
- Licença comercial limitada no free [T].
- Incerteza regulatória da ByteDance em alguns mercados.
- Sem API e pouco feito para automação em lote.

**Ideias para o produto contábil:**
- Biblioteca de templates por "tipo de conteúdo contábil" (alerta de prazo, mito × verdade, "3 erros no MEI").
- Avatar gêmeo a partir de pouco material.
- **Diferenciar-se na governança da imagem e voz do sócio**: consentimento explícito, sem licença de uso promocional e dados no Brasil.

---

### 2.4 Vizard (vizard.ai)

**Público e proposta.** Criadores, podcasts, educadores e times de marketing. É um clipper de vídeo longo com editor por texto e, agora, o **Vizard Agent**. O site diz ter "10M+ creators" [O].

**Funcionalidades:**
- **Corte e seleção:**
  - AI clipping com "30+ clips in one click" [O].
  - Usa uma **viral score**, documentada por terceiros como probabilidade de "trending". Reviews dizem que é inconsistente [T].
  - O Vizard Agent tem **22 templates** de fluxo (podcast clips, tutorial, explainer, trailer...) [O].
- **Reenquadramento:** auto reframe que mantém o sujeito centralizado e troca de proporção em 1 clique [O]. A home cita algo vago como "corta falantes", sem detalhar a detecção de falante.
- **Legendas:** auto subtitling, AI emoji, AI highlight keywords e tradução de legenda para **100+ idiomas**. Download de transcrição em TXT (free) e SRT (pagos) [O].
- **Edição:** edição por texto (apagar texto corta o vídeo), timeline com precisão de segundos e remoção de bad takes [O].
- **B-roll:** "AI B-rolls", que insere stock automaticamente durante a geração [O/T].
- **Templates de marca:** brand templates, brand kit, fontes customizadas e outros customizados. O brand kit fica no Business [O].
- **Geração do zero:** AI Studio com gerador **Seedance** (modelo de vídeo da ByteDance) [O].
- **Texto do post:** sugestão de legenda e hashtags para o post [O].
- **Agendamento:** agendamento social com 1, 6 ou 20 contas conforme o plano [O].
- **API:** limites de taxa por plano: Free 1/min e 10/h, Creator 3/min e 20/h, Business 10/min e 60/h [O].
- **Colaboração:** Team Workspace com visualização em tempo real, link de preview para cliente e assentos extras (Business) [O]. É interessante para escritório que aprova com o sócio.

**Fluxo:**
1. Colar o link ou fazer upload (até 600 min e 30 GB nos pagos).
2. Escolher o template do agente ou o clipping padrão.
3. Revisar os clipes e as notas.
4. Editar por texto.
5. Aplicar brand template.
6. Agendar.

**Diferenciais:**
- Limites generosos de upload (10 h e 4K).
- Link de preview para cliente.
- Tradução de legenda para 100+ idiomas.
- Agente com templates por tipo de conteúdo.

**Planos e preços** (vizard.ai/pricing, 23/10/2026 [O]):
- Free: 60 créditos/mês (1 crédito = 1 minuto enviado), upload de até 60 min, export em 720p, marca d'água e storage de 3 dias.
- Creator e Business: "a partir de 600" créditos/mês e de 7.200 a 74.400 créditos/ano, com 50% de desconto no anual.
- **Os valores em dólar apareceram ilegíveis ("$0") na página oficial.**
- Terceiros: **Creator ~US$ 29/mês, Business ~US$ 39/mês** e anual ~US$ 14,50 a 23/mês [T Capterra, vantaige, zoftwarehub] [?].

**Pontos fracos** [T]:
- Viral score inconsistente.
- Seleção com "miss rate" estimada em 30–40%: começa no meio de um pensamento ou termina antes da conclusão [T fluxnote, número não verificado].
- Estilos de legenda básicos e posicionamento da legenda pouco flexível [G2].
- O free posta em só uma rede.
- Avaliações gerais boas: G2 4,7 e Capterra 4,9 com 438 reviews.

**Ideias para o produto contábil:**
- **Link de aprovação para o sócio**, com comentário por clipe.
- Exportar SRT.
- Templates de agente por formato ("corte de live de IRPF", "explicação de norma").
- Limites altos para lives longas.

---

### 2.5 Klap (klap.app)

**Público e proposta.** Criadores e pequenas equipes que querem muitos clipes com o mínimo de esforço e publicação direta. O site diz ter "3.5M creators" e "8.5M clips" [O].

**Funcionalidades** [O, home e docs]:
- **Corte:** a IA escolhe os "melhores tópicos" do vídeo. A regra prática é de **~5 clipes por minuto de vídeo** (heurística citada pelo próprio site).
  - Cada clipe recebe uma **virality score**.
- **Reenquadramento:**
  - **AI Reframe 2** analisa a cena e aplica layouts como **Split Screen** (duas pessoas), **Screencast** (tela + rosto) e **Gaming**.
  - O reconhecimento facial mantém o sujeito em quadro.
- **Legendas:** em **52 idiomas**, com sugestão de legenda do post. Customização de fontes, cores, logo e enquadramento.
- **Publicação:** compartilhamento e agendamento direto para TikTok, YouTube, Instagram e **LinkedIn**. Contas sociais ilimitadas e analytics em todos os planos.
- **API:**
  - Organizada em Tasks, Projects e Exports.
  - Cobrança por operação: **Video Input US$ 0,44, Generate Short US$ 0,32 e Export US$ 0,48** [O, docs.klap.app/pricing].
- **Integrações:** **servidor MCP**, Zapier, Make e **n8n** [O].
- **Não mencionados:** b-roll, dublagem, emojis, templates de marca salvos e recursos de equipe detalhados.

**Fluxo:**
1. Colar o link do YouTube ou fazer upload.
2. A IA gera os clipes já reenquadrados e legendados.
3. Ajustar no editor.
4. Publicar ou agendar. O trial gera clipes, mas download e postagem exigem assinatura.

**Diferenciais:**
- Layouts inteligentes por tipo de cena (split screen para entrevista e screencast para tela + webcam).
- LinkedIn nativo, que é relevante para B2B.
- API com preço por operação, transparente.
- Integração n8n e MCP.

**Planos e preços** (klap.app/pricing, 23/10/2026 [O], só a cobrança anual apareceu):
- **Basic: US$ 14/mês**, 100 clipes/mês, para indivíduos.
- **Pro: US$ 39/mês**, 300 clipes/mês, o mais popular.
- **Pro+: US$ 94/mês**, 1.000 clipes/mês, para times.
- O anual traz "economia de 50%". O preço mensal não apareceu, e a home cita "Klap Pro US$ 29/mês", o que diverge [?].

**Pontos fracos** [Trustpilot, TrustScore ~3/5 com 30 reviews no ca.trustpilot; T]:
- Cobrança e cancelamento: relatos de não achar opção de cancelar e de trial que vira paywall na hora de postar.
- Legendas desalinhadas e difíceis de ajustar manualmente.
- Suporte humano lento.
- Clipes "precisam de um retoque" antes de publicar.

**Ideias para o produto contábil:**
- Detectar o layout da cena: palestra com slide vira screencast, entrevista com convidado vira split screen.
- Publicação nativa no LinkedIn, que é o canal B2B de escritório.
- Cobrança por operação para a API e os parceiros.
- n8n para escritórios que já automatizam.

---

### 2.6 AutoShorts.ai (autoshorts.ai)

**Público e proposta.** Quem quer **canais "faceless"** que crescem no automático ("grow while you sleep"). O usuário escolhe um tema e a plataforma cria e posta vídeos com frequência fixa [O].

**Funcionalidades:**
- **Geração do zero:**
  - Uma "série" é criada com tema pronto ou prompt customizado.
  - A IA escreve o roteiro (ou aceita um colado), gera imagens ou stock, voz por TTS com **clonagem de voz**, legendas grandes centralizadas e música de fundo [O e T argil].
  - Os "motion credits" animam imagens: Starter 27, Daily 62 e Hardcore 124 [O].
- **Revisão:** preview antes de postar, com edição de roteiro, título, imagens e música [O].
- **Publicação:** **auto-posting** em TikTok, YouTube e Instagram, conforme agenda [O].
- **Não encontrei:** corte de vídeo longo, reenquadramento, API pública, colaboração, idiomas suportados ou limites de duração.

**Fluxo:**
1. Criar a série (tema e estilo).
2. A IA gera o 1º vídeo.
3. Revisar e customizar.
4. Conectar os canais.
5. Definir a frequência.
6. Gerar e postar no automático.

**Diferenciais:** automação ponta a ponta "configure e esqueça" e preço por frequência de postagem.

**Planos e preços** (autoshorts.ai, 23/10/2026 [O]):
- Free: 1 vídeo, mas aparece **"Temporarily paused"**.
- **Starter: US$ 19/mês**, 3 posts por semana.
- **Daily: US$ 39/mês**, 1 por dia.
- **Hardcore: US$ 69/mês**, 2 por dia.
- **1 série por assinatura.** O anual dá "2 meses grátis", mas o valor não aparece. Um review diz que não existe plano anual, o que diverge [?].

**Pontos fracos** [Trustpilot e T]:
- Imagens estáticas e roteiros fracos e repetitivos.
- Créditos limitados para refazer imagens.
- "Os vídeos não performam como antes" (abr/2026).
- Visual padronizado e voz sintética em frases longas.
- Sem rosto ou voz próprios no formato faceless.
- Preso a 1 série por assinatura.
- Visualizações baixas em muitos canais.
- Plataformas como o YouTube vêm desvalorizando conteúdo repetitivo e produzido em massa [T, contexto de mercado; não verifiquei política específica].

**Ideias para o produto contábil:**
- **Séries editoriais** com frequência fixa, como "Pílula fiscal de segunda" ou "Prazos da semana".
- Pipeline tema → roteiro → vídeo → revisão → postagem.
- **Ao contrário do faceless**, usar o **avatar do sócio**, porque autoridade e confiança são o produto do escritório.
- Revisão humana obrigatória por causa do risco técnico e das normas éticas do CFC sobre publicidade profissional.

---

## 3. Matriz de funcionalidades

Legenda: ✅ = existe (documentado); ❌ = não existe ou não encontrei; ◐ = parcial ou só em planos altos; ? = não consegui verificar.

| Funcionalidade | Opus Clip | Submagic | CapCut (+Pippit) | Vizard | Klap | AutoShorts.ai |
|---|---|---|---|---|---|---|
| Corte de vídeo longo em clipes | ✅ | ✅ (Magic Clips) | ✅ (AI Highlights) | ✅ | ✅ | ❌ |
| Seleção multimodal (visual/áudio/emoção) | ✅ (ClipAnything, Pro) | ? | ? | ? | ? | ❌ |
| Clipping por prompt / tema | ✅ | ? | ❌ | ◐ (agente) | ❌ | ❌ |
| Virality score | ✅ (0–99, 4 eixos) | ❌ | ❌ | ✅ | ✅ | ❌ |
| Legendas animadas com estilos | ✅ | ✅ (referência) | ✅ | ✅ | ✅ | ✅ (estilo fixo) |
| Nº de idiomas de legenda | ~25 | 123 | vários | 100+ (tradução) | 52 | ? |
| Vocabulário customizado | ? | ✅ (Business) | ❌ | ? | ? | ❌ |
| Emojis / palavras destacadas por IA | ? | ✅ | ✅ | ✅ | ? | ❌ |
| B-roll automático | ✅ (IA img/vídeo + stock) | ✅ | ◐ | ✅ | ❌ | ✅ (stock/IA) |
| Reenquadramento 9:16 com rosto | ✅ | ? (vídeo já vertical) | ✅ | ✅ | ✅ | n/a |
| Rastreamento de objeto em movimento | ✅ (Pro) | ❌ | ✅ (Pro) | ? | ◐ | n/a |
| Layouts de cena (split/screencast) | ? | ❌ | ◐ (manual) | ? | ✅ (Reframe 2) | n/a |
| Auto-zoom / cortes dinâmicos | ? | ✅ (Magic Zooms) | ✅ (Auto-Edit) | ? | ? | ◐ (motion) |
| Remoção de silêncio / bad takes | ? | ✅ (Pro+) | ✅ | ✅ | ? | n/a |
| Edição por texto (transcrição) | ✅ | ✅ | ✅ | ✅ | ? | ◐ (roteiro) |
| Música de fundo / SFX | ? | ✅ | ✅ | ? | ? | ✅ |
| Limpeza de áudio | ? | ✅ | ✅ | ? | ? | ❌ |
| Eye contact | ❌ | ✅ | ? | ❌ | ❌ | ❌ |
| Templates de marca (brand kit) | ✅ | ✅ | ◐ | ✅ | ◐ (fonte/cor/logo) | ❌ |
| Intro/outro | ✅ (Pro) | ? | ✅ | ✅ | ? | ❌ |
| Geração do zero (roteiro→vídeo) | ✅ (Agent Opus) | ◐ (AI Actors) | ✅ (Video Studio/Pippit) | ✅ (AI Studio) | ❌ | ✅ (core) |
| Avatar / clone de voz | ✅ (Agent) | ✅ (AI Actors) | ✅ (Pippit, gêmeo) | ? | ❌ | ◐ (só voz) |
| Legenda/hashtags do post | ? | ✅ | ? | ✅ | ✅ | ✅ (título) |
| Agendamento / publicação | ✅ (Pro) | ✅ (Pro+) | ✅ (TikTok; Pippit agenda) | ✅ | ✅ (+LinkedIn) | ✅ (auto-post) |
| Analytics | ? | ✅ | ✅ (Pippit) | ? | ✅ | ? |
| API pública | ✅ (Pro/Business) | ✅ | ❌ | ✅ | ✅ (por operação) | ❌ |
| MCP / Zapier / Make / n8n | ✅ MCP + Zapier | ? | ❌ | ? | ✅ MCP + Zapier + Make + n8n | ❌ |
| Colaboração / workspace | ✅ | ✅ | ✅ (Teams) | ✅ (+ link para cliente) | ◐ (Pro+) | ❌ |
| Preço em BRL | ? | ✅ | ✅ (regional) | ? | ? | ❌ |

---

## 4. Como reproduzir com ferramentas abertas (arquitetura de referência)

Todos os passos abaixo usam componentes abertos ou APIs padrão. **Nenhum produto analisado publica o próprio algoritmo**, e a descrição é inferida do comportamento documentado.

1. **Ingestão e normalização**
   - Baixar a mídia com `yt-dlp` (YouTube, Vimeo). Para lives, usar o arquivo gravado (OBS/Streamyard) ou a URL.
   - Normalizar com FFmpeg: `ffmpeg -i in.mp4 -c:v libx264 -crf 18 -c:a aac -ar 48000 norm.mp4`. Extrair o áudio com `-vn -ac 1 -ar 16000 audio.wav`.
2. **Transcrição com tempo por palavra**
   - Usar **faster-whisper** (CTranslate2, com `word_timestamps=True`) ou **WhisperX**, que faz alinhamento forçado por wav2vec2 e dá timestamps de palavra mais precisos.
   - Modelo `large-v3` (ou `large-v3-turbo`) em pt-BR.
   - Fazer pós-processamento com o **dicionário contábil** (Simples Nacional, DCTFWeb, eSocial, IRPJ, CSLL, PGDAS-D, CBS/IBS...) via `initial_prompt` e correção por regex ou LLM. É o equivalente ao "custom vocabulary" do Submagic.
3. **Diarização (quem fala)**
   - Usar **pyannote.audio** para separar o sócio de convidados ou plateia e ter legenda colorida por falante (o "speaker-based colors" que a Opus ainda lista como "coming soon").
4. **Segmentação e seleção dos melhores trechos** (equivalente ao ClipAnything / virality score)
   - Gerar candidatos com **PySceneDetect** (mudança de cena e de slide) mais limites de frase e pausa na transcrição. Usar janelas de 20 a 90 s.
   - Pontuar com um LLM usando uma rubrica explícita parecida com a da Opus (Hook / Flow / Value / Trend), adaptada:
     - **Gancho:** a primeira frase é uma pergunta, um número ou uma dor?
     - **Autossuficiência:** o trecho faz sentido sozinho e tem fecho?
     - **Valor prático**
     - **Atualidade fiscal**
     - **Risco técnico**, que sinaliza afirmação que pode estar desatualizada
   - Juntar sinais de áudio: energia/RMS e risos ou aplausos com um classificador de áudio aberto, como YAMNet ou PANNs.
   - **Ajustar o início e o fim pela pontuação da transcrição**, nunca no meio de uma frase. É a falha nº 1 citada contra Opus e Vizard.
5. **Reenquadramento vertical e rastreamento de rosto**
   - Detectar rosto com **MediaPipe Face Detection**, **RetinaFace/InsightFace** ou **YOLO (face)** a cada N quadros.
   - Rastrear com ByteTrack/OC-SORT.
   - Escolher o falante ativo com diarização + movimento labial (por exemplo, TalkNet-ASD ou Light-ASD).
   - Suavizar a trajetória do centro do recorte com média móvel exponencial ou filtro de Kalman, com "zona morta" para não tremer.
   - Aplicar no FFmpeg com `crop=w:h:x:y`, com `x` variável via `sendcmd` ou expressão, ou renderizar quadro a quadro em OpenCV/PyAV.
   - **Layouts estilo Klap:** split screen (duas pessoas empilhadas) com `vstack`, e slide + rosto (screencast) recortando a região do slide em cima e o rosto embaixo.
6. **Legendas animadas**
   - Gerar **ASS (Advanced SubStation)** a partir das palavras com tempo, usando tags de karaokê `\k`/`\kf` e `\t()` para escala e cor da palavra ativa, `\pos`, contorno e sombra. Renderizar com `ffmpeg -vf "ass=legenda.ass"` (libass).
   - Para estilos mais ricos (pulo, emoji, gradiente), usar **Remotion** (React) ou **MoviePy**.
   - Destacar palavras-chave escolhidas por LLM, como valores, prazos e nomes de tributos.
7. **Remoção de silêncio e cortes**
   - Usar `ffmpeg -af silencedetect=noise=-35dB:d=0.4`, ou **auto-editor** (open source, já gera a lista de cortes), ou VAD do Silero.
   - Remover "éé" e repetições pela transcrição e concatenar com `trim/atrim` + `concat`, com crossfade de áudio curto.
8. **Zoom e cortes dinâmicos**
   - Fazer "punch-in" de 1,1 a 1,3× nas frases de ênfase com `crop` + `scale` animados, ou `zoompan` com expressão de tempo. Alternar enquadramento a cada 3 a 6 s.
9. **B-roll automático**
   - Usar o LLM para extrair palavras-chave por trecho e buscar nas APIs **Pexels** e **Pixabay** (licença livre).
   - Ranquear por similaridade texto-imagem com **CLIP/SigLIP** e sobrepor com `overlay` + fade.
   - Para contabilidade, um **b-roll gerado** costuma valer mais: gráficos de alíquota, linha do tempo de prazos e telas de formulário estilizadas, renderizados em Remotion ou matplotlib a partir de dados.
10. **Música e áudio**
    - Música de biblioteca livre, com **ducking** via `sidechaincompress` e normalização `loudnorm` (alvo de -14 LUFS para redes).
    - Limpeza de voz com **RNNoise** (`arnndn`), **DeepFilterNet** ou Demucs.
11. **Avatar do sócio e geração do zero**
    - Roteiro gerado por LLM a partir de fontes oficiais (Receita, CFC, legislação), com citação.
    - Voz com TTS clonável, via XTTS-v2 ou F5-TTS. Atenção às **licenças**, porque alguns modelos abertos são não comerciais.
    - Lip-sync com **LatentSync**, **MuseTalk** ou **Wav2Lip** sobre um vídeo base do sócio, ou animação com **LivePortrait**. A qualidade comercial (HeyGen, Synthesia, Pippit) ainda é superior. Vale avaliar um fornecedor para o avatar e manter o resto aberto.
12. **Publicação**
    - **YouTube Data API v3** (upload de Shorts), **Instagram Graph API** (Content Publishing de Reels, exige conta Business/Creator e app aprovado), **TikTok Content Posting API** (exige auditoria do app para postar em público) e **LinkedIn API**.
    - Agendamento com fila própria (cron/worker). Esse é o ponto que mais falha nos concorrentes: precisa de retry, renovação de token e alerta de conta desconectada.
13. **Orquestração e API própria**
    - Fila de jobs (Celery/RQ ou equivalente) com FFmpeg em GPU (NVENC) e webhooks.
    - Expor uma **API REST + MCP** como Opus e Klap.

---

## 5. O que incorporar no produto para escritórios de contabilidade brasileiros

1. **Cortes de lives e palestras do sócio**: clipping por tema ("tudo sobre reforma tributária"), seleção com fecho garantido, layout slide + rosto, legenda pt-BR com dicionário contábil.
2. **Nota explicável adaptada ao nicho**: Gancho, Autossuficiência, Valor prático, Atualidade fiscal e **Risco técnico/compliance**, com justificativa em texto por clipe.
3. **Checagem de exatidão**: marcar números, alíquotas, prazos e citações legais na transcrição e pedir confirmação. Isso não existe em nenhum concorrente.
4. **Avatar do sócio com governança**: termo de consentimento, uso restrito aos vídeos do escritório, sem licença promocional (em oposição aos ToS do CapCut) e conformidade com a LGPD, porque biometria facial e voz são dados sensíveis.
5. **Séries editoriais com calendário fiscal**: estilo AutoShorts, mas com o rosto do sócio e revisão obrigatória. Exemplos: "Prazos da semana", "Mito × Verdade", "Pergunta de cliente".
6. **Fluxo de aprovação**: link de preview para o sócio aprovar ou comentar pelo celular, inspirado no Vizard, com trilha de auditoria.
7. **Brand kit do escritório**: logo, cores, CRC, aviso legal padrão e CTA para WhatsApp.
8. **LinkedIn e Instagram primeiro**, com agendamento confiável e alertas de conta desconectada.
9. **Preço em reais, por escritório, com cancelamento simples**, já que cobrança e cancelamento são a maior reclamação do mercado.
10. **Compliance com o CFC**: revisar o texto e a legenda do post contra as regras de publicidade do Código de Ética Profissional do Contador. Não verifiquei a redação atual da norma, e é preciso validar com especialista.

---

## 6. Lacunas e limitações desta pesquisa

- Não testei os produtos. A qualidade real de seleção, legenda e reframe vem de reviews de terceiros, muitos escritos por **concorrentes** (eesel, argil, blitzcut, creatify) ou com afiliação.
- Preços incompletos:
  - **Vizard**: valores em dólar ilegíveis na página oficial.
  - **CapCut**: página oficial não lida, preços regionais.
  - **Klap**: só a cobrança anual.
  - **Opus**: anual e créditos por plano não confirmados.
- Não confirmei: idiomas do AutoShorts, existência de API do CapCut (assumi que não há pública), detalhes técnicos internos do ClipAnything/ReframeAnything, data de lançamento do Agent Opus e números de 2026 do Trustpilot da AutoShorts.
- O "miss rate de 30–40%" do Vizard e os "22% de 1 estrela" da Opus vêm de um único blog cada e não foram verificados.

---

## 7. Fontes (acessadas em 23/10/2026)

**Opus Clip**
- Preços: https://www.opus.pro/pricing
- Home e funcionalidades: https://www.opus.pro/
- Virality Score (ajuda oficial): https://help.opus.pro/docs/article/virality-score
- API overview: https://help.opus.pro/api-reference/overview
- API, criar projeto: https://help.opus.pro/api-reference/endpoints/upload-video-create-project
- API, obter clipes: https://help.opus.pro/api-reference/endpoints/get-clips.md
- Agent Opus (text-to-video): https://www.opus.pro/pt-br/agent/workflows/text-to-video-agent
- Explicação do Agent Opus (terceiro, jul/2026): https://mer.vin/2026/07/agent-opus-explained-opusclip-end-to-end-ai-video-agent/
- Review (concorrente): https://www.eesel.ai/blog/opusclip-reviews
- Review 2026: https://smartremotegigs.com/software/opusclip/
- Trustpilot: https://nl-be.trustpilot.com/review/opus.pro

**Submagic**
- Home: https://www.submagic.co/
- Preços: https://www.submagic.co/pricing
- API: https://www.submagic.co/sk/api
- Remoção de silêncio (ajuda): https://care.submagic.co/en/article/how-do-i-remove-silences-on-submagic-xwjvv2/
- Removedor de silêncio (pt): https://www.submagic.co/pt/features/ai-silence-remover
- Trustpilot: https://www.trustpilot.com/review/submagic.co

**CapCut / Pippit**
- Home: https://www.capcut.com/
- Long video to shorts: https://www.capcut.com/tools/long-video-to-shorts
- Guia de clipping (2024): https://www.capcut.com/resource/ai-video-clipping-tool
- Pippit (antigo Commerce Pro; commercepro.capcut.com redireciona): https://www.pippit.ai/
- Guia Commerce Pro: https://commercepro.capcut.com/resource/how-to-streamline-ecommerce-video-production-with-ai
- Pro vs Free 2026: https://vidpros.com/capcut-pro-vs-free/
- Preços 2026: https://eesel.ai/blog/capcut-pricing
- Preços 2026: https://www.bigvu.tv/blog/capcut-pricing-2026-free-vs-pro-included-alternatives
- ToS 2025: https://www.techloy.com/capcuts-latest-terms-of-service-raises-big-questions-about-content-ownership/
- ToS 2025: https://2b-advice.com/en/2025/07/04/capcut-trouble-over-new-terms-of-service-legal-risks-lurk-here/
- ToS 2025: https://www.journalism.co.uk/s6-4/
- ToS 2025: https://90seconds.com/?p=6229

**Vizard**
- Home: https://vizard.ai/
- Preços: https://vizard.ai/pricing
- Preços (Capterra): https://www.capterra.com/p/10009818/Vizard/pricing/
- G2: https://www.g2.com/products/vizard-corp-vizard
- Review: https://vantaige.io/ai-tool/vizard
- Review 2026: https://fluxnote.io/guides/vizard-ai-video-review-2026

**Klap**
- Home: https://klap.app/
- Preços: https://klap.app/pricing
- Docs da API: https://docs.klap.app/
- Preços da API: https://docs.klap.app/pricing
- Trustpilot: https://ca.trustpilot.com/review/klap.app
- Review: https://www.toolsforhumans.ai/ai-tools/klap
- Comparativo (concorrente): https://blitzcutai.com/blog/best-ai-clipping-tools

**AutoShorts.ai**
- Home e preços: https://autoshorts.ai/
- Review 2026 (concorrente): https://www.argil.ai/blog/autoshorts-ai-review-2026-features-pricing-and-better-alternatives
- Review: https://vidpros.com/autoshorts-ai-review/
- Review: https://sendshort.ai/guides/autoshorts-review/
- Trustpilot: https://www.trustpilot.com/review/autoshorts.ai

**Ferramentas abertas citadas** (referência técnica)
- FFmpeg (filtros crop, zoompan, ass, silencedetect, sidechaincompress, loudnorm, arnndn): https://ffmpeg.org/ffmpeg-filters.html
- faster-whisper: https://github.com/SYSTRAN/faster-whisper
- WhisperX: https://github.com/m-bain/whisperX
- pyannote.audio: https://github.com/pyannote/pyannote-audio
- MediaPipe: https://ai.google.dev/edge/mediapipe
- PySceneDetect: https://www.scenedetect.com/
- auto-editor: https://github.com/WyattBlue/auto-editor
- Remotion: https://www.remotion.dev/
- Pexels API: https://www.pexels.com/api/
- LatentSync: https://github.com/bytedance/LatentSync
- MuseTalk: https://github.com/TMElyralab/MuseTalk
- LivePortrait: https://github.com/KwaiVGI/LivePortrait
