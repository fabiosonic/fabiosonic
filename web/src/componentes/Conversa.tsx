import { useEffect, useRef, useState } from 'react';
import { Bot, Send, User } from 'lucide-react';
import { api, type Mensagem } from '../api';
import { IconeCanal, NOMES_INTENCAO, NOMES_STATUS_MSG } from './dominio';
import { Botao, Selo, avisar, classeEntrada, cx, dataHora } from './ui';

export function Conversa({ leadId, mensagens, canaisDisponiveis, aoEnviar, altura = 'max-h-[560px]' }: { leadId: number; mensagens: Mensagem[]; canaisDisponiveis: ('email' | 'whatsapp')[]; aoEnviar: () => void; altura?: string }) {
  const visiveis = mensagens.filter((m) => m.status !== 'descartada');
  const ultimaEntrada = [...visiveis].reverse().find((m) => m.direcao === 'entrada');
  const [canal, setCanal] = useState<'email' | 'whatsapp'>(ultimaEntrada?.canal ?? canaisDisponiveis[0] ?? 'email');
  const [texto, setTexto] = useState('');
  const [enviando, setEnviando] = useState(false);
  const fim = useRef<HTMLDivElement>(null);
  useEffect(() => fim.current?.scrollIntoView({ block: 'nearest' }), [visiveis.length]);

  return (
    <div className="flex flex-col">
      <div className={cx('flex flex-col gap-3 overflow-y-auto px-4 py-4 rolagem-fina sm:px-5', altura)}>
        {!visiveis.length && <p className="py-10 text-center text-sm text-tinta-3">Nenhuma mensagem ainda.</p>}
        {visiveis.map((m) => {
          const saida = m.direcao === 'saida';
          const humano = m.revisao && (m.revisao as any).autor === 'humano';
          return (
            <div key={m.id} className={cx('flex max-w-[88%] flex-col gap-1 sm:max-w-[75%]', saida ? 'items-end self-end' : 'items-start self-start')}>
              <div className="flex items-center gap-1.5 text-[11px] text-tinta-3">
                {saida ? humano ? <User className="size-3" /> : <Bot className="size-3" /> : null}
                <IconeCanal canal={m.canal} className="size-3" />
                <span>{saida ? (humano ? 'Você' : m.agente === 'atendente' ? 'Atendente' : 'Redator') : 'Lead'}</span>
                <span>· {dataHora(m.enviada_em ?? m.criado_em)}</span>
              </div>
              <div
                className={cx(
                  'rounded-2xl px-3.5 py-2.5 text-[14px] leading-relaxed whitespace-pre-line',
                  saida ? 'rounded-br-md bg-acento text-white' : 'rounded-bl-md border border-borda bg-superficie-2',
                  m.status === 'aguardando_aprovacao' && 'opacity-60',
                )}
              >
                {m.assunto && <div className={cx('mb-1 text-[13px] font-semibold', saida ? 'text-white/90' : '')}>{m.assunto}</div>}
                {m.corpo}
              </div>
              <div className="flex flex-wrap gap-1">
                {m.intencao && <Selo tom={['preco', 'tecnico', 'quer_humano', 'reuniao'].includes(m.intencao) ? 'alerta' : 'neutro'}>{NOMES_INTENCAO[m.intencao] ?? m.intencao}</Selo>}
                {saida && !['enviada', 'entregue', 'lida'].includes(m.status) && (
                  <Selo tom={m.status === 'falhou' || m.status === 'bloqueada' ? 'critico' : m.status === 'aguardando_aprovacao' ? 'alerta' : 'neutro'}>{NOMES_STATUS_MSG[m.status] ?? m.status}</Selo>
                )}
                {saida && m.status === 'lida' && <span className="text-[11px] text-tinta-3">lida</span>}
                {m.erro && m.status === 'falhou' && <span className="text-[11px] text-critico-tinta">{m.erro}</span>}
              </div>
            </div>
          );
        })}
        <div ref={fim} />
      </div>
      {canaisDisponiveis.length > 0 ? (
        <form
          className="flex flex-col gap-2 border-t border-borda p-3 sm:flex-row sm:items-end"
          onSubmit={async (e) => {
            e.preventDefault();
            if (!texto.trim()) return;
            setEnviando(true);
            try {
              await api(`/api/leads/${leadId}/mensagens`, { corpo: { canal, corpo: texto } });
              setTexto('');
              avisar('Mensagem na fila de envio');
              aoEnviar();
            } catch (x) {
              avisar((x as Error).message, 'critico');
            } finally {
              setEnviando(false);
            }
          }}
        >
          <select className={classeEntrada + ' sm:w-36'} value={canal} onChange={(e) => setCanal(e.target.value as 'email' | 'whatsapp')} aria-label="Canal">
            {canaisDisponiveis.map((c) => (
              <option key={c} value={c}>
                {c === 'email' ? 'E-mail' : 'WhatsApp'}
              </option>
            ))}
          </select>
          <textarea
            className={classeEntrada + ' min-h-[44px] flex-1 resize-y'}
            rows={2}
            placeholder="Escreva sua resposta…"
            value={texto}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) (e.currentTarget.form as HTMLFormElement).requestSubmit();
            }}
          />
          <Botao type="submit" variante="primario" carregando={enviando} className="sm:h-[44px]">
            <Send className="size-4" /> Enviar
          </Botao>
        </form>
      ) : (
        <p className="border-t border-borda px-5 py-3 text-[13px] text-tinta-3">Sem canal de contato disponível (bloqueado ou inexistente).</p>
      )}
    </div>
  );
}
