import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Building2, Globe, Mail, MapPin, MessageCircle, PenLine, Phone, ShieldOff, Sparkles, Users } from 'lucide-react';
import { api } from '../api';
import { Conversa } from '../componentes/Conversa';
import { descreverEvento, NOMES_AGENTE, NOMES_ETAPA, Pontuacao, SeloEtapa, SeloTemperatura } from '../componentes/dominio';
import { Botao, Campo, Cartao, Carregando, Modal, Selo, Vazio, avisar, classeEntrada, formatarCnpj, tempoRelativo, useDados } from '../componentes/ui';

const ETAPAS_MANUAIS = ['qualificada', 'proposta', 'negociacao', 'cliente', 'pausada', 'perdida', 'descartada'];

export function LeadDetalhe() {
  const { id } = useParams();
  const { dados: d, carregando, recarregar } = useDados<any>(`/api/leads/${id}`, 20_000);
  const [mover, setMover] = useState(false);
  const [destino, setDestino] = useState('proposta');
  const [nota, setNota] = useState('');
  const [redigindo, setRedigindo] = useState(false);

  if (carregando && !d) return <Carregando />;
  if (!d) return <Vazio titulo="Lead não encontrado" acao={<Link to="/leads">Voltar</Link>} />;
  const e = d.empresa;
  const canais = (['email', 'whatsapp'] as const).filter((c) => d.contatos.some((ct: any) => ct.tipo === c && !ct.bloqueado));

  return (
    <div className="space-y-5">
      <Link to="/leads" className="inline-flex items-center gap-1.5 text-[13px] text-tinta-2 hover:text-tinta">
        <ArrowLeft className="size-4" /> Leads
      </Link>

      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex items-start gap-4">
          <div className="grid size-12 shrink-0 place-items-center rounded-2xl bg-superficie-2 text-tinta-2">
            <Building2 className="size-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-[22px] font-semibold tracking-tight sm:text-[26px]">{e.nome}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[13px] text-tinta-2">
              <SeloEtapa etapa={d.lead.etapa} />
              <SeloTemperatura t={d.lead.temperatura} />
              <span className="numeros">{formatarCnpj(e.cnpj)}</span>
              {e.municipio && (
                <span className="inline-flex items-center gap-1">
                  <MapPin className="size-3.5" /> {e.municipio}/{e.uf}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Botao
            carregando={redigindo}
            onClick={async () => {
              setRedigindo(true);
              try {
                await api(`/api/leads/${id}/redigir`, { corpo: { tipo: d.mensagens.some((m: any) => m.direcao === 'saida') ? 'acompanhamento' : 'primeiro_contato', canal: canais[0] ?? 'email' } });
                avisar('Rascunho criado — veja em Aprovação');
                void recarregar();
              } catch (x) {
                avisar((x as Error).message, 'critico');
              } finally {
                setRedigindo(false);
              }
            }}
          >
            <Sparkles className="size-4" /> Pedir rascunho à IA
          </Botao>
          <Botao variante="primario" onClick={() => setMover(true)}>
            <PenLine className="size-4" /> Mover etapa
          </Botao>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_400px]">
        <div className="space-y-5">
          <Cartao titulo="Conversa" subtitulo="E-mail e WhatsApp num só lugar">
            <Conversa leadId={Number(id)} mensagens={d.mensagens} canaisDisponiveis={[...canais]} aoEnviar={recarregar} />
          </Cartao>

          <Cartao titulo="Linha do tempo" subtitulo="Trilha de auditoria de tudo o que aconteceu com este lead">
            <ol className="relative px-5 pt-3 pb-5">
              {d.eventos.map((ev: any) => (
                <li key={ev.id} className="relative border-l border-borda pb-4 pl-5 last:pb-0">
                  <span className="absolute top-1 -left-[5px] size-2.5 rounded-full border-2 border-superficie bg-tinta-3" />
                  <p className="text-[13px]">
                    <span className="font-medium">{NOMES_AGENTE[ev.agente] ?? ev.agente}</span> <span className="text-tinta-2">· {descreverEvento(ev.tipo, ev.detalhe)}</span>
                  </p>
                  <p className="text-[12px] text-tinta-3">{tempoRelativo(ev.criado_em)}</p>
                </li>
              ))}
              {!d.eventos.length && <p className="text-sm text-tinta-3">Sem eventos.</p>}
            </ol>
          </Cartao>
        </div>

        <div className="space-y-5">
          <Cartao titulo="Qualificação">
            <div className="space-y-4 px-5 pt-2 pb-5">
              <div className="flex items-center gap-4">
                <Pontuacao valor={d.lead.pontuacao} tamanho={56} />
                <div className="text-[13px] text-tinta-2">{d.lead.resumo_ia ?? 'Ainda não qualificado.'}</div>
              </div>
              {d.lead.pontuacao_motivos.length > 0 && (
                <ul className="space-y-1 text-[13px]">
                  {d.lead.pontuacao_motivos.map((m: string) => (
                    <li key={m} className="flex gap-2">
                      <span className={m.startsWith('-') ? 'text-critico-tinta' : 'text-bom-tinta'}>{m.split(' ')[0]}</span>
                      <span className="text-tinta-2">{m.split(' ').slice(1).join(' ')}</span>
                    </li>
                  ))}
                </ul>
              )}
              {d.lead.necessidades.length > 0 && (
                <div>
                  <p className="mb-1.5 text-[12px] font-medium tracking-wide text-tinta-3 uppercase">Perguntas de levantamento</p>
                  <ul className="list-disc space-y-1 pl-4 text-[13px] text-tinta-2">
                    {d.lead.necessidades.map((n: string) => (
                      <li key={n}>{n}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Cartao>

          <Cartao titulo="Empresa">
            <dl className="grid grid-cols-[110px_1fr] gap-x-3 gap-y-2 px-5 pt-2 pb-5 text-[13px]">
              <dt className="text-tinta-3">Razão social</dt>
              <dd>{e.razao_social ?? '—'}</dd>
              <dt className="text-tinta-3">Atividade</dt>
              <dd>{e.cnae_descricao ?? e.cnae_principal ?? '—'}</dd>
              <dt className="text-tinta-3">Segmento</dt>
              <dd>{e.segmento ?? '—'}</dd>
              <dt className="text-tinta-3">Abertura</dt>
              <dd className="numeros">{e.data_abertura ? new Date(e.data_abertura + 'T12:00').toLocaleDateString('pt-BR') : '—'}</dd>
              <dt className="text-tinta-3">Porte</dt>
              <dd>{e.porte ?? '—'}</dd>
              <dt className="text-tinta-3">Regime (cad.)</dt>
              <dd>{e.optante_mei ? 'MEI' : e.optante_simples === 1 ? 'Simples Nacional' : e.optante_simples === 0 ? 'Não optante do Simples' : '—'}</dd>
              <dt className="text-tinta-3">Capital</dt>
              <dd className="numeros">{e.capital_social ? e.capital_social.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL', maximumFractionDigits: 0 }) : '—'}</dd>
              {e.site && (
                <>
                  <dt className="text-tinta-3">Site</dt>
                  <dd>
                    <a href={e.site} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-acento-tinta hover:underline">
                      <Globe className="size-3.5" /> {e.site.replace(/^https?:\/\//, '')}
                    </a>
                  </dd>
                </>
              )}
              <dt className="text-tinta-3">Origem</dt>
              <dd>{e.origem_detalhe ?? e.origem}</dd>
            </dl>
            {e.site_resumo?.resumo && <p className="mx-5 mb-5 rounded-xl bg-superficie-2 p-3 text-[13px] text-tinta-2">{e.site_resumo.resumo}</p>}
          </Cartao>

          <Cartao
            titulo={
              <span className="flex items-center gap-2">
                <Users className="size-4 text-tinta-3" /> Sócios e decisores
              </span>
            }
            subtitulo="QSA público + o que o próprio lead contou na conversa"
          >
            <ul className="divide-y divide-borda px-5 pb-3">
              {d.socios.map((s: any) => (
                <li key={s.id} className="py-3 text-[13px]">
                  <p className="font-medium">{s.nome}</p>
                  <p className="text-tinta-3">{[s.qualificacao, s.faixa_etaria, s.data_entrada && `desde ${new Date(s.data_entrada + 'T12:00').toLocaleDateString('pt-BR')}`].filter(Boolean).join(' · ')}</p>
                  {s.outras_empresas.length > 0 && (
                    <p className="mt-1 text-tinta-2">
                      Participa de mais {s.outras_empresas.length} empresa(s): {s.outras_empresas.slice(0, 3).map((o: any) => o.razao_social ?? o.cnpj_basico).join(', ')}
                    </p>
                  )}
                  {s.fatos_conversa.length > 0 && (
                    <ul className="mt-1.5 space-y-0.5">
                      {s.fatos_conversa.map((f: string) => (
                        <li key={f} className="text-tinta-2">• {f}</li>
                      ))}
                    </ul>
                  )}
                  <p className="mt-1 text-[11px] text-tinta-3">Fonte: {s.origem}</p>
                </li>
              ))}
              {!d.socios.length && <p className="py-4 text-sm text-tinta-3">Sem sócios registrados.</p>}
            </ul>
          </Cartao>

          <Cartao titulo="Contatos" subtitulo="Cada contato com origem e base legal registradas">
            <ul className="divide-y divide-borda px-5 pb-3">
              {d.contatos.map((c: any) => (
                <li key={c.id} className="flex items-start gap-3 py-3 text-[13px]">
                  <span className="mt-0.5 text-tinta-3">{c.tipo === 'email' ? <Mail className="size-4" /> : c.tipo === 'whatsapp' ? <MessageCircle className="size-4" /> : <Phone className="size-4" />}</span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{c.valor}</p>
                    <p className="text-tinta-3">{c.origem}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {c.optin ? <Selo tom="bom">Autorizou contato</Selo> : <Selo>Legítimo interesse</Selo>}
                      {c.provavel_contador ? <Selo tom="alerta">Provável contador cadastral</Selo> : null}
                      {c.bloqueado ? <Selo tom="critico" icone={<ShieldOff className="size-3" />}>Bloqueado</Selo> : null}
                    </div>
                  </div>
                </li>
              ))}
              {!d.contatos.length && <p className="py-4 text-sm text-tinta-3">Nenhum contato encontrado.</p>}
            </ul>
          </Cartao>

          <Cartao titulo="Fatos que a IA pode usar" subtitulo="A IA só escreve com base nesta lista">
            <ul className="space-y-1 px-5 pt-2 pb-5 text-[12px] text-tinta-2">
              {d.fatos.map((f: string) => (
                <li key={f}>{f}</li>
              ))}
            </ul>
          </Cartao>
        </div>
      </div>

      <Modal aberto={mover} aoFechar={() => setMover(false)} titulo="Mover etapa">
        <div className="space-y-4">
          <Campo rotulo="Nova etapa">
            <select className={classeEntrada} value={destino} onChange={(x) => setDestino(x.target.value)}>
              {ETAPAS_MANUAIS.map((et) => (
                <option key={et} value={et}>
                  {NOMES_ETAPA[et]}
                </option>
              ))}
            </select>
          </Campo>
          <Campo rotulo={destino === 'cliente' ? 'Evidência do contrato formalizado (obrigatória)' : 'Motivo / observação'}>
            <textarea className={classeEntrada} rows={3} value={nota} onChange={(x) => setNota(x.target.value)} />
          </Campo>
          {['proposta', 'negociacao', 'cliente', 'perdida', 'pausada', 'descartada'].includes(destino) && (
            <p className="text-[12px] text-tinta-3">A cadência automática deste lead será interrompida.</p>
          )}
          <div className="flex justify-end gap-2">
            <Botao variante="fantasma" onClick={() => setMover(false)}>
              Cancelar
            </Botao>
            <Botao
              variante="primario"
              disabled={destino === 'cliente' && !nota.trim()}
              onClick={async () => {
                try {
                  await api(`/api/leads/${id}`, { metodo: 'PATCH', corpo: { etapa: destino, motivo: nota, evidencia: destino === 'cliente' ? nota : undefined } });
                  avisar(`Lead movido para ${NOMES_ETAPA[destino]}`);
                  setMover(false);
                  setNota('');
                  void recarregar();
                } catch (x) {
                  avisar((x as Error).message, 'critico');
                }
              }}
            >
              Mover
            </Botao>
          </div>
        </div>
      </Modal>
    </div>
  );
}
