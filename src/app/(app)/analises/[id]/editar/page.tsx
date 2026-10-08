import { notFound, redirect } from "next/navigation";
import { requirePageCtx } from "@/server/session";
import { STAFF } from "@/server/authz";
import { getAnalysis } from "@/server/services/content";
import { listAssets } from "@/server/services/market";
import { AppError } from "@/server/errors";
import { PageHeader } from "@/components/ui/panel";
import { AnalysisForm } from "@/components/content/analysis-form";

export const metadata = { title: "Editar análise" };

export default async function EditAnalysisPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx(STAFF);
  const { id } = await params;
  let a;
  try {
    a = await getAnalysis(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  if (a.status === "ARCHIVED") redirect(`/analises/${id}`);
  const assets = await listAssets(ctx);
  return (
    <>
      <PageHeader title="Editar análise" />
      <AnalysisForm assets={assets.map((x) => x.ticker)} value={{ id: a.id, title: a.title, assetTicker: a.assetTicker ?? "", summary: a.summary, body: a.body }} />
    </>
  );
}
