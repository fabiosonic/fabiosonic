# Studio Contábil + Avatar Contábil

Este repositório tem duas partes:

- **Studio Contábil** (`studio/`): aplicativo web interno do escritório que junta, num fluxo só, o melhor
  das 28 ferramentas estudadas em `docs/pesquisa/`. O desenho completo está em [`docs/PRODUTO.md`](docs/PRODUTO.md).
- **Avatar Contábil** (`avatar_contabil/`): o motor de vídeo com avatar (voz, avatar e montagem), usado pelo
  Studio e também por linha de comando.

## Studio Contábil

```bash
pip install -r requirements.txt
cp .env.example .env          # DRY_RUN=1 deixa testar tudo sem chaves de API
python -m studio              # abre em http://localhost:8000  (--publico para acessar pela rede)
```

No primeiro acesso você cria o administrador (informe o CRC para poder fazer a revisão técnica).

**O que ele faz**

| Função | Inspirada em |
|---|---|
| Perfis (escritório e clientes) com kit de marca; **preenche tom, público, serviços e cores a partir do site** | Apaya, Marky, mLabs |
| Lista "o que esta marca nunca diz", somada às vedações da NBC PG 01 | Apaya |
| Pautas de **notícias**, **calendário fiscal brasileiro** (editável em `config/calendario_fiscal.yaml`) e ideias | Lately + lacuna do mercado |
| Post, **carrossel com formatos narrativos** (Problema→Solução, Mito×Verdade, Checklist...) ou **vídeo com avatar** | GalilAI, Canva |
| **Nota de 0 a 100 explicável** em 5 eixos (Gancho, Clareza, Valor prático, Urgência, Conformidade) | FeedHive, Opus Clip |
| Imagens do carrossel desenhadas com cores, logo e CRC do perfil | Predis, Canva |
| **Revisão técnica com CRC** obrigatória, registrada no histórico | lacuna do mercado |
| **Link de aprovação para o cliente, sem login**, enviado pelo WhatsApp; pedido de ajuste trava a publicação | Metricool, mLabs, Vizard |
| Replicar o conteúdo para outros clientes, adaptado ao tom de cada um | FeedHive, Predis |
| Vídeo com **legenda palavra por palavra**, **dicionário de pronúncia** (`config/pronuncia.yaml`), **custo estimado** antes de gerar e **termo de consentimento** obrigatório | Submagic, Argil, HeyGen |
| Calendário editorial com as obrigações fiscais do mês | Later, mLabs |
| Agendamento pelo **Postiz** (opcional) ou **pacote ZIP** para postar à mão, sempre com aviso de IA e CRC na legenda | Postiz |

**Para usar com IA de verdade:** `ANTHROPIC_API_KEY` no `.env` e `DRY_RUN=0`. Para vídeo, configure HeyGen e
ElevenLabs (seção abaixo) e informe os IDs no perfil. Para agendar, ative `studio.postiz` no `config.yaml`,
coloque `POSTIZ_API_KEY` no `.env` e preencha os canais do perfil.

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
