import "server-only";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  pageCount: number;
}

export function pageArgs(page = 1, pageSize = 20) {
  const p = Math.max(1, Math.floor(page));
  const s = Math.min(100, Math.max(1, Math.floor(pageSize)));
  return { skip: (p - 1) * s, take: s, page: p, pageSize: s };
}

export function toPage<T>(items: T[], total: number, page: number, pageSize: number): Page<T> {
  return { items, total, page, pageSize, pageCount: Math.max(1, Math.ceil(total / pageSize)) };
}

/** Serializa Decimal do Prisma como string (seguro para Client Components). */
export function dec(v: { toString(): string } | null | undefined): string | null {
  return v === null || v === undefined ? null : v.toString();
}

export function iso(d: Date | null | undefined): string | null {
  return d ? d.toISOString() : null;
}

/** Diferença entre campos (para histórico de alterações). Números decimais são comparados pelo valor. */
export function diffFields(before: Record<string, unknown>, after: Record<string, unknown>) {
  const norm = (v: unknown): unknown => {
    if (v === undefined || v === null) return null;
    if (v instanceof Date) return v.toISOString();
    const s = typeof v === "string" ? v : (v as { toString?: () => string }).toString?.() ?? v;
    return typeof s === "string" && /^-?\d+(\.\d+)?$/.test(s) ? Number(s) : s;
  };
  const changes: Record<string, { de: unknown; para: unknown }> = {};
  for (const key of Object.keys(after)) {
    const a = norm(before[key]);
    const b = norm(after[key]);
    if (JSON.stringify(a) !== JSON.stringify(b)) changes[key] = { de: a, para: b };
  }
  return changes;
}
