/**
 * Importação de posições via CSV.
 * Colunas (cabeçalho obrigatório, sem diferenciar maiúsculas/acentos):
 *   ticker; quantidade; preco_medio; data_referencia; tipo (opcional: ACAO, OPCAO, FII, ETF, OUTRO)
 * Separador ";" (recomendado com vírgula decimal) ou ",". Datas dd/mm/aaaa ou aaaa-mm-dd.
 */
import Papa from "papaparse";
import { parseDecimalInput } from "./format";
import { parseDateInput } from "./dates";

export const CSV_MAX_BYTES = 512 * 1024;
export const CSV_MAX_ROWS = 1000;

export type InstrumentType = "ACAO" | "OPCAO" | "FII" | "ETF" | "OUTRO";

export interface CsvPositionRow {
  line: number;
  ticker: string;
  quantity: number;
  averagePrice: string;
  referenceDate: string; // aaaa-mm-dd
  instrumentType: InstrumentType;
}

export interface CsvRowResult {
  line: number;
  raw: Record<string, string>;
  status: "valida" | "erro" | "duplicada_no_arquivo";
  errors: string[];
  row?: CsvPositionRow;
}

export interface CsvParseResult {
  rows: CsvRowResult[];
  fatal?: string;
}

const REQUIRED = ["ticker", "quantidade", "preco_medio", "data_referencia"] as const;
const TYPES: InstrumentType[] = ["ACAO", "OPCAO", "FII", "ETF", "OUTRO"];

function normalizeHeader(h: string) {
  return h
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, "_");
}

export function inferInstrumentType(ticker: string): InstrumentType {
  if (/^[A-Z]{4}[A-X]\d{2,4}[A-Z0-9]?$/.test(ticker)) return "OPCAO";
  if (/^[A-Z]{4}(3|4|5|6|7|8)F?$/.test(ticker)) return "ACAO";
  return "OUTRO";
}

export function parsePositionsCsv(text: string, today: Date = new Date()): CsvParseResult {
  if (text.length > CSV_MAX_BYTES) return { rows: [], fatal: "Arquivo acima do limite de 512 KB." };
  const clean = text.replace(/^﻿/, "");
  if (!clean.trim()) return { rows: [], fatal: "Arquivo vazio." };

  const parsed = Papa.parse<Record<string, string>>(clean, {
    header: true,
    skipEmptyLines: "greedy",
    delimitersToGuess: [";", ",", "\t"],
    transformHeader: normalizeHeader,
  });
  const headers = parsed.meta.fields ?? [];
  const missing = REQUIRED.filter((c) => !headers.includes(c));
  if (missing.length) return { rows: [], fatal: `Colunas obrigatórias ausentes: ${missing.join(", ")}.` };
  if (parsed.data.length === 0) return { rows: [], fatal: "Nenhuma linha de dados encontrada." };
  if (parsed.data.length > CSV_MAX_ROWS) return { rows: [], fatal: `Máximo de ${CSV_MAX_ROWS} linhas por arquivo.` };

  const todayUtc = Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate());
  const seen = new Map<string, number>();
  const rows: CsvRowResult[] = parsed.data.map((raw, i) => {
    const line = i + 2; // linha 1 é o cabeçalho
    const errors: string[] = [];
    const ticker = (raw.ticker ?? "").trim().toUpperCase();
    if (!/^[A-Z0-9]{4,12}$/.test(ticker)) errors.push("Ticker inválido.");

    const qtyRaw = (raw.quantidade ?? "").trim().replace(/\./g, "");
    const quantity = /^-?\d+$/.test(qtyRaw) ? Number(qtyRaw) : NaN;
    if (!Number.isSafeInteger(quantity) || quantity === 0) errors.push("Quantidade deve ser um inteiro diferente de zero.");
    else if (Math.abs(quantity) > 100_000_000) errors.push("Quantidade fora do limite.");

    const price = parseDecimalInput(raw.preco_medio ?? "");
    if (price === null || Number(price) < 0) errors.push("Preço médio inválido.");
    else if ((price.split(".")[1]?.length ?? 0) > 4) errors.push("Preço médio com mais de 4 casas decimais.");

    const date = parseDateInput(raw.data_referencia ?? "");
    if (!date) errors.push("Data de referência inválida.");
    else if (date.getTime() > todayUtc) errors.push("Data de referência no futuro.");

    let instrumentType: InstrumentType = inferInstrumentType(ticker);
    const tipo = (raw.tipo ?? "").trim().toUpperCase();
    if (tipo) {
      if (TYPES.includes(tipo as InstrumentType)) instrumentType = tipo as InstrumentType;
      else errors.push("Tipo inválido (use ACAO, OPCAO, FII, ETF ou OUTRO).");
    }

    if (errors.length) return { line, raw, status: "erro", errors };

    const prev = seen.get(ticker);
    if (prev !== undefined) {
      return { line, raw, status: "duplicada_no_arquivo", errors: [`Ticker repetido (já informado na linha ${prev}).`] };
    }
    seen.set(ticker, line);
    return {
      line,
      raw,
      status: "valida",
      errors: [],
      row: { line, ticker, quantity, averagePrice: price!, referenceDate: date!.toISOString().slice(0, 10), instrumentType },
    };
  });
  return { rows };
}
