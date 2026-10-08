import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";
import { auth, getActorFromHeaders } from "@/server/auth";
import { prisma } from "@/server/db";
import { resetEnvCache } from "@/server/env";
import { route } from "@/server/api";
import { makeUser, PASSWORD } from "../support/factories";

const BASE = process.env.APP_URL ?? "http://localhost:3000";
let ipSeq = 0;
const nextIp = () => `198.51.100.${(ipSeq = (ipSeq + 1) % 250) + 1}`;

function authRequest(path: string, body: unknown, opts: { ip?: string; cookie?: string; origin?: string | null } = {}) {
  const headers = new Headers({ "content-type": "application/json", "x-forwarded-for": opts.ip ?? nextIp() });
  if (opts.origin !== null) headers.set("origin", opts.origin ?? BASE);
  if (opts.cookie) headers.set("cookie", opts.cookie);
  return auth.handler(new Request(`${BASE}/api/auth${path}`, { method: "POST", headers, body: JSON.stringify(body) }));
}

function sessionCookie(res: Response) {
  const raw = res.headers.getSetCookie().find((c) => c.includes("session_token="));
  return raw ? raw.split(";")[0]! : null;
}

async function signIn(email: string, password = PASSWORD, ip?: string) {
  const res = await authRequest("/sign-in/email", { email, password }, { ip });
  return { res, cookie: sessionCookie(res) };
}

describe("login e logout", () => {
  it("login válido cria sessão em cookie HttpOnly e registra auditoria", async () => {
    const u = await makeUser("USER");
    const { res, cookie } = await signIn(u.email);
    expect(res.status).toBe(200);
    const setCookie = res.headers.getSetCookie().join(";");
    expect(setCookie).toMatch(/HttpOnly/i);
    expect(setCookie).toMatch(/SameSite=Lax/i);
    const actor = await getActorFromHeaders(new Headers({ cookie: cookie! }));
    expect(actor).toMatchObject({ id: u.id, role: "USER" });
    const ev = await prisma.auditEvent.findFirst({ where: { actorId: u.id, action: "auth.login" } });
    expect(ev).not.toBeNull();
  });

  it("senha incorreta é rejeitada e registrada sem a senha", async () => {
    const u = await makeUser("USER");
    const { res, cookie } = await signIn(u.email, "senha-errada-123");
    expect(res.status).toBe(401);
    expect(cookie).toBeNull();
    const ev = await prisma.auditEvent.findFirst({ where: { action: "auth.login_failed" }, orderBy: { createdAt: "desc" } });
    expect(ev?.metadata).toEqual({ email: u.email });
    expect(JSON.stringify(ev)).not.toContain("senha-errada-123");
  });

  it("logout encerra a sessão", async () => {
    const u = await makeUser("USER");
    const { cookie } = await signIn(u.email);
    const out = await authRequest("/sign-out", {}, { cookie: cookie! });
    expect(out.status).toBe(200);
    expect(await getActorFromHeaders(new Headers({ cookie: cookie! }))).toBeNull();
    expect(await prisma.auditEvent.count({ where: { actorId: u.id, action: "auth.logout" } })).toBe(1);
  });

  it("sessão expirada não autentica", async () => {
    const u = await makeUser("USER");
    const { cookie } = await signIn(u.email);
    await prisma.session.updateMany({ where: { userId: u.id }, data: { expiresAt: new Date(Date.now() - 1000) } });
    expect(await getActorFromHeaders(new Headers({ cookie: cookie! }))).toBeNull();
  });

  it("conta desativada não consegue entrar", async () => {
    const u = await makeUser("USER", { active: false });
    const { res } = await signIn(u.email);
    expect(res.status).toBe(403);
  });

  it("sessão de usuário desativado depois do login deixa de valer", async () => {
    const u = await makeUser("USER");
    const { cookie } = await signIn(u.email);
    await prisma.user.update({ where: { id: u.id }, data: { active: false } });
    expect(await getActorFromHeaders(new Headers({ cookie: cookie! }))).toBeNull();
  });
});

describe("contas de demonstração fora do ambiente demo", () => {
  afterEach(() => {
    process.env.APP_ENV = "demo";
    process.env.EMAIL_TRANSPORT = "dev";
    resetEnvCache();
  });

  it("são bloqueadas quando APP_ENV=production", async () => {
    const u = await makeUser("USER", { isDemo: true });
    const ok = await signIn(u.email);
    expect(ok.res.status).toBe(200);
    process.env.APP_ENV = "production";
    process.env.EMAIL_TRANSPORT = "none";
    resetEnvCache();
    expect(await getActorFromHeaders(new Headers({ cookie: ok.cookie! }))).toBeNull();
    const blocked = await signIn(u.email);
    expect(blocked.res.status).toBe(403);
  });
});

describe("recuperação de acesso", () => {
  async function requestReset(email: string) {
    const res = await authRequest("/request-password-reset", { email, redirectTo: "/redefinir-senha" });
    expect(res.status).toBe(200);
    const mail = await prisma.devEmail.findFirst({ where: { to: email }, orderBy: { createdAt: "desc" } });
    const token = mail?.body.match(/reset-password\/([^?\s]+)/)?.[1];
    return { mail, token };
  }

  it("token temporário de uso único redefine a senha e encerra sessões", async () => {
    const u = await makeUser("USER");
    const { cookie: oldSession } = await signIn(u.email);
    const { mail, token } = await requestReset(u.email);
    expect(mail?.subject).toBe("Recuperação de acesso");
    expect(token).toBeTruthy();

    const reset = await authRequest("/reset-password", { newPassword: "NovaSenha@123", token });
    expect(reset.status).toBe(200);
    expect(await getActorFromHeaders(new Headers({ cookie: oldSession! }))).toBeNull();
    expect((await signIn(u.email, "NovaSenha@123")).res.status).toBe(200);
    expect((await signIn(u.email, PASSWORD)).res.status).toBe(401);

    // Reutilizar o mesmo token falha.
    const again = await authRequest("/reset-password", { newPassword: "OutraSenha@123", token });
    expect(again.status).toBeGreaterThanOrEqual(400);

    const events = await prisma.auditEvent.findMany({ where: { actorId: u.id, action: { startsWith: "auth.password_reset" } } });
    expect(events.map((e) => e.action).sort()).toEqual(["auth.password_reset_completed", "auth.password_reset_requested"]);
    expect(JSON.stringify(events)).not.toContain(token!);
  });

  it("token expirado é recusado", async () => {
    const u = await makeUser("USER");
    const { token } = await requestReset(u.email);
    await prisma.verification.updateMany({ where: { identifier: { contains: token! } }, data: { expiresAt: new Date(Date.now() - 1000) } });
    const res = await authRequest("/reset-password", { newPassword: "NovaSenha@123", token });
    expect(res.status).toBeGreaterThanOrEqual(400);
  });

  it("e-mail inexistente recebe a mesma resposta (sem enumeração)", async () => {
    const res = await authRequest("/request-password-reset", { email: "nao-existe@teste.local", redirectTo: "/redefinir-senha" });
    expect(res.status).toBe(200);
    expect(await prisma.devEmail.count({ where: { to: "nao-existe@teste.local" } })).toBe(0);
  });
});

describe("limitação de tentativas", () => {
  it("bloqueia login após exceder o limite por IP", async () => {
    const u = await makeUser("USER");
    const ip = "203.0.113.77";
    await prisma.rateLimit.deleteMany({});
    const max = Number(process.env.AUTH_RATE_LIMIT_SIGNIN_MAX ?? 5);
    const statuses: number[] = [];
    for (let i = 0; i <= max; i++) statuses.push((await signIn(u.email, "errada-123456", ip)).res.status);
    expect(statuses.slice(0, max).every((s) => s === 401)).toBe(true);
    expect(statuses[max]).toBe(429);
    // Mesmo com a senha correta, o IP segue bloqueado na janela.
    expect((await signIn(u.email, PASSWORD, ip)).res.status).toBe(429);
  });

  it("limita pedidos de recuperação por IP", async () => {
    const ip = "203.0.113.88";
    const max = Number(process.env.AUTH_RATE_LIMIT_RESET_MAX ?? 3);
    const statuses: number[] = [];
    for (let i = 0; i <= max; i++) {
      statuses.push((await authRequest("/request-password-reset", { email: "x@teste.local", redirectTo: "/redefinir-senha" }, { ip })).status);
    }
    expect(statuses[max]).toBe(429);
  });
});

describe("rotas de API próprias", () => {
  const handler = route(async ({ ctx }) => ({ me: ctx.actor.id }), { roles: ["ADMIN"] });

  async function call(method: string, cookie: string | null, origin: string | null) {
    const headers = new Headers();
    if (cookie) headers.set("cookie", cookie);
    if (origin) headers.set("origin", origin);
    return handler(new NextRequest(`${BASE}/api/teste`, { method, headers }), { params: Promise.resolve({}) });
  }

  it("sem sessão: 401 com erro padronizado", async () => {
    const res = await call("GET", null, null);
    expect(res.status).toBe(401);
    const body = await res.json();
    expect(body.error).toMatchObject({ code: "UNAUTHENTICATED" });
    expect(body.error.requestId).toBeTruthy();
  });

  it("CSRF: POST sem origem ou de outra origem é recusado", async () => {
    const admin = await makeUser("ADMIN");
    const { cookie } = await signIn(admin.email);
    expect((await call("POST", cookie, null)).status).toBe(403);
    expect((await call("POST", cookie, "https://site-malicioso.example")).status).toBe(403);
    expect((await call("POST", cookie, BASE)).status).toBe(200);
  });

  it("perfil sem permissão: 403 e auditoria de acesso negado", async () => {
    const u = await makeUser("USER");
    const { cookie } = await signIn(u.email);
    const res = await call("GET", cookie, null);
    expect(res.status).toBe(403);
    expect(await prisma.auditEvent.count({ where: { actorId: u.id, action: "access.denied" } })).toBe(1);
  });
});
