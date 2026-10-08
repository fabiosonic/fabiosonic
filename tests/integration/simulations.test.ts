import { describe, expect, it } from "vitest";
import { AppError } from "@/server/errors";
import { prisma } from "@/server/db";
import * as sims from "@/server/services/simulations";
import { makeUser } from "../support/factories";

describe("simulações: persistência e reabertura", () => {
  it("salva, reabre com os mesmos valores, atualiza e exclui", async () => {
    const { ctx } = await makeUser("USER");
    const input = {
      name: "Borboleta BOVA11",
      mode: "PREVISOES",
      underlyingTicker: "bova11",
      spotPrice: "125,30",
      fees: "12,50",
      expiration: "2026-12-18",
      notes: "Teste",
      scenarios: [
        { label: "Queda", price: "115" },
        { label: "Alta", price: "135,5" },
      ],
      legs: [
        { side: "BUY", instrument: "CALL", strike: "120", premium: "7,40", quantity: 100 },
        { side: "SELL", instrument: "CALL", strike: "125", premium: "4,30", quantity: 200 },
        { side: "BUY", instrument: "CALL", strike: "130", premium: "2,20", quantity: 100 },
      ],
    };
    const { id } = await sims.createSimulation(ctx, input);
    const s = await sims.getSimulation(ctx, id);
    expect(s).toMatchObject({ name: "Borboleta BOVA11", mode: "PREVISOES", underlyingTicker: "BOVA11", spotPrice: "125.3", fees: "12.5" });
    expect(s.expiration?.slice(0, 10)).toBe("2026-12-18");
    expect(s.scenarios).toEqual([
      { label: "Queda", price: "115" },
      { label: "Alta", price: "135.5" },
    ]);
    expect(s.legs.map((l) => [l.side, l.instrument, l.strike, l.premium, l.quantity])).toEqual([
      ["BUY", "CALL", "120", "7.4", 100],
      ["SELL", "CALL", "125", "4.3", 200],
      ["BUY", "CALL", "130", "2.2", 100],
    ]);
    // Débito 100 + custos 12,50
    expect(s.initialCashFlow).toBe("-112.50");

    await sims.updateSimulation(ctx, id, { ...input, name: "Renomeada", legs: input.legs.slice(0, 1) });
    const s2 = await sims.getSimulation(ctx, id);
    expect(s2.name).toBe("Renomeada");
    expect(s2.legs).toHaveLength(1);
    expect(await prisma.simulationLeg.count({ where: { simulationId: id } })).toBe(1);

    await sims.deleteSimulation(ctx, id);
    await expect(sims.getSimulation(ctx, id)).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(await prisma.auditEvent.count({ where: { resourceId: id, resourceType: "simulation" } })).toBe(3);
  });

  it("rejeita dados inválidos com erros por campo", async () => {
    const { ctx } = await makeUser("USER");
    try {
      await sims.createSimulation(ctx, { name: "", mode: "X", underlyingTicker: "??", spotPrice: "-1", legs: [] });
      expect.fail("deveria falhar");
    } catch (e) {
      expect(e).toBeInstanceOf(AppError);
      const err = e as AppError;
      expect(err.code).toBe("VALIDATION");
      expect(Object.keys(err.fieldErrors ?? {})).toEqual(expect.arrayContaining(["name", "mode", "underlyingTicker", "spotPrice", "legs"]));
    }
  });
});
