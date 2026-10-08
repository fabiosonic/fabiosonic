---
name: autenticacao-autorizacao
description: Sessões (better-auth), perfis ADMIN/ANALYST/USER, CSRF, limitação de tentativas, recuperação de senha e auditoria de acesso. Use ao mexer em login, permissões, rotas protegidas ou dados por usuário.
---

# Autenticação e autorização

- Configuração em `src/server/auth.ts` (better-auth + adaptador Prisma). Cadastro público desativado; usuários são criados pelo admin (`services/users.ts`).
- Sessão: cookie HttpOnly, SameSite=Lax, 12 h; `getActorFromHeaders` rejeita contas inativas e contas demo fora de `APP_ENV=demo`.
- Páginas: `requirePageCtx(roles?)`. APIs: `route(handler, { roles })`. **Serviços revalidam** com `requireRole` e filtros `userId: ctx.actor.id` — dados de outro usuário respondem 404.
- CSRF: `assertSameOrigin` em métodos não seguros; endpoints do better-auth fazem checagem de origem própria.
- Limites: variáveis `AUTH_RATE_LIMIT_*` (armazenamento no banco).
- Recuperação: token de uso único (30 min); e-mail vai para `DevEmail` (`/dev/emails`) quando `EMAIL_TRANSPORT=dev`.
- Nunca registre senha, token ou cookie em log/auditoria (`audit` remove chaves sensíveis).
- Cubra permissões novas em `tests/integration/permissions.test.ts` e `isolation.test.ts`.
