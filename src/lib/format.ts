const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const pct = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1, signDisplay: "exceptZero" });

type NumLike = number | string | { toString(): string } | null | undefined;

const toNum = (v: NumLike) => (v === null || v === undefined ? NaN : typeof v === "number" ? v : Number(v.toString()));

export function formatBRL(v: NumLike) {
  const n = toNum(v);
  return Number.isFinite(n) ? brl.format(n) : "—";
}
export function formatNumber(v: NumLike) {
  const n = toNum(v);
  return Number.isFinite(n) ? num2.format(n) : "—";
}
export function formatInt(v: NumLike) {
  const n = toNum(v);
  return Number.isFinite(n) ? int.format(n) : "—";
}
export function formatPct(v: NumLike) {
  const n = toNum(v);
  return Number.isFinite(n) ? `${pct.format(n)}%` : "—";
}

const dateOnly = new Intl.DateTimeFormat("pt-BR", { timeZone: "UTC", day: "2-digit", month: "2-digit", year: "numeric" });
const dateTime = new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
});
const dateLocal = new Intl.DateTimeFormat("pt-BR", { timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", year: "numeric" });

/** Datas sem horário (colunas DATE, armazenadas à meia-noite UTC). */
export function formatDate(d: Date | string | null | undefined) {
  if (!d) return "—";
  return dateOnly.format(new Date(d));
}
/** Data e hora no fuso de Brasília. */
export function formatDateTime(d: Date | string | null | undefined) {
  if (!d) return "—";
  return dateTime.format(new Date(d));
}
export function formatLocalDate(d: Date | string | null | undefined) {
  if (!d) return "—";
  return dateLocal.format(new Date(d));
}

/** Converte "1.234,56" ou "1234.56" em string numérica canônica "1234.56". */
export function parseDecimalInput(raw: string): string | null {
  const s = raw.trim().replace(/\s|R\$/g, "");
  if (!s) return null;
  let normalized = s;
  if (s.includes(",")) normalized = s.replace(/\./g, "").replace(",", ".");
  return /^-?\d+(\.\d+)?$/.test(normalized) ? normalized : null;
}
