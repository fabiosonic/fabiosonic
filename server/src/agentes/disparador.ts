// Agente Disparador: envia as mensagens aprovadas respeitando janela de horário,
// limites por hora/dia, intervalo mínimo entre envios e a lista de bloqueio.
// Respostas a quem escreveu para o escritório saem logo (entre 7h e 21h).
import { executar, todos, um } from '../banco.ts';
import { emailConfigurado, enviarEmail, montarEmail } from '../canais/email.ts';
import { enviarModeloWhatsapp, enviarTextoWhatsapp, exigeModeloForaDaJanela, whatsappConfigurado } from '../canais/whatsapp.ts';
import { lerConfiguracoes, pendenciasIdentificacao } from '../configuracoes.ts';
import { mudarEtapa } from '../funil.ts';
import { log, registrarEvento } from '../registro.ts';
import { agoraSql, dentroDaJanela } from '../util/tempo.ts';
import { primeiroNome } from '../util/texto.ts';
import { carregarFicha, destinatario } from './ficha.ts';

const AGENTE = 'disparador';

const contarEnvios = (canal: string, periodo: string) =>
  um<{ n: number }>(`SELECT COUNT(*) n FROM mensagens WHERE canal = ? AND direcao = 'saida' AND enviada_em >= datetime('now', ?) AND status IN ('enviada','entregue','lida')`, canal, periodo)?.n ?? 0;

const ultimoEnvio = (canal: string) =>
  um<{ t: string }>("SELECT MAX(enviada_em) t FROM mensagens WHERE canal = ? AND direcao = 'saida' AND agente <> 'atendente' AND status IN ('enviada','entregue','lida')", canal)?.t;

/** Janela de 24 h da API oficial: o lead escreveu nas últimas 24 h? */
const janelaAberta = (leadId: number) =>
  Boolean(um("SELECT 1 FROM mensagens WHERE lead_id = ? AND canal = 'whatsapp' AND direcao = 'entrada' AND criado_em >= datetime('now', '-23 hours')", leadId));

export async function dispararPendentes() {
  const c = lerConfiguracoes();
  const fila = todos<Record<string, any>>(
    `SELECT m.*, ct.valor AS destino, ct.bloqueado AS contato_bloqueado FROM mensagens m
     LEFT JOIN contatos ct ON ct.id = m.contato_id
     WHERE m.direcao = 'saida' AND m.status = 'aprovada' AND (m.agendada_para IS NULL OR m.agendada_para <= ?)
     ORDER BY CASE WHEN m.agente = 'atendente' THEN 0 ELSE 1 END, m.agendada_para LIMIT 20`,
    agoraSql(),
  );
  // NBC PG 01, item 4(r): sem identificação profissional completa, nada de prospecção.
  // Respostas a quem escreveu para o escritório continuam saindo.
  const identificacaoPendente = pendenciasIdentificacao(c).length > 0;
  let enviados = 0;
  const horaLocal = Number(new Intl.DateTimeFormat('pt-BR', { timeZone: 'America/Sao_Paulo', hour: '2-digit', hour12: false }).format(new Date()));
  for (const m of fila) {
    const resposta = m.agente === 'atendente';
    if (!m.destino || m.contato_bloqueado || um('SELECT 1 FROM bloqueios WHERE valor = ?', m.destino)) {
      // A confirmação de descadastro é a única mensagem que ainda vai para quem pediu bloqueio
      if (!(resposta && m.destino && JSON.parse(m.revisao ?? '{}').tipo === 'descadastro')) {
        executar("UPDATE mensagens SET status = 'bloqueada', erro = 'contato bloqueado ou inexistente' WHERE id = ?", m.id);
        continue;
      }
    }
    if (resposta) {
      if (horaLocal < 7 || horaLocal >= 21) continue;
    } else {
      if (identificacaoPendente) {
        executar("UPDATE mensagens SET erro = 'Aguardando identificação completa do escritório em Configurações' WHERE id = ?", m.id);
        continue;
      }
      if (!dentroDaJanela(c.horario_envio)) continue;
      const limiteDia = m.canal === 'email' ? c.limites.emails_dia : c.limites.whatsapp_dia;
      if (contarEnvios(m.canal, '-1 day') >= limiteDia) continue;
      if (m.canal === 'email' && contarEnvios('email', '-1 hour') >= c.limites.emails_hora) continue;
      const ultimo = ultimoEnvio(m.canal);
      if (ultimo && Date.now() - new Date(ultimo.replace(' ', 'T') + 'Z').getTime() < c.limites.intervalo_min_segundos * 1000) continue;
    }

    try {
      let idExterno = '';
      if (m.canal === 'email') {
        if (!emailConfigurado()) throw new Error('SMTP não configurado');
        const montado = montarEmail(c, m.corpo, m.contato_id);
        idExterno = (await enviarEmail({ para: m.destino, assunto: m.assunto || `Contato — ${c.escritorio.nome}`, texto: montado.texto, html: montado.html, linkDescadastro: montado.link, emRespostaA: m.em_resposta_a })).idExterno;
      } else {
        if (!whatsappConfigurado()) throw new Error('WhatsApp não configurado');
        if (exigeModeloForaDaJanela() && !janelaAberta(m.lead_id)) {
          const f = carregarFicha(m.lead_id)!;
          const nome = primeiroNome(destinatario(f)?.nome) || 'tudo bem';
          idExterno = (await enviarModeloWhatsapp(m.destino, [nome, c.escritorio.nome, m.corpo])).idExterno;
        } else {
          const rodape = resposta ? '' : `\n\n${c.escritorio.nome}${c.escritorio.crc_organizacao ? ` · CRC ${c.escritorio.crc_organizacao}` : ''}\nSe preferir não receber mensagens, responda PARAR.`;
          idExterno = (await enviarTextoWhatsapp(m.destino, m.corpo + rodape)).idExterno;
        }
      }
      executar("UPDATE mensagens SET status = 'enviada', id_externo = ?, enviada_em = ?, erro = NULL WHERE id = ?", idExterno, agoraSql(), m.id);
      const lead = um<{ etapa: string }>('SELECT etapa FROM leads WHERE id = ?', m.lead_id);
      if (lead?.etapa === 'qualificada') mudarEtapa(m.lead_id, 'em_contato', AGENTE, `Primeiro contato por ${m.canal}`);
      registrarEvento(m.lead_id, 'mensagem_enviada', AGENTE, { mensagemId: m.id, canal: m.canal });
      enviados++;
      if (!resposta) break; // um envio de prospecção por rodada: espalha os envios ao longo do dia
    } catch (e) {
      const erro = (e as Error).message;
      if (/não configurado|WA_NOME_MODELO/.test(erro)) {
        executar('UPDATE mensagens SET erro = ? WHERE id = ?', erro, m.id);
        continue;
      }
      const tentativas = Number(m.erro?.match(/tentativa (\d+)/)?.[1] ?? 0) + 1;
      const definitivo = /invalid|inválid|not a valid|does not exist|recipient|no such user|mailbox unavailable/i.test(erro);
      executar('UPDATE mensagens SET status = ?, erro = ? WHERE id = ?', definitivo || tentativas >= 3 ? 'falhou' : 'aprovada', `${erro.slice(0, 300)} (tentativa ${tentativas})`, m.id);
      log(AGENTE, `falha ao enviar mensagem ${m.id}: ${erro}`);
    }
  }
  return enviados;
}
