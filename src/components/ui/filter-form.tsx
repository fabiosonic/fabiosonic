import type { ReactNode } from "react";
import { Search } from "lucide-react";
import { buttonClass } from "./button";

/** Formulário de filtros via GET (estado compartilhável na URL). */
export function FilterForm({ children, action, resetHref }: { children: ReactNode; action: string; resetHref?: string }) {
  return (
    <form method="get" action={action} className="flex flex-wrap items-end gap-3" role="search">
      {children}
      <button type="submit" className={buttonClass("primary", "md")}>
        <Search className="size-4" aria-hidden="true" /> Filtrar
      </button>
      {resetHref && (
        <a href={resetHref} className={buttonClass("ghost", "md")}>
          Limpar
        </a>
      )}
    </form>
  );
}
