import "server-only";
import { prisma, type Db } from "../db";
import type { Ctx } from "../context";
import { notFound } from "../errors";
import { pageArgs, toPage, iso } from "./common";
import type { Role } from "@/generated/prisma/enums";

export interface NewNotification {
  title: string;
  body: string;
  link?: string | null;
}

export async function notifyUsers(userIds: string[], n: NewNotification, db: Db = prisma) {
  const ids = [...new Set(userIds)];
  if (!ids.length) return;
  await db.notification.createMany({ data: ids.map((userId) => ({ userId, title: n.title, body: n.body, link: n.link ?? null })) });
}

export async function notifyRoles(roles: Role[], n: NewNotification, db: Db = prisma, exceptUserId?: string) {
  const users = await db.user.findMany({ where: { role: { in: roles }, active: true }, select: { id: true } });
  await notifyUsers(
    users.map((u) => u.id).filter((id) => id !== exceptUserId),
    n,
    db,
  );
}

export async function listNotifications(ctx: Ctx, opts: { page?: number; unreadOnly?: boolean } = {}) {
  const { skip, take, page, pageSize } = pageArgs(opts.page, 20);
  const where = { userId: ctx.actor.id, ...(opts.unreadOnly ? { readAt: null } : {}) };
  const [items, total] = await Promise.all([
    prisma.notification.findMany({ where, orderBy: { createdAt: "desc" }, skip, take }),
    prisma.notification.count({ where }),
  ]);
  return toPage(
    items.map((n) => ({ id: n.id, title: n.title, body: n.body, link: n.link, readAt: iso(n.readAt), createdAt: n.createdAt.toISOString() })),
    total,
    page,
    pageSize,
  );
}

export async function unreadCount(ctx: Ctx) {
  return prisma.notification.count({ where: { userId: ctx.actor.id, readAt: null } });
}

export async function markRead(ctx: Ctx, id: string) {
  // Propriedade verificada pelo filtro userId: notificações de terceiros parecem inexistentes.
  const res = await prisma.notification.updateMany({ where: { id, userId: ctx.actor.id, readAt: null }, data: { readAt: new Date() } });
  if (res.count === 0) {
    const exists = await prisma.notification.count({ where: { id, userId: ctx.actor.id } });
    if (!exists) throw notFound("Notificação");
  }
}

export async function markAllRead(ctx: Ctx) {
  const res = await prisma.notification.updateMany({ where: { userId: ctx.actor.id, readAt: null }, data: { readAt: new Date() } });
  return res.count;
}
