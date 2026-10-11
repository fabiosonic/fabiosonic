// Agente Atendente (SDR): recebe as respostas dos leads por e-mail e WhatsApp,
// classifica a intenção, conduz a conversa inicial e entrega para você quando o
// lead pede uma pessoa, pergunta preço, traz dúvida técnica ou aceita reunião.
import { config } from '../config.ts';
import { executar, todos, um } from '../banco.ts';
import { lerConfiguracoes } from '../configuracoes.ts';
import { agendarProximaAcao, mudarEtapa } from '../funil.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { avisarResponsavel } from '../notificar.ts';
import { log, registrarEvento } from '../registro.ts';
import { agoraSql, daquiSql, DIA_MS } from '../util/tempo.ts';
import { cnpjValido, normalizarTelefone, primeiroNome, somenteDigitos, textoNovoDaResposta } from '../util/texto.ts';
import { adicionarContato, enriquecerLead, registrarFatosDaConversa } from './enriquecedor.ts';
import { carregarFicha, destinatario, montarFatos, nomeEmpresa } from './ficha.ts';
import { contextoEscritorio, INSTRUCOES } from './instrucoes.ts';
import { revisar } from './revisor.ts';

const AGENTE = 'atendente';

export type Intencao =
  | 'interesse' | 'quer_humano' | 'preco' | 'tecnico' | 'reuniao' | 'nao_interessado'
  | 'descadastro' | 'ja_tem_contador' | 'ausencia' | 'duvida_geral' | 'outro';

export const INTENCOES_QUE_CHAMAM_VOCE: Intencao[] = ['quer_humano', 'preco', 'tecnico', 'reuniao'];

/** Regras rápidas e previsíveis antes da IA; cobrem os casos que não podem falhar. */
export function intencaoPorRegras(texto: string): Intencao | null {
  const t = texto.toLowerCase().normalize('NFD').replace(/\p{M}/gu, '');
  if (/^\s*(parar|pare|sair|stop|remover|cancelar)\s*[.!]*\s*$/.test(t) || /(nao (quero|desejo) (mais )?receber|me (tire|remova|exclua)|descadastr|parem de (me )?(mandar|enviar)|nao me (mande|envie))/.test(t)) return 'descadastro';
  if (/(resposta automatica|estou (fora|de ferias|ausente)|out of office|retorno no dia)/.test(t)) return 'ausencia';
  if (/(quanto (custa|cobra|fica|sai|e)|qual (o )?(valor|preco)|preco|valores|honorario|orcamento|mensalidade|tabela de)/.test(t)) return 'preco';
  if (/(falar com (alguem|uma pessoa|um humano|o contador|a contadora|o responsavel|voces)|me (liga|ligue)|pode(m)? (me )?ligar|atendente humano)/.test(t)) return 'quer_humano';
  if (/(agendar|marcar|reuniao|uma call|videochamada|visita|podemos conversar|vamos conversar|tenho interesse em conversar)/.test(t)) return 'reuniao';
  if (/(ja tenho contador|ja temos contador|ja tenho contabilidade|ja temos (um )?escritorio)/.test(t)) return 'ja_tem_contador';
  if (/^(nao,? obrigad|sem interesse|nao tenho interesse|nao temos interesse|nao preciso)/.test(t.trim())) return 'nao_interessado';
  return null;
}

const variantesTelefone = (e164: string) => {
  const v = new Set([e164]);
  if (e164.length === 13 && e164[4] === '9') v.add(e164.slice(0, 4) + e164.slice(5));
  if (e164.length === 12) v.add(e164.slice(0, 4) + '9' + e164.slice(4));
  return [...v];
};

export type Entrada = {
  canal: 'email' | 'whatsapp';
  de: string;
  texto: string;
  idExterno: string;
  assunto?: string;
  nome?: string | null;
  emRespostaA?: string | null;
  referencias?: string[];
};

/** Registra uma mensagem recebida, ligando-a ao lead certo. Retorna o id da mensagem ou null. */
export function registrarEntrada(e: Entrada): number | null {
  if (e.idExterno && um('SELECT 1 FROM mensagens WHERE id_externo = ? AND direcao = ?', e.idExterno, 'entrada')) return null;
  const texto = e.canal === 'email' ? textoNovoDaResposta(e.texto) : e.texto.trim();
  if (!texto) return null;

  let leadId: number | null = null;
  let contatoId: number | null = null;
  // 1) resposta a uma mensagem nossa
  for (const ref of [e.emRespostaA, ...(e.referencias ?? [])].filter(Boolean)) {
    const m = um<{ lead_id: number; contato_id: number }>("SELECT lead_id, contato_id FROM mensagens WHERE id_externo = ? AND direcao = 'saida'", ref);
    if (m) {
      leadId = m.lead_id;
      contatoId = m.contato_id;
      break;
    }
  }
  // 2) pelo endereço/número do remetente
  if (!leadId) {
    const valores = e.canal === 'whatsapp' ? variantesTelefone(normalizarTelefone(e.de) ?? somenteDigitos(e.de)) : [e.de.toLowerCase()];
    const c = um<{ id: number; empresa_id: number }>(
      `SELECT id, empresa_id FROM contatos WHERE tipo = ? AND valor IN (${valores.map(() => '?').join(',')}) ORDER BY id DESC LIMIT 1`,
      e.canal,
      ...valores,
    );
    if (c) {
      contatoId = c.id;
      leadId = um<{ id: number }>('SELECT id FROM leads WHERE empresa_id = ?', c.empresa_id)?.id ?? null;
    }
  }
  // 3) WhatsApp de quem ainda não conhecemos: é um lead que chegou sozinho (captação receptiva)
  if (!leadId && e.canal === 'whatsapp') {
    const numero = normalizarTelefone(e.de) ?? somenteDigitos(e.de);
    const empresa = executar(
      "INSERT INTO empresas (cnpj, nome_fantasia, origem, origem_detalhe) VALUES (?, ?, 'whatsapp_receptivo', ?)",
      `pendente-${numero}`,
      e.nome ? `Contato de ${e.nome}` : `Contato ${numero}`,
      'Mensagem recebida no WhatsApp do escritório',
    );
    leadId = executar("INSERT INTO leads (empresa_id, etapa, temperatura) VALUES (?, 'respondeu', 'quente')", empresa.id).id;
    adicionarContato(empresa.id, 'whatsapp', numero, 'Iniciou conversa no WhatsApp do escritório', { optin: true });
    contatoId = um<{ id: number }>("SELECT id FROM contatos WHERE empresa_id = ? AND tipo = 'whatsapp'", empresa.id)?.id ?? null;
    registrarEvento(leadId, 'lead_receptivo', AGENTE, { canal: 'whatsapp', nome: e.nome });
  }
  if (!leadId) {
    registrarEvento(null, 'entrada_sem_lead', AGENTE, { canal: e.canal, de: e.de.replace(/(.{3}).+(@.+)?/, '$1***$2') });
    return null;
  }
  // Quem responde no WhatsApp passa a ter conversa ativa com o escritório
  if (e.canal === 'whatsapp' && contatoId) executar('UPDATE contatos SET optin = 1 WHERE id = ?', contatoId);

  const { id } = executar(
    `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, assunto, corpo, status, id_externo, em_resposta_a, enviada_em)
     VALUES (?, ?, ?, 'entrada', ?, ?, 'recebida', ?, ?, ?)`,
    leadId, contatoId, e.canal, e.assunto ?? null, texto, e.idExterno, e.emRespostaA ?? null, agoraSql(),
  );
  registrarEvento(leadId, 'mensagem_recebida', AGENTE, { mensagemId: id, canal: e.canal });
  return id;
}

const RESPOSTAS_FIXAS: Partial<Record<Intencao, (nome: string, resp: string) => string>> = {
  preco: (n, r) => `Obrigado pelo interesse${n ? `, ${n}` : ''}! Valores e condições quem apresenta é ${r}, que vai falar com você pessoalmente em breve. Qual o melhor horário para esse contato?`,
  tecnico: (n, r) => `Boa pergunta${n ? `, ${n}` : ''}. Para responder com a segurança que o assunto pede, vou encaminhar para ${r}, que retorna com você em breve.`,
  quer_humano: (n, r) => `Claro${n ? `, ${n}` : ''}! Já avisei ${r}, que vai falar com você em breve. Prefere continuar por aqui ou por ligação?`,
  reuniao: (n, r) => `Perfeito${n ? `, ${n}` : ''}! Já avisei ${r} para combinar o melhor dia e horário com você.`,
  descadastro: () => 'Entendido. Registramos sua preferência e não enviaremos novos contatos comerciais. Obrigado pelo retorno.',
  nao_interessado: (n) => `Sem problemas${n ? `, ${n}` : ''}, obrigado pelo retorno! Não vamos insistir. Se um dia precisar, é só chamar.`,
  ja_tem_contador: (n) => `Que bom${n ? `, ${n}` : ''}, obrigado por responder! Não vamos insistir. Se um dia quiser uma conversa, estamos à disposição.`,
};

function enfileirarResposta(leadId: number, contatoId: number | null, canal: 'email' | 'whatsapp', corpo: string, assunto: string | null, emRespostaA: string | null, status: string, revisao: unknown) {
  return executar(
    `INSERT INTO mensagens (lead_id, contato_id, canal, direcao, assunto, corpo, status, agente, revisao, em_resposta_a, agendada_para)
     VALUES (?, ?, ?, 'saida', ?, ?, ?, ?, ?, ?, ?)`,
    leadId, contatoId, canal, assunto, corpo, status, AGENTE, JSON.stringify(revisao), emRespostaA, agoraSql(),
  ).id;
}

export async function abrirAtendimentoHumano(leadId: number, motivo: string, resumo: string, mensagemId: number | null) {
  const aberto = um<{ id: number }>("SELECT id FROM atendimentos_humanos WHERE lead_id = ? AND status <> 'resolvido'", leadId);
  if (aberto) return aberto.id;
  const { id } = executar('INSERT INTO atendimentos_humanos (lead_id, motivo, resumo, mensagem_id) VALUES (?, ?, ?, ?)', leadId, motivo, resumo, mensagemId);
  mudarEtapa(leadId, 'com_voce', AGENTE, `Motivo: ${motivo}`);
  agendarProximaAcao(leadId, 'aguardando_voce', null);
  const f = carregarFicha(leadId);
  const titulo = `${f ? nomeEmpresa(f.empresa) : 'Lead'} quer falar com você (${ROTULO_MOTIVO[motivo] ?? motivo})`;
  const canais = await avisarResponsavel(titulo, resumo, `${config.urlPublica}/leads/${leadId}`);
  executar('UPDATE atendimentos_humanos SET notificado = ? WHERE id = ?', canais.length > 0, id);
  registrarEvento(leadId, 'chamou_voce', AGENTE, { motivo, avisadoPor: canais });
  return id;
}

export const ROTULO_MOTIVO: Record<string, string> = {
  preco: 'pediu preço', tecnico: 'dúvida técnica', quer_humano: 'quer falar com uma pessoa', reuniao: 'aceitou conversar',
  limite_conversa: 'conversa longa — assuma', ia_indisponivel: 'IA indisponível', outro: 'precisa de análise',
};

export async function processarEntrada(mensagemId: number) {
  const m = um<Record<string, any>>("SELECT * FROM mensagens WHERE id = ? AND direcao = 'entrada'", mensagemId);
  if (!m || m.status !== 'recebida') return;
  executar("UPDATE mensagens SET status = 'processando' WHERE id = ?", mensagemId);
  const leadId: number = m.lead_id;
  const c = lerConfiguracoes();
  let f = carregarFicha(leadId)!;

  // Para a cadência: a partir de agora é conversa
  if (['mapeada', 'enriquecida', 'qualificada', 'em_contato', 'pausada'].includes(f.lead.etapa)) {
    mudarEtapa(leadId, 'respondeu', AGENTE, `Respondeu por ${m.canal}`);
    agendarProximaAcao(leadId, null, null);
  }
  // Lead receptivo que informou o CNPJ: identifica e enriquece a empresa
  if (String(f.empresa.cnpj).startsWith('pendente-')) {
    const cnpj = (m.corpo.match(/\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}/g) ?? []).map(somenteDigitos).find(cnpjValido);
    if (cnpj && !um('SELECT 1 FROM empresas WHERE cnpj = ?', cnpj)) {
      executar('UPDATE empresas SET cnpj = ? WHERE id = ?', cnpj, f.empresa.id);
      await enriquecerLead(leadId, { manterEtapa: true }).catch((e) => log(AGENTE, `enriquecimento do receptivo falhou: ${e.message}`));
      f = carregarFicha(leadId)!;
    }
  }

  const historico = todos<{ direcao: string; corpo: string }>('SELECT direcao, corpo FROM mensagens WHERE lead_id = ? AND id <= ? ORDER BY id DESC LIMIT 8', leadId, mensagemId).reverse();
  let intencao: Intencao | null = intencaoPorRegras(m.corpo);
  let resumo = m.corpo.slice(0, 280);
  if (!intencao || intencao === 'reuniao') {
    try {
      const r = await perguntarJson<{ intencao: Intencao; confianca: number; resumo: string; fatos_novos: string[] }>({
        tarefa: 'intencao',
        sistema: INSTRUCOES.classificadorIntencao,
        usuario: `Conversa (mais antiga primeiro):\n${historico.map((h) => `${h.direcao === 'entrada' ? 'LEAD' : 'ESCRITÓRIO'}: ${h.corpo.slice(0, 600)}`).join('\n')}`,
        dadosPessoais: true,
        temperatura: 0,
      });
      if (!intencao) intencao = r.confianca >= 0.5 ? r.intencao : 'outro';
      resumo = r.resumo || resumo;
      registrarFatosDaConversa(leadId, (r.fatos_novos ?? []).slice(0, 5));
    } catch (e) {
      intencao = intencao ?? 'outro';
      log(AGENTE, `classificação por IA indisponível: ${(e as Error).message}`);
    }
  }
  executar("UPDATE mensagens SET intencao = ?, status = 'processada' WHERE id = ?", intencao, mensagemId);
  registrarEvento(leadId, 'intencao', AGENTE, { mensagemId, intencao, resumo });

  const d = destinatario(f);
  const nome = primeiroNome(d?.nome) || '';
  const responsavel = config.responsavel.nome;
  const assuntoResposta = m.assunto ? (/^re:/i.test(m.assunto) ? m.assunto : `Re: ${m.assunto}`) : null;
  const fixa = RESPOSTAS_FIXAS[intencao];

  if (intencao === 'ausencia') {
    agendarProximaAcao(leadId, 'retomar_apos_ausencia', daquiSql(3 * DIA_MS));
    if (f.lead.etapa === 'respondeu') mudarEtapa(leadId, 'em_contato', AGENTE, 'Resposta automática de ausência');
    return;
  }
  if (intencao === 'descadastro' || intencao === 'nao_interessado' || intencao === 'ja_tem_contador') {
    if (intencao === 'descadastro') {
      for (const ct of f.contatos) {
        executar('INSERT OR IGNORE INTO bloqueios (valor, tipo, motivo) VALUES (?, ?, ?)', ct.valor, ct.tipo, 'Pedido do titular');
        executar('UPDATE contatos SET bloqueado = 1 WHERE id = ?', ct.id);
      }
    }
    executar("UPDATE mensagens SET status = 'descartada', erro = 'cancelada: lead encerrou' WHERE lead_id = ? AND direcao = 'saida' AND status IN ('aguardando_aprovacao','aprovada')", leadId);
    executar('UPDATE leads SET motivo_perda = ? WHERE id = ?', intencao, leadId);
    mudarEtapa(leadId, 'perdida', AGENTE, intencao);
    agendarProximaAcao(leadId, null, null);
    enfileirarResposta(leadId, m.contato_id, m.canal, fixa!(nome, responsavel), assuntoResposta, m.id_externo, 'aprovada', { aprovado: true, etapas: ['roteiro_fixo'], problemas: [], tipo: intencao });
    return;
  }
  if (INTENCOES_QUE_CHAMAM_VOCE.includes(intencao)) {
    enfileirarResposta(leadId, m.contato_id, m.canal, fixa!(nome, responsavel), assuntoResposta, m.id_externo, 'aprovada', { aprovado: true, etapas: ['roteiro_fixo'], problemas: [], tipo: intencao });
    await abrirAtendimentoHumano(leadId, intencao, `${resumo}\n\nÚltima mensagem: "${m.corpo.slice(0, 500)}"`, mensagemId);
    return;
  }

  // interesse / dúvida geral / outro → a IA conduz até o limite de turnos
  const lead = um<{ turnos_automaticos: number }>('SELECT turnos_automaticos FROM leads WHERE id = ?', leadId)!;
  if (intencao === 'outro' || lead.turnos_automaticos >= c.autonomia.max_turnos_automaticos) {
    await abrirAtendimentoHumano(leadId, intencao === 'outro' ? 'outro' : 'limite_conversa', `${resumo}\n\nÚltima mensagem: "${m.corpo.slice(0, 500)}"`, mensagemId);
    return;
  }
  try {
    const fatos = montarFatos(f);
    const r = await perguntarJson<{ resposta: string }>({
      tarefa: 'atendimento',
      sistema: INSTRUCOES.atendente,
      usuario: `${contextoEscritorio(c)}\nResponsável humano: ${responsavel}\n\nFATOS:\n${fatos.join('\n')}\n\nConversa:\n${historico.map((h) => `${h.direcao === 'entrada' ? 'LEAD' : 'ESCRITÓRIO'}: ${h.corpo.slice(0, 600)}`).join('\n')}\n\nEscreva a próxima resposta do escritório.${String(f.empresa.cnpj).startsWith('pendente-') ? ' Ainda não sabemos o CNPJ nem a atividade: pergunte de forma natural.' : ''}`,
      dadosPessoais: true,
      temperatura: 0.5,
    });
    const parecer = await revisar(m.canal, null, r.resposta, fatos);
    const status = c.autonomia.modo === 'automatico' && parecer.aprovado ? 'aprovada' : 'aguardando_aprovacao';
    enfileirarResposta(leadId, m.contato_id, m.canal, r.resposta.trim(), assuntoResposta, m.id_externo, status, { ...parecer, tipo: 'conversa', provedor: r._provedor });
    executar('UPDATE leads SET turnos_automaticos = turnos_automaticos + 1 WHERE id = ?', leadId);
    registrarEvento(leadId, 'resposta_redigida', AGENTE, { status });
  } catch (e) {
    await abrirAtendimentoHumano(leadId, 'ia_indisponivel', `A IA não conseguiu responder agora (${(e as Error).message.slice(0, 120)}).\n\nÚltima mensagem: "${m.corpo.slice(0, 500)}"`, mensagemId);
  }
}

export const entradasPendentes = () => todos<{ id: number }>("SELECT id FROM mensagens WHERE direcao = 'entrada' AND status = 'recebida' ORDER BY id LIMIT 30");
