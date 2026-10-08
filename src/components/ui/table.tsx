import type { ComponentProps } from "react";
import { cn } from "./cn";

/** Tabela responsiva: rolagem horizontal contida no próprio contêiner. */
export function Table({ className, caption, children, ...props }: ComponentProps<"table"> & { caption?: string }) {
  return (
    <div className="relative -mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0" tabIndex={0} role="region" aria-label={caption ?? "Tabela"}>
      <table className={cn("w-full min-w-max border-collapse text-sm", className)} {...props}>
        {caption && <caption className="sr-only">{caption}</caption>}
        {children}
      </table>
    </div>
  );
}
export const Th = ({ className, ...p }: ComponentProps<"th">) => (
  <th scope="col" className={cn("border-b border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600", className)} {...p} />
);
export const Td = ({ className, ...p }: ComponentProps<"td">) => <td className={cn("border-b border-slate-100 px-3 py-2 align-top", className)} {...p} />;
