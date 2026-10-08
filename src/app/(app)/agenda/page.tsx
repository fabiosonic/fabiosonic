import Link from "next/link";
import { ExternalLink } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { listLives, type LiveDto } from "@/server/services/courses";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/alert";
import { formatDateTime } from "@/lib/format";
import { LIVE_KIND_LABEL, LIVE_STATUS_LABEL } from "@/lib/labels";

export const metadata = { title: "Lives e aulas" };

function LiveItem({ l }: { l: LiveDto }) {
  return (
    <li className="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:justify-between">
      <div>
        <p className="font-medium text-slate-900">{l.title}</p>
        <p className="text-sm text-slate-600">{l.description}</p>
        {l.courseSlug && (
          <Link href={`/cursos/${l.courseSlug}`} className="text-xs text-brand-700 underline">
            Curso: {l.courseTitle}
          </Link>
        )}
      </div>
      <div className="flex flex-wrap items-center gap-2 text-sm sm:flex-col sm:items-end">
        <span className="tabular">{formatDateTime(l.startsAt)}</span>
        <span className="flex gap-1">
          <Badge tone="brand">{LIVE_KIND_LABEL[l.kind]}</Badge>
          {l.status !== "SCHEDULED" && <Badge tone={l.status === "CANCELED" ? "danger" : "neutral"}>{LIVE_STATUS_LABEL[l.status]}</Badge>}
        </span>
        {l.link && l.status === "SCHEDULED" && (
          <a href={l.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-xs text-brand-700 underline">
            Acessar <ExternalLink className="size-3" aria-hidden="true" />
          </a>
        )}
      </div>
    </li>
  );
}

export default async function AgendaPage() {
  const ctx = await requirePageCtx();
  const [upcoming, past] = await Promise.all([listLives(ctx, { scope: "upcoming" }), listLives(ctx, { scope: "past", take: 10 })]);
  return (
    <>
      <PageHeader title="Lives e aulas" description="Agenda de transmissões e aulas ao vivo (horário de Brasília)." />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Próximas">
          {upcoming.length === 0 ? <EmptyState title="Nenhum evento agendado" /> : <ul className="divide-y divide-slate-100">{upcoming.map((l) => <LiveItem key={l.id} l={l} />)}</ul>}
        </Panel>
        <Panel title="Anteriores">
          {past.length === 0 ? <p className="text-sm text-slate-500">Nenhum evento anterior.</p> : <ul className="divide-y divide-slate-100">{past.map((l) => <LiveItem key={l.id} l={l} />)}</ul>}
        </Panel>
      </div>
    </>
  );
}
