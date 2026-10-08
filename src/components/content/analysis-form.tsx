"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";

export interface AnalysisFormValue {
  id?: string;
  title: string;
  assetTicker: string;
  summary: string;
  body: string;
}

export function AnalysisForm({ value, assets }: { value: AnalysisFormValue; assets: string[] }) {
  const router = useRouter();
  const [v, setV] = useState(value);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof AnalysisFormValue) => (e: { target: { value: string } }) => setV((s) => ({ ...s, [k]: e.target.value }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const res = await api<{ id?: string }>(value.id ? "PUT" : "POST", value.id ? `/api/analises/${value.id}` : "/api/analises", v);
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage(res.error.message);
      return;
    }
    router.push(`/analises/${value.id ?? res.data.id}`);
    router.refresh();
  }

  return (
    <form onSubmit={submit} noValidate>
      <Panel>
        <div className="space-y-3">
          {message && <Alert tone="error">{message}</Alert>}
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <Field id="title" label="Título" required className="sm:col-span-2" error={errors.title}>
              <Input {...fieldAria("title", errors.title)} value={v.title} onChange={set("title")} maxLength={160} />
            </Field>
            <Field id="assetTicker" label="Ativo (opcional)" error={errors.assetTicker}>
              <Select {...fieldAria("assetTicker", errors.assetTicker)} value={v.assetTicker} onChange={set("assetTicker")}>
                <option value="">Geral</option>
                {assets.map((a) => (
                  <option key={a} value={a}>
                    {a}
                  </option>
                ))}
              </Select>
            </Field>
          </div>
          <Field id="summary" label="Resumo" required error={errors.summary}>
            <Textarea {...fieldAria("summary", errors.summary)} value={v.summary} onChange={set("summary")} rows={2} maxLength={600} />
          </Field>
          <Field id="body" label="Conteúdo" required hint="Texto simples; quebras de linha são preservadas." error={errors.body}>
            <Textarea {...fieldAria("body", errors.body, true)} value={v.body} onChange={set("body")} rows={12} maxLength={20000} />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {value.id ? "Salvar alterações" : "Salvar como rascunho"}
          </Button>
        </div>
      </Panel>
    </form>
  );
}
