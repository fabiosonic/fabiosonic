import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { buttonClass } from "./button";

/** Paginação por links (estado na URL), preservando os filtros atuais. */
export function Pagination({
  page,
  pageCount,
  total,
  basePath,
  params,
  pageParam = "pagina",
}: {
  page: number;
  pageCount: number;
  total: number;
  basePath: string;
  params: Record<string, string | undefined>;
  pageParam?: string;
}) {
  const href = (p: number) => {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v) sp.set(k, v);
    sp.set(pageParam, String(p));
    return `${basePath}?${sp.toString()}`;
  };
  return (
    <nav aria-label="Paginação" className="flex flex-wrap items-center justify-between gap-2 pt-3 text-sm text-slate-600">
      <span>
        Página {page} de {pageCount} · {total} registro(s)
      </span>
      <div className="flex gap-2">
        {page > 1 ? (
          <Link href={href(page - 1)} className={buttonClass("secondary", "sm")} rel="prev">
            <ChevronLeft className="size-4" aria-hidden="true" /> Anterior
          </Link>
        ) : (
          <span className={buttonClass("secondary", "sm", "pointer-events-none opacity-50")} aria-disabled="true">
            <ChevronLeft className="size-4" aria-hidden="true" /> Anterior
          </span>
        )}
        {page < pageCount ? (
          <Link href={href(page + 1)} className={buttonClass("secondary", "sm")} rel="next">
            Próxima <ChevronRight className="size-4" aria-hidden="true" />
          </Link>
        ) : (
          <span className={buttonClass("secondary", "sm", "pointer-events-none opacity-50")} aria-disabled="true">
            Próxima <ChevronRight className="size-4" aria-hidden="true" />
          </span>
        )}
      </div>
    </nav>
  );
}
