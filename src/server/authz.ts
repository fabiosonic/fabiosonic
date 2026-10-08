import type { Role } from "@/generated/prisma/enums";
import { forbidden } from "./errors";
import type { Actor } from "./context";

export const STAFF: Role[] = ["ADMIN", "ANALYST"];

export const isAdmin = (a: Actor) => a.role === "ADMIN";
export const isStaff = (a: Actor) => STAFF.includes(a.role);

/** Garante que o ator possua um dos perfis informados. */
export function requireRole(actor: Actor, ...roles: Role[]) {
  if (!roles.includes(actor.role)) throw forbidden();
}
