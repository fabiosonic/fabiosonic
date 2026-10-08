import Link from "next/link";
import { GraduationCap } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { listCourses } from "@/server/services/courses";
import { PageHeader } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { ContentStatusBadge } from "@/components/ui/badge";

export const metadata = { title: "Cursos" };

export default async function CoursesPage() {
  const ctx = await requirePageCtx();
  const courses = await listCourses(ctx);
  return (
    <>
      <PageHeader title="Cursos" description="Conteúdo educacional original e demonstrativo, organizado em módulos e aulas. Seu progresso fica salvo." />
      {courses.length === 0 ? (
        <EmptyState title="Nenhum curso disponível" />
      ) : (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {courses.map((c) => {
            const pct = c.lessons ? Math.round((c.completed / c.lessons) * 100) : 0;
            return (
              <li key={c.id} className="flex flex-col rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/cursos/${c.slug}`} className="flex items-center gap-2 font-semibold text-slate-900 hover:underline">
                    <GraduationCap className="size-4 text-brand-700" aria-hidden="true" />
                    {c.title}
                  </Link>
                  {c.status !== "PUBLISHED" && <ContentStatusBadge status={c.status} />}
                </div>
                <p className="mt-2 flex-1 text-sm text-slate-600">{c.description}</p>
                <p className="mt-3 text-xs text-slate-500">
                  {c.modules} módulo(s) · {c.lessons} aula(s) · {c.durationMin} min
                </p>
                <div className="mt-2">
                  <div className="flex justify-between text-xs text-slate-600">
                    <span>Progresso</span>
                    <span>
                      {c.completed}/{c.lessons} ({pct}%)
                    </span>
                  </div>
                  <div className="mt-1 h-2 rounded-full bg-slate-100" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`Progresso em ${c.title}`}>
                    <div className="h-2 rounded-full bg-brand-600" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </>
  );
}
