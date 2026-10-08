import { requirePageCtx } from "@/server/session";
import { listAuditEvents } from "@/server/services/audit-log";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { Field, Input, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { Table, Td, Th } from "@/components/ui/table";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Auditoria" };

export default async function AuditPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx(["ADMIN"]);
  const sp = await searchParams;
  const data = await listAuditEvents(ctx, {
    page: Number(sp.pagina ?? 1),
    actor: sp.ator,
    action: sp.acao,
    resourceType: sp.recurso,
    requestId: sp.requisicao,
    from: sp.de,
    to: sp.ate,
  });
  const params = { ator: sp.ator, acao: sp.acao, recurso: sp.recurso, requisicao: sp.requisicao, de: sp.de, ate: sp.ate };
  return (
    <>
      <PageHeader title="Auditoria" description="Registro de ator, ação, recurso, horário e identificador da requisição. Senhas e tokens nunca são registrados." />
      <Panel>
        <FilterForm action="/admin/auditoria" resetHref="/admin/auditoria">
          <Field id="ator" label="Ator (e-mail)" className="w-48">
            <Input id="ator" name="ator" defaultValue={sp.ator} />
          </Field>
          <Field id="acao" label="Ação (prefixo)" className="w-40">
            <Input id="acao" name="acao" defaultValue={sp.acao} placeholder="ex.: auth." />
          </Field>
          <Field id="recurso" label="Recurso" className="w-40">
            <Select id="recurso" name="recurso" defaultValue={sp.recurso ?? ""}>
              <option value="">Todos</option>
              {data.resourceTypes.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="requisicao" label="ID da requisição" className="w-64">
            <Input id="requisicao" name="requisicao" defaultValue={sp.requisicao} />
          </Field>
          <Field id="de" label="De" className="w-40">
            <Input id="de" name="de" type="date" defaultValue={sp.de} />
          </Field>
          <Field id="ate" label="Até" className="w-40">
            <Input id="ate" name="ate" type="date" defaultValue={sp.ate} />
          </Field>
        </FilterForm>
        <div className="mt-4">
          {data.items.length === 0 ? (
            <EmptyState title="Nenhum evento encontrado" />
          ) : (
            <>
              <Table caption="Eventos de auditoria">
                <thead>
                  <tr>
                    <Th>Horário</Th>
                    <Th>Ator</Th>
                    <Th>Ação</Th>
                    <Th>Recurso</Th>
                    <Th>Requisição / IP</Th>
                    <Th>Detalhes</Th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((e) => (
                    <tr key={e.id}>
                      <Td className="tabular">{formatDateTime(e.createdAt)}</Td>
                      <Td>{e.actorEmail ?? <span className="text-slate-400">anônimo</span>}</Td>
                      <Td className="font-mono text-xs">{e.action}</Td>
                      <Td className="text-xs">
                        {e.resourceType}
                        {e.resourceId && <span className="block font-mono text-slate-500">{e.resourceId}</span>}
                      </Td>
                      <Td className="font-mono text-xs">
                        {e.requestId}
                        {e.ipAddress && <span className="block text-slate-500">{e.ipAddress}</span>}
                      </Td>
                      <Td className="max-w-72 text-xs">
                        {e.metadata ? <code className="break-all text-slate-600">{JSON.stringify(e.metadata)}</code> : "—"}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Pagination page={data.page} pageCount={data.pageCount} total={data.total} basePath="/admin/auditoria" params={params} />
            </>
          )}
        </div>
      </Panel>
    </>
  );
}
