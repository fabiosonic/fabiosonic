// Agente de Acompanhamento: executa a cadência configurada (ex.: e-mail no dia 0,
// WhatsApp no dia 3, e-mail no dia 7, último contato no dia 14). Para assim que o
// lead responde, pede para parar ou a cadência termina (lead vai para "pausada").
import { executar, todos, um } from '../banco.ts';
import { lerConfiguracoes } from '../configuracoes.ts';
import { agendarProximaAcao, mudarEtapa } from '../funil.ts';
import { registrarEvento } from '../registro.ts';
import { agoraSql, daquiSql, DIA_MS } from '../util/tempo.ts';
import { redigirMensagem } from './redator.ts';

const AGENTE = 'acompanhamento';

export function leadsComAcaoVencida(limite: number) {
  return todos<{ id: number; etapa: string; passo_cadencia: number }>(
    `SELECT id, etapa, passo_cadencia FROM leads
     WHERE etapa IN ('qualificada','em_contato') AND proxima_acao_em IS NOT NULL AND proxima_acao_em <= ?
     ORDER BY pontuacao DESC, proxima_acao_em LIMIT ?`,
    agoraSql(),
    limite,
  );
}

export async function avancarCadencia(leadId: number) {
  const c = lerConfiguracoes();
  const lead = um<{ passo_cadencia: number; etapa: string }>('SELECT passo_cadencia, etapa FROM leads WHERE id = ?', leadId);
  if (!lead) return;
  // Não empilha mensagens: espera a anterior sair (ou ser aprovada por você)
  const pendente = um("SELECT 1 FROM mensagens WHERE lead_id = ? AND direcao = 'saida' AND status IN ('aguardando_aprovacao','aprovada')", leadId);
  if (pendente) {
    agendarProximaAcao(leadId, 'aguardando_envio_anterior', daquiSql(6 * 3600_000));
    return;
  }
  const proximo = c.cadencia.find((p) => p.passo === lead.passo_cadencia + 1);
  if (!proximo) {
    mudarEtapa(leadId, 'pausada', AGENTE, 'Cadência concluída sem resposta');
    agendarProximaAcao(leadId, null, null);
    return;
  }
  const mensagemId = await redigirMensagem(leadId, proximo.tipo, proximo.canal);
  executar('UPDATE leads SET passo_cadencia = ? WHERE id = ?', proximo.passo, leadId);
  const seguinte = c.cadencia.find((p) => p.passo === proximo.passo + 1);
  if (seguinte) agendarProximaAcao(leadId, seguinte.tipo, daquiSql((seguinte.dia - proximo.dia) * DIA_MS));
  else agendarProximaAcao(leadId, 'encerrar_cadencia', daquiSql(5 * DIA_MS));
  if (!mensagemId && lead.etapa === 'qualificada' && proximo.passo === 1) {
    mudarEtapa(leadId, 'descartada', AGENTE, 'Sem canal de contato utilizável');
    agendarProximaAcao(leadId, null, null);
  }
  registrarEvento(leadId, 'cadencia', AGENTE, { passo: proximo.passo, canal: proximo.canal, mensagemId });
}
