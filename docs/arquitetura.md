# Arquitetura

## Visão geral

Aplicação única **Next.js 16 (App Router)** que serve interface e API, com **PostgreSQL 16** via **Prisma 7**. Não há serviços separados.

```
Navegador ──► proxy.ts (x-request-id, redirecionamento otimista p/ /login)
          ├─► Páginas (Server Components) ──► requirePageCtx() ──► serviços
          ├─► /api/** (route handlers) ─────► route(): CSRF + sessão + perfil ──► serviços
          └─► /api/auth/** ─────────────────► better-auth (sessões, senha, recuperação, rate limit)

serviços (src/server/services) ──► Zod (validação) ──► autorização ──► Prisma ($transaction) ──► audit()
                                └► adaptadores (src/server/integrations): B3 e market data DEMONSTRATIVOS
```

## Pilha e versões

| Camada | Escolha | Versão |
| --- | --- | --- |
| Runtime | Node.js | 22 |
| Framework | Next.js (App Router, `proxy.ts`) | 16.4.0 |
| UI | React 19, Tailwind CSS 4, Lucide, TanStack Table 8, Recharts 3 | 19.3 / 4 / 1.x / 8.21 / 3.10 |
| Banco | PostgreSQL | 16 |
| ORM | Prisma 7 + `@prisma/adapter-pg` | 7.10.0 |
| Autenticação | better-auth (e-mail/senha, sessões no banco) | 1.7.7 |
| Validação | Zod | 4.6 |
| Cálculo | decimal.js | 10.6 |
| Logs | Pino (JSON, com redação de campos sensíveis) | 10.4 |
| Testes | Vitest 5, Playwright 1.64 | — |

Decisões de versão: TypeScript 5.9 (a 7.x é muito recente), TanStack Table 8 (a 9 é major recém-lançada), ESLint 9 (exigido por `eslint-config-next` 16). Vitest 5 com `@types/node` 22 resolveu um conflito de peer dependencies do npm.

## Decisões relevantes

- **`cacheComponents: false`**: toda página depende da sessão do usuário; a renderização por requisição é a opção mais simples e segura. Páginas que não leem cookies chamam `connection()` para não serem pré-renderizadas no build (um teste E2E revelou que `/dev/emails` estava sendo congelada no build).
- **Serviços como fonte única de regras**: páginas e rotas chamam as mesmas funções; testes de integração exercitam os serviços contra PostgreSQL real.
- **Propriedade nunca vem do cliente**: consultas filtram por `ctx.actor.id`; recursos de terceiros respondem 404 (sem revelar existência).
- **Sem exclusão de usuários**: administradores desativam contas (preserva autoria e auditoria). Desativar ou trocar perfil encerra sessões.
- **Mocks só nas bordas**: `DemoB3Provider` e `DemoMarketDataProvider` implementam interfaces (`PositionsProvider`, `MarketDataProvider`). Todo dado demonstrativo é marcado (`dataSource = DEMO`, `source = B3_DEMO`) e sinalizado na interface.
- **E-mail**: transporte `dev` grava em `dev_email` (visível em `/dev/emails` apenas com `APP_ENV=demo`). Produção requer um provedor (pendente).

## Estrutura de pastas

```
prisma/              schema, migrações, seed demonstrativo
src/proxy.ts         requestId + redirecionamento otimista
src/app/(auth)       login, recuperação, redefinição
src/app/(app)        área autenticada (painel, carteira, mercado, simulador, conteúdo, admin…)
src/app/api          rotas de API (finas)
src/server           env, db, auth, api (wrapper), audit, logger, session, errors
src/server/services  regras de negócio por módulo
src/server/integrations  adaptadores B3 / market data (demonstrativos)
src/lib              código compartilhado puro (payoff, schemas Zod, CSV, formatação, datas)
src/components       UI base, shell, gráficos, simulador, conteúdo
tests/unit|integration|e2e
```

## Modelo de dados (resumo)

| Área | Tabelas | Observações |
| --- | --- | --- |
| Acesso | `user`, `session`, `account`, `verification`, `rate_limit`, `dev_email` | Modelos exigidos pelo better-auth + `role`, `active`, `isDemo` |
| Mercado | `asset`, `option_contract` | `Decimal(18,4)`; índices por (ativo, vencimento) e vencimento; `dataSource` |
| Carteira | `portfolio` (1 por usuário), `position` (único por carteira+ticker+origem), `sync_run`, `import_batch` (único por carteira+hash) | Data-base em `DATE` |
| Conteúdo | `strategy` + `strategy_leg`, `analysis`, `content_revision` | Situação DRAFT/PUBLISHED/ARCHIVED; índices por situação/publicação |
| Simulação | `simulation` + `simulation_leg` | Cenários em JSON; privadas por usuário |
| Cursos | `course`, `course_module`, `lesson`, `lesson_progress` (único usuário+aula), `live_event` | Cascata de módulo → aulas → progresso |
| Pedidos | `analysis_request`, `request_event` (criação, mensagem, mudança de status), `notification` | Índices por usuário/status/data |
| Auditoria | `audit_event` | ator, ação, recurso, requestId, IP, metadados sanitizados; índices por data/ator/recurso/ação |

**Política de exclusão**: dados pessoais do usuário (sessões, carteira, simulações, progresso, notificações) em `Cascade`; autoria de conteúdo e lives em `Restrict`; auditoria e atribuições em `SetNull`.

## Segurança

- Senhas com scrypt (better-auth); sessão em cookie **HttpOnly, SameSite=Lax**, `Secure` quando `APP_URL` é https; expiração 12 h.
- **CSRF**: rotas próprias exigem `Origin`/`Referer` igual a `APP_URL` em métodos não seguros; better-auth valida origem nas suas rotas.
- **Limitação de tentativas** (banco): login 5/60 s por IP; recuperação 3/300 s; redefinição 10/300 s (configurável).
- Recuperação por **token de uso único**, 30 min, com revogação das sessões após a troca; resposta idêntica para e-mails inexistentes.
- Upload CSV: extensão `.csv`, tipo MIME, 512 KB, 1.000 linhas, rejeição de binários; o servidor reprocessa o arquivo na confirmação.
- Conteúdo exibido como texto (React escapa HTML; sem `dangerouslySetInnerHTML`); links de vídeo apenas `https`.
- Cabeçalhos: `X-Frame-Options`, `nosniff`, `Referrer-Policy`, `Permissions-Policy` e CSP em produção.
- Segredos só por variáveis de ambiente (`.env.example` sem valores reais); validação em `src/server/env.ts`.
- `APP_ENV=production` bloqueia contas demo, desativa a caixa de e-mail local e o seed.
- Logs Pino com redação de `password`, `token`, `cookie`, `authorization`; auditoria remove chaves sensíveis.

## Contratos de API

Erros: `{ "error": { "code": "VALIDATION|UNAUTHENTICATED|FORBIDDEN|NOT_FOUND|CONFLICT|RATE_LIMITED|BAD_REQUEST|INTERNAL", "message": "...", "fieldErrors": { "campo": ["..."] }, "requestId": "..." } }`. Toda resposta inclui `x-request-id`.

| Método e rota | Perfil | Função |
| --- | --- | --- |
| `POST /api/carteira/conectar` · `/desconectar` · `/sincronizar` | qualquer | Conexão demonstrativa e sincronização |
| `POST /api/carteira/importacao/previa` · `/confirmar` (multipart) | qualquer | Importação CSV |
| `DELETE /api/carteira/posicoes/:id` | dono | Remove posição CSV |
| `GET /api/mercado/opcoes?ativo&tipo&vencimento&ordem&dir&pagina&tamanho` · `GET /api/mercado/ativos` | qualquer | Dados de mercado (demo) |
| `POST /api/operacoes` · `PUT /api/operacoes/:id` · `POST /api/operacoes/:id/situacao` | analista/admin | Estratégias |
| `POST /api/analises` · `PUT /api/analises/:id` · `POST /api/analises/:id/situacao` | analista/admin | Análises |
| `GET/POST /api/simulacoes` · `GET/PUT/DELETE /api/simulacoes/:id` | dono | Simulações |
| `POST /api/solicitacoes` · `POST /api/solicitacoes/:id/mensagens` · `/situacao` | dono/equipe | Pedidos de análise |
| `POST /api/notificacoes/:id/lida` · `POST /api/notificacoes/lidas` | dono | Notificações |
| `POST /api/aulas/:id/progresso` | qualquer | Progresso |
| `/api/admin/usuarios`, `/cursos`, `/modulos`, `/aulas`, `/lives`, `/cotacoes` | admin | Administração |
| `GET /api/health` | público | Saúde (banco) |
