# Opções Lab

Plataforma web (MVP) para **estudo e simulação de opções** no mercado brasileiro: carteira com conexão B3 demonstrativa e importação CSV, mercado e opções diárias, operações prontas e análises, boletas simuladas (rápida, clássica e previsões), cursos e lives, pedidos de análise, administração e auditoria.

Inspirada em funcionalidades **mencionadas** na live “Tire dúvidas sobre o RCO Dash” (canal Jimmy Carvalho). Identidade visual e conteúdos são próprios; não há equivalência com o sistema original. Rastreabilidade em [`docs/evidencias.md`](docs/evidencias.md).

> ⚠️ Ambiente demonstrativo: dados de mercado e conexão B3 são **fictícios**; nenhuma ordem é enviada; conteúdo educacional, não é recomendação de investimento.

## Requisitos

- Node.js 22+ e npm
- PostgreSQL 16 (Docker Compose **ou** instalação local)

## Instalação e execução local

```bash
git clone <repositório> && cd <repositório>
cp .env.example .env
# gere um segredo e coloque em BETTER_AUTH_SECRET:
openssl rand -base64 32

# Banco — opção A: Docker Compose (cria plataforma_dev e plataforma_test)
docker compose up -d db

# Banco — opção B: PostgreSQL local
#   sudo -u postgres psql -c "CREATE USER app WITH PASSWORD 'app' CREATEDB;"
#   sudo -u postgres createdb -O app plataforma_dev
#   sudo -u postgres createdb -O app plataforma_test

npm install           # também gera o Prisma Client
npm run db:migrate    # aplica as migrações
npm run db:seed       # dados demonstrativos (recria o conteúdo do banco de desenvolvimento)
npm run dev           # http://localhost:3000
```

Produção local: `npm run build && npm start`.

### Contas de demonstração (somente `APP_ENV=demo`)

| Perfil | E-mail | Senha |
| --- | --- | --- |
| Administrador | admin@demo.local | Demo@2026! |
| Analista | analista@demo.local | Demo@2026! |
| Usuário | usuario@demo.local | Demo@2026! |
| Usuário (carteira desconectada) | usuario2@demo.local | Demo@2026! |

Essas contas são marcadas como demonstrativas e **bloqueadas** quando `APP_ENV=production`; o seed também se recusa a rodar em produção.

Recuperação de senha em ambiente local: solicite em `/recuperar-acesso` e abra o link em **`/dev/emails`** (caixa de saída local).

## Variáveis de ambiente

Ver [`.env.example`](.env.example). Principais: `APP_ENV` (`demo`/`production`), `APP_URL`, `BETTER_AUTH_SECRET` (≥ 32 caracteres), `DATABASE_URL`, `TEST_DATABASE_URL`, `EMAIL_TRANSPORT` (`dev`/`none`), `AUTH_RATE_LIMIT_*`, `LOG_LEVEL`.

## Testes

```bash
npm run lint
npm run typecheck
npm test            # recria o banco de TESTE, roda unitários + integração (Vitest)
npm run test:e2e    # build de produção na porta 3100 + Playwright (desktop e celular)
npm run build
npm run check       # lint + tipos + testes + build
```

- Os testes usam **somente** `TEST_DATABASE_URL` (o script se recusa a apagar um banco cujo nome não contenha “test”).
- Nenhum teste depende de B3, corretora ou serviços pagos.
- Navegador do Playwright: `npx playwright install --with-deps chromium`, ou `PW_CHROMIUM_PATH=/caminho/do/chrome npm run test:e2e`.

## Documentação

- [`docs/evidencias.md`](docs/evidencias.md) — fontes, limitações e decisões
- [`docs/arquitetura.md`](docs/arquitetura.md) — módulos, dados, segurança, contratos de API
- [`docs/calculos.md`](docs/calculos.md) — fórmulas e convenções do simulador
- [`docs/ferramentas.md`](docs/ferramentas.md) — ferramentas, requisitos e alternativas
- [`docs/implementado-e-pendente.md`](docs/implementado-e-pendente.md) — situação de cada funcionalidade
- [`CLAUDE.md`](CLAUDE.md) e `.claude/skills/` — convenções para desenvolvimento assistido
