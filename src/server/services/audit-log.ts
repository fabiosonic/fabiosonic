import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { requireRole } from "../authz";
import { pageArgs, toPage } from "./common";
import type { Prisma } from "@/generated/prisma/client";
import { parseDateInput } from "@/lib/dates";

export interface AuditQuery {
  page?: number;
  actor?: string;
  action?: string;
  resourceType?: string;
  requestId?: string;
  from?: string;
  to?: string;
}

export async function listAuditEvents(ctx: Ctx, q: AuditQuery) {
  requireRole(ctx.actor, "ADMIN");
  const { skip, take, page, pageSize } = pageArgs(q.page, 30);
  const where: Prisma.AuditEventWhereInput = {};
  if (q.actor) where.actorEmail = { contains: q.actor, mode: "insensitive" };
  if (q.action) where.action = { startsWith: q.action };
  if (q.resourceType) where.resourceType = q.resourceType;
  if (q.requestId) where.requestId = q.requestId;
  const from = q.from ? parseDateInput(q.from) : null;
  const to = q.to ? parseDateInput(q.to) : null;
  if (from || to) {
    where.createdAt = {};
    if (from) where.createdAt.gte = from;
    if (to) where.createdAt.lt = new Date(to.getTime() + 86_400_000);
  }
  const [items, total, resourceTypes] = await Promise.all([
    prisma.auditEvent.findMany({ where, orderBy: { createdAt: "desc" }, skip, take }),
    prisma.auditEvent.count({ where }),
    prisma.auditEvent.findMany({ distinct: ["resourceType"], select: { resourceType: true }, orderBy: { resourceType: "asc" } }),
  ]);
  return {
    ...toPage(
      items.map((e) => ({
        id: e.id,
        actorEmail: e.actorEmail,
        action: e.action,
        resourceType: e.resourceType,
        resourceId: e.resourceId,
        requestId: e.requestId,
        ipAddress: e.ipAddress,
        metadata: e.metadata,
        createdAt: e.createdAt.toISOString(),
      })),
      total,
      page,
      pageSize,
    ),
    resourceTypes: resourceTypes.map((r) => r.resourceType),
  };
}

export async function adminIndicators(ctx: Ctx) {
  requireRole(ctx.actor, "ADMIN");
  const since = new Date(Date.now() - 86_400_000);
  const [usersByRole, inactive, strategies, analyses, requests, simulations, audit24h, failedLogins24h, courses] = await Promise.all([
    prisma.user.groupBy({ by: ["role"], where: { active: true }, _count: { _all: true } }),
    prisma.user.count({ where: { active: false } }),
    prisma.strategy.groupBy({ by: ["status"], _count: { _all: true } }),
    prisma.analysis.groupBy({ by: ["status"], _count: { _all: true } }),
    prisma.analysisRequest.groupBy({ by: ["status"], _count: { _all: true } }),
    prisma.simulation.count(),
    prisma.auditEvent.count({ where: { createdAt: { gte: since } } }),
    prisma.auditEvent.count({ where: { createdAt: { gte: since }, action: "auth.login_failed" } }),
    prisma.course.count({ where: { status: "PUBLISHED" } }),
  ]);
  const byKey = <K extends string>(rows: { _count: { _all: number } }[], key: string) =>
    Object.fromEntries(rows.map((r) => [(r as unknown as Record<string, K>)[key], r._count._all])) as Record<string, number>;
  return {
    usersByRole: byKey(usersByRole, "role"),
    inactiveUsers: inactive,
    strategiesByStatus: byKey(strategies, "status"),
    analysesByStatus: byKey(analyses, "status"),
    requestsByStatus: byKey(requests, "status"),
    simulations,
    audit24h,
    failedLogins24h,
    publishedCourses: courses,
  };
}
