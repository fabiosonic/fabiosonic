// Trilha de auditoria: toda ação relevante de um agente vira um evento, para que
// o painel mostre "quem fez o quê, quando e com base em quê".
import { executar } from './banco.ts';

export function registrarEvento(leadId: number | null, tipo: string, agente: string, detalhe?: unknown) {
  executar(
    'INSERT INTO eventos (lead_id, tipo, agente, detalhe) VALUES (?, ?, ?, ?)',
    leadId,
    tipo,
    agente,
    detalhe === undefined ? null : typeof detalhe === 'string' ? detalhe : JSON.stringify(detalhe),
  );
}

export function log(agente: string, mensagem: string, extra?: unknown) {
  const hora = new Date().toLocaleTimeString('pt-BR', { timeZone: 'America/Sao_Paulo' });
  console.log(`[${hora}] [${agente}] ${mensagem}`, extra === undefined ? '' : extra);
}
