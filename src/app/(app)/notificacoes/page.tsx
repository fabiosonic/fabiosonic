import Link from "next/link";
import { requirePageCtx } from "@/server/session";
import { listNotifications } from "@/server/services/notifications";
import { PageHeader, Panel } from "@/components/ui/panel";
import { EmptyState } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { ActionButton } from "@/components/ui/action-button";
import { Pagination } from "@/components/ui/pagination";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Notificações" };

export default async function NotificationsPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const unreadOnly = sp.filtro === "nao-lidas";
  const page = await listNotifications(ctx, { page: Number(sp.pagina ?? 1), unreadOnly });
  return (
    <>
      <PageHeader
        title="Notificações"
        description="Avisos da plataforma: respostas a pedidos, novos conteúdos e eventos."
        actions={<ActionButton url="/api/notificacoes/lidas" size="md">Marcar todas como lidas</ActionButton>}
      />
      <nav className="mb-3 flex gap-3 text-sm" aria-label="Filtro de notificações">
        <Link href="/notificacoes" aria-current={!unreadOnly ? "page" : undefined} className={!unreadOnly ? "font-semibold text-brand-800" : "text-brand-700 underline"}>
          Todas
        </Link>
        <Link href="/notificacoes?filtro=nao-lidas" aria-current={unreadOnly ? "page" : undefined} className={unreadOnly ? "font-semibold text-brand-800" : "text-brand-700 underline"}>
          Não lidas
        </Link>
      </nav>
      <Panel bodyClassName="p-0">
        {page.items.length === 0 ? (
          <div className="p-4">
            <EmptyState title="Nenhuma notificação" />
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {page.items.map((n) => (
              <li key={n.id} className="flex flex-wrap items-start justify-between gap-2 px-4 py-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium text-slate-900">
                    {!n.readAt && <Badge tone="info">Nova</Badge>}
                    {n.link ? (
                      <Link href={n.link} className="hover:underline">
                        {n.title}
                      </Link>
                    ) : (
                      n.title
                    )}
                  </p>
                  <p className="text-sm text-slate-600">{n.body}</p>
                  <p className="text-xs text-slate-500">{formatDateTime(n.createdAt)}</p>
                </div>
                {!n.readAt && (
                  <ActionButton url={`/api/notificacoes/${n.id}/lida`} variant="ghost">
                    Marcar como lida
                  </ActionButton>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Pagination page={page.page} pageCount={page.pageCount} total={page.total} basePath="/notificacoes" params={{ filtro: sp.filtro }} />
    </>
  );
}
