/**
 * Casos validados por cálculo independente (à mão), conforme docs/calculos.md.
 * Convenção: quantidade em unidades; compra = +1, venda = −1; resultado no vencimento.
 */
import { describe, expect, it } from "vitest";
import { analyzeStrategy, chartSeries, defaultScenarioPrices, initialCashFlow, payoffAt, scenarioTable, type LegInput } from "@/lib/options/payoff";

const n = (d: { toNumber(): number } | null) => (d === null ? null : Number(d.toNumber().toFixed(6)));
const call = (side: "BUY" | "SELL", strike: number, premium: number, quantity = 100): LegInput => ({ side, instrument: "CALL", strike, premium, quantity });
const put = (side: "BUY" | "SELL", strike: number, premium: number, quantity = 100): LegInput => ({ side, instrument: "PUT", strike, premium, quantity });

describe("opções simples", () => {
  it("compra de CALL: débito, equilíbrio, perda limitada e ganho ilimitado", () => {
    // K=36, prêmio 1,85, 100 unidades → débito 185; BE = 36 + 1,85 = 37,85
    const s = { legs: [call("BUY", 36, 1.85)] };
    const a = analyzeStrategy(s);
    expect(n(a.initialCashFlow)).toBe(-185);
    expect(a.flow).toBe("DEBITO");
    expect(a.breakevens.map(n)).toEqual([37.85]);
    expect(a.maxProfit.unlimited).toBe(true);
    expect(a.maxLoss.unlimited).toBe(false);
    expect(n(a.maxLoss.value)).toBe(-185);
    // Em S=40: (40−36−1,85)×100 = 215
    expect(n(payoffAt(s, 40))).toBe(215);
    expect(n(payoffAt(s, 30))).toBe(-185);
  });

  it("venda de CALL a descoberto: crédito e perda teoricamente ilimitada", () => {
    // K=64, prêmio 1,10 → crédito 110; BE = 65,10
    const a = analyzeStrategy({ legs: [call("SELL", 64, 1.1)] });
    expect(n(a.initialCashFlow)).toBe(110);
    expect(a.flow).toBe("CREDITO");
    expect(a.maxLoss.unlimited).toBe(true);
    expect(a.maxLoss.value).toBeNull();
    expect(n(a.maxProfit.value)).toBe(110);
    expect(a.breakevens.map(n)).toEqual([65.1]);
  });

  it("compra de PUT: ganho máximo limitado em S=0", () => {
    // K=33, prêmio 1,05 → BE 31,95; ganho máx (33−1,05)×100 = 3195 em S=0
    const a = analyzeStrategy({ legs: [put("BUY", 33, 1.05)] });
    expect(a.breakevens.map(n)).toEqual([31.95]);
    expect(a.maxProfit.unlimited).toBe(false);
    expect(n(a.maxProfit.value)).toBe(3195);
    expect(n(a.maxProfit.at)).toBe(0);
    expect(n(a.maxLoss.value)).toBe(-105);
  });

  it("venda de PUT: perda máxima limitada em S=0", () => {
    // K=26, prêmio 0,48 → BE 25,52; perda máx −(26−0,48)×100 = −2552
    const a = analyzeStrategy({ legs: [put("SELL", 26, 0.48)] });
    expect(a.breakevens.map(n)).toEqual([25.52]);
    expect(n(a.maxLoss.value)).toBe(-2552);
    expect(a.maxLoss.unlimited).toBe(false);
    expect(n(a.maxProfit.value)).toBe(48);
  });
});

describe("estratégias combinadas", () => {
  it("trava de alta com CALL 36/39", () => {
    // Débito (1,85−0,72)×100 = 113; BE 37,13; ganho máx (3−1,13)×100 = 187
    const a = analyzeStrategy({ legs: [call("BUY", 36, 1.85), call("SELL", 39, 0.72)] });
    expect(n(a.initialCashFlow)).toBe(-113);
    expect(a.breakevens.map(n)).toEqual([37.13]);
    expect(n(a.maxProfit.value)).toBe(187);
    expect(n(a.maxLoss.value)).toBe(-113);
    expect(a.maxProfit.unlimited || a.maxLoss.unlimited).toBe(false);
  });

  it("borboleta 120/125×2/130: dois pontos de equilíbrio", () => {
    // Débito 7,40 − 2×4,30 + 2,20 = 1,00 → 100; BEs 121 e 129; ganho máx (5−1)×100 = 400 em 125
    const a = analyzeStrategy({ legs: [call("BUY", 120, 7.4), call("SELL", 125, 4.3, 200), call("BUY", 130, 2.2)] });
    expect(n(a.initialCashFlow)).toBe(-100);
    expect(a.breakevens.map(n)).toEqual([121, 129]);
    expect(n(a.maxProfit.value)).toBe(400);
    expect(n(a.maxProfit.at)).toBe(125);
    expect(n(a.maxLoss.value)).toBe(-100);
  });

  it("straddle comprado: dois equilíbrios e ganho ilimitado", () => {
    // Débito (1,20+1,05)×100 = 225; BEs 33 ± 2,25
    const a = analyzeStrategy({ legs: [call("BUY", 33, 1.2), put("BUY", 33, 1.05)] });
    expect(a.breakevens.map(n)).toEqual([30.75, 35.25]);
    expect(a.maxProfit.unlimited).toBe(true);
    expect(n(a.maxLoss.value)).toBe(-225);
    expect(n(a.maxLoss.at)).toBe(33);
  });

  it("straddle vendido: perda ilimitada e dois equilíbrios", () => {
    const a = analyzeStrategy({ legs: [call("SELL", 33, 1.2), put("SELL", 33, 1.05)] });
    expect(a.maxLoss.unlimited).toBe(true);
    expect(n(a.maxProfit.value)).toBe(225);
    expect(a.breakevens.map(n)).toEqual([30.75, 35.25]);
  });

  it("venda coberta: ação + venda de CALL", () => {
    // Fluxo −6120 + 110 = −6010; ganho máx (64−61,20+1,10)×100 = 390; BE 60,10; perda máx em S=0: −6010
    const a = analyzeStrategy({
      legs: [{ side: "BUY", instrument: "STOCK", premium: 61.2, quantity: 100 }, call("SELL", 64, 1.1)],
    });
    expect(n(a.initialCashFlow)).toBe(-6010);
    expect(n(a.maxProfit.value)).toBe(390);
    expect(a.maxProfit.unlimited).toBe(false);
    expect(a.breakevens.map(n)).toEqual([60.1]);
    expect(n(a.maxLoss.value)).toBe(-6010);
    expect(n(a.slopeAtInfinity)).toBe(0);
  });

  it("ratio spread 1×2: equilíbrios múltiplos com perda ilimitada", () => {
    // Compra 100 CALL 30 @3, vende 200 CALL 35 @1 → débito 100; BE1 = 31; f(35) = 400; inclinação −100 → BE2 = 39
    const a = analyzeStrategy({ legs: [call("BUY", 30, 3), call("SELL", 35, 1, 200)] });
    expect(n(a.initialCashFlow)).toBe(-100);
    expect(a.breakevens.map(n)).toEqual([31, 39]);
    expect(n(a.maxProfit.value)).toBe(400);
    expect(a.maxLoss.unlimited).toBe(true);
  });

  it("custos e multiplicador alteram fluxo e equilíbrio", () => {
    // Compra CALL 36 @1,85 ×100, custos R$ 10 → fluxo −195; BE = 36 + 1,95 = 37,95
    const s = { legs: [call("BUY", 36, 1.85)], fees: 10 };
    expect(n(initialCashFlow(s))).toBe(-195);
    expect(analyzeStrategy(s).breakevens.map(n)).toEqual([37.95]);
    // Multiplicador 10: 1 unidade × 10 → equivale a 10 unidades
    expect(n(payoffAt({ legs: [call("BUY", 36, 1.85, 1)], multiplier: 10 }, 40))).toBe(21.5);
  });

  it("usa aritmética decimal exata (0,1 + 0,2)", () => {
    const a = analyzeStrategy({ legs: [put("SELL", 10, 0.1, 1), put("SELL", 10, 0.2, 1)] });
    expect(a.initialCashFlow.toString()).toBe("0.3");
  });
});

describe("validações e utilitários", () => {
  it("rejeita opção sem strike, quantidade inválida e prêmio negativo", () => {
    expect(() => analyzeStrategy({ legs: [{ side: "BUY", instrument: "CALL", premium: 1, quantity: 100 }] })).toThrow(/strike/);
    expect(() => analyzeStrategy({ legs: [call("BUY", 10, 1, 0)] })).toThrow(/Quantidade/);
    expect(() => analyzeStrategy({ legs: [call("BUY", 10, -1)] })).toThrow(/negativo/);
    expect(() => analyzeStrategy({ legs: [] })).toThrow();
    expect(() => payoffAt({ legs: [call("BUY", 10, 1)] }, -1)).toThrow();
  });

  it("gera cenários padrão de −20% a +20% e tabela com variação", () => {
    const prices = defaultScenarioPrices(100);
    expect(prices.map(n)).toEqual([80, 85, 90, 95, 100, 105, 110, 115, 120]);
    const rows = scenarioTable({ legs: [call("BUY", 100, 2)] }, [90, 110], 100);
    expect(rows.map((r) => [n(r.price), n(r.result), n(r.changePct)])).toEqual([
      [90, -200, -10],
      [110, 800, 10],
    ]);
  });

  it("série do gráfico inclui strikes e equilíbrios, ordenada e não negativa", () => {
    const pts = chartSeries({ legs: [call("BUY", 36, 1.85), call("SELL", 39, 0.72)] }, 36.5);
    const xs = pts.map((p) => p.price);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
    expect(xs).toContain(36);
    expect(xs).toContain(39);
    expect(xs).toContain(37.13);
    expect(Math.min(...xs)).toBeGreaterThanOrEqual(0);
  });
});
