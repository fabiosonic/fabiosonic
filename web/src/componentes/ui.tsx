import { useCallback, useEffect, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { Loader2, X } from 'lucide-react';
import { api } from '../api';

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(' ');

/** Busca dados da API com recarga manual e atualização periódica opcional. */
export function useDados<T>(caminho: string | null, intervaloMs?: number) {
  const [dados, setDados] = useState<T | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(true);
  const recarregar = useCallback(async () => {
    if (!caminho) return;
    try {
      setDados(await api<T>(caminho));
      setErro(null);
    } catch (e) {
      setErro((e as Error).message);
    } finally {
      setCarregando(false);
    }
  }, [caminho]);
  useEffect(() => {
    setCarregando(true);
    void recarregar();
    if (!intervaloMs) return;
    const t = setInterval(() => document.visibilityState === 'visible' && void recarregar(), intervaloMs);
    return () => clearInterval(t);
  }, [recarregar, intervaloMs]);
  return { dados, erro, carregando, recarregar, setDados };
}

export function Cartao({ children, className, titulo, acao, subtitulo }: { children: ReactNode; className?: string; titulo?: ReactNode; subtitulo?: ReactNode; acao?: ReactNode }) {
  return (
    <section className={cx('cartao', className)}>
      {(titulo || acao) && (
        <header className="flex items-start justify-between gap-3 px-5 pt-4 pb-1">
          <div className="min-w-0">
            {titulo && <h2 className="text-[15px] font-semibold tracking-tight">{titulo}</h2>}
            {subtitulo && <p className="mt-0.5 text-[13px] text-tinta-3">{subtitulo}</p>}
          </div>
          {acao}
        </header>
      )}
      {children}
    </section>
  );
}

type Variante = 'primario' | 'secundario' | 'fantasma' | 'perigo';
export function Botao({ variante = 'secundario', carregando, children, className, tamanho = 'md', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { variante?: Variante; carregando?: boolean; tamanho?: 'sm' | 'md' }) {
  return (
    <button
      {...p}
      disabled={p.disabled || carregando}
      className={cx(
        'inline-flex items-center justify-center gap-1.5 rounded-[10px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 whitespace-nowrap',
        tamanho === 'sm' ? 'h-8 px-3 text-[13px]' : 'h-9 px-3.5 text-sm',
        variante === 'primario' && 'bg-tinta text-fundo hover:opacity-90',
        variante === 'secundario' && 'border border-borda-forte bg-superficie text-tinta hover:bg-superficie-2',
        variante === 'fantasma' && 'text-tinta-2 hover:bg-superficie-2 hover:text-tinta',
        variante === 'perigo' && 'border border-critico/30 text-critico-tinta hover:bg-critico-suave',
        className,
      )}
    >
      {carregando && <Loader2 className="size-4 animate-spin" />}
      {children}
    </button>
  );
}

type Tom = 'neutro' | 'acento' | 'bom' | 'alerta' | 'serio' | 'critico';
export function Selo({ tom = 'neutro', children, icone, className }: { tom?: Tom; children: ReactNode; icone?: ReactNode; className?: string }) {
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[12px] font-medium leading-5 whitespace-nowrap',
        tom === 'neutro' && 'bg-superficie-2 text-tinta-2',
        tom === 'acento' && 'bg-acento-suave text-acento-tinta',
        tom === 'bom' && 'bg-bom-suave text-bom-tinta',
        tom === 'alerta' && 'bg-alerta-suave text-alerta-tinta',
        tom === 'serio' && 'bg-serio-suave text-serio-tinta',
        tom === 'critico' && 'bg-critico-suave text-critico-tinta',
        className,
      )}
    >
      {icone}
      {children}
    </span>
  );
}

export function Indicador({ rotulo, valor, detalhe, icone, destaque }: { rotulo: string; valor: ReactNode; detalhe?: ReactNode; icone?: ReactNode; destaque?: boolean }) {
  return (
    <div className={cx('cartao p-4 sm:p-5', destaque && 'ring-1 ring-alerta/60')}>
      <div className="flex items-center gap-2 text-[13px] font-medium text-tinta-2">
        {icone && <span className="text-tinta-3">{icone}</span>}
        {rotulo}
      </div>
      <div className="mt-2 text-[28px] font-semibold leading-none tracking-tight sm:text-[32px]">{valor}</div>
      {detalhe && <div className="mt-2 text-[13px] text-tinta-3">{detalhe}</div>}
    </div>
  );
}

export function Vazio({ icone, titulo, texto, acao }: { icone?: ReactNode; titulo: string; texto?: ReactNode; acao?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icone && <div className="mb-3 grid size-11 place-items-center rounded-full bg-superficie-2 text-tinta-3">{icone}</div>}
      <p className="font-medium">{titulo}</p>
      {texto && <p className="mt-1 max-w-sm text-[13px] text-tinta-3">{texto}</p>}
      {acao && <div className="mt-4">{acao}</div>}
    </div>
  );
}

export const Carregando = ({ texto = 'Carregando…' }: { texto?: string }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-tinta-3">
    <Loader2 className="size-4 animate-spin" /> {texto}
  </div>
);

export function Modal({ aberto, aoFechar, titulo, children, largura = 'max-w-lg' }: { aberto: boolean; aoFechar: () => void; titulo: string; children: ReactNode; largura?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!aberto) return;
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && aoFechar();
    window.addEventListener('keydown', tecla);
    ref.current?.querySelector<HTMLElement>('input,textarea,select,button')?.focus();
    return () => window.removeEventListener('keydown', tecla);
  }, [aberto, aoFechar]);
  if (!aberto) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && aoFechar()}>
      <div ref={ref} role="dialog" aria-modal="true" aria-label={titulo} className={cx('cartao surgir max-h-[92vh] w-full overflow-y-auto rounded-b-none sm:rounded-b-2xl', largura)}>
        <header className="sticky top-0 flex items-center justify-between border-b border-borda bg-superficie px-5 py-3.5">
          <h2 className="font-semibold">{titulo}</h2>
          <button onClick={aoFechar} className="rounded-lg p-1 text-tinta-3 hover:bg-superficie-2" aria-label="Fechar">
            <X className="size-4" />
          </button>
        </header>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Abas<T extends string>({ abas, ativa, aoMudar }: { abas: { id: T; rotulo: ReactNode }[]; ativa: T; aoMudar: (id: T) => void }) {
  return (
    <div className="flex gap-1 overflow-x-auto rounded-xl bg-superficie-2 p-1 rolagem-fina" role="tablist">
      {abas.map((a) => (
        <button
          key={a.id}
          role="tab"
          aria-selected={a.id === ativa}
          onClick={() => aoMudar(a.id)}
          className={cx('h-8 shrink-0 rounded-lg px-3 text-[13px] font-medium transition-colors', a.id === ativa ? 'bg-superficie text-tinta shadow-sm' : 'text-tinta-2 hover:text-tinta')}
        >
          {a.rotulo}
        </button>
      ))}
    </div>
  );
}

export function Campo({ rotulo, ajuda, children }: { rotulo: string; ajuda?: ReactNode; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-tinta-2">{rotulo}</span>
      {children}
      {ajuda && <span className="mt-1 block text-[12px] text-tinta-3">{ajuda}</span>}
    </label>
  );
}

export const classeEntrada =
  'w-full rounded-[10px] border border-borda-forte bg-superficie px-3 py-2 text-sm text-tinta placeholder:text-tinta-3 outline-none transition focus:border-acento focus:ring-2 focus:ring-acento/20';

export const paraData = (sql: string | null | undefined) => (sql ? new Date(sql.includes('T') ? sql : sql.replace(' ', 'T') + 'Z') : null);

export function tempoRelativo(sql: string | null | undefined) {
  const d = paraData(sql);
  if (!d) return '—';
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  const futuro = s < 0;
  const a = Math.abs(s);
  const txt = a < 60 ? 'agora' : a < 3600 ? `${Math.floor(a / 60)} min` : a < 86400 ? `${Math.floor(a / 3600)} h` : a < 86400 * 30 ? `${Math.floor(a / 86400)} d` : d.toLocaleDateString('pt-BR');
  if (txt === 'agora' || txt.includes('/')) return txt;
  return futuro ? `em ${txt}` : `há ${txt}`;
}

export const dataHora = (sql: string | null | undefined) =>
  paraData(sql)?.toLocaleString('pt-BR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) ?? '—';

export const formatarCnpj = (c: string) =>
  /^\d{14}$/.test(c) ? c.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : c.startsWith('pendente-') ? 'CNPJ a confirmar' : c;

/** Pequeno sistema de avisos (toasts). */
type Aviso = { id: number; texto: string; tom: 'bom' | 'critico' | 'neutro' };
let ouvinte: ((a: Aviso) => void) | null = null;
export const avisar = (texto: string, tom: Aviso['tom'] = 'bom') => ouvinte?.({ id: Date.now() + Math.random(), texto, tom });

export function Avisos() {
  const [lista, setLista] = useState<Aviso[]>([]);
  useEffect(() => {
    ouvinte = (a) => {
      setLista((l) => [...l, a]);
      setTimeout(() => setLista((l) => l.filter((x) => x.id !== a.id)), 4200);
    };
    return () => {
      ouvinte = null;
    };
  }, []);
  return (
    <div className="pointer-events-none fixed right-4 bottom-4 left-4 z-[60] flex flex-col items-center gap-2 sm:left-auto sm:items-end" aria-live="polite">
      {lista.map((a) => (
        <div
          key={a.id}
          className={cx(
            'surgir pointer-events-auto max-w-sm rounded-xl px-4 py-3 text-sm font-medium shadow-lg',
            a.tom === 'critico' ? 'bg-critico text-white' : 'bg-tinta text-fundo',
          )}
        >
          {a.texto}
        </div>
      ))}
    </div>
  );
}
