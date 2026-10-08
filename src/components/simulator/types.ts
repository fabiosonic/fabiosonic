export type Side = "BUY" | "SELL";
export type Instrument = "CALL" | "PUT" | "STOCK";
export type Mode = "RAPIDA" | "CLASSICA" | "PREVISOES";

/** Estado de edição (strings, como digitado pelo usuário). */
export interface LegState {
  key: string;
  side: Side;
  instrument: Instrument;
  strike: string;
  premium: string;
  quantity: string;
  optionSymbol: string;
}

export interface ScenarioState {
  key: string;
  label: string;
  price: string;
}

export interface SimulatorInitial {
  id?: string;
  name: string;
  mode: Mode;
  underlyingTicker: string;
  spotPrice: string;
  multiplier: number;
  fees: string;
  expiration: string; // aaaa-mm-dd ou ""
  notes: string;
  sourceStrategyId?: string | null;
  legs: Omit<LegState, "key">[];
  scenarios: Omit<ScenarioState, "key">[];
}

let seq = 0;
/** Chave para itens adicionados no cliente (após a hidratação). */
export const newKey = () => `n${Date.now().toString(36)}${(seq++).toString(36)}`;
/** Chave determinística para o estado inicial (igual no servidor e no cliente). */
export const initialKey = (i: number) => `i${i}`;

export const emptyLeg = (key: string = newKey()): LegState => ({ key, side: "BUY", instrument: "CALL", strike: "", premium: "", quantity: "100", optionSymbol: "" });

/** Exibe número canônico ("36.5") no formato brasileiro de edição ("36,50"). */
export function toInput(v: string | null | undefined, decimals = 2) {
  if (v === null || v === undefined || v === "") return "";
  const n = Number(v);
  if (!Number.isFinite(n)) return v;
  return n.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: 4, useGrouping: false });
}
