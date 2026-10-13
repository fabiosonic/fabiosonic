// Verificação do site M&O Contábil DIGITAL (somente módulos nativos do Node).
// Uso, a partir da raiz do projeto:  node scripts/verificar-site.mjs
// Erros mudam o código de saída para 1. Avisos são apenas informativos.

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const DOMINIO = 'https://moraeseoliveiracontabil.com.br/';
const WA_PHONE = '5521998806423';
const FRASE_LEGAL = 'Conteúdo informativo. Cada caso depende de atividade, faturamento e estrutura societária.';
const REVISAO = 'revisado em 13/10/2026';
const IGNORAR_DIRS = new Set(['node_modules', '.git', 'docs']);
const EXCLUIR_SCAN_DIRS = new Set(['docs', 'scripts', 'node_modules', '.git']);
const REGEX_PROIBIDAS = /grátis|gratuit|desconto|promoç|melhor|nº 1|número 1|garant|econom|últimas vagas|franklin|líder/i;
const SEM_CANONICAL_OBRIGATORIO = new Set(['404.html', 'links.html']);
const SEM_CTA_WHATSAPP = new Set(['index.html', 'links.html', 'politica-de-privacidade.html']);
const NAO_INDEXAR_NO_SITEMAP = new Set(['links.html', '404.html']);

const erros = [];
const avisos = [];

function erro(arquivo, msg) { erros.push({ arquivo, msg }); }
function aviso(arquivo, msg) { avisos.push({ arquivo, msg }); }

function relativo(abs) { return path.relative(ROOT, abs).split(path.sep).join('/'); }

// Percorre a árvore do projeto e devolve caminhos absolutos de arquivos.
function listarArquivos(dir, saida = []) {
  for (const nome of fs.readdirSync(dir, { withFileTypes: true })) {
    if (nome.isDirectory()) {
      if (IGNORAR_DIRS.has(nome.name)) continue;
      listarArquivos(path.join(dir, nome.name), saida);
    } else if (nome.isFile()) {
      saida.push(path.join(dir, nome.name));
    }
  }
  return saida;
}

const todos = listarArquivos(ROOT);
const paginas = todos.filter((f) => f.endsWith('.html')).sort();
const textos = todos.filter((f) => {
  const r = relativo(f).split('/');
  if (r.some((p) => EXCLUIR_SCAN_DIRS.has(p))) return false;
  return f.endsWith('.html') || f.endsWith('.txt');
}).sort();

function decodificar(s) {
  return s
    .replace(/&nbsp;/g, ' ')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&amp;/g, '&');
}

function textoPlano(s) {
  return decodificar(s.replace(/<[^>]*>/g, '')).replace(/\s+/g, ' ').trim();
}

// Lê atributos de uma tag de abertura, ex.: <a href="x" rel="y">.
function atributos(tag) {
  const out = {};
  const re = /([\w:-]+)\s*=\s*"([^"]*)"|([\w:-]+)\s*=\s*'([^']*)'/g;
  let m;
  while ((m = re.exec(tag)) !== null) {
    if (m[1] !== undefined) out[m[1].toLowerCase()] = m[2];
    else out[m[3].toLowerCase()] = m[4];
  }
  return out;
}

function metaConteudo(html, nome, valor) {
  const tags = html.match(/<meta\b[^>]*>/gi) || [];
  for (const t of tags) {
    const a = atributos(t);
    if (a[nome] && a[nome].toLowerCase() === valor.toLowerCase()) return a.content ?? null;
  }
  return undefined;
}

function escapeRegex(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

// Coleta nós do JSON-LD em qualquer profundidade.
function percorrerJsonLd(obj, visita) {
  if (Array.isArray(obj)) { obj.forEach((o) => percorrerJsonLd(o, visita)); return; }
  if (obj && typeof obj === 'object') {
    visita(obj);
    Object.values(obj).forEach((v) => percorrerJsonLd(v, visita));
  }
}

function temTipo(no, tipo) {
  const t = no['@type'];
  return Array.isArray(t) ? t.includes(tipo) : t === tipo;
}

// Resolve um href/src interno para um caminho absoluto no disco.
function resolverInterno(arquivoAbs, valor) {
  const idxHash = valor.indexOf('#');
  const ancora = idxHash >= 0 ? valor.slice(idxHash + 1) : undefined;
  const semHash = idxHash >= 0 ? valor.slice(0, idxHash) : valor;
  const caminho = semHash.split('?')[0];
  const base = caminho.startsWith('/') ? ROOT : path.dirname(arquivoAbs);
  let destino = caminho === ''
    ? arquivoAbs
    : path.join(base, decodeURIComponentSegura(caminho.replace(/^\//, '')));
  if (caminho.endsWith('/')) destino = path.join(destino, 'index.html');
  else if (fs.existsSync(destino) && fs.statSync(destino).isDirectory()) destino = path.join(destino, 'index.html');
  return { destino, ancora, caminho };
}

function decodeURIComponentSegura(s) {
  try { return decodeURIComponent(s); } catch { return s; }
}

const EXTERNO = /^(https?:|mailto:|tel:|javascript:|data:|\/\/)/i;

for (const arq of paginas) {
  const rel = relativo(arq);
  const html = fs.readFileSync(arq, 'utf8');
  const ehPaginaRaiz = rel === 'index.html';
  const h1s = (html.match(/<h1\b/gi) || []).length;

  // (2) Estrutura básica
  if (h1s !== 1) erro(rel, `h1: encontrado ${h1s}, esperado 1`);
  if (!/<html\b[^>]*\blang="pt-BR"/i.test(html)) erro(rel, 'lang="pt-BR" ausente em <html>');

  const titulo = html.match(/<title>([\s\S]*?)<\/title>/i);
  if (!titulo) erro(rel, '<title> ausente');
  else if (textoPlano(titulo[1]).length > 60) aviso(rel, `<title> com ${textoPlano(titulo[1]).length} caracteres (máximo 60)`);

  const desc = metaConteudo(html, 'name', 'description');
  if (desc === undefined) aviso(rel, 'meta description ausente');
  else if (decodificar(desc).length > 155) aviso(rel, `meta description com ${decodificar(desc).length} caracteres (máximo 155)`);

  const canonical = (html.match(/<link\b[^>]*>/gi) || []).map(atributos).find((a) => a.rel === 'canonical');
  if (!SEM_CANONICAL_OBRIGATORIO.has(rel)) {
    if (!canonical || !canonical.href) erro(rel, 'canonical ausente');
    else if (!canonical.href.startsWith(DOMINIO)) erro(rel, `canonical não absoluto em ${DOMINIO}: ${canonical.href}`);
  }

  if (metaConteudo(html, 'property', 'og:image') === undefined) aviso(rel, 'og:image ausente');
  if (!/class="[^"]*\bskip-link\b/.test(html)) aviso(rel, 'skip-link ausente');
  if (rel === '404.html') {
    const robots = metaConteudo(html, 'name', 'robots') || '';
    if (!/noindex/i.test(robots)) erro(rel, '404.html deve ter meta robots noindex');
  }

  // (3) JSON-LD
  const blocos = [...html.matchAll(/<script\b[^>]*type="application\/ld\+json"[^>]*>([\s\S]*?)<\/script>/gi)];
  const nomesPerguntas = [];
  let temFaq = false;
  for (const b of blocos) {
    let json;
    try {
      json = JSON.parse(b[1]);
    } catch (e) {
      erro(rel, `JSON-LD inválido: ${e.message}`);
      continue;
    }
    percorrerJsonLd(json, (no) => {
      if (temTipo(no, 'FAQPage')) temFaq = true;
      if (temTipo(no, 'Question') && typeof no.name === 'string') nomesPerguntas.push(no.name);
    });
  }
  if (temFaq) {
    const summaries = [...html.matchAll(/<summary\b[^>]*>([\s\S]*?)<\/summary>/gi)].map((m) => textoPlano(m[1]));
    for (const nome of nomesPerguntas) {
      if (!summaries.includes(textoPlano(nome))) erro(rel, `FAQPage: pergunta não aparece em <summary>: "${nome}"`);
    }
  }

  // (4) Links e imagens internos
  const tags = html.match(/<[a-zA-Z][^>]*>/g) || [];
  for (const t of tags) {
    const a = atributos(t);
    for (const attr of ['href', 'src']) {
      const valor = a[attr];
      if (valor === undefined) continue;
      const v = valor.trim();
      if (v === '' || v === '#' || EXTERNO.test(v)) continue;
      const { destino, ancora, caminho } = resolverInterno(arq, v);
      if (!fs.existsSync(destino)) {
        erro(rel, `${attr} quebrado: "${valor}" (procurado em ${relativo(destino)})`);
        continue;
      }
      if (ancora !== undefined && ancora !== '' && caminho !== '' && destino.endsWith('.html')) {
        const alvo = fs.readFileSync(destino, 'utf8');
        const re = new RegExp(`\\sid\\s*=\\s*["']${escapeRegex(ancora)}["']`);
        if (!re.test(alvo)) erro(rel, `âncora inexistente: "${valor}" (id="${ancora}" ausente em ${relativo(destino)})`);
      }
    }
  }

  // (6) Nota legal em páginas com conteúdo tributário
  const minusc = html.toLowerCase();
  const tributario = ['lc 123', 'lc 214', 'ec 132', 'simples nacional', 'tribut'].some((k) => minusc.includes(k));
  if (tributario) {
    const faltas = [];
    if (!minusc.includes(FRASE_LEGAL.toLowerCase())) faltas.push(`frase exata "${FRASE_LEGAL}"`);
    if (!minusc.includes(REVISAO)) faltas.push(`"${REVISAO}"`);
    if (faltas.length) {
      const msg = `conteúdo tributário sem: ${faltas.join(' e ')}`;
      if (ehPaginaRaiz) aviso(rel, msg); else erro(rel, msg);
    }
  }

  // (7) CTA de WhatsApp em páginas novas
  if (!SEM_CTA_WHATSAPP.has(rel)) {
    const anchors = [...html.matchAll(/<a\b([^>]*)>([\s\S]*?)<\/a>/gi)];
    const ok = anchors.some((m) => {
      const a = atributos(`<a ${m[1]}>`);
      const txt = textoPlano(m[2]);
      const href = a.href || '';
      const wa = href.includes(`api.whatsapp.com/send?phone=${WA_PHONE}`) || href.includes(`wa.me/${WA_PHONE}`);
      const rel_ = (a.rel || '').toLowerCase();
      return txt.includes('Conversar com um contador') && wa && a.target === '_blank' && rel_.includes('noopener');
    });
    if (!ok) erro(rel, 'CTA "Conversar com um contador" (WhatsApp, target="_blank", rel noopener) ausente');
  }
}

// (5) Varredura de termos proibidos e de "R$" em .html e .txt
for (const arq of textos) {
  const rel = relativo(arq);
  const linhas = fs.readFileSync(arq, 'utf8').split('\n');
  linhas.forEach((linha, i) => {
    const m = linha.match(REGEX_PROIBIDAS);
    if (m) aviso(rel, `linha ${i + 1}: termo a justificar "${m[0]}": ${linha.trim().slice(0, 140)}`);
    if (linha.includes('R$')) aviso(rel, `linha ${i + 1}: valor "R$" encontrado: ${linha.trim().slice(0, 140)}`);
  });
}

// (8) Sitemap
const caminhoSitemap = path.join(ROOT, 'sitemap.xml');
if (fs.existsSync(caminhoSitemap)) {
  const xml = fs.readFileSync(caminhoSitemap, 'utf8');
  const urls = [...xml.matchAll(/<loc>\s*([^<]+?)\s*<\/loc>/gi)].map((m) => m[1]);
  const noSitemap = new Set();
  for (const u of urls) {
    if (!u.startsWith(DOMINIO)) { erro('sitemap.xml', `URL fora do domínio canônico: ${u}`); continue; }
    let caminho = u.slice(DOMINIO.length).split('?')[0].split('#')[0];
    if (caminho === '' || caminho.endsWith('/')) caminho += 'index.html';
    const nomeBase = path.basename(caminho);
    if (nomeBase === 'links.html' || nomeBase === '404.html') erro('sitemap.xml', `URL não deve estar no sitemap: ${u}`);
    const alvo = path.join(ROOT, caminho);
    if (!fs.existsSync(alvo)) erro('sitemap.xml', `URL sem arquivo correspondente: ${u}`);
    noSitemap.add(caminho);
  }
  for (const arq of paginas) {
    const rel = relativo(arq);
    if (NAO_INDEXAR_NO_SITEMAP.has(rel)) continue;
    const html = fs.readFileSync(arq, 'utf8');
    const robots = metaConteudo(html, 'name', 'robots') || '';
    if (/noindex/i.test(robots)) continue;
    if (!noSitemap.has(rel)) aviso(rel, 'página indexável que não está no sitemap.xml');
  }
} else {
  aviso('sitemap.xml', 'sitemap.xml não encontrado');
}

// (9) Resumo
const porArquivo = (lista) => {
  const mapa = new Map();
  for (const item of lista) {
    if (!mapa.has(item.arquivo)) mapa.set(item.arquivo, []);
    mapa.get(item.arquivo).push(item.msg);
  }
  return mapa;
};

console.log(`Páginas HTML encontradas: ${paginas.length}`);
console.log(paginas.map(relativo).map((p) => `  - ${p}`).join('\n'));
console.log('');

if (erros.length) {
  console.log('ERROS:');
  for (const [arq, msgs] of porArquivo(erros)) msgs.forEach((m) => console.log(`  [ERRO] ${arq}: ${m}`));
  console.log('');
}
if (avisos.length) {
  console.log('AVISOS:');
  for (const [arq, msgs] of porArquivo(avisos)) msgs.forEach((m) => console.log(`  [AVISO] ${arq}: ${m}`));
  console.log('');
}

console.log(`Resumo: ${paginas.length} páginas, ${erros.length} erro(s), ${avisos.length} aviso(s).`);
process.exitCode = erros.length > 0 ? 1 : 0;
