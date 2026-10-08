import { ResetForm } from "./reset-form";

export const metadata = { title: "Redefinir senha" };

export default async function ResetPage({ searchParams }: { searchParams: Promise<{ token?: string; error?: string }> }) {
  const { token, error } = await searchParams;
  return (
    <>
      <h1 className="text-xl font-semibold text-slate-900">Redefinir senha</h1>
      <ResetForm token={token ?? null} invalid={Boolean(error)} />
    </>
  );
}
