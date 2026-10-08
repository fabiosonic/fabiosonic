import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { formatBRL } from "@/lib/format";
import { cn } from "./cn";

/**
 * Valor com sinal: usa texto (+/−), ícone e rótulo para leitores de tela,
 * além da cor — lucro/perda nunca é comunicado apenas por cor.
 */
export function SignedMoney({ value, className, positiveLabel = "ganho", negativeLabel = "perda" }: { value: number | string | null; className?: string; positiveLabel?: string; negativeLabel?: string }) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return <span>—</span>;
  const n = Number(value);
  const Icon = n > 0 ? ArrowUpRight : n < 0 ? ArrowDownRight : Minus;
  const label = n > 0 ? positiveLabel : n < 0 ? negativeLabel : "zero";
  return (
    <span className={cn("inline-flex items-center gap-0.5 tabular font-medium", n > 0 && "text-gain-700", n < 0 && "text-loss-700", className)}>
      <Icon className="size-3.5" aria-hidden="true" />
      {n > 0 ? "+" : ""}
      {formatBRL(n)}
      <span className="sr-only"> ({label})</span>
    </span>
  );
}

export function CashFlow({ value }: { value: number | string }) {
  const n = Number(value);
  return (
    <span className={cn("tabular font-medium", n > 0 && "text-gain-700", n < 0 && "text-loss-700")}>
      {formatBRL(Math.abs(n))} {n > 0 ? "(crédito)" : n < 0 ? "(débito)" : ""}
    </span>
  );
}
