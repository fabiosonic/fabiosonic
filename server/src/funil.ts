// Etapas do funil, derivadas do roteamento.json da equipe comercial. Toda mudança
// de etapa gera um evento com o agente responsável e o motivo.
import { executar, um } from './banco.ts';
import { registrarEvento } from './registro.ts';

export const ETAPAS = [
  { id: 'mapeada', nome: 'Mapeada', descricao: 'Empresa identificada com origem documentada', agente: 'prospector' },
  { id: 'enriquecida', nome: 'Enriquecida', descricao: 'Cadastro, sócios, site e contatos levantados', agente: 'enriquecedor' },
  { id: 'qualificada', nome: 'Qualificada', descricao: 'Aderente ao perfil; pronta para abordagem', agente: 'qualificador' },
  { id: 'em_contato', nome: 'Em contato', descricao: 'Cadência de abordagem em andamento', agente: 'acompanhamento' },
  { id: 'respondeu', nome: 'Respondeu', descricao: 'Lead respondeu; atendimento inicial pela IA', agente: 'atendente' },
  { id: 'com_voce', nome: 'Com você', descricao: 'Lead quer falar com você, preço ou dúvida técnica', agente: 'humano' },
  { id: 'proposta', nome: 'Proposta', descricao: 'Proposta enviada pelo responsável', agente: 'humano' },
  { id: 'negociacao', nome: 'Negociação', descricao: 'Condições em discussão', agente: 'humano' },
  { id: 'cliente', nome: 'Cliente', descricao: 'Contrato escrito formalizado (com evidência)', agente: 'humano' },
  { id: 'pausada', nome: 'Pausada', descricao: 'Sem resposta após a cadência; revisitar depois', agente: 'acompanhamento' },
  { id: 'descartada', nome: 'Descartada', descricao: 'Fora do perfil ou sem canal de contato válido', agente: 'qualificador' },
  { id: 'perdida', nome: 'Perdida', descricao: 'Não interessado, descadastro ou outro motivo registrado', agente: 'operacoes' },
] as const;

export type Etapa = (typeof ETAPAS)[number]['id'];
export const ETAPAS_ATIVAS: Etapa[] = ['mapeada', 'enriquecida', 'qualificada', 'em_contato', 'respondeu', 'com_voce', 'proposta', 'negociacao'];

export function mudarEtapa(leadId: number, etapa: Etapa, agente: string, motivo?: string, extra: Record<string, unknown> = {}) {
  const atual = um<{ etapa: string }>('SELECT etapa FROM leads WHERE id = ?', leadId);
  if (!atual || atual.etapa === etapa) return;
  executar("UPDATE leads SET etapa = ?, atualizado_em = datetime('now') WHERE id = ?", etapa, leadId);
  registrarEvento(leadId, 'mudanca_etapa', agente, { de: atual.etapa, para: etapa, motivo, ...extra });
}

export function agendarProximaAcao(leadId: number, acao: string | null, quando: string | null) {
  executar("UPDATE leads SET proxima_acao = ?, proxima_acao_em = ?, atualizado_em = datetime('now') WHERE id = ?", acao, quando, leadId);
}
