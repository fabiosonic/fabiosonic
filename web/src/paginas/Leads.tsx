import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Building2, Columns3, List, Plus, Search, Upload } from 'lucide-react';
import { api, type LeadResumo } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { NOMES_ETAPA, Pontuacao, SeloEtapa, SeloTemperatura } from '../componentes/dominio';
import { Abas, Botao, Campo, Cartao, Carregando, Modal, Vazio, avisar, classeEntrada, cx, formatarCnpj, tempoRelativo, useDados } from '../componentes/ui';

const COLUNAS = ['mapeada', 'enriquecida', 'qualificada', 'em_contato', 'respondeu', 'com_voce', 'proposta', 'negociacao', 'cliente'];
const ACOES: Record<string, string> = {
  primeiro_contato: 'Primeiro contato',
  lembrete: 'Lembrete',
  acompanhamento: 'Acompanhamento',
  ultimo_contato: 'Último contato',
  encerrar_cadencia: 'Encerrar cadência',
  aguardando_envio_anterior: 'Aguardando envio anterior',
  retomar_apos_ausencia: 'Retomar após ausência',
};

function CartaoLead({ l }: { l: LeadResumo }) {
  return (
    <Link to={`/leads/${l.id}`} className="block rounded-xl border border-borda bg-superficie p-3 shadow-[var(--sombra)] transition hover:border-borda-forte">
      <div className="flex items-start gap-2.5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-[14px] font-medium">{l.empresa}</p>
          <p className="truncate text-[12px] text-tinta-3">{l.segmento ?? 'Segmento a definir'}</p>
        </div>
        <Pontuacao valor={l.pontuacao} tamanho={32} />
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 text-[12px] text-tinta-3">
        <SeloTemperatura t={l.temperatura} />
        {l.cidade && <span className="truncate">{l.cidade}</span>}
      </div>
      {l.proximaAcao && ACOES[l.proximaAcao] && (
        <p className="mt-2 border-t border-borda pt-2 text-[12px] text-tinta-2">
          {ACOES[l.proximaAcao]} {l.proximaAcaoEm && <span className="text-tinta-3">· {tempoRelativo(l.proximaAcaoEm)}</span>}
        </p>
      )}
    </Link>
  );
}

export function Leads() {
  const [params, setParams] = useSearchParams();
  const navegar = useNavigate();
  const [visao, setVisao] = useState<'quadro' | 'lista'>(() => {
    try {
      return (localStorage.getItem('visao-leads') as 'quadro' | 'lista') || 'quadro';
    } catch {
      return 'quadro';
    }
  });
  const [busca, setBusca] = useState(params.get('busca') ?? '');
  const [etapa, setEtapa] = useState(params.get('etapa') ?? '');
  const [ordem, setOrdem] = useState('recentes');
  const [buscaAplicada, setBuscaAplicada] = useState(busca);
  useEffect(() => {
    const t = setTimeout(() => setBuscaAplicada(busca), 300);
    return () => clearTimeout(t);
  }, [busca]);
  useEffect(() => {
    try {
      localStorage.setItem('visao-leads', visao);
    } catch {
      /* sem armazenamento */
    }
  }, [visao]);

  const consulta = useMemo(() => {
    const q = new URLSearchParams({ limite: '500', ordem });
    if (buscaAplicada) q.set('busca', buscaAplicada);
    if (etapa) q.set('etapa', etapa);
    return `/api/leads?${q}`;
  }, [buscaAplicada, etapa, ordem]);
  const { dados, carregando, recarregar } = useDados<{ total: number; leads: LeadResumo[] }>(consulta, 30_000);

  const [novo, setNovo] = useState(params.get('novo') === '1');
  const [importar, setImportar] = useState(false);

  return (
    <div>
      <Cabecalho
        titulo="Leads"
        descricao="Todas as empresas no funil, com origem registrada. Os agentes movem os cards sozinhos; você pode mover manualmente na ficha."
        acoes={
          <>
            <Botao onClick={() => setImportar(true)}>
              <Upload className="size-4" /> Importar lista
            </Botao>
            <Botao variante="primario" onClick={() => setNovo(true)}>
              <Plus className="size-4" /> Novo lead
            </Botao>
          </>
        }
      />

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-tinta-3" />
          <input className={classeEntrada + ' pl-9'} placeholder="Buscar por nome, CNPJ ou cidade" value={busca} onChange={(e) => setBusca(e.target.value)} />
        </div>
        <select className={classeEntrada + ' lg:w-48'} value={etapa} onChange={(e) => (setEtapa(e.target.value), setParams(e.target.value ? { etapa: e.target.value } : {}))} aria-label="Etapa">
          <option value="">Todas as etapas</option>
          {Object.entries(NOMES_ETAPA).map(([id, nome]) => (
            <option key={id} value={id}>
              {nome}
            </option>
          ))}
        </select>
        <select className={classeEntrada + ' lg:w-48'} value={ordem} onChange={(e) => setOrdem(e.target.value)} aria-label="Ordenar">
          <option value="recentes">Atualizados recentemente</option>
          <option value="pontuacao">Maior pontuação</option>
          <option value="abertura">Abertura mais recente</option>
        </select>
        <Abas
          abas={[
            { id: 'quadro', rotulo: <span className="inline-flex items-center gap-1.5"><Columns3 className="size-4" /> Quadro</span> },
            { id: 'lista', rotulo: <span className="inline-flex items-center gap-1.5"><List className="size-4" /> Lista</span> },
          ]}
          ativa={visao}
          aoMudar={setVisao}
        />
      </div>

      {carregando && !dados ? (
        <Carregando />
      ) : !dados?.leads.length ? (
        <Cartao>
          <Vazio icone={<Building2 className="size-5" />} titulo="Nenhum lead encontrado" texto="Ative a busca nos Dados Abertos em Configurações, importe uma lista ou cadastre um lead." />
        </Cartao>
      ) : visao === 'quadro' && !etapa ? (
        <div className="-mx-4 overflow-x-auto px-4 pb-4 rolagem-fina sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="flex gap-3">
            {COLUNAS.map((c) => {
              const itens = dados.leads.filter((l) => l.etapa === c);
              return (
                <section key={c} className={cx('flex w-[272px] shrink-0 flex-col rounded-2xl bg-superficie-2/70 p-2', c === 'com_voce' && 'ring-1 ring-alerta/50')}>
                  <header className="flex items-center justify-between px-2 py-1.5">
                    <h2 className="text-[13px] font-semibold">{NOMES_ETAPA[c]}</h2>
                    <span className="numeros text-[12px] text-tinta-3">{itens.length}</span>
                  </header>
                  <div className="flex max-h-[calc(100vh-280px)] min-h-24 flex-col gap-2 overflow-y-auto p-1 rolagem-fina">
                    {itens.map((l) => (
                      <CartaoLead key={l.id} l={l} />
                    ))}
                    {!itens.length && <p className="px-2 py-6 text-center text-[12px] text-tinta-3">Vazio</p>}
                  </div>
                </section>
              );
            })}
          </div>
          <p className="mt-2 text-[12px] text-tinta-3">Pausadas, descartadas e perdidas aparecem na visão em lista ou pelo filtro de etapa.</p>
        </div>
      ) : (
        <Cartao className="overflow-hidden">
          <div className="overflow-x-auto rolagem-fina">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-borda text-left text-[12px] text-tinta-3">
                  <th className="px-5 py-3 font-medium">Empresa</th>
                  <th className="px-3 py-3 font-medium">Etapa</th>
                  <th className="px-3 py-3 font-medium">Pontos</th>
                  <th className="px-3 py-3 font-medium">Segmento</th>
                  <th className="px-3 py-3 font-medium">Cidade</th>
                  <th className="px-3 py-3 font-medium">Origem</th>
                  <th className="px-5 py-3 text-right font-medium">Atualizado</th>
                </tr>
              </thead>
              <tbody className="numeros">
                {dados.leads.map((l) => (
                  <tr key={l.id} onClick={() => navegar(`/leads/${l.id}`)} className="cursor-pointer border-b border-borda last:border-0 hover:bg-superficie-2/60">
                    <td className="px-5 py-3">
                      <div className="font-medium">{l.empresa}</div>
                      <div className="text-[12px] text-tinta-3">{formatarCnpj(l.cnpj)}</div>
                    </td>
                    <td className="px-3 py-3">
                      <SeloEtapa etapa={l.etapa} />
                    </td>
                    <td className="px-3 py-3">
                      <Pontuacao valor={l.pontuacao} tamanho={30} />
                    </td>
                    <td className="max-w-48 truncate px-3 py-3 text-tinta-2">{l.segmento ?? '—'}</td>
                    <td className="px-3 py-3 text-tinta-2">{l.cidade ?? '—'}</td>
                    <td className="px-3 py-3 text-tinta-3">{l.origem.replace(/_/g, ' ')}</td>
                    <td className="px-5 py-3 text-right text-tinta-3">{tempoRelativo(l.atualizadoEm)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="border-t border-borda px-5 py-2.5 text-[12px] text-tinta-3">{dados.total} lead(s)</p>
        </Cartao>
      )}

      <ModalNovoLead aberto={novo} aoFechar={() => (setNovo(false), setParams({}))} aoCriar={(id) => navegar(`/leads/${id}`)} />
      <ModalImportar aberto={importar} aoFechar={() => setImportar(false)} aoConcluir={recarregar} />
    </div>
  );
}

function ModalNovoLead({ aberto, aoFechar, aoCriar }: { aberto: boolean; aoFechar: () => void; aoCriar: (id: number) => void }) {
  const [f, setF] = useState({ cnpj: '', email: '', whatsapp: '', nome: '', origem: '', optin: false });
  const [enviando, setEnviando] = useState(false);
  const mudar = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value });
  return (
    <Modal aberto={aberto} aoFechar={aoFechar} titulo="Novo lead">
      <form
        className="space-y-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setEnviando(true);
          try {
            const r = await api<{ leadId: number; novo: boolean }>('/api/leads', { corpo: f });
            avisar(r.novo ? 'Lead criado. O Enriquecedor já vai buscar os dados.' : 'Este lead já existia');
            aoCriar(r.leadId);
          } catch (x) {
            avisar((x as Error).message, 'critico');
          } finally {
            setEnviando(false);
          }
        }}
      >
        <Campo rotulo="CNPJ" ajuda="Com o CNPJ, o sistema busca cadastro, sócios, site e contatos sozinho.">
          <input className={classeEntrada} value={f.cnpj} onChange={mudar('cnpj')} placeholder="00.000.000/0000-00" inputMode="numeric" />
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo rotulo="Nome do contato">
            <input className={classeEntrada} value={f.nome} onChange={mudar('nome')} />
          </Campo>
          <Campo rotulo="Origem" ajuda="Ex.: indicação do cliente X, evento Y">
            <input className={classeEntrada} value={f.origem} onChange={mudar('origem')} required />
          </Campo>
          <Campo rotulo="E-mail">
            <input className={classeEntrada} type="email" value={f.email} onChange={mudar('email')} />
          </Campo>
          <Campo rotulo="WhatsApp">
            <input className={classeEntrada} value={f.whatsapp} onChange={mudar('whatsapp')} placeholder="(11) 90000-0000" inputMode="tel" />
          </Campo>
        </div>
        <label className="flex items-start gap-2.5 rounded-xl bg-superficie-2 p-3 text-[13px]">
          <input type="checkbox" className="mt-0.5" checked={f.optin} onChange={mudar('optin')} />
          <span>O contato autorizou receber mensagens do escritório (permite iniciar pelo WhatsApp).</span>
        </label>
        <div className="flex justify-end gap-2">
          <Botao type="button" variante="fantasma" onClick={aoFechar}>
            Cancelar
          </Botao>
          <Botao type="submit" variante="primario" carregando={enviando}>
            Criar lead
          </Botao>
        </div>
      </form>
    </Modal>
  );
}

function ModalImportar({ aberto, aoFechar, aoConcluir }: { aberto: boolean; aoFechar: () => void; aoConcluir: () => void }) {
  const [texto, setTexto] = useState('');
  const [origem, setOrigem] = useState('');
  const [resultado, setResultado] = useState<any>(null);
  const [enviando, setEnviando] = useState(false);
  return (
    <Modal aberto={aberto} aoFechar={aoFechar} titulo="Importar lista de empresas" largura="max-w-2xl">
      <div className="space-y-4">
        <p className="text-sm text-tinta-2">
          Uma empresa por linha: <code className="rounded bg-superficie-2 px-1">cnpj;email;whatsapp;nome</code>. Só o CNPJ é obrigatório. Não importe listas compradas ou de origem desconhecida.
        </p>
        <Campo rotulo="Origem da lista (obrigatória)" ajuda="Registrada em cada lead para fins de LGPD.">
          <input className={classeEntrada} value={origem} onChange={(e) => setOrigem(e.target.value)} placeholder="Ex.: participantes do evento da ACIC em 05/10, com autorização" />
        </Campo>
        <textarea className={classeEntrada + ' min-h-48 font-mono text-[13px]'} value={texto} onChange={(e) => setTexto(e.target.value)} placeholder={'12345678000190;contato@empresa.com.br;11999990000;Maria\n98765432000110'} />
        {resultado && (
          <div className="rounded-xl bg-superficie-2 p-3 text-sm">
            {resultado.criados} criados, {resultado.existentes} já existiam.
            {resultado.erros.length > 0 && <ul className="mt-1 text-[12px] text-critico-tinta">{resultado.erros.slice(0, 8).map((e: string) => <li key={e}>{e}</li>)}</ul>}
          </div>
        )}
        <div className="flex justify-end gap-2">
          <Botao variante="fantasma" onClick={aoFechar}>
            Fechar
          </Botao>
          <Botao
            variante="primario"
            disabled={!texto.trim() || !origem.trim()}
            carregando={enviando}
            onClick={async () => {
              setEnviando(true);
              const r = await api('/api/leads/importar', { corpo: { texto, origem } });
              setResultado(r);
              setEnviando(false);
              aoConcluir();
            }}
          >
            Importar
          </Botao>
        </div>
      </div>
    </Modal>
  );
}
