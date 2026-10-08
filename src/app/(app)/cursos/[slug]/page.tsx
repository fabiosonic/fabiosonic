import Link from "next/link";
import { notFound } from "next/navigation";
import { CheckCircle2, Circle } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getCourse } from "@/server/services/courses";
import { AppError } from "@/server/errors";
import { PageHeader, Panel } from "@/components/ui/panel";

export const metadata = { title: "Curso" };

export default async function CoursePage({ params }: { params: Promise<{ slug: string }> }) {
  const ctx = await requirePageCtx();
  const { slug } = await params;
  let course;
  try {
    course = await getCourse(ctx, slug);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const all = course.modules.flatMap((m) => m.lessons);
  const done = all.filter((l) => l.completedAt).length;
  return (
    <>
      <PageHeader title={course.title} description={course.description} />
      <p className="mb-4 text-sm text-slate-600">
        {done} de {all.length} aula(s) concluída(s).
      </p>
      <div className="space-y-4">
        {course.modules.map((m, mi) => (
          <Panel key={m.id} title={`Módulo ${mi + 1}: ${m.title}`}>
            <ol className="divide-y divide-slate-100">
              {m.lessons.map((l) => (
                <li key={l.id} className="flex items-center gap-3 py-2">
                  {l.completedAt ? (
                    <CheckCircle2 className="size-5 shrink-0 text-gain-700" aria-label="Concluída" />
                  ) : (
                    <Circle className="size-5 shrink-0 text-slate-300" aria-label="Não concluída" />
                  )}
                  <Link href={`/cursos/${course.slug}/aulas/${l.id}`} className="flex-1 text-sm font-medium text-slate-900 hover:underline">
                    {l.title}
                  </Link>
                  <span className="text-xs text-slate-500">{l.durationMin} min</span>
                </li>
              ))}
            </ol>
          </Panel>
        ))}
      </div>
    </>
  );
}
