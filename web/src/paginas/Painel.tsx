import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, Bell, Building2, CheckCircle2, Cpu, MessageSquareReply, Send, Sparkles, UserCheck } from 'lucide-react';
import { Cabecalho } from '../componentes/Estrutura';
import { descreverEvento, NOMES_AGENTE, NOMES_ETAPA } from '../componentes/dominio';
import { BarrasHorizontais, GraficoAtividade, GraficoFunil } from '../componentes/graficos';
import { Cartao, Carregando, Indicador, Selo, Vazio, cx, tempoRelativo, useDados } from '../componentes/ui';

const ETAPAS_FUNIL = ['mapeada', 'enriquecida', 'qualificada', 'em_contato', 'respondeu', 'com_voce', 'proposta', 'negociacao', 'cliente'];

function saudacao() {
  const h = Number(new Intl.DateTimeFormat('pt-BR', { hour: 'numeric', hour12: false, timeZone: 'America/Sao_Paulo' }).format(new Date()));
  return h < 12 ? 'Bom dia' : h < 18 ? 'Boa tarde' : 'Boa noite';
}

export function Painel() {
  const { dados: d, carregando } = useDados<any>('/api/painel', 30_000);
  if (carregando && !d) return <Carregando />;
  if (!d) return <Vazio titulo="Não foi possível carregar o painel" />;
  const i = d.indicadores;
  const ativos = ['mapeada', 'enriquecida', 'qualificada', 'em_contato', 'respondeu', 'com_voce', 'proposta', 'negociacao'].reduce((s, e) => s + (i.porEtapa[e] ?? 0), 0);
  const avisosConfig: string[] = [];
  if (!d.canais.email) avisosConfig.push('e-mail (SMTP)');
  if (!d.canais.whatsapp) avisosConfig.push('WhatsApp');
  if (!d.provedores.length && !d.iaSimulada) avisosConfig.push('provedores de IA');

  return (
    <div className="space-y-6">
      <Cabecalho
        titulo={`${saudacao()}!`}
        descricao={
          d.atendimentos.length
            ? `${d.atendimentos.length} lead${d.atendimentos.length > 1 ? 's querem' : ' quer'} falar com você. O resto da operação segue com os agentes.`
            : 'Nada precisa de você agora. Os agentes estão cuidando da prospecção e das conversas.'
        }
        acoes={
          <Link to="/leads?novo=1" className="inline-flex h-9 items-center gap-1.5 rounded-[10px] bg-tinta px-3.5 text-sm font-medium text-fundo hover:opacity-90">
            <Building2 className="size-4" /> Novo lead
          </Link>
        }
      />

      {(d.pendenciasIdentificacao.length > 0 || avisosConfig.length > 0) && (
        <div className="cartao flex flex-col gap-3 border-alerta/40 bg-alerta-suave/40 p-4 sm:flex-row sm:items-center">
          <AlertTriangle className="size-5 shrink-0 text-alerta-tinta" />
          <div className="flex-1 text-sm">
            {d.pendenciasIdentificacao.length > 0 && (
              <p>
                <span className="font-medium">Identificação incompleta:</span> {d.pendenciasIdentificacao.join(', ')}. A NBC PG 01 exige identificação profissional nas peças; os envios de prospecção ficam suspensos até completar.
              </p>
            )}
            {avisosConfig.length > 0 && (
              <p className={cx(d.pendenciasIdentificacao.length > 0 && 'mt-1')}>
                <span className="font-medium">Integrações pendentes:</span> {avisosConfig.join(', ')}.
              </p>
            )}
          </div>
          <Link to="/configuracoes" className="text-sm font-medium text-acento-tinta hover:underline">
            Completar configuração
          </Link>
        </div>
      )}

      {d.atendimentos.length > 0 && (
        <Cartao
          className="ring-1 ring-alerta/50"
          titulo={
            <span className="flex items-center gap-2">
              <Bell className="size-4 text-alerta-tinta" /> Precisa de você
            </span>
          }
          subtitulo="O sistema só chama quando o lead quer falar, pergunta preço ou traz dúvida técnica."
          acao={
            <Link to="/com-voce" className="text-[13px] font-medium text-acento-tinta hover:underline">
              Ver todos
            </Link>
          }
        >
          <ul className="divide-y divide-borda">
            {d.atendimentos.map((a: any) => (
              <li key={a.id}>
                <Link to={`/leads/${a.lead_id}`} className="flex items-center gap-3 px-5 py-3 hover:bg-superficie-2/60">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{a.empresa}</span>
                      <Selo tom="alerta">{a.rotulo}</Selo>
                    </div>
                    <p className="mt-0.5 line-clamp-1 text-[13px] text-tinta-2">{a.resumo}</p>
                  </div>
                  <span className="shrink-0 text-[12px] text-tinta-3">{tempoRelativo(a.criado_em)}</span>
                  <ArrowRight className="size-4 shrink-0 text-tinta-3" />
                </Link>
              </li>
            ))}
          </ul>
        </Cartao>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        <Indicador rotulo="Leads ativos" icone={<Building2 className="size-4" />} valor={<span className="numeros">{ativos}</span>} detalhe={`${i.hoje.novosLeads} novos hoje · ${i.novos} em 30 dias`} />
        <Indicador rotulo="Empresas contatadas" icone={<Send className="size-4" />} valor={<span className="numeros">{i.contatados}</span>} detalhe={`${i.hoje.enviadas} mensagens hoje · 30 dias`} />
        <Indicador
          rotulo="Taxa de resposta"
          icone={<MessageSquareReply className="size-4" />}
          valor={i.taxaResposta === null ? <span className="text-tinta-3">n/c</span> : <span className="numeros">{i.taxaResposta.toLocaleString('pt-BR')}%</span>}
          detalhe={i.taxaResposta === null ? 'Sem contatos no período' : `${i.responderam} de ${i.contatados} responderam`}
        />
        <Indicador rotulo="Novos clientes" icone={<UserCheck className="size-4" />} valor={<span className="numeros">{i.clientes}</span>} detalhe={`${i.chamaramVoce} conversas com você · 30 dias`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <Cartao className="xl:col-span-2" titulo="Atividade dos últimos 30 dias" subtitulo="Mensagens enviadas pelos agentes e respostas recebidas por dia">
          <GraficoAtividade serie={i.serie} />
          <div className="h-3" />
        </Cartao>
        <Cartao titulo="Funil comercial" subtitulo="Leads por etapa agora">
          <GraficoFunil etapas={ETAPAS_FUNIL.map((e) => ({ id: e, nome: NOMES_ETAPA[e], valor: i.porEtapa[e] ?? 0 }))} />
        </Cartao>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Cartao
          titulo={
            <span className="flex items-center gap-2">
              <Sparkles className="size-4 text-acento" /> Briefing do Diretor Comercial
            </span>
          }
          subtitulo={d.briefing ? `Gerado ${tempoRelativo(d.briefing.criadoEm)}` : 'Gerado todo dia às 7h30'}
        >
          <div className="px-5 pt-2 pb-5 text-sm leading-relaxed whitespace-pre-line text-tinta-2">{d.briefing?.texto || 'O primeiro briefing será gerado amanhã cedo. Você pode pedir um agora na página Agentes.'}</div>
        </Cartao>

        <Cartao
          titulo="Equipe de agentes"
          acao={
            <Link to="/agentes" className="text-[13px] font-medium text-acento-tinta hover:underline">
              Detalhes
            </Link>
          }
        >
          <ul className="grid grid-cols-1 gap-0.5 px-3 pt-1 pb-4">
            {d.agentes.map((a: any) => {
              const falhou = a.ultimaExecucao && a.ultimaExecucao.sucesso === 0;
              return (
                <li key={a.id} className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-[13px]">
                  <span className={cx('size-2 shrink-0 rounded-full', a.rodando ? 'bg-acento pulsando' : falhou ? 'bg-critico' : a.ultimaExecucao ? 'bg-bom' : 'bg-superficie-3')} />
                  <span className="flex-1 font-medium">{a.nome}</span>
                  <span className="truncate text-tinta-3">{a.rodando ? 'trabalhando…' : a.ultimaExecucao ? tempoRelativo(a.ultimaExecucao.inicio) : 'sob demanda'}</span>
                </li>
              );
            })}
          </ul>
        </Cartao>

        <Cartao
          titulo="Leads por segmento"
          subtitulo="Total mapeado e quantos passaram da qualificação"
        >
          {i.porSegmento.length ? (
            <BarrasHorizontais itens={i.porSegmento.map((s: any) => ({ rotulo: s.segmento, valor: s.n, detalhe: `· ${s.qualificados} qualif.` }))} />
          ) : (
            <Vazio titulo="Sem leads ainda" />
          )}
        </Cartao>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Cartao className="lg:col-span-2" titulo="Atividade recente" subtitulo="Tudo o que os agentes e você fizeram, com registro">
          <ul className="px-5 pt-2 pb-4">
            {d.atividade.map((e: any) => (
              <li key={e.id} className="flex gap-3 border-b border-borda py-2.5 text-[13px] last:border-0">
                <span className="w-24 shrink-0 text-tinta-3">{tempoRelativo(e.criado_em)}</span>
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{NOMES_AGENTE[e.agente] ?? e.agente}</span>
                  <span className="text-tinta-2"> · {descreverEvento(e.tipo, e.detalhe)}</span>
                  {e.empresa && (
                    <Link to={`/leads/${e.lead_id}`} className="text-acento-tinta hover:underline">
                      {' '}
                      — {e.empresa}
                    </Link>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </Cartao>
        <Cartao
          titulo={
            <span className="flex items-center gap-2">
              <Cpu className="size-4 text-tinta-3" /> IA em uso
            </span>
          }
          acao={
            <Link to="/ia" className="text-[13px] font-medium text-acento-tinta hover:underline">
              Rodízio
            </Link>
          }
        >
          {d.iaSimulada ? (
            <p className="px-5 pt-2 pb-5 text-sm text-tinta-2">Modo de demonstração com IA simulada. Configure as chaves gratuitas no .env para ativar o rodízio real.</p>
          ) : d.provedores.length ? (
            <ul className="px-5 pt-2 pb-4">
              {d.provedores.map((p: any) => (
                <li key={p.id} className="flex items-center gap-2 py-1.5 text-[13px]">
                  {p.pausado ? <AlertTriangle className="size-4 text-alerta-tinta" /> : <CheckCircle2 className="size-4 text-bom-tinta" />}
                  <span className="flex-1 font-medium">{p.nome}</span>
                  <span className="numeros text-tinta-3">{p.pausado ? p.motivo : `${p.chamadasHoje}${p.limiteDiario ? `/${p.limiteDiario}` : ''} hoje`}</span>
                </li>
              ))}
            </ul>
          ) : (
            <Vazio titulo="Nenhum provedor configurado" texto="Defina ao menos uma chave gratuita (ex.: GROQ_API_KEY) no .env." />
          )}
        </Cartao>
      </div>
    </div>
  );
}
