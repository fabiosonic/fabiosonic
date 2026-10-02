"use strict";
// ---------------------------------------------------------------- utilidades
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const brl = c => "R$ " + (Number(c || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = c => (Number(c || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dt = iso => iso ? `${iso.slice(8, 10)}/${iso.slice(5, 7)}/${iso.slice(0, 4)}` : "";
const mes = c => c ? `${c.slice(5, 7)}/${c.slice(0, 4)}` : "";
const fmtDoc = d => !d ? "" : d.length == 14 ? d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5") : d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
const valorNum = s => { s = String(s ?? "").trim(); if (s.includes(",")) s = s.replace(/\./g, "").replace(",", "."); return Number(s) || 0; };
const hojeISO = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0, 10);
let ST = { clientes: [], padrao: {}, producao: false, config: {} };

async function api(rota, corpo) {
  const r = await fetch("/api/" + rota, { method: "POST", body: JSON.stringify(corpo || {}) });
  const d = await r.json();
  if (d && d.erro && !Array.isArray(d)) { aviso("⚠ " + d.erro, 7000); throw new Error(d.erro); }
  return d;
}
function aviso(t, ms = 3500) { const a = $("#aviso"); a.textContent = t; a.hidden = false; clearTimeout(a._t); a._t = setTimeout(() => a.hidden = true, ms); }
function modal(html) { $("#modal_corpo").innerHTML = html; $("#modal").hidden = false; }
function fechar() { $("#modal").hidden = true; }
$("#modal").addEventListener("click", e => { if (e.target.id == "modal") fechar(); });
function selo(sit) {
  const m = { pago: ["bom", "Pago"], aberto: ["neutro", "Em aberto"], atrasado: ["critico", "Atrasado"], cancelado: ["neutro", "Cancelado"],
    emitida: ["bom", "Emitida"], teste: ["alerta", "Teste"], emitindo: ["serio", "Em emissão — conferir no portal"], pendente: ["alerta", "Pendente"], erro: ["critico", "Erro"], nao_emitir: ["neutro", "Sem NFS-e"],
    bom: ["bom", "Bom"], "atenção": ["alerta", "Atenção"], risco: ["critico", "Risco"], enviado: ["bom", "Enviado"], feito: ["bom", "Feito"],
    sem_contato: ["alerta", "Sem contato"] };
  const [c, t] = m[sit] || ["neutro", sit];
  return `<span class="selo ${c}">${esc(t)}</span>`;
}
function tabela(cols, linhas, vazio = "Nada por aqui.") {
  if (!linhas.length) return `<div class="vazio">${vazio}</div>`;
  return `<div class="tabela"><table><thead><tr>${cols.map(c => `<th class="${c.n ? "n" : ""}">${c.t}</th>`).join("")}</tr></thead><tbody>${
    linhas.map(l => `<tr>${cols.map(c => `<td class="${c.n ? "n" : ""}">${c.f(l)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function opcoesClientes() { return ST.clientes.map(c => `<option value="${esc(c.razao_social)} — ${fmtDoc(c.cpf_cnpj)}">`).join(""); }
function docDe(txt) { const m = String(txt).match(/(\d[\d./-]{10,})\s*$/); return m ? m[1].replace(/\D/g, "") : String(txt).replace(/\D/g, ""); }
function form(el) { const o = {}; $$("[name]", el).forEach(i => o[i.name] = i.type == "checkbox" ? i.checked : i.value); return o; }
async function carregarEstado() {
  ST = await api("estado");
  const b = $("#amb");
  b.textContent = (ST.producao ? "● PRODUÇÃO" : "● HOMOLOGAÇÃO (teste)") + " · " + nomeCanal(true);
  b.className = "amb " + (ST.producao ? "prod" : "hom");
  b.title = "Clique para trocar o ambiente";
}
$("#amb").onclick = async () => {
  const p = !ST.producao;
  if (!confirm(p ? "Ativar PRODUÇÃO? As notas emitidas terão validade fiscal." : "Voltar para HOMOLOGAÇÃO (teste, sem validade)?")) return;
  await api("ambiente", { producao: p }); await carregarEstado(); ir(PAG);
};

function nomeCanal(curto) { return ST.canal == "nacional" ? (curto ? "Nacional" : "Emissor Nacional (nfse.gov.br)") : (curto ? "Itaboraí" : "Webservice da Prefeitura de Itaboraí"); }

// ---------------------------------------------------------------- navegação
const PAGINAS = {};
let PAG = "painel";
async function ir(p) {
  PAG = p;
  $$("nav a").forEach(a => a.classList.toggle("on", a.dataset.p == p));
  $("#conteudo").innerHTML = '<div class="vazio">Carregando…</div>';
  try { await PAGINAS[p]($("#conteudo")); } catch (e) { console.error(e); }
  history.replaceState(null, "", "#" + p);
}
$$("nav a").forEach(a => a.onclick = () => ir(a.dataset.p));

// ---------------------------------------------------------------- painel
function grafico(serie) {
  const W = 760, H = 240, ml = 52, mb = 26, mt = 10, larg = W - ml - 8, alt = H - mt - mb;
  const max = Math.max(1, ...serie.flatMap(s => [s.faturado, s.recebido]));
  const passo = Math.pow(10, Math.floor(Math.log10(max / 100))) * 100;
  const topo = Math.ceil(max / passo / 4) * passo * 4 || 1;
  const y = v => mt + alt - v / topo * alt, gw = larg / serie.length, bw = Math.min(18, (gw - 10) / 2);
  let s = "";
  for (let i = 0; i <= 4; i++) { const v = topo / 4 * i; s += `<line class="grade" x1="${ml}" x2="${W - 8}" y1="${y(v)}" y2="${y(v)}"/><text class="eixo" x="${ml - 6}" y="${y(v) + 4}" text-anchor="end">${(v / 100 / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}k</text>`; }
  const barra = (x, v, cor, i, k) => { const h = Math.max(0, alt - (y(v) - mt)); const yy = y(v); const r = Math.min(4, h);
    return `<path d="M${x},${yy + h} V${yy + r} Q${x},${yy} ${x + r},${yy} H${x + bw - r} Q${x + bw},${yy} ${x + bw},${yy + r} V${yy + h} Z" fill="var(${cor})" data-i="${i}" data-k="${k}"/>`; };
  serie.forEach((p, i) => {
    const x0 = ml + gw * i + (gw - (bw * 2 + 2)) / 2;
    s += barra(x0, p.faturado, "--serie-1", i, "f") + barra(x0 + bw + 2, p.recebido, "--serie-2", i, "r");
    s += `<rect x="${ml + gw * i}" y="${mt}" width="${gw}" height="${alt}" fill="transparent" data-i="${i}" class="alvo"/>`;
    s += `<text class="eixo" x="${ml + gw * i + gw / 2}" y="${H - 8}" text-anchor="middle">${p.mes.slice(5)}/${p.mes.slice(2, 4)}</text>`;
  });
  return `<div class="legenda"><span><i style="background:var(--serie-1)"></i>Faturado (competência)</span><span><i style="background:var(--serie-2)"></i>Recebido</span></div>
    <div class="grafico"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Faturado e recebido nos últimos 12 meses">${s}</svg><div class="dica" hidden></div></div>
    <details><summary class="sub">Ver tabela</summary>${tabela([{ t: "Mês", f: p => mes(p.mes) }, { t: "Faturado", n: 1, f: p => num(p.faturado) }, { t: "Recebido", n: 1, f: p => num(p.recebido) }], serie)}</details>`;
}
function ligarDica(el, serie) {
  const g = $(".grafico", el); if (!g) return; const d = $(".dica", g);
  $$(".alvo", g).forEach(r => {
    r.onmousemove = ev => { const p = serie[r.dataset.i]; const b = g.getBoundingClientRect();
      d.innerHTML = `<b>${mes(p.mes)}</b><br>Faturado ${brl(p.faturado)}<br>Recebido ${brl(p.recebido)}`; d.hidden = false;
      d.style.left = (ev.clientX - b.left) + "px"; d.style.top = (ev.clientY - b.top) + "px"; };
    r.onmouseleave = () => d.hidden = true;
  });
}
PAGINAS.painel = async el => {
  const p = await api("painel");
  const alertas = [];
  if (p.sem_nfse) alertas.push(`🧾 <b>${p.sem_nfse}</b> título(s) sem NFS-e válida — <a href="#" onclick="ir('receber');return false">ver</a>`);
  if (p.atrasado_qtd) alertas.push(`⏰ <b>${p.atrasado_qtd}</b> título(s) em atraso de <b>${p.clientes_atrasados}</b> cliente(s): ${brl(p.atrasado)}`);
  if (p.criticos.length) alertas.push(`⛔ <b>${p.criticos.length}</b> cliente(s) com atraso crítico (≥ ${ST.config.cobranca.bloquear_apos_dias} dias): ${p.criticos.slice(0, 5).map(esc).join(", ")}${p.criticos.length > 5 ? ` e mais ${p.criticos.length - 5} — <a href="#" onclick="ABA_REL='aging';ir('relatorios');return false">ver todos</a>` : ""}`);
  if (p.a_pagar_atrasado) alertas.push(`📤 Contas a pagar vencidas: ${brl(p.a_pagar_atrasado)}`);
  if (p.sublimite_pct >= 80) alertas.push(`⚠ RBT12 em ${p.sublimite_pct}% do sublimite de R$ 3,6 mi do Simples`);
  if (p.contratos_a_confirmar) alertas.unshift(`🔁 <b>${p.contratos_a_confirmar}</b> contrato(s) recorrente(s) detectado(s) nas suas notas — <a href="#" onclick="ir('contratos');return false">conferir</a> ou <a href="#" onclick="confirmarTodos();return false"><b>confirmar todos</b></a>`);
  if (!ST.config.automacao.ativa) alertas.push(`🤖 O robô financeiro está desligado — <a href="#" onclick="ir('config');return false">ligar em Configurações</a>`);
  const robo = ST.config.automacao.ativa ? `<span class="selo bom">Robô ligado</span> <span class="sub">${p.ultima_execucao_robo ? "última execução " + dt(p.ultima_execucao_robo.slice(0, 10)) + " " + p.ultima_execucao_robo.slice(11, 16) : "ainda não executou"}</span>` : `<span class="selo critico">Robô desligado</span>`;
  el.innerHTML = `<h1>Painel <span style="font-size:13px;font-weight:400">${robo}</span><span class="acoes"><button class="btn sec" id="robo">🤖 Rodar robô agora</button></span></h1>
  <div class="kpis">
    <div class="kpi"><div class="r">Faturado em ${mes(p.competencia)}</div><div class="v">${brl(p.faturado_mes)}</div><div class="s">por competência</div></div>
    <div class="kpi"><div class="r">Recebido no mês</div><div class="v">${brl(p.recebido_mes)}</div></div>
    <div class="kpi"><div class="r">A receber</div><div class="v">${brl(p.a_receber)}</div></div>
    <div class="kpi"><div class="r">Em atraso</div><div class="v">${brl(p.atrasado)}</div><div class="s">${p.atrasado_qtd} título(s) · inadimplência ${p.inadimplencia_pct}%</div></div>
    <div class="kpi"><div class="r">Receita recorrente (MRR)</div><div class="v">${brl(p.mrr)}</div><div class="s">${p.contratos_ativos} contrato(s) · ticket ${brl(p.ticket_medio)}</div></div>
    <div class="kpi"><div class="r">A pagar</div><div class="v">${brl(p.a_pagar)}</div></div>
    <div class="kpi"><div class="r">RBT12 (Simples)</div><div class="v">${brl(p.rbt12)}</div><div class="s">DAS estimado ${String(p.aliquota_simples_estimada).replace(".", ",")}% · ${p.sublimite_pct}% do sublimite</div></div>
  </div>
  <div class="grid2">
    <div class="card"><h2>Últimos 12 meses</h2>${grafico(p.serie)}</div>
    <div class="card"><h2>Alertas</h2>${alertas.length ? `<ul class="lista-alertas">${alertas.map(a => `<li>${a}</li>`).join("")}</ul>` : '<div class="vazio">Tudo em dia ✔</div>'}
      <h2 style="margin-top:16px">Maiores devedores</h2>${tabela([{ t: "Cliente", f: x => esc(x.cliente) }, { t: "Atualizado", n: 1, f: x => brl(x.valor) }], p.maiores_devedores, "Ninguém em atraso.")}</div>
  </div>
  <div class="card"><h2>Vencem nos próximos 7 dias</h2>${tabela([{ t: "Cliente", f: t => esc(t.cliente_nome) }, { t: "Vencimento", f: t => dt(t.vencimento) }, { t: "Valor", n: 1, f: t => brl(t.valor_cent) }, { t: "NFS-e", f: t => selo(t.nfse_status) }], p.proximos_7_dias, "Nenhum vencimento na semana.")}</div>`;
  ligarDica(el, p.serie);
  $("#robo").onclick = async ev => {
    if (!confirm(`Rodar o robô agora?\n\nEle gera os títulos dos contratos, ${ST.producao ? "EMITE AS NFS-e VÁLIDAS pendentes" : "não emite NFS-e (homologação)"}, cria PIX/boleto, envia a régua de cobrança e confere pagamentos.`)) return;
    ev.target.disabled = true; modal('<h2>Robô em execução…</h2><p class="sub">Pode levar alguns minutos se houver muitas notas para emitir. Não feche esta janela.</p>');
    let r; try { r = await api("robo/rodar"); } finally { ev.target.disabled = false; }
    modal(`<h2>Resultado do robô</h2>${resumoRobo(r)}<button class="btn" onclick="fechar();ir('painel')">OK</button>`); };
};

function resumoRobo(r) {
  if (!r.executado) return `<p>${esc(r.motivo || "Nada executado.")}</p>`;
  const nomes = { importacao_xml: "XML das notas (clientes, notas externas, contratos)", contatos_completados: "Contatos completados pela Receita",
    despesas_recorrentes: "Despesas recorrentes lançadas", titulos_gerados: "Títulos gerados (contratos)", nfse: "NFS-e",
    cobrancas_criadas: "Cobranças (PIX/boleto) criadas", baixas_asaas: "Baixas automáticas (Asaas)", extratos: "Extratos importados",
    regua: "Régua de cobrança", resumo: "Resumo diário por e-mail", backup: "Backup" };
  const fmt = v => typeof v == "object" ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(" · ") : String(v);
  return `<table>${Object.entries(nomes).filter(([k]) => k in r).map(([k, t]) => `<tr><td>${t}</td><td>${esc(fmt(r[k]))}</td></tr>`).join("")}</table><p></p>`;
}

// ---------------------------------------------------------------- emitir / lote
function linhaRes(r) {
  return r.sucesso ? `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · NFS-e <b>${esc(r.nfse)}</b> · ${r.canal == "nacional" ? "Nacional · chave " + esc(r.chave) : "RPS " + esc(r.rps)}${r.link && r.link.startsWith("http") ? ` · <a href="${esc(r.link)}" target="_blank">abrir nota</a>` : ""}${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`
    : `<div class="msg erro"><span class="t">✖ ${esc(r.cliente)} — ${esc(r.valor)}</span>${(r.erros || []).map(e => `<div>${esc(e)}</div>`).join("")}</div>`;
}
PAGINAS.emitir = async el => {
  el.innerHTML = `<h1>Emitir nota</h1><div class="card"><div class="campos">
    <label class="inteiro">Cliente<input id="e_cli" list="dl_cli" placeholder="Digite o nome ou CNPJ e escolha"></label>
    <label>Valor (R$)<input id="e_valor" inputmode="decimal" placeholder="0,00"></label>
    <label>Vencimento<input id="e_venc" type="date"></label>
    <label class="inteiro">Descrição<input id="e_desc" maxlength="190" value="${esc(ST.padrao.descricao)}"></label></div>
    <datalist id="dl_cli">${opcoesClientes()}</datalist>
    <p class="sub">A nota gera automaticamente a conta a receber com o PIX/boleto e entra na régua de cobrança.<br>Emitindo por: <b>${nomeCanal()}</b> — troque em <a href="#config">Configurações › Emissão</a>.</p>
    <button class="btn" id="e_btn">Emitir nota</button><div id="e_res"></div></div>`;
  $("#e_cli").oninput = () => { const c = ST.clientes.find(x => x.cpf_cnpj == docDe($("#e_cli").value)); if (c && c.ultimo_valor && !$("#e_valor").value) $("#e_valor").value = Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 }); };
  $("#e_btn").onclick = async () => {
    const doc = docDe($("#e_cli").value), cli = ST.clientes.find(c => c.cpf_cnpj == doc);
    if (!cli) return aviso("Escolha um cliente da lista (ou cadastre em Clientes).");
    const v = $("#e_valor").value.trim(); if (!valorNum(v)) return aviso("Informe o valor.");
    if (!confirm(`${ST.producao ? "EMITIR NOTA VÁLIDA" : "Teste em homologação"} — ${nomeCanal()}\n\n${cli.razao_social}\nR$ ${v}`)) return;
    $("#e_btn").disabled = true; $("#e_res").innerHTML = '<div class="msg">Enviando…</div>';
    try { const r = await api("emitir", { cpf_cnpj: doc, valor: v, descricao: $("#e_desc").value, vencimento: $("#e_venc").value }); $("#e_res").innerHTML = linhaRes(r); if (r.sucesso) $("#e_valor").value = ""; }
    finally { $("#e_btn").disabled = false; }
  };
};
PAGINAS.lote = async el => {
  el.innerHTML = `<h1>Emitir em lote</h1><div class="card"><div class="barra"><label>Filtrar<input id="l_f" placeholder="nome ou CNPJ"></label>
    <label style="flex:1">Descrição para todas<input id="l_desc" maxlength="190" value="${esc(ST.padrao.descricao)}"></label></div>
    <p class="sub">Marque os clientes. O valor vem da última nota — ajuste se precisar. Cada nota já gera a conta a receber.</p>
    <div id="l_tab"></div><p><button class="btn" id="l_btn">Emitir selecionadas</button> <span id="l_tot" class="sub"></span></p><div id="l_res"></div></div>`;
  const desenhar = () => { const f = $("#l_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#l_tab").innerHTML = tabela([{ t: '<input type="checkbox" id="l_todos">', f: c => `<input type="checkbox" class="lc" data-doc="${c.cpf_cnpj}">` },
      { t: "Cliente", f: c => `${esc(c.razao_social)}<div class="sub">${fmtDoc(c.cpf_cnpj)}</div>` },
      { t: "Valor (R$)", f: c => `<input class="lv" data-doc="${c.cpf_cnpj}" style="width:120px" value="${c.ultimo_valor ? Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : ""}">` },
      { t: "Última nota", f: c => dt(c.ultima_data) }], ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)));
    $("#l_todos") && ($("#l_todos").onclick = e => { $$(".lc").forEach(x => x.checked = e.target.checked); somar(); });
    $$(".lc,.lv").forEach(x => x.oninput = x.onchange = somar); somar(); };
  const sel = () => $$(".lc:checked").map(x => ({ cpf_cnpj: x.dataset.doc, valor: $(`.lv[data-doc="${x.dataset.doc}"]`).value, descricao: $("#l_desc").value }));
  const somar = () => { const s = sel(); $("#l_tot").textContent = s.length ? `${s.length} nota(s) · total ${brl(Math.round(s.reduce((a, b) => a + valorNum(b.valor), 0) * 100))}` : ""; };
  $("#l_f").oninput = desenhar; desenhar();
  $("#l_btn").onclick = async () => {
    const itens = sel(); if (!itens.length) return aviso("Marque ao menos um cliente.");
    if (itens.some(i => !valorNum(i.valor))) return aviso("Há cliente marcado sem valor.");
    if (!confirm(`${ST.producao ? "EMITIR " + itens.length + " NOTAS VÁLIDAS" : "Teste em homologação de " + itens.length + " notas"} — ${nomeCanal()}\n${$("#l_tot").textContent}`)) return;
    $("#l_btn").disabled = true; $("#l_res").innerHTML = '<div class="msg">Enviando, aguarde…</div>';
    try { const r = await api("lote", { itens }); $("#l_res").innerHTML = `<div class="msg"><b>${r.filter(x => x.sucesso).length} de ${r.length} emitida(s).</b></div>` + r.map(linhaRes).join(""); }
    finally { $("#l_btn").disabled = false; }
  };
};

// ---------------------------------------------------------------- contas a receber
let FILTRO_REC = "a_receber";
PAGINAS.receber = async el => {
  const comp = (el._comp ?? "");
  const lst = await api("titulos", { filtro: FILTRO_REC, competencia: comp });
  const soma = lst.reduce((a, t) => a + (t.status == "aberto" ? t.total_cent : t.status == "pago" ? t.valor_pago_cent : 0), 0);
  el.innerHTML = `<h1>Contas a receber <span class="acoes"><button class="btn" id="novo_t">+ Título avulso</button><button class="btn sec" id="pdf_bol">⬇ PDFs dos boletos</button> <a class="btn sec" href="/export/titulos.csv">⬇ Exportar CSV</a></span></h1>
  <div class="card"><div class="abas">${[["a_receber", "A receber"], ["atrasado", "Atrasados"], ["pago", "Pagos"], ["sem_nfse", "Sem NFS-e"], ["cancelado", "Cancelados"], ["todos", "Todos"]].map(([k, t]) => `<button data-f="${k}" class="${k == FILTRO_REC ? "on" : ""}">${t}</button>`).join("")}
    <label style="flex-direction:row;align-items:center;gap:6px;margin-left:auto">Competência <input type="month" id="r_comp" value="${comp}" style="width:160px"></label></div>
    <p class="sub">${lst.length} título(s) · ${brl(soma)}</p>
    ${tabela([
      { t: "Cliente", f: t => `${esc(t.cliente_nome)}<div class="sub">${esc(t.descricao)}</div>` },
      { t: "Comp.", f: t => mes(t.competencia) },
      { t: "Vencimento", f: t => dt(t.vencimento) },
      { t: "Valor", n: 1, f: t => num(t.valor_cent) + (t.situacao == "atrasado" ? `<div class="sub">atualizado ${num(t.total_cent)}</div>` : t.status == "pago" ? `<div class="sub">pago ${num(t.valor_pago_cent)} em ${dt(t.data_pagamento)}</div>` : "") },
      { t: "Situação", f: t => selo(t.situacao) + (t.dias_atraso ? `<div class="sub">${t.dias_atraso} dia(s)</div>` : "") },
      { t: "NFS-e", f: t => selo(t.nfse_status) + (t.nfse_numero ? `<div class="sub">${t.nfse_link && t.nfse_link.startsWith("http") ? `<a href="${esc(t.nfse_link)}" target="_blank">${esc(t.nfse_numero)}</a>` : esc(t.nfse_numero)}</div>` : "") + (t.nfse_erro ? `<div class="sub" title="${esc(t.nfse_erro)}">${esc(t.nfse_erro.slice(0, 60))}…</div>` : "") },
      { t: "Ações", f: t => acoesTitulo(t) }], lst)}</div>`;
  $$(".abas button", el).forEach(b => b.onclick = () => { FILTRO_REC = b.dataset.f; ir("receber"); });
  $("#r_comp").onchange = e => { el._comp = e.target.value; ir("receber"); };
  $("#novo_t").onclick = novoTitulo;
  $("#pdf_bol").onclick = async () => {
    aviso("Baixando os PDFs dos boletos…", 20000);
    const r = await api("boletos/baixar", { competencia: comp });
    aviso(`${r.baixados} PDF(s) baixado(s), ${r.ja_existiam} já estavam na pasta${r.erros.length ? `, ${r.erros.length} com erro: ${r.erros.join("; ")}` : ""}. Pasta: ${r.pasta}`, 12000);
    if (r.baixados + r.ja_existiam) api("boletos/abrir_pasta");
  };
};
function acoesTitulo(t) {
  const b = [];
  if (t.status == "aberto") {
    b.push(`<button class="btn min" onclick="baixar(${t.id},${t.total_cent})">Baixar</button>`);
    b.push(`<button class="btn min sec" onclick="cobrar(${t.id})">Cobrar</button>`);
    if (t.asaas_id) b.push(`<a class="btn min sec" href="/boleto/${t.id}.pdf" target="_blank">Boleto PDF</a>`);
    if (["pendente", "erro", "teste"].includes(t.nfse_status)) b.push(`<button class="btn min sec" onclick="emitirTitulo(${t.id})">Emitir NFS-e</button>`);
    b.push(`<button class="btn min sec" onclick="cancelarTitulo(${t.id},'${t.nfse_status}')">Cancelar</button>`);
  }
  if (t.status == "pago") b.push(`<button class="btn min sec" onclick="estornar(${t.id})">Estornar</button>`);
  b.push(`<button class="btn min sec" onclick="historicoTitulo(${t.id})">Histórico</button>`);
  return `<div style="display:flex;gap:4px;flex-wrap:wrap">${b.join("")}</div>`;
}
async function baixar(id, total) {
  modal(`<h2>Dar baixa</h2><div class="campos" id="fb"><label>Data do pagamento<input type="date" name="data" value="${hojeISO()}"></label>
    <label>Valor recebido (R$)<input name="valor" value="${num(total)}"></label>
    <label>Forma<select name="forma"><option>pix</option><option>boleto</option><option>transferencia</option><option>dinheiro</option><option>cartao</option></select></label></div>
    <p><button class="btn" id="ok">Confirmar baixa</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { await api("titulo/baixar", { id, ...form($("#fb")) }); fechar(); aviso("Baixa registrada ✔"); ir(PAG); };
}
async function estornar(id) { if (confirm("Estornar o pagamento deste título?")) { await api("titulo/estornar", { id }); ir(PAG); } }
async function emitirTitulo(id) {
  if (!confirm(ST.producao ? "Emitir a NFS-e VÁLIDA deste título?" : "Emitir NFS-e de teste (homologação)?")) return;
  aviso("Enviando NFS-e…"); const r = await api("titulo/emitir_nfse", { id });
  aviso(r.sucesso ? `NFS-e ${r.nfse} emitida ✔` : "Erro: " + (r.erros || []).join("; "), 7000); ir(PAG);
}
async function cancelarTitulo(id, nfse) {
  if (nfse == "emitida") {
    const j = prompt("Esta conta tem NFS-e emitida. Para cancelar a NFS-e (no mesmo canal em que foi emitida) e o título, informe a justificativa (mín. 15 caracteres):");
    if (!j) return; const r = await api("titulo/cancelar_nfse", { id, justificativa: j });
    aviso(r.sucesso ? "NFS-e e título cancelados ✔" : "Erro: " + (r.erros || []).join("; "), 7000);
  } else { const m = prompt("Motivo do cancelamento do título:"); if (m === null) return; await api("titulo/cancelar", { id, motivo: m }); }
  ir(PAG);
}
async function cobrar(id) {
  const r = await api("titulo/cobrar", { id });
  modal(`<h2>Cobrança</h2>${r.email ? `<div class="msg ok">E-mail enviado para ${esc(r.email)}</div>` : '<div class="msg">E-mail não enviado (cliente sem e-mail ou SMTP não configurado).</div>'}
    ${r.whatsapp ? `<p><a class="btn" href="${esc(r.whatsapp)}" target="_blank">Abrir no WhatsApp</a></p>` : '<p class="sub">Cliente sem telefone para WhatsApp.</p>'}
    <label>Mensagem<textarea rows="12" id="txt">${esc(r.texto)}</textarea></label>
    <p><button class="btn sec" onclick="navigator.clipboard.writeText($('#txt').value);aviso('Copiado')">Copiar texto</button> <button class="btn sec" onclick="fechar()">Fechar</button></p>`);
}
async function historicoTitulo(id) {
  const h = await api("titulo/historico", { id });
  modal(`<h2>Histórico de cobrança</h2>${tabela([{ t: "Data", f: e => dt(e.data) }, { t: "Etapa", f: e => e.etapa < 0 ? `${-e.etapa} dia(s) antes` : e.etapa == 0 ? "no vencimento" : `${e.etapa} dia(s) após` }, { t: "Canal", f: e => e.canal }, { t: "Status", f: e => selo(e.status) }], h, "Nenhuma cobrança enviada ainda.")}<p><button class="btn sec" onclick="fechar()">Fechar</button></p>`);
}
function novoTitulo() {
  modal(`<h2>Título avulso</h2><div class="campos" id="fn"><label class="inteiro">Cliente<input name="cliente" list="dl_cli2"></label><datalist id="dl_cli2">${opcoesClientes()}</datalist>
    <label>Valor (R$)<input name="valor"></label><label>Vencimento<input type="date" name="vencimento"></label><label>Competência<input type="month" name="competencia"></label>
    <label class="inteiro">Descrição<input name="descricao" value="${esc(ST.padrao.descricao)}"></label>
    <label class="chk"><input type="checkbox" name="emitir_nfse" checked> Emitir NFS-e agora</label></div>
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const f = form($("#fn")); f.cpf_cnpj = docDe(f.cliente); const r = await api("titulo/novo", f); fechar();
    aviso(r.sucesso ? "Título criado ✔" : "Título criado, mas a NFS-e falhou: " + (r.erros || []).join("; "), 7000); ir(PAG); };
}

// ---------------------------------------------------------------- contratos
PAGINAS.contratos = async el => {
  const lst = await api("contratos");
  const ativos = lst.filter(c => c.ativo && c.confirmado), pend = lst.filter(c => c.ativo && !c.confirmado);
  el.innerHTML = `<h1>Contratos recorrentes <span class="acoes"><button class="btn" id="nc">+ Novo contrato</button><button class="btn sec" id="hist">⚡ Criar a partir do histórico</button><button class="btn sec" id="gerar">Gerar títulos do mês</button></span></h1>
  <div class="kpis"><div class="kpi"><div class="r">Contratos ativos</div><div class="v">${ativos.length}</div></div><div class="kpi"><div class="r">MRR</div><div class="v">${brl(ativos.reduce((a, c) => a + c.valor_cent, 0))}</div></div></div>
  ${pend.length ? `<div class="card" style="border-color:var(--alerta)"><h2>${pend.length} contrato(s) detectado(s) automaticamente</h2><p>O robô encontrou cobrança mensal de mesmo valor nas suas notas. Confira e confirme: só depois disso eles passam a emitir NFS-e e cobrar. Começam no mês seguinte à última nota, para não cobrar em dobro.</p><button class="btn" onclick="confirmarTodos()">Confirmar todos</button></div>` : ""}
  <div class="card"><p class="sub">Todo mês, no dia configurado, o robô gera a conta a receber de cada contrato, emite a NFS-e, cria o PIX/boleto e coloca na régua de cobrança. Reajuste anual automático no mês escolhido.</p>
  ${tabela([{ t: "Cliente", f: c => `${esc(c.cliente_nome)}<div class="sub">${esc(c.descricao)}</div>` }, { t: "Valor", n: 1, f: c => num(c.valor_cent) }, { t: "Vence dia", f: c => c.dia_vencimento },
    { t: "Vigência", f: c => `${mes(c.inicio)} → ${c.fim ? mes(c.fim) : "sem fim"}` }, { t: "Reajuste", f: c => c.mes_reajuste ? `${c.reajuste_pct}% em ${String(c.mes_reajuste).padStart(2, "0")}` : "—" },
    { t: "NFS-e", f: c => c.emitir_nfse ? "automática" : "não emite" }, { t: "Situação", f: c => !c.ativo ? selo("cancelado").replace("Cancelado", "Encerrado") : c.confirmado ? selo("bom").replace("Bom", "Ativo") : selo("pendente").replace("Pendente", "A confirmar") + ` <button class="btn min" onclick="confirmarUm(${c.id})">Confirmar</button>` },
    { t: "", f: c => `<button class="btn min sec" onclick='editarContrato(${JSON.stringify(c).replace(/'/g, "&#39;")})'>Editar</button>${c.ativo ? ` <button class="btn min sec" onclick="encerrar(${c.id})">Encerrar</button>` : ""}` }], lst, "Nenhum contrato. Use “Criar a partir do histórico” para montar a carteira em um clique.")}</div>`;
  $("#nc").onclick = () => editarContrato({});
  $("#hist").onclick = async () => { const d = prompt("Dia de vencimento para os contratos criados:", ST.config.financeiro.dia_vencimento_padrao); if (d === null) return;
    const r = await api("contratos/historico", { dia_vencimento: Number(d) }); aviso(`${r.criados} contrato(s) criado(s) ✔`); ir("contratos"); };
  $("#gerar").onclick = async () => { const c = prompt("Competência (AAAA-MM):", hojeISO().slice(0, 7)); if (!c) return;
    const r = await api("recorrencia/gerar", { competencia: c }); aviso(`${r.gerados} título(s) gerado(s) ✔`); };
};
async function confirmarTodos() {
  if (!confirm("Confirmar todos os contratos detectados? A partir do próximo vencimento o robô passa a emitir a NFS-e e cobrar esses clientes todo mês.")) return;
  const r = await api("contratos/confirmar", {}); aviso(`${r.confirmados} contrato(s) confirmado(s) ✔`); ir(PAG);
}
async function confirmarUm(id) { await api("contratos/confirmar", { ids: [id] }); aviso("Contrato confirmado ✔"); ir("contratos"); }
function editarContrato(c) {
  const cli = ST.clientes.find(x => x.cpf_cnpj == c.cpf_cnpj);
  modal(`<h2>${c.id ? "Editar" : "Novo"} contrato</h2><div class="campos" id="fc">
    <label class="inteiro">Cliente<input name="cliente" list="dl_cli3" value="${cli ? esc(cli.razao_social + " — " + fmtDoc(cli.cpf_cnpj)) : ""}"></label><datalist id="dl_cli3">${opcoesClientes()}</datalist>
    <label class="inteiro">Descrição<input name="descricao" value="${esc(c.descricao || ST.padrao.descricao)}"></label>
    <label>Valor mensal (R$)<input name="valor" value="${c.valor_cent ? num(c.valor_cent) : ""}"></label>
    <label>Dia do vencimento<input name="dia_vencimento" type="number" min="1" max="31" value="${c.dia_vencimento || ST.config.financeiro.dia_vencimento_padrao}"></label>
    <label>Início<input name="inicio" type="month" value="${c.inicio || hojeISO().slice(0, 7)}"></label><label>Fim (opcional)<input name="fim" type="month" value="${c.fim || ""}"></label>
    <label>Mês do reajuste<select name="mes_reajuste">${["Sem reajuste", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"].map((m, i) => `<option value="${i}" ${i == (c.mes_reajuste || 0) ? "selected" : ""}>${m}</option>`).join("")}</select></label>
    <label>Reajuste (%)<input name="reajuste_pct" value="${c.reajuste_pct || ""}" placeholder="ex.: 4,5 (IPCA)"></label>
    <label class="chk"><input type="checkbox" name="emitir_nfse" ${c.emitir_nfse === 0 ? "" : "checked"}> Emitir NFS-e automaticamente</label>
    <label class="chk"><input type="checkbox" name="ativo" ${c.ativo === 0 ? "" : "checked"}> Ativo</label></div>
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const f = form($("#fc")); f.cpf_cnpj = docDe(f.cliente); if (c.id) f.id = c.id; await api("contrato/salvar", f); fechar(); aviso("Contrato salvo ✔"); ir("contratos"); };
}
async function encerrar(id) { if (confirm("Encerrar este contrato? Ele deixa de gerar cobranças.")) { await api("contrato/excluir", { id }); ir("contratos"); } }

// ---------------------------------------------------------------- cobrança
PAGINAS.cobranca = async el => {
  const [fila, hist] = await Promise.all([api("whatsapp/fila"), api("regua/historico")]);
  const c = ST.config.cobranca;
  el.innerHTML = `<h1>Cobrança <span class="acoes"><button class="btn" id="rr">Rodar régua agora</button></span></h1>
  <div class="card"><h2>Régua automática</h2><p>Etapas (dias em relação ao vencimento): <b>${c.regua_dias.map(d => d < 0 ? d : d == 0 ? "0 (vencimento)" : "+" + d).join(" · ")}</b> —
    e-mail ${c.regua_email ? "<b>ligado</b>" : "desligado"}, WhatsApp ${c.regua_whatsapp ? "<b>ligado</b>" : "desligado"}. Multa ${c.multa_pct}% + juros ${c.juros_mes_pct}% a.m. pro rata.
    <a href="#" onclick="ir('config');return false">Alterar</a></p></div>
  <div class="card"><h2>WhatsApp para enviar (${fila.length})</h2><p class="sub">${ST.config.whatsapp.provedor == "link" ? "Envio por link: clique em “Enviar” para abrir a conversa com a mensagem pronta. Para envio 100% automático, configure Z-API ou Evolution API em Configurações." : "Envio automático ligado (" + esc(ST.config.whatsapp.provedor) + "). Aqui aparecem só mensagens antigas pendentes."}</p>
    ${tabela([{ t: "Cliente", f: e => esc(e.cliente_nome) }, { t: "Venc.", f: e => dt(e.vencimento) }, { t: "Valor", n: 1, f: e => num(e.valor_cent) },
      { t: "Etapa", f: e => e.etapa < 0 ? "lembrete" : e.etapa == 0 ? "vence hoje" : `+${e.etapa} dias` },
      { t: "", f: e => `<a class="btn min" href="${esc(e.detalhe)}" target="_blank" onclick="setTimeout(()=>feito(${e.id}),800)">Enviar</a> <button class="btn min sec" onclick="feito(${e.id})">Marcar feito</button>` }], fila, "Nenhuma mensagem pendente ✔")}</div>
  <div class="card"><h2>Últimos envios</h2>${tabela([{ t: "Data", f: e => dt(e.data) }, { t: "Cliente", f: e => esc(e.cliente_nome) }, { t: "Etapa", f: e => e.etapa }, { t: "Canal", f: e => e.canal }, { t: "Status", f: e => selo(e.status) }, { t: "Detalhe", f: e => `<span class="sub">${esc(e.canal == "whatsapp" ? "" : e.detalhe)}</span>` }], hist, "Nenhum envio ainda.")}</div>`;
  $("#rr").onclick = async () => { const r = await api("regua/rodar"); aviso(`Régua: ${r.email} e-mail(s), ${r.whatsapp} WhatsApp, ${r.sem_contato} sem contato, ${r.erros} erro(s)`, 6000); ir("cobranca"); };
};
async function feito(id) { await api("whatsapp/feito", { id }); if (PAG == "cobranca") ir("cobranca"); }

// ---------------------------------------------------------------- contas a pagar
let FILTRO_PAG = "a_pagar";
PAGINAS.pagar = async el => {
  const lst = await api("despesas", { filtro: FILTRO_PAG });
  el.innerHTML = `<h1>Contas a pagar <span class="acoes"><button class="btn" id="nd">+ Nova despesa</button></span></h1>
  <div class="card"><div class="abas">${[["a_pagar", "A pagar"], ["atrasado", "Vencidas"], ["pago", "Pagas"], ["todos", "Todas"]].map(([k, t]) => `<button data-f="${k}" class="${k == FILTRO_PAG ? "on" : ""}">${t}</button>`).join("")}</div>
  <p class="sub">${lst.length} despesa(s) · ${brl(lst.reduce((a, d) => a + d.valor_cent, 0))}</p>
  ${tabela([{ t: "Descrição", f: d => `${esc(d.descricao)}<div class="sub">${esc(d.fornecedor)}${d.recorrente ? " · recorrente" : ""}</div>` }, { t: "Categoria", f: d => esc(d.categoria) },
    { t: "Vencimento", f: d => dt(d.vencimento) }, { t: "Valor", n: 1, f: d => num(d.valor_cent) }, { t: "Situação", f: d => selo(d.situacao) },
    { t: "", f: d => d.status == "aberto" ? `<button class="btn min" onclick="pagarDesp(${d.id})">Pagar</button> <button class="btn min sec" onclick='editarDesp(${JSON.stringify(d).replace(/'/g, "&#39;")})'>Editar</button> <button class="btn min sec" onclick="excluirDesp(${d.id})">Excluir</button>` : "" }], lst)}</div>`;
  $$(".abas button", el).forEach(b => b.onclick = () => { FILTRO_PAG = b.dataset.f; ir("pagar"); });
  $("#nd").onclick = () => editarDesp({});
};
function editarDesp(d) {
  modal(`<h2>${d.id ? "Editar" : "Nova"} despesa</h2><div class="campos" id="fd"><label class="inteiro">Descrição<input name="descricao" value="${esc(d.descricao || "")}"></label>
    <label>Fornecedor<input name="fornecedor" value="${esc(d.fornecedor || "")}"></label>
    <label>Categoria<select name="categoria">${ST.config.financeiro.categorias_despesa.map(c => `<option ${c == d.categoria ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label>
    <label>Valor (R$)<input name="valor" value="${d.valor_cent ? num(d.valor_cent) : ""}"></label><label>Vencimento<input type="date" name="vencimento" value="${d.vencimento || hojeISO()}"></label>
    <label class="chk"><input type="checkbox" name="recorrente" ${d.recorrente ? "checked" : ""}> Repetir todo mês</label></div>
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const f = form($("#fd")); if (d.id) f.id = d.id; await api("despesa/salvar", f); fechar(); ir("pagar"); };
}
async function pagarDesp(id) { await api("despesa/pagar", { id }); aviso("Despesa paga ✔"); ir("pagar"); }
async function excluirDesp(id) { if (confirm("Excluir esta despesa?")) { await api("despesa/excluir", { id }); ir("pagar"); } }

// ---------------------------------------------------------------- conciliação
PAGINAS.conciliacao = async el => {
  const pend = await api("conciliacao/pendentes");
  el.innerHTML = `<h1>Conciliação bancária</h1>
  <div class="card"><h2>Importar extrato (OFX)</h2><p class="sub">Exporte o extrato em OFX no internet banking e selecione aqui. Os recebimentos são casados com as contas a receber e baixados sozinhos; pagamentos casam com contas a pagar.</p>
    <input type="file" id="ofx" accept=".ofx,.OFX"><div id="ofx_res"></div></div>
  <div class="card"><h2>Lançamentos não conciliados (${pend.length})</h2>
  ${tabela([{ t: "Data", f: m => dt(m.data) }, { t: "Histórico", f: m => esc(m.descricao) }, { t: "Valor", n: 1, f: m => num(m.valor_cent) },
    { t: "Sugestões", f: m => m.sugestoes.length ? m.sugestoes.map(s => `<button class="btn min sec" onclick="vincular(${m.id},${s.id})" title="Venc. ${dt(s.vencimento)}">${esc(s.cliente.slice(0, 28))} · ${num(s.valor_cent)}</button>`).join(" ") : '<span class="sub">—</span>' }], pend, "Tudo conciliado ✔")}</div>`;
  $("#ofx").onchange = async e => { const f = e.target.files[0]; if (!f) return;
    const buf = await f.arrayBuffer(); let txt = new TextDecoder("utf-8").decode(buf); if (txt.includes("�")) txt = new TextDecoder("windows-1252").decode(buf);
    const r = await api("conciliacao/importar", { ofx: txt });
    $("#ofx_res").innerHTML = `<div class="msg ok">${r.lancamentos} lançamento(s) lidos · ${r.novos} novo(s) · <b>${r.titulos}</b> recebimento(s) baixado(s) · ${r.despesas} pagamento(s) conciliado(s)</div>`;
    setTimeout(() => ir("conciliacao"), 2500); };
};
async function vincular(movimento, titulo) { await api("conciliacao/vincular", { movimento, titulo }); aviso("Conciliado e baixado ✔"); ir("conciliacao"); }

// ---------------------------------------------------------------- relatórios
let ABA_REL = "aging";
PAGINAS.relatorios = async el => {
  const abas = [["aging", "Inadimplência (aging)"], ["clientes", "Por cliente"], ["fluxo", "Fluxo de caixa"], ["dre", "DRE gerencial"], ["log", "Log do sistema"]];
  el.innerHTML = `<h1>Relatórios <span class="acoes"><a class="btn sec" href="/export/titulos.csv">⬇ Contas a receber (CSV)</a><button class="btn sec" onclick="window.print()">🖨 Imprimir</button></span></h1>
    <div class="abas">${abas.map(([k, t]) => `<button data-a="${k}" class="${k == ABA_REL ? "on" : ""}">${t}</button>`).join("")}</div><div id="rel" class="card"><div class="vazio">Carregando…</div></div>`;
  $$(".abas button", el).forEach(b => b.onclick = () => { ABA_REL = b.dataset.a; ir("relatorios"); });
  const r = $("#rel");
  if (ABA_REL == "aging") {
    const a = await api("rel/aging"), f = a.faixas;
    r.innerHTML = `<div class="kpis">${[["a_vencer", "A vencer"], ["1_30", "1–30 dias"], ["31_60", "31–60 dias"], ["61_90", "61–90 dias"], ["90_mais", "+90 dias"]].map(([k, t]) => `<div class="kpi"><div class="r">${t}</div><div class="v">${brl(f[k])}</div></div>`).join("")}</div>` +
      tabela([{ t: "Cliente", f: c => esc(c.cliente) }, ...["a_vencer", "1_30", "31_60", "61_90", "90_mais"].map(k => ({ t: k.replace("_", "–").replace("a–vencer", "a vencer").replace("90–mais", "+90"), n: 1, f: c => c[k] ? num(c[k]) : "" }))], a.clientes);
  } else if (ABA_REL == "clientes") {
    const l = await api("rel/clientes");
    r.innerHTML = `<p class="sub">Score de pagamento: 100 = paga sempre em dia; cai com a média de dias de atraso e com títulos vencidos em aberto.</p>` + tabela([{ t: "Cliente", f: c => esc(c.cliente) }, { t: "Faturado 12m", n: 1, f: c => num(c.faturado_12m) },
      { t: "Recebido", n: 1, f: c => num(c.recebido_total) }, { t: "Em aberto", n: 1, f: c => num(c.em_aberto) }, { t: "Atrasado (atualizado)", n: 1, f: c => c.atrasado ? num(c.atrasado) : "" },
      { t: "Atraso médio", n: 1, f: c => c.media_atraso + " d" }, { t: "Score", n: 1, f: c => `${c.score} ${selo(c.faixa)}` }], l);
  } else if (ABA_REL == "fluxo") {
    const l = await api("rel/fluxo", { dias: 90 });
    r.innerHTML = `<p class="sub">Projeção semanal para 90 dias: títulos em aberto + contratos ainda não faturados − contas a pagar.</p>` + tabela([{ t: "Semana de", f: s => dt(s.semana) }, { t: "Entradas", n: 1, f: s => num(s.entradas) },
      { t: "Saídas", n: 1, f: s => num(s.saidas) }, { t: "Saldo acumulado", n: 1, f: s => `<b>${num(s.saldo_acumulado)}</b>` }], l);
  } else if (ABA_REL == "dre") {
    const ano = el._ano || new Date().getFullYear(); const d = await api("rel/dre", { ano });
    r.innerHTML = `<div class="barra"><label>Ano<input type="number" id="ano" value="${ano}" style="width:110px"></label></div>
      <p class="sub">DAS estimado pela alíquota efetiva do Anexo III (RBT12 de cada mês)${ST.config.financeiro.iss_fixo ? ", sem a parcela do ISS (escritório contábil recolhe ISS fixo — LC 123/2006, art. 18, § 22-A)" : ""}.</p>` +
      tabela([{ t: "Mês", f: m => mes(m.mes) }, { t: "Receita", n: 1, f: m => num(m.receita) }, { t: "DAS est.", n: 1, f: m => `${num(m.das_estimado)}<div class="sub">${String(m.aliquota_das).replace(".", ",")}%</div>` },
        { t: "Receita líquida", n: 1, f: m => num(m.receita_liquida) }, ...d.categorias.map(c => ({ t: esc(c), n: 1, f: m => m.por_categoria[c] ? num(m.por_categoria[c]) : "" })),
        { t: "Resultado", n: 1, f: m => `<b>${num(m.resultado)}</b>` }], d.meses) +
      `<p><b>Ano:</b> receita ${brl(d.total.receita)} · DAS ${brl(d.total.das_estimado)} · despesas ${brl(d.total.despesas)} · resultado <b>${brl(d.total.resultado)}</b></p>`;
    $("#ano").onchange = e => { el._ano = e.target.value; ir("relatorios"); };
  } else {
    const l = await api("log");
    r.innerHTML = tabela([{ t: "Quando", f: x => esc(x.quando) }, { t: "Tipo", f: x => esc(x.tipo) }, { t: "Mensagem", f: x => esc(x.mensagem) }], l);
  }
};

// ---------------------------------------------------------------- clientes
PAGINAS.clientes = async el => {
  el.innerHTML = `<h1>Clientes</h1><div class="card"><div class="barra"><label>CNPJ / CPF<input id="c_doc" placeholder="só números"></label><button class="btn sec" id="bc">Buscar na Receita</button></div>
    <div class="campos" id="fcli"><label class="inteiro">Razão social / nome<input name="razao_social"></label>
    <label>Tipo logradouro<input name="tipo_logradouro" placeholder="RUA"></label><label>Logradouro<input name="logradouro"></label><label>Número<input name="numero"></label>
    <label>Complemento<input name="complemento"></label><label>Bairro<input name="bairro"></label><label>CEP<input name="cep"></label>
    <label>Cód. IBGE município<input name="codigo_municipio"></label><label>UF<input name="uf" maxlength="2"></label>
    <label>Inscrição municipal<input name="inscricao_municipal"></label><label>E-mail (cobrança)<input name="email"></label><label>Telefone / WhatsApp<input name="telefone"></label></div>
    <p><button class="btn" id="sc">Salvar cliente</button> <button class="btn sec" id="lc">Novo</button></p></div>
    <div class="card"><div class="barra"><label style="flex:1">Procurar<input id="c_f" placeholder="nome ou CNPJ"></label></div><div id="c_tab"></div></div>`;
  const END = ["tipo_logradouro", "logradouro", "numero", "complemento", "bairro", "cep", "codigo_municipio", "uf"];
  const preencher = c => { $("#c_doc").value = c.cpf_cnpj || ""; $$("#fcli [name]").forEach(i => i.value = (END.includes(i.name) ? (c.endereco || {})[i.name] : c[i.name]) || ""); };
  const desenhar = () => { const f = $("#c_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#c_tab").innerHTML = `<p class="sub">${ST.clientes.length} cliente(s). Sem e-mail ou telefone o cliente não recebe a régua de cobrança.</p>` + tabela([{ t: "Cliente", f: c => esc(c.razao_social) }, { t: "CPF/CNPJ", f: c => fmtDoc(c.cpf_cnpj) },
      { t: "Contato", f: c => (c.email ? "✉ " : "") + (c.telefone ? "📱" : "") || '<span class="sub">sem contato</span>' }, { t: "Última nota", f: c => c.ultimo_valor ? `${dt(c.ultima_data)} · ${Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "" },
      { t: "", f: c => `<button class="btn min sec" data-ed="${c.cpf_cnpj}">Editar</button> <button class="btn min sec" data-ex="${c.cpf_cnpj}">✕</button>` }],
      ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)));
    $$("[data-ed]").forEach(b => b.onclick = () => { preencher(ST.clientes.find(c => c.cpf_cnpj == b.dataset.ed)); scrollTo(0, 0); });
    $$("[data-ex]").forEach(b => b.onclick = async () => { if (confirm("Excluir do cadastro?")) { await api("cliente/excluir", { cpf_cnpj: b.dataset.ex }); await carregarEstado(); desenhar(); } }); };
  $("#c_f").oninput = desenhar; desenhar();
  $("#bc").onclick = async () => { const r = await api("cnpj", { cnpj: $("#c_doc").value }); preencher(r); aviso("Dados da Receita preenchidos. Confira e salve."); };
  $("#lc").onclick = () => preencher({});
  $("#sc").onclick = async () => { const f = form($("#fcli")), e = {}; END.forEach(k => { e[k] = f[k]; delete f[k]; });
    await api("cliente/salvar", { ...f, cpf_cnpj: $("#c_doc").value, endereco: e }); aviso("Cliente salvo ✔"); await carregarEstado(); desenhar(); };
};

// ---------------------------------------------------------------- configurações
PAGINAS.config = async el => {
  const c = await api("config");
  const ck = (s, k, t) => `<label class="chk"><input type="checkbox" data-s="${s}" data-k="${k}" ${c[s][k] ? "checked" : ""}> ${t}</label>`;
  const sl = (s, k, t, ops) => `<label>${t}<select data-s="${s}" data-k="${k}">${ops.map(([v, x]) => `<option value="${v}" ${String(c[s][k]) == v ? "selected" : ""}>${x}</option>`).join("")}</select></label>`;
  const tx = (s, k, t, tipo = "text", extra = "") => `<label>${t}<input type="${tipo}" data-s="${s}" data-k="${k}" value="${esc(Array.isArray(c[s][k]) ? c[s][k].join(", ") : c[s][k])}" ${extra}></label>`;
  el.innerHTML = `<h1>Configurações <span class="acoes"><button class="btn" id="salvar">Salvar tudo</button></span></h1>
  <div class="card"><h2>🤖 Robô financeiro</h2><p class="sub">Com o robô ligado, o sistema roda sozinho ao abrir e a cada hora (e todo dia pelo Agendador do Windows, se você rodar INSTALAR.bat): gera os títulos dos contratos, emite as NFS-e (só em produção), cria o PIX/boleto, envia a régua de cobrança, dá baixa nos pagamentos e faz backup.</p>
    <div class="campos">${ck("automacao", "ativa", "<b>Robô ligado</b>")}${ck("automacao", "gerar_titulos", "Gerar títulos dos contratos")}${ck("automacao", "emitir_nfse", "Emitir NFS-e")}${ck("automacao", "criar_cobranca", "Criar PIX/boleto")}${ck("automacao", "baixar_boletos", "Salvar PDF dos boletos")}
    ${ck("automacao", "regua", "Régua de cobrança")}${ck("automacao", "sincronizar_asaas", "Baixa automática (Asaas)")}${ck("automacao", "despesas_recorrentes", "Despesas recorrentes")}${ck("automacao", "backup", "Backup diário")}</div></div>
  <div class="card"><h2>🧾 Emissão da NFS-e</h2><p class="sub">Escolha por onde as notas saem. <b>Itaboraí</b>: webservice da prefeitura (chave no .env). <b>Nacional</b>: Emissor Nacional da NFS-e (Sefin/ADN — nfse.gov.br), com o certificado digital A1 do escritório. A nota já emitida é sempre cancelada pelo canal em que saiu. Homologação no nacional = “Produção Restrita”.</p>
    <div class="campos"><label>Canal de emissão<select data-s="emissao" data-k="canal">${[["municipal", "Itaboraí (webservice)"], ["nacional", "Nacional (nfse.gov.br)"]].map(([v, t]) => `<option value="${v}" ${c.emissao.canal == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${tx("emissao", "certificado_pfx", "Certificado A1 (.pfx)", "text", 'placeholder="C:\\Users\\...\\certificado.pfx"')}${tx("emissao", "certificado_senha", "Senha do certificado", "password")}
    ${tx("emissao", "serie_dps", "Série da DPS")}${tx("emissao", "proximo_dps", "Próximo nº da DPS", "number")}
    ${sl("emissao", "op_simp_nac", "Situação no Simples Nacional", [["1", "Não optante"], ["2", "MEI"], ["3", "ME/EPP"]])}
    ${sl("emissao", "reg_ap_trib_sn", "Apuração no Simples", [["1", "Tudo no DAS"], ["2", "ISS fora do DAS (fixo)"], ["3", "Tudo fora do DAS"]])}
    ${sl("emissao", "reg_esp_trib", "Regime especial", [["0", "Nenhum"], ["1", "Ato cooperado"], ["2", "Estimativa"], ["3", "ME municipal"], ["4", "Notário/registrador"], ["5", "Autônomo"], ["6", "Soc. de profissionais"]])}
    ${ck("emissao", "informar_ibscbs", "Informar IBS/CBS (cIndOp/cClassTrib do serviço padrão)")}${ck("emissao", "informar_im", "Informar inscrição municipal")}</div>
    <p><button class="btn sec" id="teste_cert">Testar certificado e conexão</button> <span class="sub">Salve antes de testar.</span></p><div id="cert_res"></div></div>
  <div class="card"><h2>Automações de entrada</h2><div class="campos">${ck("automacao", "importar_xml", "Ler XML das notas (clientes, notas emitidas fora, contratos)")}${ck("automacao", "enriquecer_contatos", "Completar e-mail/telefone pela Receita")}${ck("automacao", "importar_extratos", "Importar extratos .ofx da pasta")}${ck("automacao", "despesas_do_extrato", "Débitos do extrato viram despesas")}${ck("automacao", "resumo_diario", "Resumo diário por e-mail")}</div>
    <div class="campos" style="margin-top:12px">${tx("pastas", "xml_nfse", "Pasta dos XML de NFS-e")}${tx("pastas", "extratos", "Pasta dos extratos (.ofx)")}${tx("resumo", "email_dono", "E-mail para o resumo diário")}${tx("financeiro", "inicio_financeiro", "Notas externas a partir de", "date")}</div>
    <p><button class="btn sec" id="imp_xml">Ler XML agora</button> <button class="btn sec" id="imp_cont">Completar contatos agora</button> <button class="btn sec" id="env_res">Enviar resumo agora</button></p></div>
  <div class="card"><h2>WhatsApp</h2><div class="campos">
    <label>Envio<select data-s="whatsapp" data-k="provedor">${[["link", "Link wa.me (1 clique por mensagem)"], ["zapi", "Z-API (automático)"], ["evolution", "Evolution API (automático)"]].map(([v, t]) => `<option value="${v}" ${c.whatsapp.provedor == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${tx("whatsapp", "zapi_instancia", "Z-API: instância")}${tx("whatsapp", "zapi_token", "Z-API: token", "password")}${tx("whatsapp", "zapi_client_token", "Z-API: client token", "password")}
    ${tx("whatsapp", "evolution_url", "Evolution: URL")}${tx("whatsapp", "evolution_instancia", "Evolution: instância")}${tx("whatsapp", "evolution_apikey", "Evolution: apikey", "password")}</div>
    <p><button class="btn sec" id="teste_zap">Enviar WhatsApp de teste</button></p></div>
  <div class="card"><h2>Regras de despesa do extrato</h2><p class="sub">Uma por linha: PALAVRA = Categoria. Débito cujo histórico contém a palavra entra nessa categoria.</p>
    <textarea id="regras" rows="6">${esc(c.regras_despesa.map(([p, k]) => `${p.trim()} = ${k}`).join("\n"))}</textarea></div>
  <div class="card"><h2>Empresa e PIX</h2><div class="campos">${tx("empresa", "nome", "Nome no PIX")}${tx("empresa", "pix_chave", "Chave PIX que recebe")}${tx("empresa", "pix_cidade", "Cidade (PIX)")}${tx("empresa", "whatsapp", "WhatsApp do escritório")}${tx("empresa", "assinatura", "Assinatura das mensagens")}</div></div>
  <div class="card"><h2>Cobrança</h2><div class="campos">
    <label>Meio de cobrança<select data-s="cobranca" data-k="provedor">${[["pix", "PIX copia e cola (sem tarifa, baixa pelo extrato)"], ["asaas", "Asaas: boleto + PIX com baixa automática"], ["nenhum", "Nenhum"]].map(([v, t]) => `<option value="${v}" ${c.cobranca.provedor == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${tx("cobranca", "asaas_api_key", "Chave API Asaas", "password")}${ck("cobranca", "asaas_sandbox", "Asaas em sandbox (teste)")}
    ${tx("cobranca", "multa_pct", "Multa (%)")}${tx("cobranca", "juros_mes_pct", "Juros ao mês (%)")}${tx("cobranca", "regua_dias", "Régua (dias, ex.: -3, 0, 1, 5, 15, 30)")}
    ${ck("cobranca", "regua_email", "Régua por e-mail (automático)")}${ck("cobranca", "regua_whatsapp", "Régua por WhatsApp (fila com 1 clique)")}${ck("cobranca", "anexar_boleto", "Anexar o PDF do boleto no e-mail")}${tx("pastas", "boletos", "Pasta dos PDFs dos boletos")}${tx("cobranca", "bloquear_apos_dias", "Alerta de atraso crítico após (dias)", "number")}</div></div>
  <div class="card"><h2>E-mail (SMTP)</h2><p class="sub">Gmail: servidor smtp.gmail.com, porta 587, e uma “senha de app” da conta Google.</p><div class="campos">${tx("smtp", "host", "Servidor")}${tx("smtp", "porta", "Porta", "number")}${tx("smtp", "usuario", "Usuário")}${tx("smtp", "senha", "Senha", "password")}${tx("smtp", "remetente", "Remetente")}${tx("smtp", "copia_para", "Cópia oculta para")}${ck("smtp", "ssl", "SSL direto (porta 465)")}</div>
    <p><button class="btn sec" id="teste_email">Enviar e-mail de teste</button></p></div>
  <div class="card"><h2>Financeiro</h2><div class="campos">${tx("financeiro", "dia_vencimento_padrao", "Dia de vencimento padrão", "number")}${tx("financeiro", "dia_geracao", "Dia de gerar a recorrência", "number")}${tx("financeiro", "prazo_avulso_dias", "Prazo da nota avulsa (dias)", "number")}
    ${tx("financeiro", "aliquota_simples_pct", "Alíquota DAS sem histórico (%)")}${ck("financeiro", "iss_fixo", "ISS fixo fora do DAS (escritório contábil)")}${tx("financeiro", "categorias_despesa", "Categorias de despesa")}</div></div>`;
  $("#salvar").onclick = async () => {
    const novo = { empresa: {}, smtp: {}, cobranca: {}, financeiro: {}, automacao: {}, pastas: {}, whatsapp: {}, resumo: {}, emissao: {} };
    novo.regras_despesa = $("#regras").value.split("\n").map(l => l.split("=")).filter(x => x.length == 2 && x[0].trim()).map(([p, k]) => [p.trim().toUpperCase() + (p.trim().length <= 3 ? " " : ""), k.trim()]);
    $$("[data-s]").forEach(i => { let v = i.type == "checkbox" ? i.checked : i.value;
      if (["regua_dias"].includes(i.dataset.k)) v = v.split(/[,;\s]+/).filter(Boolean).map(Number);
      else if (i.dataset.k == "categorias_despesa") v = v.split(",").map(s => s.trim()).filter(Boolean);
      else if (["multa_pct", "juros_mes_pct", "aliquota_simples_pct"].includes(i.dataset.k)) v = valorNum(v);
      else if (i.type == "number") v = Number(v);
      novo[i.dataset.s][i.dataset.k] = v; });
    await api("config/salvar", novo); await carregarEstado(); aviso("Configurações salvas ✔");
  };
  $("#teste_cert").onclick = async () => {
    $("#cert_res").innerHTML = '<div class="msg">Abrindo o certificado e consultando o ADN…</div>';
    try { const r = await api("nacional/testar");
      $("#cert_res").innerHTML = `<div class="msg ${r.conexao && !r.vencido ? "ok" : "erro"}"><b>${esc(r.titular)}</b> — CNPJ ${fmtDoc(r.cnpj || "")} — válido até ${r.validade} (${r.dias_restantes} dias)<br>${esc(r.mensagem)}${r.convenio ? "<br>Convênio do município: " + esc(JSON.stringify(r.convenio)) : ""}</div>`;
    } catch (e) { $("#cert_res").innerHTML = ""; }
  };
  $("#teste_zap").onclick = async () => { const t = prompt("Enviar teste para qual WhatsApp (com DDD)?"); if (!t) return; await api("whatsapp/testar", { telefone: t }); aviso("WhatsApp de teste enviado ✔"); };
  $("#imp_xml").onclick = async () => { aviso("Lendo XML…"); const r = await api("importacao/xml"); aviso(`XML: ${JSON.stringify(r)}`, 8000); await carregarEstado(); };
  $("#imp_cont").onclick = async () => { aviso("Consultando a Receita…"); const r = await api("importacao/contatos", { limite: 50 }); aviso(`${r.atualizados} cliente(s) com contato completado ✔`, 6000); await carregarEstado(); };
  $("#env_res").onclick = async () => { const r = await api("resumo/enviar"); aviso("Resumo: " + r.resultado, 6000); };
  $("#teste_email").onclick = async () => { const p = prompt("Enviar teste para qual e-mail?"); if (!p) return; await api("email/testar", { para: p }); aviso("E-mail de teste enviado ✔"); };
};

// ---------------------------------------------------------------- início
(async () => { await carregarEstado(); const h = location.hash.slice(1); ir(h in PAGINAS ? h : "painel"); })();
