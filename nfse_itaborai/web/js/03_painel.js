// Navegação e painel.
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

// ---------------------------------------------------------------- painel
// Gráfico de barras agrupadas (um eixo, em R$), com linha opcional, meses projetados esmaecidos, dica e tabela.
// specs: [{ k, rot, cor, linha? }] · opts: { rotulo(p), projetado(p), aria }
function svgGrafico(serie, specs, W, opts) {
  const H = 260, ml = 58, mb = 28, mt = 12, larg = W - ml - 10, alt = H - mt - mb;
  const vals = serie.flatMap(p => specs.map(e => p[e.k] || 0));
  const max = Math.max(1, ...vals), min = Math.min(0, ...vals);
  const passo = v => { const p = Math.pow(10, Math.floor(Math.log10(Math.max(1, v) / 100))) * 100; return Math.ceil(v / p / 4) * p * 4 || 1; };
  const topo = passo(max), fundo = min < 0 ? -passo(-min) : 0, faixa = topo - fundo;
  const y = v => mt + (topo - v) / faixa * alt, gw = larg / serie.length;
  const barras = specs.filter(e => !e.linha), bw = Math.max(4, Math.min(18, (gw - 10 - (barras.length - 1) * 2) / barras.length));
  const fmt = v => v ? (Math.abs(v) >= 100000 ? (v / 100 / 1000).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " mil" : (v / 100).toLocaleString("pt-BR", { maximumFractionDigits: 0 })) : "0";
  let s = "";
  for (let i = 0; i <= 4; i++) { const v = fundo + faixa / 4 * i; s += `<line class="grade" x1="${ml}" x2="${W - 10}" y1="${y(v)}" y2="${y(v)}"/><text class="eixo" x="${ml - 8}" y="${y(v) + 4}" text-anchor="end">${fmt(v)}</text>`; }
  serie.forEach((p, i) => { if (opts.projetado && opts.projetado(p)) s += `<rect class="proj" x="${ml + gw * i}" y="${mt}" width="${gw}" height="${alt}"/>`; });
  s += `<line class="base" x1="${ml}" x2="${W - 10}" y1="${y(0)}" y2="${y(0)}"/>`;
  const barra = (x, v, cor, esmaecida) => { const yy = Math.min(y(v), y(0)), h = Math.abs(y(v) - y(0)), r = Math.min(4, h); if (!h) return "";
    const d = v >= 0 ? `M${x},${yy + h} V${yy + r} Q${x},${yy} ${x + r},${yy} H${x + bw - r} Q${x + bw},${yy} ${x + bw},${yy + r} V${yy + h} Z`
                     : `M${x},${yy} V${yy + h - r} Q${x},${yy + h} ${x + r},${yy + h} H${x + bw - r} Q${x + bw},${yy + h} ${x + bw},${yy + h - r} V${yy} Z`;
    return `<path d="${d}" fill="var(${cor})"${esmaecida ? ' class="esmaecida"' : ""}/>`; };
  serie.forEach((p, i) => {
    const x0 = ml + gw * i + (gw - (bw * barras.length + (barras.length - 1) * 2)) / 2, proj = opts.projetado && opts.projetado(p);
    barras.forEach((e, j) => { s += barra(x0 + j * (bw + 2), p[e.k] || 0, e.cor, proj); });
    if (gw >= 38 || i % 2 == (serie.length - 1) % 2) s += `<text class="eixo" x="${ml + gw * i + gw / 2}" y="${H - 9}" text-anchor="middle">${esc(opts.rotulo(p))}</text>`;
  });
  specs.filter(e => e.linha).forEach(e => {
    const pts = serie.map((p, i) => `${ml + gw * i + gw / 2},${y(p[e.k] || 0)}`);
    s += `<polyline points="${pts.join(" ")}" fill="none" stroke="var(${e.cor})" stroke-width="2" stroke-linejoin="round"/>`;
    serie.forEach((p, i) => { s += `<circle cx="${ml + gw * i + gw / 2}" cy="${y(p[e.k] || 0)}" r="4" fill="var(${e.cor})" stroke="var(--superficie)" stroke-width="2"/>`; });
  });
  serie.forEach((p, i) => { s += `<rect x="${ml + gw * i}" y="${mt}" width="${gw}" height="${alt}" fill="transparent" data-i="${i}" class="alvo"/>`; });
  return `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.aria || "")}">${s}</svg><div class="dica" hidden></div>`;
}
function montarGrafico(alvo, serie, specs, opts = {}) {
  opts = { rotulo: p => `${p.mes.slice(5)}/${p.mes.slice(2, 4)}`, nome: p => mes(p.mes), ...opts };
  alvo.innerHTML = `<div class="legenda">${specs.map(e => `<span><i class="${e.linha ? "linha" : ""}" style="background:var(${e.cor})"></i>${e.rot}</span>`).join("")}${opts.legendaExtra || ""}</div>
    <div class="grafico"></div><details><summary>Ver tabela</summary>${tabela([{ t: "Período", f: p => esc(opts.nome(p)) }, ...specs.map(e => ({ t: e.rot, n: 1, f: p => num(p[e.k]) }))], serie)}</details>`;
  const g = $(".grafico", alvo);
  if (!serie.some(p => specs.some(e => p[e.k]))) { g.innerHTML = '<div class="vazio">Sem movimento no período ainda.</div>'; return; }
  const desenhar = () => { const w = Math.round(g.clientWidth); if (!w || w == g._w) return; g._w = w;
    g.innerHTML = svgGrafico(serie, specs, w, opts); const d = $(".dica", g);
    $$(".alvo", g).forEach(r => {
      r.onmousemove = ev => { const p = serie[r.dataset.i], b = g.getBoundingClientRect();
        d.innerHTML = `<b>${esc(opts.nome(p))}${opts.projetado && opts.projetado(p) ? " · projetado" : ""}</b>` + specs.map(e => `<br><i style="background:var(${e.cor})"></i>${e.rot} ${brl(p[e.k])}`).join("");
        d.hidden = false; d.style.left = (ev.clientX - b.left) + "px"; d.style.top = (ev.clientY - b.top) + "px"; };
      r.onmouseleave = () => d.hidden = true; }); };
  desenhar();
  if (window.ResizeObserver) new ResizeObserver(desenhar).observe(g);
}
PAGINAS.painel = async el => {
  const [p, sd] = await Promise.all([api("painel"), api("saude")]);
  const al = [], A = (sev, icone, html) => al.push({ sev, icone, html });
  if (p.contratos_a_confirmar) A("info", "contratos", `<b>${p.contratos_a_confirmar}</b> cliente(s) na recorrência a confirmar — <a href="#" onclick="ir('contratos');return false">conferir e marcar “Repetir todo mês”</a>`);
  if (p.sem_nfse) A("alerta", "nota", `<b>${p.sem_nfse}</b> título(s) sem NFS-e válida — <a href="#" onclick="ir('receber');return false">ver</a>`);
  if (p.atrasado_qtd) A("serio", "relogio", `<b>${p.atrasado_qtd}</b> título(s) em atraso de <b>${p.clientes_atrasados}</b> cliente(s): <b>${brl(p.atrasado)}</b>`);
  if (p.criticos.length) A("critico", "bloqueio", `<b>${p.criticos.length}</b> cliente(s) com atraso crítico (≥ ${ST.config.cobranca.bloquear_apos_dias} dias): ${p.criticos.slice(0, 3).map(esc).join(", ")}${p.criticos.length > 3 ? ` e mais ${p.criticos.length - 3} — <a href="#" onclick="ABA_REL='aging';ir('relatorios');return false">ver todos</a>` : ""}`);
  if (p.a_pagar_atrasado) A("serio", "pagar", `Contas a pagar vencidas: <b>${brl(p.a_pagar_atrasado)}</b>`);
  if (p.sublimite_pct >= 80 && (ST.fiscal_ctx || {}).regime == "simples") A("critico", "alerta", `RBT12 em ${p.sublimite_pct}% do sublimite de R$ 3,6 mi do Simples`);
  if (!ST.config.automacao.ativa) A("alerta", "play", `O robô financeiro está desligado — <a href="#" onclick="ir('config');return false">ligar em Configurações</a>`);
  const robo = ST.config.automacao.ativa ? `<span class="selo bom">Robô ligado</span><span>${p.ultima_execucao_robo ? "última execução " + dt(p.ultima_execucao_robo.slice(0, 10)) + " às " + p.ultima_execucao_robo.slice(11, 16) : "ainda não executou"}</span>` : `<span class="selo critico">Robô desligado</span>`;
  const kpi = (cls, icone, rot, val, sub = "") => `<div class="kpi ${cls}"><div class="r">${ic(icone)}${rot}</div><div class="v">${val}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div>`;
  el.innerHTML = `<h1>Painel <span class="titulo-sub">${robo}</span><span class="acoes"><button class="btn sec" id="robo">${ic("play")}Rodar robô agora</button></span></h1>
  <div id="migra"></div>
  ${sd.completo ? "" : `<details class="card checklist" ${sd.erros ? "open" : ""}><summary><span class="ck-tit">${ic(sd.erros ? "alerta" : "ok")}<b>Implantação e saúde do sistema</b><span class="sub">${sd.ok} de ${sd.total} itens em ordem${sd.erros ? ` · ${sd.erros} impedem a automação completa` : ""}</span></span><span class="ck-barra"><span style="width:${sd.ok / sd.total * 100}%"></span></span></summary>
    <ul>${sd.itens.filter(i => !i.ok).sort((a, b) => (a.nivel == "erro" ? 0 : 1) - (b.nivel == "erro" ? 0 : 1)).map(i => `<li class="ck-${i.ok ? "ok" : i.nivel}">${ic(i.ok ? "ok" : i.nivel == "erro" ? "bloqueio" : "alerta")}<div><b>${esc(i.titulo)}</b>${i.ok ? "" : `<div class="sub">${esc(i.detalhe)} <a href="#" onclick="ir('${i.pagina}');return false">resolver</a></div>`}</div></li>`).join("")}</ul>
    <p class="ck-feitos">${ic("ok")}Em ordem: ${sd.itens.filter(i => i.ok).map(i => esc(i.titulo)).join(" · ") || "nenhum item ainda"}</p></details>`}
  <div class="kpis">
    ${kpi("destaque", "nota", `Faturado em ${mes(p.competencia)}`, brl(p.faturado_mes), "por competência")}
    ${kpi("destaque", "receber", "Recebido no mês", brl(p.recebido_mes), "pagamentos baixados")}
    ${kpi("destaque", "relogio", "A receber", brl(p.a_receber), "títulos em aberto")}
    ${kpi(p.atrasado ? "critico" : "destaque", "alerta", "Em atraso", brl(p.atrasado), `${p.atrasado_qtd} título(s) <span class="selo ${p.inadimplencia_pct > 5 ? "critico" : p.inadimplencia_pct > 2 ? "alerta" : "bom"}">inadimplência ${String(p.inadimplencia_pct).replace(".", ",")}%</span>`)}
  </div>
  <div class="kpis secundarios">
    ${kpi("", "contratos", "Receita recorrente (MRR)", brl(p.mrr), `${p.contratos_ativos} cliente(s) na recorrência · ticket médio ${brl(p.ticket_medio)}`)}
    ${kpi("", "pagar", "A pagar", brl(p.a_pagar), p.a_pagar_atrasado ? `<span class="selo critico">${brl(p.a_pagar_atrasado)} vencido</span>` : "nada vencido")}
  </div>
  <div class="grid2">
    <div class="card"><h2>${ic("relatorios")}Faturado x recebido — últimos 12 meses</h2><div id="g_painel"></div></div>
    <div class="card"><h2>${ic("alerta")}Alertas</h2>${al.length ? `<ul class="alertas">${al.map(a => `<li class="${a.sev}"><span class="ai">${ic(a.icone)}</span><div class="txt">${a.html}</div></li>`).join("")}</ul>` : `<div class="tudo-ok">${ic("ok")}Tudo em dia</div>`}</div>
  </div>
  <div class="grid2">
    <div class="card"><h2>${ic("bloqueio")}Maiores devedores</h2>${tabela([{ t: "Cliente", f: x => esc(x.cliente) }, { t: "Valor atualizado", n: 1, f: x => brl(x.valor) }], p.maiores_devedores, "Ninguém em atraso.")}</div>
    <div class="card"><h2>${ic("relogio")}Vencem nos próximos 7 dias</h2>${tabela([{ t: "Cliente", f: t => esc(t.cliente_nome) }, { t: "Vencimento", f: t => dt(t.vencimento) }, { t: "Valor", n: 1, f: t => brl(t.valor_cent) }, { t: "NFS-e", f: t => selo(t.nfse_status) }], p.proximos_7_dias, "Nenhum vencimento na semana.")}</div>
  </div>`;
  if (!sd.completo) mostrarMigracao($("#migra"));
  montarGrafico($("#g_painel"), p.serie, [{ k: "faturado", rot: "Faturado (competência)", cor: "--serie-1" }, { k: "recebido", rot: "Recebido", cor: "--serie-2" }], { aria: "Faturado e recebido nos últimos 12 meses" });
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
    regua: "Régua de cobrança", resumo: "Resumo diário por e-mail", backup: "Backup" };
  const fmt = v => typeof v == "object" ? Object.entries(v).map(([k, x]) => `${k}: ${x}`).join(" · ") : String(v);
  return `<table>${Object.entries(nomes).filter(([k]) => k in r).map(([k, t]) => `<tr><td>${t}</td><td>${esc(fmt(r[k]))}</td></tr>`).join("")}</table><p></p>`;
}
