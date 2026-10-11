// Busca ativa de empresas recém-abertas nos Dados Abertos do CNPJ (Receita Federal).
// A Receita publica mensalmente todo o cadastro em arquivos .zip (CSV ";" latin1).
// Este módulo baixa os arquivos da competência, filtra pelo perfil de cliente
// ideal (UF, município, CNAE, data de abertura) e importa:
//   1) os estabelecimentos-alvo (viram leads);
//   2) os sócios dessas empresas;
//   3) as OUTRAS empresas desses mesmos sócios (grupo econômico, holdings),
//      usadas para personalizar a abordagem e dimensionar a complexidade.
// São dados públicos por lei; o uso para prospecção B2B fica registrado com
// origem e finalidade (LGPD art. 7º, IX — legítimo interesse, avaliado pelo responsável).
import { createWriteStream, existsSync, mkdirSync, renameSync, statSync, unlinkSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { createInterface } from 'node:readline';
import yauzl from 'yauzl';
import { config } from '../config.ts';
import { executar, todos, transacao, um } from '../banco.ts';
import type { Configuracoes } from '../configuracoes.ts';
import { log } from '../registro.ts';

/** Divide uma linha CSV da Receita (";" e aspas duplas). */
export function dividirLinha(linha: string): string[] {
  const campos: string[] = [];
  let atual = '';
  let aspas = false;
  for (let i = 0; i < linha.length; i++) {
    const ch = linha[i];
    if (ch === '"') {
      if (aspas && linha[i + 1] === '"') {
        atual += '"';
        i++;
      } else aspas = !aspas;
    } else if (ch === ';' && !aspas) {
      campos.push(atual);
      atual = '';
    } else atual += ch;
  }
  campos.push(atual);
  return campos;
}

export const FAIXA_ETARIA: Record<string, string> = {
  '1': '0 a 12 anos', '2': '13 a 20 anos', '3': '21 a 30 anos', '4': '31 a 40 anos', '5': '41 a 50 anos',
  '6': '51 a 60 anos', '7': '61 a 70 anos', '8': '71 a 80 anos', '9': 'Mais de 80 anos',
};
export const PORTE: Record<string, string> = { '00': 'NÃO INFORMADO', '01': 'MICRO EMPRESA', '03': 'EMPRESA DE PEQUENO PORTE', '05': 'DEMAIS' };

export type FiltroEstabelecimento = {
  ufs: Set<string>;
  municipios: Set<string> | null; // códigos de município da Receita
  cnaesPrefixos: string[];
  aberturaMinima: string; // AAAAMMDD
};

export type Estabelecimento = {
  cnpj: string;
  cnpj_basico: string;
  nome_fantasia: string;
  data_abertura: string;
  cnae_principal: string;
  logradouro: string;
  numero: string;
  bairro: string;
  cep: string;
  uf: string;
  municipio_codigo: string;
  telefone: string;
  email: string;
};

/** Converte e filtra uma linha de Estabelecimentos; retorna null se não for alvo. */
export function filtrarEstabelecimento(c: string[], f: FiltroEstabelecimento): Estabelecimento | null {
  if (c[3] !== '1' || c[5] !== '02') return null; // somente matriz e situação ATIVA
  if (f.ufs.size && !f.ufs.has(c[19])) return null;
  if (f.municipios && !f.municipios.has(c[20])) return null;
  if (!c[10] || c[10] < f.aberturaMinima) return null;
  if (f.cnaesPrefixos.length && !f.cnaesPrefixos.some((p) => c[11].startsWith(p))) return null;
  return {
    cnpj: `${c[0]}${c[1]}${c[2]}`,
    cnpj_basico: c[0],
    nome_fantasia: c[4],
    data_abertura: `${c[10].slice(0, 4)}-${c[10].slice(4, 6)}-${c[10].slice(6, 8)}`,
    cnae_principal: c[11],
    logradouro: [c[13], c[14]].filter(Boolean).join(' '),
    numero: c[15],
    bairro: c[17],
    cep: c[18],
    uf: c[19],
    municipio_codigo: c[20],
    telefone: `${c[21]}${c[22]}`,
    email: c[27]?.toLowerCase() ?? '',
  };
}

async function baixar(url: string, destino: string) {
  if (existsSync(destino) && statSync(destino).size > 0) return destino;
  const r = await fetch(url);
  if (!r.ok || !r.body) throw new Error(`Falha ao baixar ${url}: HTTP ${r.status}`);
  await pipeline(Readable.fromWeb(r.body as any), createWriteStream(destino + '.parcial'));
  renameSync(destino + '.parcial', destino);
  return destino;
}

/** Percorre linha a linha o CSV dentro de um .zip (decodificando latin1). */
export async function percorrerZip(caminho: string, aoLer: (campos: string[]) => void) {
  const zip = await new Promise<yauzl.ZipFile>((ok, erro) =>
    yauzl.open(caminho, { lazyEntries: true }, (e, z) => (e ? erro(e) : ok(z!))),
  );
  await new Promise<void>((ok, erro) => {
    zip.on('entry', (entrada: yauzl.Entry) => {
      zip.openReadStream(entrada, async (e, fluxo) => {
        if (e) return erro(e);
        fluxo!.setEncoding('latin1');
        const linhas = createInterface({ input: fluxo!, crlfDelay: Infinity });
        for await (const l of linhas) if (l) aoLer(dividirLinha(l));
        zip.readEntry();
      });
    });
    zip.on('end', ok);
    zip.on('error', erro);
    zip.readEntry();
  });
  zip.close();
}

function competenciaAtual(c: Configuracoes) {
  if (c.descoberta.competencia_rf) return c.descoberta.competencia_rf;
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - (d.getUTCDate() < 15 ? 1 : 0));
  return d.toISOString().slice(0, 7);
}

export type ResultadoDescoberta = { competencia: string; novas: number; socios: number; outrasEmpresas: number };

export async function descobrirNaReceita(
  c: Configuracoes,
  opcoes: { pastaArquivos?: string; arquivosLocais?: boolean; partes?: number } = {},
): Promise<ResultadoDescoberta> {
  const competencia = competenciaAtual(c);
  const pasta = opcoes.pastaArquivos ?? join(tmpdir(), 'rf-cnpj', competencia);
  mkdirSync(pasta, { recursive: true });
  const partes = opcoes.partes ?? 10;
  const arquivo = async (nome: string) => {
    const destino = join(pasta, nome);
    if (opcoes.arquivosLocais) return destino;
    return baixar(`${config.receita.urlDadosAbertos}/${competencia}/${nome}`, destino);
  };

  // Municípios: a Receita usa códigos próprios; traduzimos os nomes configurados.
  let municipios: Set<string> | null = null;
  const pi = c.perfil_cliente_ideal;
  if (pi.municipios.length) {
    const desejados = new Set(pi.municipios.map((m) => m.normalize('NFD').replace(/\p{M}/gu, '').toUpperCase().trim()));
    municipios = new Set();
    await percorrerZip(await arquivo('Municipios.zip'), (l) => {
      if (desejados.has(l[1].normalize('NFD').replace(/\p{M}/gu, '').toUpperCase().trim())) municipios!.add(l[0]);
    });
  }
  const nomesMunicipio = new Map<string, string>();
  await percorrerZip(await arquivo('Municipios.zip'), (l) => nomesMunicipio.set(l[0], l[1])).catch(() => undefined);

  const minima = new Date(Date.now() - pi.abertura_max_dias * 86_400_000).toISOString().slice(0, 10).replace(/-/g, '');
  const filtro: FiltroEstabelecimento = { ufs: new Set(pi.ufs), municipios, cnaesPrefixos: pi.cnaes_prefixos, aberturaMinima: minima };

  const alvos = new Map<string, Estabelecimento>();
  for (let i = 0; i < partes && alvos.size < c.descoberta.max_novas_por_execucao * 3; i++) {
    await percorrerZip(await arquivo(`Estabelecimentos${i}.zip`), (l) => {
      const e = filtrarEstabelecimento(l, filtro);
      if (e && !um('SELECT 1 FROM empresas WHERE cnpj = ?', e.cnpj)) alvos.set(e.cnpj_basico, e);
    });
    if (!opcoes.arquivosLocais) unlinkSync(join(pasta, `Estabelecimentos${i}.zip`));
  }
  const selecionados = [...alvos.values()].sort((a, b) => b.data_abertura.localeCompare(a.data_abertura)).slice(0, c.descoberta.max_novas_por_execucao);
  const basicos = new Set(selecionados.map((e) => e.cnpj_basico));
  log('prospector', `${selecionados.length} estabelecimentos novos no recorte da competência ${competencia}`);

  // Sócios das empresas-alvo e, em seguida, as outras empresas desses sócios.
  type LinhaSocio = { cnpj_basico: string; nome: string; doc: string; qualificacao: string; data_entrada: string; faixa: string };
  const sociosAlvo: LinhaSocio[] = [];
  const chavesSocio = new Set<string>();
  const outras: LinhaSocio[] = [];
  const converterSocio = (l: string[]): LinhaSocio => ({
    cnpj_basico: l[0], nome: l[2], doc: l[3], qualificacao: l[4],
    data_entrada: l[5] ? `${l[5].slice(0, 4)}-${l[5].slice(4, 6)}-${l[5].slice(6, 8)}` : '',
    faixa: FAIXA_ETARIA[l[10]] ?? '',
  });
  const arquivosSocios: string[] = [];
  for (let i = 0; i < partes; i++) {
    const caminho = await arquivo(`Socios${i}.zip`);
    arquivosSocios.push(caminho);
    await percorrerZip(caminho, (l) => {
      if (basicos.has(l[0]) && l[1] === '2') {
        const s = converterSocio(l);
        sociosAlvo.push(s);
        chavesSocio.add(`${s.nome}|${s.doc}`);
      }
    });
  }
  for (const caminho of arquivosSocios) {
    await percorrerZip(caminho, (l) => {
      if (!basicos.has(l[0]) && chavesSocio.has(`${l[2]}|${l[3]}`)) outras.push(converterSocio(l));
    });
    if (!opcoes.arquivosLocais) unlinkSync(caminho);
  }

  // Razão social, capital e porte das empresas-alvo e das relacionadas.
  const todasBasicas = new Set([...basicos, ...outras.map((o) => o.cnpj_basico)]);
  const empresasRf = new Map<string, { razao: string; capital: number; porte: string; natureza: string }>();
  for (let i = 0; i < partes; i++) {
    const caminho = await arquivo(`Empresas${i}.zip`);
    await percorrerZip(caminho, (l) => {
      if (todasBasicas.has(l[0])) empresasRf.set(l[0], { razao: l[1], natureza: l[2], capital: Number((l[4] || '0').replace(',', '.')), porte: PORTE[l[5]] ?? '' });
    });
    if (!opcoes.arquivosLocais) unlinkSync(caminho);
  }

  transacao(() => {
    for (const s of [...sociosAlvo, ...outras]) {
      executar(
        'INSERT INTO rf_socios (cnpj_basico, nome, documento_mascarado, qualificacao, data_entrada, faixa_etaria) VALUES (?, ?, ?, ?, ?, ?)',
        s.cnpj_basico, s.nome, s.doc, s.qualificacao, s.data_entrada, s.faixa,
      );
    }
    for (const [basico, e] of empresasRf) {
      executar(
        `INSERT INTO rf_empresas (cnpj_basico, razao_social, capital_social, porte) VALUES (?, ?, ?, ?)
         ON CONFLICT(cnpj_basico) DO UPDATE SET razao_social = excluded.razao_social, capital_social = excluded.capital_social, porte = excluded.porte`,
        basico, e.razao, e.capital, e.porte,
      );
    }
    for (const e of selecionados) {
      const rf = empresasRf.get(e.cnpj_basico);
      const nova = executar(
        `INSERT OR IGNORE INTO empresas (cnpj, razao_social, nome_fantasia, cnae_principal, data_abertura, situacao, porte, capital_social,
           logradouro, numero, bairro, cep, uf, municipio, email_cadastro, telefone_cadastro, origem, origem_detalhe)
         VALUES (?, ?, ?, ?, ?, 'ATIVA', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'receita_dados_abertos', ?)`,
        e.cnpj, rf?.razao ?? null, e.nome_fantasia || null, e.cnae_principal, e.data_abertura, rf?.porte ?? null, rf?.capital ?? null,
        e.logradouro, e.numero, e.bairro, e.cep, e.uf, nomesMunicipio.get(e.municipio_codigo) ?? e.municipio_codigo,
        e.email || null, e.telefone || null, `Dados Abertos CNPJ — competência ${competencia}`,
      );
      if (nova.alteradas) executar('INSERT OR IGNORE INTO leads (empresa_id, etapa) VALUES (?, ?)', nova.id, 'mapeada');
    }
  });

  return { competencia, novas: selecionados.length, socios: sociosAlvo.length, outrasEmpresas: outras.length };
}

/** Outras empresas em que o sócio aparece no recorte local dos dados abertos. */
export function outrasEmpresasDoSocio(nome: string, documentoMascarado: string | null, cnpjBasicoAtual: string) {
  const condicao = documentoMascarado ? 's.nome = ? AND s.documento_mascarado = ?' : 's.nome = ?';
  const parametros = documentoMascarado ? [nome.toUpperCase(), documentoMascarado] : [nome.toUpperCase()];
  return todos<{ cnpj_basico: string; razao_social: string | null; capital_social: number | null; porte: string | null; qualificacao: string; data_entrada: string }>(
    `SELECT DISTINCT s.cnpj_basico, e.razao_social, e.capital_social, e.porte, s.qualificacao, s.data_entrada
     FROM rf_socios s LEFT JOIN rf_empresas e ON e.cnpj_basico = s.cnpj_basico
     WHERE ${condicao} AND s.cnpj_basico <> ? LIMIT 20`,
    ...parametros,
    cnpjBasicoAtual,
  );
}
