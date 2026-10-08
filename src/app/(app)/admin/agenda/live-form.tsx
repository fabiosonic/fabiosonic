"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { LIVE_KIND_LABEL, LIVE_STATUS_LABEL } from "@/lib/labels";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";

interface Live {
  id: string;
  title: string;
  description: string;
  kind: "LIVE" | "AULA";
  status: "SCHEDULED" | "CANCELED" | "DONE";
  startsAt: string;
  durationMin: number;
  link: string | null;
  courseId: string | null;
}

/** Converte ISO (UTC) para o valor de <input type="datetime-local"> no fuso de Brasília. */
function toLocalInput(iso?: string) {
  if (!iso) return "";
  const d = new Date(new Date(iso).getTime() - 3 * 3600_000);
  return d.toISOString().slice(0, 16);
}

export function LiveForm({ live, courses }: { live?: Live; courses: { id: string; title: string }[] }) {
  const router = useRouter();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const p = live ? `lv-${live.id}` : "lv-new";

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const f = new FormData(formEl);
    const local = String(f.get("startsAt") ?? "");
    const body = {
      title: f.get("title"),
      description: f.get("description"),
      kind: f.get("kind"),
      status: f.get("status") ?? "SCHEDULED",
      startsAt: local ? `${local}:00-03:00` : "",
      durationMin: f.get("durationMin"),
      link: f.get("link"),
      courseId: f.get("courseId") || null,
    };
    setBusy(true);
    const res = await api(live ? "PUT" : "POST", live ? `/api/admin/lives/${live.id}` : "/api/admin/lives", body);
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage({ tone: "error", text: res.error.message });
      return;
    }
    setErrors({});
    setMessage({ tone: "success", text: live ? "Evento atualizado." : "Evento criado." });
    if (!live) formEl.reset();
    router.refresh();
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      {message && <Alert tone={message.tone}>{message.text}</Alert>}
      <Field id={`${p}-t`} label="Título" required error={errors.title}>
        <Input {...fieldAria(`${p}-t`, errors.title)} name="title" defaultValue={live?.title} maxLength={160} />
      </Field>
      <Field id={`${p}-d`} label="Descrição" required error={errors.description}>
        <Textarea {...fieldAria(`${p}-d`, errors.description)} name="description" defaultValue={live?.description} rows={2} maxLength={2000} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field id={`${p}-k`} label="Tipo">
          <Select {...fieldAria(`${p}-k`)} name="kind" defaultValue={live?.kind ?? "LIVE"}>
            {Object.entries(LIVE_KIND_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
        </Field>
        <Field id={`${p}-s`} label="Situação">
          <Select {...fieldAria(`${p}-s`)} name="status" defaultValue={live?.status ?? "SCHEDULED"}>
            {Object.entries(LIVE_STATUS_LABEL).map(([k, l]) => (
              <option key={k} value={k}>
                {l}
              </option>
            ))}
          </Select>
        </Field>
        <Field id={`${p}-at`} label="Início (Brasília)" required error={errors.startsAt}>
          <Input {...fieldAria(`${p}-at`, errors.startsAt)} name="startsAt" type="datetime-local" defaultValue={toLocalInput(live?.startsAt)} />
        </Field>
        <Field id={`${p}-du`} label="Duração (min)" required error={errors.durationMin}>
          <Input {...fieldAria(`${p}-du`, errors.durationMin)} name="durationMin" type="number" min={10} max={600} defaultValue={live?.durationMin ?? 60} />
        </Field>
      </div>
      <Field id={`${p}-l`} label="Link (https, opcional)" error={errors.link}>
        <Input {...fieldAria(`${p}-l`, errors.link)} name="link" type="url" defaultValue={live?.link ?? ""} />
      </Field>
      <Field id={`${p}-c`} label="Curso relacionado (opcional)">
        <Select {...fieldAria(`${p}-c`)} name="courseId" defaultValue={live?.courseId ?? ""}>
          <option value="">Nenhum</option>
          {courses.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title}
            </option>
          ))}
        </Select>
      </Field>
      <Button type="submit" disabled={busy}>
        {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
        {live ? "Salvar evento" : "Criar evento"}
      </Button>
    </form>
  );
}
