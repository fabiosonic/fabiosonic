// Roteador de IA: tenta os provedores na ordem configurada e, quando um deles
// esgota o crédito/cota, devolve erro ou fica lento, pausa esse provedor pelo
// tempo adequado e passa automaticamente para o próximo.
import { executar, um } from '../banco.ts';
import { config } from '../config.ts';
import { lerConfiguracoes } from '../configuracoes.ts';
import { log } from '../registro.ts';
import { agoraSql, dataLocalIso, daquiSql } from '../util/tempo.ts';
import { PROVEDORES, credencial, modeloDoProvedor, provedorConfigurado, urlDoProvedor, type Provedor } from './provedores.ts';
import { respostaSimulada } from './simulada.ts';

export type PedidoIA = {
  tarefa: string;
  sistema: string;
  usuario: string;
  json?: boolean;
  /** Marca a tarefa como contendo dados pessoais (nomes, conversas). */
  dadosPessoais?: boolean;
  temperatura?: number;
  maxTokens?: number;
};

export type RespostaIA = { texto: string; provedor: string; modelo: string };

export class IAIndisponivel extends Error {
  tentativas: string[];
  constructor(tentativas: string[]) {
    super(`Nenhum provedor de IA disponível agora (${tentativas.join('; ') || 'nenhum configurado'})`);
    this.tentativas = tentativas;
  }
}

let fetchImpl: typeof fetch = (...a) => fetch(...a);
/** Permite substituir o fetch nos testes. */
export const definirFetchIA = (f: typeof fetch) => (fetchImpl = f);

type Estado = { pausado_ate: string | null; motivo: string | null; chamadas_dia: number; dia: string | null };

function estado(id: string): Estado {
  return (
    um<Estado>('SELECT pausado_ate, motivo, chamadas_dia, dia FROM estado_provedores WHERE provedor = ?', id) ?? {
      pausado_ate: null,
      motivo: null,
      chamadas_dia: 0,
      dia: null,
    }
  );
}

function pausar(id: string, ms: number, motivo: string) {
  executar(
    `INSERT INTO estado_provedores (provedor, pausado_ate, motivo) VALUES (?, ?, ?)
     ON CONFLICT(provedor) DO UPDATE SET pausado_ate = excluded.pausado_ate, motivo = excluded.motivo`,
    id,
    daquiSql(ms),
    motivo,
  );
  log('roteador-ia', `provedor ${id} pausado por ${Math.round(ms / 60000)} min: ${motivo}`);
}

function contarChamada(id: string) {
  const hoje = dataLocalIso();
  executar(
    `INSERT INTO estado_provedores (provedor, chamadas_dia, dia) VALUES (?, 1, ?)
     ON CONFLICT(provedor) DO UPDATE SET
       chamadas_dia = CASE WHEN dia = excluded.dia THEN chamadas_dia + 1 ELSE 1 END,
       dia = excluded.dia`,
    id,
    hoje,
  );
}

function registrarUso(p: Provedor, modelo: string, tarefa: string, sucesso: boolean, inicio: number, extra: { status?: number; erro?: string; tin?: number; tout?: number }) {
  executar(
    `INSERT INTO uso_ia (provedor, modelo, tarefa, sucesso, status_http, erro, tokens_entrada, tokens_saida, duracao_ms)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
    p.id,
    modelo,
    tarefa,
    sucesso,
    extra.status ?? null,
    extra.erro?.slice(0, 500) ?? null,
    extra.tin ?? null,
    extra.tout ?? null,
    Date.now() - inicio,
  );
}

const MS_ATE_AMANHA = () => {
  const agora = new Date();
  const amanha = new Date(agora);
  amanha.setUTCHours(24, 5, 0, 0);
  return amanha.getTime() - agora.getTime();
};

/** Decide por quanto tempo pausar o provedor conforme o tipo de falha. */
export function classificarFalha(status: number, corpo: string, retryAfter: string | null): { ms: number; motivo: string } {
  const texto = corpo.toLowerCase();
  const cotaDiaria = /per day|daily|quota|exceeded your current|insufficient|credit|billing|tokens per day|rpd|limit reached/.test(texto);
  if (status === 402) return { ms: MS_ATE_AMANHA(), motivo: 'créditos esgotados' };
  if (status === 429) {
    if (cotaDiaria && !/per minute|rpm|tpm/.test(texto)) return { ms: MS_ATE_AMANHA(), motivo: 'cota diária esgotada' };
    const segundos = Number(retryAfter);
    return { ms: Number.isFinite(segundos) && segundos > 0 ? Math.min(segundos, 3600) * 1000 : 60_000, motivo: 'limite por minuto' };
  }
  if (status === 401 || status === 403) return { ms: 6 * 3600_000, motivo: 'credencial inválida ou sem permissão' };
  if (status === 404 || (status === 400 && /model/.test(texto))) return { ms: 6 * 3600_000, motivo: 'modelo indisponível — ajuste IA_MODELO_*' };
  if (status >= 500 || status === 0) return { ms: 2 * 60_000, motivo: `instabilidade (${status || 'rede'})` };
  return { ms: 60_000, motivo: `erro ${status}` };
}

export function provedoresElegiveis(dadosPessoais: boolean) {
  const conf = lerConfiguracoes().ia;
  const ordem = [...conf.ordem_provedores, ...PROVEDORES.map((p) => p.id).filter((id) => !conf.ordem_provedores.includes(id))];
  const hoje = dataLocalIso();
  const agora = agoraSql();
  const lista: { p: Provedor; motivoPulo?: string }[] = [];
  for (const id of ordem) {
    const p = PROVEDORES.find((x) => x.id === id);
    if (!p) continue;
    if (!provedorConfigurado(p)) continue;
    const e = estado(id);
    const limite = conf.limites_diarios[id];
    if (dadosPessoais && conf.privacidade_estrita && p.podeTreinar) lista.push({ p, motivoPulo: 'privacidade estrita' });
    else if (e.pausado_ate && e.pausado_ate > agora) lista.push({ p, motivoPulo: `pausado: ${e.motivo}` });
    else if (limite && e.dia === hoje && e.chamadas_dia >= limite) lista.push({ p, motivoPulo: 'limite diário configurado atingido' });
    else lista.push({ p });
  }
  return lista;
}

export async function perguntarIA(pedido: PedidoIA): Promise<RespostaIA> {
  if (config.ia.simulada) return { texto: respostaSimulada(pedido), provedor: 'simulada', modelo: 'simulada' };

  const tentativas: string[] = [];
  for (const { p, motivoPulo } of provedoresElegiveis(Boolean(pedido.dadosPessoais))) {
    if (motivoPulo) {
      tentativas.push(`${p.id}: ${motivoPulo}`);
      continue;
    }
    const modelo = modeloDoProvedor(p);
    const inicio = Date.now();
    const controle = new AbortController();
    const timer = setTimeout(() => controle.abort(), config.ia.tempoLimiteMs);
    try {
      contarChamada(p.id);
      const corpo: Record<string, unknown> = {
        model: modelo,
        temperature: pedido.temperatura ?? 0.4,
        max_tokens: pedido.maxTokens ?? 1200,
        messages: [
          { role: 'system', content: pedido.sistema },
          { role: 'user', content: pedido.usuario },
        ],
      };
      if (pedido.json && !p.local) corpo.response_format = { type: 'json_object' };
      const cabecalhos: Record<string, string> = { 'content-type': 'application/json' };
      if (!p.local) cabecalhos.authorization = `Bearer ${credencial(p)}`;
      if (p.id === 'openrouter') {
        cabecalhos['http-referer'] = config.urlPublica;
        cabecalhos['x-title'] = 'Central Comercial';
      }
      const r = await fetchImpl(`${urlDoProvedor(p)}/chat/completions`, {
        method: 'POST',
        headers: cabecalhos,
        body: JSON.stringify(corpo),
        signal: controle.signal,
      });
      const bruto = await r.text();
      if (!r.ok) {
        const falha = classificarFalha(r.status, bruto, r.headers.get('retry-after'));
        pausar(p.id, falha.ms, falha.motivo);
        registrarUso(p, modelo, pedido.tarefa, false, inicio, { status: r.status, erro: falha.motivo + ' | ' + bruto.slice(0, 300) });
        tentativas.push(`${p.id}: ${falha.motivo}`);
        continue;
      }
      const dados = JSON.parse(bruto);
      const texto: string = dados.choices?.[0]?.message?.content ?? '';
      if (!texto.trim()) throw new Error('resposta vazia');
      registrarUso(p, modelo, pedido.tarefa, true, inicio, {
        status: r.status,
        tin: dados.usage?.prompt_tokens,
        tout: dados.usage?.completion_tokens,
      });
      return { texto, provedor: p.id, modelo };
    } catch (e) {
      const msg = (e as Error).name === 'AbortError' ? 'tempo esgotado' : (e as Error).message;
      const falha = classificarFalha(0, msg, null);
      pausar(p.id, falha.ms, `${falha.motivo}: ${msg}`);
      registrarUso(p, modelo, pedido.tarefa, false, inicio, { erro: msg });
      tentativas.push(`${p.id}: ${msg}`);
    } finally {
      clearTimeout(timer);
    }
  }
  throw new IAIndisponivel(tentativas);
}

/** Extrai o primeiro objeto JSON de uma resposta (alguns modelos cercam com ``` ou texto). */
export function extrairJson<T>(texto: string): T {
  const limpo = texto.replace(/```(?:json)?/gi, '').trim();
  const inicio = limpo.indexOf('{');
  const fim = limpo.lastIndexOf('}');
  if (inicio < 0 || fim <= inicio) throw new Error('A IA não devolveu JSON');
  return JSON.parse(limpo.slice(inicio, fim + 1)) as T;
}

/** Pede JSON e tenta mais uma vez (em outro provedor, se preciso) quando o JSON vem quebrado. */
export async function perguntarJson<T>(pedido: PedidoIA): Promise<T & { _provedor: string }> {
  let ultimoErro: unknown;
  for (let i = 0; i < 2; i++) {
    const r = await perguntarIA({ ...pedido, json: true });
    try {
      return { ...extrairJson<T>(r.texto), _provedor: r.provedor };
    } catch (e) {
      ultimoErro = e;
    }
  }
  throw ultimoErro;
}

export function situacaoProvedores() {
  const hoje = dataLocalIso();
  const conf = lerConfiguracoes().ia;
  return PROVEDORES.map((p) => {
    const e = estado(p.id);
    const stats = um<{ total: number; ok: number; media: number }>(
      `SELECT COUNT(*) total, SUM(sucesso) ok, AVG(CASE WHEN sucesso = 1 THEN duracao_ms END) media
       FROM uso_ia WHERE provedor = ? AND criado_em >= datetime('now', '-1 day')`,
      p.id,
    );
    const pausado = Boolean(e.pausado_ate && e.pausado_ate > agoraSql());
    return {
      id: p.id,
      nome: p.nome,
      modelo: modeloDoProvedor(p),
      configurado: provedorConfigurado(p),
      podeTreinar: p.podeTreinar,
      local: Boolean(p.local),
      observacao: p.observacao,
      pausado,
      pausadoAte: pausado ? e.pausado_ate : null,
      motivo: pausado ? e.motivo : null,
      chamadasHoje: e.dia === hoje ? e.chamadas_dia : 0,
      limiteDiario: conf.limites_diarios[p.id] ?? null,
      chamadas24h: stats?.total ?? 0,
      sucesso24h: stats?.ok ?? 0,
      latenciaMediaMs: stats?.media ? Math.round(stats.media) : null,
      posicao: conf.ordem_provedores.indexOf(p.id),
    };
  });
}
