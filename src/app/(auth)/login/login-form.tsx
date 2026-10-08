"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Field, Input, fieldAria } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

export function LoginForm() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const email = String(form.get("email") ?? "").trim();
    const password = String(form.get("password") ?? "");
    if (!email || !password) {
      setError("Informe e-mail e senha.");
      return;
    }
    setBusy(true);
    setError(null);
    const { error: err } = await authClient.signIn.email({ email, password });
    setBusy(false);
    if (err) {
      setError(
        err.status === 429
          ? "Muitas tentativas. Aguarde um minuto e tente novamente."
          : err.status === 403
            ? (err.message ?? "Acesso não permitido.")
            : "E-mail ou senha inválidos.",
      );
      return;
    }
    router.push("/painel");
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
      {error && <Alert tone="error">{error}</Alert>}
      <Field id="email" label="E-mail" required>
        <Input {...fieldAria("email")} name="email" type="email" autoComplete="email" required />
      </Field>
      <Field id="password" label="Senha" required>
        <Input {...fieldAria("password")} name="password" type="password" autoComplete="current-password" required />
      </Field>
      <Button type="submit" className="w-full" disabled={busy}>
        {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Entrar
      </Button>
      <p className="text-center text-sm">
        <Link href="/recuperar-acesso" className="text-brand-700 underline">
          Esqueci minha senha
        </Link>
      </p>
    </form>
  );
}
