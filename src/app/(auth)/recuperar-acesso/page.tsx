import { connection } from "next/server";
import { RecoverForm } from "./recover-form";
import { isDemoEnv } from "@/server/env";

export const metadata = { title: "Recuperar acesso" };

export default async function RecoverPage() {
  await connection();
  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Recuperar acesso</h1>
      <p className="mt-1 text-sm text-slate-600">Informe seu e-mail. Se houver uma conta, enviaremos um link de uso único válido por 30 minutos.</p>
      <RecoverForm devMailbox={isDemoEnv()} />
    </>
  );
}
