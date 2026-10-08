import { notFound } from "next/navigation";
import { connection } from "next/server";
import { prisma } from "@/server/db";
import { env } from "@/server/env";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Caixa de e-mail (desenvolvimento)" };

/** Caixa de saída local. Disponível somente com APP_ENV=demo e EMAIL_TRANSPORT=dev. */
export default async function DevMailbox() {
  await connection(); // sempre renderizada por requisição (dados e ambiente atuais)
  const cfg = env();
  if (cfg.APP_ENV !== "demo" || cfg.EMAIL_TRANSPORT !== "dev") notFound();
  const emails = await prisma.devEmail.findMany({ orderBy: { createdAt: "desc" }, take: 20 });
  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <h1 className="text-xl font-semibold text-slate-900">Caixa de e-mail de desenvolvimento</h1>
      <p className="mt-1 text-sm text-slate-600">
        Mensagens geradas localmente (nenhum e-mail real é enviado). Em produção, configure um provedor de e-mail.
      </p>
      {emails.length === 0 ? (
        <p className="mt-6 text-sm text-slate-500">Nenhuma mensagem.</p>
      ) : (
        <ul className="mt-6 space-y-4">
          {emails.map((m) => (
            <li key={m.id} className="rounded-lg border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">
                {formatDateTime(m.createdAt)} · para <span data-testid="email-to">{m.to}</span>
              </p>
              <p className="font-medium text-slate-900">{m.subject}</p>
              <pre className="mt-2 whitespace-pre-wrap break-all font-sans text-sm text-slate-700" data-testid="email-body">
                {m.body}
              </pre>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
