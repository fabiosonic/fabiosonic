import { useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCheck, CheckSquare, RefreshCw, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react';
import { api } from '../api';
import { Cabecalho } from '../componentes/Estrutura';
import { IconeCanal, Pontuacao } from '../componentes/dominio';
import { Botao, Cartao, Carregando, Selo, Vazio, avisar, classeEntrada, tempoRelativo, useDados } from '../componentes/ui';

const TIPOS: Record<string, string> = {
  primeiro_contato: 'Primeiro contato',
  lembrete: 'Lembrete',
  acompanhamento: 'Acompanhamento',
  ultimo_contato: 'Último contato',
  conversa: 'Resposta na conversa',
};

function CartaoMensagem({ m, aoMudar }: { m: any; aoMudar: () => void }) {
  const [assunto, setAssunto] = useState(m.assunto ?? '');
  const [corpo, setCorpo] = useState(m.corpo);
  const [ocupado, setOcupado] = useState<string | null>(null);
  const r = m.revisao ?? {};
  const editada = corpo !== m.corpo || (m.assunto ?? '') !== assunto;

  const fazer = async (acao: string, fn: () => Promise<any>) => {
    setOcupado(acao);
    try {
      const res = await fn();
      if (res?.alertas?.length) avisar(`Aprovada com ${res.alertas.length} alerta(s) do revisor mantido(s)`, 'neutro');
      aoMudar();
    } catch (e) {
      avisar((e as Error).message, 'critico');
    } finally {
      setOcupado(null);
    }
  };

  return (
    <Cartao className="surgir overflow-hidden">
      <div className="flex flex-wrap items-center gap-3 border-b border-borda px-5 py-3">
        <Pontuacao valor={m.pontuacao} />
        <div className="min-w-0 flex-1">
          <Link to={`/leads/${m.lead_id}`} className="font-semibold hover:underline">
            {m.empresa}
          </Link>
          <div className="flex flex-wrap items-center gap-x-2 text-[12px] text-tinta-3">
            <span className="inline-flex items-center gap-1">
              <IconeCanal canal={m.canal} className="size-3.5" /> {m.canal === 'email' ? 'E-mail' : 'WhatsApp'} para {m.destino}
            </span>
            <span>· {TIPOS[r.tipo] ?? 'Mensagem'}</span>
            <span>· redigida {tempoRelativo(m.criado_em)}</span>
          </div>
        </div>
        {r.aprovado ? (
          <Selo tom="bom" icone={<ShieldCheck className="size-3.5" />}>
            Revisor aprovou
          </Selo>
        ) : (
          <Selo tom="serio" icone={<ShieldAlert className="size-3.5" />}>
            Revisor pediu atenção
          </Selo>
        )}
      </div>
      <div className="grid gap-5 p-5 lg:grid-cols-[1fr_300px]">
        <div className="space-y-3">
          {m.canal === 'email' && <input aria-label="Assunto" className={classeEntrada + ' font-medium'} value={assunto} onChange={(e) => setAssunto(e.target.value)} />}
          <textarea aria-label="Mensagem" className={classeEntrada + ' min-h-[220px] leading-relaxed [field-sizing:content]'} value={corpo} onChange={(e) => setCorpo(e.target.value)} />
          <p className="text-[12px] text-tinta-3">
            {m.canal === 'email' ? 'Assinatura com CNPJ/CRC e link de descadastro são adicionados automaticamente.' : 'Identificação e opção "responda PARAR" são adicionadas automaticamente no primeiro contato.'}
          </p>
        </div>
        <aside className="space-y-3 text-[13px]">
          {r.problemas?.length > 0 && (
            <div className="rounded-xl bg-serio-suave p-3">
              <p className="mb-1.5 font-medium text-serio-tinta">Apontamentos do revisor</p>
              <ul className="space-y-2">
                {r.problemas.map((p: any, i: number) => (
                  <li key={i}>
                    <span className="font-medium">“{p.trecho}”</span> — {p.regra}
                    <span className="block text-tinta-2">{p.correcao}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="rounded-xl bg-superficie-2 p-3 text-tinta-2">
            <p className="mb-1 font-medium text-tinta">Verificações</p>
            <p>{(r.etapas ?? []).map((e: string) => (e === 'regras' ? 'regras éticas' : e.startsWith('ia:') ? `IA (${e.slice(3)})` : e)).join(' → ') || '—'}</p>
            {r.fatos_usados?.length > 0 && <p className="mt-1">Fatos citados: {r.fatos_usados.join(', ')}</p>}
          </div>
        </aside>
      </div>
      <div className="flex flex-wrap justify-end gap-2 border-t border-borda bg-superficie-2/50 px-5 py-3">
        <Botao variante="fantasma" carregando={ocupado === 'rejeitar'} onClick={() => fazer('rejeitar', () => api(`/api/mensagens/${m.id}/rejeitar`, { corpo: {} }))}>
          <Trash2 className="size-4" /> Descartar
        </Botao>
        {r.tipo !== 'conversa' && (
          <Botao carregando={ocupado === 'regenerar'} onClick={() => fazer('regenerar', () => api(`/api/mensagens/${m.id}/rejeitar`, { corpo: { regenerar: true } }))}>
            <RefreshCw className="size-4" /> Reescrever
          </Botao>
        )}
        <Botao variante="primario" carregando={ocupado === 'aprovar'} onClick={() => fazer('aprovar', () => api(`/api/mensagens/${m.id}/aprovar`, { corpo: { corpo, assunto: m.canal === 'email' ? assunto : undefined } }))}>
          <CheckSquare className="size-4" /> {editada ? 'Salvar e aprovar' : 'Aprovar envio'}
        </Botao>
      </div>
    </Cartao>
  );
}

export function Aprovacao() {
  const { dados, carregando, recarregar } = useDados<any[]>('/api/mensagens/aprovacao');
  const liberadas = (dados ?? []).filter((m) => m.revisao?.aprovado);
  const [lote, setLote] = useState(false);

  return (
    <div>
      <Cabecalho
        titulo="Aprovação de mensagens"
        descricao="No modo aprovação, nenhuma mensagem sai sem o seu ok. Edite o que quiser; quando confiar nos textos, mude para o modo automático em Configurações."
        acoes={
          liberadas.length > 1 && (
            <Botao
              variante="primario"
              carregando={lote}
              onClick={async () => {
                setLote(true);
                const r = await api('/api/mensagens/aprovar-lote', { corpo: { ids: liberadas.map((m) => m.id) } });
                avisar(`${r.aprovadas} mensagens aprovadas`);
                setLote(false);
                void recarregar();
              }}
            >
              <CheckCheck className="size-4" /> Aprovar as {liberadas.length} liberadas pelo revisor
            </Botao>
          )
        }
      />
      {carregando && !dados ? (
        <Carregando />
      ) : !dados?.length ? (
        <Cartao>
          <Vazio icone={<CheckSquare className="size-5" />} titulo="Nada para aprovar" texto="As novas mensagens dos agentes aparecem aqui, já com o parecer do Revisor de Ética." />
        </Cartao>
      ) : (
        <div className="grid gap-4">
          {dados.map((m) => (
            <CartaoMensagem key={m.id} m={m} aoMudar={recarregar} />
          ))}
        </div>
      )}
    </div>
  );
}
