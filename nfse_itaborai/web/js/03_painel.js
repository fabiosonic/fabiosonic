// Navegação, componentes de dados (gráfico, indicadores, tendências) e painel.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- navegação
const PAGINAS = {};
let PAG = "painel";
async function ir(p) {
  PAG = p;
  $$("nav a").forEach(a => a.classList.toggle("on", a.dataset.p == p));
  $("#conteudo").innerHTML = '<div class="vazio">Carregando…</div>';
  try { await PAGINAS[p]($("#conteudo")); } catch (e) { console.error(e); }
  if (location.hash != "#" + p) history.pushState(null, "", "#" + p);
}
window.addEventListener("popstate", () => { const h = location.hash.slice(1); if (h in PAGINAS && h != PAG) ir(h); });
$$("nav a").forEach(a => a.onclick = () => ir(a.dataset.p));

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

// ---------------------------------------------------------------- tendência, variação e indicadores
// Minigráfico de 12 pontos: linha no tom de apoio, último ponto em destaque (o mês atual).
function spark(vals, rot = "") {
  vals = (vals || []).map(v => Number(v || 0));
  if (vals.length < 2 || !vals.some(Boolean)) return "";
  const W = 112, H = 32, p = 4, mx = Math.max(...vals), mn = Math.min(0, ...vals), f = mx - mn || 1;
  const pts = vals.map((v, i) => [p + i * (W - 2 * p) / (vals.length - 1), H - p - (v - mn) / f * (H - 2 * p)]);
  const l = pts.map(q => q.map(n => n.toFixed(1)).join(",")).join(" "), [ux, uy] = pts.at(-1);
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(rot)}"><polygon points="${p},${H - p} ${l} ${ux},${H - p}" class="spark-area"/>
    <polyline points="${l}" class="spark-linha"/><circle cx="${ux}" cy="${uy}" r="3.5" class="spark-ponto"/></svg>`;
}
// Variação contra um período nomeado. sobeBom: se subir é bom (receita) ou ruim (atraso). Seta + texto, nunca só cor.
function variacao(atual, anterior, sobeBom = true, ref = "mês anterior", curto = "") {
  if (!anterior) return "";
  const d = (atual - anterior) / Math.abs(anterior) * 100;
  if (!isFinite(d)) return "";
  const r = Math.round(d * 10) / 10, cls = Math.abs(r) < 0.5 ? "neutro" : (r > 0) == sobeBom ? "bom" : "ruim";
  return `<span class="delta ${cls}" title="Variação contra o ${ref}"><span aria-hidden="true">${Math.abs(r) < 0.5 ? "■" : r > 0 ? "▲" : "▼"}</span>${pct(Math.abs(r))}<span class="delta-ref">vs ${curto || ref}</span></span>`;
}
// Estado com ícone + rótulo (cor nunca sozinha): bom · atencao · critico
const estadoSelo = (cls, txt) => `<span class="estado ${cls}">${ic(cls == "bom" ? "ok" : cls == "critico" ? "bloqueio" : "alerta")}${txt}</span>`;
// Cartão de indicador: rótulo · valor · variação · tendência (12 meses) · complemento
function statTile({ rot, icone = "", valor, delta = "", tendencia = null, sub = "", estado = "", rotTend = "" }) {
  return `<div class="stat"><div class="stat-rot">${icone ? ic(icone) : ""}<span>${rot}</span></div>
    <div class="stat-v">${valor}</div>
    ${delta || tendencia ? `<div class="stat-corpo"><div class="stat-d">${delta}</div>${tendencia ? spark(tendencia, rotTend || `Tendência de ${rot}`) : ""}</div>` : ""}
    ${sub || estado ? `<div class="stat-s">${estado}${sub ? `<span>${sub}</span>` : ""}</div>` : ""}</div>`;
}
// Medidor: preenchimento sobre um trilho do mesmo tom
const medidor = (v, cls = "", rot = "") => `<div class="medidor ${cls}" role="meter" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(v)}" aria-label="${esc(rot)}"><span style="width:${Math.max(0, Math.min(100, v))}%"></span></div>`;

// Barra empilhada horizontal (parte do todo): segmentos com 2px de respiro, legenda com valores, dica por segmento.
function empilhada(segs, total = null) {
  total = total ?? segs.reduce((s, x) => s + x.v, 0);
  if (!total) return '<div class="vazio">Nada em aberto.</div>';
  return `<div class="empilhada" role="img" aria-label="${esc(segs.map(s => `${s.rot}: ${brl(s.v)}`).join("; "))}">${segs.filter(s => s.v > 0).map(s =>
    `<span class="seg" style="flex:${s.v};background:var(${s.cor})" tabindex="0" data-dica="${esc(`${brl(s.v)} · ${s.rot} · ${pct(s.v / total * 100)}`)}"></span>`).join("")}</div>
    <ul class="emp-leg">${segs.map(s => `<li><i style="background:var(${s.cor})"></i><span>${s.rot}</span><b>${brl(s.v)}</b><small>${pct(s.v / total * 100)}</small></li>`).join("")}</ul>`;
}
// Ranking em barras horizontais (uma série = uma cor)
function ranking(itens, vazio = "Sem dados.") {
  if (!itens.length) return `<div class="vazio">${vazio}</div>`;
  const max = Math.max(...itens.map(x => x.v)) || 1;
  return `<ol class="ranking">${itens.map((x, i) => `<li><span class="rk-n">${i + 1}</span><div class="rk-c"><div class="rk-t"><span class="rk-rot" title="${esc(x.rot)}">${esc(nomeCli(x.rot))}</span><b>${brl(x.v)}${x.extra ? `<small>${x.extra}</small>` : ""}</b></div>
    <div class="rk-trilho"><span style="width:${Math.max(1.5, x.v / max * 100)}%"></span></div></div></li>`).join("")}</ol>`;
}
// Dica flutuante única para elementos com data-dica (segmentos, barras de ranking)
document.addEventListener("pointerover", ev => { const el = ev.target.closest && ev.target.closest("[data-dica]"); if (el) mostrarDica(el); });
document.addEventListener("focusin", ev => { const el = ev.target.closest && ev.target.closest("[data-dica]"); if (el) mostrarDica(el); });
document.addEventListener("pointerout", ev => { if (ev.target.closest && ev.target.closest("[data-dica]")) esconderDica(); });
document.addEventListener("focusout", esconderDica);
function mostrarDica(el) {
  let d = $("#dica-global"); if (!d) { d = document.createElement("div"); d.id = "dica-global"; d.className = "dica flutuante"; document.body.append(d); }
  d.textContent = el.dataset.dica; d.hidden = false;
  const r = el.getBoundingClientRect(); d.style.left = (r.left + r.width / 2 + scrollX) + "px"; d.style.top = (r.top + scrollY - 8) + "px";
}
function esconderDica() { const d = $("#dica-global"); if (d) d.hidden = true; }

// ---------------------------------------------------------------- gráfico de colunas (um eixo, em R$)
// Colunas agrupadas + linha opcional, meses projetados esmaecidos, faixa de foco no mês, dica com todas as séries
// (teclado e mouse) e tabela equivalente. specs: [{ k, rot, cor, linha? }] · opts: { rotulo(p), nome(p), projetado(p), aria }
function svgGrafico(serie, specs, W, opts) {
  const H = 264, ml = 52, mr = 12, mb = 30, mt = 14, larg = W - ml - mr, alt = H - mt - mb;
  const vals = serie.flatMap(p => specs.map(e => p[e.k] || 0));
  const max = Math.max(1, ...vals), min = Math.min(0, ...vals);
  // escala "redonda": passo 1 · 2 · 2,5 · 5 × 10^k, de 3 a 5 divisões
  const nice = v => { const e = Math.pow(10, Math.floor(Math.log10(v))); return [1, 2, 2.5, 5, 10].map(k => k * e).find(x => x >= v); };
  const step = nice(Math.max(1, max - min) / 5), topo = Math.ceil(max / step) * step || step, fundo = min < 0 ? -Math.ceil(-min / step) * step : 0, faixa = topo - fundo;
  const ndiv = Math.round(faixa / step);
  const y = v => mt + (topo - v) / faixa * alt, gw = larg / serie.length;
  const barras = specs.filter(e => !e.linha), bw = Math.max(4, Math.min(24, (gw * .62 - (barras.length - 1) * 2) / barras.length));
  let s = "";
  for (let i = 0; i <= ndiv; i++) { const v = fundo + step * i; s += `<line class="grade" x1="${ml}" x2="${W - mr}" y1="${y(v)}" y2="${y(v)}"/><text class="eixo" x="${ml - 10}" y="${y(v) + 4}" text-anchor="end">${compacto(v, false)}</text>`; }
  serie.forEach((p, i) => { if (opts.projetado && opts.projetado(p)) s += `<rect class="proj" x="${ml + gw * i}" y="${mt}" width="${gw}" height="${alt}"/>`; });
  const pi = serie.findIndex(p => opts.projetado && opts.projetado(p));
  if (pi > 0) s += `<text class="eixo proj-rot" x="${ml + gw * pi + 6}" y="${mt + 12}">projetado</text>`;
  s += `<rect class="banda" x="0" y="${mt}" width="${gw}" height="${alt}" visibility="hidden"/>`;
  const barra = (x, v, cor, esm) => { const yy = Math.min(y(v), y(0)), h = Math.abs(y(v) - y(0)), r = Math.min(4, h); if (h < .5) return "";
    const d = v >= 0 ? `M${x},${yy + h} V${yy + r} Q${x},${yy} ${x + r},${yy} H${x + bw - r} Q${x + bw},${yy} ${x + bw},${yy + r} V${yy + h} Z`
                     : `M${x},${yy} V${yy + h - r} Q${x},${yy + h} ${x + r},${yy + h} H${x + bw - r} Q${x + bw},${yy + h} ${x + bw},${yy + h - r} V${yy} Z`;
    return `<path d="${d}" fill="var(${cor})"${esm ? ' class="esmaecida"' : ""}/>`; };
  const cada = Math.ceil(46 / gw);                              // rótulos do eixo X sem colisão
  serie.forEach((p, i) => {
    const x0 = ml + gw * i + (gw - (bw * barras.length + (barras.length - 1) * 2)) / 2, proj = opts.projetado && opts.projetado(p);
    s += `<g class="col" data-i="${i}">` + barras.map((e, j) => barra(x0 + j * (bw + 2), p[e.k] || 0, e.cor, proj)).join("") + "</g>";
    if ((serie.length - 1 - i) % cada == 0) s += `<text class="eixo x${i == (pi > 0 ? pi - 1 : serie.length - 1) ? " atual" : ""}" x="${ml + gw * i + gw / 2}" y="${H - 9}" text-anchor="middle">${esc(opts.rotulo(p))}</text>`;
  });
  s += `<line class="base" x1="${ml}" x2="${W - mr}" y1="${y(0)}" y2="${y(0)}"/>`;
  specs.filter(e => e.linha).forEach(e => {
    const pts = serie.map((p, i) => [ml + gw * i + gw / 2, y(p[e.k] || 0)]);
    s += `<polyline points="${pts.map(q => q.join(",")).join(" ")}" fill="none" stroke="var(${e.cor})" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    pts.forEach(([cx, cy]) => { s += `<circle cx="${cx}" cy="${cy}" r="4" fill="var(${e.cor})" stroke="var(--superficie)" stroke-width="2"/>`; });
  });
  serie.forEach((p, i) => { s += `<rect x="${ml + gw * i}" y="${mt}" width="${gw}" height="${alt + mb - 6}" fill="transparent" data-i="${i}" class="alvo" tabindex="0" role="button" aria-label="${esc(opts.nome(p) + ": " + specs.map(e => `${e.rot} ${brl(p[e.k])}`).join(", "))}"/>`; });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.aria || "")}">${s}</svg><div class="dica" hidden></div>`;
}
function montarGrafico(alvo, serie, specs, opts = {}) {
  opts = { rotulo: p => mesCurto(p.mes), nome: p => mesExtenso(p.mes), ...opts };
  alvo.innerHTML = `<div class="legenda">${specs.map(e => `<span><i class="${e.linha ? "linha" : ""}" style="background:var(${e.cor})"></i>${e.rot}</span>`).join("")}${opts.legendaExtra || ""}<span class="leg-unid">valores em R$</span></div>
    <div class="grafico"></div><details class="ver-tabela"><summary>Ver tabela</summary>${tabela([{ t: "Período", f: p => esc(opts.nome(p)) }, ...specs.map(e => ({ t: e.rot, n: 1, f: p => num(p[e.k]) }))], serie)}</details>`;
  const g = $(".grafico", alvo);
  if (!serie.some(p => specs.some(e => p[e.k]))) { g.innerHTML = '<div class="vazio">Sem movimento no período ainda.</div>'; return; }
  const desenhar = () => { const w = Math.round(g.clientWidth); if (!w || w == g._w) return; g._w = w;
    g.innerHTML = svgGrafico(serie, specs, w, opts); const d = $(".dica", g), banda = $(".banda", g);
    const mostrar = (r, px, py) => {
      const i = +r.dataset.i, p = serie[i], b = g.getBoundingClientRect(), proj = opts.projetado && opts.projetado(p);
      banda.setAttribute("x", r.getAttribute("x")); banda.setAttribute("visibility", "visible");
      $$(".col", g).forEach(c => c.classList.toggle("fora", c.dataset.i != i));
      d.innerHTML = `<div class="dica-tit">${esc(opts.nome(p)).replace(/^./, c => c.toUpperCase())}${proj ? " · projetado" : ""}</div>` +
        specs.map(e => `<div class="dica-l"><i class="${e.linha ? "linha" : ""}" style="background:var(${e.cor})"></i><b>${brl(p[e.k])}</b><span>${e.rot}</span></div>`).join("");
      d.hidden = false;
      // ao lado da coluna em foco (nunca por cima das barras); vira para a esquerda perto da borda
      const esc_ = b.width / w, x0 = +r.getAttribute("x") * esc_, x1 = (+r.getAttribute("x") + +r.getAttribute("width")) * esc_, dw = d.offsetWidth;
      const esquerda = x1 + 10 + dw > b.width;
      d.style.left = (esquerda ? Math.max(0, x0 - 10 - dw) : x1 + 10) + "px";
      d.style.top = Math.max(0, Math.min((py ?? 60) - d.offsetHeight / 2, b.height - d.offsetHeight - 40)) + "px"; };
    const ocultar = () => { d.hidden = true; banda.setAttribute("visibility", "hidden"); $$(".col", g).forEach(c => c.classList.remove("fora")); };
    $$(".alvo", g).forEach(r => {
      r.onpointermove = ev => { const b = g.getBoundingClientRect(); mostrar(r, ev.clientX - b.left, ev.clientY - b.top); };
      r.onfocus = () => mostrar(r); r.onpointerleave = ocultar; r.onblur = ocultar; }); };
  desenhar();
  if (window.ResizeObserver) new ResizeObserver(desenhar).observe(g);
}

// ---------------------------------------------------------------- painel
PAGINAS.painel = async el => {
  const [p, sd] = await Promise.all([api("painel"), api("saude")]);
  const al = [], A = (sev, icone, html) => al.push({ sev, icone, html });
  if (p.contratos_a_confirmar) A("info", "contratos", `<b>${p.contratos_a_confirmar}</b> cliente(s) na recorrência a confirmar — <a href="#" onclick="ir('contratos');return false">conferir e marcar “Repetir todo mês”</a>`);
  if (p.sem_nfse) A("alerta", "nota", `<b>${p.sem_nfse}</b> título(s) sem NFS-e válida — <a href="#" onclick="ir('receber');return false">ver</a>`);
  if (p.atrasado_qtd) A("serio", "relogio", `<b>${p.atrasado_qtd}</b> título(s) em atraso de <b>${p.clientes_atrasados}</b> cliente(s): <b>${brl(p.atrasado)}</b> — <a href="#" onclick="ir('cobranca');return false">cobrança</a>`);
  if (p.criticos.length) A("critico", "bloqueio", `<b>${p.criticos.length}</b> cliente(s) com atraso crítico (≥ ${ST.config.cobranca.bloquear_apos_dias} dias): ${p.criticos.slice(0, 3).map(n => esc(nomeCli(n))).join(", ")}${p.criticos.length > 3 ? ` e mais ${p.criticos.length - 3} — <a href="#" onclick="ABA_REL='aging';ir('relatorios');return false">ver todos</a>` : ""}`);
  if (p.a_pagar_atrasado) A("serio", "pagar", `Contas a pagar vencidas: <b>${brl(p.a_pagar_atrasado)}</b> — <a href="#" onclick="ir('pagar');return false">pagar</a>`);
  if (p.sublimite_pct >= 80 && (ST.fiscal_ctx || {}).regime == "simples") A("critico", "alerta", `RBT12 em ${pct(p.sublimite_pct)} do sublimite de R$ 3,6 mi do Simples`);
  if (!ST.config.automacao.ativa) A("alerta", "play", `O robô financeiro está desligado — <a href="#" onclick="ir('config');return false">ligar em Configurações</a>`);
  const S = p.serie, atu = S.at(-1) || {}, ant = S.at(-2) || {}, col = k => S.map(x => x[k]);
  const cobrado = Math.round((p.recebido_mes / (p.faturado_mes || 1)) * 1000) / 10;
  const caixa = (atu.recebido || 0) - (atu.despesas || 0);
  const robo = ST.config.automacao.ativa
    ? `<span class="estado bom">${ic("ok")}Robô ligado</span><span>${p.ultima_execucao_robo ? "última execução " + dt(p.ultima_execucao_robo.slice(0, 10)) + " às " + p.ultima_execucao_robo.slice(11, 16) : "ainda não executou"}</span>`
    : `<span class="estado critico">${ic("bloqueio")}Robô desligado</span>`;
  const inad = p.inadimplencia_pct, inadCls = inad > 5 ? "critico" : inad > 2 ? "atencao" : "bom";
  const ag = p.aging, agTotal = Object.values(ag).reduce((a, b) => a + b, 0);
  el.innerHTML = `<header class="pg-cab"><div><h1>Painel</h1><p class="pg-sub">${mesExtenso(p.competencia).replace(/^./, c => c.toUpperCase())} · posição de ${dt(p.hoje)} <span class="pg-robo">${robo}</span></p></div>
    <div class="acoes"><button class="btn sec" id="robo">${ic("play")}Rodar robô agora</button></div></header>
  <div id="migra"></div>
  ${sd.completo ? "" : `<details class="card checklist" ${sd.erros ? "open" : ""}><summary><span class="ck-tit">${ic(sd.erros ? "alerta" : "ok")}<b>Implantação e saúde do sistema</b><span class="sub">${sd.ok} de ${sd.total} itens em ordem${sd.erros ? ` · ${sd.erros} impedem a automação completa` : ""}</span></span><span class="ck-barra"><span style="width:${sd.ok / sd.total * 100}%"></span></span></summary>
    <ul>${sd.itens.filter(i => !i.ok).sort((a, b) => (a.nivel == "erro" ? 0 : 1) - (b.nivel == "erro" ? 0 : 1)).map(i => `<li class="ck-${i.ok ? "ok" : i.nivel}">${ic(i.ok ? "ok" : i.nivel == "erro" ? "bloqueio" : "alerta")}<div><b>${esc(i.titulo)}</b>${i.ok ? "" : `<div class="sub">${esc(i.detalhe)} <a href="#" onclick="ir('${i.pagina}');return false">resolver</a></div>`}</div></li>`).join("")}</ul>
    <p class="ck-feitos">${ic("ok")}Em ordem: ${sd.itens.filter(i => i.ok).map(i => esc(i.titulo)).join(" · ") || "nenhum item ainda"}</p></details>`}
  <section class="painel-topo">
    <div class="card heroi">
      <div class="heroi-rot">Recebido em ${mesExtenso(p.competencia)}</div>
      <div class="heroi-v">${brl(p.recebido_mes)}</div>
      <div class="heroi-meta"><span>${pct(Math.min(cobrado, 999))} do faturado no mês (${brl(p.faturado_mes)})</span><span class="sub">mês anterior: ${brl(ant.recebido)}</span></div>
      ${medidor(cobrado, "", "Recebido sobre o faturado do mês")}
      <dl class="heroi-fatos">
        <div><dt>A receber no mês</dt><dd>${brl(Math.max(0, p.faturado_mes - p.recebido_mes))}</dd></div>
        <div><dt>Despesas pagas no mês</dt><dd>${brl(atu.despesas)}</dd></div>
        <div><dt>Resultado de caixa no mês</dt><dd class="${caixa < 0 ? "neg" : ""}">${brl(caixa)}</dd></div>
      </dl>
    </div>
    <div class="card"><div class="card-cab"><h2>${ic("relogio")}Contas a receber por idade</h2><span class="sub">${brl(agTotal)} em aberto</span></div>
      ${empilhada([{ rot: "A vencer", v: ag.a_vencer, cor: "--idade-0" }, { rot: "1 a 30 dias", v: ag["1_30"], cor: "--idade-1" }, { rot: "31 a 60 dias", v: ag["31_60"], cor: "--idade-2" },
        { rot: "61 a 90 dias", v: ag["61_90"], cor: "--idade-3" }, { rot: "Mais de 90 dias", v: ag["90_mais"], cor: "--idade-4" }], agTotal)}
      <p class="card-pe"><a href="#" onclick="ABA_REL='aging';ir('relatorios');return false">Ver inadimplência por cliente</a></p></div>
  </section>
  <section class="stats">
    ${statTile({ rot: "Faturado no mês", icone: "nota", valor: brl(p.faturado_mes), delta: variacao(p.faturado_mes, ant.faturado, true, "mês anterior", mesCurto(ant.mes)), tendencia: col("faturado"), sub: "por competência · 12 meses no gráfico" })}
    ${statTile({ rot: "A receber", icone: "receber", valor: brl(p.a_receber), tendencia: col("a_receber"), rotTend: "Saldo a receber no fim de cada mês", sub: `${brl(p.recebido_mes)} já recebidos no mês` })}
    ${statTile({ rot: "Em atraso", icone: "alerta", valor: brl(p.atrasado), delta: variacao(atu.atrasado, ant.atrasado, false, "fim do mês anterior", mesCurto(ant.mes)), tendencia: col("atrasado"), rotTend: "Valor em atraso no fim de cada mês",
      estado: estadoSelo(inadCls, `${pct(inad)} inadimplência`), sub: `${p.atrasado_qtd} título(s) de ${p.clientes_atrasados} cliente(s)` })}
    ${statTile({ rot: "Recorrência (MRR)", icone: "contratos", valor: brl(p.mrr), sub: `${p.contratos_ativos} cliente(s) na recorrência · ticket médio ${brl(p.ticket_medio)}` })}
    ${statTile({ rot: "A pagar", icone: "pagar", valor: brl(p.a_pagar), estado: p.a_pagar_atrasado ? estadoSelo("critico", `${compacto(p.a_pagar_atrasado)} vencido`) : "", sub: p.a_pagar_atrasado ? "há contas vencidas" : "nada vencido", tendencia: col("despesas"), rotTend: "Despesas pagas por mês" })}
  </section>
  <div class="grid-painel">
    <div class="card span2"><div class="card-cab"><h2>${ic("relatorios")}Faturado x recebido</h2><span class="sub">últimos 12 meses</span></div><div id="g_painel"></div>
      <dl class="resumo-g">${(() => { const n = S.filter(x => x.faturado || x.recebido).length || 1, f = col("faturado").reduce((a, b) => a + b, 0), r = col("recebido").reduce((a, b) => a + b, 0);
        return `<div><dt>Média faturada</dt><dd>${brl(f / n)}</dd></div><div><dt>Média recebida</dt><dd>${brl(r / n)}</dd></div><div><dt>Recebido sobre faturado (12 meses)</dt><dd>${pct(f ? r / f * 100 : 0)}</dd></div>`; })()}</dl></div>
    <div class="coluna"><div class="card"><div class="card-cab"><h2>${ic("alerta")}Alertas</h2>${al.length ? `<span class="contador">${al.length}</span>` : ""}</div>${al.length ? `<ul class="alertas">${al.map(a => `<li class="${a.sev}"><span class="ai">${ic(a.icone)}</span><div class="txt">${a.html}</div></li>`).join("")}</ul>` : `<div class="tudo-ok">${ic("ok")}Tudo em dia</div>`}</div>
    <div class="card"><div class="card-cab"><h2>${ic("bloqueio")}Maiores devedores</h2><span class="sub">valor atualizado</span></div>${ranking(p.maiores_devedores.map(x => ({ rot: x.cliente, v: x.valor })), "Ninguém em atraso.")}</div></div>
    <div class="card span3"><div class="card-cab"><h2>${ic("relogio")}Vencem nos próximos 7 dias</h2><span class="sub">${p.proximos_7_dias.length} título(s) · ${brl(p.proximos_7_dias.reduce((s, t) => s + t.valor_cent, 0))}</span></div>
      ${p.proximos_7_dias.length ? `<ul class="vencimentos">${p.proximos_7_dias.map(t => `<li><span class="vc-data"><b>${t.vencimento.slice(8, 10)}</b>${MESES[+t.vencimento.slice(5, 7) - 1].slice(0, 3)}</span><span class="vc-nome" title="${esc(t.cliente_nome)}">${esc(nomeCli(t.cliente_nome))}</span>${selo(t.nfse_status)}<b class="vc-v">${brl(t.valor_cent)}</b></li>`).join("")}</ul>` : '<div class="vazio">Nenhum vencimento na semana.</div>'}</div>
  </div>`;
  if (!sd.completo) mostrarMigracao($("#migra"));
  montarGrafico($("#g_painel"), S, [{ k: "faturado", rot: "Faturado (competência)", cor: "--serie-1" }, { k: "recebido", rot: "Recebido", cor: "--serie-2" }], { aria: "Faturado e recebido nos últimos 12 meses" });
  $("#robo").onclick = async ev => {
    if (!confirm(`Rodar o robô agora?\n\nEle gera os títulos dos contratos, ${ST.producao ? "EMITE AS NFS-e VÁLIDAS pendentes" : "não emite NFS-e (homologação)"}, cria PIX/boleto, envia a régua de cobrança e confere pagamentos.`)) return;
    const bt = ev.currentTarget; bt.disabled = true; modal('<h2>Robô em execução…</h2><p class="sub">Pode levar alguns minutos se houver muitas notas para emitir. Não feche esta janela.</p>');
    let r; try { r = await api("robo/rodar"); } finally { bt.disabled = false; }
    modal(`<h2>Resultado do robô</h2>${resumoRobo(r)}<button class="btn" onclick="fechar();ir('painel')">OK</button>`); };
};

function resumoRobo(r) {
  if (!r.executado) return `<p>${esc(r.motivo || "Nada executado.")}</p>`;
  const nomes = { importacao_xml: "XML das notas (clientes, notas externas, contratos)",
    despesas_recorrentes: "Despesas recorrentes lançadas", titulos_gerados: "Títulos gerados (contratos)", decimo_terceiro: "Parcelas do 13º honorário geradas", nfse: "NFS-e",
    cobrancas_criadas: "Cobranças (PIX/boleto) criadas", baixas_banco: "Boletos pagos baixados (Inter)", boletos_pdf: "PDFs de boletos salvos", extratos: "Extratos importados", extrato_inter: "Extrato do Inter (API)",
    regua: "Régua de cobrança", whatsapp_web: "WhatsApp enviado automaticamente", resumo: "Resumo diário por e-mail", backup: "Backup" };
  const fmt = v => typeof v == "object" ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(" · ") : String(v);
  return `<table>${Object.entries(nomes).filter(([k]) => k in r).map(([k, t]) => `<tr><td>${t}</td><td>${esc(fmt(r[k]))}</td></tr>`).join("")}</table><p></p>`;
}
