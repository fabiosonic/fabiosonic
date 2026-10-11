import { AlertCircle, CheckCircle2, Mail, MessageCircle, Pause, Snowflake, Flame, Thermometer, XCircle } from 'lucide-react';
import { Selo, cx } from './ui';

export const NOMES_ETAPA: Record<string, string> = {
  mapeada: 'Mapeada',
  enriquecida: 'Enriquecida',
  qualificada: 'Qualificada',
  em_contato: 'Em contato',
  respondeu: 'Respondeu',
  com_voce: 'Com você',
  proposta: 'Proposta',
  negociacao: 'Negociação',
  cliente: 'Cliente',
  pausada: 'Pausada',
  descartada: 'Descartada',
  perdida: 'Perdida',
};

export function SeloEtapa({ etapa }: { etapa: string }) {
  const nome = NOMES_ETAPA[etapa] ?? etapa;
  if (etapa === 'com_voce') return <Selo tom="alerta" icone={<AlertCircle className="size-3.5" />}>{nome}</Selo>;
  if (etapa === 'cliente') return <Selo tom="bom" icone={<CheckCircle2 className="size-3.5" />}>{nome}</Selo>;
  if (etapa === 'perdida' || etapa === 'descartada') return <Selo tom="neutro" icone={<XCircle className="size-3.5" />}>{nome}</Selo>;
  if (etapa === 'pausada') return <Selo tom="neutro" icone={<Pause className="size-3.5" />}>{nome}</Selo>;
  if (['respondeu', 'proposta', 'negociacao'].includes(etapa)) return <Selo tom="acento">{nome}</Selo>;
  return <Selo tom="neutro">{nome}</Selo>;
}

export function SeloTemperatura({ t }: { t: string | null }) {
  if (!t) return null;
  if (t === 'quente') return <Selo tom="serio" icone={<Flame className="size-3.5" />}>Quente</Selo>;
  if (t === 'morna') return <Selo tom="alerta" icone={<Thermometer className="size-3.5" />}>Morna</Selo>;
  return <Selo tom="neutro" icone={<Snowflake className="size-3.5" />}>Fria</Selo>;
}

/** Anel de pontuação 0–100 (cor única; o número carrega o valor). */
export function Pontuacao({ valor, tamanho = 36 }: { valor: number | null; tamanho?: number }) {
  if (valor === null || valor === undefined) return <span className="text-[13px] text-tinta-3">—</span>;
  const r = tamanho / 2 - 3;
  const c = 2 * Math.PI * r;
  return (
    <span className="relative inline-grid place-items-center" style={{ width: tamanho, height: tamanho }} title={`Pontuação ${valor}/100`}>
      <svg width={tamanho} height={tamanho} className="-rotate-90">
        <circle cx={tamanho / 2} cy={tamanho / 2} r={r} fill="none" stroke="var(--superficie-3)" strokeWidth="3" />
        <circle cx={tamanho / 2} cy={tamanho / 2} r={r} fill="none" stroke="var(--acento)" strokeWidth="3" strokeLinecap="round" strokeDasharray={`${(valor / 100) * c} ${c}`} />
      </svg>
      <span className="numeros absolute text-[11px] font-semibold">{valor}</span>
    </span>
  );
}

export function IconeCanal({ canal, className }: { canal: string; className?: string }) {
  return canal === 'whatsapp' ? <MessageCircle className={cx('size-4', className)} aria-label="WhatsApp" /> : <Mail className={cx('size-4', className)} aria-label="E-mail" />;
}

export const NOMES_INTENCAO: Record<string, string> = {
  interesse: 'Interesse',
  quer_humano: 'Quer falar com você',
  preco: 'Perguntou preço',
  tecnico: 'Dúvida técnica',
  reuniao: 'Aceitou conversar',
  nao_interessado: 'Sem interesse',
  descadastro: 'Pediu para parar',
  ja_tem_contador: 'Já tem contador',
  ausencia: 'Resposta automática',
  duvida_geral: 'Dúvida geral',
  outro: 'Outro',
};

export const NOMES_STATUS_MSG: Record<string, string> = {
  aguardando_aprovacao: 'Aguardando aprovação',
  aprovada: 'Na fila de envio',
  enviada: 'Enviada',
  entregue: 'Entregue',
  lida: 'Lida',
  falhou: 'Falhou',
  bloqueada: 'Bloqueada',
  descartada: 'Descartada',
  recebida: 'Recebida',
  processando: 'Processando',
  processada: 'Recebida',
};

export const NOMES_AGENTE: Record<string, string> = {
  diretor: 'Diretor Comercial',
  prospector: 'Prospector',
  enriquecedor: 'Enriquecedor',
  qualificador: 'Qualificador',
  redator: 'Redator',
  revisor: 'Revisor de Ética',
  acompanhamento: 'Acompanhamento',
  disparador: 'Disparador',
  caixa: 'Caixa de Entrada',
  atendente: 'Atendente',
  operacoes: 'Operações',
  humano: 'Você',
};

export function descreverEvento(tipo: string, d: any): string {
  switch (tipo) {
    case 'mudanca_etapa':
      return `${NOMES_ETAPA[d?.de] ?? d?.de ?? '—'} → ${NOMES_ETAPA[d?.para] ?? d?.para}${d?.motivo ? ` · ${d.motivo}` : ''}`;
    case 'enriquecimento':
      return `Ficha enriquecida${d?.fontes?.length ? ` (${d.fontes.join(', ')})` : ''}`;
    case 'qualificacao':
      return `Qualificada com ${d?.pontos ?? '—'} pontos`;
    case 'mensagem_redigida':
      return `Mensagem redigida${d?.canal ? ` por ${d.canal === 'email' ? 'e-mail' : 'WhatsApp'}` : ''}${d?.aprovadoPeloRevisor === false ? ' — revisor pediu ajustes' : ''}`;
    case 'mensagem_enviada':
      return `Mensagem enviada${d?.canal ? ` por ${d.canal === 'email' ? 'e-mail' : 'WhatsApp'}` : ''}`;
    case 'mensagem_recebida':
      return 'Resposta recebida';
    case 'intencao':
      return `Intenção: ${NOMES_INTENCAO[d?.intencao] ?? d?.intencao}`;
    case 'chamou_voce':
      return 'Chamou você';
    case 'mensagem_aprovada':
      return d?.editada ? 'Você editou e aprovou a mensagem' : 'Você aprovou a mensagem';
    case 'mensagem_rejeitada':
      return 'Você rejeitou a mensagem';
    case 'descadastro':
      return 'Pediu descadastro';
    case 'sem_canal':
      return 'Sem canal de contato utilizável';
    case 'fatos_conversa':
      return `Novos fatos da conversa: ${(d?.fatos ?? []).join('; ')}`;
    case 'lead_receptivo':
      return 'Novo lead chegou pelo WhatsApp';
    case 'lead_criado':
      return `Lead cadastrado (${d?.origem ?? '—'})`;
    case 'cadencia':
      return `Cadência: passo ${d?.passo ?? '—'}`;
    case 'atendimento_resolvido':
      return 'Atendimento resolvido';
    case 'atendimento_assumido':
      return 'Você assumiu o atendimento';
    case 'resposta_redigida':
      return 'Resposta da conversa redigida';
    case 'mensagem_manual':
      return 'Você escreveu uma mensagem';
    default:
      return tipo.replace(/_/g, ' ');
  }
}
