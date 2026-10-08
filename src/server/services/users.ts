import "server-only";
import { hashPassword } from "better-auth/crypto";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { requireRole } from "../authz";
import { AppError, notFound } from "../errors";
import { parse } from "../validation";
import { audit } from "../audit";
import { userCreateSchema, userUpdateSchema } from "@/lib/schemas";
import { pageArgs, toPage } from "./common";
import type { Prisma } from "@/generated/prisma/client";
import type { Role } from "@/generated/prisma/enums";

export async function listUsers(ctx: Ctx, q: { page?: number; search?: string; role?: string; active?: string }) {
  requireRole(ctx.actor, "ADMIN");
  const { skip, take, page, pageSize } = pageArgs(q.page, 20);
  const where: Prisma.UserWhereInput = {};
  if (q.search) where.OR = [{ name: { contains: q.search, mode: "insensitive" } }, { email: { contains: q.search, mode: "insensitive" } }];
  if (q.role && ["ADMIN", "ANALYST", "USER"].includes(q.role)) where.role = q.role as Role;
  if (q.active === "true" || q.active === "false") where.active = q.active === "true";
  const [items, total] = await Promise.all([
    prisma.user.findMany({
      where,
      orderBy: [{ active: "desc" }, { name: "asc" }],
      skip,
      take,
      select: { id: true, name: true, email: true, role: true, active: true, isDemo: true, createdAt: true },
    }),
    prisma.user.count({ where }),
  ]);
  return toPage(items.map((u) => ({ ...u, createdAt: u.createdAt.toISOString() })), total, page, pageSize);
}

/** Cria usuário com senha (conta "credential" do better-auth). */
export async function createUser(ctx: Ctx, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(userCreateSchema, input);
  const exists = await prisma.user.findUnique({ where: { email: data.email } });
  if (exists) throw new AppError("CONFLICT", "Já existe um usuário com este e-mail.", { email: ["E-mail já cadastrado."] });
  const id = crypto.randomUUID();
  const hash = await hashPassword(data.password);
  const user = await prisma.$transaction(async (tx) => {
    const u = await tx.user.create({ data: { id, name: data.name, email: data.email, role: data.role, emailVerified: true } });
    await tx.account.create({ data: { id: crypto.randomUUID(), accountId: id, providerId: "credential", userId: id, password: hash } });
    await audit(ctx, { action: "user.create", resourceType: "user", resourceId: id, metadata: { email: data.email, role: data.role } }, tx);
    return u;
  });
  return { id: user.id };
}

export async function updateUser(ctx: Ctx, userId: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(userUpdateSchema, input);
  const user = await prisma.user.findUnique({ where: { id: userId } });
  if (!user) throw notFound("Usuário");
  if (userId === ctx.actor.id && (data.active === false || (data.role && data.role !== "ADMIN"))) {
    throw new AppError("CONFLICT", "Você não pode desativar nem rebaixar a própria conta.");
  }
  await prisma.$transaction(async (tx) => {
    await tx.user.update({ where: { id: userId }, data });
    // Desativar ou mudar perfil encerra as sessões abertas do usuário.
    if (data.active === false || (data.role && data.role !== user.role)) await tx.session.deleteMany({ where: { userId } });
    await audit(
      ctx,
      {
        action: "user.update",
        resourceType: "user",
        resourceId: userId,
        metadata: { de: { role: user.role, active: user.active }, para: data },
      },
      tx,
    );
  });
}
