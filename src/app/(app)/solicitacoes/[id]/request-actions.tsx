"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2, Send } from "lucide-react";
import { api } from "@/lib/client-api";
import { REQUEST_STATUS_LABEL } from "@/lib/labels";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Select, Textarea, fieldAria } from "@/components/ui/field";

export function MessageForm({ requestId, staffReply }: { requestId: string; staffReply: boolean }) {
  const router = useRouter();
  const [body, setBody] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (body.trim().length < 2) return setError("Escreva uma mensagem.");
    setBusy(true);
    setError(null);
    const res = await api("POST", `/api/solicitacoes/${requestId}/mensagens`, { body });
    setBusy(false);
    if (!res.ok) return setError(res.error.message);
    setBody("");
    router.refresh();
  }

  return (
    <form onSubmit={submit} noValidate>
      <Panel title={staffReply ? "Responder" : "Nova mensagem"} description={staffReply ? "A resposta muda a situação para “Respondido” e notifica o usuário." : undefined}>
        <Field id="msg" label="Mensagem" error={error ?? undefined}>
          <Textarea {...fieldAria("msg", error ?? undefined)} value={body} onChange={(e) => setBody(e.target.value)} rows={4} maxLength={4000} />
        </Field>
        <Button type="submit" className="mt-3" disabled={busy}>
          {busy ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Send className="size-4" aria-hidden="true" />}
          Enviar
        </Button>
      </Panel>
    </form>
  );
}

export function StatusForm({ requestId, current }: { requestId: string; current: keyof typeof REQUEST_STATUS_LABEL }) {
  const router = useRouter();
  const [status, setStatus] = useState(current);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    const res = await api("POST", `/api/solicitacoes/${requestId}/situacao`, { status });
    setBusy(false);
    setMessage(res.ok ? { tone: "success", text: "Situação atualizada." } : { tone: "error", text: res.error.message });
    if (res.ok) router.refresh();
  }

  return (
    <form onSubmit={submit} className="space-y-2">
      <Field id="status" label="Alterar situação">
        <Select {...fieldAria("status")} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
          {Object.entries(REQUEST_STATUS_LABEL).map(([k, l]) => (
            <option key={k} value={k}>
              {l}
            </option>
          ))}
        </Select>
      </Field>
      <Button type="submit" variant="secondary" disabled={busy || status === current}>
        {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        Atualizar
      </Button>
      {message && <Alert tone={message.tone}>{message.text}</Alert>}
    </form>
  );
}
