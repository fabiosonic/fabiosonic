import Link from "next/link";
import { ShieldX } from "lucide-react";

export const metadata = { title: "Acesso negado" };

export default function AccessDenied() {
  return (
    <main className="mx-auto max-w-lg px-4 py-20 text-center">
      <ShieldX className="mx-auto size-10 text-loss-700" aria-hidden="true" />
      <h1 className="mt-3 text-2xl font-semibold text-slate-900">Acesso negado</h1>
      <p className="mt-2 text-slate-600">Seu perfil não tem permissão para acessar esta área.</p>
      <Link href="/painel" className="mt-6 inline-block text-brand-700 underline">
        Voltar ao painel
      </Link>
    </main>
  );
}
