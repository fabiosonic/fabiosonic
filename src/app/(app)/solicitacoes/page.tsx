import Link from "next/link";
import { Plus } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { listRequests } from "@/server/services/requests";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { RequestStatusBadge } from "@/components/ui/badge";
import { Field, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { Table, Td, Th } from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";
import { REQUEST_STATUS_LABEL } from "@/lib/labels";

export const metadata = { title: "Pedidos de análise" };

export default async function RequestsPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const staff = isStaff(ctx.actor);
  const page = await listRequests(ctx, { page: Number(sp.pagina ?? 1), status: sp.situacao, mine: sp.meus === "1" });
  return (
    <>
      <PageHeader
        title="Pedidos de análise"
        description={staff ? "Pedidos de todos os usuários. Responda e atualize a situação." : "Solicite análises à equipe e acompanhe as respostas."}
        actions={
          <LinkButton href="/solicitacoes/nova">
            <Plus className="size-4" aria-hidden="true" /> Novo pedido
          </LinkButton>
        }
      />
      <Panel>
        <FilterForm action="/solicitacoes" resetHref="/solicitacoes">
          <Field id="situacao" label="Situação" className="w-40">
            <Select id="situacao" name="situacao" defaultValue={sp.situacao ?? ""}>
              <option value="">Todas</option>
              {Object.entries(REQUEST_STATUS_LABEL).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          {staff && (
            <Field id="meus" label="Responsável" className="w-44">
              <Select id="meus" name="meus" defaultValue={sp.meus ?? ""}>
                <option value="">Todos</option>
                <option value="1">Atribuídos a mim</option>
              </Select>
            </Field>
          )}
        </FilterForm>
        <div className="mt-4">
          {page.items.length === 0 ? (
            <EmptyState title="Nenhum pedido encontrado" action={<LinkButton href="/solicitacoes/nova" size="sm">Abrir pedido</LinkButton>} />
          ) : (
            <>
              <Table caption="Pedidos de análise">
                <thead>
                  <tr>
                    <Th>Assunto</Th>
                    <Th>Ativo</Th>
                    {staff && <Th>Solicitante</Th>}
                    <Th>Responsável</Th>
                    <Th>Situação</Th>
                    <Th>Atualizado</Th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((r) => (
                    <tr key={r.id}>
                      <Td>
                        <Link href={`/solicitacoes/${r.id}`} className="font-medium text-brand-700 underline">
                          {r.subject}
                        </Link>
                      </Td>
                      <Td>{r.assetTicker ?? "—"}</Td>
                      {staff && <Td>{r.userName}</Td>}
                      <Td>{r.assignedToName ?? "—"}</Td>
                      <Td>
                        <RequestStatusBadge status={r.status} />
                      </Td>
                      <Td className="tabular">{formatDateTime(r.updatedAt)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={page.page} pageCount={page.pageCount} total={page.total} basePath="/solicitacoes" params={{ situacao: sp.situacao, meus: sp.meus }} />
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
