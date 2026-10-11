import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Bell, CheckCheck, Hand, MessageSquareText } from 'lucide-react';
import { api } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { Pontuacao } from '../componentes/dominio';
import { Abas, Botao, Cartao, Carregando, Modal, Selo, Vazio, avisar, classeEntrada, Campo, tempoRelativo, useDados } from '../componentes/ui';

const RESULTADOS = [
  { id: '', rotulo: 'Devolver ao atendimento automático' },
  { id: 'proposta', rotulo: 'Vou enviar proposta' },
  { id: 'negociacao', rotulo: 'Em negociação' },
  { id: 'cliente', rotulo: 'Fechou contrato (cliente)' },
  { id: 'perdida', rotulo: 'Não avançou (perdida)' },
];

export function ComVoce() {
  const [filtro, setFiltro] = useState<'abertos' | 'todos'>('abertos');
  const { dados, carregando, recarregar } = useDados<any[]>(`/api/atendimentos${filtro === 'todos' ? '?status=todos' : ''}`, 20_000);
  const [resolvendo, setResolvendo] = useState<any | null>(null);
  const [resultado, setResultado] = useState('');
  const [observacao, setObservacao] = useState('');

  const acao = async (id: number, tipo: 'assumir' | 'resolver', corpo: object = {}) => {
    await api(`/api/atendimentos/${id}/${tipo}`, { corpo });
    avisar(tipo === 'assumir' ? 'Atendimento assumido' : 'Atendimento resolvido');
    void recarregar();
  };

  return (
    <div>
      <Cabecalho
        titulo="Com você"
        descricao="Leads que pediram para falar com uma pessoa, perguntaram preço, trouxeram dúvida técnica ou aceitaram conversar. A IA já respondeu avisando que você vai retornar."
        acoes={<Abas abas={[{ id: 'abertos', rotulo: 'Em aberto' }, { id: 'todos', rotulo: 'Todos' }]} ativa={filtro} aoMudar={setFiltro} />}
      />
      {carregando && !dados ? (
        <Carregando />
      ) : !dados?.length ? (
        <Cartao>
          <Vazio icone={<Bell className="size-5" />} titulo="Ninguém esperando por você" texto="Quando um lead quiser falar com você, ele aparece aqui e você recebe um aviso por e-mail e WhatsApp." />
        </Cartao>
      ) : (
        <div className="grid gap-3">
          {dados.map((a) => (
            <Cartao key={a.id} className="surgir p-5">
              <div className="flex flex-col gap-4 md:flex-row md:items-start">
                <Pontuacao valor={a.pontuacao} tamanho={44} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link to={`/leads/${a.lead_id}`} className="text-[16px] font-semibold hover:underline">
                      {a.empresa}
                    </Link>
                    <Selo tom="alerta">{a.rotulo}</Selo>
                    {a.status === 'assumido' && <Selo tom="acento">Com você</Selo>}
                    {a.status === 'resolvido' && <Selo tom="bom">Resolvido</Selo>}
                  </div>
                  <p className="mt-1 text-[13px] text-tinta-3">
                    {[a.segmento, a.municipio && `${a.municipio}/${a.uf}`].filter(Boolean).join(' · ')} · chamou {tempoRelativo(a.criado_em)}
                    {a.notificado ? ' · você foi avisado' : ''}
                  </p>
                  {a.mensagem && <blockquote className="mt-3 rounded-xl border-l-[3px] border-alerta bg-superficie-2 px-4 py-3 text-sm whitespace-pre-line">{a.mensagem}</blockquote>}
                  {a.resumo && !a.mensagem && <p className="mt-3 text-sm text-tinta-2">{a.resumo}</p>}
                </div>
                <div className="flex shrink-0 flex-wrap gap-2 md:flex-col">
                  <Link to={`/conversas/${a.lead_id}`} className="inline-flex h-9 items-center gap-1.5 rounded-[10px] bg-tinta px-3.5 text-sm font-medium text-fundo hover:opacity-90">
                    <MessageSquareText className="size-4" /> Responder
                  </Link>
                  {a.status === 'aberto' && (
                    <Botao onClick={() => acao(a.id, 'assumir')}>
                      <Hand className="size-4" /> Assumir
                    </Botao>
                  )}
                  {a.status !== 'resolvido' && (
                    <Botao variante="fantasma" onClick={() => (setResolvendo(a), setResultado(''), setObservacao(''))}>
                      <CheckCheck className="size-4" /> Resolver
                    </Botao>
                  )}
                </div>
              </div>
            </Cartao>
          ))}
        </div>
      )}

      <Modal aberto={Boolean(resolvendo)} aoFechar={() => setResolvendo(null)} titulo={`Resolver — ${resolvendo?.empresa ?? ''}`}>
        <div className="space-y-4">
          <Campo rotulo="Como ficou?">
            <select className={classeEntrada} value={resultado} onChange={(e) => setResultado(e.target.value)}>
              {RESULTADOS.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.rotulo}
                </option>
              ))}
            </select>
          </Campo>
          <Campo rotulo={resultado === 'cliente' ? 'Evidência do contrato (obrigatória)' : 'Observação'} ajuda={resultado === 'cliente' ? 'Ex.: contrato assinado em 10/10 via plataforma X. Só contrato formalizado conta como novo cliente.' : undefined}>
            <textarea className={classeEntrada} rows={3} value={observacao} onChange={(e) => setObservacao(e.target.value)} />
          </Campo>
          <div className="flex justify-end gap-2">
            <Botao variante="fantasma" onClick={() => setResolvendo(null)}>
              Cancelar
            </Botao>
            <Botao
              variante="primario"
              disabled={resultado === 'cliente' && !observacao.trim()}
              onClick={async () => {
                if (resultado === 'cliente') await api(`/api/leads/${resolvendo.lead_id}`, { metodo: 'PATCH', corpo: { etapa: 'cliente', evidencia: observacao } });
                await acao(resolvendo.id, 'resolver', resultado ? { resultado: resultado === 'cliente' ? 'cliente' : resultado, observacao } : { observacao });
                setResolvendo(null);
              }}
            >
              Confirmar
            </Botao>
          </div>
        </div>
      </Modal>
    </div>
  );
}
