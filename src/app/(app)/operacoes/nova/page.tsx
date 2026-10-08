import { requirePageCtx } from "@/server/session";
import { STAFF } from "@/server/authz";
import { listAssets } from "@/server/services/market";
import { PageHeader } from "@/components/ui/panel";
import { StrategyForm } from "@/components/content/strategy-form";

export const metadata = { title: "Nova operação" };

export default async function NewStrategyPage() {
  const ctx = await requirePageCtx(STAFF);
  const assets = await listAssets(ctx);
  const a = assets[0];
  return (
    <>
      <PageHeader title="Nova operação pronta" />
      <StrategyForm
        assets={assets.map((x) => ({ ticker: x.ticker, lastPrice: x.lastPrice }))}
        value={{ title: "", strategyType: "TRAVA_ALTA", assetTicker: a?.ticker ?? "", summary: "", assumptions: "", riskNotes: "", referencePrice: a?.lastPrice ?? "", expiration: "", legs: [] }}
      />
    </>
  );
}
