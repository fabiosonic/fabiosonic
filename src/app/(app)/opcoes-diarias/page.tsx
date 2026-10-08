import Link from "next/link";
import { requirePageCtx } from "@/server/session";
import { dailyOptions, listAssets } from "@/server/services/market";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Alert, EmptyState } from "@/components/ui/alert";
import { Field, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { OptionsTable } from "@/components/market/options-table";
import { cn } from "@/components/ui/cn";
import { formatDate } from "@/lib/format";

export const metadata = { title: "Opções diárias" };

export default async function DailyOptionsPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const [assets, daily] = await Promise.all([
    listAssets(ctx),
    dailyOptions(ctx, { date: sp.data, asset: sp.ativo, type: sp.tipo, page: Number(sp.pagina ?? 1) }),
  ]);
  const chip = (d: string) => {
    const p = new URLSearchParams();
    p.set("data", d);
    if (sp.ativo) p.set("ativo", sp.ativo);
    if (sp.tipo) p.set("tipo", sp.tipo);
    return `/opcoes-diarias?${p.toString()}`;
  };

  return (
    <>
      <PageHeader
        title="Opções diárias"
        description="Contratos agrupados por data de vencimento, para consulta rápida dos vencimentos mais próximos e envio direto ao simulador."
      />
      <Alert tone="warning" className="mb-4">
        Lista demonstrativa: os contratos são fictícios e não indicam disponibilidade ou liquidez de contratos reais na B3.
      </Alert>
      <Panel>
        <nav aria-label="Próximos vencimentos" className="mb-4 flex flex-wrap gap-2">
          {daily.upcoming.length === 0 && <span className="text-sm text-slate-500">Sem vencimentos nos próximos 45 dias.</span>}
          {daily.upcoming.map((d) => (
            <Link
              key={d}
              href={chip(d)}
              aria-current={d === daily.date ? "date" : undefined}
              className={cn(
                "rounded-full border px-3 py-1 text-sm tabular",
                d === daily.date ? "border-brand-700 bg-brand-700 text-white" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
              )}
            >
              {formatDate(d)}
            </Link>
          ))}
        </nav>
        <FilterForm action="/opcoes-diarias" resetHref="/opcoes-diarias">
          <input type="hidden" name="data" value={daily.date} />
          <Field id="ativo" label="Ativo" className="w-36">
            <Select id="ativo" name="ativo" defaultValue={sp.ativo ?? ""}>
              <option value="">Todos</option>
              {assets.map((a) => (
                <option key={a.ticker} value={a.ticker}>
                  {a.ticker}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="tipo" label="Tipo" className="w-28">
            <Select id="tipo" name="tipo" defaultValue={sp.tipo ?? ""}>
              <option value="">Todos</option>
              <option value="CALL">CALL</option>
              <option value="PUT">PUT</option>
            </Select>
          </Field>
        </FilterForm>
        <h2 className="mt-5 text-sm font-semibold text-slate-800">Vencimento em {formatDate(daily.date)}</h2>
        <div className="mt-2">
          {daily.page.items.length === 0 ? (
            <EmptyState title="Nenhum contrato para esta data e filtros." />
          ) : (
            <>
              <OptionsTable rows={daily.page.items} />
              <Pagination
                page={daily.page.page}
                pageCount={daily.page.pageCount}
                total={daily.page.total}
                basePath="/opcoes-diarias"
                params={{ data: daily.date, ativo: sp.ativo, tipo: sp.tipo }}
              />
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
