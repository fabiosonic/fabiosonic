import "server-only";
import { createHash } from "node:crypto";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { AppError } from "../errors";
import { audit } from "../audit";
import { logger } from "../logger";
import { positionsProvider, ProviderError } from "../integrations/b3";
import { parsePositionsCsv, CSV_MAX_BYTES, type CsvRowResult } from "@/lib/csv-positions";
import { dec, iso } from "./common";
import { Prisma } from "@/generated/prisma/client";

/** Obtém (ou cria) a carteira do próprio usuário. O dono vem sempre da sessão. */
async function ensurePortfolio(userId: string) {
  const existing = await prisma.portfolio.findUnique({ where: { userId } });
  if (existing) return existing;
  try {
    return await prisma.portfolio.create({ data: { userId } });
  } catch (e) {
    // Requisições simultâneas do mesmo usuário: outra já criou a carteira.
    if (e instanceof Prisma.PrismaClientKnownRequestError && e.code === "P2002") {
      return prisma.portfolio.findUniqueOrThrow({ where: { userId } });
    }
    throw e;
  }
}

export async function getPortfolio(ctx: Ctx) {
  const p = await ensurePortfolio(ctx.actor.id);
  const [positions, syncRuns, imports, assets] = await Promise.all([
    prisma.position.findMany({ where: { portfolioId: p.id }, orderBy: [{ ticker: "asc" }, { source: "asc" }] }),
    prisma.syncRun.findMany({ where: { portfolioId: p.id }, orderBy: { startedAt: "desc" }, take: 10 }),
    prisma.importBatch.findMany({ where: { portfolioId: p.id }, orderBy: { createdAt: "desc" }, take: 5 }),
    prisma.asset.findMany({ select: { ticker: true, lastPrice: true, priceAt: true, dataSource: true } }),
  ]);
  const quotes = new Map(assets.map((a) => [a.ticker, a]));
  const rows = positions.map((pos) => {
    const quote = quotes.get(pos.ticker);
    const cost = pos.averagePrice.mul(pos.quantity);
    const marketValue = quote ? quote.lastPrice.mul(pos.quantity) : null;
    return {
      id: pos.id,
      ticker: pos.ticker,
      instrumentType: pos.instrumentType,
      quantity: pos.quantity,
      averagePrice: dec(pos.averagePrice)!,
      cost: dec(cost)!,
      lastPrice: quote ? dec(quote.lastPrice) : null,
      priceAt: quote ? iso(quote.priceAt) : null,
      priceSource: quote?.dataSource ?? null,
      marketValue: dec(marketValue),
      referenceDate: iso(pos.referenceDate)!,
      source: pos.source,
    };
  });
  return {
    portfolio: {
      id: p.id,
      connectionStatus: p.connectionStatus,
      connectionProvider: p.connectionProvider,
      connectedAt: iso(p.connectedAt),
      lastSyncAt: iso(p.lastSyncAt),
      lastReferenceDate: iso(p.lastReferenceDate),
      lastError: p.lastError,
    },
    positions: rows,
    syncRuns: syncRuns.map((s) => ({
      id: s.id,
      provider: s.provider,
      status: s.status,
      referenceDate: iso(s.referenceDate),
      positionsCount: s.positionsCount,
      message: s.message,
      startedAt: s.startedAt.toISOString(),
      finishedAt: iso(s.finishedAt),
    })),
    imports: imports.map((b) => ({
      id: b.id,
      fileName: b.fileName,
      rowsTotal: b.rowsTotal,
      rowsImported: b.rowsImported,
      rowsSkipped: b.rowsSkipped,
      createdAt: b.createdAt.toISOString(),
    })),
  };
}

/** Conexão DEMONSTRATIVA: não acessa a B3 e não solicita credenciais. */
export async function connectDemo(ctx: Ctx) {
  const p = await ensurePortfolio(ctx.actor.id);
  if (p.connectionStatus === "CONNECTED" || p.connectionStatus === "SYNCING") {
    throw new AppError("CONFLICT", "A carteira já está conectada.");
  }
  await prisma.portfolio.update({
    where: { id: p.id },
    data: { connectionStatus: "CONNECTED", connectionProvider: positionsProvider().id, connectedAt: new Date(), lastError: null },
  });
  await audit(ctx, { action: "portfolio.connect", resourceType: "portfolio", resourceId: p.id, metadata: { provider: "DEMO" } });
}

export async function disconnect(ctx: Ctx) {
  const p = await ensurePortfolio(ctx.actor.id);
  if (p.connectionStatus === "DISCONNECTED") throw new AppError("CONFLICT", "A carteira já está desconectada.");
  await prisma.$transaction(async (tx) => {
    // Posições da conexão são removidas; importações CSV permanecem.
    await tx.position.deleteMany({ where: { portfolioId: p.id, source: "B3_DEMO" } });
    await tx.portfolio.update({
      where: { id: p.id },
      data: { connectionStatus: "DISCONNECTED", connectionProvider: null, connectedAt: null, lastError: null },
    });
    await audit(ctx, { action: "portfolio.disconnect", resourceType: "portfolio", resourceId: p.id }, tx);
  });
}

export async function syncNow(ctx: Ctx, opts: { simulateFailure?: boolean } = {}, now = new Date()) {
  const p = await ensurePortfolio(ctx.actor.id);
  if (p.connectionStatus === "DISCONNECTED") throw new AppError("CONFLICT", "Conecte a carteira antes de sincronizar.");
  // Transição atômica para SYNCING evita sincronizações concorrentes.
  const claimed = await prisma.portfolio.updateMany({
    where: { id: p.id, connectionStatus: { in: ["CONNECTED", "ERROR"] } },
    data: { connectionStatus: "SYNCING" },
  });
  if (claimed.count === 0) throw new AppError("CONFLICT", "Já existe uma sincronização em andamento.");

  const provider = positionsProvider();
  const run = await prisma.syncRun.create({ data: { portfolioId: p.id, provider: provider.id, status: "RUNNING" } });
  try {
    const result = await provider.fetchPositions(ctx.actor.id, now, opts);
    await prisma.$transaction(async (tx) => {
      await tx.position.deleteMany({ where: { portfolioId: p.id, source: "B3_DEMO" } });
      await tx.position.createMany({
        data: result.positions.map((pos) => ({
          portfolioId: p.id,
          ticker: pos.ticker,
          instrumentType: pos.instrumentType,
          quantity: pos.quantity,
          averagePrice: pos.averagePrice,
          referenceDate: result.referenceDate,
          source: "B3_DEMO" as const,
        })),
      });
      await tx.syncRun.update({
        where: { id: run.id },
        data: { status: "SUCCESS", finishedAt: new Date(), referenceDate: result.referenceDate, positionsCount: result.positions.length },
      });
      await tx.portfolio.update({
        where: { id: p.id },
        data: { connectionStatus: "CONNECTED", lastSyncAt: new Date(), lastReferenceDate: result.referenceDate, lastError: null },
      });
      await audit(ctx, { action: "portfolio.sync", resourceType: "portfolio", resourceId: p.id, metadata: { positions: result.positions.length } }, tx);
    });
    return { status: "SUCCESS" as const, positions: result.positions.length };
  } catch (err) {
    const message = err instanceof ProviderError ? err.message : "Falha inesperada na sincronização.";
    if (!(err instanceof ProviderError)) logger.error({ err, requestId: ctx.requestId }, "Erro na sincronização");
    await prisma.$transaction([
      prisma.syncRun.update({ where: { id: run.id }, data: { status: "ERROR", finishedAt: new Date(), message } }),
      prisma.portfolio.update({ where: { id: p.id }, data: { connectionStatus: "ERROR", lastError: message } }),
    ]);
    await audit(ctx, { action: "portfolio.sync_failed", resourceType: "portfolio", resourceId: p.id, metadata: { message } });
    return { status: "ERROR" as const, message };
  }
}

// ---------------------------------------------------------------------------
// Importação CSV
// ---------------------------------------------------------------------------

export type ImportRowStatus = CsvRowResult["status"] | "nova" | "atualizacao" | "identica";

export interface ImportPreview {
  fileName: string;
  fileHash: string;
  alreadyImported: boolean;
  fatal?: string;
  rows: (Omit<CsvRowResult, "status"> & { status: ImportRowStatus })[];
  summary: { total: number; novas: number; atualizacoes: number; identicas: number; erros: number };
}

function validateFile(fileName: string, text: string) {
  if (!/\.csv$/i.test(fileName)) throw new AppError("VALIDATION", "Envie um arquivo com extensão .csv.", { file: ["Formato não suportado."] });
  if (Buffer.byteLength(text, "utf8") > CSV_MAX_BYTES) throw new AppError("VALIDATION", "Arquivo acima do limite de 512 KB.", { file: ["Arquivo muito grande."] });
  if (text.includes("\u0000")) throw new AppError("VALIDATION", "Arquivo binário não é aceito.", { file: ["Conteúdo inválido."] });
}

export async function previewImport(ctx: Ctx, fileName: string, text: string): Promise<ImportPreview> {
  validateFile(fileName, text);
  const p = await ensurePortfolio(ctx.actor.id);
  const fileHash = createHash("sha256").update(text).digest("hex");
  const alreadyImported = (await prisma.importBatch.count({ where: { portfolioId: p.id, fileHash } })) > 0;
  const parsed = parsePositionsCsv(text);
  const summary = { total: parsed.rows.length, novas: 0, atualizacoes: 0, identicas: 0, erros: 0 };
  if (parsed.fatal) return { fileName, fileHash, alreadyImported, fatal: parsed.fatal, rows: [], summary };

  const existing = await prisma.position.findMany({ where: { portfolioId: p.id, source: "CSV" } });
  const byTicker = new Map(existing.map((e) => [e.ticker, e]));
  const rows = parsed.rows.map((r) => {
    if (r.status !== "valida" || !r.row) {
      summary.erros++;
      return r;
    }
    const current = byTicker.get(r.row.ticker);
    let status: ImportRowStatus = "nova";
    if (current) {
      const same =
        current.quantity === r.row.quantity &&
        current.averagePrice.equals(r.row.averagePrice) &&
        current.referenceDate.toISOString().slice(0, 10) === r.row.referenceDate &&
        current.instrumentType === r.row.instrumentType;
      status = same ? "identica" : "atualizacao";
    }
    if (status === "nova") summary.novas++;
    else if (status === "atualizacao") summary.atualizacoes++;
    else summary.identicas++;
    return { ...r, status };
  });
  return { fileName, fileHash, alreadyImported, rows, summary };
}

/** Confirma a importação: o arquivo é reprocessado no servidor (a prévia do cliente não é confiável). */
export async function confirmImport(ctx: Ctx, fileName: string, text: string) {
  const preview = await previewImport(ctx, fileName, text);
  if (preview.fatal) throw new AppError("VALIDATION", preview.fatal);
  if (preview.alreadyImported) throw new AppError("CONFLICT", "Este arquivo já foi importado anteriormente.");
  if (preview.summary.erros > 0) throw new AppError("VALIDATION", "Corrija as linhas com erro antes de importar.");
  const toApply = preview.rows.filter((r) => r.status === "nova" || r.status === "atualizacao");
  const p = await ensurePortfolio(ctx.actor.id);
  const batch = await prisma.$transaction(async (tx) => {
    const b = await tx.importBatch.create({
      data: {
        portfolioId: p.id,
        createdById: ctx.actor.id,
        fileName: fileName.slice(0, 200),
        fileHash: preview.fileHash,
        rowsTotal: preview.summary.total,
        rowsImported: toApply.length,
        rowsSkipped: preview.summary.total - toApply.length,
      },
    });
    for (const r of toApply) {
      const row = r.row!;
      const data = {
        instrumentType: row.instrumentType,
        quantity: row.quantity,
        averagePrice: row.averagePrice,
        referenceDate: new Date(`${row.referenceDate}T00:00:00.000Z`),
        importBatchId: b.id,
      };
      await tx.position.upsert({
        where: { portfolioId_ticker_source: { portfolioId: p.id, ticker: row.ticker, source: "CSV" } },
        create: { portfolioId: p.id, ticker: row.ticker, source: "CSV", ...data },
        update: data,
      });
    }
    await audit(
      ctx,
      { action: "portfolio.import_csv", resourceType: "import_batch", resourceId: b.id, metadata: { fileName, imported: toApply.length } },
      tx,
    );
    return b;
  });
  return { batchId: batch.id, imported: toApply.length, skipped: preview.summary.total - toApply.length };
}

export async function deleteCsvPosition(ctx: Ctx, positionId: string) {
  const p = await ensurePortfolio(ctx.actor.id);
  const res = await prisma.position.deleteMany({ where: { id: positionId, portfolioId: p.id, source: "CSV" } });
  if (res.count === 0) throw new AppError("NOT_FOUND", "Posição não encontrada.");
  await audit(ctx, { action: "portfolio.position_delete", resourceType: "position", resourceId: positionId });
}
