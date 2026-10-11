import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, MessagesSquare } from 'lucide-react';
import { Cabecalho } from '../componentes/Estrutura';
import { Conversa } from '../componentes/Conversa';
import { IconeCanal, NOMES_INTENCAO, SeloEtapa } from '../componentes/dominio';
import { Cartao, Carregando, Selo, Vazio, cx, tempoRelativo, useDados } from '../componentes/ui';

export function Conversas() {
  const { id } = useParams();
  const navegar = useNavigate();
  const { dados: lista, carregando } = useDados<any[]>('/api/conversas', 15_000);
  const { dados: lead, recarregar } = useDados<any>(id ? `/api/leads/${id}` : null, 15_000);
  const canais = lead ? (['email', 'whatsapp'] as const).filter((c) => lead.contatos.some((ct: any) => ct.tipo === c && !ct.bloqueado)) : [];

  return (
    <div>
      <Cabecalho titulo="Conversas" descricao="Respostas dos leads por e-mail e WhatsApp, numa caixa única. O Atendente responde sozinho até o lead pedir você." />
      <div className="grid gap-4 lg:grid-cols-[340px_1fr]">
        <Cartao className={cx('overflow-hidden', id && 'hidden lg:block')}>
          {carregando && !lista ? (
            <Carregando />
          ) : !lista?.length ? (
            <Vazio icone={<MessagesSquare className="size-5" />} titulo="Nenhuma conversa ainda" texto="Quando um lead responder, a conversa aparece aqui." />
          ) : (
            <ul className="max-h-[calc(100vh-220px)] divide-y divide-borda overflow-y-auto rolagem-fina">
              {lista.map((c) => (
                <li key={c.lead_id}>
                  <button
                    onClick={() => navegar(`/conversas/${c.lead_id}`)}
                    className={cx('flex w-full flex-col gap-1 px-4 py-3 text-left hover:bg-superficie-2/60', String(c.lead_id) === id && 'bg-acento-suave/60')}
                  >
                    <div className="flex items-center gap-2">
                      <span className="flex-1 truncate text-[14px] font-medium">{c.empresa}</span>
                      <span className="shrink-0 text-[11px] text-tinta-3">{tempoRelativo(c.criado_em)}</span>
                    </div>
                    <p className="flex items-center gap-1.5 text-[13px] text-tinta-2">
                      <IconeCanal canal={c.canal} className="size-3.5 shrink-0 text-tinta-3" />
                      <span className="truncate">
                        {c.direcao === 'saida' ? 'Você: ' : ''}
                        {c.corpo}
                      </span>
                    </p>
                    <div className="flex gap-1">
                      <SeloEtapa etapa={c.etapa} />
                      {c.intencao && <Selo>{NOMES_INTENCAO[c.intencao] ?? c.intencao}</Selo>}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Cartao>
        <Cartao className={cx(!id && 'hidden lg:block')}>
          {!id ? (
            <Vazio icone={<MessagesSquare className="size-5" />} titulo="Selecione uma conversa" />
          ) : !lead ? (
            <Carregando />
          ) : (
            <>
              <header className="flex items-center gap-3 border-b border-borda px-5 py-3">
                <Link to="/conversas" className="rounded-lg p-1 hover:bg-superficie-2 lg:hidden" aria-label="Voltar">
                  <ArrowLeft className="size-4" />
                </Link>
                <div className="min-w-0 flex-1">
                  <Link to={`/leads/${id}`} className="font-semibold hover:underline">
                    {lead.empresa.nome}
                  </Link>
                  <p className="truncate text-[12px] text-tinta-3">{[lead.empresa.segmento, lead.empresa.municipio && `${lead.empresa.municipio}/${lead.empresa.uf}`].filter(Boolean).join(' · ')}</p>
                </div>
                <SeloEtapa etapa={lead.lead.etapa} />
              </header>
              <Conversa leadId={Number(id)} mensagens={lead.mensagens} canaisDisponiveis={[...canais]} aoEnviar={recarregar} altura="h-[calc(100vh-330px)] min-h-[320px]" />
            </>
          )}
        </Cartao>
      </div>
    </div>
  );
}
