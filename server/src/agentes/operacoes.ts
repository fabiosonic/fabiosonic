// Agente de Operações e Indicadores: mantém o funil consistente e calcula os
// números do painel sem inflar resultados (proposta aceita ≠ contrato; taxa com
// denominador zero = "não calculável").
import { executar, todos, um } from '../banco.ts';
import { ETAPAS } from '../funil.ts';
import { avisarResponsavel } from '../notificar.ts';
import { config } from '../config.ts';
import { registrarEvento } from '../registro.ts';

export function higienizar() {
  // Contatos repetidos em várias empresas → provavelmente do contador cadastral
  const repetidos = executar(
    `UPDATE contatos SET provavel_contador = 1 WHERE provavel_contador = 0 AND (tipo, valor) IN (
       SELECT tipo, valor FROM contatos GROUP BY tipo, valor HAVING COUNT(DISTINCT empresa_id) >= 3)`,
  ).alteradas;
  // Contatos que entraram na lista de bloqueio depois de cadastrados
  const bloqueados = executar('UPDATE contatos SET bloqueado = 1 WHERE bloqueado = 0 AND valor IN (SELECT valor FROM bloqueios)').alteradas;
  return { repetidos, bloqueados };
}

/** Atendimentos humanos abertos há mais de 4 h sem resolução recebem novo aviso (uma vez por dia). */
export async function lembrarAtendimentosParados() {
  const parados = todos<{ id: number; lead_id: number; motivo: string; resumo: string }>(
    `SELECT a.id, a.lead_id, a.motivo, a.resumo FROM atendimentos_humanos a
     WHERE a.status = 'aberto' AND a.criado_em <= datetime('now', '-4 hours')
       AND NOT EXISTS (SELECT 1 FROM eventos e WHERE e.lead_id = a.lead_id AND e.tipo = 'lembrete_responsavel' AND e.criado_em >= datetime('now', '-1 day'))`,
  );
  for (const p of parados) {
    await avisarResponsavel('Lead aguardando seu retorno', p.resumo ?? '', `${config.urlPublica}/leads/${p.lead_id}`);
    registrarEvento(p.lead_id, 'lembrete_responsavel', 'operacoes', { atendimento: p.id });
  }
  return parados.length;
}

const taxa = (num: number, den: number) => (den > 0 ? Math.round((num / den) * 1000) / 10 : null);

export function indicadores(dias = 30) {
  const periodo = `-${dias} days`;
  const porEtapa = Object.fromEntries(ETAPAS.map((e) => [e.id, 0]));
  for (const r of todos<{ etapa: string; n: number }>('SELECT etapa, COUNT(*) n FROM leads GROUP BY etapa')) porEtapa[r.etapa] = r.n;

  const contatados = um<{ n: number }>(
    "SELECT COUNT(DISTINCT lead_id) n FROM mensagens WHERE direcao = 'saida' AND status IN ('enviada','entregue','lida') AND enviada_em >= datetime('now', ?)",
    periodo,
  )!.n;
  const responderam = um<{ n: number }>(
    "SELECT COUNT(DISTINCT lead_id) n FROM mensagens WHERE direcao = 'entrada' AND criado_em >= datetime('now', ?)",
    periodo,
  )!.n;
  const chamaramVoce = um<{ n: number }>('SELECT COUNT(*) n FROM atendimentos_humanos WHERE criado_em >= datetime(\'now\', ?)', periodo)!.n;
  const clientes = um<{ n: number }>(
    "SELECT COUNT(*) n FROM eventos WHERE tipo = 'mudanca_etapa' AND json_extract(detalhe, '$.para') = 'cliente' AND criado_em >= datetime('now', ?)",
    periodo,
  )!.n;
  const novos = um<{ n: number }>("SELECT COUNT(*) n FROM leads WHERE criado_em >= datetime('now', ?)", periodo)!.n;

  const serie = todos<{ dia: string; enviadas: number; recebidas: number }>(
    `WITH RECURSIVE d(dia) AS (SELECT date('now', ?) UNION ALL SELECT date(dia, '+1 day') FROM d WHERE dia < date('now'))
     SELECT d.dia,
       (SELECT COUNT(*) FROM mensagens WHERE direcao = 'saida' AND status IN ('enviada','entregue','lida') AND date(enviada_em) = d.dia) enviadas,
       (SELECT COUNT(*) FROM mensagens WHERE direcao = 'entrada' AND date(criado_em) = d.dia) recebidas
     FROM d`,
    `-${dias - 1} days`,
  );
  const motivosPerda = todos<{ motivo: string; n: number }>(
    "SELECT COALESCE(motivo_perda, 'não registrado') motivo, COUNT(*) n FROM leads WHERE etapa = 'perdida' GROUP BY 1 ORDER BY n DESC",
  );
  const porSegmento = todos<{ segmento: string; n: number; qualificados: number }>(
    `SELECT COALESCE(e.segmento, 'Não classificado') segmento, COUNT(*) n,
       SUM(CASE WHEN l.etapa NOT IN ('mapeada','enriquecida','descartada') THEN 1 ELSE 0 END) qualificados
     FROM leads l JOIN empresas e ON e.id = l.empresa_id GROUP BY 1 ORDER BY n DESC LIMIT 8`,
  );
  const pendentes = {
    aprovacao: um<{ n: number }>("SELECT COUNT(*) n FROM mensagens WHERE status = 'aguardando_aprovacao'")!.n,
    atendimentos: um<{ n: number }>("SELECT COUNT(*) n FROM atendimentos_humanos WHERE status <> 'resolvido'")!.n,
    filaEnvio: um<{ n: number }>("SELECT COUNT(*) n FROM mensagens WHERE status = 'aprovada'")!.n,
  };
  const hoje = {
    enviadas: um<{ n: number }>("SELECT COUNT(*) n FROM mensagens WHERE direcao = 'saida' AND date(enviada_em) = date('now') AND status IN ('enviada','entregue','lida')")!.n,
    recebidas: um<{ n: number }>("SELECT COUNT(*) n FROM mensagens WHERE direcao = 'entrada' AND date(criado_em) = date('now')")!.n,
    novosLeads: um<{ n: number }>("SELECT COUNT(*) n FROM leads WHERE date(criado_em) = date('now')")!.n,
  };
  return {
    periodoDias: dias,
    porEtapa,
    novos,
    contatados,
    responderam,
    chamaramVoce,
    clientes,
    taxaResposta: taxa(responderam, contatados),
    taxaConversa: taxa(chamaramVoce, contatados),
    serie,
    motivosPerda,
    porSegmento,
    pendentes,
    hoje,
  };
}
