/** Utilitários de data. Datas de referência são tratadas como meia-noite UTC (coluna DATE). */

export function toDateOnly(d: Date): Date {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
}

/** Data de hoje no fuso de Brasília, como meia-noite UTC. */
export function todayBrasilia(now = new Date()): Date {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Sao_Paulo", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  return new Date(`${parts}T00:00:00.000Z`);
}

/**
 * Dia útil anterior (considera apenas fins de semana; feriados não são tratados no MVP).
 * Usado como data-base D+1: posições de D ficam disponíveis no dia útil seguinte.
 */
export function previousBusinessDay(d: Date): Date {
  const r = toDateOnly(d);
  do {
    r.setUTCDate(r.getUTCDate() - 1);
  } while (r.getUTCDay() === 0 || r.getUTCDay() === 6);
  return r;
}

export function addDays(d: Date, days: number): Date {
  const r = new Date(d);
  r.setUTCDate(r.getUTCDate() + days);
  return r;
}

/** Aceita "dd/mm/aaaa" ou "aaaa-mm-dd". Retorna null se inválida. */
export function parseDateInput(raw: string): Date | null {
  const s = raw.trim();
  let y: number, m: number, d: number;
  const br = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(s);
  const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s);
  if (br) [d, m, y] = [Number(br[1]), Number(br[2]), Number(br[3])];
  else if (iso) [y, m, d] = [Number(iso[1]), Number(iso[2]), Number(iso[3])];
  else return null;
  const date = new Date(Date.UTC(y, m - 1, d));
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== m - 1 || date.getUTCDate() !== d) return null;
  return date;
}

export function isoDate(d: Date | string | null | undefined): string {
  if (!d) return "";
  return new Date(d).toISOString().slice(0, 10);
}
