import Link from "next/link";
import { Plus } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { listAnalyses } from "@/server/services/content";
import { listAssets } from "@/server/services/market";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { ContentStatusBadge } from "@/components/ui/badge";
import { Field, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { formatDateTime } from "@/lib/format";
import { CONTENT_STATUS_LABEL } from "@/lib/labels";

export const metadata = { title: "Análises" };

export default async function AnalysesPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const staff = isStaff(ctx.actor);
  const [page, assets] = await Promise.all([
    listAnalyses(ctx, { page: Number(sp.pagina ?? 1), asset: sp.ativo, status: sp.situacao }),
    listAssets(ctx),
  ]);
  return (
    <>
      <PageHeader
        title="Análises"
        description="Textos da equipe de análise. Conteúdo educacional e demonstrativo."
        actions={
          staff && (
            <LinkButton href="/analises/nova">
              <Plus className="size-4" aria-hidden="true" /> Nova análise
            </LinkButton>
          )
        }
      />
      <Panel className="mb-4">
        <FilterForm action="/analises" resetHref="/analises">
          <Field id="ativo" label="Ativo" className="w-32">
            <Select id="ativo" name="ativo" defaultValue={sp.ativo ?? ""}>
              <option value="">Todos</option>
              {assets.map((a) => (
                <option key={a.ticker} value={a.ticker}>
                  {a.ticker}
                </option>
              ))}
            </Select>
          </Field>
          {staff && (
            <Field id="situacao" label="Situação" className="w-36">
              <Select id="situacao" name="situacao" defaultValue={sp.situacao ?? ""}>
                <option value="">Todas</option>
                {Object.entries(CONTENT_STATUS_LABEL).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
          )}
        </FilterForm>
      </Panel>
      {page.items.length === 0 ? (
        <EmptyState title="Nenhuma análise encontrada" />
      ) : (
        <>
          <ul className="space-y-3">
            {page.items.map((a) => (
              <li key={a.id} className="rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <Link href={`/analises/${a.id}`} className="font-semibold text-slate-900 hover:underline">
                    {a.title}
                  </Link>
                  {staff && <ContentStatusBadge status={a.status} />}
                </div>
                <p className="text-xs text-slate-500">
                  {a.assetTicker ?? "Geral"} · {a.authorName} · {a.publishedAt ? `publicada em ${formatDateTime(a.publishedAt)}` : `atualizada em ${formatDateTime(a.updatedAt)}`}
                </p>
                <p className="mt-2 text-sm text-slate-700">{a.summary}</p>
              </li>
            ))}
          </ul>
          <Pagination page={page.page} pageCount={page.pageCount} total={page.total} basePath="/analises" params={{ ativo: sp.ativo, situacao: sp.situacao }} />
        </>
      )}
    </>
  );
}
