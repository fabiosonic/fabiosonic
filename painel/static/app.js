/* Painel Quant B3 — front-end (vanilla JS + TradingView Lightweight Charts) */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const num2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const int0 = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const R = (v) => (v == null ? "—" : brl.format(v));
const N = (v) => (v == null ? "—" : num2.format(v));
const P = (v, casas = 1) => (v == null ? "—" : `${v > 0 ? "+" : ""}${(v * 100).toFixed(casas).replace(".", ",")}%`);
const Pabs = (v, casas = 1) => (v == null ? "—" : `${(v * 100).toFixed(casas).replace(".", ",")}%`);
const cls = (v) => (v == null ? "" : v > 0 ? "sobe" : v < 0 ? "desce" : "");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const estado = { resumo: null, ranking: null, scanner: null, lab: null, ativo: "IBOV", dias: 252, estrategia: "dividendos", universo: "44 ações", chat: [], rebal: null };

// ---------------------------------------------------------------- utilidades
async function api(caminho, opcoes = {}) {
  const r = await fetch(caminho, { headers: { "Content-Type": "application/json" }, ...opcoes });
  const corpo = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(corpo.detail || `Erro ${r.status}`);
  return corpo;
}
function toast(msg, tipo = "") {
  const t = document.createElement("div");
  t.className = `toast ${tipo}`;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 5000);
}
function css(nome) { return getComputedStyle(document.documentElement).getPropertyValue(nome).trim(); }
function tabela(colunas, linhas, opcoes = {}) {
  if (!linhas.length) return `<div class="vazio"><b>${opcoes.vazioTitulo || "Nada por aqui"}</b>${opcoes.vazio || ""}</div>`;
  const th = colunas.map((c) => `<th class="${c.n ? "n" : ""}">${c.t}</th>`).join("");
  const tr = linhas.map((l, i) => `<tr class="${opcoes.clicavel ? "clicavel" : ""}" data-i="${i}">${colunas.map((c) => `<td class="${c.n ? "n" : ""}">${c.f(l)}</td>`).join("")}</tr>`).join("");
  return `<table><thead><tr>${th}</tr></thead><tbody>${tr}</tbody></table>`;
}
const etiquetaDirecao = (d) => `<span class="etiqueta ${d === "Compra" ? "compra" : "venda"}">${d === "Compra" ? "COMPRAR" : "VENDER"}</span>`;
function evidencia(e) {
  if (!e || e.excesso_cdi_aa == null) return `<span class="etiqueta">sem estudo</span>`;
  const consistente = e.metade1 > 0 && e.metade2 > 0;
  const c = e.excesso_cdi_aa > 0 ? (consistente ? "compra" : "aviso") : "venda";
  return `<span class="etiqueta ${c}" title="1ª metade ${P(e.metade1)} · 2ª metade ${P(e.metade2)} · queda máx. ${P(e.dd_max, 0)}">${P(e.excesso_cdi_aa)} a.a.${consistente ? " ✓" : ""}</span>`;
}

// ---------------------------------------------------------------- navegação e tema
$$("#abas button").forEach((b) => b.addEventListener("click", () => abrirAba(b.dataset.aba)));
function abrirAba(id) {
  $$("#abas button").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === id));
  $$(".secao").forEach((s) => s.classList.toggle("ativa", s.id === id));
  history.replaceState(null, "", `#${id}`);
  if (id === "laboratorio") carregarLab();
  if (id === "fiscal") carregarFiscal();
  if (id === "robo") carregarRobo();
  if (id === "ranking") carregarRebal();
}
function aplicarTema(t) {
  document.documentElement.dataset.theme = t;
  try { localStorage.setItem("tema", t); } catch (_) {}
  atualizarCoresGraficos();
}
$("#btn-tema").addEventListener("click", () => aplicarTema(document.documentElement.dataset.theme === "light" ? "dark" : "light"));
(() => { let t = "dark"; try { t = localStorage.getItem("tema") || "dark"; } catch (_) {} document.documentElement.dataset.theme = t; })();

// ---------------------------------------------------------------- KPIs e topo
function renderResumo() {
  const r = estado.resumo, m = r.mercado;
  $("#pilula-dados").innerHTML = `<span class="ponto"></span>Dados até ${m.data_dados.split("-").reverse().join("/")}`;
  const pm = $("#pilula-modo");
  pm.className = `pilula ${r.parar || r.kill_switch ? "perigo" : r.modo === "real" ? "alerta" : "ok"}`;
  pm.innerHTML = `<span class="ponto"></span>${r.parar ? "ROBÔ TRAVADO" : r.kill_switch ? "KILL SWITCH" : r.modo === "real" ? "MODO REAL" : r.modo === "manual" ? "MODO MANUAL" : "SIMULADO"}`;
  const kpis = [
    { r: r.modo === "manual" ? "Meu patrimônio (registrado)" : "Patrimônio do robô", v: R(r.patrimonio), rod: `<span class="${cls(r.resultado_total)}">${P(r.resultado_total_pct, 2)}</span> desde o início` },
    { r: "Resultado", v: `<span class="${cls(r.resultado_total)}">${R(r.resultado_total)}</span>`, rod: `realizado ${R(r.resultado_realizado)}` },
    { r: "Exposição", v: Pabs(r.exposicao_pct, 0), rod: `${r.posicoes.length}/${r.regras.max_posicoes} posições`, barra: r.exposicao_pct },
    { r: "Risco aberto (até stops)", v: R(r.risco_aberto), rod: `${Pabs(r.risco_aberto_pct, 2)} do patrimônio`, barra: r.risco_aberto_pct / r.regras.perda_maxima_total, aviso: true },
    { r: "Ibovespa", v: int0.format(m.ibov), rod: `<span class="${cls(m.ibov_dia)}">${P(m.ibov_dia, 2)} dia</span> · <span class="${cls(m.ibov_12m)}">${P(m.ibov_12m)} 12m</span>` },
    { r: "Regime · CDI", v: `<span class="${m.ibov_acima_mm200 ? "sobe" : "desce"}">${m.ibov_acima_mm200 ? "Alta" : "Baixa"}</span>`, rod: `${P(m.ibov_dist_mm200)} da MM200 · CDI ${Pabs(m.cdi_aa)} a.a.` },
  ];
  $("#kpis").innerHTML = kpis.map((k) => `<div class="cartao kpi"><div class="kpi-rotulo">${k.r}</div><div class="kpi-valor">${k.v}</div>
    <div class="kpi-rodape">${k.rod}</div>${k.barra != null ? `<div class="barra ${k.aviso ? "aviso" : ""}"><span style="width:${Math.min(100, Math.max(0, k.barra * 100))}%"></span></div>` : ""}</div>`).join("");
  renderPosicoes();
}
function renderPosicoes() {
  const r = estado.resumo;
  const col = [
    { t: "Ativo", f: (p) => `<span class="tk">${p.ticker}</span>` },
    { t: "Qtd", n: 1, f: (p) => int0.format(p.quantidade) },
    { t: "PM", n: 1, f: (p) => N(p.preco_medio) },
    { t: "Atual", n: 1, f: (p) => N(p.preco) },
    { t: "Resultado", n: 1, f: (p) => `<span class="${cls(p.resultado)}">${R(p.resultado)} (${P(p.resultado_pct)})</span>` },
    { t: "Stop", n: 1, f: (p) => `${N(p.stop)} <span class="nota">${P(p.dist_stop_pct)}</span>` },
    { t: "Na Clear", f: (p) => (p.stop_enviado ? `<span class="etiqueta compra">stop ativo</span>` : `<span class="etiqueta aviso">sem stop</span>`) },
  ];
  const vazio = { vazioTitulo: "Sem posições abertas", vazio: "Use o scanner, a análise de IA ou o rebalanceamento para gerar ordens." };
  $("#tab-posicoes-resumo").innerHTML = tabela(col, r.posicoes, vazio);
  $("#tab-posicoes").innerHTML = tabela(col, r.posicoes, vazio);
  $("#sub-posicoes").textContent = r.modo === "manual" ? "operações registradas por você" : `carteira ${r.carteira} · caixa ${R(r.caixa)}`;
  $$(".cartao-topo h2").forEach((h) => { if (h.textContent === "Posições do robô" && r.modo === "manual") h.textContent = "Minhas posições"; });
  $("#sub-carteira").textContent = `Carteira ${r.carteira} · capital de teste ${R(r.capital_inicial)} · risco por operação ${Pabs(r.regras.risco_por_operacao)} · kill switch em -${Pabs(r.regras.perda_maxima_total, 0)}`;
  const concentr = r.posicoes.length ? Math.max(...r.posicoes.map((p) => p.valor)) / r.patrimonio : 0;
  $("#risco-cards").innerHTML = [
    { r: "Risco aberto até os stops", v: R(r.risco_aberto), rod: `${Pabs(r.risco_aberto_pct, 2)} do patrimônio`, b: r.risco_aberto_pct / r.regras.perda_maxima_total },
    { r: "Maior concentração", v: Pabs(concentr, 0), rod: "limite por ativo: 40%", b: concentr / 0.4 },
    { r: "Orçamento de perda consumido", v: Pabs(Math.max(0, -r.resultado_total_pct) / r.regras.perda_maxima_total, 0), rod: `kill switch trava em ${R(r.capital_inicial * (1 - r.regras.perda_maxima_total))}`, b: Math.max(0, -r.resultado_total_pct) / r.regras.perda_maxima_total },
  ].map((k) => `<div class="cartao kpi"><div class="kpi-rotulo">${k.r}</div><div class="kpi-valor">${k.v}</div><div class="kpi-rodape">${k.rod}</div><div class="barra aviso"><span style="width:${Math.min(100, Math.max(0, k.b * 100))}%"></span></div></div>`).join("");
  const cust = r.custodia_clear;
  $("#sub-custodia").textContent = cust ? `sincronizada em ${cust.atualizado_em}` : "não sincronizada";
  const linhasCust = cust ? Object.entries(cust.posicoes).map(([t, v]) => ({ t, ...v })) : [];
  $("#tab-custodia").innerHTML = tabela([
    { t: "Ativo", f: (x) => `<span class="tk">${x.t}</span>` }, { t: "Qtd", n: 1, f: (x) => int0.format(x.quantidade) }, { t: "PM", n: 1, f: (x) => N(x.preco_medio) },
  ], linhasCust, { vazioTitulo: "Custódia não sincronizada", vazio: "Na aba Robô Clear, clique em “Sincronizar custódia”." });
  $("#tab-trades").innerHTML = tabela([
    { t: "Ativo", f: (x) => `<span class="tk">${x.ticker}</span>` }, { t: "Entrada", f: (x) => x.entrada }, { t: "Saída", f: (x) => x.saida },
    { t: "Qtd", n: 1, f: (x) => int0.format(x.quantidade) }, { t: "Resultado", n: 1, f: (x) => `<span class="${cls(x.resultado)}">${R(x.resultado)}</span>` },
    { t: "Motivo", f: (x) => `<span class="etiqueta">${esc(x.motivo)}</span>${x.day_trade ? ' <span class="etiqueta aviso">day trade</span>' : ""}` },
  ], [...r.trades].reverse(), { vazioTitulo: "Nenhuma operação encerrada" });
}

// ---------------------------------------------------------------- gráfico principal
let gPrincipal, gMacd, sVelas, sVol, sM9, sM21, sM200, sMacd, sSinal, sHist;
function opcoesGrafico(altura) {
  return {
    autoSize: true, height: altura,
    layout: { background: { type: "solid", color: "transparent" }, textColor: css("--texto-2"), fontFamily: "Inter, system-ui", fontSize: 11 },
    grid: { vertLines: { color: css("--borda") }, horzLines: { color: css("--borda") } },
    rightPriceScale: { borderColor: css("--borda") }, timeScale: { borderColor: css("--borda"), timeVisible: false },
    crosshair: { mode: 1 }, localization: { locale: "pt-BR", priceFormatter: (p) => (Math.abs(p) >= 10000 ? int0.format(p) : num2.format(p)) },
  };
}
function criarGraficos() {
  if (!window.LightweightCharts) { $("#grafico-principal").innerHTML = '<div class="vazio"><b>Biblioteca de gráficos indisponível</b>Verifique a conexão com a internet.</div>'; return; }
  gPrincipal = LightweightCharts.createChart($("#grafico-principal"), opcoesGrafico(400));
  sVelas = gPrincipal.addCandlestickSeries({ upColor: css("--alta"), downColor: css("--baixa"), borderVisible: false, wickUpColor: css("--alta"), wickDownColor: css("--baixa") });
  sVol = gPrincipal.addHistogramSeries({ priceScaleId: "", priceFormat: { type: "volume" }, lastValueVisible: false, priceLineVisible: false });
  sVol.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  sM9 = gPrincipal.addLineSeries({ color: "#f5b84a", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
  sM21 = gPrincipal.addLineSeries({ color: "#4f8cff", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
  sM200 = gPrincipal.addLineSeries({ color: "#a78bfa", lineWidth: 2, priceLineVisible: false, lastValueVisible: false });
  gMacd = LightweightCharts.createChart($("#grafico-macd"), { ...opcoesGrafico(120), timeScale: { visible: false } });
  sHist = gMacd.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
  sMacd = gMacd.addLineSeries({ color: css("--alta"), lineWidth: 1, priceLineVisible: false });
  sSinal = gMacd.addLineSeries({ color: "#f0566a", lineWidth: 1, priceLineVisible: false });
  gPrincipal.timeScale().subscribeVisibleLogicalRangeChange((r) => r && gMacd.timeScale().setVisibleLogicalRange(r));
}
function atualizarCoresGraficos() {
  [gPrincipal, gMacd, gLab].forEach((g) => g && g.applyOptions({
    layout: { textColor: css("--texto-2") }, grid: { vertLines: { color: css("--borda") }, horzLines: { color: css("--borda") } },
  }));
}
async function carregarGrafico() {
  if (!gPrincipal) return;
  try {
    const g = await api(`/api/grafico/${encodeURIComponent(estado.ativo)}?dias=${estado.dias + 200}`);
    const corte = g.velas.length - estado.dias;
    const cortar = (a) => a.filter((x) => x.time >= g.velas[Math.max(0, corte)].time);
    const velas = cortar(g.velas);
    sVelas.setData(velas);
    sVol.setData(cortar(g.volume).map((v) => ({ ...v, color: v.color === "up" ? css("--alta-suave") : css("--baixa-suave") })));
    sM9.setData(cortar(g.linhas.mme9)); sM21.setData(cortar(g.linhas.mme21)); sM200.setData(cortar(g.linhas.mms200));
    sMacd.setData(cortar(g.linhas.macd)); sSinal.setData(cortar(g.linhas.sinal));
    sHist.setData(cortar(g.linhas.hist).map((h) => ({ ...h, color: h.value >= 0 ? css("--alta-suave") : css("--baixa-suave") })));
    sVelas.setMarkers(cortar(g.marcas).map((m) => ({ time: m.time, position: m.tipo === "compra" ? "belowBar" : "aboveBar", color: m.tipo === "compra" ? css("--alta") : css("--baixa"), shape: m.tipo === "compra" ? "arrowUp" : "arrowDown", size: 0.8 })));
    gPrincipal.timeScale().fitContent();
    const u = velas[velas.length - 1], a = velas[velas.length - 2];
    $("#cot-preco").textContent = estado.ativo === "IBOV" ? int0.format(u.close) : N(u.close);
    const v = u.close / a.close - 1;
    $("#cot-var").className = `num ${cls(v)}`; $("#cot-var").textContent = P(v, 2);
  } catch (e) { toast(e.message, "erro"); }
}
$("#sel-ativo").addEventListener("change", (e) => { estado.ativo = e.target.value; carregarGrafico(); });
$$("#seg-periodo button").forEach((b) => b.addEventListener("click", () => {
  $$("#seg-periodo button").forEach((x) => x.classList.toggle("ativa", x === b)); estado.dias = +b.dataset.dias; carregarGrafico();
}));
function verNoGrafico(t) { estado.ativo = t; $("#sel-ativo").value = t; abrirAba("visao"); carregarGrafico(); window.scrollTo({ top: 0, behavior: "smooth" }); }

// ---------------------------------------------------------------- scanner
function renderScanner() {
  const s = estado.scanner;
  const col = [
    { t: "Ativo", f: (o) => `<span class="tk">${o.ticker}</span>` },
    { t: "Setup", f: (o) => esc(o.setup) },
    { t: "Direção", f: (o) => etiquetaDirecao(o.direcao) },
    { t: "Gatilho", f: (o) => `<span class="nota">${esc(o.gatilho)}</span>` },
    { t: "Entrada", n: 1, f: (o) => N(o.entrada) },
    { t: "Stop", n: 1, f: (o) => N(o.stop) },
    { t: "Risco", n: 1, f: (o) => Pabs(o.risco_pct) },
    { t: "Tendência", f: (o) => (o.acima_mm200 ? '<span class="etiqueta compra">acima MM200</span>' : '<span class="etiqueta venda">abaixo MM200</span>') },
    { t: "Evidência 10a", f: (o) => evidencia(o.evidencia) },
    { t: "", f: (o, i) => `<button class="btn peq fantasma" data-acao="grafico" title="Ver no gráfico">📈</button> <button class="btn peq" data-acao="boleta">Ordem</button>` },
  ];
  const vz = { vazioTitulo: "Nenhum sinal no último pregão" };
  $("#tab-opps").innerHTML = tabela([...col.slice(0, 4), { t: "Saída", f: (o) => `<span class="nota">${esc(o.saida)}</span>` }, ...col.slice(4)], s.oportunidades, { ...vz, clicavel: true });
  $("#tab-opps-resumo").innerHTML = tabela([col[0], col[1], col[2], col[4], col[6], col[8], col[9]], s.oportunidades.slice(0, 8), { ...vz, clicavel: true });
  $("#sub-scanner").textContent = `${s.oportunidades.length} sinais · ${s.data.split("-").reverse().join("/")}`;
  ["#tab-opps", "#tab-opps-resumo"].forEach((sel) => $(sel).onclick = (ev) => {
    const tr = ev.target.closest("tr[data-i]"); if (!tr) return;
    const o = s.oportunidades[+tr.dataset.i];
    estado.atrBoleta = o.atr;
    if (ev.target.closest("[data-acao='grafico']")) { if (o.ticker !== "IBOV") verNoGrafico(o.ticker); return; }
    // clique na linha (ou no botão Ordem): boleta preenchida com entrada, stop, alvo 2R e tamanho pelo risco
    const avisos = [];
    if (o.direcao === "Compra" && !o.acima_mm200) avisos.push("ativo abaixo da média de 200 dias (tendência de baixa)");
    const evid = o.evidencia && o.evidencia.excesso_cdi_aa;
    if (evid != null && evid <= 0) avisos.push(`este setup perdeu para o CDI no estudo de 10 anos (${P(evid)} a.a.)`);
    else if (o.evidencia && !(o.evidencia.metade1 > 0 && o.evidencia.metade2 > 0)) avisos.push("resultado do setup inconsistente entre 2016–21 e 2021–26");
    abrirBoleta({ ticker: o.ticker, lado: o.direcao === "Compra" ? "C" : "V", preco: o.entrada, stop: o.stop, motivo: o.setup,
      aviso: avisos.length ? `⚠️ Sinal de ${o.direcao === "Compra" ? "COMPRA" : "VENDA"} FRACO: ${avisos.join("; ")}. Se entrar, use posição menor e respeite o stop.` : "" });
  });
}

// ---------------------------------------------------------------- ranking e rebalanceamento
let ordenacao = { campo: "rank_dy", asc: true };
function renderRanking() {
  const rk = estado.ranking;
  const alvo = rk.carteiras_alvo[estado.estrategia];
  const campoPadrao = { dividendos: "rank_dy", momentum: "rank_mom", mix: "rank_dy" }[estado.estrategia];
  if (!["rank_dy", "rank_mom"].includes(ordenacao.campo) || ordenacao.padrao !== estado.estrategia) ordenacao = { campo: campoPadrao, asc: true, padrao: estado.estrategia };
  const linhas = [...rk.ativos].sort((a, b) => ((a[ordenacao.campo] ?? -1e9) - (b[ordenacao.campo] ?? -1e9)) * (ordenacao.asc ? 1 : -1));
  const col = [
    { t: "Ativo", f: (a) => `<span class="tk">${a.ticker}</span>${alvo[a.ticker] ? ` <span class="etiqueta destaque">${Pabs(alvo[a.ticker], 0)}</span>` : ""}${a.alerta_dy ? ' <span class="etiqueta aviso" title="Preço caiu mais de 30% desde a máxima de 6 meses: o DY pode estar inflado por dividendos passados">armadilha?</span>' : ""}` },
    { t: "Preço", n: 1, f: (a) => N(a.preco) },
    { t: "Dia", n: 1, f: (a) => `<span class="${cls(a.var_dia)}">${P(a.var_dia, 2)}</span>` },
    { t: "3 meses", n: 1, f: (a) => `<span class="${cls(a.var_3m)}">${P(a.var_3m)}</span>` },
    { t: "DY 12m", n: 1, f: (a) => Pabs(a.dy_12m) },
    { t: "#DY", n: 1, f: (a) => a.rank_dy },
    { t: "Momentum 12-1", n: 1, f: (a) => `<span class="${cls(a.momentum_12_1)}">${P(a.momentum_12_1)}</span>` },
    { t: "#Mom", n: 1, f: (a) => a.rank_mom },
    { t: "Volatilidade", n: 1, f: (a) => Pabs(a.vol_anual, 0) },
  ];
  $("#tab-ranking").innerHTML = tabela(col, linhas, { clicavel: true });
  $("#sub-ranking").textContent = `${rk.ativos.length} ativos · ${rk.data.split("-").reverse().join("/")}`;
  $("#tab-ranking").onclick = (ev) => { const tr = ev.target.closest("tr[data-i]"); if (tr) verNoGrafico(linhas[+tr.dataset.i].ticker); };
}
$$("#seg-estrategia button").forEach((b) => b.addEventListener("click", () => {
  $$("#seg-estrategia button").forEach((x) => x.classList.toggle("ativa", x === b));
  estado.estrategia = b.dataset.e; renderRanking(); carregarRebal();
}));
async function carregarRebal() {
  try {
    const cap = +$("#inp-capital").value || 10000;
    const rb = await api(`/api/rebalanceamento?estrategia=${estado.estrategia}&capital=${cap}`);
    estado.rebal = rb;
    const tot = rb.ordens.reduce((s, o) => s + o.valor, 0);
    $("#rebal-saida").innerHTML = tabela([
      { t: "Ativo", f: (o) => `<span class="tk">${o.ticker}</span>` }, { t: "", f: (o) => etiquetaDirecao(o.lado === "C" ? "Compra" : "Venda") },
      { t: "Qtd", n: 1, f: (o) => int0.format(o.quantidade) }, { t: "Preço", n: 1, f: (o) => N(o.preco_ref) }, { t: "Valor", n: 1, f: (o) => R(o.valor) },
    ], rb.ordens, { vazioTitulo: "Carteira já está no alvo" }) + `<p class="nota">${rb.ordens.length} ordens · ${R(tot)} · base: ${rb.usa_custodia ? "custódia da Clear" : "carteira vazia (sincronize a custódia)"}</p>`;
  } catch (e) { $("#rebal-saida").innerHTML = `<div class="vazio">${esc(e.message)}</div>`; }
}
$("#inp-capital").addEventListener("change", carregarRebal);
$("#btn-rebal-fila").addEventListener("click", async () => {
  if (!estado.rebal || !estado.rebal.ordens.length) return toast("Nenhuma ordem de rebalanceamento.");
  if (!confirm(`Enviar ${estado.rebal.ordens.length} ordens limitadas à fila do robô?`)) return;
  for (const o of estado.rebal.ordens) {
    const folga = o.lado === "C" ? 1.005 : 0.995;
    await api("/api/fila", { method: "POST", body: JSON.stringify({ ticker: o.ticker, lado: o.lado, quantidade: o.quantidade, preco: +(o.preco_ref * folga).toFixed(2), motivo: o.motivo, origem: "rebalanceamento" }) });
  }
  toast("Ordens adicionadas à fila do robô.", "ok"); carregarRobo();
});

// ---------------------------------------------------------------- IA
function renderAnalise(a) {
  const ideias = (a.oportunidades || []).map((o, i) => `
    <div class="ideia">
      <div class="ideia-topo"><span><span class="tk">${esc(o.ticker)}</span> ${etiquetaDirecao(o.direcao)} <span class="etiqueta">${esc(o.estrategia)}</span></span>
        <span class="etiqueta ${o.confianca === "alta" ? "compra" : o.confianca === "media" ? "destaque" : "aviso"}">confiança ${o.confianca}</span></div>
      <div class="ideia-numeros num"><div><span>Entrada</span>${N(o.entrada)}</div><div><span>Stop</span>${N(o.stop)}</div><div><span>Risco</span>${Pabs(o.risco_pct)}</div></div>
      <p>${esc(o.tese)}</p><p><b>Saída:</b> ${esc(o.saida)}</p><p><b>Evidência:</b> ${esc(o.evidencia)}</p>
      <button class="btn peq" data-ideia="${i}">Montar ordem</button>
    </div>`).join("");
  const lista = (xs) => (xs && xs.length ? `<ul>${xs.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : "<p class='nota'>Nenhum.</p>");
  $("#ia-saida").innerHTML = `
    <div class="ia-bloco"><h3>Mercado · regime ${esc(a.regime)}</h3><p>${esc(a.resumo_mercado)}</p></div>
    <div class="ia-bloco"><h3>Postura</h3><p>${esc(a.postura_recomendada)}</p></div>
    <div class="ia-bloco"><h3>Ideias de operação (${(a.oportunidades || []).length})</h3>${ideias || "<p class='nota'>A IA não viu operações com boa relação risco/evidência hoje.</p>"}</div>
    <div class="ia-bloco"><h3>Alertas da carteira</h3>${lista(a.alertas_carteira)}</div>
    <div class="ia-bloco"><h3>Riscos</h3>${lista(a.riscos)}<p class="nota" style="margin-top:8px">${esc(a.modelo || "")} · apoio à decisão, não é recomendação.</p></div>`;
  $("#ia-saida").onclick = (ev) => {
    const b = ev.target.closest("[data-ideia]"); if (!b) return;
    const o = a.oportunidades[+b.dataset.ideia];
    abrirBoleta({ ticker: o.ticker, lado: o.direcao === "Compra" ? "C" : "V", preco: o.entrada, stop: o.stop, motivo: `IA: ${o.estrategia}` });
  };
}
$("#btn-ia").addEventListener("click", async () => {
  const b = $("#btn-ia"); b.disabled = true; b.textContent = "Analisando…"; $("#ia-orbe").classList.add("pensando");
  $("#ia-saida").innerHTML = `<div class="ia-bloco">${'<div class="esqueleto"></div>'.repeat(3)}<div class="esqueleto" style="width:60%"></div></div><div class="ia-bloco">${'<div class="esqueleto"></div>'.repeat(4)}</div>`;
  try { renderAnalise(await api("/api/ia/analise", { method: "POST" })); carregarUsoIA(); }
  catch (e) { $("#ia-saida").innerHTML = `<div class="vazio"><b>IA indisponível</b>${esc(e.message)}</div>`; }
  finally { b.disabled = false; b.textContent = "Gerar análise do dia"; $("#ia-orbe").classList.remove("pensando"); }
});

// chat
$("#chat-abrir").addEventListener("click", () => { $("#chat-painel").classList.toggle("aberto"); $("#chat-texto").focus(); });
$("#chat-fechar").addEventListener("click", () => $("#chat-painel").classList.remove("aberto"));
$$("#chat-sugestoes button").forEach((b) => b.addEventListener("click", () => { $("#chat-texto").value = b.textContent; enviarChat(); }));
$("#chat-texto").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); enviarChat(); } });
$("#chat-enviar").addEventListener("click", enviarChat);
function addMsg(papel, html) { const d = document.createElement("div"); d.className = `msg ${papel}`; d.innerHTML = html; $("#chat-msgs").appendChild(d); $("#chat-msgs").scrollTop = 1e9; return d; }
async function enviarChat() {
  const texto = $("#chat-texto").value.trim(); if (!texto) return;
  $("#chat-texto").value = ""; addMsg("user", esc(texto));
  const espera = addMsg("assistant", '<div class="esqueleto" style="width:180px"></div>'); $("#chat-orbe").classList.add("pensando");
  try {
    const r = await api("/api/ia/chat", { method: "POST", body: JSON.stringify({ pergunta: texto, historico: estado.chat, pesquisar_web: $("#chat-web").checked }) });
    espera.innerHTML = esc(r.resposta) + (r.fontes.length ? `<div class="fontes">Fontes: ${r.fontes.map((f, i) => `<a href="${esc(f.url)}" target="_blank" rel="noopener">[${i + 1}] ${esc(f.titulo).slice(0, 40)}</a>`).join(" ")}</div>` : "");
    estado.chat.push({ role: "user", content: texto }, { role: "assistant", content: r.resposta }); carregarUsoIA();
  } catch (e) { espera.innerHTML = `⚠️ ${esc(e.message)}`; }
  finally { $("#chat-orbe").classList.remove("pensando"); }
}

// ---------------------------------------------------------------- boleta
let ladoBoleta = "C";
function abrirBoleta({ ticker = estado.ativo, lado = "C", preco = null, stop = null, motivo = "", aviso = "" } = {}) {
  $("#b-aviso").textContent = aviso;
  if (ticker === "IBOV") ticker = "BOVA11";
  $("#b-ticker").value = ticker; $("#b-preco").value = preco ? (+preco).toFixed(2) : ""; $("#b-motivo").value = motivo;
  $("#b-tipo").value = "limitada"; $("#campo-disparo").style.display = "none"; definirLado(lado);
  // tamanho sugerido: risco por operação sobre o patrimônio do robô
  const r = estado.resumo;
  if (r && preco && stop && Math.abs(preco - stop) > 0) {
    const qtd = Math.max(1, Math.floor(Math.min(r.patrimonio * r.regras.risco_por_operacao / Math.abs(preco - stop), r.patrimonio * 0.4 / preco)));
    $("#b-qtd").value = qtd; $("#b-qtd").dataset.stop = stop;
  } else { $("#b-qtd").value = ""; delete $("#b-qtd").dataset.stop; }
  const risco1 = preco && stop ? Math.abs(preco - stop) : null;
  $("#b-sl").value = stop && lado === "C" ? (+stop).toFixed(2) : "";
  $("#b-tp").value = risco1 && lado === "C" ? (+preco + 2 * risco1).toFixed(2) : "";
  $("#b-tr-tipo").value = ""; $("#b-tr-valor").value = ""; $("#b-tr-ativ").value = "0"; $("#b-be").value = ""; $("#b-oco").checked = false; $("#b-rev").value = "avisar";
  atualizarResumoBoleta(); $("#modal-boleta").classList.add("aberto"); $("#b-qtd").focus();
}
function definirLado(l) { ladoBoleta = l; $$(".lado-toggle button").forEach((b) => b.classList.toggle("ativa", b.dataset.lado === l)); $("#b-protecoes").style.display = l === "C" && $("#b-tipo").value === "limitada" ? "" : "none"; ajustarBoletaAoModo(); atualizarResumoBoleta(); }
$$(".lado-toggle button").forEach((b) => b.addEventListener("click", () => definirLado(b.dataset.lado)));
$("#b-tipo").addEventListener("change", () => { const s = $("#b-tipo").value === "stop"; $("#campo-disparo").style.display = s ? "" : "none"; definirLado(s ? "V" : ladoBoleta); });
["#b-qtd", "#b-preco", "#b-ticker", "#b-disparo", "#b-sl", "#b-tp"].forEach((s) => $(s).addEventListener("input", atualizarResumoBoleta));
function lerProtecao() {
  if (ladoBoleta !== "C" || $("#b-tipo").value !== "limitada" || !$("#b-sl").value) return null;
  const pr = { stop: +$("#b-sl").value, take_profit: $("#b-tp").value ? +$("#b-tp").value : null, usa_oco: $("#b-oco").checked, na_reversao: $("#b-rev").value,
    breakeven_pct: $("#b-be").value ? +$("#b-be").value / 100 : null, trailing: null };
  const tipo = $("#b-tr-tipo").value;
  if (tipo) {
    const v = +$("#b-tr-valor").value;
    pr.trailing = { tipo, valor: tipo === "pct" ? v / 100 : v, ativacao_pct: (+$("#b-tr-ativ").value || 0) / 100 };
    if (tipo === "atr") pr.trailing.atr = estado.atrBoleta || null;
  }
  return pr;
}
function atualizarResumoBoleta() {
  const q = +$("#b-qtd").value, p = +$("#b-preco").value, stop = +$("#b-qtd").dataset.stop || null;
  if (!q || !p) { $("#b-resumo").textContent = "Informe quantidade e preço."; return; }
  const lotes = q >= 100 ? `${Math.floor(q / 100) * 100} no lote padrão${q % 100 ? ` + ${q % 100} no fracionário` : ""}` : `${q} no fracionário (${$("#b-ticker").value.toUpperCase()}F)`;
  const sl = +$("#b-sl").value || stop, tp = +$("#b-tp").value;
  const risco = sl && ladoBoleta === "C" ? ` · perda máx. no stop: <b class="desce">${R(Math.abs(p - sl) * q)}</b>` : "";
  const ganho = tp && sl && ladoBoleta === "C" ? ` · ganho no alvo: <b class="sobe">${R((tp - p) * q)}</b> (R:R ${num2.format((tp - p) / Math.abs(p - sl))})` : "";
  $("#b-resumo").innerHTML = `${ladoBoleta === "C" ? "Compra" : "Venda"} de <b>${int0.format(q)}</b> × ${N(p)} = <b>${R(q * p)}</b> · ${lotes}${risco}${ganho}`;
}
$$("[data-fechar]").forEach((b) => b.addEventListener("click", () => $("#modal-boleta").classList.remove("aberto")));
$("#modal-boleta").addEventListener("click", (e) => { if (e.target.id === "modal-boleta") e.target.classList.remove("aberto"); });
$("#btn-boleta-grafico").addEventListener("click", () => abrirBoleta({ ticker: estado.ativo }));
const modoManual = () => estado.resumo && estado.resumo.modo === "manual";
function ajustarBoletaAoModo() {
  const m = modoManual();
  $("#b-enviar").textContent = m ? (ladoBoleta === "C" ? "Registrar compra feita na Clear" : "Registrar venda feita na Clear") : "Adicionar à fila";
  $("#b-nota").textContent = m
    ? "Modo manual: primeiro execute a ordem na Clear; depois registre aqui o preço que você conseguiu. O painel passa a acompanhar e avisar quando subir o stop ou sair."
    : "A ordem não vai direto para a Clear: ela entra na fila e só é executada pelo robô, com sua confirmação.";
  $("#campo-stop-clear").style.display = m && ladoBoleta === "C" ? "" : "none";
  $(".modal .cartao-topo h2").textContent = m ? "Registrar operação feita na Clear" : "Nova ordem → fila do robô";
}
$("#b-enviar").addEventListener("click", async () => {
  if (modoManual()) {
    const corpo = { ticker: $("#b-ticker").value, quantidade: +$("#b-qtd").value, preco: +$("#b-preco").value,
      motivo: $("#b-motivo").value, stop_na_clear: $("#b-stop-clear").checked };
    if (ladoBoleta === "C") Object.assign(corpo, lerProtecao() || {});
    try {
      const r = await api(ladoBoleta === "C" ? "/api/manual/compra" : "/api/manual/venda", { method: "POST", body: JSON.stringify(corpo) });
      $("#modal-boleta").classList.remove("aberto");
      toast(ladoBoleta === "C" ? "Compra registrada: o painel está acompanhando este ativo." :
        `Venda registrada. Resultado: ${R(r.resultado)}.`, "ok");
      estado.resumo = await api("/api/resumo"); renderResumo(); carregarAcoes();
    } catch (e) { toast(e.message, "erro"); }
    return;
  }
  try {
    await api("/api/fila", { method: "POST", body: JSON.stringify({
      ticker: $("#b-ticker").value, lado: ladoBoleta, quantidade: +$("#b-qtd").value, preco: +$("#b-preco").value,
      tipo: $("#b-tipo").value, disparo: $("#b-disparo").value ? +$("#b-disparo").value : null, motivo: $("#b-motivo").value,
      protecao: lerProtecao() }) });
    $("#modal-boleta").classList.remove("aberto"); toast("Ordem adicionada à fila do robô.", "ok"); carregarRobo();
  } catch (e) { toast(e.message, "erro"); }
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") { $("#modal-boleta").classList.remove("aberto"); $("#chat-painel").classList.remove("aberto"); } });

// ---------------------------------------------------------------- laboratório
let gLab;
const CORES_LAB = { "Dividend yield": "#1fc28b", "Momentum 12-1": "#4f8cff", Universo: "#a78bfa", Ibovespa: "#f5b84a", CDI: "#9aa7b4" };
async function carregarLab() {
  try {
    if (!estado.lab) estado.lab = await api("/api/laboratorio");
    const lab = estado.lab;
    if (!gLab && window.LightweightCharts) {
      gLab = LightweightCharts.createChart($("#grafico-lab"), { ...opcoesGrafico(360), rightPriceScale: { mode: 1, borderColor: css("--borda") } });
      Object.entries(lab.curvas).forEach(([nome, dados]) => gLab.addLineSeries({ color: CORES_LAB[nome] || "#888", lineWidth: nome === "CDI" ? 1 : 2, lineStyle: nome === "CDI" ? 2 : 0, title: nome, priceLineVisible: false }).setData(dados));
      gLab.timeScale().fitContent();
      $("#legenda-lab").innerHTML = Object.keys(lab.curvas).map((n) => `<span><i style="background:${CORES_LAB[n]}"></i>${n}</span>`).join("");
    }
    $("#tab-fatores").innerHTML = tabela([
      { t: "Estratégia", f: (x) => esc(x.estrategia) }, { t: "CAGR", n: 1, f: (x) => P(x.cagr) },
      { t: "vs CDI", n: 1, f: (x) => `<span class="${cls(x.excesso_cdi)}">${P(x.excesso_cdi)}</span>` },
      { t: "2016–21", n: 1, f: (x) => `<span class="${cls(x.excesso_cdi_1a)}">${P(x.excesso_cdi_1a)}</span>` },
      { t: "2021–26", n: 1, f: (x) => `<span class="${cls(x.excesso_cdi_2a)}">${P(x.excesso_cdi_2a)}</span>` },
      { t: "Queda máx.", n: 1, f: (x) => P(x.dd_max, 0) },
    ], [...lab.fatores].sort((a, b) => b.excesso_cdi_2a - a.excesso_cdi_2a));
    renderSetups();
  } catch (e) { toast(e.message, "erro"); }
}
function renderSetups() {
  const linhas = estado.lab.setups.filter((s) => s.universo === estado.universo).sort((a, b) => b.excesso_cdi_aa - a.excesso_cdi_aa);
  $("#tab-setups").innerHTML = tabela([
    { t: "Setup", f: (x) => esc(x.setup) }, { t: "Lado", f: (x) => etiquetaDirecao(x.lado.startsWith("Comprado") ? "Compra" : "Venda") },
    { t: "vs CDI", n: 1, f: (x) => `<span class="${cls(x.excesso_cdi_aa)}">${P(x.excesso_cdi_aa)}</span>` },
    { t: "2016–21", n: 1, f: (x) => P(x.excesso_1a_metade) }, { t: "2021–26", n: 1, f: (x) => P(x.excesso_2a_metade) },
    { t: "Queda", n: 1, f: (x) => P(x.dd_max, 0) }, { t: "Trades", n: 1, f: (x) => int0.format(x.trades) },
  ], linhas);
}
$$("#seg-universo button").forEach((b) => b.addEventListener("click", () => { $$("#seg-universo button").forEach((x) => x.classList.toggle("ativa", x === b)); estado.universo = b.dataset.u; renderSetups(); }));

// ---------------------------------------------------------------- fiscal
async function carregarFiscal() {
  try {
    const f = await api("/api/fiscal");
    $("#tab-fiscal").innerHTML = tabela([
      { t: "Mês", f: (m) => m.mes }, { t: "Vendas de ações", n: 1, f: (m) => R(m.vendas_acoes) },
      { t: "Situação", f: (m) => (m.isento ? '<span class="etiqueta compra">isento</span>' : '<span class="etiqueta aviso">tributável</span>') },
      { t: "Resultado comum", n: 1, f: (m) => `<span class="${cls(m.resultado_comum_acoes + m.resultado_comum_outros)}">${R(m.resultado_comum_acoes + m.resultado_comum_outros)}</span>` },
      { t: "Day trade", n: 1, f: (m) => R(m.resultado_day_trade) }, { t: "Prejuízo a compensar", n: 1, f: (m) => R(m.prejuizo_comum_acumulado + m.prejuizo_dt_acumulado) },
      { t: "IR bruto", n: 1, f: (m) => R(m.imposto_bruto) }, { t: "IRRF", n: 1, f: (m) => R(m.irrf_utilizado) },
      { t: "DARF 6015", n: 1, f: (m) => `<b>${R(m.darf_6015)}</b>` },
    ], f.meses, { vazioTitulo: "Sem operações registradas", vazio: `Carteira ${f.carteira}.` });
  } catch (e) { toast(e.message, "erro"); }
}

// ---------------------------------------------------------------- robô
async function carregarRobo() {
  try {
    const [fila, logs, prots] = await Promise.all([api("/api/fila"), api("/api/robo/logs"), api("/api/protecoes")]);
    $("#tab-protecoes").innerHTML = tabela([
      { t: "Ativo", f: (x) => `<span class="tk">${x.ticker}</span>` }, { t: "Qtd", n: 1, f: (x) => int0.format(x.quantidade) },
      { t: "Entrada", n: 1, f: (x) => N(x.preco_entrada) },
      { t: "Atual", n: 1, f: (x) => `${N(x.preco)} <span class="${cls(x.resultado_pct)}">${P(x.resultado_pct)}</span>` },
      { t: "Stop loss", n: 1, f: (x) => `${N(x.stop)} <span class="nota">${P(x.dist_stop_pct)}</span>` },
      { t: "Próx. stop", n: 1, f: (x) => (x.proximo_stop > x.stop ? `<span class="sobe">${N(x.proximo_stop)}</span>` : "—") },
      { t: "Take profit", n: 1, f: (x) => (x.take_profit ? `${N(x.take_profit)} <span class="nota">${P(x.dist_alvo_pct)}</span>` : "—") },
      { t: "Trailing / BE", f: (x) => (x.trailing ? `<span class="etiqueta destaque">${x.trailing.tipo === "pct" ? Pabs(x.trailing.valor) : x.trailing.valor + "×ATR"}${x.trailing.ativacao_pct ? " após " + Pabs(x.trailing.ativacao_pct) : ""}</span>` : "—") + (x.breakeven_pct ? ` <span class="etiqueta">BE ${Pabs(x.breakeven_pct)}</span>` : "") + (x.usa_oco ? ' <span class="etiqueta">OCO</span>' : "") },
      { t: "Tendência", f: (x) => { const al = (estado.alertas || []).find((a) => a.ticker === x.ticker); return !x.ativa ? "—" : !al ? "—" : `<span class="etiqueta ${al.nivel === "SAIR" ? "venda" : al.nivel === "OK" ? "compra" : "aviso"}" title="${esc(al.sinais.join(" · "))}">${al.nivel === "OK" ? "intacta" : al.nivel}</span> <span class="nota">${x.na_reversao === "vender" ? "auto-saída" : "aviso"}</span>`; } },
      { t: "Status", f: (x) => (!x.ativa ? '<span class="etiqueta">encerrada</span>' : x.stop_enviado ? '<span class="etiqueta compra">stop na Clear</span>' : '<span class="etiqueta aviso">aguardando monitor</span>') },
      { t: "", f: (x) => `<button class="btn peq fantasma" data-remprot="${x.ticker}">remover</button>` },
    ], prots, { vazioTitulo: "Nenhuma proteção", vazio: "Defina stop loss, take profit e trailing na boleta de compra." });
    $("#tab-protecoes").onclick = async (ev) => {
      const t = ev.target.dataset.remprot;
      if (!t || !confirm(`Remover a proteção de ${t}? A ordem stop já registrada na Clear NÃO é cancelada automaticamente.`)) return;
      await api(`/api/protecoes/${t}`, { method: "DELETE" }); carregarRobo();
    };
    $("#sub-fila").textContent = `${fila.length} ordem(ns)`;
    $("#tab-fila").innerHTML = tabela([
      { t: "Ativo", f: (o) => `<span class="tk">${o.ticker}</span>` }, { t: "", f: (o) => etiquetaDirecao(o.lado === "C" ? "Compra" : "Venda") },
      { t: "Tipo", f: (o) => o.tipo }, { t: "Qtd", n: 1, f: (o) => int0.format(o.quantidade) }, { t: "Preço", n: 1, f: (o) => N(o.preco) },
      { t: "Status", f: (o) => `<span class="etiqueta ${o.status.startsWith("execut") ? "compra" : o.status.startsWith("falha") ? "venda" : "aviso"}">${esc(o.status)}</span>` },
      { t: "", f: (o) => `<button class="btn peq fantasma" data-rem="${o.id}">remover</button>` },
    ], fila, { vazioTitulo: "Fila vazia", vazio: "Monte ordens pelo scanner, pela IA, pela boleta ou pelo rebalanceamento." });
    $("#tab-fila").onclick = async (ev) => { const id = ev.target.dataset.rem; if (!id) return; await api(`/api/fila/${id}`, { method: "DELETE" }); carregarRobo(); };
    $("#log-robo").textContent = logs.length ? logs.join("\n") : "Sem registros hoje.";
  } catch (e) { toast(e.message, "erro"); }
}
$("#btn-sincronizar").addEventListener("click", async () => {
  try { const r = await api("/api/robo/sincronizar", { method: "POST" }); toast(r.mensagem, "ok"); } catch (e) { toast(e.message, "erro"); }
});
$("#btn-atualizar").addEventListener("click", async () => {
  const b = $("#btn-atualizar"); b.disabled = true; toast("Baixando cotações, dividendos e CDI… (1 a 3 min)");
  try { const r = await api("/api/dados/atualizar", { method: "POST" }); toast(`Dados atualizados em ${r.segundos}s.`, "ok"); estado.lab = null; await iniciar(); }
  catch (e) { toast(e.message, "erro"); } finally { b.disabled = false; }
});

// ---------------------------------------------------------------- consenso das casas
let filtroConsenso = "todos";
function renderConsenso() {
  const c = estado.consenso;
  if (!c || !c.ativos.length) { $("#tab-consenso").innerHTML = '<div class="vazio"><b>Sem dados de consenso</b>Clique em “Atualizar dados”.</div>'; return; }
  const compra = (a) => (a.nota_media || 9) <= 2.5;
  let linhas = c.ativos;
  if (filtroConsenso === "todos") linhas = linhas.filter(compra);
  if (filtroConsenso === "convergentes") linhas = linhas.filter((a) => compra(a) && a.convergencia.length >= 2);
  if (filtroConsenso === "neutros") linhas = linhas.filter((a) => !compra(a));
  const rec = (a) => {
    const n = a.nota_media || 9;
    return `<span class="etiqueta ${n <= 1.8 ? "compra" : n <= 2.5 ? "destaque" : n <= 3.5 ? "" : "venda"}">${esc(a.recomendacao)}</span>`;
  };
  const distrib = (a) => {
    const tot = a.compra + a.neutro + a.venda || 1;
    return `<div class="distrib" title="${a.compra} compra · ${a.neutro} neutro · ${a.venda} venda"><span style="width:${a.compra / tot * 100}%"></span><span style="width:${a.neutro / tot * 100}%"></span><span style="width:${a.venda / tot * 100}%"></span></div>`;
  };
  const faixa = (a) => {
    if (!a.alvo_min || !a.alvo_max) return "—";
    const lo = Math.min(a.alvo_min, a.preco), hi = Math.max(a.alvo_max, a.preco), pos = (v) => ((v - lo) / (hi - lo || 1)) * 100;
    return `<div class="faixa-alvo" title="mín ${N(a.alvo_min)} · médio ${N(a.alvo_medio)} · máx ${N(a.alvo_max)}"><i class="preco" style="left:${pos(a.preco)}%"></i><i class="alvo" style="left:${pos(a.alvo_medio)}%"></i></div>`;
  };
  $("#tab-consenso").innerHTML = tabela([
    { t: "Ativo", f: (a) => `<span class="tk">${a.ticker}</span> <span class="nota">${esc((a.nome || "").slice(0, 22))}</span>` },
    { t: "Consenso", f: rec },
    { t: "Nota", n: 1, f: (a) => (a.nota_media ? num2.format(a.nota_media) : "—") },
    { t: "Analistas", n: 1, f: (a) => a.analistas },
    { t: "Compra/Neutro/Venda", f: distrib },
    { t: "Preço", n: 1, f: (a) => N(a.preco) },
    { t: "Alvo médio", n: 1, f: (a) => N(a.alvo_medio) },
    { t: "Potencial", n: 1, f: (a) => `<b class="${cls(a.upside)}">${P(a.upside)}</b>` },
    { t: "Faixa de alvos", f: faixa },
    { t: "Convergência", f: (a) => a.convergencia.map((x) => `<span class="etiqueta ${x.startsWith("Top") ? "destaque" : "compra"}">${x}</span>`).join(" ") || "—" },
  ], linhas, { clicavel: true, vazioTitulo: "Nenhum ativo neste filtro" });
  $("#sub-consenso").textContent = `· ${linhas.length} ativos · atualizado ${c.atualizado_em}`;
  $("#tab-consenso").onclick = (ev) => { const tr = ev.target.closest("tr[data-i]"); if (tr) verNoGrafico(linhas[+tr.dataset.i].ticker); };
}
$$("#seg-consenso button").forEach((b) => b.addEventListener("click", () => {
  $$("#seg-consenso button").forEach((x) => x.classList.toggle("ativa", x === b)); filtroConsenso = b.dataset.f; renderConsenso();
}));
// ---------------------------------------------------------------- carteiras das casas
function renderCasas(d) {
  if (!d || !d.casas || !d.casas.length) return;
  $("#sub-casas").textContent = `· ${d.casas.length} carteiras · ${d.atualizado_em}${d.custo_usd != null ? ` · custo US$ ${num2.format(d.custo_usd)}` : ""}`;
  const citados = tabela([
    { t: "Ativo", f: (m) => `<span class="tk">${esc(m.ticker)}</span>` },
    { t: "Casas", n: 1, f: (m) => `<b>${m.casas}</b>` },
    { t: "Quem recomenda", f: (m) => `<span class="nota">${esc(m.nomes_casas.join(", "))}</span>` },
    { t: "Consenso", f: (m) => (m.consenso ? `<span class="etiqueta">${esc(m.consenso)}</span>` : "—") },
    { t: "Potencial", n: 1, f: (m) => `<span class="${cls(m.upside)}">${P(m.upside)}</span>` },
    { t: "Convergência", f: (m) => (m.convergencia || []).map((x) => `<span class="etiqueta ${x.startsWith("Top") ? "destaque" : "compra"}">${x}</span>`).join(" ") || "—" },
  ], d.mais_citados, { clicavel: true, vazioTitulo: "Sem ativos consolidados" });
  const lista = d.casas.map((c) => `<div class="casa-item"><b>${esc(c.casa)}</b> <span class="nota">· ${esc(c.carteira)} · ${esc(c.data)}</span>
      ${c.fonte ? ` <a href="${esc(c.fonte)}" target="_blank" rel="noopener">fonte ↗</a>` : ""}
      <div class="chips">${c.ativos.map((t) => `<span class="etiqueta">${esc(t)}</span>`).join("")}</div></div>`).join("");
  $("#casas-saida").innerHTML = `<div class="casas-grade"><div class="tabela-wrap" style="max-height:420px">${citados}</div><div class="lista-casas">${lista}</div></div>
    ${d.observacoes ? `<div class="legenda">${esc(d.observacoes)}</div>` : ""}`;
  $("#casas-saida").onclick = (ev) => {
    const tr = ev.target.closest("tr[data-i]"); if (!tr) return;
    const t = d.mais_citados[+tr.dataset.i].ticker.toUpperCase();
    const a = (estado.ranking?.ativos || []).find((x) => x.ticker === t);
    abrirBoleta({ ticker: t, lado: "C", preco: a ? a.preco : null, motivo: `Carteiras recomendadas (${d.mais_citados[+tr.dataset.i].casas} casas)` });
  };
}
async function carregarCasas() { try { renderCasas(await api("/api/casas")); } catch (_) {} }
$("#btn-casas").addEventListener("click", async () => {
  const pago = estado.usoIA && !estado.usoIA.gratuito;
  if (pago && !confirm("Pesquisar com a API paga da Anthropic (cerca de US$ 0,30 a US$ 1,00)?")) return;
  const b = $("#btn-casas"); b.disabled = true; b.textContent = "Pesquisando nas notícias… (30–90 s)";
  $("#casas-saida").innerHTML = `<div class="ia-bloco">${'<div class="esqueleto"></div>'.repeat(5)}</div>`;
  try { await api("/api/casas/atualizar", { method: "POST" }); await carregarCasas(); carregarUsoIA(); }
  catch (e) { $("#casas-saida").innerHTML = `<div class="vazio"><b>Pesquisa indisponível</b>${esc(e.message)}</div>`; }
  finally { b.disabled = false; b.textContent = "Pesquisar carteiras do mês (grátis)"; }
});

// ---------------------------------------------------------------- gasto com IA
async function carregarUsoIA() {
  try {
    const u = await api("/api/ia/uso");
    estado.usoIA = u;
    const el = $("#ia-gasto");
    if (u.gratuito) {
      el.innerHTML = `<span class="etiqueta compra">Gratuito</span> <span class="nota">${esc(u.descricao)}</span>`;
      el.className = "sub"; el.title = "Sem custo: troque o provedor em config/config.yaml (ia.provedor)";
    } else {
      const pct = u.orcamento_usd ? u.gasto_usd / u.orcamento_usd : 1;
      el.textContent = `· US$ ${num2.format(u.gasto_usd)} / ${num2.format(u.orcamento_usd)} no mês`;
      el.className = `sub ${pct >= 0.8 ? "desce" : ""}`;
      el.title = `${u.chamadas} chamadas · análise: ${u.modelo_analise} · chat: ${u.modelo_chat}`;
    }
  } catch (_) {}
}

// ---------------------------------------------------------------- O QUE FAZER AGORA (modo manual)
const acoesVistas = new Set();
const ICONES = { VENDER: "⛔", SUBIR_STOP: "⬆️", COLOCAR_STOP: "🛡️", ATENCAO: "⚠️" };
async function carregarAcoes() {
  try {
    const r = await api("/api/manual/acoes");
    estado.acoes = r.acoes;
    if (!r.acompanhando) { $("#acoes-manuais").innerHTML = ""; return; }
    const itens = r.acoes.map((a, i) => `
      <div class="acao-item u${a.urgencia}">
        <span class="veredito ${(a.veredito || "").split(" ")[0]}">${esc(a.veredito || a.acao)}</span>
        <div class="txt"><b class="tk">${a.ticker}</b> — você está <b>COMPRADO</b> em ${a.quantidade} ações
          (entrada ${N(a.entrada)} · agora ${N(a.preco)} <span class="${cls(a.resultado_pct)}">${P(a.resultado_pct)}</span>)
          <span class="nota">· preço ${esc(a.fonte)}</span><br>${esc(a.texto)}</div>
        ${a.acao === "SUBIR_STOP" ? `<button class="btn peq primario" data-acao-i="${i}" data-tipo="stop">Já subi o stop na Clear</button>` : ""}
        ${a.acao === "COLOCAR_STOP" ? `<button class="btn peq primario" data-acao-i="${i}" data-tipo="pus">Já coloquei o stop</button>` : ""}
        ${a.acao === "VENDER" ? `<button class="btn peq primario" data-acao-i="${i}" data-tipo="venda">Registrar a venda</button>` : ""}
        <button class="btn peq fantasma" data-acao-i="${i}" data-tipo="grafico">Gráfico</button>
      </div>`).join("");
    $("#acoes-manuais").innerHTML = `<div class="cartao"><div class="cartao-topo"><h2>O que fazer agora na Clear — suas posições</h2>
      <span class="sub">acompanhando ${r.acompanhando} ativo(s) · atualizado ${r.atualizado}</span></div>
      <div class="cartao-corpo sem-pad">${itens || '<div class="vazio"><b>Nada a fazer agora ✓</b>Suas posições estão dentro do plano. O painel avisa quando precisar agir.</div>'}</div></div>`;
    $("#acoes-manuais").onclick = async (ev) => {
      const b = ev.target.closest("[data-acao-i]"); if (!b) return;
      const a = estado.acoes[+b.dataset.acaoI];
      if (b.dataset.tipo === "grafico") return verNoGrafico(a.ticker);
      if (b.dataset.tipo === "venda") {
        abrirBoleta({ ticker: a.ticker, lado: "V", preco: a.preco, motivo: a.texto.slice(0, 60) });
        $("#b-qtd").value = a.quantidade; atualizarResumoBoleta(); return;
      }
      const stop = b.dataset.tipo === "stop" ? a.novo_stop : a.stop;
      try { await api(`/api/protecoes/${a.ticker}/stop`, { method: "POST", body: JSON.stringify({ stop }) });
        toast(`Stop de ${a.ticker} registrado em ${N(stop)}.`, "ok"); carregarAcoes(); } catch (e) { toast(e.message, "erro"); }
    };
    for (const a of r.acoes.filter((x) => x.urgencia <= 2)) {
      const chave = `${a.ticker}:${a.acao}:${a.novo_stop || ""}`;
      if (!acoesVistas.has(chave)) notificar(`${ICONES[a.acao] || ""} ${a.ticker}`, a.texto);
      acoesVistas.add(chave);
    }
  } catch (_) {}
}

// ---------------------------------------------------------------- alertas de reversão (saída)
const alertasVistos = new Set();
function notificar(titulo, corpo) {
  try {
    if (!("Notification" in window)) return;
    if (Notification.permission === "granted") new Notification(titulo, { body: corpo });
    else if (Notification.permission !== "denied") Notification.requestPermission();
  } catch (_) {}
}
async function carregarAlertas() {
  try {
    const r = await api("/api/alertas");
    estado.alertas = r.alertas;
    const relevantes = r.alertas.filter((a) => a.nivel !== "OK");
    $("#faixa-alertas").innerHTML = relevantes.map((a, i) => `
      <div class="alerta-saida ${a.nivel === "SAIR" ? "sair pulso" : "atencao"}">
        <span class="icone-alerta">${a.nivel === "SAIR" ? "⛔" : "⚠️"}</span>
        <div class="txt"><b class="tk">${a.ticker}</b><span class="etiqueta ${a.nivel === "SAIR" ? "venda" : "aviso"}">${a.nivel === "SAIR" ? "REVERSÃO: SAIR" : "ATENÇÃO"} · ${a.pontos} pts</span>
          <span class="num ${cls(a.resultado_pct)}">${P(a.resultado_pct)}</span>
          <div class="sinais">${a.sinais.map(esc).join(" · ")}${a.nivel === "SAIR" ? ` — ${a.na_reversao === "vender" ? "o monitor vai vender automaticamente" : "considere sair do ativo"}` : ""}</div></div>
        <button class="btn peq" data-alerta-grafico="${i}">Ver gráfico</button>
        ${a.nivel === "SAIR" ? `<button class="btn peq primario" data-alerta-sair="${i}">Sair agora</button>` : ""}
      </div>`).join("");
    $("#faixa-alertas").onclick = (ev) => {
      const g = ev.target.dataset.alertaGrafico, sx = ev.target.dataset.alertaSair;
      if (g != null) verNoGrafico(relevantes[+g].ticker);
      if (sx != null) { const a = relevantes[+sx]; abrirBoleta({ ticker: a.ticker, lado: "V", preco: +(a.preco * 0.997).toFixed(2), motivo: "reversão de tendência" }); $("#b-qtd").value = a.quantidade; atualizarResumoBoleta(); }
    };
    for (const a of relevantes) {
      const chave = `${a.ticker}:${a.nivel}`;
      if (a.nivel === "SAIR" && !alertasVistos.has(chave)) notificar(`⛔ ${a.ticker}: reversão de tendência`, a.sinais.join(" · "));
      alertasVistos.add(chave);
    }
  } catch (_) {}
}

// ---------------------------------------------------------------- inicialização
async function iniciar() {
  try {
    const [resumo, ranking, scanner, ativos, consenso] = await Promise.all([api("/api/resumo"), api("/api/ranking"), api("/api/scanner"), api("/api/ativos"), api("/api/consenso")]);
    Object.assign(estado, { resumo, ranking, scanner, consenso });
    $("#sel-ativo").innerHTML = ativos.map((t) => `<option ${t === estado.ativo ? "selected" : ""}>${t}</option>`).join("");
    renderResumo(); renderScanner(); renderRanking(); renderConsenso(); carregarGrafico();
  } catch (e) {
    $("#kpis").innerHTML = `<div class="cartao" style="grid-column:1/-1"><div class="vazio"><b>Não foi possível carregar os dados</b>${esc(e.message)}</div></div>`;
  }
}
criarGraficos();
iniciar().then(() => { const aba = location.hash.slice(1); if (aba && $(`#${aba}`)) abrirAba(aba); carregarAlertas(); carregarCasas(); carregarUsoIA(); carregarAcoes(); });
setInterval(carregarAlertas, 60000);   // reavalia as posições a cada minuto
setInterval(carregarAcoes, 60000);
