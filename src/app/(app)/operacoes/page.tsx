import Link from "next/link";
import { Plus } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { listStrategies } from "@/server/services/content";
import { listAssets } from "@/server/services/market";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { ContentStatusBadge } from "@/components/ui/badge";
import { CashFlow } from "@/components/ui/money";
import { Field, Input, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { formatBRL, formatDate } from "@/lib/format";
import { CONTENT_STATUS_LABEL, STRATEGY_TYPES, type StrategyType } from "@/lib/labels";

export const metadata = { title: "Operações prontas" };

export default async function StrategiesPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const staff = isStaff(ctx.actor);
  const [page, assets] = await Promise.all([
    listStrategies(ctx, { page: Number(sp.pagina ?? 1), asset: sp.ativo, type: sp.estrategia, status: sp.situacao, month: sp.mes }),
    listAssets(ctx),
  ]);
  return (
    <>
      <PageHeader
        title="Operações prontas"
        description="Estratégias montadas pela equipe de análise, com pernas, premissas e riscos. Conteúdo educacional; não é recomendação de investimento."
        actions={
          staff && (
            <LinkButton href="/operacoes/nova">
              <Plus className="size-4" aria-hidden="true" /> Nova operação
            </LinkButton>
          )
        }
      />
      <Panel className="mb-4">
        <FilterForm action="/operacoes" resetHref="/operacoes">
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
          <Field id="estrategia" label="Estratégia" className="w-52">
            <Select id="estrategia" name="estrategia" defaultValue={sp.estrategia ?? ""}>
              <option value="">Todas</option>
              {Object.entries(STRATEGY_TYPES).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="mes" label="Mês de vencimento" className="w-44">
            <Input id="mes" name="mes" type="month" defaultValue={sp.mes} />
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
        <EmptyState title="Nenhuma operação encontrada">Ajuste os filtros ou volte mais tarde.</EmptyState>
      ) : (
        <>
          <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {page.items.map((s) => (
              <li key={s.id} className="flex flex-col rounded-lg border border-slate-200 bg-white p-4">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/operacoes/${s.id}`} className="font-semibold text-slate-900 hover:underline">
                    {s.title}
                  </Link>
                  {staff && <ContentStatusBadge status={s.status} />}
                </div>
                <p className="mt-1 text-xs text-slate-500">
                  {s.assetTicker} · {STRATEGY_TYPES[s.strategyType as StrategyType] ?? s.strategyType} · vence {formatDate(s.expiration)}
                </p>
                <p className="mt-2 line-clamp-3 text-sm text-slate-700">{s.summary}</p>
                <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3 text-xs">
                  <div>
                    <dt className="text-slate-500">Montagem</dt>
                    <dd>
                      <CashFlow value={s.metrics.initialCashFlow} />
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Equilíbrio</dt>
                    <dd className="tabular">{s.metrics.breakevens.map((b) => formatBRL(b)).join(" · ") || "—"}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Ganho máx.</dt>
                    <dd className="tabular">{s.metrics.maxProfitUnlimited ? "Ilimitado" : formatBRL(s.metrics.maxProfit)}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Perda máx.</dt>
                    <dd className="tabular">{s.metrics.maxLossUnlimited ? "Ilimitada" : formatBRL(s.metrics.maxLoss)}</dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>
          <Pagination
            page={page.page}
            pageCount={page.pageCount}
            total={page.total}
            basePath="/operacoes"
            params={{ ativo: sp.ativo, estrategia: sp.estrategia, situacao: sp.situacao, mes: sp.mes }}
          />
        </>
      )}
    </>
  );
}
