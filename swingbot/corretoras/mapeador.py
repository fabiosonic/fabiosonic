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
  const ATTRS = ['col-id', 'aria-colindex', 'row-index', 'aria-rowindex', 'row-id', 'aria-haspopup', 'aria-expanded',
                 'aria-selected', 'aria-checked', 'data-value', 'data-testid', 'for', 'href'];
  const NUMERICOS = ['col-id', 'aria-colindex', 'row-index', 'aria-rowindex'];
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
      attrs: Object.fromEntries([...e.attributes].filter(a => ATTRS.includes(a.name))
        .map(a => [a.name, NUMERICOS.includes(a.name) ? a.value.slice(0, 40) : red(a.value)])),
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
  return { url: (location.origin + location.pathname).replace(/\d{4,}/g, '#'), titulo: red(document.title), itens, tabelas,
           diagnostico: { elementos: todos.length, componentes_shadow: hosts,
                          iframes: document.querySelectorAll('iframe').length } };
}
"""


def _url_limpa(url: str) -> str:
    """Endereço sem parâmetros (?code=, ?state=...), que podem conter códigos de acesso."""
    return re.sub(r"[?#].*$", "", url or "")[:100]


def coletar(page) -> dict:
    """Coleta a estrutura da página principal e de todos os iframes."""
    quadros = []
    for f in page.frames:
        for tentativa in range(3):
            try:
                quadros.append(f.evaluate(COLETOR_JS))
                break
            except Exception as e:  # noqa: BLE001 - página navegando ou iframe de outro domínio
                if "destroyed" in str(e) and tentativa < 2:
                    page.wait_for_timeout(2000)   # a página ainda estava carregando: tenta de novo
                    continue
                quadros.append({"url": _url_limpa(f.url), "erro": str(e)[:120]})
                break
    return {"quadros": quadros}


def esperar_homebroker(contexto, log=print, timeout_seg: int = 600):
    """Espera o login terminar e o Home Broker carregar (painel 'Resumo da conta' visível)."""
    import time
    limite, aviso = time.time() + timeout_seg, 0.0
    while time.time() < limite:
        for pg in reversed([p for p in contexto.pages if not p.is_closed()]):
            try:
                # a Clear mantém na página as janelas de TODOS os workspaces (inclusive escondidos): só vale o visível
                if "trader.clear.com.br" in pg.url and pg.locator("text=Resumo da conta >> visible=true").count() > 0:
                    pg.wait_for_timeout(3000)   # deixa terminar de desenhar as janelas
                    return pg
            except Exception:  # noqa: BLE001
                continue
        if time.time() - aviso > 15:
            log("    aguardando você concluir o login e o Home Broker carregar...")
            aviso = time.time()
        time.sleep(2)
    return None


def sem_dados_pessoais(dados: dict) -> bool:
    """Confere que não sobrou nenhum dígito em textos visíveis (valores, quantidades, CPF)."""
    texto = json.dumps(dados, ensure_ascii=False)
    campos = re.findall(r'"(?:texto|placeholder|aria|rotulo|titulo_proximo)": "([^"]*)"', texto)
    return not any(re.search(r"\d", c) for c in campos)


# ---------------------------------------------------------------------------- exploração automática
PROIBIDOS = re.compile(r"^\s*(comprar|vender|enviar|confirmar|executar|zerar|cancelar todas)", re.I)
# âncoras estáveis do Home Broker (data-testid), confirmadas no mapa real
BOLETA = "[data-testid='SomaWindow']:has([data-testid='SomaButtonTrade'])"
CHIP = "[data-testid='SomaChipChoice']:has-text('{}')"
LINHA_TIPO = "[data-testid='SomaListItemSingleLine']:has-text('Tipo de ordem')"


def _clique_seguro(loc, log) -> bool:
    """Clica somente se o elemento NÃO for de envio/confirmação de ordem."""
    try:
        texto = (loc.inner_text(timeout=2000) or "").strip()
    except Exception:  # noqa: BLE001
        texto = ""
    if PROIBIDOS.search(texto):
        log(f"    (bloqueado por segurança: '{texto[:20]}')")
        return False
    try:
        loc.click(timeout=4000)
        return True
    except Exception as e:  # noqa: BLE001
        log(f"    (não foi possível clicar: {str(e)[:60]})")
        return False


TEXTOS_VISIVEIS_JS = r"""
() => { const out = [];
  const andar = (raiz) => { for (const e of raiz.querySelectorAll('*')) {
    if (e.shadowRoot) andar(e.shadowRoot);
    if (e.children.length > 0) continue;
    const t = (e.innerText || e.textContent || '').replace(/\s+/g, ' ').trim();
    if (!t || t.length > 30 || /\d/.test(t)) continue;
    const b = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none')
      out.push([t, Math.round(b.y), Math.round(b.x)]); } };
  andar(document); return out; }
"""


def _textos_visiveis(page) -> list:
    try:
        return page.evaluate(TEXTOS_VISIVEIS_JS)
    except Exception:  # noqa: BLE001
        return []


def _novos_textos(antes: list, depois: list) -> list[str]:
    """Textos que APARECERAM após o clique (as opções da lista), na ordem da tela."""
    vistos = {t for t, _, _ in antes}
    novos = []
    for t, _, _ in sorted(depois, key=lambda x: (x[1], x[2])):
        if t not in vistos and t not in novos:
            novos.append(t)
    return novos


def _texto_opcoes(page) -> list[str]:
    ops = page.locator("[role=option], [role=menuitem], .MuiMenu-list li, .MuiPopover-paper li, [role=listbox] li")
    textos = []
    for i in range(min(ops.count(), 30)):
        t = re.sub(r"\s+", " ", ops.nth(i).inner_text() or "").strip()
        if t and not re.search(r"\d", t) and t not in textos:
            textos.append(t)
    return textos


def explorar_boleta(page, log=print) -> dict:
    """Abre a lista 'Tipo de ordem', testa cada opção e coleta os campos — sem nunca enviar ordem."""
    res = {"opcoes_tipo_ordem": [], "estados": {}, "seletores_descobertos": {}}
    boleta = page.locator(f"{BOLETA} >> visible=true").first   # ignora boletas de workspaces escondidos
    if not boleta.count():
        log("    boleta não encontrada (abra uma janela de boleta no Home Broker)")
        return res

    def vis(seletor):
        return boleta.locator(f"{seletor} >> visible=true")

    log("    boleta encontrada; selecionando 'Compra'...")
    if _clique_seguro(vis(CHIP.format("Compra")).first, log):
        page.wait_for_timeout(500)
    # descobre ONDE clicar para abrir a lista: no "A mercado ⌄", na linha "Tipo de ordem" ou num botão de menu
    candidatos = {
        "valor_atual": vis(f"{LINHA_TIPO} .SomaListItemSingleLine-endSlot").first,
        "linha": vis(LINHA_TIPO).first,
        "seta": vis(f"{LINHA_TIPO} svg").last,
        "item": vis("li:has-text('Tipo de ordem')").first,
        "popup": vis("[aria-haspopup]").first,
    }
    tipo = None
    for nome, loc in candidatos.items():
        if not loc.count():
            continue
        log(f"    testando abrir a lista pelo ponto '{nome}'... (aguarde)")
        antes = _textos_visiveis(page)
        if not _clique_seguro(loc, log):
            continue
        page.wait_for_timeout(900)
        depois = _textos_visiveis(page)
        opcoes = _texto_opcoes(page) or _novos_textos(antes, depois)
        res["estados"][f"apos_clicar_{nome}"] = coletar(page)
        if opcoes:
            tipo = loc
            res["abrir_tipo"] = nome
            res["opcoes_tipo_ordem"] = opcoes
            log(f"    lista aberta clicando em '{nome}'. Opções: {opcoes}")
            page.keyboard.press("Escape")
            page.wait_for_timeout(400)
            break
        log(f"    clique em '{nome}' não abriu lista")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
    if tipo is None:
        log("    não consegui abrir a lista 'Tipo de ordem' automaticamente")
        return res
    for op in res["opcoes_tipo_ordem"]:
        log(f"    escolhendo '{op}' (sem enviar)...")
        if not _clique_seguro(tipo, log):
            break
        page.wait_for_timeout(600)
        item = page.locator(f"text='{op}' >> visible=true").last
        if item.count() and _clique_seguro(item, log):
            page.wait_for_timeout(800)
            res["estados"][f"tipo_{op}"] = coletar(page)
            campos = vis("input:not([type=checkbox])")
            nomes = []
            for k in range(min(campos.count(), 12)):
                c = campos.nth(k)
                nomes.append({"name": c.get_attribute("name"), "id": c.get_attribute("id"),
                              "type": c.get_attribute("type"), "placeholder": c.get_attribute("placeholder")})
            res["seletores_descobertos"][op] = nomes
            log(f"    '{op}': campos {[n['name'] or n['id'] for n in nomes]}")
        else:
            page.keyboard.press("Escape")
    # como trocar o ativo da boleta: clicar no código no topo da janela
    cab = vis(".SomaWindow-header").first
    if cab.count():
        alvo = cab.locator("text=/^[A-Z]{4}[0-9]{1,2}$/").first
        if alvo.count() and _clique_seguro(alvo, log):
            page.wait_for_timeout(800)
            res["estados"]["busca_ativo"] = coletar(page)
            entradas = page.locator("input:focus, [role=dialog] input, .MuiPopover-paper input, .MuiAutocomplete-input")
            res["seletores_descobertos"]["busca_ativo"] = [
                {"name": entradas.nth(i).get_attribute("name"), "id": entradas.nth(i).get_attribute("id"),
                 "placeholder": entradas.nth(i).get_attribute("placeholder")} for i in range(min(entradas.count(), 5))]
            log(f"    busca de ativo: {res['seletores_descobertos']['busca_ativo']}")
            page.keyboard.press("Escape")
    # volta ao estado inicial (Compra / A mercado) sem enviar nada
    page.keyboard.press("Escape")
    return res
