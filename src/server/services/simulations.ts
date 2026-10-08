import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { AppError, notFound } from "../errors";
import { parse } from "../validation";
import { audit } from "../audit";
import { simulationSchema } from "@/lib/schemas";
import { analyzeStrategy } from "@/lib/options/payoff";
import { dec, iso, pageArgs, toPage } from "./common";
import type { Prisma } from "@/generated/prisma/client";

const include = { legs: { orderBy: { position: "asc" } } } satisfies Prisma.SimulationInclude;

function mapSimulation(s: Prisma.SimulationGetPayload<{ include: typeof include }>) {
  const legs = s.legs.map((l) => ({
    side: l.side,
    instrument: l.instrument,
    strike: dec(l.strike),
    premium: dec(l.premium)!,
    quantity: l.quantity,
    optionSymbol: l.optionSymbol,
  }));
  const a = analyzeStrategy({ legs, multiplier: s.multiplier, fees: s.fees.toString() });
  return {
    id: s.id,
    name: s.name,
    mode: s.mode,
    underlyingTicker: s.underlyingTicker,
    spotPrice: dec(s.spotPrice)!,
    multiplier: s.multiplier,
    fees: dec(s.fees)!,
    expiration: iso(s.expiration),
    scenarios: (s.scenarios as { label: string; price: string }[] | null) ?? [],
    notes: s.notes,
    sourceStrategyId: s.sourceStrategyId,
    createdAt: s.createdAt.toISOString(),
    updatedAt: s.updatedAt.toISOString(),
    legs,
    initialCashFlow: a.initialCashFlow.toFixed(2),
  };
}
export type SimulationDto = ReturnType<typeof mapSimulation>;

function toData(data: ReturnType<typeof parseSim>) {
  return {
    name: data.name,
    mode: data.mode,
    underlyingTicker: data.underlyingTicker,
    spotPrice: data.spotPrice,
    multiplier: data.multiplier,
    fees: data.fees,
    expiration: data.expiration,
    scenarios: data.scenarios as Prisma.InputJsonValue,
    notes: data.notes ?? null,
    sourceStrategyId: data.sourceStrategyId ?? null,
  };
}

function legsData(data: ReturnType<typeof parseSim>) {
  return data.legs.map((l, i) => ({
    position: i,
    side: l.side,
    instrument: l.instrument,
    strike: l.instrument === "STOCK" ? null : l.strike,
    premium: l.premium,
    quantity: l.quantity,
    optionSymbol: l.optionSymbol || null,
  }));
}

function parseSim(input: unknown) {
  const data = parse(simulationSchema, input);
  try {
    analyzeStrategy({ legs: data.legs, multiplier: data.multiplier, fees: data.fees });
  } catch (e) {
    throw new AppError("VALIDATION", e instanceof Error ? e.message : "Pernas inválidas.", { legs: ["Pernas inválidas."] });
  }
  return data;
}

export async function listSimulations(ctx: Ctx, q: { page?: number; search?: string }) {
  const { skip, take, page, pageSize } = pageArgs(q.page, 20);
  const where: Prisma.SimulationWhereInput = { userId: ctx.actor.id };
  if (q.search) where.OR = [{ name: { contains: q.search, mode: "insensitive" } }, { underlyingTicker: { contains: q.search.toUpperCase() } }];
  const [items, total] = await Promise.all([
    prisma.simulation.findMany({ where, include, orderBy: { updatedAt: "desc" }, skip, take }),
    prisma.simulation.count({ where }),
  ]);
  return toPage(items.map(mapSimulation), total, page, pageSize);
}

/** Simulações são privadas: outro usuário (inclusive administrador) recebe 404. */
export async function getSimulation(ctx: Ctx, id: string) {
  const s = await prisma.simulation.findFirst({ where: { id, userId: ctx.actor.id }, include });
  if (!s) throw notFound("Simulação");
  return mapSimulation(s);
}

export async function createSimulation(ctx: Ctx, input: unknown) {
  const data = parseSim(input);
  const s = await prisma.$transaction(async (tx) => {
    const created = await tx.simulation.create({
      data: { ...toData(data), userId: ctx.actor.id, legs: { create: legsData(data) } },
    });
    await audit(ctx, { action: "simulation.create", resourceType: "simulation", resourceId: created.id }, tx);
    return created;
  });
  return { id: s.id };
}

export async function updateSimulation(ctx: Ctx, id: string, input: unknown) {
  const data = parseSim(input);
  await prisma.$transaction(async (tx) => {
    const owned = await tx.simulation.findFirst({ where: { id, userId: ctx.actor.id }, select: { id: true } });
    if (!owned) throw notFound("Simulação");
    await tx.simulationLeg.deleteMany({ where: { simulationId: id } });
    await tx.simulation.update({ where: { id }, data: { ...toData(data), legs: { create: legsData(data) } } });
    await audit(ctx, { action: "simulation.update", resourceType: "simulation", resourceId: id }, tx);
  });
}

export async function deleteSimulation(ctx: Ctx, id: string) {
  const res = await prisma.simulation.deleteMany({ where: { id, userId: ctx.actor.id } });
  if (res.count === 0) throw notFound("Simulação");
  await audit(ctx, { action: "simulation.delete", resourceType: "simulation", resourceId: id });
}
