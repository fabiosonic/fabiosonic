---
name: avatar-contabil
description: Opera o pipeline de vídeos com avatar de IA do escritório contábil - busca pautas tributárias, gera roteiros, apresenta para revisão do contador, produz voz/avatar/montagem e publica. Use quando o usuário pedir para gerar, revisar, produzir ou publicar vídeos do perfil, ou perguntar o que está na fila.
---

# Pipeline de vídeos com avatar (contabilidade)

O código fica em `avatar_contabil/`; a configuração em `config/config.yaml`; as chaves em `.env`.
Todos os comandos rodam da raiz do repositório com `python -m avatar_contabil.cli <comando>`.

## Fluxo

1. `pautas` - busca notícias nos feeds, dá nota, escreve roteiros e põe na fila como `pendente_revisao`.
2. `fila` e `ver ID` - mostre ao usuário o roteiro, a fonte, a base legal, os pontos a verificar e os alertas das travas.
3. Revisão humana - **só o usuário aprova**. Nunca rode `aprovar` por conta própria nem invente o nome do revisor.
   Se o usuário pedir ajustes, edite o JSON em `data/fila/ID.json` (campos de `roteiro`), rode `revalidar ID`
   e mostre o resultado de novo.
4. `aprovar ID --revisor "Nome CRC"` - apenas quando o usuário disser explicitamente que aprova, informando o revisor.
5. `produzir` - gera narração (ElevenLabs), avatar (HeyGen) e as versões `instagram.mp4` (com CTA) e
   `youtube.mp4` (sem CTA) em `data/videos/ID/`. Custa créditos das duas plataformas quando `DRY_RUN=0`.
6. `publicar` - publica os produzidos, respeitando `publicacao.limite_diario`. Confirme com o usuário antes de
   rodar com `DRY_RUN=0`, pois a publicação é visível ao público.

## Regras ao revisar ou editar roteiros

- Não acrescente dado técnico (alíquota, prazo, número de norma) que não esteja na fonte; se faltar, coloque em
  `pontos_a_verificar`.
- Publicidade sóbria (NBC PG 01): sem promessa de resultado, sem sensacionalismo, sem comparar com concorrentes.
- O aviso de conteúdo gerado por IA e o aviso técnico entram automaticamente na legenda; não os remova.

## Problemas comuns

- `Variável X não definida`: falta chave no `.env`.
- Erro do FFmpeg: rode `ffmpeg -version`; o pipeline precisa de libass (legendas) e libx264.
- Instagram exige `publicacao.instagram.url_publica_base` com os vídeos acessíveis por URL pública.
