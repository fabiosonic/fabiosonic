import { notFound } from "next/navigation";
import { History } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getSimulation } from "@/server/services/simulations";
import { listAssets } from "@/server/services/market";
import { AppError } from "@/server/errors";
import { PageHeader } from "@/components/ui/panel";
import { LinkButton } from "@/components/ui/button";
import { Simulator } from "@/components/simulator/simulator";
import { formatDateTime } from "@/lib/format";

export const metadata = { title: "Simulação salva" };

export default async function SavedSimulationPage({ params }: { params: Promise<{ id: string }> }) {
  const ctx = await requirePageCtx();
  const { id } = await params;
  let sim;
  try {
    sim = await getSimulation(ctx, id);
  } catch (e) {
    if (e instanceof AppError && e.code === "NOT_FOUND") notFound();
    throw e;
  }
  const assets = await listAssets(ctx);
  return (
    <>
      <PageHeader
        title={sim.name}
        description={`Atualizada em ${formatDateTime(sim.updatedAt)}.`}
        actions={
          <LinkButton href="/simulador/salvas" variant="secondary">
            <History className="size-4" aria-hidden="true" /> Simulações salvas
          </LinkButton>
        }
      />
      <Simulator
        key={sim.updatedAt}
        assets={assets.map((a) => ({ ticker: a.ticker, lastPrice: a.lastPrice }))}
        initial={{
          id: sim.id,
          name: sim.name,
          mode: sim.mode,
          underlyingTicker: sim.underlyingTicker,
          spotPrice: sim.spotPrice,
          multiplier: sim.multiplier,
          fees: sim.fees,
          expiration: sim.expiration?.slice(0, 10) ?? "",
          notes: sim.notes ?? "",
          sourceStrategyId: sim.sourceStrategyId,
          legs: sim.legs.map((l) => ({ side: l.side, instrument: l.instrument, strike: l.strike ?? "", premium: l.premium, quantity: String(l.quantity), optionSymbol: l.optionSymbol ?? "" })),
          scenarios: sim.scenarios,
        }}
      />
    </>
  );
}
