import "server-only";
import type { Role } from "@/generated/prisma/enums";

export interface Actor {
  id: string;
  email: string;
  name: string;
  role: Role;
}

/** Contexto de execução de um serviço: ator autenticado e rastreabilidade. */
export interface Ctx {
  actor: Actor;
  requestId: string;
  ip?: string | null;
}

export interface AuditCtx {
  actor?: Actor | null;
  requestId: string;
  ip?: string | null;
}

export function newRequestId() {
  return crypto.randomUUID();
}

export function clientIp(headers: Headers): string | null {
  const fwd = headers.get("x-forwarded-for");
  if (fwd) return fwd.split(",")[0]!.trim();
  return headers.get("x-real-ip");
}
