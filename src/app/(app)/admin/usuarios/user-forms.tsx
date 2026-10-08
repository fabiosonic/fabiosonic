"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Loader2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { ROLE_LABEL } from "@/lib/labels";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ActionButton } from "@/components/ui/action-button";
import { Field, Input, Select, fieldAria } from "@/components/ui/field";

type RoleKey = keyof typeof ROLE_LABEL;

export function NewUserForm() {
  const router = useRouter();
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const formEl = e.currentTarget;
    const f = new FormData(formEl);
    setBusy(true);
    const res = await api("POST", "/api/admin/usuarios", { name: f.get("name"), email: f.get("email"), role: f.get("role"), password: f.get("password") });
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage({ tone: "error", text: res.error.message });
      return;
    }
    setErrors({});
    setMessage({ tone: "success", text: "Usuário criado. Informe a senha temporária por canal seguro." });
    formEl.reset();
    router.refresh();
  }

  return (
    <form onSubmit={submit} noValidate>
      <Panel title="Novo usuário">
        <div className="space-y-3">
          {message && <Alert tone={message.tone}>{message.text}</Alert>}
          <Field id="nu-name" label="Nome" required error={errors.name}>
            <Input {...fieldAria("nu-name", errors.name)} name="name" maxLength={120} />
          </Field>
          <Field id="nu-email" label="E-mail" required error={errors.email}>
            <Input {...fieldAria("nu-email", errors.email)} name="email" type="email" autoComplete="off" />
          </Field>
          <Field id="nu-role" label="Perfil" required error={errors.role}>
            <Select {...fieldAria("nu-role", errors.role)} name="role" defaultValue="USER">
              {Object.entries(ROLE_LABEL).map(([k, l]) => (
                <option key={k} value={k}>
                  {l}
                </option>
              ))}
            </Select>
          </Field>
          <Field id="nu-pass" label="Senha temporária" required hint="Mínimo de 8 caracteres. O usuário pode redefini-la pelo fluxo de recuperação." error={errors.password}>
            <Input {...fieldAria("nu-pass", errors.password, true)} name="password" type="password" autoComplete="new-password" />
          </Field>
          <Button type="submit" disabled={busy}>
            {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
            Criar usuário
          </Button>
        </div>
      </Panel>
    </form>
  );
}

export function UserRowActions({ user, self }: { user: { id: string; name: string; role: RoleKey; active: boolean }; self: boolean }) {
  const router = useRouter();
  const [role, setRole] = useState<RoleKey>(user.role);
  const [error, setError] = useState<string | null>(null);

  async function changeRole(next: RoleKey) {
    setRole(next);
    const res = await api("PATCH", `/api/admin/usuarios/${user.id}`, { role: next });
    if (!res.ok) {
      setRole(user.role);
      setError(res.error.message);
      return;
    }
    setError(null);
    router.refresh();
  }

  if (self) return <span className="text-xs text-slate-500">Sua conta</span>;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="sr-only" htmlFor={`role-${user.id}`}>
        Perfil de {user.name}
      </label>
      <Select id={`role-${user.id}`} value={role} onChange={(e) => changeRole(e.target.value as RoleKey)} className="h-8 w-36 py-1">
        {Object.entries(ROLE_LABEL).map(([k, l]) => (
          <option key={k} value={k}>
            {l}
          </option>
        ))}
      </Select>
      <ActionButton
        method="PATCH"
        url={`/api/admin/usuarios/${user.id}`}
        body={{ active: !user.active }}
        variant={user.active ? "danger" : "secondary"}
        confirm={
          user.active
            ? { title: `Desativar ${user.name}?`, description: "O usuário perderá o acesso e as sessões abertas serão encerradas." }
            : { title: `Reativar ${user.name}?`, description: "O usuário poderá entrar novamente." }
        }
        confirmLabel={user.active ? "Desativar" : "Reativar"}
      >
        {user.active ? "Desativar" : "Reativar"}
      </ActionButton>
      {error && (
        <span role="alert" className="text-xs text-loss-700">
          {error}
        </span>
      )}
    </div>
  );
}
