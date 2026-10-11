// IA simulada (IA_SIMULADA=1): respostas determinísticas para demonstração e
// testes sem chave de API. Nunca é usada em produção quando há provedores reais.
import type { PedidoIA } from './roteador.ts';

const fato = (texto: string, rotulo: string) => texto.match(new RegExp(`\\[F\\d+\\] ${rotulo}:? ([^\\n]+)`))?.[1]?.trim() ?? '';

export function respostaSimulada(p: PedidoIA): string {
  const u = p.usuario;
  switch (p.tarefa) {
    case 'analise_site':
      return JSON.stringify({
        resumo: (u.match(/Descrição: (.+)/)?.[1] || 'Empresa com site institucional ativo.').slice(0, 200),
        segmento: 'Conforme CNAE',
        sinais: /marketplace|loja|e-?commerce/i.test(u) ? ['Vende por loja virtual'] : [],
        publico: 'Não identificado',
      });
    case 'qualificacao': {
      const nova = /aberta há \d+ dias/.test(u);
      return JSON.stringify({
        resumo: nova ? 'Empresa recém-aberta, provavelmente estruturando a rotina contábil e fiscal.' : 'Empresa ativa com perfil aderente aos serviços.',
        necessidades: [
          'Como está organizada hoje a emissão de notas e a rotina fiscal?',
          'Já existe definição de pró-labore e folha para os sócios ou equipe?',
          'Quando pretendem ter a contabilidade estruturada?',
        ],
        angulo: nova ? 'Estruturação dos primeiros meses da empresa' : 'Organização da rotina contábil',
        temperatura: nova ? 'morna' : 'fria',
      });
    }
    case 'redacao': {
      const empresa = fato(u, 'Empresa').replace(/ \(razão social.+$/, '') || 'sua empresa';
      const nome = (fato(u, 'Destinatário').split('—')[0] || '').trim();
      const atividade = fato(u, 'Atividade principal \\(CNAE\\)').toLowerCase();
      const cidade = fato(u, 'Localização');
      const recente = /\[F\d+\] Empresa aberta há/.test(u);
      const ids = [...u.matchAll(/\[(F\d+)\]/g)].map((m) => m[1]).slice(0, 3);
      const saudacao = nome ? `Olá, ${nome}, tudo bem?` : 'Olá, tudo bem?';
      const gancho = recente
        ? `Vi que a ${empresa} começou as atividades há pouco tempo${cidade ? ` em ${cidade}` : ''}. Nessa fase, muitas empresas de ${atividade || 'seu ramo'} ainda estão definindo como organizar notas, impostos e pró-labore.`
        : `Acompanho empresas de ${atividade || 'seu ramo'}${cidade ? ` em ${cidade}` : ''} e achei que valeria um contato com a ${empresa}.`;
      return JSON.stringify({
        assunto: recente ? `Primeiros meses da ${empresa}` : `Rotina contábil da ${empresa}`,
        corpo_email: `${saudacao}\n\n${gancho}\n\nSomos um escritório de contabilidade e gostaríamos de entender como vocês estão organizando essa rotina hoje. Faz sentido uma conversa rápida de 15 minutos nesta semana?`,
        whatsapp: `${saudacao} ${recente ? `Vi que a ${empresa} começou há pouco tempo.` : `Falo sobre a ${empresa}.`} Somos um escritório de contabilidade — posso te fazer duas perguntas rápidas sobre como vocês organizam a parte fiscal hoje?`,
        fatos_usados: ids,
      });
    }
    case 'revisao':
      return JSON.stringify({ aprovado: true, problemas: [] });
    case 'intencao': {
      const ultima = u.split('\n').filter((l) => l.startsWith('LEAD:')).pop() ?? '';
      const interesse = /(sim|interess|pode|claro|quero|gostaria)/i.test(ultima);
      return JSON.stringify({ intencao: interesse ? 'interesse' : 'duvida_geral', confianca: 0.8, resumo: `Lead respondeu: ${ultima.slice(5, 120)}`, fatos_novos: [] });
    }
    case 'atendimento':
      return JSON.stringify({ resposta: 'Que bom ter seu retorno! Para entender melhor: qual é a atividade principal da empresa hoje e quantas pessoas trabalham com vocês?' });
    case 'briefing':
      return JSON.stringify({ briefing: '• Funil operando normalmente (dados de demonstração).\n• Verifique as mensagens aguardando aprovação.\n• Recomendação: revisar os segmentos prioritários em Configurações.' });
    default:
      return JSON.stringify({ resposta: 'ok' });
  }
}
