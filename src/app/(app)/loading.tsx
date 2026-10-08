export default function Loading() {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">Carregando…</span>
      <div className="h-7 w-56 animate-pulse rounded bg-slate-200" />
      <div className="h-32 animate-pulse rounded-lg bg-slate-200/70" />
      <div className="h-64 animate-pulse rounded-lg bg-slate-200/50" />
    </div>
  );
}
