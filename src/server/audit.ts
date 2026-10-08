import "server-only";
import type { Prisma } from "@/generated/prisma/client";
import type { Db } from "./db";
import { prisma } from "./db";
import { logger } from "./logger";
import type { AuditCtx } from "./context";

export interface AuditEntry {
  action: string;
  resourceType: string;
  resourceId?: string | null;
  /** Apenas dados não sensíveis (nunca senhas, tokens ou cookies). */
  metadata?: Prisma.InputJsonValue;
}

const FORBIDDEN_KEYS = /pass(word)?|senha|token|secret|cookie|authorization/i;

function sanitize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sanitize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([k]) => !FORBIDDEN_KEYS.test(k))
        .map(([k, v]) => [k, sanitize(v)]),
    );
  }
  return value;
}

/** Registra evento de auditoria (ator, ação, recurso, horário e requestId). */
export async function audit(ctx: AuditCtx, entry: AuditEntry, db: Db = prisma) {
  const metadata = entry.metadata === undefined ? undefined : (sanitize(entry.metadata) as Prisma.InputJsonValue);
  await db.auditEvent.create({
    data: {
      actorId: ctx.actor?.id ?? null,
      actorEmail: ctx.actor?.email ?? null,
      action: entry.action,
      resourceType: entry.resourceType,
      resourceId: entry.resourceId ?? null,
      requestId: ctx.requestId,
      ipAddress: ctx.ip ?? null,
      metadata,
    },
  });
  logger.info(
    { requestId: ctx.requestId, actorId: ctx.actor?.id, action: entry.action, resourceType: entry.resourceType, resourceId: entry.resourceId },
    "audit",
  );
}
