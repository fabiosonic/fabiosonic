import { notFound } from "next/navigation";
import { requirePageCtx } from "@/server/session";
import { getCourseForAdmin } from "@/server/services/courses";
import { AppError } from "@/server/errors";
import { PageHeader, Panel } from "@/components/ui/panel";
import { ActionButton } from "@/components/ui/action-button";
import { CourseForm, LessonForm, ModuleForm } from "../course-forms";

export const metadata = { title: "Editar curso" };

export default async function AdminCoursePage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx(["ADMIN"]);
  const { id } = await params;
  let c;
  try {
    c = await getCourseForAdmin(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  return (
    <>
      <PageHeader title={c.title} description="Editar dados do curso, módulos e aulas." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <div className="space-y-4 xl:col-span-2">
          {c.modules.map((m, mi) => (
            <Panel
              key={m.id}
              title={`Módulo ${mi + 1}: ${m.title}`}
              actions={
                <ActionButton
                  method="DELETE"
                  url={`/api/admin/modulos/${m.id}`}
                  variant="ghost"
                  confirm={{ title: "Excluir módulo?", description: "O módulo, suas aulas e o progresso dos usuários nessas aulas serão excluídos." }}
                  confirmLabel="Excluir"
                >
                  Excluir módulo
                </ActionButton>
              }
            >
              <ul className="space-y-2">
                {m.lessons.map((l) => (
                  <li key={l.id} className="rounded-md border border-slate-200">
                    <details>
                      <summary className="cursor-pointer px-3 py-2 text-sm font-medium">
                        {l.title} <span className="text-xs font-normal text-slate-500">· {l.durationMin} min</span>
                      </summary>
                      <div className="border-t border-slate-100 p-3">
                        <LessonForm moduleId={m.id} lesson={{ id: l.id, title: l.title, content: l.content, videoUrl: l.videoUrl ?? "", durationMin: l.durationMin }} />
                        <div className="mt-2">
                          <ActionButton
                            method="DELETE"
                            url={`/api/admin/aulas/${l.id}`}
                            variant="ghost"
                            confirm={{ title: "Excluir aula?", description: "A aula e o progresso associado serão excluídos." }}
                            confirmLabel="Excluir"
                          >
                            Excluir aula
                          </ActionButton>
                        </div>
                      </div>
                    </details>
                  </li>
                ))}
              </ul>
              <details className="mt-3 rounded-md border border-dashed border-slate-300">
                <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-brand-700">Adicionar aula</summary>
                <div className="border-t border-slate-100 p-3">
                  <LessonForm moduleId={m.id} />
                </div>
              </details>
            </Panel>
          ))}
          <ModuleForm courseId={c.id} />
        </div>
        <CourseForm course={{ id: c.id, title: c.title, slug: c.slug, description: c.description, status: c.status }} />
      </div>
    </>
  );
}
