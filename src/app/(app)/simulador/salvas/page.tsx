import Link from "next/link";
import { Plus } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { listSimulations } from "@/server/services/simulations";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { ActionButton } from "@/components/ui/action-button";
import { Field, Input } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { CashFlow } from "@/components/ui/money";
import { Table, Td, Th } from "@/components/ui/table";
import { formatBRL, formatDate, formatDateTime } from "@/lib/format";
import { SIM_MODE_LABEL } from "@/lib/labels";

export const metadata = { title: "Simulações salvas" };

export default async function SavedPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const page = await listSimulations(ctx, { page: Number(sp.pagina ?? 1), search: sp.q });
  return (
    <>
      <PageHeader
        title="Simulações salvas"
        description="Somente você tem acesso às suas simulações."
        actions={
          <LinkButton href="/simulador">
            <Plus className="size-4" aria-hidden="true" /> Nova simulação
          </LinkButton>
        }
      />
      <Panel>
        <FilterForm action="/simulador/salvas" resetHref="/simulador/salvas">
          <Field id="q" label="Buscar" className="w-64">
            <Input id="q" name="q" defaultValue={sp.q} placeholder="Nome ou ativo" />
          </Field>
        </FilterForm>
        <div className="mt-4">
          {page.items.length === 0 ? (
            <EmptyState title="Nenhuma simulação salva" action={<LinkButton href="/simulador" size="sm">Abrir simulador</LinkButton>} />
          ) : (
            <>
              <Table caption="Simulações salvas">
                <thead>
                  <tr>
                    <Th>Nome</Th>
                    <Th>Boleta</Th>
                    <Th>Ativo</Th>
                    <Th className="text-right">Referência</Th>
                    <Th>Vencimento</Th>
                    <Th className="text-right">Pernas</Th>
                    <Th className="text-right">Montagem</Th>
                    <Th>Atualizada</Th>
                    <Th>
                      <span className="sr-only">Ações</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((s) => (
                    <tr key={s.id}>
                      <Td>
                        <Link href={`/simulador/${s.id}`} className="font-medium text-brand-700 underline">
                          {s.name}
                        </Link>
                      </Td>
                      <Td>{SIM_MODE_LABEL[s.mode]}</Td>
                      <Td>{s.underlyingTicker}</Td>
                      <Td className="text-right tabular">{formatBRL(s.spotPrice)}</Td>
                      <Td>{formatDate(s.expiration)}</Td>
                      <Td className="text-right">{s.legs.length}</Td>
                      <Td className="text-right">
                        <CashFlow value={s.initialCashFlow} />
                      </Td>
                      <Td className="tabular">{formatDateTime(s.updatedAt)}</Td>
                      <Td>
                        <ActionButton
                          method="DELETE"
                          url={`/api/simulacoes/${s.id}`}
                          variant="ghost"
                          confirm={{ title: "Excluir simulação?", description: `“${s.name}” será excluída permanentemente.` }}
                          confirmLabel="Excluir"
                        >
                          Excluir
                        </ActionButton>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={page.page} pageCount={page.pageCount} total={page.total} basePath="/simulador/salvas" params={{ q: sp.q }} />
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
