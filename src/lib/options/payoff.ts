/**
 * Motor de payoff no vencimento para estratégias com opções e ações.
 *
 * Convenções (ver docs/calculos.md):
 * - Quantidade em unidades do ativo-objeto (na B3, 1 opção de ação = 1 ação; lote padrão de 100).
 * - `multiplier` multiplica todas as pernas (1 para opções de ações na B3).
 * - Sinal: compra (BUY) = +1, venda (SELL) = -1.
 * - Prêmio/preço por unidade, em R$. Para STOCK, `premium` é o preço de entrada da ação.
 * - Fluxo inicial = -Σ sinal·qtd·mult·prêmio − custos. Positivo = crédito; negativo = débito.
 * - Resultado no vencimento(S) = Σ sinal·qtd·mult·(valorIntrínseco(S) − prêmio) − custos.
 * - Custos (`fees`) são um valor total fixo em R$, cobrado uma vez.
 * - Domínio de preço: S ≥ 0. Não há modelo de precificação antes do vencimento.
 */
import Decimal from "decimal.js";

export const Dec = Decimal.clone({ precision: 40, rounding: Decimal.ROUND_HALF_EVEN });
export type Dec = InstanceType<typeof Dec>;

export type LegSide = "BUY" | "SELL";
export type LegInstrument = "CALL" | "PUT" | "STOCK";
export type Numeric = string | number | Dec;

export interface LegInput {
  side: LegSide;
  instrument: LegInstrument;
  strike?: Numeric | null;
  premium: Numeric;
  quantity: number;
}

export interface StrategyInput {
  legs: LegInput[];
  multiplier?: number;
  fees?: Numeric;
}

interface NormalizedLeg {
  sign: Dec;
  instrument: LegInstrument;
  strike: Dec | null;
  premium: Dec;
  units: Dec; // quantidade × multiplicador
}

export interface Extreme {
  /** Valor em R$ (null quando ilimitado). */
  value: Dec | null;
  unlimited: boolean;
  /** Preço do ativo-objeto onde o extremo ocorre (quando limitado). */
  at: Dec | null;
}

export interface StrategyAnalysis {
  initialCashFlow: Dec;
  flow: "CREDITO" | "DEBITO" | "NEUTRO";
  breakevens: Dec[];
  maxProfit: Extreme;
  maxLoss: Extreme;
  /** Inclinação do resultado para S → ∞ (R$ por R$ de variação do ativo). */
  slopeAtInfinity: Dec;
  breakpoints: Dec[];
}

function normalize(input: StrategyInput): NormalizedLeg[] {
  const mult = new Dec(input.multiplier ?? 1);
  return input.legs.map((leg) => {
    const strike = leg.strike === null || leg.strike === undefined || leg.strike === "" ? null : new Dec(leg.strike);
    if (leg.instrument !== "STOCK" && (strike === null || strike.lte(0))) {
      throw new Error("Pernas de opção exigem strike positivo.");
    }
    if (!Number.isInteger(leg.quantity) || leg.quantity <= 0) {
      throw new Error("Quantidade deve ser um inteiro positivo.");
    }
    const premium = new Dec(leg.premium);
    if (premium.isNeg()) throw new Error("Prêmio/preço não pode ser negativo.");
    return {
      sign: new Dec(leg.side === "BUY" ? 1 : -1),
      instrument: leg.instrument,
      strike: leg.instrument === "STOCK" ? null : strike,
      premium,
      units: new Dec(leg.quantity).mul(mult),
    };
  });
}

function intrinsic(leg: NormalizedLeg, s: Dec): Dec {
  switch (leg.instrument) {
    case "CALL":
      return Dec.max(s.sub(leg.strike!), 0);
    case "PUT":
      return Dec.max(leg.strike!.sub(s), 0);
    case "STOCK":
      return s;
  }
}

function fees(input: StrategyInput): Dec {
  const f = new Dec(input.fees ?? 0);
  if (f.isNeg()) throw new Error("Custos não podem ser negativos.");
  return f;
}

function evalNormalized(legs: NormalizedLeg[], fee: Dec, s: Dec): Dec {
  let total = new Dec(0);
  for (const leg of legs) total = total.add(leg.sign.mul(leg.units).mul(intrinsic(leg, s).sub(leg.premium)));
  return total.sub(fee);
}

/** Resultado da estratégia no vencimento para o preço `price` do ativo-objeto. */
export function payoffAt(input: StrategyInput, price: Numeric): Dec {
  const s = new Dec(price);
  if (s.isNeg()) throw new Error("Preço do ativo não pode ser negativo.");
  return evalNormalized(normalize(input), fees(input), s);
}

/** Fluxo financeiro na montagem: positivo = crédito recebido, negativo = débito pago. */
export function initialCashFlow(input: StrategyInput): Dec {
  const legs = normalize(input);
  let total = new Dec(0);
  for (const leg of legs) total = total.sub(leg.sign.mul(leg.units).mul(leg.premium));
  return total.sub(fees(input));
}

/** Pontos onde a função de payoff muda de inclinação (strikes), incluindo 0. */
function breakpointsOf(legs: NormalizedLeg[]): Dec[] {
  const set = new Map<string, Dec>();
  set.set("0", new Dec(0));
  for (const leg of legs) if (leg.strike) set.set(leg.strike.toString(), leg.strike);
  return [...set.values()].sort((a, b) => a.comparedTo(b));
}

export function analyzeStrategy(input: StrategyInput): StrategyAnalysis {
  const legs = normalize(input);
  if (legs.length === 0) throw new Error("Informe ao menos uma perna.");
  const fee = fees(input);
  const points = breakpointsOf(legs);
  const values = points.map((p) => evalNormalized(legs, fee, p));

  // Inclinação após o maior strike: CALL e STOCK crescem 1:1; PUT é constante.
  let slope = new Dec(0);
  for (const leg of legs) {
    if (leg.instrument === "CALL" || leg.instrument === "STOCK") slope = slope.add(leg.sign.mul(leg.units));
  }

  // Pontos de equilíbrio: payoff linear por partes entre breakpoints.
  const roots: Dec[] = [];
  const pushRoot = (r: Dec) => {
    if (r.lte(0)) return;
    if (!roots.some((x) => x.sub(r).abs().lt("1e-12"))) roots.push(r);
  };
  for (let i = 0; i < points.length; i++) {
    const a = points[i]!;
    const fa = values[i]!;
    if (fa.isZero()) pushRoot(a);
    if (i + 1 < points.length) {
      const b = points[i + 1]!;
      const fb = values[i + 1]!;
      if (!fa.isZero() && !fb.isZero() && fa.isNeg() !== fb.isNeg()) {
        pushRoot(a.add(fa.neg().mul(b.sub(a)).div(fb.sub(fa))));
      }
    }
  }
  const last = points[points.length - 1]!;
  const fLast = values[values.length - 1]!;
  // À direita do maior strike: cruza zero se o sinal de fLast for oposto ao da inclinação.
  if (!slope.isZero() && !fLast.isZero() && fLast.isNeg() === slope.gt(0)) {
    pushRoot(last.sub(fLast.div(slope)));
  }
  roots.sort((x, y) => x.comparedTo(y));

  const idxMax = values.reduce((best, v, i) => (v.gt(values[best]!) ? i : best), 0);
  const idxMin = values.reduce((best, v, i) => (v.lt(values[best]!) ? i : best), 0);

  // Atenção: em decimal.js, isPos() é verdadeiro para zero; usar comparações explícitas.
  const maxProfit: Extreme = slope.gt(0)
    ? { value: null, unlimited: true, at: null }
    : { value: values[idxMax]!, unlimited: false, at: points[idxMax]! };
  const maxLoss: Extreme = slope.lt(0)
    ? { value: null, unlimited: true, at: null }
    : { value: values[idxMin]!, unlimited: false, at: points[idxMin]! };

  const flowValue = initialCashFlow(input);
  return {
    initialCashFlow: flowValue,
    flow: flowValue.isZero() ? "NEUTRO" : flowValue.gt(0) ? "CREDITO" : "DEBITO",
    breakevens: roots,
    maxProfit,
    maxLoss,
    slopeAtInfinity: slope,
    breakpoints: points,
  };
}

export interface ScenarioRow {
  price: Dec;
  result: Dec;
  /** Variação do ativo em relação ao preço de referência (%). */
  changePct: Dec | null;
}

export function scenarioTable(input: StrategyInput, prices: Numeric[], reference?: Numeric): ScenarioRow[] {
  const legs = normalize(input);
  const fee = fees(input);
  const ref = reference !== undefined ? new Dec(reference) : null;
  return prices.map((p) => {
    const price = new Dec(p);
    return {
      price,
      result: evalNormalized(legs, fee, price),
      changePct: ref && !ref.isZero() ? price.sub(ref).div(ref).mul(100) : null,
    };
  });
}

/** Preços padronizados para a tabela de cenários: variações percentuais sobre a referência. */
export function defaultScenarioPrices(reference: Numeric, steps: number[] = [-20, -15, -10, -5, 0, 5, 10, 15, 20]): Dec[] {
  const ref = new Dec(reference);
  return steps.map((pct) => ref.mul(new Dec(100).add(pct)).div(100).toDecimalPlaces(2));
}

/** Pontos para o gráfico: amostragem uniforme + breakpoints + equilíbrios (todos no domínio S ≥ 0). */
export function chartSeries(input: StrategyInput, reference: Numeric, samples = 80): { price: number; result: number }[] {
  const legs = normalize(input);
  const fee = fees(input);
  const ref = new Dec(reference);
  const strikes = legs.filter((l) => l.strike).map((l) => l.strike!);
  const lo = Dec.min(ref, ...(strikes.length ? strikes : [ref])).mul(0.7);
  const hi = Dec.max(ref, ...(strikes.length ? strikes : [ref])).mul(1.3);
  const step = hi.sub(lo).div(samples);
  const xs = new Map<string, Dec>();
  for (let i = 0; i <= samples; i++) {
    const x = lo.add(step.mul(i)).toDecimalPlaces(4);
    xs.set(x.toString(), x);
  }
  for (const k of strikes) if (k.gte(lo) && k.lte(hi)) xs.set(k.toString(), k);
  for (const r of analyzeStrategy(input).breakevens) if (r.gte(lo) && r.lte(hi)) xs.set(r.toDecimalPlaces(4).toString(), r.toDecimalPlaces(4));
  return [...xs.values()]
    .sort((a, b) => a.comparedTo(b))
    .map((x) => ({ price: x.toNumber(), result: evalNormalized(legs, fee, x).toDecimalPlaces(2).toNumber() }));
}
