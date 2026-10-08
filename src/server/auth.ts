import "server-only";
import { betterAuth } from "better-auth";
import { prismaAdapter } from "better-auth/adapters/prisma";
import { APIError, createAuthMiddleware } from "better-auth/api";
import { nextCookies } from "better-auth/next-js";
import { prisma } from "./db";
import { env, isDemoEnv } from "./env";
import { audit } from "./audit";
import { sendEmail } from "./email";
import { clientIp, newRequestId, type Actor } from "./context";
import type { Role } from "@/generated/prisma/enums";

function reqMeta(headers?: Headers | null) {
  return {
    requestId: headers?.get("x-request-id") ?? newRequestId(),
    ip: headers ? clientIp(headers) : null,
  };
}

async function actorById(id: string): Promise<Actor | null> {
  const u = await prisma.user.findUnique({ where: { id }, select: { id: true, email: true, name: true, role: true } });
  return u;
}

const config = env();

export const auth = betterAuth({
  appName: "Plataforma de Opções",
  baseURL: config.APP_URL,
  secret: config.BETTER_AUTH_SECRET,
  trustedOrigins: [config.APP_URL],
  database: prismaAdapter(prisma, { provider: "postgresql" }),
  user: {
    additionalFields: {
      role: { type: "string", input: false, defaultValue: "USER" },
      active: { type: "boolean", input: false, defaultValue: true },
      isDemo: { type: "boolean", input: false, defaultValue: false },
    },
  },
  session: {
    expiresIn: 60 * 60 * 12, // 12 horas
    updateAge: 60 * 60, // renova a cada 1 hora de uso
  },
  emailAndPassword: {
    enabled: true,
    // Cadastro público desativado: usuários são criados pelo administrador.
    disableSignUp: true,
    minPasswordLength: 8,
    maxPasswordLength: 128,
    resetPasswordTokenExpiresIn: 60 * 30, // 30 minutos, uso único
    revokeSessionsOnPasswordReset: true,
    sendResetPassword: async ({ user, url }, request) => {
      const meta = reqMeta(request?.headers);
      await sendEmail({
        to: user.email,
        subject: "Recuperação de acesso",
        body: [
          `Olá, ${user.name}.`,
          "",
          "Recebemos um pedido para redefinir sua senha. O link abaixo é válido por 30 minutos e pode ser usado uma única vez:",
          url,
          "",
          "Se você não fez este pedido, ignore esta mensagem.",
        ].join("\n"),
      });
      await audit(
        { ...meta, actor: await actorById(user.id) },
        { action: "auth.password_reset_requested", resourceType: "user", resourceId: user.id },
      );
    },
    onPasswordReset: async ({ user }, request) => {
      await audit(
        { ...reqMeta(request?.headers), actor: await actorById(user.id) },
        { action: "auth.password_reset_completed", resourceType: "user", resourceId: user.id },
      );
    },
  },
  rateLimit: {
    enabled: true,
    storage: "database",
    window: 60,
    max: 200,
    customRules: {
      "/sign-in/email": { window: config.AUTH_RATE_LIMIT_SIGNIN_WINDOW, max: config.AUTH_RATE_LIMIT_SIGNIN_MAX },
      "/request-password-reset": { window: config.AUTH_RATE_LIMIT_RESET_WINDOW, max: config.AUTH_RATE_LIMIT_RESET_MAX },
      "/reset-password": { window: config.AUTH_RATE_LIMIT_RESET_WINDOW, max: 10 },
    },
  },
  advanced: {
    useSecureCookies: config.APP_URL.startsWith("https://"),
    ipAddress: { ipAddressHeaders: ["x-forwarded-for", "x-real-ip"] },
  },
  databaseHooks: {
    session: {
      create: {
        // Bloqueia contas desativadas e contas demonstrativas fora do ambiente demo.
        before: async (session) => {
          const user = await prisma.user.findUnique({ where: { id: session.userId } });
          if (!user || !user.active) {
            throw new APIError("FORBIDDEN", { message: "Conta desativada. Procure o administrador." });
          }
          if (user.isDemo && !isDemoEnv()) {
            throw new APIError("FORBIDDEN", { message: "Contas de demonstração não são permitidas neste ambiente." });
          }
        },
        after: async (session, context) => {
          await audit(
            { ...reqMeta(context?.headers ?? null), actor: await actorById(session.userId) },
            { action: "auth.login", resourceType: "session", resourceId: session.id },
          );
        },
      },
    },
  },
  hooks: {
    before: createAuthMiddleware(async (ctx) => {
      if (ctx.path === "/sign-out" && ctx.headers) {
        const session = await auth.api.getSession({ headers: ctx.headers }).catch(() => null);
        if (session) {
          await audit(
            { ...reqMeta(ctx.headers), actor: await actorById(session.user.id) },
            { action: "auth.logout", resourceType: "session", resourceId: session.session.id },
          );
        }
      }
    }),
    after: createAuthMiddleware(async (ctx) => {
      if (ctx.path === "/sign-in/email" && ctx.context.returned instanceof APIError) {
        const email = typeof ctx.body?.email === "string" ? ctx.body.email.slice(0, 200) : null;
        await audit(
          { ...reqMeta(ctx.headers ?? null), actor: null },
          { action: "auth.login_failed", resourceType: "session", metadata: { email } },
        );
      }
    }),
  },
  plugins: [nextCookies()],
});

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: Role;
  active: boolean;
  isDemo: boolean;
}

/** Resolve o ator a partir dos cabeçalhos (cookie de sessão). Retorna null se ausente/expirada. */
export async function getActorFromHeaders(headers: Headers): Promise<Actor | null> {
  const session = await auth.api.getSession({ headers });
  if (!session) return null;
  const user = session.user as unknown as SessionUser;
  if (!user.active) return null;
  if (user.isDemo && !isDemoEnv()) return null;
  return { id: user.id, email: user.email, name: user.name, role: user.role };
}
