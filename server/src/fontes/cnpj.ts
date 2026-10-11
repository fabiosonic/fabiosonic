// Consulta cadastral do CNPJ em APIs gratuitas, com o mesmo princípio do
// roteador de IA: se uma fonte falhar ou limitar, tenta a próxima.
// Todas retornam dados públicos do cadastro da Receita Federal (inclusive o
// quadro de sócios e administradores — QSA).
import { somenteDigitos } from '../util/texto.ts';

export type SocioCadastro = {
  nome: string;
  qualificacao: string | null;
  faixa_etaria: string | null;
  data_entrada: string | null;
  documento_mascarado: string | null;
};

export type CadastroCnpj = {
  cnpj: string;
  razao_social: string | null;
  nome_fantasia: string | null;
  cnae_principal: string | null;
  cnae_descricao: string | null;
  cnaes_secundarios: { codigo: string; descricao: string }[];
  natureza_juridica: string | null;
  porte: string | null;
  capital_social: number | null;
  data_abertura: string | null;
  situacao: string | null;
  optante_simples: boolean | null;
  optante_mei: boolean | null;
  logradouro: string | null;
  numero: string | null;
  bairro: string | null;
  municipio: string | null;
  uf: string | null;
  cep: string | null;
  email: string | null;
  telefones: string[];
  socios: SocioCadastro[];
  fonte: string;
};

let fetchImpl: typeof fetch = (...a) => fetch(...a);
export const definirFetchCnpj = (f: typeof fetch) => (fetchImpl = f);

const brParaIso = (d?: string | null) => {
  if (!d) return null;
  const m = d.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : d.slice(0, 10);
};
const nulo = (v: unknown) => (v === undefined || v === null || v === '' ? null : String(v));

function deBrasilApi(d: any): CadastroCnpj {
  return {
    cnpj: somenteDigitos(d.cnpj),
    razao_social: nulo(d.razao_social),
    nome_fantasia: nulo(d.nome_fantasia),
    cnae_principal: nulo(d.cnae_fiscal),
    cnae_descricao: nulo(d.cnae_fiscal_descricao),
    cnaes_secundarios: (d.cnaes_secundarios ?? []).filter((c: any) => c.codigo).map((c: any) => ({ codigo: String(c.codigo), descricao: c.descricao })),
    natureza_juridica: nulo(d.natureza_juridica),
    porte: nulo(d.porte),
    capital_social: d.capital_social != null ? Number(d.capital_social) : null,
    data_abertura: nulo(d.data_inicio_atividade),
    situacao: nulo(d.descricao_situacao_cadastral),
    optante_simples: d.opcao_pelo_simples ?? null,
    optante_mei: d.opcao_pelo_mei ?? null,
    logradouro: nulo([d.descricao_tipo_de_logradouro, d.logradouro].filter(Boolean).join(' ')),
    numero: nulo(d.numero),
    bairro: nulo(d.bairro),
    municipio: nulo(d.municipio),
    uf: nulo(d.uf),
    cep: nulo(d.cep),
    email: nulo(d.email),
    telefones: [d.ddd_telefone_1, d.ddd_telefone_2].map(somenteDigitos).filter(Boolean),
    socios: (d.qsa ?? []).map((s: any) => ({
      nome: s.nome_socio,
      qualificacao: nulo(s.qualificacao_socio),
      faixa_etaria: nulo(s.faixa_etaria),
      data_entrada: nulo(s.data_entrada_sociedade),
      documento_mascarado: nulo(s.cnpj_cpf_do_socio),
    })),
    fonte: 'BrasilAPI',
  };
}

function deCnpjWs(d: any): CadastroCnpj {
  const e = d.estabelecimento ?? {};
  return {
    cnpj: somenteDigitos(e.cnpj),
    razao_social: nulo(d.razao_social),
    nome_fantasia: nulo(e.nome_fantasia),
    cnae_principal: nulo(e.atividade_principal?.id),
    cnae_descricao: nulo(e.atividade_principal?.descricao),
    cnaes_secundarios: (e.atividades_secundarias ?? []).map((a: any) => ({ codigo: String(a.id), descricao: a.descricao })),
    natureza_juridica: nulo(d.natureza_juridica?.descricao),
    porte: nulo(d.porte?.descricao)?.toUpperCase() ?? null,
    capital_social: d.capital_social != null ? Number(d.capital_social) : null,
    data_abertura: nulo(e.data_inicio_atividade),
    situacao: nulo(e.situacao_cadastral)?.toUpperCase() ?? null,
    optante_simples: d.simples ? d.simples.simples === 'Sim' : null,
    optante_mei: d.simples ? d.simples.mei === 'Sim' : null,
    logradouro: nulo([e.tipo_logradouro, e.logradouro].filter(Boolean).join(' ')),
    numero: nulo(e.numero),
    bairro: nulo(e.bairro),
    municipio: nulo(e.cidade?.nome),
    uf: nulo(e.estado?.sigla),
    cep: nulo(e.cep),
    email: nulo(e.email),
    telefones: [`${e.ddd1 ?? ''}${e.telefone1 ?? ''}`, `${e.ddd2 ?? ''}${e.telefone2 ?? ''}`].map(somenteDigitos).filter(Boolean),
    socios: (d.socios ?? []).map((s: any) => ({
      nome: s.nome,
      qualificacao: nulo(s.qualificacao_socio?.descricao),
      faixa_etaria: nulo(s.faixa_etaria),
      data_entrada: nulo(s.data_entrada),
      documento_mascarado: nulo(s.cpf_cnpj_socio),
    })),
    fonte: 'CNPJ.ws',
  };
}

function deReceitaWs(d: any): CadastroCnpj {
  if (d.status === 'ERROR') throw new Error(d.message ?? 'erro ReceitaWS');
  return {
    cnpj: somenteDigitos(d.cnpj),
    razao_social: nulo(d.nome),
    nome_fantasia: nulo(d.fantasia),
    cnae_principal: nulo(somenteDigitos(d.atividade_principal?.[0]?.code)),
    cnae_descricao: nulo(d.atividade_principal?.[0]?.text),
    cnaes_secundarios: (d.atividades_secundarias ?? []).map((a: any) => ({ codigo: somenteDigitos(a.code), descricao: a.text })),
    natureza_juridica: nulo(d.natureza_juridica),
    porte: nulo(d.porte),
    capital_social: d.capital_social != null ? Number(d.capital_social) : null,
    data_abertura: brParaIso(d.abertura),
    situacao: nulo(d.situacao),
    optante_simples: d.simples ? Boolean(d.simples.optante) : null,
    optante_mei: d.simei ? Boolean(d.simei.optante) : null,
    logradouro: nulo(d.logradouro),
    numero: nulo(d.numero),
    bairro: nulo(d.bairro),
    municipio: nulo(d.municipio),
    uf: nulo(d.uf),
    cep: nulo(somenteDigitos(d.cep)),
    email: nulo(d.email),
    telefones: String(d.telefone ?? '')
      .split('/')
      .map(somenteDigitos)
      .filter(Boolean),
    socios: (d.qsa ?? []).map((s: any) => ({ nome: s.nome, qualificacao: nulo(s.qual), faixa_etaria: null, data_entrada: null, documento_mascarado: null })),
    fonte: 'ReceitaWS',
  };
}

const FONTES = [
  { nome: 'BrasilAPI', url: (c: string) => `https://brasilapi.com.br/api/cnpj/v1/${c}`, converter: deBrasilApi },
  { nome: 'CNPJ.ws', url: (c: string) => `https://publica.cnpj.ws/cnpj/${c}`, converter: deCnpjWs },
  { nome: 'ReceitaWS', url: (c: string) => `https://receitaws.com.br/v1/cnpj/${c}`, converter: deReceitaWs },
];

const pausadaAte = new Map<string, number>();

export class CnpjNaoEncontrado extends Error {}

export async function consultarCnpj(cnpj: string): Promise<CadastroCnpj> {
  const c = somenteDigitos(cnpj);
  const erros: string[] = [];
  for (const f of FONTES) {
    if ((pausadaAte.get(f.nome) ?? 0) > Date.now()) {
      erros.push(`${f.nome}: pausada`);
      continue;
    }
    try {
      const r = await fetchImpl(f.url(c), { headers: { accept: 'application/json', 'user-agent': 'CentralComercial/1.0' }, signal: AbortSignal.timeout(20000) });
      if (r.status === 404) throw new CnpjNaoEncontrado(`CNPJ ${c} não encontrado`);
      if (r.status === 429) {
        pausadaAte.set(f.nome, Date.now() + 65_000);
        erros.push(`${f.nome}: limite de consultas`);
        continue;
      }
      if (!r.ok) {
        pausadaAte.set(f.nome, Date.now() + 5 * 60_000);
        erros.push(`${f.nome}: HTTP ${r.status}`);
        continue;
      }
      const dados = f.converter(await r.json());
      if (!dados.cnpj) dados.cnpj = c;
      return dados;
    } catch (e) {
      if (e instanceof CnpjNaoEncontrado) throw e;
      pausadaAte.set(f.nome, Date.now() + 2 * 60_000); // rede instável: descansa a fonte
      erros.push(`${f.nome}: ${(e as Error).message}`);
    }
  }
  throw new Error(`Consulta de CNPJ indisponível (${erros.join('; ')})`);
}

export const _conversores = { deBrasilApi, deCnpjWs, deReceitaWs };
