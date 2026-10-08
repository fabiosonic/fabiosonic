"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/client-api";
import { STRATEGY_TYPES } from "@/lib/labels";
import { formatBRL } from "@/lib/format";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { CashFlow } from "@/components/ui/money";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";
import { compute } from "@/components/simulator/compute";
import { emptyLeg, initialKey, toInput, type LegState } from "@/components/simulator/types";

export interface StrategyFormValue {
  id?: string;
  title: string;
  strategyType: string;
  assetTicker: string;
  summary: string;
  assumptions: string;
  riskNotes: string;
  referencePrice: string;
  expiration: string;
  legs: Omit<LegState, "key">[];
}

export function StrategyForm({ value, assets }: { value: StrategyFormValue; assets: { ticker: string; lastPrice: string }[] }) {
  const router = useRouter();
  const [v, setV] = useState({ ...value, referencePrice: toInput(value.referencePrice) });
  const [legs, setLegs] = useState<LegState[]>(
    value.legs.length ? value.legs.map((l, i) => ({ ...l, key: initialKey(i), strike: toInput(l.strike), premium: toInput(l.premium) })) : [emptyLeg(initialKey(0))],
  );
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const preview = useMemo(() => compute({ legs, spot: v.referencePrice, multiplier: 1, fees: "0", scenarios: [] }), [legs, v.referencePrice]);
  const set = (k: keyof StrategyFormValue) => (e: { target: { value: string } }) => setV((s) => ({ ...s, [k]: e.target.value }));
  const updateLeg = (i: number, patch: Partial<LegState>) => setLegs((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage(null);
    const payload = {
      ...v,
      legs: legs.map((l) => ({
        side: l.side,
        instrument: l.instrument,
        strike: l.instrument === "STOCK" ? null : l.strike,
        premium: l.premium,
        quantity: l.quantity,
        optionSymbol: l.optionSymbol || null,
      })),
    };
    const res = await api<{ id?: string }>(value.id ? "PUT" : "POST", value.id ? `/api/operacoes/${value.id}` : "/api/operacoes", payload);
    setBusy(false);
    if (!res.ok) {
      setErrors(res.error.fieldErrors ?? {});
      setMessage(res.error.message);
      return;
    }
    router.push(`/operacoes/${value.id ?? res.data.id}`);
    router.refresh();
  }

  const err = (k: string) => errors[k];

  return (
    <form onSubmit={submit} noValidate className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        {message && <Alert tone="error">{message}</Alert>}
        <Panel title="Identificação">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Field id="title" label="Título" required className="sm:col-span-2" error={err("title")}>
              <Input {...fieldAria("title", err("title"))} value={v.title} onChange={set("title")} maxLength={160} />
            </Field>
            <Field id="strategyType" label="Estratégia" required error={err("strategyType")}>
              <Select {...fieldAria("strategyType", err("strategyType"))} value={v.strategyType} onChange={set("strategyType")}>
                {Object.entries(STRATEGY_TYPES).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="assetTicker" label="Ativo" required error={err("assetTicker")}>
              <Select
                {...fieldAria("assetTicker", err("assetTicker"))}
                value={v.assetTicker}
                onChange={(e) => {
                  const a = assets.find((x) => x.ticker === e.target.value);
                  setV((s) => ({ ...s, assetTicker: e.target.value, referencePrice: a ? toInput(a.lastPrice) : s.referencePrice }));
                }}
              >
                {assets.map((a) => (
                  <option key={a.ticker} value={a.ticker}>
                    {a.ticker}
                  </option>
                ))}
              </Select>
            </Field>
            <Field id="referencePrice" label="Preço de referência (R$)" required error={err("referencePrice")}>
              <Input {...fieldAria("referencePrice", err("referencePrice"))} inputMode="decimal" value={v.referencePrice} onChange={set("referencePrice")} />
            </Field>
            <Field id="expiration" label="Vencimento" required error={err("expiration")}>
              <Input {...fieldAria("expiration", err("expiration"))} type="date" value={v.expiration} onChange={set("expiration")} />
            </Field>
          </div>
        </Panel>

        <Panel
          title={`Pernas (${legs.length})`}
          actions={
            <Button size="sm" variant="secondary" onClick={() => setLegs((l) => [...l, emptyLeg()])} disabled={legs.length >= 8}>
              <Plus className="size-4" aria-hidden="true" /> Perna
            </Button>
          }
        >
          {err("legs") && <Alert tone="error" className="mb-3">{err("legs")!.join(" ")}</Alert>}
          <ol className="space-y-3">
            {legs.map((leg, i) => {
              const le = preview.ok ? {} : (preview.legErrors[i] ?? {});
              const id = `sl-${leg.key}`;
              return (
                <li key={leg.key} className="grid grid-cols-2 gap-2 rounded-md border border-slate-200 p-3 sm:grid-cols-6">
                  <Field id={`${id}-side`} label="Operação">
                    <Select {...fieldAria(`${id}-side`)} value={leg.side} onChange={(e) => updateLeg(i, { side: e.target.value as LegState["side"] })}>
                      <option value="BUY">Compra</option>
                      <option value="SELL">Venda</option>
                    </Select>
                  </Field>
                  <Field id={`${id}-inst`} label="Instrumento">
                    <Select {...fieldAria(`${id}-inst`)} value={leg.instrument} onChange={(e) => updateLeg(i, { instrument: e.target.value as LegState["instrument"] })}>
                      <option value="CALL">CALL</option>
                      <option value="PUT">PUT</option>
                      <option value="STOCK">Ação</option>
                    </Select>
                  </Field>
                  <Field id={`${id}-k`} label="Strike" error={le.strike}>
                    <Input
                      {...fieldAria(`${id}-k`, le.strike)}
                      inputMode="decimal"
                      disabled={leg.instrument === "STOCK"}
                      value={leg.instrument === "STOCK" ? "" : leg.strike}
                      onChange={(e) => updateLeg(i, { strike: e.target.value })}
                    />
                  </Field>
                  <Field id={`${id}-p`} label={leg.instrument === "STOCK" ? "Preço" : "Prêmio"} error={le.premium}>
                    <Input {...fieldAria(`${id}-p`, le.premium)} inputMode="decimal" value={leg.premium} onChange={(e) => updateLeg(i, { premium: e.target.value })} />
                  </Field>
                  <Field id={`${id}-q`} label="Qtd." error={le.quantity}>
                    <Input {...fieldAria(`${id}-q`, le.quantity)} type="number" min={1} value={leg.quantity} onChange={(e) => updateLeg(i, { quantity: e.target.value })} />
                  </Field>
                  <div className="flex items-end">
                    <Button variant="ghost" onClick={() => setLegs((ls) => ls.filter((_, idx) => idx !== i))} disabled={legs.length <= 1} aria-label={`Remover perna ${i + 1}`}>
                      <Trash2 className="size-4" aria-hidden="true" /> Remover
                    </Button>
                  </div>
                </li>
              );
            })}
          </ol>
        </Panel>

        <Panel title="Conteúdo">
          <div className="space-y-3">
            <Field id="summary" label="Resumo" required hint="10 a 600 caracteres." error={err("summary")}>
              <Textarea {...fieldAria("summary", err("summary"), true)} value={v.summary} onChange={set("summary")} rows={2} maxLength={600} />
            </Field>
            <Field id="assumptions" label="Premissas" required error={err("assumptions")}>
              <Textarea {...fieldAria("assumptions", err("assumptions"))} value={v.assumptions} onChange={set("assumptions")} rows={4} maxLength={4000} />
            </Field>
            <Field id="riskNotes" label="Riscos" required error={err("riskNotes")}>
              <Textarea {...fieldAria("riskNotes", err("riskNotes"))} value={v.riskNotes} onChange={set("riskNotes")} rows={3} maxLength={2000} />
            </Field>
          </div>
        </Panel>
      </div>

      <div className="space-y-4">
        <Panel title="Prévia dos cálculos" description="No vencimento, multiplicador 1, sem custos.">
          {preview.ok ? (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Montagem</dt>
                <dd>
                  <CashFlow value={preview.initialCashFlow} />
                </dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Equilíbrio</dt>
                <dd className="text-right tabular">{preview.breakevens.map((b) => formatBRL(b)).join(" · ") || "—"}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Ganho máximo</dt>
                <dd className="tabular">{preview.maxProfitUnlimited ? "Ilimitado" : formatBRL(preview.maxProfit)}</dd>
              </div>
              <div className="flex justify-between gap-2">
                <dt className="text-slate-500">Perda máxima</dt>
                <dd className="tabular">{preview.maxLossUnlimited ? "Ilimitada" : formatBRL(preview.maxLoss)}</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">Preencha as pernas e o preço de referência.</p>
          )}
        </Panel>
        <Button type="submit" className="w-full" disabled={busy}>
          {busy && <Loader2 className="size-4 animate-spin" aria-hidden="true" />}
          {value.id ? "Salvar alterações" : "Salvar como rascunho"}
        </Button>
        <p className="text-xs text-slate-500">Novas operações são criadas como rascunho. Publique na página da operação.</p>
      </div>
    </form>
  );
}
