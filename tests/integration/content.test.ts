import { describe, expect, it } from "vitest";
import { prisma } from "@/server/db";
import * as content from "@/server/services/content";
import { makeUser, validStrategy } from "../support/factories";

describe("operações prontas e análises", () => {
  it("fluxo rascunho → edição → publicação → arquivamento → reativação, com histórico", async () => {
    const analyst = await makeUser("ANALYST");
    const user = await makeUser("USER");
    const { id } = await content.createStrategy(analyst.ctx, validStrategy());
    let s = await content.getStrategy(analyst.ctx, id);
    expect(s.status).toBe("DRAFT");
    expect(s.metrics).toMatchObject({ initialCashFlow: "-113.00", breakevens: ["37.13"], maxProfit: "187.00", maxLoss: "-113.00" });

    await content.updateStrategy(analyst.ctx, id, validStrategy({ title: "Título revisado", legs: [{ side: "BUY", instrument: "CALL", strike: "36", premium: "1,85", quantity: 200 }] }));
    s = await content.getStrategy(analyst.ctx, id);
    expect(s.title).toBe("Título revisado");
    expect(s.legs).toHaveLength(1);

    const before = await prisma.notification.count({ where: { userId: user.id } });
    await content.changeStrategyStatus(analyst.ctx, id, { action: "publish" });
    expect((await content.getStrategy(user.ctx, id)).status).toBe("PUBLISHED");
    expect(await prisma.notification.count({ where: { userId: user.id } })).toBe(before + 1);

    await expect(content.changeStrategyStatus(analyst.ctx, id, { action: "publish" })).rejects.toMatchObject({ code: "CONFLICT" });
    await content.changeStrategyStatus(analyst.ctx, id, { action: "archive" });
    await expect(content.getStrategy(user.ctx, id)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(content.updateStrategy(analyst.ctx, id, validStrategy())).rejects.toMatchObject({ code: "CONFLICT" });
    await content.changeStrategyStatus(analyst.ctx, id, { action: "unarchive" });
    expect((await content.getStrategy(analyst.ctx, id)).status).toBe("DRAFT");

    const revs = await content.listRevisions(analyst.ctx, "strategy", id);
    expect(revs.map((r) => r.action).reverse()).toEqual(["create", "update", "publish", "archive", "unarchive"]);
    const upd = revs.find((r) => r.action === "update")!;
    expect(Object.keys(upd.changes as object)).toEqual(expect.arrayContaining(["title", "pernas"]));
    expect(await prisma.auditEvent.count({ where: { resourceId: id, resourceType: "strategy" } })).toBe(5);
  });

  it("edição sem mudanças não gera revisão", async () => {
    const analyst = await makeUser("ANALYST");
    const { id } = await content.createStrategy(analyst.ctx, validStrategy());
    await content.updateStrategy(analyst.ctx, id, validStrategy());
    expect(await prisma.contentRevision.count({ where: { entityId: id } })).toBe(1);
  });

  it("valida ativo, vencimento e pernas", async () => {
    const analyst = await makeUser("ANALYST");
    await expect(content.createStrategy(analyst.ctx, validStrategy({ assetTicker: "XXXX9" }))).rejects.toMatchObject({ code: "VALIDATION" });
    await expect(content.createStrategy(analyst.ctx, validStrategy({ expiration: "2020-01-01" }))).rejects.toMatchObject({ code: "VALIDATION" });
    await expect(content.createStrategy(analyst.ctx, validStrategy({ legs: [{ side: "BUY", instrument: "CALL", premium: "1", quantity: 1 }] }))).rejects.toMatchObject({
      code: "VALIDATION",
    });
  });

  it("filtra por ativo, estratégia e mês de vencimento", async () => {
    const analyst = await makeUser("ANALYST");
    const exp = new Date(Date.now() + 40 * 86_400_000).toISOString().slice(0, 10);
    const { id } = await content.createStrategy(analyst.ctx, validStrategy({ assetTicker: "ABEV3", strategyType: "STRANGLE", expiration: exp }));
    const res = await content.listStrategies(analyst.ctx, { asset: "ABEV3", type: "STRANGLE", month: exp.slice(0, 7) });
    expect(res.items.map((s) => s.id)).toContain(id);
    const none = await content.listStrategies(analyst.ctx, { asset: "ABEV3", type: "BORBOLETA" });
    expect(none.items.some((s) => s.id === id)).toBe(false);
  });

  it("análises: publicação e visibilidade", async () => {
    const analyst = await makeUser("ANALYST");
    const user = await makeUser("USER");
    const { id } = await content.createAnalysis(analyst.ctx, { title: "Análise X", assetTicker: "PETR4", summary: "Resumo da análise X", body: "Corpo da análise com texto suficiente <script>alert(1)</script>" });
    await expect(content.getAnalysis(user.ctx, id)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await content.changeAnalysisStatus(analyst.ctx, id, { action: "publish" });
    const a = await content.getAnalysis(user.ctx, id);
    expect(a.status).toBe("PUBLISHED");
    // O conteúdo é armazenado como texto; a interface o exibe sem interpretar HTML.
    expect(a.body).toContain("<script>");
  });
});
