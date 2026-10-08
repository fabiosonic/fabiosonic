"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { requestCreateSchema } from "@/lib/schemas";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";

export function RequestForm({ assets }: { assets: string[] }) {
  const router = useRouter();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = { subject: form.get("subject"), assetTicker: form.get("assetTicker"), question: form.get("question") };
    const check = requestCreateSchema.safeParse(payload);
    if (!check.success) {
      const fe: Record<string, string[]> = {};
      for (const i of check.error.issues) (fe[String(i.path[0])] ??= []).push(i.message);
      setErrors(fe);
      setMessage("Verifique os campos destacados.");
      return;
    }
    setBusy(true);
    const res = await api<{ id: string }>("POST", "/api/solicitacoes", payload);
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage(res.error.message);
      return;
    }
    router.push(`/solicitacoes/${res.data.id}`);
  }

  return (
    <form onSubmit={submit} noValidate className="max-w-2xl">
      <Panel>
        <div className="space-y-3">
          {message && <Alert tone="error">{message}</Alert>}
          <Field id="subject" label="Assunto" required error={errors.subject}>
            <Input {...fieldAria("subject", errors.subject)} name="subject" maxLength={160} />
          </Field>
          <Field id="assetTicker" label="Ativo (opcional)" error={errors.assetTicker}>
            <Select {...fieldAria("assetTicker", errors.assetTicker)} name="assetTicker" defaultValue="">
              <option value="">Nenhum</option>
              {assets.map((a) => (
                <option key={a} value={a}>
                  {a}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="question" label="Descrição" required hint="Mínimo de 20 caracteres." error={errors.question}>
            <Textarea {...fieldAria("question", errors.question, true)} name="question" rows={6} maxLength={4000} />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Enviar pedido
          </Button>
        </div>
      </Panel>
    </form>
  );
}
