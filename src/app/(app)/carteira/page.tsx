import { Upload } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getPortfolio } from "@/server/services/portfolio";
import { PageHeader, Panel } from "@/components/ui/panel";
import { Badge, DataSourceBadge, SyncBadge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { ActionButton } from "@/components/ui/action-button";
import { SignedMoney } from "@/components/ui/money";
import { Table, Td, Th } from "@/components/ui/table";
import { formatBRL, formatDate, formatDateTime, formatInt } from "@/lib/format";
import { INSTRUMENT_TYPE_LABEL, POSITION_SOURCE_LABEL } from "@/lib/labels";
import { ConnectionPanel } from "./connection-panel";

export const metadata = { title: "Carteira" };

export default async function PortfolioPage() {
  const ctx = await requirePageCtx();
  const data = await getPortfolio(ctx);
  const { portfolio, positions, syncRuns, imports } = data;

  return (
    <>
      <PageHeader
        title="Carteira"
        description="Posições consolidadas pela conexão B3 (modo demonstrativo) e por importação CSV. Na B3, as posições ficam disponíveis no dia útil seguinte (D+1)."
        actions={
          <LinkButton href="/carteira/importar" variant="secondary">
            <Upload className="size-4" aria-hidden="true" /> Importar CSV
          </LinkButton>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <ConnectionPanel portfolio={portfolio} />

        <Panel
          className="lg:col-span-2"
          title="Posições"
          description={portfolio.lastReferenceDate ? `Data-base da última sincronização: ${formatDate(portfolio.lastReferenceDate)}` : undefined}
          bodyClassName="p-0 sm:p-4"
        >
          {positions.length === 0 ? (
            <div className="p-4 sm:p-0">
              <EmptyState title="Nenhuma posição">Conecte a carteira (demonstração) e sincronize, ou importe um arquivo CSV.</EmptyState>
            </div>
          ) : (
            <div className="px-4 pb-4 sm:p-0">
              <Table caption="Posições da carteira">
                <thead>
                  <tr>
                    <Th>Ativo</Th>
                    <Th>Tipo</Th>
                    <Th className="text-right">Qtd.</Th>
                    <Th className="text-right">Preço médio</Th>
                    <Th className="text-right">Custo</Th>
                    <Th className="text-right">Cotação</Th>
                    <Th className="text-right">Resultado est.</Th>
                    <Th>Origem / data-base</Th>
                    <Th>
                      <span className="sr-only">Ações</span>
                    </Th>
                  </tr>
                </thead>
                <tbody>
                  {positions.map((p) => {
                    const result = p.marketValue !== null ? Number(p.marketValue) - Number(p.cost) : null;
                    return (
                      <tr key={p.id}>
                        <Td className="font-medium">{p.ticker}</Td>
                        <Td>{INSTRUMENT_TYPE_LABEL[p.instrumentType]}</Td>
                        <Td className="text-right tabular">{formatInt(p.quantity)}</Td>
                        <Td className="text-right tabular">{formatBRL(p.averagePrice)}</Td>
                        <Td className="text-right tabular">{formatBRL(p.cost)}</Td>
                        <Td className="text-right tabular">
                          {p.lastPrice ? (
                            <span className="inline-flex flex-col items-end gap-0.5">
                              {formatBRL(p.lastPrice)}
                              {p.priceSource && <DataSourceBadge source={p.priceSource} />}
                            </span>
                          ) : (
                            <span className="text-slate-400">sem cotação</span>
                          )}
                        </Td>
                        <Td className="text-right">{result === null ? "—" : <SignedMoney value={result} />}</Td>
                        <Td>
                          <Badge tone={p.source === "CSV" ? "info" : "brand"}>{POSITION_SOURCE_LABEL[p.source]}</Badge>
                          <span className="block text-xs text-slate-500">{formatDate(p.referenceDate)}</span>
                        </Td>
                        <Td>
                          {p.source === "CSV" && (
                            <ActionButton
                              method="DELETE"
                              url={`/api/carteira/posicoes/${p.id}`}
                              variant="ghost"
                              confirm={{ title: `Remover ${p.ticker}?`, description: "A posição importada por CSV será removida da carteira." }}
                              confirmLabel="Remover"
                            >
                              Remover
                            </ActionButton>
                          )}
                        </Td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </div>
          )}
        </Panel>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Panel title="Histórico de sincronizações" description="Últimas 10 execuções.">
          {syncRuns.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma sincronização realizada.</p>
          ) : (
            <Table caption="Histórico de sincronizações">
              <thead>
                <tr>
                  <Th>Início</Th>
                  <Th>Situação</Th>
                  <Th>Data-base</Th>
                  <Th className="text-right">Posições</Th>
                  <Th>Mensagem</Th>
                </tr>
              </thead>
              <tbody>
                {syncRuns.map((s) => (
                  <tr key={s.id}>
                    <Td className="tabular">{formatDateTime(s.startedAt)}</Td>
                    <Td>
                      <SyncBadge status={s.status} />
                    </Td>
                    <Td>{formatDate(s.referenceDate)}</Td>
                    <Td className="text-right tabular">{s.positionsCount}</Td>
                    <Td className="text-slate-600">{s.message ?? (s.provider === "DEMO" ? "Provedor demonstrativo" : "—")}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
        <Panel title="Importações CSV recentes">
          {imports.length === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma importação realizada.</p>
          ) : (
            <Table caption="Importações recentes">
              <thead>
                <tr>
                  <Th>Data</Th>
                  <Th>Arquivo</Th>
                  <Th className="text-right">Linhas</Th>
                  <Th className="text-right">Aplicadas</Th>
                  <Th className="text-right">Ignoradas</Th>
                </tr>
              </thead>
              <tbody>
                {imports.map((b) => (
                  <tr key={b.id}>
                    <Td className="tabular">{formatDateTime(b.createdAt)}</Td>
                    <Td className="max-w-48 truncate">{b.fileName}</Td>
                    <Td className="text-right tabular">{b.rowsTotal}</Td>
                    <Td className="text-right tabular">{b.rowsImported}</Td>
                    <Td className="text-right tabular">{b.rowsSkipped}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      </div>
    </>
  );
}
