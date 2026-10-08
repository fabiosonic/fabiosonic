import Link from "next/link";
import { CalendarDays, MessageSquare, RefreshCw } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getDashboard } from "@/server/services/dashboard";
import { PageHeader, Panel, Stat } from "@/components/ui/panel";
import { ConnectionBadge, ContentStatusBadge, DataSourceBadge, Badge } from "@/components/ui/badge";
import { SignedMoney } from "@/components/ui/money";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { Table, Td, Th } from "@/components/ui/table";
import { DistributionChart } from "@/components/charts/distribution-chart";
import { formatBRL, formatDate, formatDateTime, formatPct } from "@/lib/format";
import { LIVE_KIND_LABEL, STRATEGY_TYPES, type StrategyType } from "@/lib/labels";

export const metadata = { title: "Painel" };

export default async function DashboardPage() {
  const ctx = await requirePageCtx();
  const d = await getDashboard(ctx);
  const p = d.portfolio;

  return (
    <>
      <PageHeader title={`Olá, ${ctx.actor.name.split(" ")[0]}`} description="Resumo da sua carteira, conteúdos publicados e próximos eventos." />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Panel
          className="lg:col-span-2"
          title="Resumo da carteira"
          description={`Origem: conexão B3 demonstrativa e/ou importação CSV${p.lastReferenceDate ? ` · data-base ${formatDate(p.lastReferenceDate)} (D+1)` : ""}`}
          actions={<LinkButton href="/carteira" variant="secondary" size="sm">Ver carteira</LinkButton>}
        >
          {d.summary.positions === 0 ? (
            <EmptyState title="Nenhuma posição registrada" action={<LinkButton href="/carteira" size="sm">Conectar ou importar</LinkButton>}>
              Conecte a carteira em modo demonstrativo ou importe um arquivo CSV.
            </EmptyState>
          ) : (
            <>
              <dl className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                <Stat label="Posições" value={d.summary.positions} />
                <Stat label="Custo total" value={formatBRL(d.summary.totalCost)} hint="Quantidade × preço médio" />
                <Stat
                  label="Valor estimado"
                  value={formatBRL(d.summary.totalMarket)}
                  hint={d.summary.allPriced ? "Cotações demonstrativas" : "Parte avaliada pelo custo"}
                />
                <Stat label="Resultado estimado" value={<SignedMoney value={d.summary.result} />} hint="Não realizado" />
              </dl>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <DistributionChart data={d.distribution} />
                <Table caption="Distribuição por ativo">
                  <thead>
                    <tr>
                      <Th>Ativo</Th>
                      <Th className="text-right">Valor</Th>
                      <Th className="text-right">Participação</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.distribution.map((x) => (
                      <tr key={x.ticker}>
                        <Td className="font-medium">{x.ticker}</Td>
                        <Td className="text-right tabular">
                          {formatBRL(x.value)}
                          {x.basis === "custo" && <span className="block text-xs text-slate-500">pelo custo</span>}
                        </Td>
                        <Td className="text-right tabular">{formatPct(x.pct).replace("+", "")}</Td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </div>
            </>
          )}
        </Panel>

        <Panel title="Sincronização" actions={<ConnectionBadge status={p.connectionStatus} />}>
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-slate-500">Provedor</dt>
              <dd className="font-medium">{p.connectionProvider === "DEMO" ? "B3 — modo demonstrativo" : "Não conectado"}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Última sincronização</dt>
              <dd className="font-medium">{formatDateTime(p.lastSyncAt)}</dd>
            </div>
            <div>
              <dt className="text-slate-500">Data-base das posições</dt>
              <dd className="font-medium">{formatDate(p.lastReferenceDate)}</dd>
            </div>
            {p.lastError && (
              <div>
                <dt className="text-slate-500">Último erro</dt>
                <dd className="text-loss-700">{p.lastError}</dd>
              </div>
            )}
            <div>
              <dt className="text-slate-500">Cotações</dt>
              <dd className="flex flex-wrap items-center gap-2">
                {d.marketData ? (
                  <>
                    <DataSourceBadge source={d.marketData.dataSource} />
                    <span>{formatDateTime(d.marketData.priceAt)}</span>
                  </>
                ) : (
                  "—"
                )}
              </dd>
            </div>
          </dl>
          <LinkButton href="/carteira" variant="secondary" size="sm" className="mt-4">
            <RefreshCw className="size-4" aria-hidden="true" /> Gerenciar conexão
          </LinkButton>
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Panel title="Últimas operações prontas" actions={<Link href="/operacoes" className="text-sm text-brand-700 underline">Ver todas</Link>}>
          {d.strategies.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma operação publicada.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.strategies.map((s) => (
                <li key={s.id} className="py-2">
                  <Link href={`/operacoes/${s.id}`} className="font-medium text-slate-900 hover:underline">
                    {s.title}
                  </Link>
                  <p className="text-xs text-slate-500">
                    {s.assetTicker} · {STRATEGY_TYPES[s.strategyType as StrategyType] ?? s.strategyType} · vence {formatDate(s.expiration)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Últimas análises" actions={<Link href="/analises" className="text-sm text-brand-700 underline">Ver todas</Link>}>
          {d.analyses.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma análise publicada.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.analyses.map((a) => (
                <li key={a.id} className="py-2">
                  <Link href={`/analises/${a.id}`} className="font-medium text-slate-900 hover:underline">
                    {a.title}
                  </Link>
                  <p className="flex items-center gap-2 text-xs text-slate-500">
                    {a.assetTicker ?? "Geral"} · {formatDateTime(a.publishedAt)}
                    {a.status !== "PUBLISHED" && <ContentStatusBadge status={a.status} />}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Próximas lives e aulas" actions={<Link href="/agenda" className="text-sm text-brand-700 underline">Agenda</Link>}>
          {d.lives.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhum evento agendado.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {d.lives.map((l) => (
                <li key={l.id} className="flex items-start gap-2 py-2">
                  <CalendarDays className="mt-0.5 size-4 shrink-0 text-slate-400" aria-hidden="true" />
                  <div>
                    <p className="font-medium text-slate-900">{l.title}</p>
                    <p className="text-xs text-slate-500">
                      {LIVE_KIND_LABEL[l.kind]} · {formatDateTime(l.startsAt)}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3 text-sm">
            <MessageSquare className="size-4 text-slate-400" aria-hidden="true" />
            <Link href="/solicitacoes" className="text-brand-700 underline">
              Pedidos de análise em aberto
            </Link>
            <Badge tone="info">{d.openRequests}</Badge>
          </p>
        </Panel>
      </div>
    </>
  );
}
