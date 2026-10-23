# Studio Contábil + Avatar Contábil

Este repositório tem duas partes:

- **Studio Contábil** (`studio/`): aplicativo web interno do escritório que junta, num fluxo só, o melhor
  das 28 ferramentas estudadas em `docs/pesquisa/`. O desenho completo está em [`docs/PRODUTO.md`](docs/PRODUTO.md).
- **Avatar Contábil** (`avatar_contabil/`): o motor de vídeo com avatar (voz, avatar e montagem), usado pelo
  Studio e também por linha de comando.

## Studio Contábil

Material para o **Instagram** (posts e carrosséis) no **piloto automático**: o sistema busca as pautas,
escreve, desenha as artes com a marca do perfil, manda para o contador revisar e publica sozinho no horário marcado.

```bash
pip install -r requirements.txt
cp .env.example .env          # DRY_RUN=1 deixa testar tudo sem chaves (a publicação é simulada)
python -m studio              # abre em http://localhost:8000  (--publico para acessar pela rede)
```

No primeiro acesso você cria o administrador (informe o CRC: ele é exigido na revisão técnica).

### Como funciona

```
todo dia (piloto automático)                     contador                   cliente (se for perfil de cliente)
─────────────────────────────                    ─────────                  ───────────────────────────────────
busca notícias + calendário fiscal                revisa e aprova            recebe o link no WhatsApp
escolhe a melhor pauta para cada dia livre  ───►  (1 clique, com CRC)  ───►  aprova pelo celular, sem senha
escreve, dá nota 0–100, aplica as travas                                       │
desenha o carrossel/post com a marca                                           ▼
                                                                 imagens finais em JPEG + agendado
                                                                 ─► publicado no Instagram na data marcada
```

- Para cada perfil, você escolhe **dias da semana, horário, formatos** (alternando carrossel e post) e com quantos
  dias de **antecedência** os posts são criados. O tempo de antecedência existe para dar prazo à revisão.
- Prioridade das pautas: **vencimento fiscal** da semana seguinte ao post (lembrete do DAS, FGTS, DCTFWeb, 13º...),
  depois **notícias** com nota boa para o público do perfil, depois as **ideias** cadastradas.
- Nada é publicado sem a aprovação técnica com CRC. Se o post não for aprovado a tempo, ele simplesmente não sai.
- Se a publicação falhar (por exemplo, token vencido), o sistema tenta mais duas vezes e depois mostra o erro no painel.

| Função | Inspirada em |
|---|---|
| Perfis (escritório e clientes) com kit de marca; **preenche tom, público, serviços e cores a partir do site** | Apaya, Marky, mLabs |
| Lista "o que esta marca nunca diz", somada às vedações da NBC PG 01 | Apaya |
| Pautas de **notícias**, **calendário fiscal brasileiro** (editável em `config/calendario_fiscal.yaml`) e ideias | Lately + lacuna do mercado |
| **Carrossel com formatos narrativos** (Problema→Solução, Mito×Verdade, Checklist...) ou post de imagem única | GalilAI, Canva |
| **Nota de 0 a 100 explicável** em 5 eixos (Gancho, Clareza, Valor prático, Urgência, Conformidade) | FeedHive, Opus Clip |
| **Piloto automático** por perfil, com calendário de dias e horários | Apaya, SocialBee |
| **Revisão técnica com CRC** obrigatória, registrada no histórico | lacuna do mercado |
| **Link de aprovação para o cliente, sem login**, enviado pelo WhatsApp; pedido de ajuste trava a publicação | Metricool, mLabs, Vizard |
| Replicar o conteúdo para outros clientes, adaptado ao tom de cada um | FeedHive, Predis |
| **Publicação direta no Instagram** pela API oficial (post e carrossel), com aviso técnico e CRC na legenda | Later, Buffer |
| Calendário editorial com as obrigações fiscais do mês | Later, mLabs |

### O que é preciso para usar de verdade

1. **Claude:** `ANTHROPIC_API_KEY` no `.env` e `DRY_RUN=0`.
2. **Endereço público:** o Instagram baixa as imagens pela internet e o cliente abre o link de aprovação no celular,
   então o Studio precisa estar acessível de fora: um servidor na nuvem ou um túnel (ex.: Cloudflare Tunnel).
   Informe o endereço em `studio.url_publica` no `config/config.yaml`.
3. **Instagram de cada perfil** (ID da conta e token, na página do perfil):
   - A conta precisa ser **profissional** (Comercial ou Criador de conteúdo).
   - Crie um app em developers.facebook.com, adicione o produto **Instagram** e peça a permissão
     `instagram_content_publish`.
   - Gere um **token de longa duração** e copie o **ID da conta do Instagram**.
   - Com o login do Facebook, a conta precisa estar ligada a uma Página e a API é `https://graph.facebook.com/v21.0`
     (padrão). Com o login do Instagram, use `https://graph.instagram.com/v21.0` em `studio.instagram_api`.
   - Enquanto o app estiver em modo de desenvolvimento, só publicam as contas cadastradas com função no app
     (testadoras). Para muitos clientes, peça a análise do app à Meta.
   - O token de longa duração vale cerca de 60 dias: renove e cole o novo token no perfil.
4. **Rodar sozinho:** ponha `studio.automacao.ativo: true` (o próprio servidor verifica a cada 5 minutos e cria os
   posts do dia a partir das 7h) ou agende `python -m studio rotina` no cron. O botão **Rodar agora** no painel faz o
   mesmo na hora.

Vídeo com avatar vem **desligado**. Para ligar, acrescente `"video"` em `studio.formatos` e configure HeyGen e
ElevenLabs (seção abaixo). A publicação pelo Postiz (várias redes) continua disponível em `studio.postiz`.

## Avatar Contábil (linha de comando)

Pipeline que produz vídeos curtos com o **avatar de IA do contador**, a partir de notícias tributárias,
com **aprovação humana obrigatória** antes de publicar.

```
 pautas ──► triagem ──► roteiro ──► REVISÃO DO CONTADOR ──► voz ──► avatar ──► montagem ──► publicação
 (RSS)      (Claude)    (Claude)     (fila em data/fila)    (ElevenLabs) (HeyGen) (FFmpeg)   (YouTube / Instagram)
```

| Etapa | Módulo | O que faz |
|---|---|---|
| 1. Pauta | `pauta.py` | Lê os feeds de `config.yaml` e ignora o que já foi visto |
| 2. Triagem | `roteiro.py` | Claude dá nota de 0 a 10 por relevância para PMEs/MEIs e descarta as fracas |
| 3. Roteiro | `roteiro.py` | Gancho + explicação + pergunta final, base legal citada e lista do que conferir |
| 4. Revisão | `fila.py` | Nada é produzido sem `aprovar ID --revisor "Nome CRC"` |
| Travas | `travas.py` | Bloqueia termos proibidos (promessa, sonegação), texto longo, e limita posts por dia |
| 5. Voz | `voz.py` | Voz clonada no ElevenLabs, com checagem de duração do áudio |
| 6. Avatar | `avatar.py` | Avatar na HeyGen sobre fundo verde |
| 7-8. Montagem | `montagem.py` | Recorte do fundo, cor/imagem da marca, legenda, logo, música; gera `instagram.mp4` (com CTA) e `youtube.mp4` (sem CTA) |
| 9. Publicação | `publicar.py` | YouTube Shorts (marcado como conteúdo sintético) e Instagram Reels, com avisos na legenda |

## Instalação

Requisitos: Python 3.10+ e FFmpeg (com libass e libx264).

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Testar sem gastar nada

Com `DRY_RUN=1` (padrão), nenhuma API paga é chamada: o pipeline usa pautas e roteiro de exemplo,
gera um áudio e um "avatar" de mentira e monta os vídeos de verdade.

```bash
python -m avatar_contabil.cli pautas
python -m avatar_contabil.cli fila
python -m avatar_contabil.cli ver <ID>
python -m avatar_contabil.cli aprovar <ID> --revisor "Fulano CRC-SP 000000"
python -m avatar_contabil.cli produzir      # vídeos em data/videos/<ID>/
python -m pytest
```

## Colocar em produção

1. **Autorização.** Colha o termo em `docs/termo_autorizacao_imagem_voz.md`, assinado por quem será clonado.
2. **Claude.** Coloque `ANTHROPIC_API_KEY` no `.env` (ou rode `ant auth login`).
3. **Voz.** No ElevenLabs, crie o clone de voz do sócio (Voice Cloning), copie o *Voice ID* para
   `voz.elevenlabs_voice_id` e a chave para `ELEVENLABS_API_KEY`.
4. **Avatar.** Na HeyGen, grave o avatar do sócio (2 a 5 minutos de vídeo, fundo neutro, boa luz), copie o
   *Avatar ID* para `avatar.heygen_avatar_id` e a chave para `HEYGEN_API_KEY`. O plano precisa incluir acesso à API.
5. **Marca.** Ajuste `escritorio` no `config.yaml`: nome, CRC, WhatsApp, cor, e opcionalmente logo (PNG),
   imagem de fundo 1080x1920 e música livre de direitos.
6. **Pautas.** Ajuste as buscas em `pauta.fontes`; dá para adicionar qualquer feed RSS.
7. **Publicação (opcional).**
   - YouTube: crie um projeto no Google Cloud, ative a *YouTube Data API v3*, baixe o OAuth client (Desktop) para
     `config/youtube_client_secret.json` e ponha `publicacao.youtube.ativo: true`. No primeiro envio o navegador
     abre para autorizar. Os vídeos sobem como `private` até você mudar `privacidade`.
   - Instagram: conta profissional ligada a uma página do Facebook, app na Meta com permissão
     `instagram_content_publish`, `INSTAGRAM_USER_ID` e `INSTAGRAM_ACCESS_TOKEN` no `.env`. O Instagram só aceita
     vídeo por URL pública: sincronize `data/videos/` com um bucket (S3, R2, GCS) e informe a URL em
     `publicacao.instagram.url_publica_base`.
   - Sem publicação automática, basta postar à mão os arquivos de `data/videos/<ID>/`.
8. Mude `DRY_RUN=0` no `.env`.

> Os endpoints da HeyGen, do ElevenLabs e da Meta mudam de versão com alguma frequência. Se uma chamada falhar,
> confira a documentação atual da plataforma; cada integração está isolada em um único arquivo.

## Rotina diária

`scripts/rodar_diario.sh` produz e publica o que foi aprovado, busca pautas novas e lista o que espera revisão.
Agende no `cron` (exemplo no próprio script). O contador revisa a fila uma vez por dia.

## Usando pelo Claude Code

A skill `.claude/skills/avatar-contabil` ensina o Claude Code a operar o pipeline. Peça, por exemplo:
"busca as pautas de hoje e me mostra os roteiros", "deixa o gancho do vídeo X mais direto" ou
"produz os aprovados". O Claude nunca aprova roteiros por conta própria.

## Cuidados legais e éticos

- **NBC PG 01 (Código de Ética):** publicidade sóbria, sem promessa de resultado. As travas bloqueiam os
  termos de `travas.termos_proibidos`; amplie a lista conforme a política do escritório.
- **Responsabilidade técnica:** o roteiro só fala do que está na fonte; o revisor confere a base legal.
- **Rótulo de IA:** YouTube (`containsSyntheticMedia`) e aviso na legenda das duas redes.
- **LGPD e direito de imagem:** termo assinado, com direito de revogação.
- **Direito autoral:** o pipeline usa só notícias como pauta (fato não tem direito autoral) e não
  reaproveita vídeos de terceiros.
