// Banco SQLite embutido (node:sqlite). Um único arquivo, sem servidor extra:
// suficiente para o volume comercial de um escritório e fácil de copiar para backup.
import { DatabaseSync, type SQLInputValue } from 'node:sqlite';
import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { config } from './config.ts';

const ESQUEMA = `
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS configuracoes (
  chave TEXT PRIMARY KEY,
  valor TEXT NOT NULL,
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS empresas (
  id INTEGER PRIMARY KEY,
  cnpj TEXT UNIQUE NOT NULL,
  razao_social TEXT,
  nome_fantasia TEXT,
  cnae_principal TEXT,
  cnae_descricao TEXT,
  cnaes_secundarios TEXT DEFAULT '[]',
  natureza_juridica TEXT,
  porte TEXT,
  capital_social REAL,
  data_abertura TEXT,
  situacao TEXT,
  optante_simples INTEGER,
  optante_mei INTEGER,
  logradouro TEXT, numero TEXT, bairro TEXT, municipio TEXT, uf TEXT, cep TEXT,
  email_cadastro TEXT,
  telefone_cadastro TEXT,
  site TEXT,
  site_resumo TEXT,
  segmento TEXT,
  origem TEXT NOT NULL,
  origem_detalhe TEXT,
  enriquecida_em TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS socios (
  id INTEGER PRIMARY KEY,
  empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  nome TEXT NOT NULL,
  qualificacao TEXT,
  faixa_etaria TEXT,
  data_entrada TEXT,
  documento_mascarado TEXT,
  outras_empresas TEXT DEFAULT '[]',
  perfil_url TEXT,
  perfil_resumo TEXT,
  fatos_conversa TEXT DEFAULT '[]',
  origem TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(empresa_id, nome)
);

CREATE TABLE IF NOT EXISTS contatos (
  id INTEGER PRIMARY KEY,
  empresa_id INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  socio_id INTEGER REFERENCES socios(id) ON DELETE SET NULL,
  tipo TEXT NOT NULL CHECK (tipo IN ('email','whatsapp','telefone')),
  valor TEXT NOT NULL,
  origem TEXT NOT NULL,
  finalidade TEXT NOT NULL DEFAULT 'prospeccao_comercial_b2b',
  base_legal TEXT NOT NULL DEFAULT 'legitimo_interesse',
  optin INTEGER NOT NULL DEFAULT 0,
  provavel_contador INTEGER NOT NULL DEFAULT 0,
  bloqueado INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(empresa_id, tipo, valor)
);
CREATE INDEX IF NOT EXISTS ix_contatos_valor ON contatos(tipo, valor);

CREATE TABLE IF NOT EXISTS leads (
  id INTEGER PRIMARY KEY,
  empresa_id INTEGER UNIQUE NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
  etapa TEXT NOT NULL DEFAULT 'mapeada',
  pontuacao INTEGER,
  pontuacao_motivos TEXT DEFAULT '[]',
  temperatura TEXT,
  necessidades TEXT DEFAULT '[]',
  resumo_ia TEXT,
  passo_cadencia INTEGER NOT NULL DEFAULT 0,
  proxima_acao TEXT,
  proxima_acao_em TEXT,
  turnos_automaticos INTEGER NOT NULL DEFAULT 0,
  motivo_perda TEXT,
  valor_estimado REAL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  atualizado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_leads_etapa ON leads(etapa, proxima_acao_em);

CREATE TABLE IF NOT EXISTS mensagens (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  contato_id INTEGER REFERENCES contatos(id) ON DELETE SET NULL,
  canal TEXT NOT NULL CHECK (canal IN ('email','whatsapp')),
  direcao TEXT NOT NULL CHECK (direcao IN ('saida','entrada')),
  assunto TEXT,
  corpo TEXT NOT NULL,
  status TEXT NOT NULL,
  agente TEXT,
  revisao TEXT,
  intencao TEXT,
  id_externo TEXT,
  em_resposta_a TEXT,
  erro TEXT,
  agendada_para TEXT,
  enviada_em TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_mensagens_lead ON mensagens(lead_id, criado_em);
CREATE INDEX IF NOT EXISTS ix_mensagens_status ON mensagens(status);
CREATE INDEX IF NOT EXISTS ix_mensagens_externo ON mensagens(id_externo);

CREATE TABLE IF NOT EXISTS atendimentos_humanos (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
  motivo TEXT NOT NULL,
  resumo TEXT,
  mensagem_id INTEGER REFERENCES mensagens(id) ON DELETE SET NULL,
  status TEXT NOT NULL DEFAULT 'aberto',
  notificado INTEGER NOT NULL DEFAULT 0,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  resolvido_em TEXT
);

CREATE TABLE IF NOT EXISTS eventos (
  id INTEGER PRIMARY KEY,
  lead_id INTEGER REFERENCES leads(id) ON DELETE CASCADE,
  tipo TEXT NOT NULL,
  agente TEXT,
  detalhe TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_eventos_lead ON eventos(lead_id, criado_em);
CREATE INDEX IF NOT EXISTS ix_eventos_data ON eventos(criado_em);

CREATE TABLE IF NOT EXISTS bloqueios (
  valor TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,
  motivo TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS uso_ia (
  id INTEGER PRIMARY KEY,
  provedor TEXT NOT NULL,
  modelo TEXT,
  tarefa TEXT,
  sucesso INTEGER NOT NULL,
  status_http INTEGER,
  erro TEXT,
  tokens_entrada INTEGER,
  tokens_saida INTEGER,
  duracao_ms INTEGER,
  criado_em TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_uso_ia_data ON uso_ia(criado_em);

CREATE TABLE IF NOT EXISTS estado_provedores (
  provedor TEXT PRIMARY KEY,
  pausado_ate TEXT,
  motivo TEXT,
  chamadas_dia INTEGER NOT NULL DEFAULT 0,
  dia TEXT
);

CREATE TABLE IF NOT EXISTS execucoes_agentes (
  id INTEGER PRIMARY KEY,
  agente TEXT NOT NULL,
  inicio TEXT NOT NULL,
  fim TEXT,
  sucesso INTEGER,
  processados INTEGER DEFAULT 0,
  resumo TEXT
);
CREATE INDEX IF NOT EXISTS ix_execucoes_agente ON execucoes_agentes(agente, inicio);

-- Recorte local dos dados abertos do CNPJ (Receita Federal) para cruzar sócios
-- com outras empresas. Só são importadas as linhas do recorte configurado.
CREATE TABLE IF NOT EXISTS rf_socios (
  cnpj_basico TEXT NOT NULL,
  nome TEXT NOT NULL,
  documento_mascarado TEXT,
  qualificacao TEXT,
  data_entrada TEXT,
  faixa_etaria TEXT
);
CREATE INDEX IF NOT EXISTS ix_rf_socios_nome ON rf_socios(nome, documento_mascarado);
CREATE INDEX IF NOT EXISTS ix_rf_socios_cnpj ON rf_socios(cnpj_basico);

CREATE TABLE IF NOT EXISTS rf_empresas (
  cnpj_basico TEXT PRIMARY KEY,
  razao_social TEXT,
  capital_social REAL,
  porte TEXT
);
`;

let instancia: DatabaseSync | null = null;

export function banco(): DatabaseSync {
  if (instancia) return instancia;
  if (config.caminhoBanco !== ':memory:') mkdirSync(dirname(config.caminhoBanco), { recursive: true });
  instancia = new DatabaseSync(config.caminhoBanco);
  instancia.exec(ESQUEMA);
  return instancia;
}

/** Usado pelos testes para recomeçar com um banco limpo em memória. */
export function reiniciarBanco(caminho = ':memory:') {
  instancia?.close();
  instancia = new DatabaseSync(caminho);
  instancia.exec(ESQUEMA);
  return instancia;
}

type Parametro = SQLInputValue | boolean | undefined;
const normalizar = (p: Parametro[]) =>
  p.map((v) => (v === undefined ? null : typeof v === 'boolean' ? (v ? 1 : 0) : v)) as SQLInputValue[];

export function todos<T = Record<string, any>>(sql: string, ...p: Parametro[]): T[] {
  return banco().prepare(sql).all(...normalizar(p)) as T[];
}

export function um<T = Record<string, any>>(sql: string, ...p: Parametro[]): T | undefined {
  return banco().prepare(sql).get(...normalizar(p)) as T | undefined;
}

export function executar(sql: string, ...p: Parametro[]) {
  const r = banco().prepare(sql).run(...normalizar(p));
  return { alteradas: Number(r.changes), id: Number(r.lastInsertRowid) };
}

export function transacao<T>(fn: () => T): T {
  const b = banco();
  b.exec('BEGIN');
  try {
    const r = fn();
    b.exec('COMMIT');
    return r;
  } catch (e) {
    b.exec('ROLLBACK');
    throw e;
  }
}

export const json = <T>(texto: string | null | undefined, padrao: T): T => {
  if (!texto) return padrao;
  try {
    return JSON.parse(texto) as T;
  } catch {
    return padrao;
  }
};
