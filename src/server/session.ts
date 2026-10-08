import "server-only";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { Role } from "@/generated/prisma/enums";
import { getActorFromHeaders } from "./auth";
import { clientIp, newRequestId, type Ctx } from "./context";

/** Para páginas: exige sessão válida (e perfil, se informado); caso contrário redireciona. */
export async function requirePageCtx(roles?: Role[]): Promise<Ctx> {
  const h = await headers();
  const actor = await getActorFromHeaders(h);
  if (!actor) redirect("/login");
  if (roles && !roles.includes(actor.role)) redirect("/acesso-negado");
  return { actor, requestId: h.get("x-request-id") ?? newRequestId(), ip: clientIp(h) };
}

export async function getOptionalActor() {
  return getActorFromHeaders(await headers());
}
