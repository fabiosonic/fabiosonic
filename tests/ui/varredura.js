// Varredura das telas no navegador (Playwright): abre todas as páginas e abas em desktop, tema escuro,
// celular e notebook e acusa erro de JavaScript, HTTP 5xx, rolagem horizontal e textos que transbordam.
// Uso: node tests/ui/varredura.js <porta> [pasta_para_prints]
const fs = require('fs');
const { chromium } = require('playwright');
const PAGS = ['painel', 'emitir', 'lote', 'notas', 'receber', 'contratos', 'cobranca', 'pagar', 'conciliacao',
  'relatorios', 'clientes', 'config', 'validacao'];
const ABAS = ['indicadores', 'dre', 'fluxo', 'livro', 'aging', 'clientes', 'fechamento', 'log'];
const porta = process.argv[2] || '8799', prints = process.argv[3] || '';
const exe = process.env.CHROMIUM_PATH || (fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
(async () => {
  const b = await chromium.launch(exe ? { executablePath: exe } : {});
  const problemas = [];
  for (const [nome, vp, tema] of [['desktop', { width: 1440, height: 950 }, 'light'], ['escuro', { width: 1440, height: 950 }, 'dark'],
    ['celular', { width: 390, height: 844 }, 'light'], ['notebook', { width: 1280, height: 720 }, 'light']]) {
    const p = await b.newPage({ viewport: vp, colorScheme: tema });
    p.on('pageerror', e => problemas.push(`${nome} JS: ${e.message}`));
    p.on('response', r => { if (r.status() >= 500) problemas.push(`${nome} HTTP ${r.status()} ${r.url()}`); });
    const checar = async rot => {
      const r = await p.evaluate(() => {
        const out = [];
        if (document.documentElement.scrollWidth > window.innerWidth + 2) out.push(`rolagem horizontal ${document.documentElement.scrollWidth}>${window.innerWidth}`);
        for (const el of document.querySelectorAll('.kpi .v, .btn, .selo, h1, h2, .marca-txt, .amb, .bh-val')) {
          if (el.offsetParent === null) continue;
          if (el.scrollWidth > el.clientWidth + 2 && getComputedStyle(el).overflow !== 'hidden') out.push(`transborda: ${el.className || el.tagName} "${el.textContent.trim().slice(0, 40)}"`);
          const card = el.closest('.kpi, .card');
          if (card && !el.closest('.tabela')) { const a = el.getBoundingClientRect(), c = card.getBoundingClientRect(); if (a.right > c.right + 2) out.push(`sai do cartão: "${el.textContent.trim().slice(0, 40)}"`); }
        }
        const erro = document.querySelector('.aviso:not([hidden])');
        if (erro && /⚠/.test(erro.textContent)) out.push('aviso de erro: ' + erro.textContent.slice(0, 120));
        return out;
      });
      for (const x of r) problemas.push(`${nome} ${rot}: ${x}`);
    };
    for (const pg of PAGS) {
      await p.goto(`http://127.0.0.1:${porta}/#${pg}`); await p.reload(); await p.waitForTimeout(900);
      if (pg === 'relatorios') {
        for (const a of ABAS) { await p.click(`.abas button[data-a="${a}"]`); await p.waitForTimeout(700); await checar(`relatorios/${a}`); }
      } else {
        await checar(pg);
        if (prints && nome !== 'notebook') await p.screenshot({ path: `${prints}/${nome}_${pg}.png` });
      }
    }
    await p.close();
  }
  console.log(problemas.length ? [...new Set(problemas)].join('\n') : 'SEM PROBLEMAS');
  await b.close();
  process.exit(problemas.length ? 1 : 0);
})();
