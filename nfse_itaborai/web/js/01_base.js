// Utilidades, chamadas à API, tema, avisos e tabelas.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- utilidades
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const brl = c => "R$ " + (Number(c || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = c => (Number(c || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dt = iso => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";
const mes = c => c ? `${c.slice(5, 7)}/${c.slice(0, 4)}` : "";
const fmtDoc = d => !d ? "" : /^99\d{7}$/.test(d) ? `exterior nº ${d}` : d.length == 14 ? d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5") : d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
const valorNum = s => { s = String(s ?? "").trim(); if (s.includes(",")) s = s.replace(/\./g, "").replace(",", "."); return Number(s) || 0; };
// tema: automático (segue o Windows), claro ou escuro — preferência guardada neste navegador
const TEMAS = [["", "automático"], ["light", "claro"], ["dark", "escuro"]];
function aplicarTema(t) {
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  const b = document.getElementById("tema"); if (b) b.querySelector("span").textContent = "Tema: " + TEMAS.find(x => x[0] == t)[1];
}
let TEMA = ""; try { TEMA = localStorage.getItem("tema") || ""; } catch (e) { /* sem armazenamento: automático */ }
aplicarTema(TEMA);
document.getElementById("sair").onclick = async () => {
  if (!confirm("Encerrar o sistema? O robô agendado continua rodando de hora em hora. Para abrir de novo, use o atalho “Sistema Financeiro NFS-e” na área de trabalho.")) return;
  try { await api("sistema/encerrar"); } catch (e) { /* já encerrando */ }
  document.body.innerHTML = '<main style="display:grid;place-items:center;min-height:100vh;text-align:center;padding:24px"><div><h1>Sistema encerrado</h1><p>Para abrir de novo, use o atalho <b>Sistema Financeiro NFS-e</b> na área de trabalho.<br>O robô agendado continua cuidando das rotinas de hora em hora.</p></div></main>';
};
document.getElementById("tema").onclick = () => {
  TEMA = TEMAS[(TEMAS.findIndex(x => x[0] == TEMA) + 1) % TEMAS.length][0];
  try { localStorage.setItem("tema", TEMA); } catch (e) { /* ignora */ }
  aplicarTema(TEMA); if (PAG == "painel" || PAG == "relatorios") ir(PAG);
};
const ic = n => `<svg class="ic" aria-hidden="true"><use href="#i-${n}"/></svg>`;
const hojeISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
let ST = { clientes: [], padrao: {}, producao: false, config: {} };

const API_CAB = { "X-Requested-With": "EmissorItaborai", "Content-Type": "application/json" };   // identifica a própria tela
async function api(rota, corpo) {
  const r = await fetch("/api/" + rota, { method: "POST", headers: API_CAB, body: JSON.stringify(corpo || {}) });
  const d = await r.json();
  if (d && d.bloqueado) { telaPin(); throw new Error(d.erro); }
  if (d && d.erro && !Array.isArray(d)) { aviso("⚠ " + d.erro, 7000); destravar(); throw new Error(d.erro); }
  return d;
}
// Botão desativado durante uma operação ("Enviando…"): se a operação der erro, ele volta ao normal (não fica travado).
document.addEventListener("click", e => { const b = e.target.closest && e.target.closest("button");
  if (b && !b.disabled) { b._rotulo = b.innerHTML; b._clicado = Date.now(); } }, true);
function destravar() {
  document.querySelectorAll("button:disabled").forEach(b => {
    if (b._clicado && Date.now() - b._clicado < 300000) { b.disabled = false; b.innerHTML = b._rotulo; b._clicado = 0; } });
}
// Erro já mostrado no aviso (validação, configuração faltando): não vira "erro não tratado" no console.
window.addEventListener("unhandledrejection", e => { if (e.reason && document.querySelector("#aviso") && !$("#aviso").hidden
  && $("#aviso").textContent.includes(e.reason.message)) e.preventDefault(); });
function aviso(t, ms = 3500) { const a = $("#aviso"); a.textContent = t; a.hidden = false; clearTimeout(a._t); a._t = setTimeout(() => a.hidden = true, ms); }
function modal(html, larga = false) {
  $("#modal .caixa").classList.toggle("larga", !!larga);
  $("#modal_corpo").innerHTML = `<button class="modal-x" type="button" onclick="fechar()" aria-label="Fechar" title="Fechar (Esc)">${ic("x")}</button>` + html;
  const novo = $("#modal").hidden; $("#modal").hidden = false;
  if (novo) { const f = $("#modal_corpo").querySelector("input:not([type=hidden]):not([disabled]), select, textarea"); if (f) setTimeout(() => f.focus(), 30); }
}
document.addEventListener("keydown", e => { if (e.key == "Escape" && !$("#modal").hidden) fechar(); });
function fechar() { $("#modal").hidden = true; }
$("#modal").addEventListener("click", e => { if (e.target.id == "modal") fechar(); });
function selo(sit) {
  const m = { pago: ["bom", "Pago"], aberto: ["neutro", "Em aberto"], atrasado: ["critico", "Atrasado"], cancelado: ["neutro", "Cancelado"],
    emitida: ["bom", "Emitida"], teste: ["alerta", "Teste"], emitindo: ["serio", "Em emissão — conferir no portal"], pendente: ["alerta", "Pendente"], erro: ["critico", "Erro"], nao_emitir: ["neutro", "Sem NFS-e"], apos_pagamento: ["neutro", "Após o pagamento"], sem_cobranca: ["neutro", "Sem cobrança"], juridico: ["serio", "Jurídico"], suspenso: ["neutro", "Suspenso"], nf_cancelada: ["critico", "Cancelada"],
    bom: ["bom", "Bom"], "atenção": ["alerta", "Atenção"], risco: ["critico", "Risco"], enviado: ["bom", "Enviado"], feito: ["bom", "Feito"],
    sem_contato: ["alerta", "Sem contato"] };
  const [c, t] = m[sit] || ["neutro", sit];
  return `<span class="selo ${c}">${esc(t)}</span>`;
}
function tabela(cols, linhas, vazio = "Nada por aqui.") {
  if (!linhas.length) return `<div class="vazio">${vazio}</div>`;
  return `<div class="tabela"><table><thead><tr>${cols.map(c => `<th class="${c.n ? "n" : ""}">${c.t}</th>`).join("")}</tr></thead><tbody>${
    linhas.map(l => `<tr>${cols.map(c => `<td class="${c.n ? "n" : ""}" data-r="${esc(String(c.t).replace(/<[^>]*>/g, ""))}">${c.f(l)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
// ---------------------------------------------------------------- formatação para leitura rápida
const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const mesExtenso = c => c ? `${MESES[+c.slice(5, 7) - 1]} de ${c.slice(0, 4)}` : "";
const mesCurto = c => c ? `${MESES[+c.slice(5, 7) - 1].slice(0, 3)}/${c.slice(2, 4)}` : "";
// R$ compacto: 1.284 · 12,9 mil · 4,2 mi (valores em centavos)
function compacto(c, moeda = true) {
  const v = Number(c || 0) / 100, a = Math.abs(v), f = (x, d) => x.toLocaleString("pt-BR", { maximumFractionDigits: d });
  const t = a >= 1e6 ? f(v / 1e6, 1) + " mi" : a >= 1e4 ? f(v / 1e3, 1) + " mil" : f(v, 0);
  return moeda ? "R$ " + t : t;
}
const pct = (v, d = 1) => Number(v || 0).toLocaleString("pt-BR", { maximumFractionDigits: d }) + "%";
// "RPS CONSULTORIA E SERVICOS LTDA" -> "RPS Consultoria e Servicos LTDA" (siglas e conectivos preservados)
function nomeCli(n) {
  n = String(n || "").split(" - ")[0].trim();
  if (n != n.toUpperCase()) return n;
  const SIG = new Set(["LTDA", "ME", "EPP", "EIRELI", "S/A", "SA", "MEI", "SS", "SLU", "TI"]), MIN = new Set(["DE", "DA", "DO", "DAS", "DOS", "E", "EM"]);
  return n.split(/\s+/).map((w, i) => SIG.has(w) || (!/[AEIOUÁÉÍÓÚÂÊÔÃÕ]/.test(w) && w.length <= 4) ? w
    : i && MIN.has(w) ? w.toLowerCase() : w.charAt(0) + w.slice(1).toLowerCase()).join(" ");
}

const frase = s => { s = String(s || "").trim().toLowerCase(); return s.charAt(0).toUpperCase() + s.slice(1); };
// Célula de cliente: nome legível numa linha (nome completo ao passar o mouse) + complemento
const fone = d => { d = String(d || "").replace(/\D/g, ""); return d.length == 11 ? d.replace(/(\d{2})(\d{5})(\d{4})/, "($1) $2-$3") : d.length == 10 ? d.replace(/(\d{2})(\d{4})(\d{4})/, "($1) $2-$3") : d; };
const celNome = (nome, sub = "") => `<div class="cel-nome"><span class="nome" title="${esc(nome)}">${esc(nomeCli(nome))}</span>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
function servPadrao() { return (ST.servicos || []).find(s => s.padrao) || ST.padrao || {}; }
function servDe(id) { return (ST.servicos || []).find(s => s.id == id) || servPadrao(); }
function opcoesServ(sel, vazio) {
  return (vazio ? `<option value="">${esc(vazio)}</option>` : "") + (ST.servicos || []).map(s => `<option value="${esc(s.id)}" ${s.id == sel ? "selected" : ""}>${esc(s.nome)}${s.padrao ? " (padrão)" : ""} — item ${esc(s.item_lista_servico || "?")}</option>`).join("");
}
function nfseAposPagamento() { return !!((ST.config || {}).emissao || {}).nfse_apos_pagamento; }

// ---------------------------------------------------------------- campo de mês sempre em português
// O <input type="month"> do navegador segue o idioma do Edge/Windows ("October 2026") e não existe no Firefox.
// Cada um vira dois seletores (mês por extenso + ano); o campo original continua guardando "AAAA-MM", com os mesmos
// eventos (input/change), .value e .disabled — as telas não precisam saber da troca.
const _valorInput = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value");
function campoMes(inp) {
  if (inp._mesPt) return;
  inp._mesPt = true;
  const w = document.createElement("span"), sm = document.createElement("select"), sa = document.createElement("select");
  w.className = "mes-pt"; w.title = inp.title || "";
  inp.style.width = "";                          // a largura vem do CSS (cabe "fevereiro" e o ano)
  sm.setAttribute("aria-label", "Mês"); sa.setAttribute("aria-label", "Ano");
  const curto = !!inp.closest("td");                 // dentro de tabela: "out" em vez de "outubro" (cabe na linha)
  sm.innerHTML = `<option value="">mês</option>` + MESES.map((m, i) => `<option value="${String(i + 1).padStart(2, "0")}" title="${m}">${curto ? m.slice(0, 3) : m}</option>`).join("");
  const anos = v => {
    const atual = new Date().getFullYear(), a = +String(v).slice(0, 4) || atual;
    let h = `<option value="">ano</option>`;
    for (let x = Math.min(atual - 8, a); x <= Math.max(atual + 6, a); x++) h += `<option>${x}</option>`;
    sa.innerHTML = h;
  };
  const mostrar = () => {
    const v = _valorInput.get.call(inp);
    if (v && ![...sa.options].some(o => o.value == v.slice(0, 4))) anos(v);
    sm.value = v.slice(5, 7); sa.value = v ? v.slice(0, 4) : "";
    sm.disabled = sa.disabled = inp.disabled;
  };
  const mudou = () => {
    if (sm.value && !sa.value) sa.value = String(new Date().getFullYear());
    _valorInput.set.call(inp, sm.value && sa.value ? `${sa.value}-${sm.value}` : "");
    if (!sm.value) sa.value = "";
    inp.dispatchEvent(new Event("input", { bubbles: true })); inp.dispatchEvent(new Event("change", { bubbles: true }));
  };
  sm.onchange = sa.onchange = mudou;
  inp.type = "hidden";
  Object.defineProperty(inp, "value", { configurable: true, get() { return _valorInput.get.call(this); },
    set(v) { _valorInput.set.call(this, v || ""); mostrar(); } });
  new MutationObserver(mostrar).observe(inp, { attributes: true, attributeFilter: ["disabled"] });
  w.append(sm, sa); inp.after(w); anos(_valorInput.get.call(inp)); mostrar();
}
new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
  if (n.nodeType != 1) return;
  (n.matches('input[type="month"]') ? [n] : n.querySelectorAll('input[type="month"]')).forEach(campoMes);
}))).observe(document.documentElement, { childList: true, subtree: true });

// ---------------------------------------------------------------- campo de data sempre em dd/mm/aaaa
// O <input type="date"> segue o idioma do navegador (num Edge em inglês aparece "mm/dd/yyyy", fácil de trocar dia e
// mês). O campo original fica escondido guardando "AAAA-MM-DD" (mesmo .value, eventos e name); por cima vai um campo
// digitado no padrão brasileiro, com máscara, e um botão que abre o calendário.
function campoData(inp) {
  if (inp._dataPt) return;
  inp._dataPt = true;
  const w = document.createElement("span"), txt = document.createElement("input"), bt = document.createElement("button");
  w.className = "data-pt"; txt.type = "text"; txt.inputMode = "numeric"; txt.maxLength = 10; txt.placeholder = "dd/mm/aaaa";
  txt.autocomplete = "off"; txt.title = inp.title || "Data no formato dia/mês/ano";
  if (inp.id) txt.dataset.de = inp.id;
  bt.type = "button"; bt.className = "data-cal"; bt.title = "Abrir o calendário"; bt.setAttribute("aria-label", "Abrir o calendário");
  bt.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/></svg>`;
  if (inp.style.width) { w.style.width = inp.style.width; inp.style.width = ""; }
  const iso = () => _valorInput.get.call(inp);
  const mostrar = () => {
    const v = iso();
    txt.value = /^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v.slice(8, 10)}/${v.slice(5, 7)}/${v.slice(0, 4)}` : "";
    txt.classList.remove("invalido");
    txt.disabled = bt.disabled = inp.disabled; txt.required = inp.required;
  };
  const avisar = () => { inp.dispatchEvent(new Event("input", { bubbles: true })); inp.dispatchEvent(new Event("change", { bubbles: true })); };
  txt.oninput = () => {
    const d = txt.value.replace(/\D/g, "").slice(0, 8);
    txt.value = d.length > 4 ? `${d.slice(0, 2)}/${d.slice(2, 4)}/${d.slice(4)}` : d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
    if (d.length == 8) {
      const v = `${d.slice(4)}-${d.slice(2, 4)}-${d.slice(0, 2)}`, dt = new Date(v + "T12:00:00");
      const ok = !isNaN(dt) && dt.toISOString().slice(0, 10) == v;
      txt.classList.toggle("invalido", !ok);
      if (ok && v != iso()) { _valorInput.set.call(inp, v); avisar(); }
    } else if (!d && iso()) { _valorInput.set.call(inp, ""); avisar(); }
  };
  txt.onblur = () => { if (txt.value && txt.value.replace(/\D/g, "").length < 8) txt.classList.add("invalido"); };
  inp.addEventListener("change", e => { if (e.isTrusted) mostrar(); });   // escolhido no calendário
  bt.onclick = () => { try { inp.showPicker(); } catch (_) { txt.focus(); } };
  Object.defineProperty(inp, "value", { configurable: true, get() { return _valorInput.get.call(this); },
    set(v) { _valorInput.set.call(this, v || ""); mostrar(); } });
  new MutationObserver(mostrar).observe(inp, { attributes: true, attributeFilter: ["disabled", "required"] });
  inp.classList.add("data-orig"); inp.tabIndex = -1; inp.setAttribute("aria-hidden", "true");
  inp.after(w); w.append(txt, bt, inp); mostrar();
}
new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
  if (n.nodeType != 1) return;
  (n.matches('input[type="date"]') ? [n] : n.querySelectorAll('input[type="date"]')).forEach(campoData);
}))).observe(document.documentElement, { childList: true, subtree: true });

// menu compacto (notebook): o nome de cada item aparece ao passar o mouse
document.querySelectorAll("#menu nav a, #menu .tema").forEach(a => { if (!a.title) a.title = a.textContent.trim(); });
