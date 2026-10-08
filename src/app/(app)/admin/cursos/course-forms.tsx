"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { CONTENT_STATUS_LABEL } from "@/lib/labels";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";

function useSubmit() {
  const router = useRouter();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  async function run(method: string, url: string, body: unknown, ok: string, after?: (data: unknown) => void) {
    setBusy(true);
    const res = await api(method, url, body);
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage({ tone: "error", text: res.error.message });
      return false;
    }
    setErrors({});
    setMessage({ tone: "success", text: ok });
    after?.(res.data);
    router.refresh();
    return true;
  }
  return { errors, message, busy, run, router };
}

export function CourseForm({ course }: { course?: { id: string; title: string; slug: string; description: string; status: "DRAFT" | "PUBLISHED" | "ARCHIVED" } }) {
  const { errors, message, busy, run, router } = useSubmit();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const f = new FormData(formEl);
    const body = { title: f.get("title"), slug: f.get("slug"), description: f.get("description"), status: f.get("status") };
    if (course) await run("PUT", `/api/admin/cursos/${course.id}`, body, "Curso atualizado.");
    else
      await run("POST", "/api/admin/cursos", body, "Curso criado.", (d) => {
        formEl.reset();
        router.push(`/admin/cursos/${(d as { id: string }).id}`);
      });
  }
  const p = course ? "ec" : "nc";
  return (
    <form onSubmit={submit} noValidate>
      <Panel title={course ? "Dados do curso" : "Novo curso"}>
        <div className="space-y-3">
          {message && <Alert tone={message.tone}>{message.text}</Alert>}
          <Field id={`${p}-title`} label="Título" required error={errors.title}>
            <Input {...fieldAria(`${p}-title`, errors.title)} name="title" defaultValue={course?.title} maxLength={160} />
          </Field>
          <Field id={`${p}-slug`} label="Identificador (URL)" required hint="Ex.: fundamentos-de-opcoes" error={errors.slug}>
            <Input {...fieldAria(`${p}-slug`, errors.slug, true)} name="slug" defaultValue={course?.slug} maxLength={80} />
          </Field>
          <Field id={`${p}-desc`} label="Descrição" required error={errors.description}>
            <Textarea {...fieldAria(`${p}-desc`, errors.description)} name="description" defaultValue={course?.description} rows={3} maxLength={2000} />
          </Field>
          <Field id={`${p}-status`} label="Situação">
            <Select {...fieldAria(`${p}-status`)} name="status" defaultValue={course?.status ?? "DRAFT"}>
              {Object.entries(CONTENT_STATUS_LABEL).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            {course ? "Salvar curso" : "Criar curso"}
          </Button>
        </div>
      </Panel>
    </form>
  );
}

export function ModuleForm({ courseId }: { courseId: string }) {
  const { errors, message, busy, run } = useSubmit();
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const ok = await run("POST", `/api/admin/cursos/${courseId}/modulos`, { title: new FormData(formEl).get("title") }, "Módulo adicionado.");
    if (ok) formEl.reset();
  }
  return (
    <form onSubmit={submit} noValidate>
      <Panel title="Novo módulo">
        <div className="flex flex-wrap items-end gap-2">
          <Field id="nm-title" label="Título" className="min-w-56 flex-1" error={errors.title}>
            <Input {...fieldAria("nm-title", errors.title)} name="title" maxLength={160} />
          </Field>
          <Button type="submit" disabled={busy}>
            Adicionar módulo
          </Button>
        </div>
        {message && <Alert tone={message.tone} className="mt-2">{message.text}</Alert>}
      </Panel>
    </form>
  );
}

export function LessonForm({ moduleId, lesson }: { moduleId: string; lesson?: { id: string; title: string; content: string; videoUrl: string; durationMin: number } }) {
  const { errors, message, busy, run } = useSubmit();
  const p = lesson ? `el-${lesson.id}` : `nl-${moduleId}`;
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const f = new FormData(formEl);
    const body = { title: f.get("title"), content: f.get("content"), videoUrl: f.get("videoUrl"), durationMin: f.get("durationMin") };
    if (lesson) await run("PUT", `/api/admin/aulas/${lesson.id}`, body, "Aula atualizada.");
    else if (await run("POST", `/api/admin/modulos/${moduleId}/aulas`, body, "Aula adicionada.")) formEl.reset();
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-3">
      {message && <Alert tone={message.tone}>{message.text}</Alert>}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Field id={`${p}-t`} label="Título" required className="sm:col-span-2" error={errors.title}>
          <Input {...fieldAria(`${p}-t`, errors.title)} name="title" defaultValue={lesson?.title} maxLength={160} />
        </Field>
        <Field id={`${p}-d`} label="Duração (min)" required error={errors.durationMin}>
          <Input {...fieldAria(`${p}-d`, errors.durationMin)} name="durationMin" type="number" min={1} max={600} defaultValue={lesson?.durationMin ?? 10} />
        </Field>
      </div>
      <Field id={`${p}-c`} label="Conteúdo" required error={errors.content}>
        <Textarea {...fieldAria(`${p}-c`, errors.content)} name="content" defaultValue={lesson?.content} rows={5} maxLength={20000} />
      </Field>
      <Field id={`${p}-v`} label="Link de vídeo autorizado (opcional)" hint="Somente https e com autorização de uso." error={errors.videoUrl}>
        <Input {...fieldAria(`${p}-v`, errors.videoUrl, true)} name="videoUrl" type="url" defaultValue={lesson?.videoUrl} />
      </Field>
      <Button type="submit" size="sm" disabled={busy}>
        {lesson ? "Salvar aula" : "Adicionar aula"}
      </Button>
    </form>
  );
}
