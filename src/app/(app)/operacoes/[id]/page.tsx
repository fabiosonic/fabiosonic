import { notFound } from "next/navigation";
import { Calculator, Pencil } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { isStaff } from "@/server/authz";
import { getStrategy, listRevisions } from "@/server/services/content";
import { AppError } from "@/server/errors";
import { PageHeader, Panel, Stat } from "@/components/ui/panel";
import { ContentStatusBadge, DataSourceBadge } from "@/components/ui/badge";
import { LinkButton } from "@/components/ui/button";
import { CashFlow } from "@/components/ui/money";
import { Alert } from "@/components/ui/alert";
import { Table, Td, Th } from "@/components/ui/table";
import { StatusActions } from "@/components/content/status-actions";
import { Revisions } from "@/components/content/revisions";
import { formatBRL, formatDate, formatDateTime, formatInt } from "@/lib/format";
import { INSTRUMENT_LABEL, SIDE_LABEL, STRATEGY_TYPES, type StrategyType } from "@/lib/labels";

export const metadata = { title: "Operação" };

export default async function StrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx();
  const { id } = await params;
  let s;
  try {
    s = await getStrategy(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const staff = isStaff(ctx.actor);
  const revisions = staff ? await listRevisions(ctx, "strategy", id) : [];
  const m = s.metrics;

  return (
    <>
      <PageHeader
        title={s.title}
        description={`${s.assetTicker} · ${STRATEGY_TYPES[s.strategyType as StrategyType] ?? s.strategyType} · vencimento ${formatDate(s.expiration)} · por ${s.authorName}${s.publishedAt ? ` · publicada em ${formatDateTime(s.publishedAt)}` : ""}`}
        actions={
          <>
            {staff && <ContentStatusBadge status={s.status} />}
            <LinkButton href={`/simulador?estrategia=${s.id}`} variant="secondary">
              <Calculator className="size-4" aria-hidden="true" /> Abrir no simulador
            </LinkButton>
            {staff && s.status !== "ARCHIVED" && (
              <LinkButton href={`/operacoes/${s.id}/editar`} variant="secondary">
                <Pencil className="size-4" aria-hidden="true" /> Editar
              </LinkButton>
            )}
            {staff && <StatusActions base={`/api/operacoes/${s.id}`} status={s.status} noun="operação" />}
          </>
        }
      />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="space-y-4 lg:col-span-2">
          <Panel title="Resumo">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{s.summary}</p>
            <dl className="mt-4 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-4">
              <Stat label="Montagem" value={<CashFlow value={m.initialCashFlow} />} />
              <Stat label="Equilíbrio" value={m.breakevens.map((b) => formatBRL(b)).join(" · ") || "—"} />
              <Stat label="Ganho máximo" value={m.maxProfitUnlimited ? "Ilimitado" : formatBRL(m.maxProfit)} />
              <Stat label="Perda máxima" value={m.maxLossUnlimited ? "Ilimitada" : formatBRL(m.maxLoss)} />
            </dl>
            {m.maxLossUnlimited && (
              <Alert tone="error" className="mt-3">
                Atenção: perda teoricamente ilimitada.
              </Alert>
            )}
          </Panel>
          <Panel title="Pernas">
            <Table caption="Pernas da operação">
              <thead>
                <tr>
                  <Th>Operação</Th>
                  <Th>Instrumento</Th>
                  <Th className="text-right">Strike</Th>
                  <Th className="text-right">Prêmio/preço</Th>
                  <Th className="text-right">Quantidade</Th>
                  <Th>Contrato</Th>
                </tr>
              </thead>
              <tbody>
                {s.legs.map((l, i) => (
                  <tr key={i}>
                    <Td>{SIDE_LABEL[l.side]}</Td>
                    <Td>{INSTRUMENT_LABEL[l.instrument]}</Td>
                    <Td className="text-right tabular">{l.strike ? formatBRL(l.strike) : "—"}</Td>
                    <Td className="text-right tabular">{formatBRL(l.premium)}</Td>
                    <Td className="text-right tabular">{formatInt(l.quantity)}</Td>
                    <Td className="font-mono text-xs">{l.optionSymbol ?? "—"}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
              Preço de referência {formatBRL(s.referencePrice)} · cotação atual {formatBRL(s.assetPrice)} <DataSourceBadge source={s.assetDataSource} />
            </p>
          </Panel>
          <Panel title="Premissas">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{s.assumptions}</p>
          </Panel>
          <Panel title="Riscos">
            <p className="whitespace-pre-wrap text-sm text-slate-700">{s.riskNotes}</p>
          </Panel>
        </div>
        <div className="space-y-4">
          <Alert tone="info" title="Conteúdo educacional">
            Valores calculados no vencimento a partir dos prêmios informados. Não constitui recomendação de investimento.
          </Alert>
          {staff && <Revisions items={revisions} />}
        </div>
      </div>
    </>
  );
}
