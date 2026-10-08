import { notFound } from "next/navigation";
import { Pencil } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { getAnalysis, listRevisions } from "@/server/services/content";
import { AppError } from "@/server/errors";
import { PageHeader, Panel } from "@/components/ui/panel";
import { ContentStatusBadge } from "@/components/ui/badge";
import { LinkButton } from "@/components/ui/button";
import { StatusActions } from "@/components/content/status-actions";
import { Revisions } from "@/components/content/revisions";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Análise" };

export default async function AnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx();
  const { id } = await params;
  let a;
  try {
    a = await getAnalysis(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const staff = isStaff(ctx.actor);
  const revisions = staff ? await listRevisions(ctx, "analysis", id) : [];
  return (
    <>
      <PageHeader
        title={a.title}
        description={`${a.assetTicker ?? "Geral"} · por ${a.authorName}${a.publishedAt ? ` · publicada em ${formatDateTime(a.publishedAt)}` : ""}`}
        actions={
          staff && (
            <>
              <ContentStatusBadge status={a.status} />
              {a.status !== "ARCHIVED" && (
                <LinkButton href={`/analises/${a.id}/editar`} variant="secondary">
                  <Pencil className="size-4" aria-hidden="true" /> Editar
                </LinkButton>
              )}
              <StatusActions base={`/api/analises/${a.id}`} status={a.status} noun="análise" />
            </>
          )
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel className="lg:col-span-2">
          <p className="text-sm font-medium text-slate-800">{a.summary}</p>
          {/* Texto exibido como conteúdo simples (sem HTML), preservando quebras de linha. */}
          <div className="mt-4 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">{a.body}</div>
          <p className="mt-6 border-t border-slate-100 pt-3 text-xs text-slate-500">Conteúdo educacional. Não constitui recomendação de investimento.</p>
        </Panel>
        {staff && <Revisions items={revisions} />}
      </div>
    </>
  );
}
