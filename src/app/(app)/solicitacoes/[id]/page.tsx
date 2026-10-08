import { notFound } from "next/navigation";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { getRequest } from "@/server/services/requests";
import { AppError } from "@/server/errors";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge, RequestStatusBadge } from "@/components/ui/badge";
import { ActionButton } from "@/components/ui/action-button";
import { formatDateTime } from "@/lib/format";
import { REQUEST_STATUS_LABEL, ROLE_LABEL } from "@/lib/labels";
import { MessageForm, StatusForm } from "./request-actions";

export const metadata = { title: "Pedido de análise" };

export default async function RequestPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx();
  const { id } = await params;
  let r;
  try {
    r = await getRequest(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const staff = isStaff(ctx.actor);
  return (
    <>
      <PageHeader
        title={r.subject}
        description={`Aberto por ${r.userName}${r.userEmail ? ` (${r.userEmail})` : ""} em ${formatDateTime(r.createdAt)}${r.assetTicker ? ` · ativo ${r.assetTicker}` : ""}`}
        actions={<RequestStatusBadge status={r.status} />}
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Panel title="Pergunta">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{r.question}</p>
          </Panel>
          <Panel title="Histórico">
            <ol className="space-y-3" aria-label="Histórico do pedido">
              {r.events.map((e) => (
                <li key={e.id} className={e.kind === "MESSAGE" ? "rounded-md border border-slate-200 p-3" : "text-sm text-slate-600"}>
                  {e.kind === "MESSAGE" ? (
                    <>
                      <p className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                        <span className="font-medium text-slate-800">{e.authorName}</span>
                        <Badge tone={e.authorRole === "USER" ? "neutral" : "brand"}>{ROLE_LABEL[e.authorRole]}</Badge>
                        {formatDateTime(e.createdAt)}
                      </p>
                      <p className="mt-1 whitespace-pre-wrap text-sm text-slate-800">{e.body}</p>
                    </>
                  ) : e.kind === "CREATED" ? (
                    <p>
                      {formatDateTime(e.createdAt)} — pedido aberto por {e.authorName}.
                    </p>
                  ) : (
                    <p>
                      {formatDateTime(e.createdAt)} — {e.authorName} alterou a situação de “{e.fromStatus ? REQUEST_STATUS_LABEL[e.fromStatus] : "—"}” para “
                      {e.toStatus ? REQUEST_STATUS_LABEL[e.toStatus] : "—"}”.
                    </p>
                  )}
                </li>
              ))}
            </ol>
          </Panel>
          {r.status !== "CLOSED" ? (
            <MessageForm requestId={r.id} staffReply={staff && !r.isOwner} />
          ) : (
            <p className="text-sm text-slate-500">Pedido encerrado em {formatDateTime(r.closedAt)}. Abra um novo pedido se precisar.</p>
          )}
        </div>
        <div className="space-y-4">
          <Panel title="Situação">
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Atual</dt>
                <dd>
                  <RequestStatusBadge status={r.status} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Responsável</dt>
                <dd>{r.assignedToName ?? "—"}</dd>
              </div>
            </dl>
            <div className="mt-4">
              {staff ? (
                <StatusForm requestId={r.id} current={r.status} />
              ) : (
                r.status !== "CLOSED" && (
                  <ActionButton
                    url={`/api/solicitacoes/${r.id}/situacao`}
                    body={{ status: "CLOSED" }}
                    confirm={{ title: "Encerrar pedido?", description: "Pedidos encerrados não recebem novas mensagens." }}
                    confirmLabel="Encerrar"
                    size="md"
                  >
                    Encerrar pedido
                  </ActionButton>
                )
              )}
            </div>
          </Panel>
        </div>
      </div>
    </>
  );
}
