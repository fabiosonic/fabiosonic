"use client";

import { AlertTriangle, Infinity as InfinityIcon } from "lucide-react";
import { PayoffChart } from "@/components/charts/payoff-chart";
import { Panel, Stat } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { CashFlow, SignedMoney } from "@/components/ui/money";
import { Table, Td, Th } from "@/components/ui/table";
import { formatBRL, formatPct } from "@/lib/format";
import type { ComputeResult } from "./compute";

function Extreme({ unlimited, value, kind, at }: { unlimited: boolean; value: number | null; kind: "ganho" | "perda"; at: number | null }) {
  if (unlimited)
    return (
      <span className={`inline-flex items-center gap-1 font-semibold ${kind === "perda" ? "text-loss-700" : "text-gain-700"}`}>
        <InfinityIcon className="size-4" aria-hidden="true" /> Teoricamente ilimitado
      </span>
    );
  return (
    <span className="inline-flex flex-col">
      <SignedMoney value={value} />
      {at !== null && <span className="text-xs font-normal text-slate-500">com o ativo a {formatBRL(at)}{at === 0 ? " (preço zero)" : ""}</span>}
    </span>
  );
}

export function Results({ result, showScenarios }: { result: ComputeResult; showScenarios: boolean }) {
  if (!result.ok) {
    return (
      <Panel title="Resultado no vencimento">
        <Alert tone="info" title="Complete os dados para calcular">
          {result.general.length > 0 ? result.general.join(" ") : "Corrija os campos destacados nas pernas."}
        </Alert>
      </Panel>
    );
  }
  const r = result;
  return (
    <div className="space-y-4">
      <Panel title="Resultado no vencimento" description="Payoff calculado no vencimento. Não é cotação antes do vencimento, previsão de mercado nem garantia de resultado.">
        <dl className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat label="Montagem" value={<CashFlow value={r.initialCashFlow} />} hint={r.flow === "CREDITO" ? "Valor recebido" : r.flow === "DEBITO" ? "Valor pago" : "Sem fluxo"} />
          <Stat
            label="Ponto(s) de equilíbrio"
            value={r.breakevens.length ? r.breakevens.map((b) => formatBRL(b)).join(" · ") : "Nenhum"}
            hint={r.breakevens.length > 1 ? `${r.breakevens.length} pontos` : undefined}
          />
          <Stat label="Ganho máximo" value={<Extreme unlimited={r.maxProfitUnlimited} value={r.maxProfit} kind="ganho" at={r.maxProfitAt} />} />
          <Stat label="Perda máxima" value={<Extreme unlimited={r.maxLossUnlimited} value={r.maxLoss} kind="perda" at={r.maxLossAt} />} />
        </dl>
        {r.maxLossUnlimited && (
          <Alert tone="error" title="Perda teoricamente ilimitada" className="mt-4">
            A estratégia perde valor sem limite se o ativo subir indefinidamente (há venda a descoberto de CALL ou posição vendida sem proteção).
          </Alert>
        )}
        <div className="mt-4">
          <PayoffChart data={r.chart} reference={r.reference} breakevens={r.breakevens} scenarios={showScenarios ? r.scenarios : []} />
        </div>
      </Panel>

      {showScenarios && (
        <Panel title="Cenários de previsão" description="Resultado no vencimento para os preços que você definiu. Nenhuma probabilidade é atribuída aos cenários.">
          {r.scenarios.length === 0 ? (
            <p className="text-sm text-slate-500">Adicione cenários de preço para comparar.</p>
          ) : (
            <Table caption="Resultados por cenário">
              <thead>
                <tr>
                  <Th>Cenário</Th>
                  <Th className="text-right">Preço do ativo</Th>
                  <Th className="text-right">Variação</Th>
                  <Th className="text-right">Resultado no vencimento</Th>
                </tr>
              </thead>
              <tbody>
                {r.scenarios.map((s, i) => (
                  <tr key={`${s.label}-${i}`}>
                    <Td className="font-medium">{s.label}</Td>
                    <Td className="text-right tabular">{formatBRL(s.price)}</Td>
                    <Td className="text-right tabular">{s.changePct === null ? "—" : formatPct(s.changePct)}</Td>
                    <Td className="text-right">
                      <SignedMoney value={s.result} />
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Panel>
      )}

      <Panel title="Tabela de cenários" description="Variações de −20% a +20% sobre o preço de referência, mais os pontos de equilíbrio.">
        <Table caption="Resultado no vencimento por preço do ativo">
          <thead>
            <tr>
              <Th className="text-right">Preço do ativo</Th>
              <Th className="text-right">Variação</Th>
              <Th className="text-right">Resultado no vencimento</Th>
            </tr>
          </thead>
          <tbody>
            {r.table.map((row) => (
              <tr key={row.price} className={r.breakevens.includes(row.price) ? "bg-amber-50" : undefined}>
                <Td className="text-right tabular">
                  {formatBRL(row.price)}
                  {r.breakevens.includes(row.price) && <span className="ml-1 text-xs text-amber-800">(equilíbrio)</span>}
                </Td>
                <Td className="text-right tabular">{row.changePct === null ? "—" : formatPct(row.changePct)}</Td>
                <Td className="text-right">
                  <SignedMoney value={row.result} />
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
        <p className="mt-3 flex items-start gap-1.5 text-xs text-slate-500">
          <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Simulação educacional. Nenhuma ordem é enviada. Custos considerados apenas como valor fixo informado; tributos, margem e ajustes não são calculados.
        </p>
      </Panel>
    </div>
  );
}
