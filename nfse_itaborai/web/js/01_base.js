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

async function api(rota, corpo) {
  const r = await fetch("/api/" + rota, { method: "POST", body: JSON.stringify(corpo || {}) });
  const d = await r.json();
  if (d && d.bloqueado) { telaPin(); throw new Error(d.erro); }
  if (d && d.erro && !Array.isArray(d)) { aviso("⚠ " + d.erro, 7000); throw new Error(d.erro); }
  return d;
}
function aviso(t, ms = 3500) { const a = $("#aviso"); a.textContent = t; a.hidden = false; clearTimeout(a._t); a._t = setTimeout(() => a.hidden = true, ms); }
function modal(html) {
  $("#modal_corpo").innerHTML = `<button class="modal-x" type="button" onclick="fechar()" aria-label="Fechar" title="Fechar (Esc)">${ic("x")}</button>` + html;
  const novo = $("#modal").hidden; $("#modal").hidden = false;
  if (novo) { const f = $("#modal_corpo").querySelector("input:not([type=hidden]):not([disabled]), select, textarea"); if (f) setTimeout(() => f.focus(), 30); }
}
document.addEventListener("keydown", e => { if (e.key == "Escape" && !$("#modal").hidden) fechar(); });
function fechar() { $("#modal").hidden = true; }
$("#modal").addEventListener("click", e => { if (e.target.id == "modal") fechar(); });
function selo(sit) {
  const m = { pago: ["bom", "Pago"], aberto: ["neutro", "Em aberto"], atrasado: ["critico", "Atrasado"], cancelado: ["neutro", "Cancelado"],
    emitida: ["bom", "Emitida"], teste: ["alerta", "Teste"], emitindo: ["serio", "Em emissão — conferir no portal"], pendente: ["alerta", "Pendente"], erro: ["critico", "Erro"], nao_emitir: ["neutro", "Sem NFS-e"], apos_pagamento: ["neutro", "Após o pagamento"], sem_cobranca: ["neutro", "Sem cobrança"], nf_cancelada: ["critico", "Cancelada"],
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
const celNome = (nome, sub = "") => `<div class="cel-nome"><span class="nome" title="${esc(nome)}">${esc(nomeCli(nome))}</span>${sub ? `<div class="sub">${sub}</div>` : ""}</div>`;
function servPadrao() { return (ST.servicos || []).find(s => s.padrao) || ST.padrao || {}; }
function servDe(id) { return (ST.servicos || []).find(s => s.id == id) || servPadrao(); }
function opcoesServ(sel, vazio) {
  return (vazio ? `<option value="">${esc(vazio)}</option>` : "") + (ST.servicos || []).map(s => `<option value="${esc(s.id)}" ${s.id == sel ? "selected" : ""}>${esc(s.nome)}${s.padrao ? " (padrão)" : ""} — item ${esc(s.item_lista_servico || "?")}</option>`).join("");
}
function nfseAposPagamento() { return !!((ST.config || {}).emissao || {}).nfse_apos_pagamento; }
