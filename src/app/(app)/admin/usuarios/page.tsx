import { requirePageCtx } from "@/server/session";
import { listUsers } from "@/server/services/users";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge } from "@/components/ui/badge";
import { Field, Input, Select } from "@/components/ui/field";
import { FilterForm } from "@/components/ui/filter-form";
import { Pagination } from "@/components/ui/pagination";
import { Table, Td, Th } from "@/components/ui/table";
import { EmptyState } from "@/components/ui/alert";
import { formatDate } from "@/lib/format";
import { ROLE_LABEL } from "@/lib/labels";
import { NewUserForm, UserRowActions } from "./user-forms";

export const metadata = { title: "Usuários" };

export default async function UsersPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx(["ADMIN"]);
  const sp = await searchParams;
  const page = await listUsers(ctx, { page: Number(sp.pagina ?? 1), search: sp.q, role: sp.perfil, active: sp.ativo });
  return (
    <>
      <PageHeader title="Usuários" description="Crie contas, altere perfis e desative acessos. Alterações encerram as sessões abertas do usuário." />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Panel className="xl:col-span-2">
          <FilterForm action="/admin/usuarios" resetHref="/admin/usuarios">
            <Field id="q" label="Buscar" className="w-56">
              <Input id="q" name="q" defaultValue={sp.q} placeholder="Nome ou e-mail" />
            </Field>
            <Field id="perfil" label="Perfil" className="w-40">
              <Select id="perfil" name="perfil" defaultValue={sp.perfil ?? ""}>
                <option value="">Todos</option>
                {Object.entries(ROLE_LABEL).map(([k, l]) => (
                  <option key={k} value={k}>
                    {l}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="ativo" label="Situação" className="w-36">
              <Select id="ativo" name="ativo" defaultValue={sp.ativo ?? ""}>
                <option value="">Todas</option>
                <option value="true">Ativos</option>
                <option value="false">Desativados</option>
              </Select>
            </Field>
          </FilterForm>
          <div className="mt-4">
            {page.items.length === 0 ? (
              <EmptyState title="Nenhum usuário encontrado" />
            ) : (
              <Table caption="Usuários">
                <thead>
                  <tr>
                    <Th>Nome</Th>
                    <Th>E-mail</Th>
                    <Th>Perfil</Th>
                    <Th>Situação</Th>
                    <Th>Criado em</Th>
                    <Th>Ações</Th>
                  </tr>
                </thead>
                <tbody>
                  {page.items.map((u) => (
                    <tr key={u.id}>
                      <Td className="font-medium">
                        {u.name}
                        {u.isDemo && (
                          <Badge tone="warning" className="ml-1">
                            demo
                          </Badge>
                        )}
                      </Td>
                      <Td>{u.email}</Td>
                      <Td>{ROLE_LABEL[u.role]}</Td>
                      <Td>{u.active ? <Badge tone="success">Ativo</Badge> : <Badge tone="danger">Desativado</Badge>}</Td>
                      <Td>{formatDate(u.createdAt)}</Td>
                      <Td>
                        <UserRowActions user={{ id: u.id, name: u.name, role: u.role, active: u.active }} self={u.id === ctx.actor.id} />
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            <Pagination page={page.page} pageCount={page.pageCount} total={page.total} basePath="/admin/usuarios" params={{ q: sp.q, perfil: sp.perfil, ativo: sp.ativo }} />
          </div>
        </Panel>
        <NewUserForm />
      </div>
    </>
  );
}
