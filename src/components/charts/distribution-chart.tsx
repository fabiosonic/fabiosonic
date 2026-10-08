"use client";

import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatBRL, formatPct } from "@/lib/format";

export interface DistributionItem {
  ticker: string;
  value: number;
  pct: number;
}

/** Barras horizontais por ativo. A tabela ao lado/abaixo é a alternativa textual. */
export function DistributionChart({ data }: { data: DistributionItem[] }) {
  const height = Math.max(160, data.length * 38 + 30);
  return (
    <figure aria-label="Gráfico de distribuição da carteira por ativo" className="w-full">
      <div style={{ height }} aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
            <CartesianGrid horizontal={false} stroke="#e2e8f0" />
            <XAxis type="number" tickFormatter={(v: number) => formatPct(v).replace("+", "")} domain={[0, 100]} fontSize={12} stroke="#64748b" dataKey="pct" />
            <YAxis type="category" dataKey="ticker" width={64} fontSize={12} stroke="#64748b" />
            <Tooltip
              formatter={(_v, _n, item) => [`${formatPct((item.payload as DistributionItem).pct).replace("+", "")} · ${formatBRL((item.payload as DistributionItem).value)}`, "Participação"]}
            />
            <Bar dataKey="pct" name="Participação (%)" fill="#0e6b78" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="sr-only">Participação percentual de cada ativo no valor total da carteira. Os valores estão na tabela a seguir.</figcaption>
    </figure>
  );
}
