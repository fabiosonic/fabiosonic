// Agente Qualificador: pontua a aderência ao perfil de cliente ideal com regras
// explícitas (cada ponto tem motivo registrado) e usa a IA apenas para formular
// as hipóteses de necessidade como perguntas e o ângulo da primeira conversa.
import { executar, json, todos } from '../banco.ts';
import { lerConfiguracoes, type Configuracoes } from '../configuracoes.ts';
import { agendarProximaAcao, mudarEtapa } from '../funil.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { log, registrarEvento } from '../registro.ts';
import { agoraSql } from '../util/tempo.ts';
import { carregarFicha, montarFatos, type Ficha } from './ficha.ts';
import { contextoEscritorio, INSTRUCOES } from './instrucoes.ts';

const AGENTE = 'qualificador';

export function pontuar(f: Ficha, c: Configuracoes): { pontos: number; motivos: string[] } {
  const e = f.empresa;
  const pi = c.perfil_cliente_ideal;
  const motivos: string[] = [];
  let p = 30;
  const somar = (v: number, motivo: string) => {
    p += v;
    motivos.push(`${v > 0 ? '+' : ''}${v} ${motivo}`);
  };

  if (e.situacao && e.situacao !== 'ATIVA') return { pontos: 0, motivos: [`Situação ${e.situacao}`] };
  if (e.segmento && pi.segmentos.includes(e.segmento)) somar(20, `segmento prioritário (${e.segmento})`);
  else if (e.segmento) somar(-5, `segmento fora da prioridade (${e.segmento})`);

  if (e.data_abertura) {
    const dias = (Date.now() - new Date(e.data_abertura).getTime()) / 86_400_000;
    if (dias <= pi.abertura_max_dias) somar(15, 'empresa recém-aberta');
    else if (dias <= 365) somar(8, 'aberta há menos de 1 ano');
  }
  if (e.optante_mei && pi.excluir_mei) somar(-40, 'MEI (fora do perfil configurado)');
  if (e.porte && pi.portes.length && pi.portes.includes(e.porte)) somar(e.porte === 'DEMAIS' ? 12 : 10, `porte ${e.porte.toLowerCase()}`);
  if (e.capital_social >= 100_000) somar(8, 'capital social ≥ R$ 100 mil');
  else if (e.capital_social >= 10_000) somar(4, 'capital social ≥ R$ 10 mil');
  if (pi.capital_minimo && (e.capital_social ?? 0) < pi.capital_minimo) somar(-15, 'capital abaixo do mínimo configurado');

  if (pi.ufs.length) pi.ufs.includes(e.uf) ? somar(5, `UF atendida (${e.uf})`) : somar(-20, `UF fora da área (${e.uf})`);
  if (pi.municipios.length && e.municipio) {
    const norm = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toUpperCase();
    pi.municipios.map(norm).includes(norm(e.municipio)) ? somar(5, 'município atendido') : somar(-10, 'município fora da área');
  }

  const utilizaveis = f.contatos.filter((ct) => !ct.bloqueado && !ct.provavel_contador && ct.tipo !== 'telefone');
  if (utilizaveis.length) somar(10, `${utilizaveis.length} canal(is) de contato utilizável(is)`);
  else somar(-25, 'sem canal de contato próprio da empresa');
  if (f.socios.some((s) => json<unknown[]>(s.outras_empresas, []).length > 0)) somar(5, 'sócio com outras empresas (grupo)');
  if (json<{ resumo?: string }>(e.site_resumo, {}).resumo) somar(5, 'site ativo com informações');

  return { pontos: Math.max(0, Math.min(100, p)), motivos };
}

export async function qualificarLead(leadId: number) {
  const f = carregarFicha(leadId);
  if (!f) return;
  const c = lerConfiguracoes();
  const { pontos, motivos } = pontuar(f, c);
  executar("UPDATE leads SET pontuacao = ?, pontuacao_motivos = ?, atualizado_em = datetime('now') WHERE id = ?", pontos, JSON.stringify(motivos), leadId);

  if (pontos < c.pontuacao_minima) {
    mudarEtapa(leadId, 'descartada', AGENTE, `Pontuação ${pontos} abaixo do mínimo ${c.pontuacao_minima}`, { motivos });
    return;
  }

  // Hipóteses de necessidade (sem dados pessoais no pedido)
  try {
    const r = await perguntarJson<{ resumo: string; necessidades: string[]; angulo: string; temperatura: string }>({
      tarefa: 'qualificacao',
      sistema: INSTRUCOES.qualificador,
      usuario: `${contextoEscritorio(c)}\n\nFATOS DA EMPRESA:\n${montarFatos(f, false).join('\n')}\n\nPontuação de aderência: ${pontos}/100 (${motivos.join('; ')})`,
      dadosPessoais: false,
    });
    executar(
      'UPDATE leads SET resumo_ia = ?, necessidades = ?, temperatura = ? WHERE id = ?',
      `${r.resumo}${r.angulo ? `\nÂngulo sugerido: ${r.angulo}` : ''}`,
      JSON.stringify((r.necessidades ?? []).slice(0, 5)),
      ['fria', 'morna', 'quente'].includes(r.temperatura) ? r.temperatura : 'fria',
      leadId,
    );
  } catch (e) {
    log(AGENTE, `hipóteses pela IA indisponíveis para o lead ${leadId}: ${(e as Error).message}`);
  }
  registrarEvento(leadId, 'qualificacao', AGENTE, { pontos, motivos });
  mudarEtapa(leadId, 'qualificada', AGENTE, `Pontuação ${pontos}`);
  agendarProximaAcao(leadId, 'primeiro_contato', agoraSql());
}

export const pendentesDeQualificacao = (limite: number) =>
  todos<{ id: number }>("SELECT id FROM leads WHERE etapa = 'enriquecida' ORDER BY criado_em LIMIT ?", limite);
