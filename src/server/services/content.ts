import "server-only";
import { prisma, type Db } from "../db";
import type { Ctx } from "../context";
import { isStaff, requireRole, STAFF } from "../authz";
import { AppError, notFound } from "../errors";
import { parse } from "../validation";
import { audit } from "../audit";
import { analysisSchema, contentStatusActionSchema, strategySchema } from "@/lib/schemas";
import { analyzeStrategy } from "@/lib/options/payoff";
import { todayBrasilia } from "@/lib/dates";
import { dec, diffFields, iso, pageArgs, toPage } from "./common";
import { notifyRoles } from "./notifications";
import type { Prisma } from "@/generated/prisma/client";
import type { ContentStatus } from "@/generated/prisma/enums";

type Action = "publish" | "archive" | "unarchive";

const TRANSITIONS: Record<Action, { from: ContentStatus[]; to: ContentStatus }> = {
  publish: { from: ["DRAFT"], to: "PUBLISHED" },
  archive: { from: ["DRAFT", "PUBLISHED"], to: "ARCHIVED" },
  unarchive: { from: ["ARCHIVED"], to: "DRAFT" },
};

async function recordRevision(
  db: Db,
  ctx: Ctx,
  entityType: "strategy" | "analysis",
  entityId: string,
  action: string,
  changes?: Prisma.InputJsonValue,
) {
  await db.contentRevision.create({ data: { entityType, entityId, action, actorId: ctx.actor.id, changes } });
}

async function assetIdByTicker(db: Db, ticker: string) {
  const asset = await db.asset.findUnique({ where: { ticker } });
  if (!asset) throw new AppError("VALIDATION", "Ativo não cadastrado.", { assetTicker: ["Ativo não encontrado no cadastro."] });
  return asset.id;
}

export async function listRevisions(ctx: Ctx, entityType: "strategy" | "analysis", entityId: string) {
  requireRole(ctx.actor, ...STAFF);
  const revs = await prisma.contentRevision.findMany({
    where: { entityType, entityId },
    orderBy: { createdAt: "desc" },
    include: { actor: { select: { name: true } } },
    take: 50,
  });
  return revs.map((r) => ({ id: r.id, action: r.action, actorName: r.actor.name, changes: r.changes, createdAt: r.createdAt.toISOString() }));
}

// ---------------------------------------------------------------------------
// Estratégias (operações prontas)
// ---------------------------------------------------------------------------

const strategyInclude = {
  asset: true,
  author: { select: { name: true } },
  legs: { orderBy: { position: "asc" } },
} satisfies Prisma.StrategyInclude;

type StrategyRow = Prisma.StrategyGetPayload<{ include: typeof strategyInclude }>;

function mapStrategy(s: StrategyRow) {
  const legs = s.legs.map((l) => ({
    side: l.side,
    instrument: l.instrument,
    strike: dec(l.strike),
    premium: dec(l.premium)!,
    quantity: l.quantity,
    optionSymbol: l.optionSymbol,
  }));
  const a = analyzeStrategy({ legs });
  return {
    id: s.id,
    title: s.title,
    strategyType: s.strategyType,
    assetTicker: s.asset.ticker,
    assetPrice: dec(s.asset.lastPrice)!,
    assetDataSource: s.asset.dataSource,
    summary: s.summary,
    assumptions: s.assumptions,
    riskNotes: s.riskNotes,
    referencePrice: dec(s.referencePrice)!,
    expiration: iso(s.expiration)!,
    status: s.status,
    authorName: s.author.name,
    publishedAt: iso(s.publishedAt),
    archivedAt: iso(s.archivedAt),
    createdAt: s.createdAt.toISOString(),
    updatedAt: s.updatedAt.toISOString(),
    legs,
    metrics: {
      initialCashFlow: a.initialCashFlow.toFixed(2),
      flow: a.flow,
      breakevens: a.breakevens.map((b) => b.toFixed(2)),
      maxProfit: a.maxProfit.unlimited ? null : a.maxProfit.value!.toFixed(2),
      maxProfitUnlimited: a.maxProfit.unlimited,
      maxLoss: a.maxLoss.unlimited ? null : a.maxLoss.value!.toFixed(2),
      maxLossUnlimited: a.maxLoss.unlimited,
    },
  };
}
export type StrategyDto = ReturnType<typeof mapStrategy>;

export interface StrategyQuery {
  page?: number;
  asset?: string;
  type?: string;
  status?: string;
  month?: string; // aaaa-mm
}

export async function listStrategies(ctx: Ctx, q: StrategyQuery) {
  const { skip, take, page, pageSize } = pageArgs(q.page, 12);
  const where: Prisma.StrategyWhereInput = {};
  // Usuários veem somente conteúdo publicado, independentemente do filtro solicitado.
  if (!isStaff(ctx.actor)) where.status = "PUBLISHED";
  else if (q.status === "DRAFT" || q.status === "PUBLISHED" || q.status === "ARCHIVED") where.status = q.status;
  if (q.asset) where.asset = { ticker: q.asset.toUpperCase() };
  if (q.type) where.strategyType = q.type;
  if (q.month && /^\d{4}-\d{2}$/.test(q.month)) {
    const [y, m] = q.month.split("-").map(Number) as [number, number];
    where.expiration = { gte: new Date(Date.UTC(y, m - 1, 1)), lt: new Date(Date.UTC(y, m, 1)) };
  }
  const [items, total] = await Promise.all([
    prisma.strategy.findMany({
      where,
      include: strategyInclude,
      orderBy: [{ publishedAt: { sort: "desc", nulls: "first" } }, { updatedAt: "desc" }],
      skip,
      take,
    }),
    prisma.strategy.count({ where }),
  ]);
  return toPage(items.map(mapStrategy), total, page, pageSize);
}

export async function getStrategy(ctx: Ctx, id: string) {
  const s = await prisma.strategy.findUnique({ where: { id }, include: strategyInclude });
  // Conteúdo não publicado é invisível para usuários (resposta 404, sem revelar existência).
  if (!s || (!isStaff(ctx.actor) && s.status !== "PUBLISHED")) throw notFound("Operação");
  return mapStrategy(s);
}

function validateLegs(legs: { side: "BUY" | "SELL"; instrument: "CALL" | "PUT" | "STOCK"; strike: string | null; premium: string; quantity: number }[]) {
  try {
    analyzeStrategy({ legs });
  } catch (e) {
    throw new AppError("VALIDATION", e instanceof Error ? e.message : "Pernas inválidas.", { legs: ["Pernas inválidas."] });
  }
}

export async function createStrategy(ctx: Ctx, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const data = parse(strategySchema, input);
  if (data.expiration < todayBrasilia()) throw new AppError("VALIDATION", "Vencimento no passado.", { expiration: ["Informe um vencimento futuro."] });
  validateLegs(data.legs);
  const created = await prisma.$transaction(async (tx) => {
    const assetId = await assetIdByTicker(tx, data.assetTicker);
    const s = await tx.strategy.create({
      data: {
        title: data.title,
        strategyType: data.strategyType,
        assetId,
        summary: data.summary,
        assumptions: data.assumptions,
        riskNotes: data.riskNotes,
        referencePrice: data.referencePrice,
        expiration: data.expiration,
        authorId: ctx.actor.id,
        legs: {
          create: data.legs.map((l, i) => ({
            position: i,
            side: l.side,
            instrument: l.instrument,
            strike: l.instrument === "STOCK" ? null : l.strike,
            premium: l.premium,
            quantity: l.quantity,
            optionSymbol: l.optionSymbol || null,
          })),
        },
      },
    });
    await recordRevision(tx, ctx, "strategy", s.id, "create");
    await audit(ctx, { action: "strategy.create", resourceType: "strategy", resourceId: s.id, metadata: { title: data.title } }, tx);
    return s;
  });
  return { id: created.id };
}

export async function updateStrategy(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const data = parse(strategySchema, input);
  validateLegs(data.legs);
  await prisma.$transaction(async (tx) => {
    const current = await tx.strategy.findUnique({ where: { id }, include: strategyInclude });
    if (!current) throw notFound("Operação");
    if (current.status === "ARCHIVED") throw new AppError("CONFLICT", "Reative a operação arquivada antes de editar.");
    const assetId = await assetIdByTicker(tx, data.assetTicker);
    const fields = {
      title: data.title,
      strategyType: data.strategyType,
      assetTicker: data.assetTicker,
      summary: data.summary,
      assumptions: data.assumptions,
      riskNotes: data.riskNotes,
      referencePrice: data.referencePrice,
      expiration: data.expiration,
    };
    const changes: Record<string, unknown> = diffFields(
      { ...current, assetTicker: current.asset.ticker, referencePrice: current.referencePrice.toString() },
      fields,
    );
    const legsBefore = JSON.stringify(mapStrategy(current).legs.map((l) => ({ ...l, optionSymbol: l.optionSymbol ?? null })));
    const legsAfter = JSON.stringify(
      data.legs.map((l) => ({
        side: l.side,
        instrument: l.instrument,
        strike: l.instrument === "STOCK" ? null : l.strike,
        premium: l.premium,
        quantity: l.quantity,
        optionSymbol: l.optionSymbol || null,
      })),
    );
    const legsChanged = !sameLegs(legsBefore, legsAfter);
    if (legsChanged) changes.pernas = { de: JSON.parse(legsBefore), para: JSON.parse(legsAfter) };
    await tx.strategy.update({
      where: { id },
      data: {
        title: data.title,
        strategyType: data.strategyType,
        assetId,
        summary: data.summary,
        assumptions: data.assumptions,
        riskNotes: data.riskNotes,
        referencePrice: data.referencePrice,
        expiration: data.expiration,
      },
    });
    if (legsChanged) {
      await tx.strategyLeg.deleteMany({ where: { strategyId: id } });
      await tx.strategyLeg.createMany({
        data: data.legs.map((l, i) => ({
          strategyId: id,
          position: i,
          side: l.side,
          instrument: l.instrument,
          strike: l.instrument === "STOCK" ? null : l.strike,
          premium: l.premium,
          quantity: l.quantity,
          optionSymbol: l.optionSymbol || null,
        })),
      });
    }
    if (Object.keys(changes).length) {
      await recordRevision(tx, ctx, "strategy", id, "update", changes as Prisma.InputJsonValue);
      await audit(ctx, { action: "strategy.update", resourceType: "strategy", resourceId: id, metadata: { campos: Object.keys(changes) } }, tx);
    }
  });
}

/** Compara pernas normalizando a representação decimal (ex.: "1.5" vs "1.5000"). */
function sameLegs(a: string, b: string) {
  const norm = (s: string) =>
    (JSON.parse(s) as Record<string, unknown>[]).map((l) => ({
      ...l,
      strike: l.strike === null ? null : Number(l.strike),
      premium: Number(l.premium),
    }));
  return JSON.stringify(norm(a)) === JSON.stringify(norm(b));
}

export async function changeStrategyStatus(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const { action } = parse(contentStatusActionSchema, input);
  const t = TRANSITIONS[action];
  const s = await prisma.$transaction(async (tx) => {
    const current = await tx.strategy.findUnique({ where: { id } });
    if (!current) throw notFound("Operação");
    if (!t.from.includes(current.status)) throw new AppError("CONFLICT", "Transição de situação não permitida.");
    const updated = await tx.strategy.update({
      where: { id },
      data: {
        status: t.to,
        ...(t.to === "PUBLISHED" ? { publishedAt: new Date() } : {}),
        ...(t.to === "ARCHIVED" ? { archivedAt: new Date() } : { archivedAt: null }),
      },
    });
    await recordRevision(tx, ctx, "strategy", id, action, { situacao: { de: current.status, para: t.to } });
    await audit(ctx, { action: `strategy.${action}`, resourceType: "strategy", resourceId: id }, tx);
    if (t.to === "PUBLISHED") {
      await notifyRoles(["USER"], { title: "Nova operação publicada", body: updated.title, link: `/operacoes/${id}` }, tx);
    }
    return updated;
  });
  return { status: s.status };
}

// ---------------------------------------------------------------------------
// Análises
// ---------------------------------------------------------------------------

const analysisInclude = { asset: true, author: { select: { name: true } } } satisfies Prisma.AnalysisInclude;

function mapAnalysis(a: Prisma.AnalysisGetPayload<{ include: typeof analysisInclude }>) {
  return {
    id: a.id,
    title: a.title,
    assetTicker: a.asset?.ticker ?? null,
    summary: a.summary,
    body: a.body,
    status: a.status,
    authorName: a.author.name,
    publishedAt: iso(a.publishedAt),
    createdAt: a.createdAt.toISOString(),
    updatedAt: a.updatedAt.toISOString(),
  };
}
export type AnalysisDto = ReturnType<typeof mapAnalysis>;

export async function listAnalyses(ctx: Ctx, q: { page?: number; asset?: string; status?: string }) {
  const { skip, take, page, pageSize } = pageArgs(q.page, 12);
  const where: Prisma.AnalysisWhereInput = {};
  if (!isStaff(ctx.actor)) where.status = "PUBLISHED";
  else if (q.status === "DRAFT" || q.status === "PUBLISHED" || q.status === "ARCHIVED") where.status = q.status;
  if (q.asset) where.asset = { ticker: q.asset.toUpperCase() };
  const [items, total] = await Promise.all([
    prisma.analysis.findMany({
      where,
      include: analysisInclude,
      orderBy: [{ publishedAt: { sort: "desc", nulls: "first" } }, { updatedAt: "desc" }],
      skip,
      take,
    }),
    prisma.analysis.count({ where }),
  ]);
  return toPage(items.map(mapAnalysis), total, page, pageSize);
}

export async function getAnalysis(ctx: Ctx, id: string) {
  const a = await prisma.analysis.findUnique({ where: { id }, include: analysisInclude });
  if (!a || (!isStaff(ctx.actor) && a.status !== "PUBLISHED")) throw notFound("Análise");
  return mapAnalysis(a);
}

export async function createAnalysis(ctx: Ctx, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const data = parse(analysisSchema, input);
  const created = await prisma.$transaction(async (tx) => {
    const assetId = data.assetTicker ? await assetIdByTicker(tx, data.assetTicker) : null;
    const a = await tx.analysis.create({
      data: { title: data.title, assetId, summary: data.summary, body: data.body, authorId: ctx.actor.id },
    });
    await recordRevision(tx, ctx, "analysis", a.id, "create");
    await audit(ctx, { action: "analysis.create", resourceType: "analysis", resourceId: a.id, metadata: { title: data.title } }, tx);
    return a;
  });
  return { id: created.id };
}

export async function updateAnalysis(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const data = parse(analysisSchema, input);
  await prisma.$transaction(async (tx) => {
    const current = await tx.analysis.findUnique({ where: { id }, include: { asset: true } });
    if (!current) throw notFound("Análise");
    if (current.status === "ARCHIVED") throw new AppError("CONFLICT", "Reative a análise arquivada antes de editar.");
    const assetId = data.assetTicker ? await assetIdByTicker(tx, data.assetTicker) : null;
    const changes = diffFields(
      { title: current.title, assetTicker: current.asset?.ticker ?? null, summary: current.summary, body: current.body },
      { title: data.title, assetTicker: data.assetTicker, summary: data.summary, body: data.body },
    );
    await tx.analysis.update({ where: { id }, data: { title: data.title, assetId, summary: data.summary, body: data.body } });
    if (Object.keys(changes).length) {
      await recordRevision(tx, ctx, "analysis", id, "update", changes as Prisma.InputJsonValue);
      await audit(ctx, { action: "analysis.update", resourceType: "analysis", resourceId: id, metadata: { campos: Object.keys(changes) } }, tx);
    }
  });
}

export async function changeAnalysisStatus(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, ...STAFF);
  const { action } = parse(contentStatusActionSchema, input);
  const t = TRANSITIONS[action];
  const a = await prisma.$transaction(async (tx) => {
    const current = await tx.analysis.findUnique({ where: { id } });
    if (!current) throw notFound("Análise");
    if (!t.from.includes(current.status)) throw new AppError("CONFLICT", "Transição de situação não permitida.");
    const updated = await tx.analysis.update({
      where: { id },
      data: {
        status: t.to,
        ...(t.to === "PUBLISHED" ? { publishedAt: new Date() } : {}),
        ...(t.to === "ARCHIVED" ? { archivedAt: new Date() } : { archivedAt: null }),
      },
    });
    await recordRevision(tx, ctx, "analysis", id, action, { situacao: { de: current.status, para: t.to } });
    await audit(ctx, { action: `analysis.${action}`, resourceType: "analysis", resourceId: id }, tx);
    if (t.to === "PUBLISHED") {
      await notifyRoles(["USER"], { title: "Nova análise publicada", body: updated.title, link: `/analises/${id}` }, tx);
    }
    return updated;
  });
  return { status: a.status };
}
