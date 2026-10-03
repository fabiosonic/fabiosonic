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
function modal(html) { $("#modal_corpo").innerHTML = html; $("#modal").hidden = false; }
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
function servPadrao() { return (ST.servicos || []).find(s => s.padrao) || ST.padrao || {}; }
function servDe(id) { return (ST.servicos || []).find(s => s.id == id) || servPadrao(); }
function opcoesServ(sel, vazio) {
  return (vazio ? `<option value="">${esc(vazio)}</option>` : "") + (ST.servicos || []).map(s => `<option value="${esc(s.id)}" ${s.id == sel ? "selected" : ""}>${esc(s.nome)}${s.padrao ? " (padrão)" : ""} — item ${esc(s.item_lista_servico || "?")}</option>`).join("");
}
function nfseAposPagamento() { return !!((ST.config || {}).emissao || {}).nfse_apos_pagamento; }
