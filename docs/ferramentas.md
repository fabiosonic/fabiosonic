# Ferramentas

## Utilizadas neste desenvolvimento

| Ferramenta | Uso | Situação no ambiente |
| --- | --- | --- |
| Ferramentas nativas do Claude Code (arquivos, terminal, busca, Git) | Todo o desenvolvimento | Disponíveis |
| Node.js 22 + npm 10 | Execução e dependências (`package-lock.json`) | Disponível |
| PostgreSQL 16 (pacote do sistema) | Bancos `plataforma_dev` e `plataforma_test` | Disponível; usado em todos os testes |
| Docker / Docker Compose | `docker-compose.yml` para o banco | Daemon iniciado; `docker compose config` válido, mas o **download da imagem falhou (Docker Hub 429)**. Alternativa usada: PostgreSQL local |
| Playwright (dependência de desenvolvimento) | Testes E2E e verificação visual (desktop e celular) | Usado com o Chromium pré-instalado via `PW_CHROMIUM_PATH` |
| `create-next-app@16.4.0` e `prisma init` | Geração da base e conferência do formato do Prisma 7 | Executados em diretório temporário |
| Documentação embarcada do Next (`node_modules/next/dist/docs`) | Conferir `proxy.ts`, `cacheComponents`, `connection()` | Consultada |
| WebFetch/WebSearch | Tentativa de acessar o vídeo e documentação oficial de skills | YouTube bloqueado (egress 403); docs de skills consultadas |

MCPs opcionais (Playwright MCP, Context7, GitHub MCP) **não foram necessários**. O GitHub MCP do ambiente está disponível, mas não foi preciso para o código.

## Dependências obrigatórias

- Node.js ≥ 22 e npm.
- PostgreSQL 16 (via Docker Compose ou instalação local).
- Para E2E: navegador Chromium do Playwright.

## Recursos opcionais e benefícios

| Recurso | Benefício | Alternativa se indisponível |
| --- | --- | --- |
| Docker Compose | Banco padronizado com um comando | PostgreSQL local: criar usuário `app` e bancos `plataforma_dev`/`plataforma_test` (ver README) |
| Playwright MCP | Inspecionar a interface interativamente pelo agente | Scripts Node com `@playwright/test` (como feito aqui) |
| Context7 MCP | Documentação atualizada de bibliotecas | Docs embarcadas em `node_modules` e sites oficiais |
| GitHub CLI/MCP | Abrir PRs, acompanhar CI | Interface web do GitHub |

## Instalação verificada

- Dependências do projeto: `npm install` (o `postinstall` executa `prisma generate`).
- Navegador do Playwright: `npx playwright install --with-deps chromium` (comando oficial: https://playwright.dev/docs/browsers). Em ambientes com Chromium já instalado, defina `PW_CHROMIUM_PATH=/caminho/para/chrome`.
- Docker Compose: https://docs.docker.com/compose/install/ — depois `docker compose up -d db`.
- Prisma 7 com PostgreSQL: https://www.prisma.io/docs/orm/v7/core-concepts/supported-databases/postgresql
- better-auth: https://www.better-auth.com/docs
- Skills do Claude Code (formato `SKILL.md`): https://code.claude.com/docs/en/skills
- MCPs no Claude Code (opcional): https://code.claude.com/docs/en/mcp — instale apenas servidores de fontes confiáveis e com escopo mínimo.

## Skills locais deste projeto

Em `.claude/skills/` (frontmatter `name` + `description`, conforme a documentação oficial): `pesquisa-evidencias`, `arquitetura-plataforma`, `interface-financeira`, `calculos-opcoes`, `autenticacao-autorizacao`, `testes-e-validacao`, `documentacao-entrega`. São instruções do projeto, não plugins externos.
