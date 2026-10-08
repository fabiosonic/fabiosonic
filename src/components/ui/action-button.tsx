"use client";

import { useRef, useState, useTransition, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { Button } from "./button";

/**
 * Botão que executa uma chamada à API, com confirmação opcional (diálogo nativo acessível),
 * estado de carregamento e mensagem de erro.
 */
export function ActionButton({
  method = "POST",
  url,
  body,
  children,
  confirm,
  confirmLabel = "Confirmar",
  variant = "secondary",
  size = "sm",
  onDone,
  redirectTo,
}: {
  method?: string;
  url: string;
  body?: unknown;
  children: ReactNode;
  confirm?: { title: string; description: string };
  confirmLabel?: string;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md";
  onDone?: (data: unknown) => void;
  redirectTo?: string;
}) {
  const router = useRouter();
  const dialog = useRef<HTMLDialogElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [, startTransition] = useTransition();

  async function run() {
    setBusy(true);
    setError(null);
    const res = await api(method, url, body);
    setBusy(false);
    dialog.current?.close();
    if (!res.ok) {
      setError(res.error.message);
      if (res.error.code === "UNAUTHENTICATED") router.push("/login");
      return;
    }
    onDone?.(res.data);
    startTransition(() => {
      if (redirectTo) router.push(redirectTo);
      router.refresh();
    });
  }

  return (
    <span className="inline-flex flex-col items-start gap-1">
      <Button variant={variant} size={size} disabled={busy} onClick={() => (confirm ? dialog.current?.showModal() : run())}>
        {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        {children}
      </Button>
      {error && (
        <span role="alert" className="text-xs font-medium text-loss-700">
          {error}
        </span>
      )}
      {confirm && (
        <dialog ref={dialog} className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-lg border border-slate-200 p-0 shadow-xl backdrop:bg-slate-900/40" aria-labelledby={`${url}-t`}>
          <div className="space-y-2 p-5">
            <h2 id={`${url}-t`} className="text-base font-semibold text-slate-900">
              {confirm.title}
            </h2>
            <p className="text-sm text-slate-600">{confirm.description}</p>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-100 bg-slate-50 px-5 py-3">
            <Button variant="secondary" size="sm" onClick={() => dialog.current?.close()}>
              Cancelar
            </Button>
            <Button variant={variant === "danger" ? "danger" : "primary"} size="sm" disabled={busy} onClick={run}>
              {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
              {confirmLabel}
            </Button>
          </div>
        </dialog>
      )}
    </span>
  );
}
