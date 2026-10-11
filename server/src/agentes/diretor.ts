// Agente Diretor Comercial: coordena a equipe (o agendador executa o plano dele)
// e todo dia escreve um briefing curto para você com o que avançou e o que precisa
// da sua atenção.
import { todos, um } from '../banco.ts';
import { config } from '../config.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { avisarResponsavel } from '../notificar.ts';
import { registrarEvento } from '../registro.ts';
import { INSTRUCOES } from './instrucoes.ts';
import { indicadores } from './operacoes.ts';

export async function briefingDiario(forcar = false) {
  if (!forcar && um("SELECT 1 FROM eventos WHERE tipo = 'briefing' AND date(criado_em, '-3 hours') = date('now', '-3 hours')")) return null;
  const ind = indicadores(7);
  const eventos = todos<{ tipo: string; n: number }>("SELECT tipo, COUNT(*) n FROM eventos WHERE criado_em >= datetime('now', '-1 day') GROUP BY tipo ORDER BY n DESC");
  const numeros = {
    funil: ind.porEtapa,
    ultimos7dias: { novos: ind.novos, contatados: ind.contatados, responderam: ind.responderam, chamaramVoce: ind.chamaramVoce, clientes: ind.clientes, taxaResposta: ind.taxaResposta },
    pendentes: ind.pendentes,
    eventos24h: eventos,
  };
  let texto: string;
  try {
    texto = (await perguntarJson<{ briefing: string }>({ tarefa: 'briefing', sistema: INSTRUCOES.diretor, usuario: JSON.stringify(numeros, null, 2), dadosPessoais: false })).briefing;
  } catch {
    texto = [
      `• Funil: ${ind.porEtapa.qualificada} qualificadas, ${ind.porEtapa.em_contato} em contato, ${ind.porEtapa.respondeu} respondendo, ${ind.porEtapa.com_voce} com você.`,
      `• 7 dias: ${ind.contatados} empresas contatadas, ${ind.responderam} responderam (${ind.taxaResposta ?? 'n/c'}%).`,
      `• Pendências: ${ind.pendentes.aprovacao} mensagens para aprovar, ${ind.pendentes.atendimentos} leads aguardando você.`,
    ].join('\n');
  }
  registrarEvento(null, 'briefing', 'diretor', { texto, numeros });
  await avisarResponsavel('Briefing comercial do dia', texto, config.urlPublica);
  return texto;
}
