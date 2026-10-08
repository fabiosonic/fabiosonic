import { requirePageCtx } from "@/server/session";
import { STAFF } from "@/server/authz";
import { listAssets } from "@/server/services/market";
import { PageHeader } from "@/components/ui/panel";
import { AnalysisForm } from "@/components/content/analysis-form";

export const metadata = { title: "Nova análise" };

export default async function NewAnalysisPage() {
  const ctx = await requirePageCtx(STAFF);
  const assets = await listAssets(ctx);
  return (
    <>
      <PageHeader title="Nova análise" />
      <AnalysisForm assets={assets.map((a) => a.ticker)} value={{ title: "", assetTicker: "", summary: "", body: "" }} />
    </>
  );
}
