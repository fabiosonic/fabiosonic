import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { requireRole } from "../authz";
import { audit } from "../audit";
import { marketDataProvider } from "../integrations/market-data";
import { pageArgs, toPage, dec, iso } from "./common";
import type { Prisma } from "@/generated/prisma/client";
import { parseDateInput, todayBrasilia, addDays } from "@/lib/dates";

export interface OptionQuery {
  page?: number;
  pageSize?: number;
  q?: string;
  asset?: string;
  type?: string;
  expiration?: string;
  sort?: string;
  dir?: string;
}

const SORTABLE: Record<string, (dir: "asc" | "desc") => Prisma.OptionContractOrderByWithRelationInput[]> = {
  symbol: (d) => [{ symbol: d }],
  strike: (d) => [{ strike: d }, { symbol: "asc" }],
  expiration: (d) => [{ expiration: d }, { strike: "asc" }],
  lastPrice: (d) => [{ lastPrice: { sort: d, nulls: "last" } }, { symbol: "asc" }],
  asset: (d) => [{ asset: { ticker: d } }, { expiration: "asc" }, { strike: "asc" }],
};

function optionWhere(q: OptionQuery): Prisma.OptionContractWhereInput {
  const where: Prisma.OptionContractWhereInput = {};
  if (q.q) where.symbol = { contains: q.q.trim().toUpperCase() };
  if (q.asset) where.asset = { ticker: q.asset.toUpperCase() };
  if (q.type === "CALL" || q.type === "PUT") where.type = q.type;
  const exp = q.expiration ? parseDateInput(q.expiration) : null;
  if (exp) where.expiration = exp;
  return where;
}

function mapOption(o: Prisma.OptionContractGetPayload<{ include: { asset: true } }>) {
  return {
    id: o.id,
    symbol: o.symbol,
    assetTicker: o.asset.ticker,
    assetPrice: dec(o.asset.lastPrice)!,
    type: o.type,
    style: o.style,
    strike: dec(o.strike)!,
    expiration: iso(o.expiration)!,
    lastPrice: dec(o.lastPrice),
    multiplier: o.multiplier,
    dataSource: o.dataSource,
    quoteAt: iso(o.quoteAt),
  };
}
export type OptionRow = ReturnType<typeof mapOption>;

export async function listOptions(_ctx: Ctx, q: OptionQuery) {
  const { skip, take, page, pageSize } = pageArgs(q.page, q.pageSize ?? 25);
  const dir = q.dir === "desc" ? "desc" : "asc";
  const orderBy = (SORTABLE[q.sort ?? ""] ?? SORTABLE.asset)(dir);
  const where = optionWhere(q);
  const [items, total] = await Promise.all([
    prisma.optionContract.findMany({ where, include: { asset: true }, orderBy, skip, take }),
    prisma.optionContract.count({ where }),
  ]);
  return toPage(items.map(mapOption), total, page, pageSize);
}

export async function listAssets(_ctx: Ctx, q: { q?: string } = {}) {
  const where: Prisma.AssetWhereInput = q.q
    ? { OR: [{ ticker: { contains: q.q.toUpperCase() } }, { name: { contains: q.q, mode: "insensitive" } }] }
    : {};
  const assets = await prisma.asset.findMany({ where, orderBy: { ticker: "asc" }, include: { _count: { select: { options: true } } } });
  return assets.map((a) => ({
    id: a.id,
    ticker: a.ticker,
    name: a.name,
    type: a.type,
    lastPrice: dec(a.lastPrice)!,
    priceAt: a.priceAt.toISOString(),
    dataSource: a.dataSource,
    optionsCount: a._count.options,
  }));
}

export async function listExpirations(_ctx: Ctx, asset?: string) {
  const rows = await prisma.optionContract.findMany({
    where: asset ? { asset: { ticker: asset.toUpperCase() } } : {},
    distinct: ["expiration"],
    select: { expiration: true },
    orderBy: { expiration: "asc" },
  });
  return rows.map((r) => iso(r.expiration)!.slice(0, 10));
}

/**
 * Opções diárias: contratos com vencimento na data escolhida (padrão: próximo vencimento a partir de hoje).
 * Os contratos listados são DEMONSTRATIVOS; não indicam disponibilidade ou liquidez reais.
 */
export async function dailyOptions(ctx: Ctx, q: { date?: string; asset?: string; type?: string; page?: number }) {
  const today = todayBrasilia();
  let date = q.date ? parseDateInput(q.date) : null;
  if (!date) {
    const next = await prisma.optionContract.findFirst({
      where: { expiration: { gte: today }, ...(q.asset ? { asset: { ticker: q.asset.toUpperCase() } } : {}) },
      orderBy: { expiration: "asc" },
      select: { expiration: true },
    });
    date = next?.expiration ?? today;
  }
  const upcoming = await prisma.optionContract.findMany({
    where: { expiration: { gte: today, lte: addDays(today, 45) } },
    distinct: ["expiration"],
    select: { expiration: true },
    orderBy: { expiration: "asc" },
  });
  const page = await listOptions(ctx, {
    expiration: iso(date)!.slice(0, 10),
    asset: q.asset,
    type: q.type,
    page: q.page,
    pageSize: 50,
    sort: "asset",
  });
  return { date: iso(date)!.slice(0, 10), upcoming: upcoming.map((u) => iso(u.expiration)!.slice(0, 10)), page };
}

export async function getOptionBySymbol(_ctx: Ctx, symbol: string) {
  const o = await prisma.optionContract.findUnique({ where: { symbol: symbol.toUpperCase() }, include: { asset: true } });
  return o ? mapOption(o) : null;
}

/** Atualiza cotações a partir do provedor configurado (demonstrativo no MVP). */
export async function refreshQuotes(ctx: Ctx, now = new Date()) {
  requireRole(ctx.actor, "ADMIN");
  const provider = marketDataProvider();
  const assets = await prisma.asset.findMany();
  const quotes = await provider.quoteAssets(
    assets.map((a) => ({ ticker: a.ticker, lastPrice: a.lastPrice.toString() })),
    now,
  );
  await prisma.$transaction(
    quotes.map((q) =>
      prisma.asset.update({ where: { ticker: q.ticker }, data: { lastPrice: q.price, priceAt: now, dataSource: provider.dataSource } }),
    ),
  );
  await audit(ctx, { action: "market.refresh_quotes", resourceType: "asset", metadata: { provider: provider.id, count: quotes.length } });
  return { updated: quotes.length };
}
