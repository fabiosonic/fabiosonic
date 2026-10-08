"use client";

import { useEffect, useState } from "react";
import { Loader2, Search } from "lucide-react";
import { api } from "@/lib/client-api";
import { formatBRL, formatDate } from "@/lib/format";
import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/field";
import { DataSourceBadge } from "@/components/ui/badge";

export interface PickedOption {
  symbol: string;
  type: "CALL" | "PUT";
  strike: string;
  lastPrice: string | null;
  expiration: string;
  assetPrice: string;
}

interface OptionRow extends PickedOption {
  id: string;
  dataSource: "DEMO" | "DELAYED" | "REALTIME";
}

/** Busca contratos (demonstrativos) do ativo para preencher uma perna. */
export function OptionPicker({ ticker, onPick, onClose }: { ticker: string; onPick: (o: PickedOption) => void; onClose: () => void }) {
  const [type, setType] = useState<"CALL" | "PUT">("CALL");
  const [expirations, setExpirations] = useState<string[]>([]);
  const [expiration, setExpiration] = useState("");
  const [rows, setRows] = useState<OptionRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancel = false;
    (async () => {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams({ ativo: ticker, tipo: type, tamanho: "100", ordem: "expiration" });
      if (expiration) params.set("vencimento", expiration);
      const res = await api<{ items: OptionRow[] }>("GET", `/api/mercado/opcoes?${params.toString()}`);
      if (cancel) return;
      setLoading(false);
      if (!res.ok) return setError(res.error.message);
      setRows(res.data.items);
      if (!expiration) setExpirations([...new Set(res.data.items.map((r) => r.expiration.slice(0, 10)))]);
    })();
    return () => {
      cancel = true;
    };
  }, [ticker, type, expiration]);

  return (
    <div className="rounded-md border border-brand-100 bg-brand-50/40 p-3" role="group" aria-label={`Escolher contrato de ${ticker}`}>
      <div className="flex flex-wrap items-end gap-2">
        <div>
          <label htmlFor="pick-type" className="block text-xs font-medium text-slate-600">
            Tipo
          </label>
          <Select id="pick-type" value={type} onChange={(e) => setType(e.target.value as "CALL" | "PUT")} className="h-9 w-24">
            <option value="CALL">CALL</option>
            <option value="PUT">PUT</option>
          </Select>
        </div>
        <div>
          <label htmlFor="pick-exp" className="block text-xs font-medium text-slate-600">
            Vencimento
          </label>
          <Select id="pick-exp" value={expiration} onChange={(e) => setExpiration(e.target.value)} className="h-9 w-36">
            <option value="">Todos</option>
            {expirations.map((e) => (
              <option key={e} value={e}>
                {formatDate(e)}
              </option>
            ))}
          </Select>
        </div>
        <Button variant="ghost" size="sm" onClick={onClose}>
          Fechar
        </Button>
        {loading && <Loader2 className="mb-2 size-4 animate-spin text-slate-500" aria-label="Carregando" />}
      </div>
      {error && <p className="mt-2 text-sm text-loss-700" role="alert">{error}</p>}
      {rows && rows.length === 0 && !loading && <p className="mt-2 text-sm text-slate-500">Nenhum contrato para o ativo {ticker}.</p>}
      {rows && rows.length > 0 && (
        <div className="relative mt-2 max-h-64 overflow-auto rounded border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <caption className="sr-only">Contratos disponíveis (demonstrativos)</caption>
            <thead className="sticky top-0 bg-slate-50 text-xs text-slate-600">
              <tr>
                <th scope="col" className="px-2 py-1 text-left">Código</th>
                <th scope="col" className="px-2 py-1 text-right">Strike</th>
                <th scope="col" className="px-2 py-1 text-left">Venc.</th>
                <th scope="col" className="px-2 py-1 text-right">Prêmio</th>
                <th scope="col" className="px-2 py-1"><span className="sr-only">Ação</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-slate-100">
                  <td className="px-2 py-1 font-mono text-xs">{r.symbol}</td>
                  <td className="px-2 py-1 text-right tabular">{formatBRL(r.strike)}</td>
                  <td className="px-2 py-1 tabular">{formatDate(r.expiration)}</td>
                  <td className="px-2 py-1 text-right tabular">{formatBRL(r.lastPrice)}</td>
                  <td className="px-2 py-1 text-right">
                    <Button size="sm" variant="secondary" onClick={() => onPick(r)} aria-label={`Usar ${r.symbol}`}>
                      <Search className="size-3.5" aria-hidden="true" /> Usar
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="border-t border-slate-100 px-2 py-1">
            <DataSourceBadge source="DEMO" />
          </div>
        </div>
      )}
    </div>
  );
}
