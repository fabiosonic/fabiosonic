// Cliente da API do painel.
export class ErroApi extends Error {
  status: number;
  constructor(status: number, mensagem: string) {
    super(mensagem);
    this.status = status;
  }
}

export async function api<T = any>(caminho: string, opcoes: { metodo?: string; corpo?: unknown } = {}): Promise<T> {
  const r = await fetch(caminho, {
    method: opcoes.metodo ?? (opcoes.corpo ? 'POST' : 'GET'),
    headers: opcoes.corpo ? { 'content-type': 'application/json' } : undefined,
    body: opcoes.corpo ? JSON.stringify(opcoes.corpo) : undefined,
    credentials: 'same-origin',
  });
  const dados = await r.json().catch(() => ({}));
  if (r.status === 401 && caminho !== '/api/entrar') window.dispatchEvent(new Event('sessao-expirada'));
  if (!r.ok) throw new ErroApi(r.status, dados.erro ?? `Erro ${r.status}`);
  return dados as T;
}

export type Etapa = { id: string; nome: string; descricao: string; agente: string };

export type LeadResumo = {
  id: number;
  etapa: string;
  pontuacao: number | null;
  temperatura: string | null;
  empresa: string;
  razaoSocial: string | null;
  cnpj: string;
  segmento: string | null;
  cidade: string | null;
  dataAbertura: string | null;
  origem: string;
  proximaAcao: string | null;
  proximaAcaoEm: string | null;
  atualizadoEm: string;
  criadoEm: string;
  ultimaMensagem: string | null;
};

export type Mensagem = {
  id: number;
  lead_id: number;
  canal: 'email' | 'whatsapp';
  direcao: 'saida' | 'entrada';
  assunto: string | null;
  corpo: string;
  status: string;
  agente: string | null;
  revisao: { aprovado?: boolean; problemas?: { trecho: string; regra: string; correcao: string }[]; etapas?: string[]; tipo?: string; fatos_usados?: string[] } | null;
  intencao: string | null;
  erro: string | null;
  enviada_em: string | null;
  criado_em: string;
  destino?: string;
};
