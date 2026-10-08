"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Field, Input, fieldAria } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

export function ResetForm({ token, invalid }: { token: string | null; invalid: boolean }) {
  const [state, setState] = useState<"idle" | "busy" | "done">("idle");
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({});

  if (!token || invalid) {
    return (
      <div className="mt-4 space-y-4">
        <Alert tone="error">Link inválido, expirado ou já utilizado.</Alert>
        <Link href="/recuperar-acesso" className="text-sm text-brand-700 underline">
          Solicitar novo link
        </Link>
      </div>
    );
  }

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirm = String(form.get("confirm") ?? "");
    const fe: typeof fieldErrors = {};
    if (password.length < 8) fe.password = "Mínimo de 8 caracteres.";
    if (password !== confirm) fe.confirm = "As senhas não conferem.";
    setFieldErrors(fe);
    if (Object.keys(fe).length) return;
    setState("busy");
    setError(null);
    const { error: err } = await authClient.resetPassword({ newPassword: password, token: token! });
    if (err) {
      setState("idle");
      setError(err.status === 429 ? "Muitas tentativas. Aguarde alguns minutos." : "Link inválido, expirado ou já utilizado.");
      return;
    }
    setState("done");
  }

  if (state === "done") {
    return (
      <div className="mt-4 space-y-4">
        <Alert tone="success" title="Senha redefinida">
          Por segurança, as sessões abertas foram encerradas.
        </Alert>
        <Link href="/login" className="text-sm text-brand-700 underline">
          Ir para o login
        </Link>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <Field id="password" label="Nova senha" required hint="Mínimo de 8 caracteres." error={fieldErrors.password}>
        <Input {...fieldAria("password", fieldErrors.password, true)} name="password" type="password" autoComplete="new-password" />
      </Field>
      <Field id="confirm" label="Confirmar nova senha" required error={fieldErrors.confirm}>
        <Input {...fieldAria("confirm", fieldErrors.confirm)} name="confirm" type="password" autoComplete="new-password" />
      </Field>
      <Button type="submit" className="w-full" disabled={state === "busy"}>
        {state === "busy" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Salvar nova senha
      </Button>
    </form>
  );
}
