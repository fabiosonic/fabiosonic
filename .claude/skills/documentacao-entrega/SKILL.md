---
name: documentacao-entrega
description: Mantém README, docs/*.md e a lista de implementado/pendente coerentes com o código. Use ao concluir uma funcionalidade, mudar comandos/variáveis de ambiente ou integrações.
---

# Documentação e entrega

- `README.md`: instalação, `.env`, migração, seed, execução, testes, contas demo.
- `docs/implementado-e-pendente.md`: classifique cada item como **implementado**, **demonstrativo**, **parcial** ou **pendente**, e o que falta (credenciais, contratos, infraestrutura).
- `docs/evidencias.md`, `docs/arquitetura.md`, `docs/calculos.md`, `docs/ferramentas.md`: atualize quando o comportamento mudar.
- Novas variáveis de ambiente entram em `.env.example` (sem valores reais) e em `src/server/env.ts`.
- Relate resultados de testes efetivamente executados.
