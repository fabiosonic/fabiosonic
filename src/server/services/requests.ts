import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { isStaff, STAFF } from "../authz";
import { AppError, notFound } from "../errors";
import { parse } from "../validation";
import { audit } from "../audit";
import { requestCreateSchema, requestMessageSchema, requestStatusSchema } from "@/lib/schemas";
import { REQUEST_STATUS_LABEL } from "@/lib/labels";
import { iso, pageArgs, toPage } from "./common";
import { notifyRoles, notifyUsers } from "./notifications";
import type { Prisma } from "@/generated/prisma/client";
import type { RequestStatus } from "@/generated/prisma/enums";

/** Escopo de visibilidade: usuário vê apenas os próprios pedidos; equipe vê todos. */
function scope(ctx: Ctx): Prisma.AnalysisRequestWhereInput {
  return isStaff(ctx.actor) ? {} : { userId: ctx.actor.id };
}

export async function listRequests(ctx: Ctx, q: { page?: number; status?: string; mine?: boolean }) {
  const { skip, take, page, pageSize } = pageArgs(q.page, 20);
  const where: Prisma.AnalysisRequestWhereInput = { ...scope(ctx) };
  if (q.status && q.status in REQUEST_STATUS_LABEL) where.status = q.status as RequestStatus;
  if (q.mine && isStaff(ctx.actor)) where.assignedToId = ctx.actor.id;
  const [items, total] = await Promise.all([
    prisma.analysisRequest.findMany({
      where,
      orderBy: { updatedAt: "desc" },
      skip,
      take,
      include: { user: { select: { name: true } }, assignedTo: { select: { name: true } }, _count: { select: { events: true } } },
    }),
    prisma.analysisRequest.count({ where }),
  ]);
  return toPage(
    items.map((r) => ({
      id: r.id,
      subject: r.subject,
      assetTicker: r.assetTicker,
      status: r.status,
      userName: r.user.name,
      assignedToName: r.assignedTo?.name ?? null,
      events: r._count.events,
      createdAt: r.createdAt.toISOString(),
      updatedAt: r.updatedAt.toISOString(),
    })),
    total,
    page,
    pageSize,
  );
}

export async function getRequest(ctx: Ctx, id: string) {
  const r = await prisma.analysisRequest.findFirst({
    where: { id, ...scope(ctx) },
    include: {
      user: { select: { name: true, email: true } },
      assignedTo: { select: { name: true } },
      events: { orderBy: { createdAt: "asc" }, include: { author: { select: { name: true, role: true } } } },
    },
  });
  if (!r) throw notFound("Pedido");
  return {
    id: r.id,
    subject: r.subject,
    assetTicker: r.assetTicker,
    question: r.question,
    status: r.status,
    isOwner: r.userId === ctx.actor.id,
    userName: r.user.name,
    userEmail: isStaff(ctx.actor) ? r.user.email : null,
    assignedToName: r.assignedTo?.name ?? null,
    closedAt: iso(r.closedAt),
    createdAt: r.createdAt.toISOString(),
    events: r.events.map((e) => ({
      id: e.id,
      kind: e.kind,
      body: e.body,
      fromStatus: e.fromStatus,
      toStatus: e.toStatus,
      authorName: e.author.name,
      authorRole: e.author.role,
      createdAt: e.createdAt.toISOString(),
    })),
  };
}

export async function createRequest(ctx: Ctx, input: unknown) {
  const data = parse(requestCreateSchema, input);
  const r = await prisma.$transaction(async (tx) => {
    const created = await tx.analysisRequest.create({
      data: { userId: ctx.actor.id, subject: data.subject, assetTicker: data.assetTicker, question: data.question },
    });
    await tx.requestEvent.create({ data: { requestId: created.id, authorId: ctx.actor.id, kind: "CREATED", toStatus: "OPEN" } });
    await notifyRoles(STAFF, { title: "Novo pedido de análise", body: data.subject, link: `/solicitacoes/${created.id}` }, tx, ctx.actor.id);
    await audit(ctx, { action: "request.create", resourceType: "analysis_request", resourceId: created.id }, tx);
    return created;
  });
  return { id: r.id };
}

export async function addMessage(ctx: Ctx, id: string, input: unknown) {
  const { body } = parse(requestMessageSchema, input);
  await prisma.$transaction(async (tx) => {
    const r = await tx.analysisRequest.findFirst({ where: { id, ...scope(ctx) } });
    if (!r) throw notFound("Pedido");
    if (r.status === "CLOSED") throw new AppError("CONFLICT", "Pedido encerrado não recebe novas mensagens.");
    const staffReply = isStaff(ctx.actor) && r.userId !== ctx.actor.id;
    await tx.requestEvent.create({ data: { requestId: id, authorId: ctx.actor.id, kind: "MESSAGE", body } });
    if (staffReply) {
      // Resposta da equipe muda o status para "respondido" e atribui o analista.
      const next: RequestStatus = "ANSWERED";
      if (r.status !== next) {
        await tx.requestEvent.create({ data: { requestId: id, authorId: ctx.actor.id, kind: "STATUS_CHANGED", fromStatus: r.status, toStatus: next } });
      }
      await tx.analysisRequest.update({ where: { id }, data: { status: next, assignedToId: r.assignedToId ?? ctx.actor.id } });
      await notifyUsers([r.userId], { title: "Seu pedido foi respondido", body: r.subject, link: `/solicitacoes/${id}` }, tx);
    } else {
      await tx.analysisRequest.update({ where: { id }, data: { updatedAt: new Date() } });
      const recipients = r.assignedToId ? [r.assignedToId] : [];
      if (recipients.length) await notifyUsers(recipients, { title: "Nova mensagem em pedido", body: r.subject, link: `/solicitacoes/${id}` }, tx);
      else await notifyRoles(STAFF, { title: "Nova mensagem em pedido", body: r.subject, link: `/solicitacoes/${id}` }, tx, ctx.actor.id);
    }
    await audit(ctx, { action: "request.message", resourceType: "analysis_request", resourceId: id }, tx);
  });
}

export async function changeRequestStatus(ctx: Ctx, id: string, input: unknown) {
  const { status } = parse(requestStatusSchema, input);
  await prisma.$transaction(async (tx) => {
    const r = await tx.analysisRequest.findFirst({ where: { id, ...scope(ctx) } });
    if (!r) throw notFound("Pedido");
    // O próprio usuário pode apenas encerrar seu pedido; demais transições são da equipe.
    if (!isStaff(ctx.actor) && status !== "CLOSED") throw new AppError("FORBIDDEN", "Você só pode encerrar o pedido.");
    if (r.status === status) throw new AppError("CONFLICT", "O pedido já está nesta situação.");
    await tx.analysisRequest.update({
      where: { id },
      data: {
        status,
        closedAt: status === "CLOSED" ? new Date() : null,
        ...(status === "IN_ANALYSIS" && isStaff(ctx.actor) && !r.assignedToId ? { assignedToId: ctx.actor.id } : {}),
      },
    });
    await tx.requestEvent.create({ data: { requestId: id, authorId: ctx.actor.id, kind: "STATUS_CHANGED", fromStatus: r.status, toStatus: status } });
    if (r.userId !== ctx.actor.id) {
      await notifyUsers(
        [r.userId],
        { title: `Pedido: ${REQUEST_STATUS_LABEL[status].toLowerCase()}`, body: r.subject, link: `/solicitacoes/${id}` },
        tx,
      );
    }
    await audit(ctx, { action: "request.status", resourceType: "analysis_request", resourceId: id, metadata: { de: r.status, para: status } }, tx);
  });
}
