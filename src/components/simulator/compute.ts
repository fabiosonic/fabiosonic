import { z } from "zod";
import { legSchema } from "@/lib/schemas";
import { parseDecimalInput } from "@/lib/format";
import { analyzeStrategy, chartSeries, defaultScenarioPrices, scenarioTable, Dec } from "@/lib/options/payoff";
import type { LegState, ScenarioState } from "./types";

export interface ComputeInput {
  legs: LegState[];
  spot: string;
  multiplier: number;
  fees: string;
  scenarios: ScenarioState[];
}

export interface ComputeOk {
  ok: true;
  initialCashFlow: number;
  flow: "CREDITO" | "DEBITO" | "NEUTRO";
  breakevens: number[];
  maxProfit: number | null;
  maxProfitUnlimited: boolean;
  maxProfitAt: number | null;
  maxLoss: number | null;
  maxLossUnlimited: boolean;
  maxLossAt: number | null;
  chart: { price: number; result: number }[];
  table: { price: number; result: number; changePct: number | null }[];
  scenarios: { label: string; price: number; result: number; changePct: number | null }[];
  reference: number;
}

export type ComputeResult = ComputeOk | { ok: false; legErrors: Record<number, Record<string, string>>; general: string[] };

/** Valida as entradas (mesmos schemas do servidor) e calcula os resultados no vencimento. */
export function compute(input: ComputeInput): ComputeResult {
  const general: string[] = [];
  const spot = parseDecimalInput(input.spot);
  if (!spot || Number(spot) <= 0) general.push("Informe o preço de referência do ativo (maior que zero).");
  const fees = input.fees.trim() === "" ? "0" : parseDecimalInput(input.fees);
  if (fees === null || Number(fees) < 0) general.push("Custos inválidos.");
  if (!input.legs.length) general.push("Inclua ao menos uma perna.");

  const legErrors: Record<number, Record<string, string>> = {};
  const legs = input.legs.map((l, i) => {
    const r = legSchema.safeParse({
      side: l.side,
      instrument: l.instrument,
      strike: l.instrument === "STOCK" ? null : l.strike,
      premium: l.premium,
      quantity: l.quantity,
      optionSymbol: l.optionSymbol || null,
    });
    if (!r.success) {
      legErrors[i] = Object.fromEntries(r.error.issues.map((iss) => [String(iss.path[0] ?? "_"), iss.message]));
      return null;
    }
    return r.data;
  });
  if (general.length || Object.keys(legErrors).length) return { ok: false, legErrors, general };

  const strategy = { legs: legs as z.output<typeof legSchema>[], multiplier: input.multiplier, fees: fees! };
  const a = analyzeStrategy(strategy);
  const prices = defaultScenarioPrices(spot!);
  const keySet = new Map(prices.map((p) => [p.toString(), p]));
  for (const b of a.breakevens) keySet.set(b.toDecimalPlaces(2).toString(), b.toDecimalPlaces(2));
  const all = [...keySet.values()].sort((x, y) => x.comparedTo(y));
  const table = scenarioTable(strategy, all, spot!).map((r) => ({
    price: r.price.toNumber(),
    result: r.result.toDecimalPlaces(2).toNumber(),
    changePct: r.changePct ? r.changePct.toDecimalPlaces(2).toNumber() : null,
  }));

  const validScenarios = input.scenarios
    .map((s) => ({ label: s.label.trim(), price: parseDecimalInput(s.price) }))
    .filter((s): s is { label: string; price: string } => Boolean(s.label) && s.price !== null);
  const scen = scenarioTable(strategy, validScenarios.map((s) => s.price), spot!).map((r, i) => ({
    label: validScenarios[i]!.label,
    price: r.price.toNumber(),
    result: r.result.toDecimalPlaces(2).toNumber(),
    changePct: r.changePct ? r.changePct.toDecimalPlaces(2).toNumber() : null,
  }));

  const n = (d: InstanceType<typeof Dec> | null) => (d ? d.toDecimalPlaces(2).toNumber() : null);
  return {
    ok: true,
    initialCashFlow: a.initialCashFlow.toDecimalPlaces(2).toNumber(),
    flow: a.flow,
    breakevens: a.breakevens.map((b) => b.toDecimalPlaces(2).toNumber()),
    maxProfit: n(a.maxProfit.value),
    maxProfitUnlimited: a.maxProfit.unlimited,
    maxProfitAt: n(a.maxProfit.at),
    maxLoss: n(a.maxLoss.value),
    maxLossUnlimited: a.maxLoss.unlimited,
    maxLossAt: n(a.maxLoss.at),
    chart: chartSeries(strategy, spot!),
    table,
    scenarios: scen,
    reference: Number(spot),
  };
}
