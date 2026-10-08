# Opções Lab — instruções do projeto

Plataforma web (MVP) de estudo e simulação de opções, inspirada em funcionalidades verificáveis do vídeo de referência (ver `docs/evidencias.md`). Domínio: mercado financeiro (não é sistema contábil).

## Comandos
- `npm install` (gera o Prisma Client no `postinstall`)
- `npm run dev` — desenvolvimento em http://localhost:3000
- `npm run db:migrate` (deploy) / `npm run db:migrate:dev -- --name x` (nova migração) / `npm run db:seed` / `npm run db:reset`
- `npm run lint` · `npm run typecheck` · `npm test` · `npm run test:e2e` · `npm run build`
- `npm run check` — lint + tipos + testes + build

## Convenções
- TypeScript estrito; Next.js 16 App Router (`src/app`), `proxy.ts` (antigo middleware). `cacheComponents` desativado (app 100% por usuário).
- Prisma 7: schema em `prisma/schema.prisma`, client gerado em `src/generated/prisma` (não versionado), adaptador `@prisma/adapter-pg`.
- Regras de negócio em `src/server/services/*` com `ctx` (ator + requestId), validação Zod (`src/lib/schemas.ts`), autorização e auditoria.
- Rotas de API finas com `route()` (`src/server/api.ts`). Erros: `{ error: { code, message, fieldErrors?, requestId } }`.
- Textos em português do Brasil; moeda BRL; datas dd/mm/aaaa.
- Cálculos financeiros com `decimal.js` (`src/lib/options/payoff.ts`); testes com valores calculados à mão.
- Dados/integrações demonstrativos sempre identificados na interface. Nunca pedir senha da B3, nunca enviar ordens reais.
- Antes de concluir: lint, typecheck, `npm test` e, se mexeu em UI, `npm run test:e2e`.

Skills locais em `.claude/skills/` (pesquisa-evidencias, arquitetura-plataforma, interface-financeira, calculos-opcoes, autenticacao-autorizacao, testes-e-validacao, documentacao-entrega).
