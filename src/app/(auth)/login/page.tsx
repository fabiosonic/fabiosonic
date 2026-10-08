import { redirect } from "next/navigation";
import { getOptionalActor } from "@/server/session";
import { LoginForm } from "./login-form";

export const metadata = { title: "Entrar" };

export default async function LoginPage() {
  if (await getOptionalActor()) redirect("/painel");
  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Entrar</h1>
      <p className="mt-1 text-sm text-slate-600">Acesse com seu e-mail e senha.</p>
      <LoginForm />
    </>
  );
}
