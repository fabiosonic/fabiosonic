// Gráficos do painel, seguindo o método dataviz: forma pela função do dado,
// paleta validada (séries 1 e 2 para duas séries; cor única para magnitude),
// marcas finas, grade discreta, legenda + tooltip em todo gráfico interativo.
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { ReactNode } from 'react';

const eixo = { stroke: 'var(--eixo)', tick: { fill: 'var(--tinta-3)', fontSize: 12 }, tickLine: false };

function CaixaTooltip({ titulo, linhas }: { titulo: ReactNode; linhas: { cor: string; rotulo: string; valor: ReactNode }[] }) {
  return (
    <div className="rounded-xl border border-borda bg-superficie px-3 py-2 text-[13px] shadow-lg">
      <div className="mb-1 font-medium">{titulo}</div>
      {linhas.map((l) => (
        <div key={l.rotulo} className="flex items-center gap-2 text-tinta-2">
          <span className="inline-block size-2.5 rounded-full" style={{ background: l.cor }} />
          <span>{l.rotulo}</span>
          <span className="numeros ml-auto pl-4 font-medium text-tinta">{l.valor}</span>
        </div>
      ))}
    </div>
  );
}

export function Legenda({ itens }: { itens: { cor: string; rotulo: string }[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-tinta-2">
      {itens.map((i) => (
        <span key={i.rotulo} className="inline-flex items-center gap-1.5">
          <span className="inline-block h-[3px] w-3 rounded-full" style={{ background: i.cor }} />
          {i.rotulo}
        </span>
      ))}
    </div>
  );
}

const diaCurto = (iso: string) => {
  const [, m, d] = iso.split('-');
  return `${d}/${m}`;
};

export function GraficoAtividade({ serie }: { serie: { dia: string; enviadas: number; recebidas: number }[] }) {
  const series = [
    { chave: 'enviadas', rotulo: 'Mensagens enviadas', cor: 'var(--serie-1)' },
    { chave: 'recebidas', rotulo: 'Respostas recebidas', cor: 'var(--serie-2)' },
  ] as const;
  return (
    <div>
      <div className="px-5 pt-1 pb-2">
        <Legenda itens={series.map((s) => ({ cor: s.cor, rotulo: s.rotulo }))} />
      </div>
      <div className="h-56 px-2">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={serie} margin={{ top: 8, right: 16, bottom: 0, left: -12 }}>
            <CartesianGrid stroke="var(--grade)" vertical={false} />
            <XAxis dataKey="dia" tickFormatter={diaCurto} {...eixo} minTickGap={24} />
            <YAxis allowDecimals={false} {...eixo} axisLine={false} width={40} />
            <Tooltip
              cursor={{ stroke: 'var(--eixo)', strokeWidth: 1 }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <CaixaTooltip
                    titulo={new Date(`${label}T12:00:00`).toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: 'short' })}
                    linhas={series.map((s) => ({ cor: s.cor, rotulo: s.rotulo, valor: payload.find((p) => p.dataKey === s.chave)?.value ?? 0 }))}
                  />
                ) : null
              }
            />
            {series.map((s) => (
              <Line key={s.chave} type="monotoneX" dataKey={s.chave} stroke={s.cor} strokeWidth={2} dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: 'var(--superficie)' }} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Funil: etapas ordenadas, magnitude pelo comprimento — uma única cor, rótulo direto em cada barra. */
export function GraficoFunil({ etapas }: { etapas: { id: string; nome: string; valor: number }[] }) {
  const max = Math.max(1, ...etapas.map((e) => e.valor));
  return (
    <ol className="space-y-2.5 px-5 pt-2 pb-5">
      {etapas.map((e) => (
        <li key={e.id} className="group grid grid-cols-[96px_1fr_36px] items-center gap-3 text-[13px] sm:grid-cols-[112px_1fr_40px]" title={`${e.nome}: ${e.valor}`}>
          <span className="truncate text-tinta-2">{e.nome}</span>
          <span className="relative h-6 rounded-md bg-superficie-2">
            <span
              className="absolute inset-y-0 left-0 rounded-md transition-[width] duration-500 group-hover:opacity-85"
              style={{ width: `${Math.max(e.valor ? 3 : 0, (e.valor / max) * 100)}%`, background: e.id === 'com_voce' ? 'var(--alerta)' : 'var(--serie-1)' }}
            />
          </span>
          <span className="numeros text-right font-medium">{e.valor}</span>
        </li>
      ))}
    </ol>
  );
}

const CORES_PROVEDOR = ['var(--serie-1)', 'var(--serie-2)', 'var(--serie-3)', 'var(--serie-4)'];

/** Uso de IA por hora: até 4 provedores com cor própria (fixa pela ordem configurada) + "Outros". */
export function GraficoUsoIA({ porHora, ordem, nomes }: { porHora: { hora: string; provedor: string; total: number }[]; ordem: string[]; nomes: Record<string, string> }) {
  const volume = new Map<string, number>();
  for (const r of porHora) volume.set(r.provedor, (volume.get(r.provedor) ?? 0) + r.total);
  const principais = ordem.filter((p) => volume.has(p)).slice(0, 4);
  const cor = (p: string) => CORES_PROVEDOR[principais.indexOf(p)] ?? 'var(--serie-outros)';
  const horas = [...new Set(porHora.map((r) => r.hora))].sort();
  const dados = horas.map((h) => {
    const linha: Record<string, number | string> = { hora: h.slice(11, 13) + 'h' };
    for (const r of porHora.filter((x) => x.hora === h)) {
      const chave = principais.includes(r.provedor) ? r.provedor : 'outros';
      linha[chave] = ((linha[chave] as number) ?? 0) + r.total;
    }
    return linha;
  });
  const chaves = [...principais, ...(volume.size > principais.length ? ['outros'] : [])];
  const rotulo = (k: string) => (k === 'outros' ? 'Outros' : nomes[k] ?? k);
  if (!dados.length) return <p className="px-5 py-10 text-center text-sm text-tinta-3">Nenhuma chamada de IA nas últimas 24 horas.</p>;
  return (
    <div>
      <div className="px-5 pt-1 pb-2">
        <Legenda itens={chaves.map((k) => ({ cor: k === 'outros' ? 'var(--serie-outros)' : cor(k), rotulo: rotulo(k) }))} />
      </div>
      <div className="h-56 px-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={dados} margin={{ top: 8, right: 16, bottom: 0, left: -12 }} barCategoryGap={3}>
            <CartesianGrid stroke="var(--grade)" vertical={false} />
            <XAxis dataKey="hora" {...eixo} minTickGap={16} />
            <YAxis allowDecimals={false} {...eixo} axisLine={false} width={40} />
            <Tooltip
              cursor={{ fill: 'var(--superficie-2)' }}
              content={({ active, payload, label }) =>
                active && payload?.length ? (
                  <CaixaTooltip titulo={label} linhas={chaves.map((k) => ({ cor: k === 'outros' ? 'var(--serie-outros)' : cor(k), rotulo: rotulo(k), valor: (payload.find((p) => p.dataKey === k)?.value as number) ?? 0 }))} />
                ) : null
              }
            />
            {chaves.map((k, i) => (
              <Bar key={k} dataKey={k} stackId="ia" fill={k === 'outros' ? 'var(--serie-outros)' : cor(k)} stroke="var(--superficie)" strokeWidth={1} radius={i === chaves.length - 1 ? [4, 4, 0, 0] : 0} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/** Barras horizontais simples (uma série, uma cor) com rótulo direto. */
export function BarrasHorizontais({ itens }: { itens: { rotulo: string; valor: number; detalhe?: string }[] }) {
  const max = Math.max(1, ...itens.map((i) => i.valor));
  return (
    <ul className="space-y-3 px-5 pt-2 pb-5">
      {itens.map((i) => (
        <li key={i.rotulo} title={`${i.rotulo}: ${i.valor}`}>
          <div className="mb-1 flex items-baseline justify-between gap-3 text-[13px]">
            <span className="truncate text-tinta-2">{i.rotulo}</span>
            <span className="numeros shrink-0 font-medium">
              {i.valor}
              {i.detalhe && <span className="ml-1 font-normal text-tinta-3">{i.detalhe}</span>}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-superficie-2">
            <div className="h-full rounded-full" style={{ width: `${(i.valor / max) * 100}%`, background: 'var(--serie-1)' }} />
          </div>
        </li>
      ))}
    </ul>
  );
}
