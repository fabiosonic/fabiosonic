import Link from "next/link";
import { connection } from "next/server";
import { isDemoEnv } from "@/server/env";

export default async function AuthLayout({ children }: { children: React.ReactNode }) {
  await connection(); // o aviso de ambiente reflete a configuração em execução, não a do build
  return (
    <div className="flex min-h-dvh flex-col items-center justify-center px-4 py-10">
      <Link href="/login" className="mb-6 flex items-center gap-2 text-lg font-semibold text-slate-900">
        <svg viewBox="0 0 32 32" className="size-8" aria-hidden="true">
          <rect width="32" height="32" rx="7" fill="#0b5763" />
          <path d="M7 21l6-6 4 4 8-9" stroke="#fff" strokeWidth="2.6" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        Opções Lab
      </Link>
      <main className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">{children}</main>
      {isDemoEnv() && (
        <p className="mt-4 max-w-sm text-center text-xs text-slate-500">
          Ambiente demonstrativo local. Consulte o README para as contas de demonstração.
        </p>
      )}
    </div>
  );
}
