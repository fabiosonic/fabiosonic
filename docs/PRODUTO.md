# Studio Contábil: estudo consolidado e documento de produto

> Ferramenta interna do escritório para produzir, revisar e publicar o marketing do próprio escritório
> e dos clientes PME. Baseada no estudo de 28 ferramentas (relatórios em `docs/pesquisa/`).
> Combinamos as **ideias** que funcionam nesses produtos com implementação própria. Não copiamos código, marca nem textos.

## 1. O que o estudo mostrou

### O mercado é forte em quatro peças, mas elas são separadas

| Peça | Melhores do mundo | O que fazem muito bem |
|---|---|---|
| Geração de posts | Apaya, Marky, Predis, GalilAI, Canva | Marca montada a partir do site, formatos narrativos de carrossel, aprovar/regenerar com um clique |
| Agendamento e gestão | mLabs, Metricool, FeedHive, SocialBee, Postiz | Aprovação pelo cliente, nota do post antes de publicar, categorias evergreen, API |
| Avatar de IA | HeyGen, Synthesia, Argil, Captions | Clone do sócio, consentimento, API com webhooks, estimativa de custo |
| Vídeo curto | Opus Clip, Submagic, Klap, Vizard | Nota de viralidade explicável, legenda palavra por palavra, link de aprovação |

### Os buracos aparecem em todas elas

1. **Nada é vertical para contabilidade.** Não há calendário fiscal brasileiro, nem checagem de base legal, nem trava das regras de publicidade do CFC (NBC PG 01).
2. **A aprovação é fraca.** Ou só existe nos planos caros, ou não bloqueia a publicação de fato (Postiz e Buffer).
3. **O conteúdo sai genérico.** A voz da marca é ignorada e os layouts ficam iguais. A página da GalilAI para contadores lista temas de livro-texto.
4. **Créditos e cobrança são opacos.** O usuário não sabe quanto um vídeo vai custar antes de gerar.
5. **A publicação é instável.** Contas desconectam sem aviso.
6. **Português do Brasil tem pouco suporte.** Siglas como DAS, IRPF e DCTFWeb saem mal pronunciadas e não há glossário.

**Posicionamento:** o Studio Contábil junta as quatro peças num fluxo só, com o que nenhuma delas tem: **pauta fiscal brasileira, revisão técnica com CRC e travas éticas**.

## 2. Funções escolhidas e de onde veio cada ideia

| # | Função | Inspirada em | Como fazemos | Fase |
|---|---|---|---|---|
| 1 | **Perfis**: o escritório e cada cliente PME, cada um com seu kit de marca | mLabs (por marca), Marky (portal do cliente) | Cadastro de perfil com cores, logo, tom, público e CRC | MVP |
| 2 | **Marca a partir do site**: cola a URL e o sistema preenche cores, tom e público | Apaya, Marky, SocialBee Copilot | Lê o HTML público e o Claude resume tom, público e serviços | MVP |
| 3 | **"O que a marca nunca diz"** somado às vedações do CFC | Apaya | Lista por perfil mais lista padrão NBC PG 01, aplicadas na trava | MVP |
| 4 | **Pautas de 3 fontes**: notícias (RSS), **calendário fiscal** e ideias livres | Lately (RSS), lacuna do mercado | Feeds configuráveis mais um calendário fiscal editável (`config/calendario_fiscal.yaml`) | MVP |
| 5 | **Formatos narrativos de carrossel**: Problema→Solução, Mito×Verdade, Passo a passo, Checklist, Antes×Depois | GalilAI | O formato entra no prompt e o carrossel é desenhado com a marca do perfil | MVP |
| 6 | **Um conteúdo em 3 formatos**: post, carrossel e roteiro de vídeo | Canva Magic Switch, Lately | Uma pauta gera os três | MVP |
| 7 | **Nota do conteúdo explicável (0 a 100)** em 5 eixos: Gancho, Clareza, Valor prático, Urgência fiscal e Conformidade, com sugestões | FeedHive (nota), Opus Clip (eixos) | Rubrica própria avaliada pelo Claude | MVP |
| 8 | **Variações para vários clientes**: o mesmo tema adaptado ao tom de cada perfil | FeedHive (variáveis), Predis (em massa) | "Replicar para perfis" gera versões por perfil | MVP |
| 9 | **Vídeo com o avatar do sócio**, legenda palavra por palavra e versões Instagram/YouTube | HeyGen + Submagic + Argil | Pipeline `avatar_contabil` com legenda karaokê | MVP |
| 10 | **Dicionário de pronúncia contábil** (DAS, IRPF, DCTFWeb...) | Lacuna citada nos reviews | `config/pronuncia.yaml`, aplicado só ao texto falado | MVP |
| 11 | **Custo estimado antes de gerar o vídeo** | Argil (`videos.estimate`) | Cálculo por duração, com preços configuráveis | MVP |
| 12 | **Registro de consentimento** do clone (termo assinado e data) | HeyGen, Synthesia | O avatar só é liberado com o termo anexado | MVP |
| 13 | **Revisão técnica interna** com nome e CRC do revisor | Lacuna do mercado | Status "em revisão técnica" → "aprovado internamente" | MVP |
| 14 | **Link de aprovação do cliente sem login**, em que a rejeição trava a publicação | Metricool, Vizard | Página pública com token: aprovar ou pedir ajuste | MVP |
| 15 | **Enviar para aprovação pelo WhatsApp** | mLabs | Botão que abre o WhatsApp com a mensagem e o link prontos | MVP |
| 16 | **Calendário editorial com as obrigações fiscais no mesmo mês** | Later, mLabs | Visão mensal: conteúdos agendados e vencimentos lado a lado | MVP |
| 17 | **Publicação via Postiz**: rascunho até aprovar e agendamento só depois | Postiz (API) | Cliente da API pública; sem Postiz, gera um **pacote para postar à mão** | MVP |
| 18 | **Aviso de IA e rodapé com CRC** automáticos | Synthesia (rótulo), lacuna | Inseridos em toda legenda final | MVP |
| 19 | **Histórico/auditoria**: quem criou, revisou, aprovou e publicou | Metricool | Tabela de eventos | MVP |
| 20 | Cortar lives e palestras em Reels (transcrição com tempo por palavra e nota por trecho) | Opus Clip, Klap | WhisperX + Claude + FFmpeg | Fase 2 |
| 21 | Categorias evergreen com reciclagem automática | SocialBee | Fila por categoria | Fase 2 |
| 22 | Métricas e aprendizado (a IA aprende com o que performou) | Lately, Metricool | Analytics do Postiz | Fase 2 |
| 23 | Criar conteúdo mandando um áudio no WhatsApp | GalilAI | WhatsApp Business API | Fase 3 |
| 24 | Google Business Profile e avaliações | Marky, Ocoya | Postiz (GBP) | Fase 3 |
| 25 | Inbox de comentários e DMs | mLabs Chat, Metricool | Fase 3 | Fase 3 |

## 3. Fluxo principal

```
Pauta (notícia · vencimento fiscal · ideia)
   └─► Criar conteúdo: perfil + formato (post / carrossel / vídeo) + estilo narrativo
          └─► IA escreve + nota 0-100 + travas (CFC, termos do perfil, tamanho)
                 └─► Revisão técnica (contador com CRC) ── ajustar / regenerar
                        └─► Aprovação do cliente (link sem login / WhatsApp) ── pedir ajuste trava
                               └─► Produção (imagens do carrossel / voz + avatar + montagem)
                                      └─► Agendar (Postiz) ou baixar pacote ─► Publicado
```

Status de um conteúdo: `rascunho → revisao_tecnica → aguardando_cliente → aprovado → produzido → agendado → publicado`
(ou `ajuste_solicitado`, que volta para rascunho). Um perfil marcado como "do próprio escritório" pula a etapa do cliente.

## 4. Decisões técnicas

- **Uso interno:** um escritório, vários usuários de confiança, sem cobrança. Roda num servidor pequeno ou no próprio computador.
- **Stack:** Python, FastAPI, SQLite (SQLModel), páginas HTML renderizadas no servidor (Jinja) e CSS próprio, sem dependência de CDN.
- **IA:** Claude (`claude-opus-5-5`) com saída estruturada (Pydantic). Sem chave, ou com `DRY_RUN=1`, tudo funciona com respostas de exemplo.
- **Vídeo:** reaproveita `avatar_contabil` (ElevenLabs + HeyGen + FFmpeg).
- **Imagens do carrossel:** Pillow, 1080x1350, com cores e logo do perfil.
- **Publicação:** Postiz pela API pública, usado sem modificação por causa da AGPL. Como alternativa, um pacote ZIP com as mídias e a legenda.
- **Segurança:** login simples por usuário, segredos no `.env`, link do cliente com token aleatório de 32 bytes que expira em 14 dias.

## 5. Fora do escopo do MVP

Cobrança e planos, múltiplos escritórios, app mobile, transcrição de lives, inbox, métricas e WhatsApp com bot.
Esses itens estão nas fases 2 e 3 da tabela acima.

## 6. Riscos e cuidados

- **Precisão técnica:** a IA não acrescenta dado que não está na fonte e a revisão com CRC é obrigatória. O calendário fiscal é um ponto de partida editável: datas mudam por lei, feriado e município.
- **Ética (NBC PG 01):** publicidade sóbria; as travas bloqueiam promessa, sensacionalismo e comparação com concorrentes.
- **LGPD e imagem:** termo de consentimento do clone, guardado com a data; dados de clientes ficam no servidor do escritório.
- **Fornecedores:** HeyGen, ElevenLabs e Postiz mudam preços e APIs. Cada integração fica num módulo isolado, e o custo por minuto é configurável.
