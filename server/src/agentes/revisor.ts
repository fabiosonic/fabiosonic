// Agente Revisor de Ética: portão obrigatório antes de qualquer envio.
// Primeiro aplica regras determinísticas (rápidas, não dependem de IA); se passar,
// pede uma segunda verificação à IA contra os fatos. O parecer não substitui a
// aprovação humana: no modo "aprovação" você confirma cada mensagem no painel.
import { lerConfiguracoes } from '../configuracoes.ts';
import { perguntarJson } from '../ia/roteador.ts';
import { INSTRUCOES } from './instrucoes.ts';

export type Problema = { trecho: string; regra: string; correcao: string };
export type Parecer = { aprovado: boolean; problemas: Problema[]; etapas: string[] };

const REGRAS: { padrao: RegExp; regra: string; correcao: string }[] = [
  { padrao: /\bgarant(imos|ido|ida|idos|idas|ia|e|em)\b/i, regra: 'Promessa de resultado garantido (política: sem resultado assegurado)', correcao: 'Remova a garantia; descreva o serviço, não o resultado.' },
  { padrao: /(economi[az]\w*|reduz\w*|pagar? menos)\s.{0,40}(imposto|tribut|\d+\s?%)/i, regra: 'Promessa de economia tributária', correcao: 'Troque por convite a entender a situação, sem prometer redução.' },
  { padrao: /\b(o|a|os|as) melhor(es)?\b|\bn[º°o]\.?\s?1\b|\blíder(es)?\b|\bincompar[aá]vel\b/i, regra: 'Superlativo sem prova (NBC PG 01, itens 11-15)', correcao: 'Use informação objetiva e comprovável.' },
  { padrao: /R\$\s?\d|\b\d+[.,]?\d*\s?reais\b|honor[aá]rios?\s.{0,25}\d/i, regra: 'Menção a preço/honorário (tratado só pelo responsável)', correcao: 'Remova valores; preço é discutido pelo responsável.' },
  { padrao: /(seu|sua|atual|antigo)\s+(contador|contadora|contabilidade|escrit[oó]rio).{0,60}(err|problema|falh|ruim|incompet|descuid|atras|não\s+(faz|cuida))/i, regra: 'Depreciação de outro profissional (NBC PG 01, itens 15-18)', correcao: 'Fale apenas da própria oferta.' },
  { padrao: /(última chance|só hoje|apenas hoje|vagas limitadas|corra|imperd[ií]vel|urgente)/i, regra: 'Urgência ou escassez artificial', correcao: 'Retire a pressão; convide para conversar.' },
  { padrao: /(multa|autua[çc][aã]o|malha fina|fiscaliza[çc][aã]o)\s.{0,40}(vai|pode|risco|evitar)/i, regra: 'Uso de medo como argumento', correcao: 'Não use risco fiscal como gancho de venda.' },
  { padrao: /\bcpf\b|\d{3}\.\d{3}\.\d{3}-\d{2}/i, regra: 'Exposição de dado pessoal sensível ao contexto', correcao: 'Não mencione CPF ou documentos pessoais.' },
  { padrao: /(sem|zero)\s+(risco|fiscaliza)/i, regra: 'Promessa de ausência de risco/fiscalização', correcao: 'Remova a promessa.' },
];

export function regrasDeterministicas(texto: string): Problema[] {
  const problemas: Problema[] = [];
  for (const r of REGRAS) {
    const m = texto.match(r.padrao);
    if (m) problemas.push({ trecho: m[0], regra: r.regra, correcao: r.correcao });
  }
  return problemas;
}

export function verificarFormato(canal: 'email' | 'whatsapp', assunto: string | null, corpo: string): Problema[] {
  const p: Problema[] = [];
  const palavras = corpo.trim().split(/\s+/).length;
  if (canal === 'email' && palavras > 160) p.push({ trecho: `${palavras} palavras`, regra: 'E-mail longo demais para primeiro contato', correcao: 'Reduza para até ~110 palavras.' });
  if (canal === 'whatsapp' && palavras > 80) p.push({ trecho: `${palavras} palavras`, regra: 'WhatsApp longo demais', correcao: 'Reduza para até ~55 palavras.' });
  if (canal === 'email' && assunto && (assunto.length > 80 || assunto === assunto.toUpperCase())) p.push({ trecho: assunto, regra: 'Assunto longo ou em caixa alta', correcao: 'Assunto curto e natural.' });
  if (/\[(nome|empresa|segmento|servi[çc]o)[^\]]*\]|\{\{|\}\}/i.test(corpo + (assunto ?? ''))) p.push({ trecho: 'campo não preenchido', regra: 'Texto com campo de modelo pendente', correcao: 'Preencha ou remova o campo.' });
  return p;
}

export async function revisar(canal: 'email' | 'whatsapp', assunto: string | null, corpo: string, fatos: string[]): Promise<Parecer> {
  const texto = `${assunto ?? ''}\n${corpo}`;
  const problemas = [...regrasDeterministicas(texto), ...verificarFormato(canal, assunto, corpo)];
  if (problemas.length) return { aprovado: false, problemas, etapas: ['regras'] };
  const c = lerConfiguracoes();
  const r = await perguntarJson<{ aprovado: boolean; problemas: Problema[] }>({
    tarefa: 'revisao',
    sistema: INSTRUCOES.revisor,
    usuario: `Escritório: ${c.escritorio.nome}\nDiferenciais comprovados: ${c.diferenciais_comprovados.join('; ') || 'nenhum'}\n\nFATOS DISPONÍVEIS:\n${fatos.join('\n')}\n\nMENSAGEM (${canal}):\n${assunto ? `Assunto: ${assunto}\n` : ''}${corpo}`,
    dadosPessoais: true,
    temperatura: 0,
  });
  const lista = Array.isArray(r.problemas) ? r.problemas.filter((x) => x && x.regra) : [];
  return { aprovado: Boolean(r.aprovado) && lista.length === 0, problemas: lista, etapas: ['regras', `ia:${r._provedor}`] };
}
