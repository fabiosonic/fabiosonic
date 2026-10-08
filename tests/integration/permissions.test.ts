import { describe, expect, it } from "vitest";
import { AppError } from "@/server/errors";
import { prisma } from "@/server/db";
import * as content from "@/server/services/content";
import * as users from "@/server/services/users";
import * as courses from "@/server/services/courses";
import * as market from "@/server/services/market";
import * as auditLog from "@/server/services/audit-log";
import { makeUser, validStrategy } from "../support/factories";

async function code(p: Promise<unknown>) {
  try {
    await p;
    return "OK";
  } catch (e) {
    if (e instanceof AppError) return e.code;
    throw e;
  }
}

describe("perfis e permissões", () => {
  it("usuário não gerencia conteúdo, usuários, cursos, cotações nem auditoria", async () => {
    const { ctx } = await makeUser("USER");
    expect(await code(content.createStrategy(ctx, validStrategy()))).toBe("FORBIDDEN");
    expect(await code(content.createAnalysis(ctx, { title: "Título", summary: "Resumo suficiente", body: "Corpo da análise com mais de vinte caracteres." }))).toBe("FORBIDDEN");
    expect(await code(users.listUsers(ctx, {}))).toBe("FORBIDDEN");
    expect(await code(users.createUser(ctx, { name: "X Y", email: "x@y.local", role: "ADMIN", password: "12345678" }))).toBe("FORBIDDEN");
    expect(await code(courses.createCourse(ctx, { title: "Curso", slug: "curso-x", description: "Descrição do curso" }))).toBe("FORBIDDEN");
    expect(await code(market.refreshQuotes(ctx))).toBe("FORBIDDEN");
    expect(await code(auditLog.listAuditEvents(ctx, {}))).toBe("FORBIDDEN");
    expect(await code(content.listRevisions(ctx, "strategy", "x"))).toBe("FORBIDDEN");
  });

  it("analista gerencia análises e estratégias, mas não usuários nem cursos", async () => {
    const { ctx } = await makeUser("ANALYST");
    expect(await code(content.createStrategy(ctx, validStrategy()))).toBe("OK");
    expect(await code(users.listUsers(ctx, {}))).toBe("FORBIDDEN");
    expect(await code(courses.createCourse(ctx, { title: "Curso", slug: "curso-y", description: "Descrição do curso" }))).toBe("FORBIDDEN");
    expect(await code(auditLog.listAuditEvents(ctx, {}))).toBe("FORBIDDEN");
  });

  it("administrador gerencia usuários e não pode rebaixar a si mesmo", async () => {
    const { ctx, id } = await makeUser("ADMIN");
    const created = await users.createUser(ctx, { name: "Novo Usuário", email: `novo${Date.now()}@teste.local`, role: "USER", password: "Senha@12345" });
    expect(await code(users.updateUser(ctx, created.id, { role: "ANALYST" }))).toBe("OK");
    expect(await code(users.updateUser(ctx, id, { role: "USER" }))).toBe("CONFLICT");
    expect(await code(users.updateUser(ctx, id, { active: false }))).toBe("CONFLICT");
    expect(await code(users.createUser(ctx, { name: "Duplicado", email: "admin@demo.local", role: "USER", password: "Senha@12345" }))).toBe("CONFLICT");
  });

  it("desativar usuário encerra suas sessões", async () => {
    const admin = await makeUser("ADMIN");
    const target = await makeUser("USER");
    await prisma.session.create({ data: { id: crypto.randomUUID(), token: crypto.randomUUID(), userId: target.id, expiresAt: new Date(Date.now() + 3600_000) } });
    await users.updateUser(admin.ctx, target.id, { active: false });
    expect(await prisma.session.count({ where: { userId: target.id } })).toBe(0);
  });

  it("usuário vê apenas conteúdo publicado, mesmo pedindo rascunhos", async () => {
    const analyst = await makeUser("ANALYST");
    const user = await makeUser("USER");
    const { id } = await content.createStrategy(analyst.ctx, validStrategy({ title: "Rascunho secreto" }));
    expect(await code(content.getStrategy(user.ctx, id))).toBe("NOT_FOUND");
    const list = await content.listStrategies(user.ctx, { status: "DRAFT" });
    expect(list.items.every((s) => s.status === "PUBLISHED")).toBe(true);
    expect(list.items.some((s) => s.id === id)).toBe(false);
    // Analista enxerga o rascunho.
    expect((await content.getStrategy(analyst.ctx, id)).status).toBe("DRAFT");
  });

  it("usuário não vê cursos em rascunho", async () => {
    const user = await makeUser("USER");
    const list = await courses.listCourses(user.ctx);
    expect(list.every((c) => c.status === "PUBLISHED")).toBe(true);
    expect(await code(courses.getCourse(user.ctx, "gestao-de-risco"))).toBe("NOT_FOUND");
    const draftLesson = await prisma.lesson.findFirst({ where: { module: { course: { slug: "gestao-de-risco" } } } });
    expect(await code(courses.setLessonProgress(user.ctx, draftLesson!.id, true))).toBe("NOT_FOUND");
  });
});
