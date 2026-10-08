---
name: interface-financeira
description: Padrões visuais, de texto (pt-BR) e de acessibilidade da interface financeira. Use ao criar ou alterar telas, componentes, tabelas, formulários ou gráficos.
---

# Interface financeira

- Componentes base em `src/components/ui/*` (Panel, Field+fieldAria, Badge, Table, Alert, ActionButton, Pagination, FilterForm). Reutilize-os.
- Português do Brasil; moeda com `formatBRL`, datas com `formatDate` (colunas DATE, UTC) ou `formatDateTime` (Brasília).
- **Nunca comunique ganho/perda ou status só por cor**: use `SignedMoney`/`CashFlow` (sinal, ícone, texto) e badges com ícone + rótulo.
- Dados demonstrativos sempre identificados (`DataSourceBadge`, alertas "Modo demonstrativo").
- Tabelas largas usam `Table` (contêiner com rolagem própria e `relative`); grids usam `grid-cols-1` no celular.
- Gráficos têm `figcaption`/alternativa em tabela. Payoff é sempre "no vencimento".
- Estados obrigatórios: carregando, vazio (`EmptyState`), erro, sucesso, confirmação (diálogo nativo em `ActionButton`).
- Foco visível e navegação por teclado; ícones decorativos com `aria-hidden`, botões só-ícone com `aria-label`.
- Verifique no celular: `node` + Playwright com `devices["Pixel 7"]` ou `npm run test:e2e` (projeto `celular`).
