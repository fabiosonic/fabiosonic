import { requirePageCtx } from "@/server/session";
import { adminIndicators } from "@/server/services/audit-log";
import { PageHeader, Panel, Stat } from "@/components/ui/panel";
import { ActionButton } from "@/components/ui/action-button";
import { CONTENT_STATUS_LABEL, REQUEST_STATUS_LABEL, ROLE_LABEL } from "@/lib/labels";

export const metadata = { title: "Indicadores" };

function Breakdown<K extends string>({ labels, data }: { labels: Record<K, string>; data: Record<string, number> }) {
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {(Object.keys(labels) as K[]).map((k) => (
        <Stat key={k} label={labels[k]} value={data[k] ?? 0} />
      ))}
    </dl>
  );
}

export default async function AdminHome() {
  const ctx = await requirePageCtx(["ADMIN"]);
  const i = await adminIndicators(ctx);
  return (
    <>
      <PageHeader
        title="Indicadores"
        description="Números calculados a partir dos dados persistidos."
        actions={
          <ActionButton url="/api/admin/cotacoes" size="md" confirm={{ title: "Atualizar cotações demonstrativas?", description: "O provedor demonstrativo gera novos preços fictícios para os ativos." }}>
            Atualizar cotações (demo)
          </ActionButton>
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Panel title="Usuários ativos por perfil">
          <Breakdown labels={ROLE_LABEL} data={i.usersByRole} />
          <p className="mt-3 text-sm text-slate-500">{i.inactiveUsers} usuário(s) desativado(s).</p>
        </Panel>
        <Panel title="Pedidos de análise">
          <Breakdown labels={REQUEST_STATUS_LABEL} data={i.requestsByStatus} />
        </Panel>
        <Panel title="Operações prontas">
          <Breakdown labels={CONTENT_STATUS_LABEL} data={i.strategiesByStatus} />
        </Panel>
        <Panel title="Análises">
          <Breakdown labels={CONTENT_STATUS_LABEL} data={i.analysesByStatus} />
        </Panel>
        <Panel title="Atividade" className="lg:col-span-2">
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Simulações salvas" value={i.simulations} />
            <Stat label="Cursos publicados" value={i.publishedCourses} />
            <Stat label="Eventos de auditoria (24 h)" value={i.audit24h} />
            <Stat label="Falhas de login (24 h)" value={i.failedLogins24h} />
          </dl>
        </Panel>
      </div>
    </>
  );
}
