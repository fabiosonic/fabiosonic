# Implementado e pendente

Legenda: **Implementado** (funcional, persistido e testado) · **Demonstrativo** (funcional, mas com dados/integração simulados e identificados) · **Parcial** · **Pendente**.

## Acesso e perfis

| Item | Situação | Observações |
| --- | --- | --- |
| Login/logout com sessão em cookie HttpOnly | Implementado | Testes de integração e E2E |
| Sessão expirada | Implementado | Testado |
| Recuperação por token de uso único (30 min) | Implementado | E-mail na caixa local `/dev/emails` |
| Envio real de e-mail | **Pendente** | Requer provedor (SMTP/API) e credenciais; com `EMAIL_TRANSPORT=none` nada é enviado (aviso no log) |
| Perfis ADMIN/ANALYST/USER com verificação no servidor | Implementado | Serviços + rotas + páginas |
| Limitação de tentativas (login/recuperação) | Implementado | Armazenada no banco |
| Cadastro público | Fora do escopo | Usuários criados pelo administrador |
| 2FA, SSO | Pendente | — |

## Módulos

| Módulo | Situação | Observações |
| --- | --- | --- |
| Painel inicial | Implementado | Origem e data dos dados exibidas |
| Carteira — conexão B3 | **Demonstrativo** | Sem senha, sem acesso real. Integração oficial exige contrato, credenciamento e autorização do investidor junto à B3 |
| Carteira — sincronização D+1 e histórico | Demonstrativo | Data-base = dia útil anterior; **feriados não considerados** (parcial) |
| Carteira — importação CSV | Implementado | Prévia, validação, idempotência por hash e por linha |
| Mercado (ativos e opções) | **Demonstrativo** | Dados fictícios; requer contratação de market data licenciado |
| Opções diárias | Demonstrativo | Interpretação: contratos por data de vencimento |
| Operações prontas e análises | Implementado | Rascunho/publicação/arquivamento, histórico, filtros, notificações |
| Boleta rápida, clássica e previsões | Implementado (simulação) | **Nunca envia ordens**; payoff no vencimento |
| Gregas/precificação antes do vencimento | Pendente | Não implementado por decisão (evitar parecer previsão) |
| Envio de ordens a corretora | Fora do escopo | Exigiria integração e autorização regulatória |
| Cursos, módulos, aulas e progresso | Implementado | Conteúdo original demonstrativo, em texto |
| Vídeos | Parcial | Apenas campo para link https autorizado |
| Agenda de lives/aulas | Implementado | Link externo opcional; sem streaming próprio |
| Pedidos de análise | Implementado | Histórico, status, notificações |
| Notificações na plataforma | Implementado | Sem push/e-mail |
| Administração (usuários, cursos, agenda, cotações demo) | Implementado | — |
| Auditoria com filtros | Implementado | Exportação de logs: pendente |
| Indicadores administrativos | Implementado | Calculados a partir do banco |

## Qualidade e operação

| Item | Situação |
| --- | --- |
| Lint, tipos, testes unitários/integração/E2E, build | Implementado e executado (ver README) |
| CI (GitHub Actions) | Configurado em `.github/workflows/ci.yml` — **não executado** neste ambiente |
| Docker Compose para o banco | Arquivo válido; imagem não baixada aqui (limite do Docker Hub) |
| Publicação/deploy | Não realizado (não autorizado) |
| Feriados da B3 no cálculo de D+1 | Pendente |
| Exportação de auditoria, retenção de logs | Pendente |
| Testes de acessibilidade automatizados (axe) | Pendente; verificação manual e por papéis ARIA nos E2E |

## Integrações que exigem terceiros

1. **B3 (posições do investidor)**: contrato/credenciamento, documentação do fornecedor, fluxo de consentimento. Implementar `PositionsProvider` em `src/server/integrations/b3.ts`.
2. **Dados de mercado**: distribuidor licenciado (tempo real ou atrasado). Implementar `MarketDataProvider` e marcar `dataSource` como `DELAYED`/`REALTIME`.
3. **E-mail transacional**: provedor e domínio verificado; implementar transporte em `src/server/email.ts`.
