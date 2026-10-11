import { AlertTriangle, CheckCircle2, CircleDashed, Lock, RotateCcw, Server, ShieldAlert } from 'lucide-react';
import { api } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { GraficoUsoIA } from '../componentes/graficos';
import { Botao, Cartao, Carregando, Selo, avisar, cx, dataHora, tempoRelativo, useDados } from '../componentes/ui';

export function IA() {
  const { dados, carregando, recarregar } = useDados<any>('/api/ia', 20_000);
  if (carregando && !dados) return <Carregando />;
  if (!dados) return null;
  const provedores = [...dados.provedores].sort((a: any, b: any) => (a.posicao < 0 ? 99 : a.posicao) - (b.posicao < 0 ? 99 : b.posicao));
  const configurados = provedores.filter((p: any) => p.configurado);
  const nomes = Object.fromEntries(provedores.map((p: any) => [p.id, p.nome]));
  const ordem = provedores.map((p: any) => p.id);
  const ativo = configurados.find((p: any) => !p.pausado && !(p.limiteDiario && p.chamadasHoje >= p.limiteDiario));

  return (
    <div className="space-y-5">
      <Cabecalho
        titulo="IA integrada"
        descricao="Rodízio automático entre provedores gratuitos: quando um esgota o crédito, atinge o limite ou falha, o sistema pausa esse provedor pelo tempo certo e passa para o próximo da fila — sem você fazer nada."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Cartao className="p-5">
          <p className="text-[13px] font-medium text-tinta-2">Atendendo agora</p>
          <p className="mt-2 text-[24px] font-semibold tracking-tight">{dados.simulada ? 'IA simulada' : (ativo?.nome ?? 'Nenhum disponível')}</p>
          <p className="mt-1 text-[13px] text-tinta-3">{dados.simulada ? 'Modo demonstração (IA_SIMULADA=1)' : ativo ? `Modelo ${ativo.modelo}` : 'Os agentes aguardam o próximo provedor liberar'}</p>
        </Cartao>
        <Cartao className="p-5">
          <p className="text-[13px] font-medium text-tinta-2">Provedores no rodízio</p>
          <p className="numeros mt-2 text-[24px] font-semibold tracking-tight">
            {configurados.filter((p: any) => !p.pausado).length}
            <span className="text-tinta-3"> / {configurados.length}</span>
          </p>
          <p className="mt-1 text-[13px] text-tinta-3">disponíveis agora / configurados</p>
        </Cartao>
        <Cartao className="p-5">
          <p className="flex items-center gap-1.5 text-[13px] font-medium text-tinta-2">
            <Lock className="size-4" /> Privacidade estrita
          </p>
          <p className="mt-2 text-[24px] font-semibold tracking-tight">{dados.privacidadeEstrita ? 'Ligada' : 'Desligada'}</p>
          <p className="mt-1 text-[13px] text-tinta-3">
            {dados.privacidadeEstrita ? 'Tarefas com nomes e conversas não vão para provedores que podem treinar com os dados.' : 'Todos os provedores recebem todas as tarefas.'}
          </p>
        </Cartao>
      </div>

      <Cartao titulo="Fila de provedores" subtitulo="Ordem de tentativa (ajuste em Configurações › IA). Cada provedor entra no rodízio ao definir a chave no .env.">
        <ol className="divide-y divide-borda">
          {provedores.map((p: any, i: number) => {
            const uso = p.limiteDiario ? Math.min(100, (p.chamadasHoje / p.limiteDiario) * 100) : null;
            return (
              <li key={p.id} className={cx('grid gap-3 px-5 py-4 md:grid-cols-[28px_1.4fr_1fr_1fr_auto] md:items-center', !p.configurado && 'opacity-55')}>
                <span className="numeros text-[13px] text-tinta-3">{i + 1}</span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{p.nome}</span>
                    {!p.configurado ? (
                      <Selo icone={<CircleDashed className="size-3.5" />}>Sem chave</Selo>
                    ) : p.pausado ? (
                      <Selo tom="alerta" icone={<AlertTriangle className="size-3.5" />}>Pausado</Selo>
                    ) : (
                      <Selo tom="bom" icone={<CheckCircle2 className="size-3.5" />}>Disponível</Selo>
                    )}
                    {p.local && <Selo tom="acento" icone={<Server className="size-3.5" />}>Local</Selo>}
                    {p.podeTreinar && <Selo tom="serio" icone={<ShieldAlert className="size-3.5" />}>Pode treinar com dados</Selo>}
                  </div>
                  <p className="mt-0.5 truncate text-[12px] text-tinta-3">{p.modelo} · {p.observacao}</p>
                  {p.pausado && <p className="mt-0.5 text-[12px] text-alerta-tinta">{p.motivo} · volta {tempoRelativo(p.pausadoAte)}</p>}
                </div>
                <div className="text-[12px]">
                  <div className="numeros mb-1 flex justify-between text-tinta-2">
                    <span>Hoje</span>
                    <span>
                      {p.chamadasHoje}
                      {p.limiteDiario ? ` / ${p.limiteDiario}` : ''}
                    </span>
                  </div>
                  {uso !== null && (
                    <div className="h-1.5 rounded-full bg-superficie-2">
                      <div className="h-full rounded-full" style={{ width: `${uso}%`, background: uso >= 100 ? 'var(--alerta)' : 'var(--serie-1)' }} />
                    </div>
                  )}
                </div>
                <div className="numeros text-[12px] text-tinta-2">
                  {p.chamadas24h ? `${Math.round((p.sucesso24h / p.chamadas24h) * 100)}% sucesso · ${p.latenciaMediaMs ? `${(p.latenciaMediaMs / 1000).toFixed(1)} s` : '—'}` : 'Sem chamadas em 24 h'}
                </div>
                <div>
                  {p.pausado && (
                    <Botao
                      tamanho="sm"
                      variante="fantasma"
                      onClick={async () => {
                        await api(`/api/ia/${p.id}/reativar`, { corpo: {} });
                        avisar(`${p.nome} reativado`);
                        void recarregar();
                      }}
                    >
                      <RotateCcw className="size-3.5" /> Reativar
                    </Botao>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      </Cartao>

      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Cartao titulo="Chamadas por hora (24 h)" subtitulo="Veja o rodízio acontecer: quando um provedor esgota, outro assume">
          <GraficoUsoIA porHora={dados.porHora} ordem={ordem} nomes={nomes} />
          <div className="h-3" />
        </Cartao>
        <Cartao titulo="Falhas recentes" subtitulo="Cada falha pausa o provedor e passa a vez">
          <ul className="max-h-80 divide-y divide-borda overflow-y-auto px-5 pb-3 rolagem-fina">
            {dados.falhas.map((f: any, i: number) => (
              <li key={i} className="py-2.5 text-[13px]">
                <div className="flex justify-between gap-2">
                  <span className="font-medium">{nomes[f.provedor] ?? f.provedor}</span>
                  <span className="text-[12px] text-tinta-3">{dataHora(f.criado_em)}</span>
                </div>
                <p className="line-clamp-2 text-tinta-2">
                  {f.status_http ? `HTTP ${f.status_http} · ` : ''}
                  {f.erro}
                </p>
              </li>
            ))}
            {!dados.falhas.length && <p className="py-8 text-center text-sm text-tinta-3">Nenhuma falha registrada.</p>}
          </ul>
        </Cartao>
      </div>
    </div>
  );
}
