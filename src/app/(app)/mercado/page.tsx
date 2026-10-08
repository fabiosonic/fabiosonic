import { requirePageCtx } from "@/server/session";
import { listAssets, listExpirations, listOptions } from "@/server/services/market";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Alert, EmptyState } from "@/components/ui/alert";
import { DataSourceBadge } from "@/components/ui/badge";
import { Field, Input, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { Table, Td, Th } from "@/components/ui/table";
import { OptionsTable } from "@/components/market/options-table";
import { formatBRL, formatDate, formatDateTime } from "@/lib/format";

export const metadata = { title: "Mercado" };

type SP = Promise<Record<string, string | undefined>>;

export default async function MarketPage({ searchParams }: { searchParams: SP }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const filters = { q: sp.q, ativo: sp.ativo, tipo: sp.tipo, vencimento: sp.vencimento, ordem: sp.ordem, dir: sp.dir };
  const [assets, expirations, options] = await Promise.all([
    listAssets(ctx),
    listExpirations(ctx, sp.ativo),
    listOptions(ctx, {
      q: sp.q,
      asset: sp.ativo,
      type: sp.tipo,
      expiration: sp.vencimento,
      sort: sp.ordem,
      dir: sp.dir,
      page: Number(sp.pagina ?? 1),
      pageSize: 25,
    }),
  ]);

  return (
    <>
      <PageHeader title="Mercado" description="Ativos e grade de opções com pesquisa, filtros, ordenação e paginação." />
      <Alert tone="warning" title="Dados demonstrativos" className="mb-4">
        Cotações e contratos são fictícios (códigos terminados em “D”) e não representam disponibilidade, preço ou liquidez reais. Dados reais exigem contratação de um distribuidor licenciado de market data.
      </Alert>

      <Panel title="Ativos" className="mb-4">
        <Table caption="Ativos">
          <thead>
            <tr>
              <Th>Ticker</Th>
              <Th>Nome</Th>
              <Th className="text-right">Último preço</Th>
              <Th>Atualizado em</Th>
              <Th>Origem</Th>
              <Th className="text-right">Opções</Th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.id}>
                <Td className="font-medium">
                  <a href={`/mercado?ativo=${a.ticker}`} className="text-brand-700 underline">
                    {a.ticker}
                  </a>
                </Td>
                <Td>{a.name}</Td>
                <Td className="text-right tabular">{formatBRL(a.lastPrice)}</Td>
                <Td className="tabular">{formatDateTime(a.priceAt)}</Td>
                <Td>
                  <DataSourceBadge source={a.dataSource} />
                </Td>
                <Td className="text-right tabular">{a.optionsCount}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Panel>

      <Panel title="Grade de opções">
        <FilterForm action="/mercado" resetHref="/mercado">
          <Field id="q" label="Código" className="w-36">
            <Input id="q" name="q" defaultValue={sp.q} placeholder="Ex.: PETRK" />
          </Field>
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
          <Field id="vencimento" label="Vencimento" className="w-40">
            <Select id="vencimento" name="vencimento" defaultValue={sp.vencimento ?? ""}>
              <option value="">Todos</option>
              {expirations.map((e) => (
                <option key={e} value={e}>
                  {formatDate(e)}
                </option>
              ))}
            </Select>
          </Field>
          {sp.ordem && <input type="hidden" name="ordem" value={sp.ordem} />}
          {sp.dir && <input type="hidden" name="dir" value={sp.dir} />}
        </FilterForm>

        <div className="mt-4">
          {options.items.length === 0 ? (
            <EmptyState title="Nenhum contrato encontrado">Ajuste os filtros para ver outros contratos.</EmptyState>
          ) : (
            <>
              <OptionsTable rows={options.items} sort={sp.ordem} dir={sp.dir} />
              <Pagination page={options.page} pageCount={options.pageCount} total={options.total} basePath="/mercado" params={filters} />
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
