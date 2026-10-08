---
name: arquitetura-plataforma
description: Organização de módulos, contratos de API, serviços e persistência (Next.js App Router + Prisma 7 + PostgreSQL). Use ao criar ou alterar rotas, serviços, modelos do banco ou migrações.
---

# Arquitetura da plataforma

Referência completa: `docs/arquitetura.md`.

- **Regras de negócio ficam em `src/server/services/*`**. Toda função recebe `ctx: Ctx` (ator da sessão + requestId) e faz validação (Zod, `parse`), autorização (`requireRole`, filtros por `ctx.actor.id`) e auditoria (`audit`).
- **Rotas de API (`src/app/api/**/route.ts`) são finas**: use `route(handler, { roles })` de `src/server/api.ts` (CSRF, sessão, erros padronizados `{ error: { code, message, fieldErrors, requestId } }`).
- **Páginas** chamam serviços diretamente após `requirePageCtx()`; nunca confie em IDs do cliente para propriedade.
- Valores monetários: `Decimal(18,4)` no banco, serializados como string (`dec()`), nunca `float` em regras.
- Integrações externas só via adaptadores em `src/server/integrations/*` (B3 e market data são demonstrativos).
- Mudou o schema? `npx prisma migrate dev --name <nome>` e `npx prisma generate`; atualize o seed se necessário.
- Operações com várias escritas usam `prisma.$transaction`.
