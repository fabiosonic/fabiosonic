"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { createColumnHelper, flexRender, getCoreRowModel, useReactTable, type SortingState } from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown, Calculator } from "lucide-react";
import { Badge, DataSourceBadge } from "@/components/ui/badge";
import { formatBRL, formatDate } from "@/lib/format";

export interface OptionRowView {
  id: string;
  symbol: string;
  assetTicker: string;
  assetPrice: string;
  type: "CALL" | "PUT";
  style: "AMERICANA" | "EUROPEIA";
  strike: string;
  expiration: string;
  lastPrice: string | null;
  dataSource: "DEMO" | "DELAYED" | "REALTIME";
}

const col = createColumnHelper<OptionRowView>();

function moneyness(o: OptionRowView) {
  const s = Number(o.assetPrice);
  const k = Number(o.strike);
  if (Math.abs(s - k) / s < 0.01) return "ATM";
  const itm = o.type === "CALL" ? s > k : s < k;
  return itm ? "ITM" : "OTM";
}

const columns = [
  col.accessor("symbol", { header: "Código", cell: (c) => <span className="font-mono text-xs font-semibold">{c.getValue()}</span> }),
  col.accessor("assetTicker", { id: "asset", header: "Ativo" }),
  col.accessor("type", {
    header: "Tipo",
    enableSorting: false,
    cell: (c) => <Badge tone={c.getValue() === "CALL" ? "brand" : "info"}>{c.getValue()}</Badge>,
  }),
  col.accessor("strike", { header: "Strike", cell: (c) => <span className="tabular">{formatBRL(c.getValue())}</span>, meta: { align: "right" } }),
  col.accessor("expiration", { header: "Vencimento", cell: (c) => <span className="tabular">{formatDate(c.getValue())}</span> }),
  col.accessor("lastPrice", { header: "Prêmio", cell: (c) => <span className="tabular">{formatBRL(c.getValue())}</span>, meta: { align: "right" } }),
  col.display({
    id: "moneyness",
    header: "Situação",
    cell: (c) => {
      const m = moneyness(c.row.original);
      return (
        <span className="text-xs text-slate-600" title={m === "ITM" ? "Dentro do dinheiro" : m === "OTM" ? "Fora do dinheiro" : "No dinheiro"}>
          {m}
        </span>
      );
    },
  }),
  col.accessor("dataSource", { header: "Dado", enableSorting: false, cell: (c) => <DataSourceBadge source={c.getValue()} /> }),
  col.display({
    id: "actions",
    header: () => <span className="sr-only">Ações</span>,
    cell: (c) => (
      <Link
        href={`/simulador?opcao=${encodeURIComponent(c.row.original.symbol)}`}
        className="inline-flex items-center gap-1 rounded px-2 py-1 text-xs font-medium text-brand-700 hover:bg-brand-50"
        aria-label={`Simular ${c.row.original.symbol}`}
        title="Abrir no simulador"
      >
        <Calculator className="size-3.5" aria-hidden="true" /> Simular
      </Link>
    ),
  }),
];

const SORT_KEYS: Record<string, string> = { symbol: "symbol", asset: "asset", strike: "strike", expiration: "expiration", lastPrice: "lastPrice" };

/** Tabela com ordenação controlada pelo servidor (estado na URL). */
export function OptionsTable({ rows, sort, dir }: { rows: OptionRowView[]; sort?: string; dir?: string }) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const sorting: SortingState = sort ? [{ id: sort, desc: dir === "desc" }] : [];

  // A TanStack Table não é compatível com a memoização do React Compiler, que ignora este componente.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: rows,
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    state: { sorting },
    onSortingChange: (updater) => {
      const next = typeof updater === "function" ? updater(sorting) : updater;
      const sp = new URLSearchParams(params.toString());
      sp.delete("pagina");
      if (next[0] && SORT_KEYS[next[0].id]) {
        sp.set("ordem", SORT_KEYS[next[0].id]!);
        sp.set("dir", next[0].desc ? "desc" : "asc");
      } else {
        sp.delete("ordem");
        sp.delete("dir");
      }
      router.push(`${pathname}?${sp.toString()}`);
    },
  });

  return (
    <div className="relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0" role="region" aria-label="Tabela de opções" tabIndex={0}>
      <table className="w-full min-w-max border-collapse text-sm">
        <caption className="sr-only">Contratos de opções (dados demonstrativos)</caption>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const canSort = h.column.getCanSort() && SORT_KEYS[h.column.id];
                const s = h.column.getIsSorted();
                const align = (h.column.columnDef.meta as { align?: string } | undefined)?.align === "right" ? "text-right" : "text-left";
                return (
                  <th
                    key={h.id}
                    scope="col"
                    aria-sort={s === "asc" ? "ascending" : s === "desc" ? "descending" : canSort ? "none" : undefined}
                    className={`border-b border-slate-200 bg-slate-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-600 ${align}`}
                  >
                    {canSort ? (
                      <button type="button" onClick={h.column.getToggleSortingHandler()} className="inline-flex items-center gap-1 uppercase hover:text-slate-900">
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        {s === "asc" ? <ArrowUp className="size-3" aria-hidden="true" /> : s === "desc" ? <ArrowDown className="size-3" aria-hidden="true" /> : <ArrowUpDown className="size-3 opacity-50" aria-hidden="true" />}
                        <span className="sr-only">{s ? `(ordenado ${s === "asc" ? "crescente" : "decrescente"})` : "(ordenar)"}</span>
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((r) => (
            <tr key={r.id} className="hover:bg-slate-50">
              {r.getVisibleCells().map((c) => (
                <td key={c.id} className={`border-b border-slate-100 px-3 py-2 ${(c.column.columnDef.meta as { align?: string } | undefined)?.align === "right" ? "text-right" : ""}`}>
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
