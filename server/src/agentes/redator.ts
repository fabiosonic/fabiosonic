// Agente Redator: escreve cada mensagem especificamente para o lead, a partir dos
// fatos numerados da ficha. Toda mensagem passa pelo Revisor; se reprovada, o
// Redator reescreve uma vez com os apontamentos. Persistindo o problema, a
// mensagem fica na fila de aprovação para você decidir.
import { executar, json, todos, um } from '../banco.ts';
import { lerConfiguracoes } from '../configuracoes.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { log, registrarEvento } from '../registro.ts';
import { agoraSql } from '../util/tempo.ts';
import { carregarFicha, destinatario, montarFatos, type Ficha } from './ficha.ts';
import { contextoEscritorio, INSTRUCOES } from './instrucoes.ts';
import { revisar, type Parecer } from './revisor.ts';

const AGENTE = 'redator';

export type TipoMensagem = 'primeiro_contato' | 'lembrete' | 'acompanhamento' | 'ultimo_contato';

const OBJETIVO: Record<TipoMensagem, string> = {
  primeiro_contato: 'Primeira abordagem: apresente o escritório em 1 frase ligada a um fato da empresa e faça uma pergunta aberta sobre a necessidade.',
  lembrete: 'Lembrete curto por outro canal, referindo-se ao e-mail anterior sem cobrar resposta; traga um ângulo novo.',
  acompanhamento: 'Acompanhamento com informação útil e diferente das anteriores (uma das perguntas de levantamento), sem pressão.',
  ultimo_contato: 'Último contato: agradeça, diga que não vai insistir e deixe a porta aberta. Muito curto.',
};

/** Escolhe o contato do canal respeitando bloqueios, contador cadastral e opt-in. */
export function escolherContato(f: Ficha, canal: 'email' | 'whatsapp', exigirOptinWhatsapp: boolean) {
  const candidatos = f.contatos.filter((c) => c.tipo === canal && !c.bloqueado && !c.provavel_contador && !um('SELECT 1 FROM bloqueios WHERE valor = ?', c.valor));
  if (canal === 'whatsapp' && exigirOptinWhatsapp) {
    const jaConversou = um("SELECT 1 FROM mensagens WHERE lead_id = ? AND canal = 'whatsapp' AND direcao = 'entrada'", f.lead.id);
    return candidatos.find((c) => c.optin || jaConversou) ?? null;
  }
  // Preferência: contato ligado a sócio > e-mail do site > cadastro
  return candidatos.sort((a, b) => Number(Boolean(b.socio_id)) - Number(Boolean(a.socio_id)) || Number(/^Site/.test(b.origem)) - Number(/^Site/.test(a.origem)))[0] ?? null;
}

type Rascunho = { assunto: string; corpo_email: string; whatsapp: string; fatos_usados: string[] };

async function pedirRascunho(f: Ficha, fatos: string[], tipo: TipoMensagem, canal: 'email' | 'whatsapp', ajustes?: Parecer) {
  const c = lerConfiguracoes();
  const anteriores = todos<{ canal: string; corpo: string; direcao: string }>(
    'SELECT canal, corpo, direcao FROM mensagens WHERE lead_id = ? AND status NOT IN (\'descartada\') ORDER BY criado_em DESC LIMIT 4',
    f.lead.id,
  );
  const d = destinatario(f);
  const pedido = [
    contextoEscritorio(c),
    '',
    'FATOS (use somente estes):',
    ...fatos,
    '',
    `Perguntas de levantamento sugeridas: ${json<string[]>(f.lead.necessidades, []).join(' | ') || 'nenhuma'}`,
    f.lead.resumo_ia ? `Análise da qualificação: ${f.lead.resumo_ia}` : '',
    `Destinatário: ${d ? 'use o primeiro nome indicado nos fatos' : 'nome desconhecido — use saudação neutra como "Olá, tudo bem?"'}`,
    `Canal principal desta etapa: ${canal}. Objetivo: ${OBJETIVO[tipo]}`,
    anteriores.length ? `Mensagens anteriores (não repita):\n${anteriores.map((m) => `- (${m.direcao}/${m.canal}) ${m.corpo.slice(0, 280)}`).join('\n')}` : '',
    ajustes ? `CORRIJA estes problemas apontados pelo revisor:\n${ajustes.problemas.map((p) => `- "${p.trecho}": ${p.regra} → ${p.correcao}`).join('\n')}` : '',
  ]
    .filter(Boolean)
    .join('\n');
  return perguntarJson<Rascunho>({ tarefa: 'redacao', sistema: INSTRUCOES.redator, usuario: pedido, dadosPessoais: true, temperatura: 0.7 });
}

export function fatosInexistentes(usados: string[], fatos: string[]) {
  const ids = new Set(fatos.map((f) => f.match(/^\[(F\d+)\]/)?.[1]));
  return (usados ?? []).map((u) => String(u).replace(/[[\]]/g, '')).filter((u) => !ids.has(u));
}

export async function redigirMensagem(leadId: number, tipo: TipoMensagem, canalPreferido: 'email' | 'whatsapp'): Promise<number | null> {
  const f = carregarFicha(leadId);
  if (!f) return null;
  const c = lerConfiguracoes();
  let canal = canalPreferido;
  let contato = escolherContato(f, canal, c.whatsapp.primeiro_contato_somente_optin);
  if (!contato) {
    canal = canal === 'email' ? 'whatsapp' : 'email';
    contato = escolherContato(f, canal, c.whatsapp.primeiro_contato_somente_optin);
  }
  if (!contato) {
    registrarEvento(leadId, 'sem_canal', AGENTE, { tipo, motivo: 'Nenhum contato utilizável (bloqueado, do contador cadastral ou sem opt-in no WhatsApp)' });
    return null;
  }

  const fatos = montarFatos(f);
  let rascunho = await pedirRascunho(f, fatos, tipo, canal);
  const corpoDe = (r: Rascunho) => (canal === 'email' ? r.corpo_email : r.whatsapp) ?? '';
  let parecer = await avaliar(canal, rascunho, fatos, corpoDe);
  if (!parecer.aprovado) {
    rascunho = await pedirRascunho(f, fatos, tipo, canal, parecer);
    parecer = await avaliar(canal, rascunho, fatos, corpoDe);
  }

  const automatico = c.autonomia.modo === 'automatico' && parecer.aprovado;
  const { id } = executar(
    `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, assunto, corpo, status, agente, revisao, agendada_para)
     VALUES (?, ?, ?, 'saida', ?, ?, ?, ?, ?, ?)`,
    leadId,
    contato.id,
    canal,
    canal === 'email' ? rascunho.assunto : null,
    corpoDe(rascunho).trim(),
    automatico ? 'aprovada' : 'aguardando_aprovacao',
    AGENTE,
    JSON.stringify({ ...parecer, tipo, fatos_usados: rascunho.fatos_usados, provedor: (rascunho as any)._provedor, whatsapp_alternativo: rascunho.whatsapp }),
    agoraSql(),
  );
  registrarEvento(leadId, 'mensagem_redigida', AGENTE, { mensagemId: id, canal, tipo, aprovadoPeloRevisor: parecer.aprovado, envioAutomatico: automatico });
  log(AGENTE, `lead ${leadId}: ${tipo} por ${canal} → ${automatico ? 'fila de envio' : 'aguardando sua aprovação'}`);
  return id;
}

async function avaliar(canal: 'email' | 'whatsapp', r: Rascunho, fatos: string[], corpoDe: (r: Rascunho) => string): Promise<Parecer> {
  const corpo = corpoDe(r);
  if (!corpo.trim()) return { aprovado: false, problemas: [{ trecho: '(vazio)', regra: 'Mensagem vazia', correcao: 'Gerar novamente' }], etapas: ['formato'] };
  const inexistentes = fatosInexistentes(r.fatos_usados, fatos);
  if (inexistentes.length) {
    return { aprovado: false, problemas: [{ trecho: inexistentes.join(', '), regra: 'Cita fato que não existe na ficha', correcao: 'Use somente os fatos fornecidos' }], etapas: ['fatos'] };
  }
  try {
    return await revisar(canal, canal === 'email' ? r.assunto : null, corpo, fatos);
  } catch (e) {
    return { aprovado: false, problemas: [{ trecho: '-', regra: 'Revisão por IA indisponível no momento', correcao: `Revise manualmente (${(e as Error).message.slice(0, 120)})` }], etapas: ['regras'] };
  }
}
