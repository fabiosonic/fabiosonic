"""Mapeador do Home Broker: coleta a ESTRUTURA da página (botões, campos, abas, tabelas) para
configurar os seletores — sem valores da conta.

Privacidade: todo dígito é trocado por '#', textos são cortados em 40 caracteres e nenhuma
captura de tela entra no arquivo. Revise o JSON antes de enviá-lo a alguém.
"""
from __future__ import annotations

import json
import re

COLETOR_JS = r"""
() => {
  const red = (t) => (t || '').replace(/\s+/g, ' ').trim().replace(/\d/g, '#').slice(0, 40);
  const vis = (e) => { const r = e.getBoundingClientRect(); const s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const caminho = (e) => { const p = []; let n = e;
    for (let i = 0; n && n.nodeType === 1 && i < 6; i++, n = n.parentElement) {
      let s = n.tagName.toLowerCase();
      if (n.id && !/\d{3,}/.test(n.id)) { s += '#' + n.id; p.unshift(s); break; }
      const tid = n.getAttribute('data-testid') || n.getAttribute('data-test') || n.getAttribute('data-cy');
      if (tid) { s += `[data-testid="${tid}"]`; p.unshift(s); break; }
      const cls = [...n.classList].filter(c => !/\d{3,}|^css-|^sc-|^jss/.test(c)).slice(0, 2);
      if (cls.length) s += '.' + cls.join('.');
      p.unshift(s);
    }
    return p.join(' > '); };
  const rotulo = (e) => {
    if (e.labels && e.labels[0]) return red(e.labels[0].innerText);
    const fs = e.closest('fieldset'); if (fs && fs.querySelector('legend')) return red(fs.querySelector('legend').innerText);
    const lb = e.getAttribute('aria-labelledby'); if (lb && document.getElementById(lb)) return red(document.getElementById(lb).innerText);
    const ant = e.parentElement && e.parentElement.previousElementSibling; return ant ? red(ant.innerText) : '';
  };
  // percorre o documento E o conteúdo dos componentes (Shadow DOM aberto), onde ficam os botões do HB novo
  const todos = []; let hosts = 0;
  const andar = (raiz) => { for (const e of raiz.querySelectorAll('*')) { todos.push(e);
    if (e.shadowRoot) { hosts++; andar(e.shadowRoot); } } };
  andar(document);
  const sel = 'button, a, input, select, textarea, [role], th, label, legend, [data-testid], [aria-label], [tabindex], [contenteditable]';
  const itens = [];
  const clicaveis = (e) => getComputedStyle(e).cursor === 'pointer' && (e.innerText || '').trim().length > 0
    && (e.innerText || '').trim().length < 40 && e.children.length <= 3;
  for (const e of todos) {
    if (itens.length > 2500) break;
    if (!(e.matches(sel) || clicaveis(e)) || !vis(e)) continue;
    const r = e.getBoundingClientRect();
    itens.push({
      tag: e.tagName.toLowerCase(), role: e.getAttribute('role') || '', type: e.getAttribute('type') || '',
      id: e.id || '', name: e.getAttribute('name') || '', placeholder: red(e.getAttribute('placeholder')),
      aria: red(e.getAttribute('aria-label')), testid: e.getAttribute('data-testid') || e.getAttribute('data-test') || '',
      classes: [...e.classList].slice(0, 4).join(' '), texto: red(e.innerText || e.value || ''),
      rotulo: ['input', 'select', 'textarea'].includes(e.tagName.toLowerCase()) ? rotulo(e) : '',
      caminho: caminho(e), x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
    });
  }
  const tabelas = todos.filter(t => t.matches('table, [role=table], [role=grid]') && vis(t)).slice(0, 12).map(t => ({
    caminho: caminho(t),
    titulo_proximo: red((t.closest('section, article, div[class]') || t).querySelector('h1,h2,h3,h4,span,p')?.innerText),
    cabecalhos: [...t.querySelectorAll('th, [role=columnheader]')].slice(0, 15).map(h => red(h.innerText)),
    linha_exemplo: (() => { const l = t.querySelector('tbody tr, [role=row]:not(:first-child)'); if (!l) return null;
      return { caminho: caminho(l), celulas: [...l.children].slice(0, 15).map(c => ({ tag: c.tagName.toLowerCase(),
        classes: [...c.classList].slice(0, 3).join(' '), texto: red(c.innerText) })) }; })(),
    linhas: t.querySelectorAll('tbody tr, [role=row]').length,
  }));
  return { url: location.href.replace(/\d{4,}/g, '#'), titulo: red(document.title), itens, tabelas,
           diagnostico: { elementos: todos.length, componentes_shadow: hosts,
                          iframes: document.querySelectorAll('iframe').length } };
}
"""


def coletar(page) -> dict:
    """Coleta a estrutura da página principal e de todos os iframes."""
    quadros = []
    for f in page.frames:
        try:
            quadros.append(f.evaluate(COLETOR_JS))
        except Exception as e:  # noqa: BLE001 - iframes de outros domínios podem recusar
            quadros.append({"url": f.url[:80], "erro": str(e)[:120]})
    return {"quadros": quadros}


def sem_dados_pessoais(dados: dict) -> bool:
    """Confere que não sobrou nenhum dígito em textos visíveis (valores, quantidades, CPF)."""
    texto = json.dumps(dados, ensure_ascii=False)
    campos = re.findall(r'"(?:texto|placeholder|aria|rotulo|titulo_proximo)": "([^"]*)"', texto)
    return not any(re.search(r"\d", c) for c in campos)
