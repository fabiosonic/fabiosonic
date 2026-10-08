import { notFound, redirect } from "next/navigation";
import { requirePageCtx } from "@/server/session";
import { STAFF } from "@/server/authz";
import { getStrategy } from "@/server/services/content";
import { listAssets } from "@/server/services/market";
import { AppError } from "@/server/errors";
import { PageHeader } from "@/components/ui/panel";
import { StrategyForm } from "@/components/content/strategy-form";

export const metadata = { title: "Editar operação" };

export default async function EditStrategyPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx(STAFF);
  const { id } = await params;
  let s;
  try {
    s = await getStrategy(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  if (s.status === "ARCHIVED") redirect(`/operacoes/${id}`);
  const assets = await listAssets(ctx);
  return (
    <>
      <PageHeader title="Editar operação" description="As alterações ficam registradas no histórico." />
      <StrategyForm
        assets={assets.map((x) => ({ ticker: x.ticker, lastPrice: x.lastPrice }))}
        value={{
          id: s.id,
          title: s.title,
          strategyType: s.strategyType,
          assetTicker: s.assetTicker,
          summary: s.summary,
          assumptions: s.assumptions,
          riskNotes: s.riskNotes,
          referencePrice: s.referencePrice,
          expiration: s.expiration.slice(0, 10),
          legs: s.legs.map((l) => ({ side: l.side, instrument: l.instrument, strike: l.strike ?? "", premium: l.premium, quantity: String(l.quantity), optionSymbol: l.optionSymbol ?? "" })),
        }}
      />
    </>
  );
}
