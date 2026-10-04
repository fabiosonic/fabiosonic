// Robô de cliques: abre cada tela (e cada aba dos relatórios), aperta cada botão visível e, se abrir uma janela,
// cada botão dela. Acusa erro de JavaScript, HTTP 5xx, requisição que falhou e resposta da API com cara de defeito.
// Uso: python tests/ui/servidor_demo.py <pasta> <porta> & node tests/ui/cliques.js <porta>
const { chromium } = require('playwright');
const porta = process.argv[2];
const PAGS = ['painel', 'emitir', 'lote', 'notas', 'receber', 'contratos', 'cobranca', 'pagar', 'conciliacao',
  'relatorios', 'relatorios:dre', 'relatorios:fluxo', 'relatorios:livro', 'relatorios:aging', 'relatorios:clientes', 'relatorios:fechamento', 'relatorios:log', 'clientes', 'config', 'validacao'];
const PROIBIDO = /encerrar|sair do sistema|excluir|apagar|remover|restaurar|atualizar o sistema|aplicar|produ[cç][aã]o|conectar|desconectar|cancelar (t[ií]tulo|nota|nfs)|trocar|nova empresa|outra empresa|pin|bloquear|tema/i;
const BUG = /object has no attribute|NoneType|TypeError|unsupported operand|list index|not subscriptable|Traceback|sqlite3|referenced before|is not defined|undefined|NaN|^'[a-z_]+'$/i;
(async () => {
  const b = await chromium.launch({ ...(require('fs').existsSync('/opt/pw-browsers/chromium') ? { executablePath: '/opt/pw-browsers/chromium' } : {}) });
  const ctx = await b.newContext({ viewport: { width: 1440, height: 950 } });
  const p = await ctx.newPage();
  ctx.on('page', async np => { if (np !== p) { await np.waitForTimeout(300); await np.close().catch(() => {}); } });
  const prob = new Set(); let onde = '';
  p.on('pageerror', e => prob.add(`${onde} — JS: ${e.message}`));
  p.on('requestfailed', r => { if (r.url().includes('/api/') && !/ABORTED/.test(r.failure() && r.failure().errorText)) prob.add(`${onde} — falhou ${r.url()}`); });
  p.on('response', async r => {
    if (r.status() >= 500) prob.add(`${onde} — HTTP ${r.status()} ${r.url()}`);
    if (r.url().includes('/api/')) { try { const d = await r.json(); const e = d && (d.erro || ''); if (e && BUG.test(e)) prob.add(`${onde} — API ${r.url().split('/api/')[1]}: ${e}`); } catch (_) {} }
  });
  p.on('dialog', d => d.dismiss().catch(() => {}));
  p.on('filechooser', () => {});
  const abrir = async pgaba => { const [pg, aba] = pgaba.split(':'); await p.goto(`http://127.0.0.1:${porta}/#${pg}`); await p.reload(); await p.waitForTimeout(1100);
    if (aba) { await p.click(`.abas button[data-a="${aba}"]`); await p.waitForTimeout(900); }
    await p.evaluate(() => document.querySelectorAll('details').forEach((d, i) => { if (i < 6) d.open = true; })); };
  const alvos = async (raiz) => p.evaluate(raiz => {
    const r = document.querySelector(raiz); if (!r) return [];
    const els = [...r.querySelectorAll('button, a[onclick], a[href^="#"], summary, [role=button]')];
    const vis = e => { const q = e.getBoundingClientRect(); return q.width > 0 && q.height > 0 && !e.disabled && getComputedStyle(e).visibility != 'hidden'; };
    const vistos = new Set(); const out = [];
    els.forEach((e, i) => { if (!vis(e)) return; const t = (e.innerText || e.title || e.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 50);
      const k = t + '|' + (e.getAttribute('onclick') || '').replace(/\d+/g, '#'); if (vistos.has(k)) return; vistos.add(k); out.push({ i, t }); });
    return out;
  }, raiz);
  const clicar = async (raiz, i) => p.evaluate(([raiz, i]) => {
    const e = document.querySelector(raiz).querySelectorAll('button, a[onclick], a[href^="#"], summary, [role=button]')[i]; if (e) (e.click ? e.click() : e.dispatchEvent(new MouseEvent('click', { bubbles: true }))); }, [raiz, i]).catch(err => prob.add(onde + ' — clique: ' + err.message.split('\n')[0]));
  let total = 0;
  for (const pg of PAGS) {
    await abrir(pg);
    const lista = (await alvos('#conteudo')).filter(a => !PROIBIDO.test(a.t));
    for (const a of lista) {
      onde = `${pg} › "${a.t}"`;
      await abrir(pg); await clicar('#conteudo', a.i); total++;
      await p.waitForTimeout(900);
      if (!(await p.evaluate(() => !document.querySelector('#modal').hidden))) continue;
      const mod = (await alvos('#modal')).filter(m => !PROIBIDO.test(m.t) && !/fechar|voltar|cancelar|decidir depois/i.test(m.t));
      for (const m of mod) {
        onde = `${pg} › "${a.t}" › "${m.t}"`;
        await abrir(pg); await clicar('#conteudo', a.i); await p.waitForTimeout(800);
        if (await p.evaluate(() => document.querySelector('#modal').hidden)) break;
        await clicar('#modal', m.i); total++; await p.waitForTimeout(1200);
      }
      await p.keyboard.press('Escape');
    }
    process.stdout.write(`${pg}: ${lista.length} botões\n`);
  }
  console.log(`\n${total} cliques`); console.log(prob.size ? [...prob].join('\n') : 'NENHUM ERRO');
  await b.close();
})();
