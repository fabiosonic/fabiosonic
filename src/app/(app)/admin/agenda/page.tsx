import { requirePageCtx } from "@/server/session";
import { listCourseOptions, listLives } from "@/server/services/courses";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/format";
import { LIVE_KIND_LABEL, LIVE_STATUS_LABEL } from "@/lib/labels";
import { LiveForm } from "./live-form";

export const metadata = { title: "Gestão da agenda" };

export default async function AdminAgendaPage() {
  const ctx = await requirePageCtx(["ADMIN"]);
  const [lives, courses] = await Promise.all([listLives(ctx, { scope: "all", take: 100 }), listCourseOptions(ctx)]);
  return (
    <>
      <PageHeader title="Gestão da agenda" description="Agende lives e aulas ao vivo. Usuários são notificados de novos eventos." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2" title="Eventos">
          <ul className="space-y-2">
            {lives.map((l) => (
              <li key={l.id} className="rounded-md border border-slate-200">
                <details>
                  <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2 text-sm">
                    <span className="font-medium">{l.title}</span>
                    <span className="text-slate-500">{formatDateTime(l.startsAt)}</span>
                    <Badge tone="brand">{LIVE_KIND_LABEL[l.kind]}</Badge>
                    <Badge tone={l.status === "CANCELED" ? "danger" : l.status === "DONE" ? "neutral" : "info"}>{LIVE_STATUS_LABEL[l.status]}</Badge>
                  </summary>
                  <div className="border-t border-slate-100 p-3">
                    <LiveForm live={l} courses={courses} />
                  </div>
                </details>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Novo evento">
          <LiveForm courses={courses} />
        </Panel>
      </div>
    </>
  );
}
