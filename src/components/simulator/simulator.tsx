"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { Copy, Layers, ListPlus, Loader2, Plus, Save, Search, Trash2, Zap, TrendingUp } from "lucide-react";
import { api } from "@/lib/client-api";
import { parseDecimalInput } from "@/lib/format";
import { Panel } from "@/components/ui/panel";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea, fieldAria } from "@/components/ui/field";
import { cn } from "@/components/ui/cn";
import { compute } from "./compute";
import { Results } from "./results";
import { OptionPicker, type PickedOption } from "./option-picker";
import { emptyLeg, initialKey, newKey, toInput, type LegState, type Mode, type ScenarioState, type SimulatorInitial } from "./types";

const TABS: { mode: Mode; label: string; icon: typeof Zap; help: string }[] = [
  { mode: "RAPIDA", label: "Boleta rápida", icon: Zap, help: "Uma perna: compra ou venda de CALL, PUT ou ação." },
  { mode: "CLASSICA", label: "Boleta clássica", icon: Layers, help: "Estratégias com várias pernas." },
  { mode: "PREVISOES", label: "Previsões", icon: TrendingUp, help: "Compare o resultado em cenários de preço definidos por você." },
];

export function Simulator({ initial, assets }: { initial: SimulatorInitial; assets: { ticker: string; lastPrice: string }[] }) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>(initial.mode);
  const [name, setName] = useState(initial.name);
  const [ticker, setTicker] = useState(initial.underlyingTicker);
  const [spot, setSpot] = useState(toInput(initial.spotPrice));
  const [multiplier, setMultiplier] = useState(String(initial.multiplier));
  const [fees, setFees] = useState(toInput(initial.fees));
  const [expiration, setExpiration] = useState(initial.expiration);
  const [notes, setNotes] = useState(initial.notes);
  const [legs, setLegs] = useState<LegState[]>(
    initial.legs.length
      ? initial.legs.map((l, i) => ({ ...l, key: initialKey(i), strike: toInput(l.strike), premium: toInput(l.premium) }))
      : [emptyLeg(initialKey(0))],
  );
  const [scenarios, setScenarios] = useState<ScenarioState[]>(initial.scenarios.map((s, i) => ({ ...s, key: `s${i}`, price: toInput(s.price) })));
  const [picker, setPicker] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const [serverErrors, setServerErrors] = useState<Record<string, string[]>>({});

  const visibleLegs = mode === "RAPIDA" ? legs.slice(0, 1) : legs;
  const result = useMemo(
    () => compute({ legs: visibleLegs, spot, multiplier: Math.max(1, Number(multiplier) || 1), fees, scenarios: mode === "PREVISOES" ? scenarios : [] }),
    [visibleLegs, spot, multiplier, fees, scenarios, mode],
  );
  const legErrors = result.ok ? {} : result.legErrors;

  function updateLeg(i: number, patch: Partial<LegState>) {
    setLegs((ls) => ls.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  function onTicker(t: string) {
    setTicker(t);
    const asset = assets.find((a) => a.ticker === t);
    if (asset) setSpot(toInput(asset.lastPrice));
  }

  function pick(i: number, o: PickedOption) {
    updateLeg(i, { instrument: o.type, strike: toInput(o.strike), premium: toInput(o.lastPrice ?? ""), optionSymbol: o.symbol });
    setExpiration(o.expiration.slice(0, 10));
    setPicker(null);
  }

  function addScenarioPreset() {
    const s = Number(parseDecimalInput(spot) ?? 0);
    if (!s) return;
    const fmt = (v: number) => toInput(v.toFixed(2));
    setScenarios([
      { key: newKey(), label: "Queda de 10%", price: fmt(s * 0.9) },
      { key: newKey(), label: "Estável", price: fmt(s) },
      { key: newKey(), label: "Alta de 10%", price: fmt(s * 1.1) },
    ]);
  }

  async function save(asNew: boolean) {
    setSaving(true);
    setMessage(null);
    setServerErrors({});
    const payload = {
      name,
      mode,
      underlyingTicker: ticker,
      spotPrice: spot,
      multiplier: Number(multiplier) || 1,
      fees: fees || "0",
      expiration: expiration || null,
      notes: notes || null,
      sourceStrategyId: initial.sourceStrategyId ?? null,
      scenarios: mode === "PREVISOES" ? scenarios.map((s) => ({ label: s.label, price: s.price })) : [],
      legs: visibleLegs.map((l) => ({
        side: l.side,
        instrument: l.instrument,
        strike: l.instrument === "STOCK" ? null : l.strike,
        premium: l.premium,
        quantity: l.quantity,
        optionSymbol: l.optionSymbol || null,
      })),
    };
    const editing = initial.id && !asNew;
    const res = await api<{ id?: string }>(editing ? "PUT" : "POST", editing ? `/api/simulacoes/${initial.id}` : "/api/simulacoes", payload);
    setSaving(false);
    if (!res.ok) {
      setServerErrors(res.error.fieldErrors ?? {});
      setMessage({ tone: "error", text: res.error.message });
      return;
    }
    setMessage({ tone: "success", text: "Simulação salva." });
    if (!editing && res.data.id) router.push(`/simulador/${res.data.id}`);
    else router.refresh();
  }

  const multiLegInQuick = mode === "RAPIDA" && legs.length > 1;

  return (
    <div className="space-y-4">
      <div role="tablist" aria-label="Tipo de boleta" className="flex flex-wrap gap-1 rounded-lg border border-slate-200 bg-white p-1">
        {TABS.map((t) => {
          const Icon = t.icon;
          return (
            <button
              key={t.mode}
              role="tab"
              type="button"
              id={`tab-${t.mode}`}
              aria-selected={mode === t.mode}
              aria-controls="painel-boleta"
              onClick={() => setMode(t.mode)}
              className={cn(
                "inline-flex flex-1 items-center justify-center gap-2 rounded-md px-3 py-2 text-sm font-medium sm:flex-none",
                mode === t.mode ? "bg-brand-700 text-white" : "text-slate-700 hover:bg-slate-100",
              )}
            >
              <Icon className="size-4" aria-hidden="true" />
              {t.label}
            </button>
          );
        })}
      </div>

      <div id="painel-boleta" role="tabpanel" aria-labelledby={`tab-${mode}`} className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <div className="space-y-4">
          <Panel title="Dados da simulação" description={TABS.find((t) => t.mode === mode)!.help}>
            <div className="grid grid-cols-2 gap-3">
              <Field id="sim-name" label="Nome" required className="col-span-2" error={serverErrors.name}>
                <Input {...fieldAria("sim-name", serverErrors.name)} value={name} onChange={(e) => setName(e.target.value)} maxLength={120} />
              </Field>
              <Field id="sim-ticker" label="Ativo" required>
                <Select {...fieldAria("sim-ticker")} value={ticker} onChange={(e) => onTicker(e.target.value)}>
                  {assets.map((a) => (
                    <option key={a.ticker} value={a.ticker}>
                      {a.ticker}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field id="sim-spot" label="Preço de referência (R$)" required hint="Cotação demonstrativa; editável." error={serverErrors.spotPrice}>
                <Input {...fieldAria("sim-spot", serverErrors.spotPrice, true)} inputMode="decimal" value={spot} onChange={(e) => setSpot(e.target.value)} />
              </Field>
              <Field id="sim-exp" label="Vencimento">
                <Input {...fieldAria("sim-exp")} type="date" value={expiration} onChange={(e) => setExpiration(e.target.value)} />
              </Field>
              <Field id="sim-fees" label="Custos totais (R$)" hint="Corretagem/emolumentos, valor fixo.">
                <Input {...fieldAria("sim-fees", undefined, true)} inputMode="decimal" value={fees} onChange={(e) => setFees(e.target.value)} placeholder="0,00" />
              </Field>
              <Field id="sim-mult" label="Multiplicador" hint="1 para opções de ações na B3.">
                <Input {...fieldAria("sim-mult", undefined, true)} type="number" min={1} max={10000} value={multiplier} onChange={(e) => setMultiplier(e.target.value)} />
              </Field>
            </div>
          </Panel>

          <Panel
            title={mode === "RAPIDA" ? "Ordem simulada" : `Pernas (${legs.length})`}
            actions={
              mode !== "RAPIDA" && (
                <Button size="sm" variant="secondary" onClick={() => setLegs((l) => [...l, emptyLeg()])} disabled={legs.length >= 12}>
                  <Plus className="size-4" aria-hidden="true" /> Perna
                </Button>
              )
            }
          >
            {multiLegInQuick && (
              <Alert tone="info" className="mb-3">
                Esta simulação tem {legs.length} pernas; a boleta rápida mostra apenas a primeira.{" "}
                <button type="button" className="underline" onClick={() => setMode("CLASSICA")}>
                  Abrir na boleta clássica
                </button>
              </Alert>
            )}
            <ol className="space-y-3">
              {visibleLegs.map((leg, i) => {
                const errs = legErrors[i] ?? {};
                const id = `leg-${leg.key}`;
                return (
                  <li key={leg.key} className="rounded-md border border-slate-200 p-3">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-sm font-semibold text-slate-800">{mode === "RAPIDA" ? "Ordem" : `Perna ${i + 1}`}</span>
                      <div className="flex gap-1">
                        {leg.instrument !== "STOCK" && (
                          <Button size="sm" variant="ghost" onClick={() => setPicker(picker === i ? null : i)} aria-label={`Buscar contrato para a perna ${i + 1}`}>
                            <Search className="size-4" aria-hidden="true" /> Contrato
                          </Button>
                        )}
                        {mode !== "RAPIDA" && (
                          <>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setLegs((ls) => [...ls.slice(0, i + 1), { ...leg, key: newKey() }, ...ls.slice(i + 1)])}
                              aria-label={`Duplicar perna ${i + 1}`}
                              title="Duplicar"
                              disabled={legs.length >= 12}
                            >
                              <Copy className="size-4" aria-hidden="true" />
                            </Button>
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setLegs((ls) => ls.filter((_, idx) => idx !== i))}
                              aria-label={`Remover perna ${i + 1}`}
                              title="Remover"
                              disabled={legs.length <= 1}
                            >
                              <Trash2 className="size-4" aria-hidden="true" />
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <Field id={`${id}-side`} label="Operação">
                        <Select {...fieldAria(`${id}-side`)} value={leg.side} onChange={(e) => updateLeg(i, { side: e.target.value as LegState["side"] })}>
                          <option value="BUY">Compra</option>
                          <option value="SELL">Venda</option>
                        </Select>
                      </Field>
                      <Field id={`${id}-inst`} label="Instrumento">
                        <Select {...fieldAria(`${id}-inst`)} value={leg.instrument} onChange={(e) => updateLeg(i, { instrument: e.target.value as LegState["instrument"], optionSymbol: "" })}>
                          <option value="CALL">CALL</option>
                          <option value="PUT">PUT</option>
                          <option value="STOCK">Ação</option>
                        </Select>
                      </Field>
                      <Field id={`${id}-qty`} label="Quantidade" error={errs.quantity}>
                        <Input {...fieldAria(`${id}-qty`, errs.quantity)} type="number" min={1} step={1} value={leg.quantity} onChange={(e) => updateLeg(i, { quantity: e.target.value })} />
                      </Field>
                      {leg.instrument !== "STOCK" && (
                        <Field id={`${id}-strike`} label="Strike (R$)" error={errs.strike}>
                          <Input {...fieldAria(`${id}-strike`, errs.strike)} inputMode="decimal" value={leg.strike} onChange={(e) => updateLeg(i, { strike: e.target.value, optionSymbol: "" })} />
                        </Field>
                      )}
                      <Field id={`${id}-prem`} label={leg.instrument === "STOCK" ? "Preço (R$)" : "Prêmio (R$)"} error={errs.premium}>
                        <Input {...fieldAria(`${id}-prem`, errs.premium)} inputMode="decimal" value={leg.premium} onChange={(e) => updateLeg(i, { premium: e.target.value })} />
                      </Field>
                      {leg.optionSymbol && (
                        <p className="col-span-2 self-end pb-2 text-xs text-slate-500 sm:col-span-1">
                          Contrato: <span className="font-mono">{leg.optionSymbol}</span>
                        </p>
                      )}
                    </div>
                    {picker === i && (
                      <div className="mt-3">
                        <OptionPicker ticker={ticker} onPick={(o) => pick(i, o)} onClose={() => setPicker(null)} />
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>
          </Panel>

          {mode === "PREVISOES" && (
            <Panel
              title="Cenários de preço"
              description="Defina preços-alvo no vencimento. Não há probabilidades associadas."
              actions={
                <>
                  <Button size="sm" variant="ghost" onClick={addScenarioPreset}>
                    <ListPlus className="size-4" aria-hidden="true" /> Sugerir ±10%
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={scenarios.length >= 10}
                    onClick={() => setScenarios((s) => [...s, { key: newKey(), label: `Cenário ${s.length + 1}`, price: "" }])}
                  >
                    <Plus className="size-4" aria-hidden="true" /> Cenário
                  </Button>
                </>
              }
            >
              {scenarios.length === 0 ? (
                <p className="text-sm text-slate-500">Nenhum cenário. Adicione ao menos um preço-alvo.</p>
              ) : (
                <ul className="space-y-2">
                  {scenarios.map((s, i) => (
                    <li key={s.key} className="flex items-end gap-2">
                      <Field id={`sc-${s.key}-l`} label="Nome" className="flex-1">
                        <Input
                          {...fieldAria(`sc-${s.key}-l`)}
                          value={s.label}
                          maxLength={40}
                          onChange={(e) => setScenarios((all) => all.map((x, idx) => (idx === i ? { ...x, label: e.target.value } : x)))}
                        />
                      </Field>
                      <Field id={`sc-${s.key}-p`} label="Preço (R$)" className="w-32">
                        <Input
                          {...fieldAria(`sc-${s.key}-p`)}
                          inputMode="decimal"
                          value={s.price}
                          onChange={(e) => setScenarios((all) => all.map((x, idx) => (idx === i ? { ...x, price: e.target.value } : x)))}
                        />
                      </Field>
                      <Button size="md" variant="ghost" onClick={() => setScenarios((all) => all.filter((_, idx) => idx !== i))} aria-label={`Remover cenário ${s.label}`}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          )}

          <Panel title="Salvar">
            <Field id="sim-notes" label="Anotações" hint="Opcional, até 2.000 caracteres.">
              <Textarea {...fieldAria("sim-notes", undefined, true)} value={notes} onChange={(e) => setNotes(e.target.value)} maxLength={2000} rows={3} />
            </Field>
            {message && (
              <Alert tone={message.tone} className="mt-3">
                {message.text}
              </Alert>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              <Button onClick={() => save(false)} disabled={saving || !result.ok}>
                {saving ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : <Save className="size-4" aria-hidden="true" />}
                {initial.id ? "Salvar alterações" : "Salvar simulação"}
              </Button>
              {initial.id && (
                <Button variant="secondary" onClick={() => save(true)} disabled={saving || !result.ok}>
                  Salvar como nova
                </Button>
              )}
            </div>
            <p className="mt-2 text-xs text-slate-500">Simulação apenas. Nenhuma ordem é enviada a corretora ou à B3.</p>
          </Panel>
        </div>

        <Results result={result} showScenarios={mode === "PREVISOES"} />
      </div>
    </div>
  );
}
