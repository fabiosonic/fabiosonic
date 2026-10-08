"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatBRL } from "@/lib/format";

/**
 * Gráfico de resultado NO VENCIMENTO (não é cotação antes do vencimento nem previsão).
 * Linhas de referência: preço atual (tracejada), pontos de equilíbrio (pontilhadas) e cenários.
 */
export function PayoffChart({
  data,
  reference,
  breakevens,
  scenarios = [],
}: {
  data: { price: number; result: number }[];
  reference: number;
  breakevens: number[];
  scenarios?: { label: string; price: number }[];
}) {
  return (
    <figure className="w-full" aria-label="Gráfico do resultado da estratégia no vencimento">
      <div className="h-72 sm:h-80" aria-hidden="true">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 16, right: 16, bottom: 8, left: 8 }}>
            <CartesianGrid stroke="#e2e8f0" />
            <XAxis
              dataKey="price"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: 2 })}
              fontSize={12}
              stroke="#64748b"
              label={{ value: "Preço do ativo no vencimento (R$)", position: "insideBottom", offset: -4, fontSize: 12, fill: "#475569" }}
              height={44}
            />
            <YAxis tickFormatter={(v: number) => v.toLocaleString("pt-BR", { maximumFractionDigits: 0 })} fontSize={12} stroke="#64748b" width={64} label={{ value: "R$", position: "insideTopLeft", offset: 0, fontSize: 11, fill: "#475569" }} />
            <Tooltip
              formatter={(v) => [formatBRL(Number(v)), "Resultado no vencimento"]}
              labelFormatter={(l) => `Ativo a ${formatBRL(Number(l))}`}
            />
            <ReferenceLine y={0} stroke="#334155" />
            <ReferenceLine x={reference} stroke="#0b5763" strokeDasharray="6 4" label={{ value: "Atual", fontSize: 11, fill: "#0b5763", position: "insideTopRight" }} />
            {breakevens.map((b) => (
              <ReferenceLine key={b} x={b} stroke="#b45309" strokeDasharray="2 3" />
            ))}
            {scenarios.map((s) => (
              <ReferenceLine key={`${s.label}-${s.price}`} x={s.price} stroke="#7c3aed" strokeDasharray="4 2" label={{ value: s.label, fontSize: 11, fill: "#6d28d9", position: "insideTop" }} />
            ))}
            <Line type="linear" dataKey="result" name="Resultado no vencimento" stroke="#0e6b78" strokeWidth={2} dot={false} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="mt-1 text-xs text-slate-500">
        Linha tracejada azul: preço de referência. Linhas pontilhadas laranja: pontos de equilíbrio. A tabela de cenários apresenta os mesmos valores em texto.
      </figcaption>
    </figure>
  );
}
