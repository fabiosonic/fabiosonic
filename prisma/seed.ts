/**
 * Dados DEMONSTRATIVOS e fictícios para ambiente local.
 * - Recria todo o conteúdo do banco apontado por DATABASE_URL (apenas APP_ENV=demo).
 * - Contas de demonstração são marcadas com isDemo=true e bloqueadas quando APP_ENV=production.
 * - Cotações e contratos são fictícios (dataSource=DEMO); códigos de opção terminam em "D".
 */
import "dotenv/config";
import { PrismaPg } from "@prisma/adapter-pg";
import { hashPassword } from "better-auth/crypto";
import { PrismaClient } from "../src/generated/prisma/client";
import { previousBusinessDay, todayBrasilia, addDays } from "../src/lib/dates";

export const DEMO_PASSWORD = "Demo@2026!";

export const DEMO_USERS = [
  { email: "admin@demo.local", name: "Ana Administradora (demo)", role: "ADMIN" as const },
  { email: "analista@demo.local", name: "Bruno Analista (demo)", role: "ANALYST" as const },
  { email: "usuario@demo.local", name: "Carla Usuária (demo)", role: "USER" as const },
  { email: "usuario2@demo.local", name: "Diego Usuário (demo)", role: "USER" as const },
];

const ASSETS = [
  { ticker: "PETR4", name: "Petrobras PN (fictício)", type: "ACAO" as const, price: 36.5 },
  { ticker: "VALE3", name: "Vale ON (fictício)", type: "ACAO" as const, price: 61.2 },
  { ticker: "ITUB4", name: "Itaú Unibanco PN (fictício)", type: "ACAO" as const, price: 33.1 },
  { ticker: "BBAS3", name: "Banco do Brasil ON (fictício)", type: "ACAO" as const, price: 27.4 },
  { ticker: "ABEV3", name: "Ambev ON (fictício)", type: "ACAO" as const, price: 12.8 },
  { ticker: "BOVA11", name: "ETF Ibovespa (fictício)", type: "ETF" as const, price: 125.3 },
];

const WEEKLY = new Set(["PETR4", "VALE3", "BOVA11"]);

// ---------------------------------------------------------------------------
// Auxiliares
// ---------------------------------------------------------------------------

function normCdf(x: number) {
  // Aproximação de Abramowitz-Stegun (apenas para gerar prêmios fictícios plausíveis).
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989423 * Math.exp((-x * x) / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))));
  return x > 0 ? 1 - p : p;
}

/** Prêmio fictício via Black-Scholes simplificado (vol 30% a.a., juros 10,5% a.a.). Uso exclusivo do seed. */
function demoPremium(type: "CALL" | "PUT", s: number, k: number, days: number) {
  const t = Math.max(days, 1) / 252;
  const v = 0.3;
  const r = 0.105;
  const d1 = (Math.log(s / k) + (r + (v * v) / 2) * t) / (v * Math.sqrt(t));
  const d2 = d1 - v * Math.sqrt(t);
  const price = type === "CALL" ? s * normCdf(d1) - k * Math.exp(-r * t) * normCdf(d2) : k * Math.exp(-r * t) * normCdf(-d2) - s * normCdf(-d1);
  return Math.max(0.01, Math.round(price * 100) / 100);
}

function thirdFriday(year: number, month: number) {
  const d = new Date(Date.UTC(year, month, 1));
  const offset = (5 - d.getUTCDay() + 7) % 7;
  return new Date(Date.UTC(year, month, 1 + offset + 14));
}

function nextFridays(from: Date, count: number) {
  const out: Date[] = [];
  const d = new Date(from);
  while (out.length < count) {
    d.setUTCDate(d.getUTCDate() + 1);
    if (d.getUTCDay() === 5) out.push(new Date(d));
  }
  return out;
}

/** Código fictício no padrão B3 (letra da série indica mês/tipo) com sufixo "D" de demonstração. */
function demoSymbol(ticker: string, type: "CALL" | "PUT", strike: number, expiration: Date, weekly: boolean) {
  const month = expiration.getUTCMonth();
  const letter = String.fromCharCode((type === "CALL" ? 65 : 77) + month);
  const strikeCode = Math.round(strike * 10).toString();
  const week = weekly ? `W${Math.ceil(expiration.getUTCDate() / 7)}` : "";
  return `${ticker.slice(0, 4)}${letter}${strikeCode}${week}D`;
}

// ---------------------------------------------------------------------------

async function main() {
  const appEnv = process.env.APP_ENV ?? "demo";
  if (appEnv === "production" || process.env.NODE_ENV === "production") {
    throw new Error("Seed demonstrativo bloqueado em produção (APP_ENV/NODE_ENV=production).");
  }
  const url = process.env.DATABASE_URL;
  if (!url) throw new Error("DATABASE_URL não definida.");
  const prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString: url }) });

  try {
    console.log("Limpando dados…");
    await prisma.$transaction([
      prisma.auditEvent.deleteMany(),
      prisma.notification.deleteMany(),
      prisma.requestEvent.deleteMany(),
      prisma.analysisRequest.deleteMany(),
      prisma.lessonProgress.deleteMany(),
      prisma.liveEvent.deleteMany(),
      prisma.lesson.deleteMany(),
      prisma.courseModule.deleteMany(),
      prisma.course.deleteMany(),
      prisma.simulationLeg.deleteMany(),
      prisma.simulation.deleteMany(),
      prisma.contentRevision.deleteMany(),
      prisma.strategyLeg.deleteMany(),
      prisma.strategy.deleteMany(),
      prisma.analysis.deleteMany(),
      prisma.position.deleteMany(),
      prisma.importBatch.deleteMany(),
      prisma.syncRun.deleteMany(),
      prisma.portfolio.deleteMany(),
      prisma.optionContract.deleteMany(),
      prisma.asset.deleteMany(),
      prisma.devEmail.deleteMany(),
      prisma.rateLimit.deleteMany(),
      prisma.verification.deleteMany(),
      prisma.session.deleteMany(),
      prisma.account.deleteMany(),
      prisma.user.deleteMany(),
    ]);

    console.log("Usuários de demonstração…");
    const hash = await hashPassword(DEMO_PASSWORD);
    const users: Record<string, string> = {};
    for (const u of DEMO_USERS) {
      const id = crypto.randomUUID();
      users[u.role === "USER" && users.USER ? "USER2" : u.role] = id;
      await prisma.user.create({ data: { id, email: u.email, name: u.name, role: u.role, emailVerified: true, isDemo: true } });
      await prisma.account.create({ data: { id: crypto.randomUUID(), accountId: id, providerId: "credential", userId: id, password: hash } });
    }

    console.log("Ativos e opções (fictícios)…");
    const now = new Date();
    const today = todayBrasilia(now);
    const monthly = [0, 1, 2].map((i) => thirdFriday(today.getUTCFullYear(), today.getUTCMonth() + i)).filter((d) => d >= today);
    if (monthly.length < 3) monthly.push(thirdFriday(today.getUTCFullYear(), today.getUTCMonth() + 3));
    const weekly = nextFridays(today, 4).filter((d) => !monthly.some((m) => m.getTime() === d.getTime()));
    const assetIds: Record<string, string> = {};
    for (const a of ASSETS) {
      const asset = await prisma.asset.create({
        data: { ticker: a.ticker, name: a.name, type: a.type, lastPrice: a.price, priceAt: now, dataSource: "DEMO" },
      });
      assetIds[a.ticker] = asset.id;
      const step = a.price < 20 ? 0.5 : a.price < 50 ? 1 : a.price < 100 ? 2 : 5;
      const center = Math.round(a.price / step) * step;
      const strikes = Array.from({ length: 9 }, (_, i) => +(center + (i - 4) * step).toFixed(2));
      const expirations = [...monthly.map((d) => ({ d, w: false })), ...(WEEKLY.has(a.ticker) ? weekly.map((d) => ({ d, w: true })) : [])];
      const rows = expirations.flatMap(({ d, w }) =>
        (["CALL", "PUT"] as const).flatMap((type) =>
          strikes.map((k) => {
            const days = Math.max(1, Math.round((d.getTime() - today.getTime()) / 86_400_000 * (5 / 7)));
            return {
              symbol: demoSymbol(a.ticker, type, k, d, w),
              assetId: asset.id,
              type,
              style: type === "CALL" ? ("AMERICANA" as const) : ("EUROPEIA" as const),
              strike: k,
              expiration: d,
              lastPrice: demoPremium(type, a.price, k, days),
              multiplier: 1,
              dataSource: "DEMO" as const,
              quoteAt: now,
            };
          }),
        ),
      );
      await prisma.optionContract.createMany({ data: rows, skipDuplicates: true });
    }

    console.log("Operações prontas e análises…");
    const exp1 = monthly[0]!;
    const exp2 = monthly[1]!;
    const strategies = [
      {
        title: "Trava de alta com CALL em PETR4",
        strategyType: "TRAVA_ALTA",
        ticker: "PETR4",
        ref: 36.5,
        exp: exp2,
        status: "PUBLISHED" as const,
        summary: "Exemplo didático de trava de alta: compra de CALL no strike 36 e venda de CALL no strike 39, limitando custo e ganho.",
        assumptions: "Cenário hipotético de alta moderada do ativo até o vencimento. Prêmios fictícios para fins de demonstração.",
        riskNotes: "Perda máxima limitada ao débito inicial. Ganho limitado à diferença entre strikes menos o débito. Não é recomendação de investimento.",
        legs: [
          { side: "BUY" as const, instrument: "CALL" as const, strike: 36, premium: 1.85, quantity: 100 },
          { side: "SELL" as const, instrument: "CALL" as const, strike: 39, premium: 0.72, quantity: 100 },
        ],
      },
      {
        title: "Venda coberta em VALE3",
        strategyType: "VENDA_COBERTA",
        ticker: "VALE3",
        ref: 61.2,
        exp: exp1,
        status: "PUBLISHED" as const,
        summary: "Exemplo de venda coberta: posição de 100 ações com venda de CALL fora do dinheiro.",
        assumptions: "Investidor já possui as ações e aceita vendê-las no strike. Valores fictícios.",
        riskNotes: "A queda do ativo continua gerando prejuízo (amortecido pelo prêmio). O ganho fica limitado acima do strike.",
        legs: [
          { side: "BUY" as const, instrument: "STOCK" as const, strike: null, premium: 61.2, quantity: 100 },
          { side: "SELL" as const, instrument: "CALL" as const, strike: 64, premium: 1.1, quantity: 100 },
        ],
      },
      {
        title: "Borboleta com CALL em BOVA11",
        strategyType: "BORBOLETA",
        ticker: "BOVA11",
        ref: 125.3,
        exp: exp2,
        status: "PUBLISHED" as const,
        summary: "Borboleta simétrica: 1 compra no 120, 2 vendas no 125 e 1 compra no 130. Dois pontos de equilíbrio.",
        assumptions: "Expectativa hipotética de lateralidade próxima de 125. Valores fictícios.",
        riskNotes: "Perda máxima limitada ao débito. Ganho máximo no strike central, no vencimento.",
        legs: [
          { side: "BUY" as const, instrument: "CALL" as const, strike: 120, premium: 7.4, quantity: 100 },
          { side: "SELL" as const, instrument: "CALL" as const, strike: 125, premium: 4.3, quantity: 200 },
          { side: "BUY" as const, instrument: "CALL" as const, strike: 130, premium: 2.2, quantity: 100 },
        ],
      },
      {
        title: "Straddle comprado em ITUB4 (rascunho)",
        strategyType: "STRADDLE",
        ticker: "ITUB4",
        ref: 33.1,
        exp: exp2,
        status: "DRAFT" as const,
        summary: "Rascunho de straddle comprado para cenário de alta volatilidade.",
        assumptions: "Expectativa hipotética de movimento forte em qualquer direção.",
        riskNotes: "Perda máxima igual ao débito se o ativo terminar no strike.",
        legs: [
          { side: "BUY" as const, instrument: "CALL" as const, strike: 33, premium: 1.2, quantity: 100 },
          { side: "BUY" as const, instrument: "PUT" as const, strike: 33, premium: 1.05, quantity: 100 },
        ],
      },
      {
        title: "Venda de PUT em BBAS3 (arquivada)",
        strategyType: "VENDA_PUT",
        ticker: "BBAS3",
        ref: 27.4,
        exp: exp1,
        status: "ARCHIVED" as const,
        summary: "Exemplo arquivado de venda de PUT com intenção de compra do ativo no strike.",
        assumptions: "Investidor aceita comprar o ativo a 26.",
        riskNotes: "Exige margem/garantia. Perda relevante em quedas fortes.",
        legs: [{ side: "SELL" as const, instrument: "PUT" as const, strike: 26, premium: 0.48, quantity: 100 }],
      },
    ];
    let firstStrategyId = "";
    for (const [i, s] of strategies.entries()) {
      const created = await prisma.strategy.create({
        data: {
          title: s.title,
          strategyType: s.strategyType,
          assetId: assetIds[s.ticker]!,
          summary: s.summary,
          assumptions: s.assumptions,
          riskNotes: s.riskNotes,
          referencePrice: s.ref,
          expiration: s.exp,
          status: s.status,
          authorId: users.ANALYST!,
          publishedAt: s.status !== "DRAFT" ? addDays(now, -i - 1) : null,
          archivedAt: s.status === "ARCHIVED" ? now : null,
          legs: { create: s.legs.map((l, position) => ({ ...l, position })) },
        },
      });
      if (!firstStrategyId) firstStrategyId = created.id;
      await prisma.contentRevision.create({ data: { entityType: "strategy", entityId: created.id, action: "create", actorId: users.ANALYST! } });
    }

    const analyses = [
      {
        title: "Como ler a grade de opções (exemplo)",
        ticker: null,
        status: "PUBLISHED" as const,
        summary: "Leitura comentada de uma grade de opções fictícia: strikes, vencimentos e prêmios.",
        body:
          "Esta análise demonstrativa explica como interpretar a grade de opções da plataforma.\n\n" +
          "1. Cada linha representa um contrato com tipo (CALL ou PUT), strike e vencimento.\n" +
          "2. O prêmio exibido é fictício e serve apenas para simulação.\n" +
          "3. Compare o strike com o preço do ativo para identificar opções dentro, no ou fora do dinheiro.\n\n" +
          "Nenhum conteúdo aqui constitui recomendação de investimento.",
      },
      {
        title: "PETR4: cenários hipotéticos para o próximo vencimento",
        ticker: "PETR4",
        status: "PUBLISHED" as const,
        summary: "Três cenários de preço (queda, estabilidade, alta) usados para comparar estratégias no simulador.",
        body:
          "Cenários hipotéticos, sem atribuição de probabilidade:\n\n" +
          "- Queda: R$ 32,00\n- Estabilidade: R$ 36,50\n- Alta: R$ 40,00\n\n" +
          "Use a visão de Previsões do simulador para comparar o resultado de cada estratégia nesses preços no vencimento.",
      },
      {
        title: "Rascunho: volatilidade em bancos",
        ticker: "ITUB4",
        status: "DRAFT" as const,
        summary: "Rascunho interno ainda não publicado sobre volatilidade no setor bancário.",
        body: "Texto em elaboração pela equipe de análise. Conteúdo fictício para demonstração.",
      },
    ];
    for (const [i, a] of analyses.entries()) {
      const created = await prisma.analysis.create({
        data: {
          title: a.title,
          assetId: a.ticker ? assetIds[a.ticker]! : null,
          summary: a.summary,
          body: a.body,
          status: a.status,
          authorId: users.ANALYST!,
          publishedAt: a.status === "PUBLISHED" ? addDays(now, -i) : null,
        },
      });
      await prisma.contentRevision.create({ data: { entityType: "analysis", entityId: created.id, action: "create", actorId: users.ANALYST! } });
    }

    console.log("Cursos, aulas e agenda…");
    const courses = [
      {
        slug: "fundamentos-de-opcoes",
        title: "Fundamentos de opções",
        description: "Curso demonstrativo e original sobre conceitos básicos de opções: direitos, obrigações, prêmio, strike e vencimento.",
        status: "PUBLISHED" as const,
        modules: [
          {
            title: "Conceitos essenciais",
            lessons: [
              ["O que é uma opção", "Uma opção é um contrato que dá ao titular o direito, mas não a obrigação, de comprar (CALL) ou vender (PUT) um ativo por um preço definido (strike) até ou em uma data (vencimento). O lançador (vendedor) recebe o prêmio e assume a obrigação correspondente."],
              ["CALL e PUT", "A CALL ganha valor quando o ativo sobe acima do strike; a PUT ganha valor quando o ativo cai abaixo do strike. No vencimento, o valor intrínseco da CALL é max(S − K, 0) e o da PUT é max(K − S, 0)."],
              ["Prêmio e valor intrínseco", "O prêmio é o preço pago pela opção. Antes do vencimento ele inclui valor intrínseco e valor extrínseco (tempo, volatilidade, juros). No vencimento resta apenas o valor intrínseco."],
            ],
          },
          {
            title: "Leitura de resultados",
            lessons: [
              ["Gráfico de payoff no vencimento", "O gráfico de payoff mostra o resultado da estratégia para cada preço do ativo no vencimento. Ele não representa a cotação da opção antes do vencimento nem uma previsão de mercado."],
              ["Ponto de equilíbrio", "Ponto de equilíbrio é o preço do ativo no vencimento em que o resultado é zero. Estratégias com várias pernas podem ter mais de um ponto de equilíbrio."],
            ],
          },
        ],
      },
      {
        slug: "estrategias-com-travas",
        title: "Estratégias com travas",
        description: "Travas de alta e de baixa com CALL e PUT: montagem, risco limitado e leitura no simulador.",
        status: "PUBLISHED" as const,
        modules: [
          {
            title: "Travas verticais",
            lessons: [
              ["Trava de alta com CALL", "Compra de CALL de strike menor e venda de CALL de strike maior, mesmo vencimento. Débito inicial, perda e ganho limitados."],
              ["Trava de baixa com PUT", "Compra de PUT de strike maior e venda de PUT de strike menor. Débito inicial, ganho limitado se o ativo cair."],
              ["Praticando no simulador", "Abra a boleta clássica, monte as duas pernas e compare a tabela de cenários com o gráfico. Salve a simulação para reabrir depois."],
            ],
          },
        ],
      },
      {
        slug: "gestao-de-risco",
        title: "Gestão de risco (em produção)",
        description: "Curso em elaboração: dimensionamento de posições e limites de perda.",
        status: "DRAFT" as const,
        modules: [{ title: "Introdução", lessons: [["Por que gerir risco", "Conteúdo em elaboração pela equipe."]] }],
      },
    ];
    const courseIds: string[] = [];
    let firstLessonIds: string[] = [];
    for (const [ci, c] of courses.entries()) {
      const course = await prisma.course.create({ data: { slug: c.slug, title: c.title, description: c.description, status: c.status, position: ci } });
      courseIds.push(course.id);
      for (const [mi, m] of c.modules.entries()) {
        const mod = await prisma.courseModule.create({ data: { courseId: course.id, title: m.title, position: mi } });
        for (const [li, [title, content]] of m.lessons.entries()) {
          const lesson = await prisma.lesson.create({ data: { moduleId: mod.id, title: title!, content: content!, durationMin: 8 + li * 4, position: li } });
          if (ci === 0 && firstLessonIds.length < 2) firstLessonIds.push(lesson.id);
        }
      }
    }
    for (const lessonId of firstLessonIds) await prisma.lessonProgress.create({ data: { userId: users.USER!, lessonId } });
    firstLessonIds = [];

    const at = (days: number, hour: number) => {
      const d = addDays(today, days);
      d.setUTCHours(hour + 3); // horário de Brasília → UTC
      return d;
    };
    await prisma.liveEvent.createMany({
      data: [
        { title: "Live: tira-dúvidas da plataforma", description: "Sessão demonstrativa de perguntas e respostas sobre as ferramentas.", kind: "LIVE", startsAt: at(2, 19), durationMin: 90, createdById: users.ADMIN! },
        { title: "Aula ao vivo: travas de alta", description: "Montagem de travas no simulador.", kind: "AULA", startsAt: at(5, 20), durationMin: 60, courseId: courseIds[1], createdById: users.ADMIN! },
        { title: "Live: leitura da grade de opções", description: "Como filtrar e ordenar a grade.", kind: "LIVE", startsAt: at(9, 19), durationMin: 60, createdById: users.ADMIN! },
        { title: "Aula ao vivo: conceitos essenciais", description: "Revisão do módulo 1.", kind: "AULA", status: "DONE", startsAt: at(-6, 20), durationMin: 60, courseId: courseIds[0], createdById: users.ADMIN! },
      ],
    });

    console.log("Carteiras…");
    const ref = previousBusinessDay(now);
    const p1 = await prisma.portfolio.create({
      data: { userId: users.USER!, connectionStatus: "CONNECTED", connectionProvider: "DEMO", connectedAt: addDays(now, -3), lastSyncAt: now, lastReferenceDate: ref },
    });
    await prisma.position.createMany({
      data: [
        { portfolioId: p1.id, ticker: "PETR4", instrumentType: "ACAO", quantity: 400, averagePrice: 33.2, referenceDate: ref, source: "B3_DEMO" },
        { portfolioId: p1.id, ticker: "VALE3", instrumentType: "ACAO", quantity: 200, averagePrice: 64.85, referenceDate: ref, source: "B3_DEMO" },
        { portfolioId: p1.id, ticker: "BOVA11", instrumentType: "ETF", quantity: 100, averagePrice: 118.4, referenceDate: ref, source: "B3_DEMO" },
        { portfolioId: p1.id, ticker: "ITUB4", instrumentType: "ACAO", quantity: 300, averagePrice: 30.15, referenceDate: ref, source: "B3_DEMO" },
      ],
    });
    await prisma.syncRun.createMany({
      data: [
        { portfolioId: p1.id, provider: "DEMO", status: "SUCCESS", referenceDate: ref, positionsCount: 4, startedAt: now, finishedAt: now },
        { portfolioId: p1.id, provider: "DEMO", status: "ERROR", message: "Falha simulada no provedor demonstrativo.", startedAt: addDays(now, -1), finishedAt: addDays(now, -1) },
      ],
    });
    await prisma.portfolio.create({ data: { userId: users.USER2! } });

    console.log("Simulação, pedidos e notificações…");
    await prisma.simulation.create({
      data: {
        userId: users.USER!,
        name: "Minha trava de alta PETR4",
        mode: "CLASSICA",
        underlyingTicker: "PETR4",
        spotPrice: 36.5,
        expiration: exp2,
        sourceStrategyId: firstStrategyId,
        scenarios: [],
        legs: {
          create: [
            { position: 0, side: "BUY", instrument: "CALL", strike: 36, premium: 1.85, quantity: 100 },
            { position: 1, side: "SELL", instrument: "CALL", strike: 39, premium: 0.72, quantity: 100 },
          ],
        },
      },
    });

    const r1 = await prisma.analysisRequest.create({
      data: {
        userId: users.USER!,
        subject: "Dúvida sobre trava de alta em PETR4",
        assetTicker: "PETR4",
        question: "Gostaria de entender como a perda máxima é calculada na trava de alta publicada.",
        status: "ANSWERED",
        assignedToId: users.ANALYST!,
      },
    });
    await prisma.requestEvent.createMany({
      data: [
        { requestId: r1.id, authorId: users.USER!, kind: "CREATED", toStatus: "OPEN", createdAt: addDays(now, -2) },
        { requestId: r1.id, authorId: users.ANALYST!, kind: "STATUS_CHANGED", fromStatus: "OPEN", toStatus: "IN_ANALYSIS", createdAt: addDays(now, -1.5) },
        {
          requestId: r1.id,
          authorId: users.ANALYST!,
          kind: "MESSAGE",
          body: "A perda máxima é o débito inicial: (1,85 − 0,72) × 100 = R$ 113,00, que ocorre se PETR4 terminar abaixo de 36 no vencimento.",
          createdAt: addDays(now, -1),
        },
        { requestId: r1.id, authorId: users.ANALYST!, kind: "STATUS_CHANGED", fromStatus: "IN_ANALYSIS", toStatus: "ANSWERED", createdAt: addDays(now, -1) },
      ],
    });
    const r2 = await prisma.analysisRequest.create({
      data: { userId: users.USER!, subject: "Venda coberta em VALE3", assetTicker: "VALE3", question: "Quais cenários devo considerar antes de montar uma venda coberta?" },
    });
    await prisma.requestEvent.create({ data: { requestId: r2.id, authorId: users.USER!, kind: "CREATED", toStatus: "OPEN" } });
    const r3 = await prisma.analysisRequest.create({
      data: { userId: users.USER2!, subject: "Pedido de outro usuário", question: "Este pedido pertence a outro usuário e não deve aparecer para a Carla." },
    });
    await prisma.requestEvent.create({ data: { requestId: r3.id, authorId: users.USER2!, kind: "CREATED", toStatus: "OPEN" } });

    await prisma.notification.createMany({
      data: [
        { userId: users.USER!, title: "Seu pedido foi respondido", body: "Dúvida sobre trava de alta em PETR4", link: `/solicitacoes/${r1.id}` },
        { userId: users.USER!, title: "Nova live agendada", body: "Live: tira-dúvidas da plataforma", link: "/agenda" },
        { userId: users.ANALYST!, title: "Novo pedido de análise", body: "Venda coberta em VALE3", link: `/solicitacoes/${r2.id}` },
      ],
    });

    console.log("\nSeed concluído. Contas de demonstração (somente ambiente local):");
    for (const u of DEMO_USERS) console.log(`  ${u.role.padEnd(8)} ${u.email}  senha: ${DEMO_PASSWORD}`);
  } finally {
    await prisma.$disconnect();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
