---
name: testes-e-validacao
description: Como executar e escrever testes (Vitest unitário/integração com PostgreSQL isolado e Playwright desktop/celular) e checar regressões antes de entregar. Use ao finalizar qualquer alteração.
---

# Testes e validação

Comandos (ver `CLAUDE.md`):
- `npm run lint && npm run typecheck`
- `npm test` — recria o banco de TESTE (`TEST_DATABASE_URL`), roda unitários + integração.
- `npm run test:e2e` — build de produção na porta 3100 contra o banco de teste; projetos `desktop` e `celular`. Em ambiente sem download de navegadores: `PW_CHROMIUM_PATH=/caminho/do/chrome`.
- `npm run build`

Regras:
- Integração usa `tests/support/factories.ts` (`makeUser`) para criar dados isolados; testes devem ser repetíveis sem reset.
- Testes não dependem de B3, corretora ou serviços pagos.
- Para interface, verifique também ausência de rolagem horizontal (`expectNoHorizontalOverflow`) e erros de console.
- Nunca declare verificação não executada; registre resultados reais.
