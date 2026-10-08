import "server-only";
/**
 * Adaptador de posições da B3.
 *
 * A integração oficial (Área do Investidor / APIs de posição) exige contrato, credenciamento
 * e autorização do investidor junto à B3 — não disponível neste MVP. A implementação abaixo é
 * DEMONSTRATIVA: gera posições fictícias e determinísticas, sem acessar a B3 e sem solicitar
 * senha. Para integrar oficialmente, implemente `PositionsProvider` com o fluxo autorizado.
 */
import { previousBusinessDay } from "@/lib/dates";

export interface ProviderPosition {
  ticker: string;
  instrumentType: "ACAO" | "OPCAO" | "FII" | "ETF" | "OUTRO";
  quantity: number;
  averagePrice: string;
}

export interface FetchResult {
  referenceDate: Date;
  positions: ProviderPosition[];
}

export interface PositionsProvider {
  readonly id: string;
  readonly isDemo: boolean;
  fetchPositions(userId: string, now: Date, opts?: { simulateFailure?: boolean }): Promise<FetchResult>;
}

export class ProviderError extends Error {}

function seeded(seed: string) {
  let h = 2166136261;
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

const DEMO_BOOK: { ticker: string; instrumentType: ProviderPosition["instrumentType"]; base: number }[] = [
  { ticker: "PETR4", instrumentType: "ACAO", base: 36 },
  { ticker: "VALE3", instrumentType: "ACAO", base: 62 },
  { ticker: "ITUB4", instrumentType: "ACAO", base: 33 },
  { ticker: "BOVA11", instrumentType: "ETF", base: 125 },
  { ticker: "BBAS3", instrumentType: "ACAO", base: 27 },
];

export class DemoB3Provider implements PositionsProvider {
  readonly id = "DEMO";
  readonly isDemo = true;

  async fetchPositions(userId: string, now: Date, opts?: { simulateFailure?: boolean }): Promise<FetchResult> {
    if (opts?.simulateFailure) throw new ProviderError("Falha simulada no provedor demonstrativo.");
    // Data-base D+1: as posições disponíveis hoje referem-se ao último dia útil.
    const referenceDate = previousBusinessDay(now);
    const rnd = seeded(`${userId}:${referenceDate.toISOString().slice(0, 10)}`);
    const positions = DEMO_BOOK.slice(0, 3 + Math.floor(rnd() * 3)).map((p) => ({
      ticker: p.ticker,
      instrumentType: p.instrumentType,
      quantity: (1 + Math.floor(rnd() * 10)) * 100,
      averagePrice: (p.base * (0.85 + rnd() * 0.3)).toFixed(2),
    }));
    return { referenceDate, positions };
  }
}

export function positionsProvider(): PositionsProvider {
  return new DemoB3Provider();
}
