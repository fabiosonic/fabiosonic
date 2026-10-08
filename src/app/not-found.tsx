import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-lg px-4 py-20 text-center">
      <p className="text-sm font-semibold text-brand-700">404</p>
      <h1 className="mt-1 text-2xl font-semibold text-slate-900">Página ou registro não encontrado</h1>
      <p className="mt-2 text-slate-600">O conteúdo pode ter sido removido, não estar publicado ou não pertencer à sua conta.</p>
      <Link href="/painel" className="mt-6 inline-block text-brand-700 underline">
        Voltar ao painel
      </Link>
    </main>
  );
}
