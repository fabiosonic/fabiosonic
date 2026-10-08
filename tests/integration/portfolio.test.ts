import { describe, expect, it } from "vitest";
import { prisma } from "@/server/db";
import * as portfolio from "@/server/services/portfolio";
import { previousBusinessDay } from "@/lib/dates";
import { makeUser } from "../support/factories";

const CSV = "ticker;quantidade;preco_medio;data_referencia\nPETR4;100;30,00;01/10/2026\nVALE3;50;60,50;01/10/2026\n";

describe("carteira: conexão demonstrativa e sincronização D+1", () => {
  it("conecta, sincroniza, registra histórico e desconecta", async () => {
    const { ctx, id } = await makeUser("USER");
    expect((await portfolio.getPortfolio(ctx)).portfolio.connectionStatus).toBe("DISCONNECTED");
    await expect(portfolio.syncNow(ctx)).rejects.toMatchObject({ code: "CONFLICT" });

    await portfolio.connectDemo(ctx);
    await expect(portfolio.connectDemo(ctx)).rejects.toMatchObject({ code: "CONFLICT" });
    const now = new Date("2026-10-12T15:00:00Z"); // segunda-feira
    const res = await portfolio.syncNow(ctx, {}, now);
    expect(res.status).toBe("SUCCESS");
    const p = await portfolio.getPortfolio(ctx);
    expect(p.portfolio.connectionStatus).toBe("CONNECTED");
    expect(p.portfolio.lastReferenceDate?.slice(0, 10)).toBe(previousBusinessDay(now).toISOString().slice(0, 10)); // sexta 09/10
    expect(p.positions.length).toBeGreaterThanOrEqual(3);
    expect(p.positions.every((x) => x.source === "B3_DEMO")).toBe(true);
    expect(p.syncRuns[0]).toMatchObject({ status: "SUCCESS", provider: "DEMO" });

    // Falha simulada → estado de erro e histórico
    const fail = await portfolio.syncNow(ctx, { simulateFailure: true });
    expect(fail.status).toBe("ERROR");
    const p2 = await portfolio.getPortfolio(ctx);
    expect(p2.portfolio.connectionStatus).toBe("ERROR");
    expect(p2.portfolio.lastError).toMatch(/simulada/);
    expect(p2.syncRuns[0]!.status).toBe("ERROR");
    // Recupera do erro
    expect((await portfolio.syncNow(ctx)).status).toBe("SUCCESS");

    await portfolio.disconnect(ctx);
    const p3 = await portfolio.getPortfolio(ctx);
    expect(p3.portfolio.connectionStatus).toBe("DISCONNECTED");
    expect(p3.positions.filter((x) => x.source === "B3_DEMO")).toHaveLength(0);
    const actions = (await prisma.auditEvent.findMany({ where: { actorId: id, resourceType: "portfolio" } })).map((e) => e.action);
    expect(actions).toEqual(expect.arrayContaining(["portfolio.connect", "portfolio.sync", "portfolio.sync_failed", "portfolio.disconnect"]));
  });

  it("impede sincronizações concorrentes", async () => {
    const { ctx } = await makeUser("USER");
    await portfolio.connectDemo(ctx);
    await prisma.portfolio.update({ where: { userId: ctx.actor.id }, data: { connectionStatus: "SYNCING" } });
    await expect(portfolio.syncNow(ctx)).rejects.toMatchObject({ code: "CONFLICT" });
  });
});

describe("carteira: importação CSV", () => {
  it("prévia, confirmação e prevenção de duplicidade", async () => {
    const { ctx } = await makeUser("USER");
    const preview = await portfolio.previewImport(ctx, "posicoes.csv", CSV);
    expect(preview.summary).toMatchObject({ total: 2, novas: 2, erros: 0 });
    expect(preview.alreadyImported).toBe(false);
    // A prévia não grava nada.
    expect((await portfolio.getPortfolio(ctx)).positions).toHaveLength(0);

    const done = await portfolio.confirmImport(ctx, "posicoes.csv", CSV);
    expect(done).toMatchObject({ imported: 2, skipped: 0 });
    const pos = (await portfolio.getPortfolio(ctx)).positions;
    expect(pos.map((p) => [p.ticker, p.quantity, p.averagePrice])).toEqual([
      ["PETR4", 100, "30"],
      ["VALE3", 50, "60.5"],
    ]);

    // Mesmo arquivo novamente: bloqueado.
    expect((await portfolio.previewImport(ctx, "posicoes.csv", CSV)).alreadyImported).toBe(true);
    await expect(portfolio.confirmImport(ctx, "posicoes.csv", CSV)).rejects.toMatchObject({ code: "CONFLICT" });

    // Arquivo diferente: linha idêntica ignorada, linha alterada atualizada, linha nova criada.
    const csv2 = "ticker;quantidade;preco_medio;data_referencia\nPETR4;100;30,00;01/10/2026\nVALE3;80;59,00;02/10/2026\nITUB4;10;33;02/10/2026\n";
    const p2 = await portfolio.previewImport(ctx, "posicoes2.csv", csv2);
    expect(p2.rows.map((r) => r.status)).toEqual(["identica", "atualizacao", "nova"]);
    const r2 = await portfolio.confirmImport(ctx, "posicoes2.csv", csv2);
    expect(r2).toMatchObject({ imported: 2, skipped: 1 });
    const after = (await portfolio.getPortfolio(ctx)).positions;
    expect(after.find((p) => p.ticker === "VALE3")).toMatchObject({ quantity: 80, averagePrice: "59" });
    expect(after).toHaveLength(3);
  });

  it("recusa arquivo com erros, extensão inválida ou conteúdo binário", async () => {
    const { ctx } = await makeUser("USER");
    await expect(portfolio.confirmImport(ctx, "x.csv", "ticker;quantidade;preco_medio;data_referencia\nPETR4;0;30;01/10/2026\n")).rejects.toMatchObject({ code: "VALIDATION" });
    await expect(portfolio.previewImport(ctx, "x.xlsx", CSV)).rejects.toMatchObject({ code: "VALIDATION" });
    await expect(portfolio.previewImport(ctx, "x.csv", "ticker\u0000")).rejects.toMatchObject({ code: "VALIDATION" });
    await expect(portfolio.previewImport(ctx, "x.csv", "a".repeat(600 * 1024))).rejects.toMatchObject({ code: "VALIDATION" });
    expect((await portfolio.getPortfolio(ctx)).positions).toHaveLength(0);
  });
});
