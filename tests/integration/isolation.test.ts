import { describe, expect, it } from "vitest";
import { AppError } from "@/server/errors";
import { prisma } from "@/server/db";
import * as sims from "@/server/services/simulations";
import * as requests from "@/server/services/requests";
import * as notifications from "@/server/services/notifications";
import * as portfolio from "@/server/services/portfolio";
import { makeUser } from "../support/factories";

const sim = {
  name: "Minha simulação",
  mode: "CLASSICA",
  underlyingTicker: "PETR4",
  spotPrice: "36,50",
  legs: [{ side: "BUY", instrument: "CALL", strike: "36", premium: "1,85", quantity: 100 }],
};

async function code(p: Promise<unknown>) {
  try {
    await p;
    return "OK";
  } catch (e) {
    if (e instanceof AppError) return e.code;
    throw e;
  }
}

describe("isolamento de dados entre usuários", () => {
  it("simulações de outro usuário são inacessíveis (inclusive para administrador)", async () => {
    const a = await makeUser("USER");
    const b = await makeUser("USER");
    const admin = await makeUser("ADMIN");
    const { id } = await sims.createSimulation(a.ctx, sim);
    expect(await code(sims.getSimulation(b.ctx, id))).toBe("NOT_FOUND");
    expect(await code(sims.updateSimulation(b.ctx, id, sim))).toBe("NOT_FOUND");
    expect(await code(sims.deleteSimulation(b.ctx, id))).toBe("NOT_FOUND");
    expect(await code(sims.getSimulation(admin.ctx, id))).toBe("NOT_FOUND");
    expect((await sims.listSimulations(b.ctx, {})).items.some((s) => s.id === id)).toBe(false);
    expect((await sims.getSimulation(a.ctx, id)).name).toBe("Minha simulação");
  });

  it("pedidos de análise de outro usuário são invisíveis; equipe enxerga todos", async () => {
    const a = await makeUser("USER");
    const b = await makeUser("USER");
    const analyst = await makeUser("ANALYST");
    const { id } = await requests.createRequest(a.ctx, { subject: "Pedido privado", question: "Conteúdo privado do usuário A, com detalhes." });
    expect(await code(requests.getRequest(b.ctx, id))).toBe("NOT_FOUND");
    expect(await code(requests.addMessage(b.ctx, id, { body: "intrusão" }))).toBe("NOT_FOUND");
    expect(await code(requests.changeRequestStatus(b.ctx, id, { status: "CLOSED" }))).toBe("NOT_FOUND");
    expect((await requests.listRequests(b.ctx, {})).items.some((r) => r.id === id)).toBe(false);
    expect((await requests.getRequest(analyst.ctx, id)).subject).toBe("Pedido privado");
  });

  it("notificações e posições de outro usuário não podem ser alteradas", async () => {
    const a = await makeUser("USER");
    const b = await makeUser("USER");
    const n = await prisma.notification.create({ data: { userId: a.id, title: "t", body: "b" } });
    expect(await code(notifications.markRead(b.ctx, n.id))).toBe("NOT_FOUND");
    expect((await prisma.notification.findUnique({ where: { id: n.id } }))!.readAt).toBeNull();

    await portfolio.confirmImport(a.ctx, "a.csv", "ticker;quantidade;preco_medio;data_referencia\nPETR4;100;30,00;01/10/2026\n");
    const pos = await prisma.position.findFirst({ where: { portfolio: { userId: a.id } } });
    expect(await code(portfolio.deleteCsvPosition(b.ctx, pos!.id))).toBe("NOT_FOUND");
    expect(await prisma.position.count({ where: { id: pos!.id } })).toBe(1);
  });
});

describe("concorrência", () => {
  it("criação simultânea da carteira do mesmo usuário não falha", async () => {
    const u = await makeUser("USER");
    const results = await Promise.all(Array.from({ length: 5 }, () => portfolio.getPortfolio(u.ctx)));
    expect(new Set(results.map((r) => r.portfolio.id)).size).toBe(1);
  });
});
