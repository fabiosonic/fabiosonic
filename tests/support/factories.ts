import { hashPassword } from "better-auth/crypto";
import { prisma } from "@/server/db";
import type { Ctx } from "@/server/context";
import type { Role } from "@/generated/prisma/enums";

export const PASSWORD = "Senha@Teste1";

let n = 0;
/** Cria um usuário isolado para o teste e devolve o contexto de serviço correspondente. */
export async function makeUser(role: Role = "USER", opts: { active?: boolean; isDemo?: boolean } = {}) {
  n++;
  const id = crypto.randomUUID();
  const email = `t${Date.now()}${n}${Math.floor(Math.random() * 1e6)}@teste.local`;
  await prisma.user.create({
    data: { id, email, name: `Teste ${role} ${n}`, role, emailVerified: true, active: opts.active ?? true, isDemo: opts.isDemo ?? false },
  });
  await prisma.account.create({
    data: { id: crypto.randomUUID(), accountId: id, providerId: "credential", userId: id, password: await hashPassword(PASSWORD) },
  });
  const ctx: Ctx = { actor: { id, email, name: `Teste ${role} ${n}`, role }, requestId: `req-${id}`, ip: "127.0.0.1" };
  return { id, email, ctx };
}

export const validStrategy = (overrides: Record<string, unknown> = {}) => ({
  title: "Trava de alta de teste",
  strategyType: "TRAVA_ALTA",
  assetTicker: "PETR4",
  summary: "Resumo de teste com mais de dez caracteres.",
  assumptions: "Premissas de teste com mais de dez caracteres.",
  riskNotes: "Riscos de teste com mais de dez caracteres.",
  referencePrice: "36,50",
  expiration: new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10),
  legs: [
    { side: "BUY", instrument: "CALL", strike: "36", premium: "1,85", quantity: 100 },
    { side: "SELL", instrument: "CALL", strike: "39", premium: "0,72", quantity: 100 },
  ],
  ...overrides,
});
