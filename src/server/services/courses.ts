import "server-only";
import { prisma } from "../db";
import type { Ctx } from "../context";
import { isAdmin, requireRole } from "../authz";
import { AppError, notFound } from "../errors";
import { parse } from "../validation";
import { audit } from "../audit";
import { courseSchema, lessonSchema, liveSchema, moduleSchema } from "@/lib/schemas";
import { iso } from "./common";
import { notifyRoles } from "./notifications";
import type { Prisma } from "@/generated/prisma/client";

// ---------------------------------------------------------------------------
// Consulta (usuários veem apenas cursos publicados)
// ---------------------------------------------------------------------------

function visible(ctx: Ctx): Prisma.CourseWhereInput {
  return isAdmin(ctx.actor) ? {} : { status: "PUBLISHED" };
}

export async function listCourses(ctx: Ctx) {
  const courses = await prisma.course.findMany({
    where: visible(ctx),
    orderBy: [{ position: "asc" }, { title: "asc" }],
    include: { modules: { include: { lessons: { select: { id: true, durationMin: true } } } } },
  });
  const lessonIds = courses.flatMap((c) => c.modules.flatMap((m) => m.lessons.map((l) => l.id)));
  const done = new Set(
    (await prisma.lessonProgress.findMany({ where: { userId: ctx.actor.id, lessonId: { in: lessonIds } }, select: { lessonId: true } })).map(
      (p) => p.lessonId,
    ),
  );
  return courses.map((c) => {
    const lessons = c.modules.flatMap((m) => m.lessons);
    return {
      id: c.id,
      slug: c.slug,
      title: c.title,
      description: c.description,
      status: c.status,
      modules: c.modules.length,
      lessons: lessons.length,
      durationMin: lessons.reduce((s, l) => s + l.durationMin, 0),
      completed: lessons.filter((l) => done.has(l.id)).length,
    };
  });
}

export async function getCourse(ctx: Ctx, slug: string) {
  const c = await prisma.course.findFirst({
    where: { slug, ...visible(ctx) },
    include: { modules: { orderBy: { position: "asc" }, include: { lessons: { orderBy: { position: "asc" } } } } },
  });
  if (!c) throw notFound("Curso");
  const ids = c.modules.flatMap((m) => m.lessons.map((l) => l.id));
  const progress = await prisma.lessonProgress.findMany({ where: { userId: ctx.actor.id, lessonId: { in: ids } } });
  const done = new Map(progress.map((p) => [p.lessonId, p.completedAt]));
  return {
    id: c.id,
    slug: c.slug,
    title: c.title,
    description: c.description,
    status: c.status,
    modules: c.modules.map((m) => ({
      id: m.id,
      title: m.title,
      position: m.position,
      lessons: m.lessons.map((l) => ({
        id: l.id,
        title: l.title,
        content: l.content,
        videoUrl: l.videoUrl,
        durationMin: l.durationMin,
        position: l.position,
        completedAt: iso(done.get(l.id)),
      })),
    })),
  };
}
export type CourseDetail = Awaited<ReturnType<typeof getCourse>>;

async function visibleLesson(ctx: Ctx, lessonId: string) {
  const lesson = await prisma.lesson.findFirst({
    where: { id: lessonId, module: { course: visible(ctx) } },
    select: { id: true },
  });
  if (!lesson) throw notFound("Aula");
  return lesson;
}

export async function setLessonProgress(ctx: Ctx, lessonId: string, completed: boolean) {
  await visibleLesson(ctx, lessonId);
  if (completed) {
    await prisma.lessonProgress.upsert({
      where: { userId_lessonId: { userId: ctx.actor.id, lessonId } },
      create: { userId: ctx.actor.id, lessonId },
      update: {},
    });
  } else {
    await prisma.lessonProgress.deleteMany({ where: { userId: ctx.actor.id, lessonId } });
  }
  await audit(ctx, { action: completed ? "lesson.complete" : "lesson.uncomplete", resourceType: "lesson", resourceId: lessonId });
}

// ---------------------------------------------------------------------------
// Gestão (administrador)
// ---------------------------------------------------------------------------

export async function createCourse(ctx: Ctx, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(courseSchema, input);
  if (await prisma.course.findUnique({ where: { slug: data.slug } })) {
    throw new AppError("CONFLICT", "Identificador já utilizado.", { slug: ["Escolha outro identificador."] });
  }
  const max = await prisma.course.aggregate({ _max: { position: true } });
  const c = await prisma.course.create({ data: { ...data, position: (max._max.position ?? 0) + 1 } });
  await audit(ctx, { action: "course.create", resourceType: "course", resourceId: c.id, metadata: { title: c.title } });
  return { id: c.id, slug: c.slug };
}

export async function updateCourse(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(courseSchema, input);
  const current = await prisma.course.findUnique({ where: { id } });
  if (!current) throw notFound("Curso");
  const clash = await prisma.course.findFirst({ where: { slug: data.slug, id: { not: id } } });
  if (clash) throw new AppError("CONFLICT", "Identificador já utilizado.", { slug: ["Escolha outro identificador."] });
  await prisma.course.update({ where: { id }, data });
  await audit(ctx, { action: "course.update", resourceType: "course", resourceId: id, metadata: { status: { de: current.status, para: data.status } } });
  return { slug: data.slug };
}

export async function addModule(ctx: Ctx, courseId: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(moduleSchema, input);
  if (!(await prisma.course.findUnique({ where: { id: courseId } }))) throw notFound("Curso");
  const max = await prisma.courseModule.aggregate({ where: { courseId }, _max: { position: true } });
  const m = await prisma.courseModule.create({ data: { courseId, title: data.title, position: (max._max.position ?? 0) + 1 } });
  await audit(ctx, { action: "course.module_create", resourceType: "course_module", resourceId: m.id });
  return { id: m.id };
}

export async function deleteModule(ctx: Ctx, moduleId: string) {
  requireRole(ctx.actor, "ADMIN");
  const res = await prisma.courseModule.deleteMany({ where: { id: moduleId } });
  if (!res.count) throw notFound("Módulo");
  await audit(ctx, { action: "course.module_delete", resourceType: "course_module", resourceId: moduleId });
}

export async function addLesson(ctx: Ctx, moduleId: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(lessonSchema, input);
  if (!(await prisma.courseModule.findUnique({ where: { id: moduleId } }))) throw notFound("Módulo");
  const max = await prisma.lesson.aggregate({ where: { moduleId }, _max: { position: true } });
  const l = await prisma.lesson.create({ data: { ...data, moduleId, position: (max._max.position ?? 0) + 1 } });
  await audit(ctx, { action: "course.lesson_create", resourceType: "lesson", resourceId: l.id });
  return { id: l.id };
}

export async function updateLesson(ctx: Ctx, lessonId: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(lessonSchema, input);
  const res = await prisma.lesson.updateMany({ where: { id: lessonId }, data });
  if (!res.count) throw notFound("Aula");
  await audit(ctx, { action: "course.lesson_update", resourceType: "lesson", resourceId: lessonId });
}

export async function deleteLesson(ctx: Ctx, lessonId: string) {
  requireRole(ctx.actor, "ADMIN");
  const res = await prisma.lesson.deleteMany({ where: { id: lessonId } });
  if (!res.count) throw notFound("Aula");
  await audit(ctx, { action: "course.lesson_delete", resourceType: "lesson", resourceId: lessonId });
}

// ---------------------------------------------------------------------------
// Agenda de lives e aulas
// ---------------------------------------------------------------------------

function mapLive(l: Prisma.LiveEventGetPayload<{ include: { course: { select: { title: true; slug: true } } } }>) {
  return {
    id: l.id,
    title: l.title,
    description: l.description,
    kind: l.kind,
    status: l.status,
    startsAt: l.startsAt.toISOString(),
    durationMin: l.durationMin,
    link: l.link,
    courseId: l.courseId,
    courseTitle: l.course?.title ?? null,
    courseSlug: l.course?.slug ?? null,
  };
}
export type LiveDto = ReturnType<typeof mapLive>;

export async function listLives(_ctx: Ctx, q: { scope?: "upcoming" | "past" | "all"; take?: number } = {}) {
  const now = new Date();
  const where: Prisma.LiveEventWhereInput =
    q.scope === "past"
      ? { startsAt: { lt: now } }
      : q.scope === "all"
        ? {}
        : { startsAt: { gte: new Date(now.getTime() - 2 * 3600_000) }, status: { not: "CANCELED" } };
  const lives = await prisma.liveEvent.findMany({
    where,
    orderBy: { startsAt: q.scope === "past" ? "desc" : "asc" },
    take: q.take ?? 50,
    include: { course: { select: { title: true, slug: true } } },
  });
  return lives.map(mapLive);
}

export async function createLive(ctx: Ctx, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(liveSchema, input);
  if (data.courseId && !(await prisma.course.findUnique({ where: { id: data.courseId } }))) {
    throw new AppError("VALIDATION", "Curso inválido.", { courseId: ["Curso não encontrado."] });
  }
  const l = await prisma.$transaction(async (tx) => {
    const created = await tx.liveEvent.create({ data: { ...data, courseId: data.courseId || null, createdById: ctx.actor.id } });
    await notifyRoles(["USER", "ANALYST"], { title: `Nova ${data.kind === "LIVE" ? "live" : "aula"} agendada`, body: data.title, link: "/agenda" }, tx);
    await audit(ctx, { action: "live.create", resourceType: "live_event", resourceId: created.id }, tx);
    return created;
  });
  return { id: l.id };
}

export async function updateLive(ctx: Ctx, id: string, input: unknown) {
  requireRole(ctx.actor, "ADMIN");
  const data = parse(liveSchema, input);
  const res = await prisma.liveEvent.updateMany({ where: { id }, data: { ...data, courseId: data.courseId || null } });
  if (!res.count) throw notFound("Evento");
  await audit(ctx, { action: "live.update", resourceType: "live_event", resourceId: id, metadata: { status: data.status } });
}

/** Para a gestão: localiza o curso pelo id (administrador vê qualquer situação). */
export async function getCourseForAdmin(ctx: Ctx, id: string) {
  requireRole(ctx.actor, "ADMIN");
  const c = await prisma.course.findUnique({ where: { id }, select: { slug: true } });
  if (!c) throw notFound("Curso");
  return getCourse(ctx, c.slug);
}

export async function listCourseOptions(ctx: Ctx) {
  requireRole(ctx.actor, "ADMIN");
  return prisma.course.findMany({ orderBy: { title: "asc" }, select: { id: true, title: true } });
}
