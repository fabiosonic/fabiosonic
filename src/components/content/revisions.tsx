import { Panel } from "@/components/ui/panel";
import { formatDateTime } from "@/lib/format";

const ACTION: Record<string, string> = {
  create: "Criação",
  update: "Edição",
  publish: "Publicação",
  archive: "Arquivamento",
  unarchive: "Reativação",
};

export function Revisions({ items }: { items: { id: string; action: string; actorName: string; changes: unknown; createdAt: string }[] }) {
  return (
    <Panel title="Histórico de alterações" description="Visível apenas para a equipe.">
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">Sem registros.</p>
      ) : (
        <ol className="space-y-3 text-sm">
          {items.map((r) => (
            <li key={r.id} className="border-l-2 border-slate-200 pl-3">
              <p className="font-medium text-slate-800">
                {ACTION[r.action] ?? r.action} · {r.actorName}
              </p>
              <p className="text-xs text-slate-500">{formatDateTime(r.createdAt)}</p>
              {r.changes && typeof r.changes === "object" ? (
                <p className="mt-0.5 text-xs text-slate-600">Campos: {Object.keys(r.changes as object).join(", ")}</p>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </Panel>
  );
}
