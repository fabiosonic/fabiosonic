// Converte manuais/*.html em PDF A4 (Playwright/Chromium).
const { chromium } = require('playwright');
const fs = require('fs'); const path = require('path');
(async () => {
  const dir = path.resolve(__dirname, '..', 'manuais');
  const browser = await chromium.launch();
  const page = await browser.newPage();
  for (const f of fs.readdirSync(dir).filter(f => f.endsWith('.html') && f !== 'index.html')) {
    await page.goto('file://' + path.join(dir, f), { waitUntil: 'networkidle' });
    await page.pdf({ path: path.join(dir, f.replace('.html', '.pdf')), format: 'A4', printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
    if (process.argv[2] === f) { await page.setViewportSize({ width: 820, height: 1160 }); await page.screenshot({ path: process.argv[3], fullPage: true }); }
  }
  await browser.close();
})();
