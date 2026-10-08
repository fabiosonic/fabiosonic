import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { isStaff } from "../authz";
import { getPortfolio } from "./portfolio";
import { listStrategies, listAnalyses } from "./content";
import { listLives } from "./courses";

export async function getDashboard(ctx: Ctx) {
  const [portfolio, strategies, analyses, lives, openRequests, latestQuote] = await Promise.all([
    getPortfolio(ctx),
    listStrategies(ctx, { status: "PUBLISHED", page: 1 }),
    listAnalyses(ctx, { status: "PUBLISHED", page: 1 }),
    listLives(ctx, { scope: "upcoming", take: 5 }),
    prisma.analysisRequest.count({
      where: { status: { in: ["OPEN", "IN_ANALYSIS"] }, ...(isStaff(ctx.actor) ? {} : { userId: ctx.actor.id }) },
    }),
    prisma.asset.findFirst({ orderBy: { priceAt: "desc" }, select: { priceAt: true, dataSource: true } }),
  ]);

  // Distribuição por ativo: soma por ticker (valor de mercado demonstrativo quando houver cotação, senão custo).
  const byTicker = new Map<string, { ticker: string; value: number; basis: "mercado" | "custo" }>();
  let totalCost = 0;
  let totalMarket = 0;
  let allPriced = true;
  for (const p of portfolio.positions) {
    const cost = Number(p.cost);
    const mv = p.marketValue !== null ? Number(p.marketValue) : null;
    totalCost += cost;
    if (mv === null) allPriced = false;
    totalMarket += mv ?? cost;
    const value = mv ?? cost;
    const prev = byTicker.get(p.ticker);
    byTicker.set(p.ticker, {
      ticker: p.ticker,
      value: (prev?.value ?? 0) + value,
      basis: mv === null || prev?.basis === "custo" ? "custo" : "mercado",
    });
  }
  const distribution = [...byTicker.values()].sort((a, b) => b.value - a.value);
  const totalForPct = distribution.reduce((s, d) => s + Math.abs(d.value), 0) || 1;

  return {
    portfolio: portfolio.portfolio,
    summary: {
      positions: portfolio.positions.length,
      totalCost,
      totalMarket,
      allPriced,
      result: totalMarket - totalCost,
    },
    distribution: distribution.map((d) => ({ ...d, pct: (Math.abs(d.value) / totalForPct) * 100 })),
    strategies: strategies.items.slice(0, 5),
    analyses: analyses.items.slice(0, 5),
    lives,
    openRequests,
    marketData: latestQuote ? { priceAt: latestQuote.priceAt.toISOString(), dataSource: latestQuote.dataSource } : null,
    lastSync: portfolio.syncRuns[0] ?? null,
  };
}
