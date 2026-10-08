import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getCourse } from "@/server/services/courses";
import { AppError } from "@/server/errors";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge } from "@/components/ui/badge";
import { buttonClass } from "@/components/ui/button";
import { ActionButton } from "@/components/ui/action-button";

export const metadata = { title: "Aula" };

export default async function LessonPage({ params }: { params: Promise<{ slug: string; lessonId: string }> }) {
  const ctx = await requirePageCtx();
  const { slug, lessonId } = await params;
  let course;
  try {
    course = await getCourse(ctx, slug);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const lessons = course.modules.flatMap((m) => m.lessons.map((l) => ({ ...l, moduleTitle: m.title })));
  const idx = lessons.findIndex((l) => l.id === lessonId);
  if (idx < 0) notFound();
  const lesson = lessons[idx]!;
  const prev = lessons[idx - 1];
  const next = lessons[idx + 1];

  return (
    <>
      <nav aria-label="Trilha" className="mb-2 text-sm">
        <Link href={`/cursos/${course.slug}`} className="text-brand-700 underline">
          {course.title}
        </Link>{" "}
        <span className="text-slate-400">/ {lesson.moduleTitle}</span>
      </nav>
      <PageHeader
        title={lesson.title}
        description={`Aula ${idx + 1} de ${lessons.length} · ${lesson.durationMin} min`}
        actions={lesson.completedAt ? <Badge tone="success">Concluída</Badge> : <Badge>Não concluída</Badge>}
      />
      <Panel>
        <div className="whitespace-pre-wrap text-sm leading-relaxed text-slate-800">{lesson.content}</div>
        {lesson.videoUrl ? (
          <a href={lesson.videoUrl} target="_blank" rel="noopener noreferrer" className="mt-4 inline-flex items-center gap-1 text-sm text-brand-700 underline">
            Abrir vídeo autorizado <ExternalLink className="size-3.5" aria-hidden="true" />
          </a>
        ) : (
          <p className="mt-4 text-xs text-slate-500">Aula demonstrativa em texto (sem vídeo).</p>
        )}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-4">
          <ActionButton url={`/api/aulas/${lesson.id}/progresso`} body={{ completed: !lesson.completedAt }} variant={lesson.completedAt ? "secondary" : "primary"} size="md">
            {lesson.completedAt ? "Marcar como não concluída" : "Marcar como concluída"}
          </ActionButton>
          <div className="flex gap-2">
            {prev && (
              <Link href={`/cursos/${course.slug}/aulas/${prev.id}`} className={buttonClass("secondary", "md")}>
                <ChevronLeft className="size-4" aria-hidden="true" /> Anterior
              </Link>
            )}
            {next && (
              <Link href={`/cursos/${course.slug}/aulas/${next.id}`} className={buttonClass("secondary", "md")}>
                Próxima <ChevronRight className="size-4" aria-hidden="true" />
              </Link>
            )}
          </div>
        </div>
      </Panel>
    </>
  );
}
