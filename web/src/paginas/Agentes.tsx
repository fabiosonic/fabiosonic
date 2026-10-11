import { useState } from 'react';
import { Bot, CheckCircle2, Clock, Play, XCircle } from 'lucide-react';
import { api } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { NOMES_AGENTE } from '../componentes/dominio';
import { Botao, Cartao, Carregando, Selo, avisar, cx, dataHora, tempoRelativo, useDados } from '../componentes/ui';

const intervalo = (ms: number | null) => (!ms ? 'Sob demanda' : ms < 3600_000 ? `A cada ${Math.round(ms / 60_000)} min` : `A cada ${Math.round(ms / 3600_000)} h`);

export function Agentes() {
  const { dados, carregando, recarregar } = useDados<{ agentes: any[]; execucoes: any[] }>('/api/agentes', 10_000);
  const [executando, setExecutando] = useState<string | null>(null);
  if (carregando && !dados) return <Carregando />;
  if (!dados) return null;
  const diretor = dados.agentes.find((a) => a.id === 'diretor');
  const equipe = dados.agentes.filter((a) => a.id !== 'diretor');

  const CartaoAgente = ({ a, grande }: { a: any; grande?: boolean }) => {
    const u = a.ultimaExecucao;
    return (
      <Cartao className={cx('flex flex-col p-5', grande && 'md:flex-row md:items-center md:gap-6')}>
        <div className="flex flex-1 items-start gap-3">
          <div className={cx('grid shrink-0 place-items-center rounded-xl', grande ? 'size-12 bg-tinta text-fundo' : 'size-10 bg-superficie-2 text-tinta-2')}>
            <Bot className={grande ? 'size-6' : 'size-5'} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-semibold">{a.nome}</h2>
              {a.rodando ? (
                <Selo tom="acento" icone={<span className="size-1.5 rounded-full bg-acento pulsando" />}>Trabalhando</Selo>
              ) : u?.sucesso === 0 ? (
                <Selo tom="critico" icone={<XCircle className="size-3.5" />}>Última execução falhou</Selo>
              ) : u ? (
                <Selo tom="bom" icone={<CheckCircle2 className="size-3.5" />}>Operando</Selo>
              ) : (
                <Selo>{a.executavel ? 'Aguardando' : 'Acionado por outros agentes'}</Selo>
              )}
            </div>
            <p className="text-[12px] font-medium text-tinta-3">{a.papel}</p>
            <p className="mt-2 text-[13px] leading-relaxed text-tinta-2">{a.descricao}</p>
          </div>
        </div>
        <div className={cx('mt-4 space-y-2 border-t border-borda pt-3 text-[12px] text-tinta-3', grande && 'md:mt-0 md:w-72 md:border-t-0 md:border-l md:pt-0 md:pl-6')}>
          <div className="flex items-center gap-1.5">
            <Clock className="size-3.5" /> {intervalo(a.intervaloMs)}
            {u && <span>· última {tempoRelativo(u.inicio)}</span>}
          </div>
          {u?.resumo && <p className="line-clamp-2 text-tinta-2">{u.resumo}</p>}
          <p className="numeros">
            {a.atividade24h} ações em 24 h{a.falhas24h ? ` · ${a.falhas24h} falha(s)` : ''}
          </p>
          {a.executavel && (
            <Botao
              tamanho="sm"
              carregando={executando === a.id}
              onClick={async () => {
                setExecutando(a.id);
                try {
                  const r = await api(`/api/agentes/${a.id}/executar`, { corpo: {} });
                  avisar(`${a.nome}: ${typeof r.resumo === 'string' ? r.resumo.slice(0, 120) : 'concluído'}`);
                } catch (e) {
                  avisar((e as Error).message, 'critico');
                } finally {
                  setExecutando(null);
                  void recarregar();
                }
              }}
            >
              <Play className="size-3.5" /> Executar agora
            </Botao>
          )}
        </div>
      </Cartao>
    );
  };

  return (
    <div className="space-y-5">
      <Cabecalho
        titulo="Equipe de agentes"
        descricao="Cada agente é especialista em uma etapa do comercial e trabalha 24 horas por dia. O Diretor Comercial coordena; o Revisor de Ética é portão obrigatório antes de qualquer envio."
      />
      {diretor && <CartaoAgente a={diretor} grande />}
      <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3">
        {equipe.map((a) => (
          <CartaoAgente key={a.id} a={a} />
        ))}
      </div>
      <Cartao titulo="Execuções recentes">
        <div className="overflow-x-auto rolagem-fina">
          <table className="w-full min-w-[640px] text-[13px]">
            <thead>
              <tr className="border-b border-borda text-left text-[12px] text-tinta-3">
                <th className="px-5 py-2.5 font-medium">Agente</th>
                <th className="px-3 py-2.5 font-medium">Início</th>
                <th className="px-3 py-2.5 font-medium">Resultado</th>
                <th className="px-5 py-2.5 text-right font-medium">Processados</th>
              </tr>
            </thead>
            <tbody className="numeros">
              {dados.execucoes.map((x) => (
                <tr key={x.id} className="border-b border-borda last:border-0">
                  <td className="px-5 py-2.5 font-medium">{NOMES_AGENTE[x.agente] ?? x.agente}</td>
                  <td className="px-3 py-2.5 text-tinta-3">{dataHora(x.inicio)}</td>
                  <td className={cx('max-w-md truncate px-3 py-2.5', x.sucesso === 0 ? 'text-critico-tinta' : 'text-tinta-2')}>{x.resumo ?? (x.fim ? 'ok' : 'em andamento')}</td>
                  <td className="px-5 py-2.5 text-right">{x.processados ?? 0}</td>
                </tr>
              ))}
              {!dados.execucoes.length && (
                <tr>
                  <td colSpan={4} className="px-5 py-8 text-center text-tinta-3">
                    Os agentes ainda não rodaram. Eles começam sozinhos quando o servidor inicia.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Cartao>
    </div>
  );
}
