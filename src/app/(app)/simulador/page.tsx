import { History } from "lucide-react";
import { requirePageCtx } from "@/server/session";
import { getOptionBySymbol, listAssets } from "@/server/services/market";
import { getStrategy } from "@/server/services/content";
import { AppError } from "@/server/errors";
import { PageHeader } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { LinkButton } from "@/components/ui/button";
import { Simulator } from "@/components/simulator/simulator";
import type { Mode, SimulatorInitial } from "@/components/simulator/types";

export const metadata = { title: "Simulador" };

const MODES: Mode[] = ["RAPIDA", "CLASSICA", "PREVISOES"];

export default async function SimulatorPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const ctx = await requirePageCtx();
  const sp = await searchParams;
  const assets = await listAssets(ctx);
  const modeParam = (sp.modo ?? "").toUpperCase() as Mode;
  let notice: string | null = null;

  const first = assets[0];
  let initial: SimulatorInitial = {
    name: "Nova simulação",
    mode: MODES.includes(modeParam) ? modeParam : "RAPIDA",
    underlyingTicker: first?.ticker ?? "PETR4",
    spotPrice: first?.lastPrice ?? "",
    multiplier: 1,
    fees: "0",
    expiration: "",
    notes: "",
    legs: [],
    scenarios: [],
  };

  if (sp.opcao) {
    const o = await getOptionBySymbol(ctx, sp.opcao);
    if (o) {
      initial = {
        ...initial,
        name: `Simulação ${o.symbol}`,
        underlyingTicker: o.assetTicker,
        spotPrice: o.assetPrice,
        expiration: o.expiration.slice(0, 10),
        multiplier: o.multiplier,
        legs: [{ side: "BUY", instrument: o.type, strike: o.strike, premium: o.lastPrice ?? "", quantity: "100", optionSymbol: o.symbol }],
      };
    } else notice = "Contrato não encontrado; iniciando simulação em branco.";
  } else if (sp.estrategia) {
    try {
      const s = await getStrategy(ctx, sp.estrategia);
      initial = {
        ...initial,
        name: s.title,
        mode: s.legs.length > 1 ? "CLASSICA" : "RAPIDA",
        underlyingTicker: s.assetTicker,
        spotPrice: s.assetPrice,
        expiration: s.expiration.slice(0, 10),
        sourceStrategyId: s.id,
        legs: s.legs.map((l) => ({ side: l.side, instrument: l.instrument, strike: l.strike ?? "", premium: l.premium, quantity: String(l.quantity), optionSymbol: l.optionSymbol ?? "" })),
      };
    } catch (e) {
      if (!(e instanceof AppError)) throw e;
      notice = "Operação não encontrada ou não publicada.";
    }
  }

  return (
    <>
      <PageHeader
        title="Simulador de opções"
        description="Boletas simuladas: monte operações, veja débito/crédito inicial, payoff no vencimento, pontos de equilíbrio e limites de ganho e perda."
        actions={
          <LinkButton href="/simulador/salvas" variant="secondary">
            <History className="size-4" aria-hidden="true" /> Simulações salvas
          </LinkButton>
        }
      />
      {notice && (
        <Alert tone="warning" className="mb-4">
          {notice}
        </Alert>
      )}
      <Simulator key={JSON.stringify(sp)} initial={initial} assets={assets.map((a) => ({ ticker: a.ticker, lastPrice: a.lastPrice }))} />
    </>
  );
}
