import { describe, expect, it } from "vitest";
import { prisma } from "@/server/db";
import { audit } from "@/server/audit";
import * as courses from "@/server/services/courses";
import * as auditLog from "@/server/services/audit-log";
import * as market from "@/server/services/market";
import * as notifications from "@/server/services/notifications";
import { makeUser } from "../support/factories";

describe("cursos, aulas, progresso e agenda", () => {
  it("administrador cria curso/módulo/aula; usuário vê após publicar e registra progresso", async () => {
    const admin = await makeUser("ADMIN");
    const user = await makeUser("USER");
    const slug = `curso-teste-${Date.now()}`;
    const c = await courses.createCourse(admin.ctx, { title: "Curso de teste", slug, description: "Descrição do curso de teste" });
    const m = await courses.addModule(admin.ctx, c.id, { title: "Módulo 1" });
    const l = await courses.addLesson(admin.ctx, m.id, { title: "Aula 1", content: "Conteúdo da aula 1", durationMin: 5 });
    await expect(courses.getCourse(user.ctx, slug)).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(courses.createCourse(admin.ctx, { title: "Outro", slug, description: "Descrição duplicada" })).rejects.toMatchObject({ code: "CONFLICT" });

    await courses.updateCourse(admin.ctx, c.id, { title: "Curso de teste", slug, description: "Descrição do curso de teste", status: "PUBLISHED" });
    await courses.setLessonProgress(user.ctx, l.id, true);
    await courses.setLessonProgress(user.ctx, l.id, true); // idempotente
    let detail = await courses.getCourse(user.ctx, slug);
    expect(detail.modules[0]!.lessons[0]!.completedAt).not.toBeNull();
    expect((await courses.listCourses(user.ctx)).find((x) => x.slug === slug)).toMatchObject({ lessons: 1, completed: 1 });
    await courses.setLessonProgress(user.ctx, l.id, false);
    detail = await courses.getCourse(user.ctx, slug);
    expect(detail.modules[0]!.lessons[0]!.completedAt).toBeNull();
    await expect(courses.addLesson(admin.ctx, m.id, { title: "Aula", content: "Conteúdo com link", videoUrl: "http://x.y", durationMin: 5 })).rejects.toMatchObject({
      code: "VALIDATION",
    });
  });

  it("agenda: criação notifica usuários e lista próximos eventos", async () => {
    const admin = await makeUser("ADMIN");
    const user = await makeUser("USER");
    const startsAt = new Date(Date.now() + 3 * 86_400_000).toISOString();
    const { id } = await courses.createLive(admin.ctx, { title: "Live de teste", description: "Descrição", kind: "LIVE", startsAt, durationMin: 60 });
    expect((await courses.listLives(user.ctx)).some((x) => x.id === id)).toBe(true);
    expect(await notifications.unreadCount(user.ctx)).toBe(1);
    await courses.updateLive(admin.ctx, id, { title: "Live de teste", description: "Descrição", kind: "LIVE", status: "CANCELED", startsAt, durationMin: 60 });
    expect((await courses.listLives(user.ctx)).some((x) => x.id === id)).toBe(false);
  });
});

describe("auditoria", () => {
  it("remove campos sensíveis dos metadados", async () => {
    const admin = await makeUser("ADMIN");
    await audit(admin.ctx, { action: "teste.sensivel", resourceType: "teste", metadata: { password: "x", token: "y", nested: { senha: "z", ok: 1 }, ok: true } });
    const ev = await prisma.auditEvent.findFirst({ where: { action: "teste.sensivel", actorId: admin.id } });
    expect(ev?.metadata).toEqual({ nested: { ok: 1 }, ok: true });
    expect(ev).toMatchObject({ actorId: admin.id, actorEmail: admin.email, requestId: admin.ctx.requestId, resourceType: "teste" });
  });

  it("consulta com filtros por ator, ação, recurso, requisição e período", async () => {
    const admin = await makeUser("ADMIN");
    await market.refreshQuotes(admin.ctx);
    const byActor = await auditLog.listAuditEvents(admin.ctx, { actor: admin.email });
    expect(byActor.items.map((e) => e.action)).toContain("market.refresh_quotes");
    expect((await auditLog.listAuditEvents(admin.ctx, { action: "market.", resourceType: "asset" })).total).toBeGreaterThan(0);
    expect((await auditLog.listAuditEvents(admin.ctx, { requestId: admin.ctx.requestId })).total).toBeGreaterThan(0);
    expect((await auditLog.listAuditEvents(admin.ctx, { from: "2000-01-01", to: "2000-01-02" })).total).toBe(0);
    const ind = await auditLog.adminIndicators(admin.ctx);
    expect(ind.audit24h).toBeGreaterThan(0);
    expect(ind.usersByRole.ADMIN).toBeGreaterThan(0);
  });
});
