"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { authClient } from "@/lib/auth-client";
import { Field, Input, fieldAria } from "@/components/ui/field";
import { Button } from "@/components/ui/button";
import { Alert } from "@/components/ui/alert";

export function RecoverForm({ devMailbox }: { devMailbox: boolean }) {
  const [state, setState] = useState<"idle" | "busy" | "sent" | "error" | "limited">("idle");
  const [fieldError, setFieldError] = useState<string>();

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const email = String(new FormData(e.currentTarget).get("email") ?? "").trim();
    if (!/^\S+@\S+\.\S+$/.test(email)) {
      setFieldError("Informe um e-mail válido.");
      return;
    }
    setFieldError(undefined);
    setState("busy");
    const { error } = await authClient.requestPasswordReset({ email, redirectTo: "/redefinir-senha" });
    // A resposta é a mesma exista ou não a conta (evita enumeração de usuários).
    setState(error ? (error.status === 429 ? "limited" : "error") : "sent");
  }

  return (
    <form onSubmit={onSubmit} className="mt-5 space-y-4" noValidate>
      {state === "sent" && (
        <Alert tone="success" title="Pedido registrado">
          Se o e-mail estiver cadastrado, você receberá o link de redefinição.
          {devMailbox && (
            <>
              {" "}
              Em ambiente local, consulte a{" "}
              <Link href="/dev/emails" className="underline">
                caixa de e-mail de desenvolvimento
              </Link>
              .
            </>
          )}
        </Alert>
      )}
      {state === "limited" && <Alert tone="error">Muitas solicitações. Aguarde alguns minutos.</Alert>}
      {state === "error" && <Alert tone="error">Não foi possível processar o pedido. Tente novamente.</Alert>}
      <Field id="email" label="E-mail" required error={fieldError}>
        <Input {...fieldAria("email", fieldError)} name="email" type="email" autoComplete="email" required />
      </Field>
      <Button type="submit" className="w-full" disabled={state === "busy"}>
        {state === "busy" && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Enviar link
      </Button>
      <p className="text-center text-sm">
        <Link href="/login" className="text-brand-700 underline">
          Voltar ao login
        </Link>
      </p>
    </form>
  );
}
