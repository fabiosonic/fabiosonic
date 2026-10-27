// Gera contrato/condicoes-gerais.html (estática, sem JS) a partir de assets/js/contrato-modelo.js.
// Uso: node scripts/gerar-contrato.mjs   — rode sempre que o modelo do contrato mudar.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import vm from 'node:vm';

const raiz = new URL('..', import.meta.url).pathname;
const ctx = { window: {} };
vm.runInNewContext(readFileSync(raiz + 'assets/js/contrato-modelo.js', 'utf8'), ctx);
const M = ctx.window.MOContrato;
if (!M || !Array.isArray(M.clausulas)) throw new Error('Modelo do contrato inválido');

const esc = (t) => String(t).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
// Na versão pública, os campos variáveis aparecem como lacunas destacadas.
const campo = (t) => esc(t).replace(/\{\{([A-Z_]+)\}\}/g, (_, k) => `<mark>[${k.toLowerCase().replace(/_/g, ' ')}]</mark>`);

const sumario = M.clausulas.map((c) => `<li><a href="#clausula-${c.numero}">${c.numero}. ${esc(c.titulo)}</a></li>`).join('\n          ')
  + M.anexos.map((a, i) => `\n          <li><a href="#anexo-${i + 1}">${esc(a.titulo)}</a></li>`).join('');
const corpo = [
  ...M.preambulo.map((p) => `<p>${campo(p)}</p>`),
  ...M.clausulas.map((c) => `<section id="clausula-${c.numero}"${(M.destaques || []).includes(c.numero) ? ' class="dest"' : ''}><h2>Cláusula ${c.numero} — ${esc(c.titulo)}${(M.destaques || []).includes(c.numero) ? ' <span class="badge">atenção</span>' : ''}</h2>\n${c.itens.map((i) => `<p>${campo(i)}</p>`).join('\n')}</section>`),
  ...M.anexos.map((a, i) => `<section id="anexo-${i + 1}"><h2>${esc(a.titulo)}</h2>\n${a.itens.map((x) => `<p>${campo(x)}</p>`).join('\n')}</section>`),
  ...M.fechamento.map((p) => `<p>${campo(p)}</p>`),
].join('\n');
const hashModelo = createHash('sha256').update(JSON.stringify(M)).digest('hex');

const html = `<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Condições Gerais do Contrato | M&amp;O Contábil DIGITAL</title>
  <meta name="description" content="Condições gerais do contrato de prestação de serviços contábeis da Moraes e Oliveira Contabilidade, aceitas eletronicamente na contratação pelo site.">
  <meta name="robots" content="noindex">
  <link rel="canonical" href="https://moraeseoliveiracontabil.com.br/contrato/condicoes-gerais.html">
  <meta property="og:title" content="Condições Gerais do Contrato — M&amp;O Contábil DIGITAL">
  <meta property="og:description" content="Contrato de prestação de serviços contábeis: responsabilidades das partes e envio de informações pela plataforma.">
  <meta property="og:image" content="https://moraeseoliveiracontabil.com.br/assets/img/og-image.jpg">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="../assets/img/favicon-32.png" sizes="32x32">
  <link href="https://fonts.googleapis.com/css2?family=Chivo:wght@700;800&family=Inter:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="../assets/css/style.css">
  <style>
    .site-header { background: var(--navy-900); }
    .doc { padding: 130px 0 80px; }
    .doc .container { max-width: 860px; }
    .doc h1 { font-size: clamp(1.7rem, 3.4vw, 2.4rem); }
    .doc h2 { font-size: 1.15rem; margin-top: 2em; color: var(--navy-800); }
    .doc p { color: var(--ink); }
    .doc mark { background: #FFF3BF; padding: 0 3px; border-radius: 3px; }
    .doc .meta { color: var(--ink-soft); font-size: .9rem; }
    .doc .toc { background: var(--surface-2); border-radius: 16px; padding: 18px 22px; margin: 24px 0; }
    .doc .toc ol { columns: 2; margin: 0; padding-left: 18px; font-size: .92rem; }
    .doc .dest { border-left: 4px solid #D97706; background: #FFF8EB; padding: 2px 18px 8px; border-radius: 10px; margin-top: 1.6em; }
    .doc .dest p { font-weight: 600; }
    .doc .badge { font: 700 .7rem var(--font-body); text-transform: uppercase; letter-spacing: .08em; background: #D97706; color: #fff; padding: 3px 8px; border-radius: 999px; vertical-align: middle; }
    .doc .aviso { border-left: 4px solid var(--cyan-500); background: #EEF6FF; padding: 14px 18px; border-radius: 10px; }
    @media (max-width: 720px) { .doc .toc ol { columns: 1; } }
    @media print { .site-header, .site-footer, .no-print { display: none !important; } .doc { padding: 0; } }
  </style>
</head>
<body>
  <a class="skip-link" href="#conteudo">Pular para o conteúdo</a>
  <header class="site-header scrolled">
    <div class="container header-inner">
      <a class="brand" href="../index.html"><img src="../assets/img/logo-mo.webp" width="153" height="130" alt="Logotipo M&amp;O Contabilidade"><span class="brand-text"><strong>M&amp;O Contábil</strong><em>DIGITAL</em></span></a>
      <a class="btn btn-primary btn-sm" href="../index.html#pacotes">Ver pacotes</a>
    </div>
  </header>
  <main class="doc" id="conteudo">
    <div class="container">
      <nav aria-label="Trilha de navegação" class="meta"><a href="../index.html">Início</a> › Condições Gerais do Contrato</nav>
      <h1>${esc(M.titulo)}</h1>
      <p class="meta">Versão ${esc(M.versao)} de ${esc(M.dataVersao)} · Moraes e Oliveira Contabilidade Ltda · CNPJ 24.875.410/0001-44 · CRC RJ-007873/O · Responsável técnico: Fábio Moraes — CRC RJ-118632/O-1</p>
      <p class="aviso">Este é o texto aceito eletronicamente na contratação pelo site. Os campos destacados são preenchidos com os dados do contratante no momento do aceite. Honorários, forma e condições de pagamento constam da Proposta Comercial (Anexo I), enviada por escrito.</p>
      <div class="toc no-print"><b>Sumário</b>
        <ol>
          ${sumario}
        </ol>
      </div>
${corpo}
      <p class="meta">Identificador do modelo (SHA-256): <code style="word-break:break-all">${hashModelo}</code></p>
      <p class="no-print"><button class="btn btn-ghost-dark" onclick="window.print()">Imprimir</button> <a class="btn btn-primary" href="../index.html#contratar">Contratar um pacote</a></p>
    </div>
  </main>
  <footer class="site-footer">
    <div class="container footer-bottom">
      <p>Moraes e Oliveira Contabilidade Ltda · CNPJ 24.875.410/0001-44 · CRC RJ-007873/O · Responsável técnico: Fábio Moraes — CRC RJ-118632/O-1 · Av. Vinte e Dois de Maio, 4845, Sala 908 - Rio Várzea, Itaboraí/RJ, CEP 24812-086 · (21) 99880-6423 · <a href="../politica-de-privacidade.html">Política de Privacidade</a></p>
    </div>
  </footer>
</body>
</html>
`;
mkdirSync(raiz + 'contrato', { recursive: true });
writeFileSync(raiz + 'contrato/condicoes-gerais.html', html);
console.log(`contrato/condicoes-gerais.html gerado: ${M.clausulas.length} cláusulas, ${M.anexos.length} anexos, versão ${M.versao}`);

// docs/contrato-modelo.md — espelho legível do mesmo modelo (fonte única: assets/js/contrato-modelo.js)
const md = [
  `# ${M.titulo}`, '', `**Versão ${M.versao} — ${M.dataVersao}**`, '',
  '> Gerado automaticamente por `node scripts/gerar-contrato.mjs` a partir de `assets/js/contrato-modelo.js` — não edite este arquivo à mão. Os textos entre colchetes [ ] são valores sugeridos que o escritório deve definir (ver `docs/contrato-notas-juridicas.md`). Os campos `{{...}}` são preenchidos automaticamente no aceite. Este modelo deve ser revisado por advogado inscrito na OAB antes do uso.', '',
  (M.destaques || []).length ? `Cláusulas em destaque (CDC, art. 54, § 4º): ${M.destaques.join(', ')}.\n` : '',
  '## Partes e preâmbulo', '', ...M.preambulo.flatMap((p) => [p, '']),
  ...M.clausulas.flatMap((c) => [`## Cláusula ${c.numero} — ${c.titulo}${(M.destaques || []).includes(c.numero) ? ' (destaque)' : ''}`, '', ...c.itens.flatMap((i) => [i.replace(/^(\d+\.\d+)\s/, '**$1** '), '']) ]),
  ...M.anexos.flatMap((a) => [`## ${a.titulo}`, '', ...a.itens.map((i) => `- ${i}`), '']),
  '## Fechamento', '', ...M.fechamento.flatMap((p) => [p, '']),
].join('\n');
writeFileSync(raiz + 'docs/contrato-modelo.md', md);
console.log('docs/contrato-modelo.md gerado');
