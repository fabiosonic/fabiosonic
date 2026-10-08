import "server-only";
/**
 * Adaptador de dados de mercado.
 *
 * Cotações reais da B3 exigem contratação de um distribuidor de market data licenciado.
 * O provedor DEMONSTRATIVO abaixo gera preços fictícios (marcados como DEMO) a partir de
 * uma semente diária, para que telas e filtros funcionem sem dependências externas.
 */
export interface QuoteUpdate {
  ticker: string;
  price: string;
}

export interface MarketDataProvider {
  readonly id: string;
  readonly dataSource: "DEMO" | "DELAYED" | "REALTIME";
  quoteAssets(tickers: { ticker: string; lastPrice: string }[], now: Date): Promise<QuoteUpdate[]>;
}

function hash(s: string) {
  let h = 0;
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) | 0;
  return Math.abs(h);
}

export class DemoMarketDataProvider implements MarketDataProvider {
  readonly id = "DEMO";
  readonly dataSource = "DEMO" as const;

  async quoteAssets(tickers: { ticker: string; lastPrice: string }[], now: Date): Promise<QuoteUpdate[]> {
    const day = now.toISOString().slice(0, 10);
    return tickers.map(({ ticker, lastPrice }) => {
      const drift = ((hash(`${ticker}:${day}`) % 401) - 200) / 10000; // −2% a +2%
      return { ticker, price: (Number(lastPrice) * (1 + drift)).toFixed(2) };
    });
  }
}

export function marketDataProvider(): MarketDataProvider {
  return new DemoMarketDataProvider();
}
