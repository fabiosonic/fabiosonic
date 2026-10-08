import { describe, expect, it } from "vitest";
import { prisma } from "@/server/db";
import * as requests from "@/server/services/requests";
import { makeUser } from "../support/factories";

describe("pedidos de análise", () => {
  it("fluxo completo com histórico, status e notificações", async () => {
    const user = await makeUser("USER");
    const analyst = await makeUser("ANALYST");
    const { id } = await requests.createRequest(user.ctx, { subject: "Dúvida sobre travas", assetTicker: "PETR4", question: "Como calcular a perda máxima de uma trava de alta?" });
    // Equipe é notificada do novo pedido.
    expect(await prisma.notification.count({ where: { userId: analyst.id, link: `/solicitacoes/${id}` } })).toBe(1);

    await requests.changeRequestStatus(analyst.ctx, id, { status: "IN_ANALYSIS" });
    let r = await requests.getRequest(user.ctx, id);
    expect(r.status).toBe("IN_ANALYSIS");
    expect(r.assignedToName).toBe(analyst.ctx.actor.name);

    await requests.addMessage(analyst.ctx, id, { body: "A perda máxima é o débito inicial." });
    r = await requests.getRequest(user.ctx, id);
    expect(r.status).toBe("ANSWERED");
    expect(r.userEmail).toBeNull(); // e-mail visível apenas para a equipe
    expect(await prisma.notification.count({ where: { userId: user.id, link: `/solicitacoes/${id}` } })).toBe(2);

    await requests.addMessage(user.ctx, id, { body: "Obrigado!" });
    await expect(requests.changeRequestStatus(user.ctx, id, { status: "IN_ANALYSIS" })).rejects.toMatchObject({ code: "FORBIDDEN" });
    await requests.changeRequestStatus(user.ctx, id, { status: "CLOSED" });
    await expect(requests.addMessage(user.ctx, id, { body: "Mais uma" })).rejects.toMatchObject({ code: "CONFLICT" });

    r = await requests.getRequest(analyst.ctx, id);
    expect(r.closedAt).not.toBeNull();
    expect(r.events.map((e) => (e.kind === "STATUS_CHANGED" ? `${e.fromStatus}>${e.toStatus}` : e.kind))).toEqual([
      "CREATED",
      "OPEN>IN_ANALYSIS",
      "MESSAGE",
      "IN_ANALYSIS>ANSWERED",
      "MESSAGE",
      "ANSWERED>CLOSED",
    ]);
    const actions = (await prisma.auditEvent.findMany({ where: { resourceId: id }, orderBy: { createdAt: "asc" } })).map((e) => e.action);
    expect(actions).toEqual(["request.create", "request.status", "request.message", "request.message", "request.status"]);
  });

  it("filtra por situação e valida entrada", async () => {
    const user = await makeUser("USER");
    await requests.createRequest(user.ctx, { subject: "Pedido aberto", question: "Pergunta com tamanho suficiente para validar." });
    const open = await requests.listRequests(user.ctx, { status: "OPEN" });
    expect(open.items.length).toBe(1);
    expect((await requests.listRequests(user.ctx, { status: "CLOSED" })).items.length).toBe(0);
    await expect(requests.createRequest(user.ctx, { subject: "x", question: "curta" })).rejects.toMatchObject({ code: "VALIDATION" });
  });
});
