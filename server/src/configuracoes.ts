// Configurações de negócio editáveis pelo painel. Valores padrão conservadores:
// o sistema nasce em modo "aprovação" (você aprova as mensagens até confiar nos
// textos) e só passa a enviar sozinho quando você mudar para "automático".
import { executar, json, todos } from './banco.ts';

export type EtapaCadencia = {
  passo: number;
  dia: number;
  canal: 'email' | 'whatsapp';
  tipo: 'primeiro_contato' | 'lembrete' | 'acompanhamento' | 'ultimo_contato';
};

export type Configuracoes = {
  escritorio: {
    nome: string;
    razao_social: string;
    cnpj: string;
    crc_organizacao: string;
    responsavel_tecnico: { nome: string; categoria: string; crc: string };
    telefone: string;
    site: string;
    cidade: string;
    cargo_assinatura: string;
  };
  servicos: string[];
  diferenciais_comprovados: string[];
  perfil_cliente_ideal: {
    ufs: string[];
    municipios: string[];
    cnaes_prefixos: string[];
    segmentos: string[];
    abertura_max_dias: number;
    excluir_mei: boolean;
    portes: string[];
    capital_minimo: number;
  };
  pontuacao_minima: number;
  cadencia: EtapaCadencia[];
  limites: { emails_dia: number; emails_hora: number; whatsapp_dia: number; intervalo_min_segundos: number };
  horario_envio: { dias_semana: number[]; inicio: string; fim: string };
  autonomia: { modo: 'aprovacao' | 'automatico'; max_turnos_automaticos: number };
  ia: { ordem_provedores: string[]; privacidade_estrita: boolean; limites_diarios: Record<string, number> };
  descoberta: { receita_dados_abertos: boolean; competencia_rf: string; lote_enriquecimento: number; max_novas_por_execucao: number };
  whatsapp: { primeiro_contato_somente_optin: boolean };
};

export const PADRAO: Configuracoes = {
  escritorio: {
    nome: 'Moraes & Oliveira Contabilidade',
    razao_social: '',
    cnpj: '',
    crc_organizacao: '',
    responsavel_tecnico: { nome: '', categoria: 'Contador', crc: '' },
    telefone: '',
    site: '',
    cidade: '',
    cargo_assinatura: 'Equipe comercial',
  },
  servicos: [],
  diferenciais_comprovados: [],
  perfil_cliente_ideal: {
    ufs: [],
    municipios: [],
    cnaes_prefixos: [],
    segmentos: ['Comércio e e-commerce', 'Serviços profissionais e tecnologia', 'Saúde', 'Indústria', 'Construção e imobiliário'],
    abertura_max_dias: 120,
    excluir_mei: true,
    portes: ['MICRO EMPRESA', 'EMPRESA DE PEQUENO PORTE', 'DEMAIS'],
    capital_minimo: 0,
  },
  pontuacao_minima: 55,
  cadencia: [
    { passo: 1, dia: 0, canal: 'email', tipo: 'primeiro_contato' },
    { passo: 2, dia: 3, canal: 'whatsapp', tipo: 'lembrete' },
    { passo: 3, dia: 7, canal: 'email', tipo: 'acompanhamento' },
    { passo: 4, dia: 14, canal: 'email', tipo: 'ultimo_contato' },
  ],
  limites: { emails_dia: 40, emails_hora: 10, whatsapp_dia: 20, intervalo_min_segundos: 90 },
  horario_envio: { dias_semana: [1, 2, 3, 4, 5], inicio: '08:30', fim: '18:00' },
  autonomia: { modo: 'aprovacao', max_turnos_automaticos: 4 },
  ia: {
    ordem_provedores: ['groq', 'cerebras', 'gemini', 'openrouter', 'sambanova', 'mistral', 'github', 'cloudflare', 'ollama'],
    privacidade_estrita: true,
    limites_diarios: { groq: 900, cerebras: 900, gemini: 450, openrouter: 45, sambanova: 300, mistral: 500, github: 140, cloudflare: 300 },
  },
  descoberta: { receita_dados_abertos: false, competencia_rf: '', lote_enriquecimento: 20, max_novas_por_execucao: 200 },
  whatsapp: { primeiro_contato_somente_optin: true },
};

function mesclar<T>(base: T, extra: unknown): T {
  if (Array.isArray(base) || typeof base !== 'object' || base === null) return (extra ?? base) as T;
  const saida: Record<string, unknown> = { ...(base as Record<string, unknown>) };
  if (extra && typeof extra === 'object' && !Array.isArray(extra)) {
    for (const [k, v] of Object.entries(extra)) saida[k] = k in saida ? mesclar(saida[k], v) : v;
  }
  return saida as T;
}

export function lerConfiguracoes(): Configuracoes {
  const linhas = todos<{ chave: string; valor: string }>('SELECT chave, valor FROM configuracoes');
  const salvo: Record<string, unknown> = {};
  for (const l of linhas) salvo[l.chave] = json(l.valor, null);
  return mesclar(PADRAO, salvo);
}

export function salvarConfiguracoes(parcial: Partial<Configuracoes>) {
  const chaves = Object.keys(PADRAO) as (keyof Configuracoes)[];
  for (const chave of chaves) {
    if (!(chave in parcial)) continue;
    executar(
      `INSERT INTO configuracoes (chave, valor) VALUES (?, ?)
       ON CONFLICT(chave) DO UPDATE SET valor = excluded.valor, atualizado_em = datetime('now')`,
      chave,
      JSON.stringify(parcial[chave]),
    );
  }
  return lerConfiguracoes();
}

/** Campos de identificação exigidos pela NBC PG 01 (item 4(r)) e orientação do CFC antes de qualquer peça externa. */
export function pendenciasIdentificacao(c: Configuracoes): string[] {
  const p: string[] = [];
  if (!c.escritorio.nome) p.push('Nome do escritório');
  if (!c.escritorio.cnpj) p.push('CNPJ do escritório');
  if (!c.escritorio.crc_organizacao) p.push('Registro CRC da organização');
  if (!c.escritorio.responsavel_tecnico.nome) p.push('Nome do responsável técnico');
  if (!c.escritorio.responsavel_tecnico.crc) p.push('CRC do responsável técnico');
  if (c.servicos.length === 0) p.push('Serviços comercializáveis');
  return p;
}
