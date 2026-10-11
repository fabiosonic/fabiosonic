// Agendador 24/7: cada agente roda no seu intervalo, sem sobreposição, e cada
// execução fica registrada para o painel. O Diretor Comercial é o "dono" deste
// plano; os demais agentes executam as etapas do funil.
import { executar, todos } from './banco.ts';
import { config } from './config.ts';
import { lerConfiguracoes } from './configuracoes.ts';
import { avancarCadencia, leadsComAcaoVencida } from './agentes/acompanhamento.ts';
import { entradasPendentes, processarEntrada, registrarEntrada } from './agentes/atendente.ts';
import { briefingDiario } from './agentes/diretor.ts';
import { dispararPendentes } from './agentes/disparador.ts';
import { enriquecerLead, pendentesDeEnriquecimento } from './agentes/enriquecedor.ts';
import { higienizar, lembrarAtendimentosParados } from './agentes/operacoes.ts';
import { pendentesDeQualificacao, qualificarLead } from './agentes/qualificador.ts';
import { imapConfigurado, lerCaixaDeEntrada } from './canais/email.ts';
import { descobrirNaReceita } from './fontes/receita-dados-abertos.ts';
import { IAIndisponivel } from './ia/roteador.ts';
import { log } from './registro.ts';
import { agoraSql, horaLocal } from './util/tempo.ts';

type Resultado = { processados: number; resumo: string };

export type Agente = {
  id: string;
  nome: string;
  papel: string;
  descricao: string;
  intervaloMs: number | null;
  executar?: () => Promise<Resultado>;
};

async function emLote(ids: { id: number }[], fn: (id: number) => Promise<void>): Promise<Resultado> {
  let ok = 0;
  const erros: string[] = [];
  for (const { id } of ids) {
    try {
      await fn(id);
      ok++;
    } catch (e) {
      erros.push(`#${id}: ${(e as Error).message.slice(0, 120)}`);
      if (e instanceof IAIndisponivel) break; // sem IA agora: tenta na próxima rodada
    }
  }
  return { processados: ok, resumo: erros.length ? `${ok} ok; ${erros.length} pendente(s): ${erros[0]}` : `${ok} processado(s)` };
}

export const AGENTES: Agente[] = [
  {
    id: 'diretor',
    nome: 'Diretor Comercial',
    papel: 'Coordenação',
    descricao: 'Coordena a equipe, acompanha gargalos e envia o briefing diário às 7h30.',
    intervaloMs: 30 * 60_000,
    executar: async () => {
      const { minutos } = horaLocal();
      if (minutos < 7 * 60 + 30) return { processados: 0, resumo: 'aguardando 7h30' };
      const texto = await briefingDiario();
      return { processados: texto ? 1 : 0, resumo: texto ? 'briefing enviado' : 'briefing de hoje já enviado' };
    },
  },
  {
    id: 'prospector',
    nome: 'Prospector',
    papel: 'Busca ativa de empresas',
    descricao: 'Varre os Dados Abertos do CNPJ por empresas recém-abertas no seu perfil de cliente ideal e recebe leads do site, formulários e WhatsApp.',
    intervaloMs: 12 * 3600_000,
    executar: async () => {
      const c = lerConfiguracoes();
      if (!c.descoberta.receita_dados_abertos) return { processados: 0, resumo: 'busca nos Dados Abertos desligada (ative em Configurações)' };
      const r = await descobrirNaReceita(c);
      return { processados: r.novas, resumo: `competência ${r.competencia}: ${r.novas} empresas novas, ${r.socios} sócios, ${r.outrasEmpresas} participações em outras empresas` };
    },
  },
  {
    id: 'enriquecedor',
    nome: 'Enriquecedor',
    papel: 'Dados da empresa e dos sócios',
    descricao: 'Consulta o cadastro CNPJ e o QSA, cruza os sócios com outras empresas, lê o site e organiza os contatos com origem registrada.',
    intervaloMs: 3 * 60_000,
    executar: () => emLote(pendentesDeEnriquecimento(lerConfiguracoes().descoberta.lote_enriquecimento), (id) => enriquecerLead(id)),
  },
  {
    id: 'qualificador',
    nome: 'Qualificador',
    papel: 'Aderência e necessidades',
    descricao: 'Pontua cada empresa com regras explícitas e formula as perguntas de levantamento e o ângulo de abordagem.',
    intervaloMs: 3 * 60_000,
    executar: () => emLote(pendentesDeQualificacao(20), qualificarLead),
  },
  {
    id: 'redator',
    nome: 'Redator',
    papel: 'Mensagens personalizadas',
    descricao: 'Escreve cada e-mail e WhatsApp especificamente para o lead, citando somente fatos da ficha.',
    intervaloMs: null,
  },
  {
    id: 'revisor',
    nome: 'Revisor de Ética',
    papel: 'Portão de conformidade',
    descricao: 'Bloqueia promessas, superlativos, preço, crítica a colegas e fatos não comprovados antes de qualquer envio (NBC PG 01).',
    intervaloMs: null,
  },
  {
    id: 'acompanhamento',
    nome: 'Acompanhamento',
    papel: 'Cadência multicanal',
    descricao: 'Conduz a sequência e-mail → WhatsApp → e-mail e para assim que o lead responde ou pede para parar.',
    intervaloMs: 5 * 60_000,
    executar: () => emLote(leadsComAcaoVencida(10), avancarCadencia),
  },
  {
    id: 'disparador',
    nome: 'Disparador',
    papel: 'Envio controlado',
    descricao: 'Envia as mensagens aprovadas dentro do horário comercial, dos limites diários e do intervalo mínimo entre envios.',
    intervaloMs: 60_000,
    executar: async () => {
      const n = await dispararPendentes();
      return { processados: n, resumo: `${n} enviada(s)` };
    },
  },
  {
    id: 'caixa',
    nome: 'Caixa de Entrada',
    papel: 'Leitura de respostas',
    descricao: 'Lê as respostas de e-mail (IMAP) e liga cada uma ao lead certo. As de WhatsApp chegam em tempo real pelo webhook.',
    intervaloMs: 2 * 60_000,
    executar: async () => {
      if (!imapConfigurado()) return { processados: 0, resumo: 'IMAP não configurado' };
      const emails = await lerCaixaDeEntrada();
      let ligados = 0;
      for (const e of emails) {
        const id = registrarEntrada({ canal: 'email', de: e.de, texto: e.texto, idExterno: e.idMensagem, assunto: e.assunto, emRespostaA: e.emRespostaA, referencias: e.referencias });
        if (id) ligados++;
      }
      return { processados: ligados, resumo: `${emails.length} e-mail(s) lidos, ${ligados} de leads` };
    },
  },
  {
    id: 'atendente',
    nome: 'Atendente (SDR)',
    papel: 'Conversa e repasse para você',
    descricao: 'Classifica cada resposta, conduz a conversa inicial e chama você quando o lead quer falar, pergunta preço ou tem dúvida técnica.',
    intervaloMs: 60_000,
    executar: () => emLote(entradasPendentes(), processarEntrada),
  },
  {
    id: 'operacoes',
    nome: 'Operações e Indicadores',
    papel: 'Higiene do funil',
    descricao: 'Detecta contatos do contador cadastral, aplica bloqueios e relembra você de leads aguardando retorno.',
    intervaloMs: 30 * 60_000,
    executar: async () => {
      const h = higienizar();
      const lembretes = await lembrarAtendimentosParados();
      return { processados: h.repetidos + h.bloqueados + lembretes, resumo: `${h.repetidos} contato(s) de contador marcados, ${h.bloqueados} bloqueio(s), ${lembretes} lembrete(s)` };
    },
  },
];

const rodando = new Set<string>();

export async function executarAgente(id: string): Promise<Resultado> {
  const agente = AGENTES.find((a) => a.id === id);
  if (!agente?.executar) throw new Error(`Agente ${id} não é executável sozinho`);
  if (rodando.has(id)) return { processados: 0, resumo: 'já em execução' };
  rodando.add(id);
  const registro = executar('INSERT INTO execucoes_agentes (agente, inicio) VALUES (?, ?)', id, agoraSql());
  try {
    const r = await agente.executar();
    executar('UPDATE execucoes_agentes SET fim = ?, sucesso = 1, processados = ?, resumo = ? WHERE id = ?', agoraSql(), r.processados, r.resumo, registro.id);
    return r;
  } catch (e) {
    const msg = (e as Error).message;
    executar('UPDATE execucoes_agentes SET fim = ?, sucesso = 0, resumo = ? WHERE id = ?', agoraSql(), msg.slice(0, 500), registro.id);
    log(id, `erro: ${msg}`);
    return { processados: 0, resumo: `erro: ${msg}` };
  } finally {
    rodando.delete(id);
  }
}

export function situacaoAgentes() {
  return AGENTES.map((a) => {
    const ultima = todos<Record<string, any>>('SELECT * FROM execucoes_agentes WHERE agente = ? ORDER BY id DESC LIMIT 1', a.id)[0] ?? null;
    const atividade24h = todos<{ n: number }>(
      "SELECT COUNT(*) n FROM eventos WHERE agente = ? AND criado_em >= datetime('now', '-1 day')",
      a.id,
    )[0]?.n ?? 0;
    const falhas24h = todos<{ n: number }>("SELECT COUNT(*) n FROM execucoes_agentes WHERE agente = ? AND sucesso = 0 AND inicio >= datetime('now', '-1 day')", a.id)[0]?.n ?? 0;
    return {
      id: a.id,
      nome: a.nome,
      papel: a.papel,
      descricao: a.descricao,
      intervaloMs: a.intervaloMs,
      executavel: Boolean(a.executar),
      rodando: rodando.has(a.id),
      ultimaExecucao: ultima,
      atividade24h,
      falhas24h,
    };
  });
}

const timers: NodeJS.Timeout[] = [];

export function iniciarAgendador() {
  if (!config.agendadorLigado) {
    log('agendador', 'desligado por AGENDADOR_DESLIGADO');
    return;
  }
  AGENTES.filter((a) => a.executar && a.intervaloMs).forEach((a, i) => {
    // Escalona o início para não disparar tudo no mesmo segundo
    setTimeout(() => void executarAgente(a.id), 5000 + i * 3000);
    timers.push(setInterval(() => void executarAgente(a.id), a.intervaloMs!));
  });
  log('agendador', `${timers.length} agentes em operação contínua`);
}

export function pararAgendador() {
  timers.splice(0).forEach(clearInterval);
}
