import { useEffect, useState, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Bell, Bot, Building2, CheckSquare, Cpu, LayoutDashboard, LogOut, Menu, MessagesSquare, Moon, Settings, Sun, X } from 'lucide-react';
import { api } from '../api';
import { cx, useDados } from './ui';

type Contadores = { atendimentos: number; aprovacao: number; modo: 'aprovacao' | 'automatico'; iaSimulada: boolean };

const ITENS = [
  { para: '/', rotulo: 'Painel', icone: LayoutDashboard },
  { para: '/com-voce', rotulo: 'Com você', icone: Bell, contador: 'atendimentos' as const, destaque: true },
  { para: '/aprovacao', rotulo: 'Aprovação', icone: CheckSquare, contador: 'aprovacao' as const },
  { para: '/leads', rotulo: 'Leads', icone: Building2 },
  { para: '/conversas', rotulo: 'Conversas', icone: MessagesSquare },
  { para: '/agentes', rotulo: 'Agentes', icone: Bot },
  { para: '/ia', rotulo: 'IA', icone: Cpu },
  { para: '/configuracoes', rotulo: 'Configurações', icone: Settings },
];

function alternarTema() {
  const raiz = document.documentElement;
  const escuroAtual = raiz.dataset.theme ? raiz.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
  raiz.dataset.theme = escuroAtual ? 'light' : 'dark';
  try {
    localStorage.setItem('tema', raiz.dataset.theme);
  } catch {
    /* armazenamento indisponível: o tema vale só nesta sessão */
  }
}

function Marca() {
  return (
    <div className="flex items-center gap-2.5">
      <img src="/icone.svg" alt="" className="size-8 rounded-[10px]" />
      <div className="leading-tight">
        <div className="text-[14px] font-semibold tracking-tight">Moraes & Oliveira</div>
        <div className="text-[12px] text-tinta-3">Central Comercial</div>
      </div>
    </div>
  );
}

function Navegacao({ c, aoNavegar }: { c: Contadores | null; aoNavegar?: () => void }) {
  return (
    <nav className="flex flex-col gap-0.5" aria-label="Principal">
      {ITENS.map((i) => {
        const n = i.contador && c ? c[i.contador] : 0;
        return (
          <NavLink
            key={i.para}
            to={i.para}
            end={i.para === '/'}
            onClick={aoNavegar}
            className={({ isActive }) =>
              cx('group flex h-9 items-center gap-2.5 rounded-[10px] px-2.5 text-[14px] font-medium transition-colors', isActive ? 'bg-superficie text-tinta shadow-sm ring-1 ring-borda' : 'text-tinta-2 hover:bg-superficie-2 hover:text-tinta')
            }
          >
            <i.icone className="size-[18px] shrink-0" strokeWidth={1.8} />
            <span className="flex-1">{i.rotulo}</span>
            {n > 0 && (
              <span className={cx('numeros min-w-5 rounded-full px-1.5 text-center text-[11px] leading-5 font-semibold', i.destaque ? 'bg-alerta text-[#2a1d00]' : 'bg-superficie-3 text-tinta-2')}>{n}</span>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

export function Estrutura({ children }: { children: ReactNode }) {
  const { dados: c } = useDados<Contadores>('/api/contadores', 20_000);
  const [menu, setMenu] = useState(false);
  const local = useLocation();
  useEffect(() => setMenu(false), [local.pathname]);

  const rodape = (
    <div className="space-y-2 border-t border-borda pt-3">
      {c && (
        <div className="rounded-xl bg-superficie-2 px-3 py-2.5 text-[12px] leading-snug">
          <div className="flex items-center gap-1.5 font-medium">
            <span className={cx('size-2 rounded-full', c.modo === 'automatico' ? 'bg-bom pulsando' : 'bg-alerta')} />
            {c.modo === 'automatico' ? 'Modo automático' : 'Modo aprovação'}
          </div>
          <p className="mt-0.5 text-tinta-3">{c.modo === 'automatico' ? 'Agentes enviam após a revisão ética.' : 'Você aprova cada mensagem antes do envio.'}</p>
          {c.iaSimulada && <p className="mt-1 font-medium text-alerta-tinta">IA simulada (demonstração)</p>}
        </div>
      )}
      <div className="flex gap-1">
        <button onClick={alternarTema} className="flex h-9 flex-1 items-center justify-center gap-2 rounded-[10px] text-[13px] text-tinta-2 hover:bg-superficie-2" aria-label="Alternar tema claro/escuro">
          <Sun className="size-4 dark:hidden" />
          <Moon className="hidden size-4 dark:block" />
          Tema
        </button>
        <button
          onClick={async () => {
            await api('/api/sair', { corpo: {} });
            location.href = '/';
          }}
          className="flex h-9 flex-1 items-center justify-center gap-2 rounded-[10px] text-[13px] text-tinta-2 hover:bg-superficie-2"
        >
          <LogOut className="size-4" /> Sair
        </button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_1fr]">
      {/* Barra lateral (desktop) */}
      <aside className="sticky top-0 hidden h-screen flex-col gap-6 border-r border-borda px-3 py-5 lg:flex">
        <div className="px-2">
          <Marca />
        </div>
        <div className="flex-1 overflow-y-auto rolagem-fina">
          <Navegacao c={c} />
        </div>
        {rodape}
      </aside>

      {/* Topo (celular/tablet) */}
      <header className="sticky top-0 z-40 flex items-center justify-between border-b border-borda bg-fundo/90 px-4 py-3 backdrop-blur lg:hidden">
        <Marca />
        <button onClick={() => setMenu(true)} className="relative rounded-lg p-2 hover:bg-superficie-2" aria-label="Abrir menu">
          <Menu className="size-5" />
          {c && c.atendimentos > 0 && <span className="absolute top-1.5 right-1.5 size-2 rounded-full bg-alerta" />}
        </button>
      </header>
      {menu && (
        <div className="fixed inset-0 z-50 bg-black/40 lg:hidden" onClick={() => setMenu(false)}>
          <div className="surgir absolute inset-y-0 left-0 flex w-[280px] flex-col gap-5 bg-fundo px-3 py-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-2">
              <Marca />
              <button onClick={() => setMenu(false)} className="rounded-lg p-2 hover:bg-superficie-2" aria-label="Fechar menu">
                <X className="size-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <Navegacao c={c} aoNavegar={() => setMenu(false)} />
            </div>
            {rodape}
          </div>
        </div>
      )}

      <main className="min-w-0 px-4 py-5 sm:px-6 lg:px-8 lg:py-7">{children}</main>
    </div>
  );
}

export function Cabecalho({ titulo, descricao, acoes }: { titulo: string; descricao?: ReactNode; acoes?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[22px] font-semibold tracking-tight sm:text-[26px]">{titulo}</h1>
        {descricao && <p className="mt-1 max-w-2xl text-sm text-tinta-2">{descricao}</p>}
      </div>
      {acoes && <div className="flex flex-wrap gap-2">{acoes}</div>}
    </div>
  );
}
