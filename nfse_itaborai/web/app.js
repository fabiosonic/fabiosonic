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
const ic = n => `<svg class="ic" aria-hidden="true"><use href="#i-${n}"/></svg>`;
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
    linhas.map(l => `<tr>${cols.map(c => `<td class="${c.n ? "n" : ""}" data-r="${esc(String(c.t).replace(/<[^>]*>/g, ""))}">${c.f(l)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
}
function opcoesClientes() { return ST.clientes.map(c => `<option value="${esc(c.razao_social)} — ${fmtDoc(c.cpf_cnpj)}">`).join(""); }
function docDe(txt) { const m = String(txt).match(/(\d[\d./-]{10,})\s*$/); return m ? m[1].replace(/\D/g, "") : String(txt).replace(/\D/g, ""); }
function form(el) { const o = {}; $$("[name]", el).forEach(i => o[i.name] = i.type == "checkbox" ? i.checked : i.value); return o; }
async function carregarEstado() {
  ST = await api("estado");
  const b = $("#amb");
  b.innerHTML = `<span class="ponto"></span><span><b>${ST.producao ? "Produção" : "Homologação"}</b><small>${ST.producao ? "Notas com validade fiscal" : "Teste, sem validade"} · ${nomeCanal(true)}</small></span>`;
  b.className = "amb " + (ST.producao ? "prod" : "hom");
  b.title = "Clique para trocar o ambiente";
  const e = ST.empresa || {}, nome = (e.nome || "Empresa").trim();
  const ini = nome.split(/\s+/).filter(w => w.length > 2 && !/^(ltda|me|epp|eireli|s\/a|de|da|do|e)$/i.test(w)).slice(0, 2).map(w => w[0]).join("").toUpperCase() || nome.slice(0, 2).toUpperCase();
  $("#empresa").innerHTML = `<span class="selo-marca">${esc(ini)}</span><span class="marca-txt">${esc(nome)}<small>${ST.empresas.length > 1 ? `${ST.empresas.length} empresas · trocar` : "Financeiro · NFS-e"}</small></span><svg class="ic seta"><use href="#i-contratos"/></svg>`;
  document.title = `${nome} · Financeiro e NFS-e`;
}
async function trocarEmpresa() {
  const l = await api("empresas");
  modal(`<h2>${ic("clientes")}Empresas</h2><p class="sub">Cada empresa tem seus próprios clientes, notas, financeiro, credenciais e configurações. O robô trabalha para todas.</p>
    <div class="lista-empresas">${l.map(e => `<button class="emp ${e.ativa ? "on" : ""}" data-id="${esc(e.id)}"><b>${esc(e.nome)}</b><span>CNPJ ${fmtDoc(e.cnpj || "")} · ${e.producao ? "produção" : "homologação"}</span>${e.ativa ? '<span class="selo bom">em uso</span>' : ""}</button>`).join("")}</div>
    <details class="nova-emp"><summary class="btn sec">${ic("mais")}Nova empresa</summary>
      <div class="campos" id="f_emp" style="margin-top:14px"><label class="inteiro">Razão social<input name="nome"></label><label>CNPJ<input name="cnpj"></label>
      <label>Inscrição municipal<input name="im"></label><label>Canal da NFS-e<select name="canal"><option value="municipal">Itaboraí (webservice)</option><option value="nacional">Nacional (nfse.gov.br)</option></select></label>
      <label>Chave do webservice (Itaboraí)<input name="chave" type="password"></label><label>Município emissor (IBGE)<input name="municipio" value="3301900"></label>
      <label>Optante do Simples<select name="simples"><option value="S">Sim</option><option value="N">Não</option></select></label></div>
      <p><button class="btn" id="criar_emp">Cadastrar e usar</button></p></details>
    <p><button class="btn sec" onclick="fechar()">Fechar</button></p>`);
  $$(".emp").forEach(b => b.onclick = async () => { await api("empresa/ativar", { id: b.dataset.id }); fechar(); await carregarEstado(); ir(PAG); aviso("Empresa em uso: " + b.querySelector("b").textContent); });
  $("#criar_emp").onclick = async () => { await api("empresa/criar", form($("#f_emp"))); fechar(); await carregarEstado(); ir("config"); aviso("Empresa cadastrada. Complete as configurações e o serviço padrão.", 7000); };
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
  if (p.contratos_a_confirmar) A("info", "contratos", `<b>${p.contratos_a_confirmar}</b> contrato(s) recorrente(s) detectado(s) nas suas notas — <a href="#" onclick="ir('contratos');return false">conferir</a> ou <a href="#" onclick="confirmarTodos();return false"><b>confirmar todos</b></a>`);
  if (p.sem_nfse) A("alerta", "nota", `<b>${p.sem_nfse}</b> título(s) sem NFS-e válida — <a href="#" onclick="ir('receber');return false">ver</a>`);
  if (p.atrasado_qtd) A("serio", "relogio", `<b>${p.atrasado_qtd}</b> título(s) em atraso de <b>${p.clientes_atrasados}</b> cliente(s): <b>${brl(p.atrasado)}</b>`);
  if (p.criticos.length) A("critico", "bloqueio", `<b>${p.criticos.length}</b> cliente(s) com atraso crítico (≥ ${ST.config.cobranca.bloquear_apos_dias} dias): ${p.criticos.slice(0, 3).map(esc).join(", ")}${p.criticos.length > 3 ? ` e mais ${p.criticos.length - 3} — <a href="#" onclick="ABA_REL='aging';ir('relatorios');return false">ver todos</a>` : ""}`);
  if (p.a_pagar_atrasado) A("serio", "pagar", `Contas a pagar vencidas: <b>${brl(p.a_pagar_atrasado)}</b>`);
  if (p.sublimite_pct >= 80) A("critico", "alerta", `RBT12 em ${p.sublimite_pct}% do sublimite de R$ 3,6 mi do Simples`);
  if (!ST.config.automacao.ativa) A("alerta", "play", `O robô financeiro está desligado — <a href="#" onclick="ir('config');return false">ligar em Configurações</a>`);
  const robo = ST.config.automacao.ativa ? `<span class="selo bom">Robô ligado</span><span>${p.ultima_execucao_robo ? "última execução " + dt(p.ultima_execucao_robo.slice(0, 10)) + " às " + p.ultima_execucao_robo.slice(11, 16) : "ainda não executou"}</span>` : `<span class="selo critico">Robô desligado</span>`;
  const kpi = (cls, icone, rot, val, sub = "") => `<div class="kpi ${cls}"><div class="r">${ic(icone)}${rot}</div><div class="v">${val}</div>${sub ? `<div class="s">${sub}</div>` : ""}</div>`;
  el.innerHTML = `<h1>Painel <span class="titulo-sub">${robo}</span><span class="acoes"><button class="btn sec" id="robo">${ic("play")}Rodar robô agora</button></span></h1>
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
    ${kpi("", "contratos", "Receita recorrente (MRR)", brl(p.mrr), `${p.contratos_ativos} contrato(s) · ticket médio ${brl(p.ticket_medio)}`)}
    ${kpi("", "pagar", "A pagar", brl(p.a_pagar), p.a_pagar_atrasado ? `<span class="selo critico">${brl(p.a_pagar_atrasado)} vencido</span>` : "nada vencido")}
    ${kpi("", "relatorios", "RBT12 (Simples Nacional)", brl(p.rbt12), `DAS estimado ${String(p.aliquota_simples_estimada).replace(".", ",")}% · ${String(p.sublimite_pct).replace(".", ",")}% do sublimite`)}
  </div>
  <div class="grid2">
    <div class="card"><h2>${ic("relatorios")}Faturado x recebido — últimos 12 meses</h2><div id="g_painel"></div></div>
    <div class="card"><h2>${ic("alerta")}Alertas</h2>${al.length ? `<ul class="alertas">${al.map(a => `<li class="${a.sev}"><span class="ai">${ic(a.icone)}</span><div class="txt">${a.html}</div></li>`).join("")}</ul>` : `<div class="tudo-ok">${ic("ok")}Tudo em dia</div>`}</div>
  </div>
  <div class="grid2">
    <div class="card"><h2>${ic("bloqueio")}Maiores devedores</h2>${tabela([{ t: "Cliente", f: x => esc(x.cliente) }, { t: "Valor atualizado", n: 1, f: x => brl(x.valor) }], p.maiores_devedores, "Ninguém em atraso.")}</div>
    <div class="card"><h2>${ic("relogio")}Vencem nos próximos 7 dias</h2>${tabela([{ t: "Cliente", f: t => esc(t.cliente_nome) }, { t: "Vencimento", f: t => dt(t.vencimento) }, { t: "Valor", n: 1, f: t => brl(t.valor_cent) }, { t: "NFS-e", f: t => selo(t.nfse_status) }], p.proximos_7_dias, "Nenhum vencimento na semana.")}</div>
  </div>`;
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
    cobrancas_criadas: "Cobranças (PIX/boleto) criadas", baixas_banco: "Boletos pagos baixados (Inter)", boletos_pdf: "PDFs de boletos salvos", extratos: "Extratos importados",
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
  el.innerHTML = `<h1>Contas a receber <span class="acoes"><button class="btn" id="novo_t">${ic("mais")}Título avulso</button><button class="btn sec" id="pdf_bol">${ic("download")}PDFs dos boletos</button><a class="btn sec" href="/export/titulos.csv">${ic("download")}Exportar CSV</a></span></h1>
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
  const prin = [], mais = [];
  const it = (txt, js) => `<button onclick="this.closest('details').open=false;${js}">${txt}</button>`;
  if (t.status == "aberto") {
    prin.push(`<button class="btn min" onclick="baixar(${t.id},${t.total_cent})">Baixar</button>`);
    prin.push(`<button class="btn min sec" onclick="cobrar(${t.id})">Cobrar</button>`);
    if (t.banco_id) mais.push(`<a href="/boleto/${t.id}.pdf" target="_blank">${ic("download")}Boleto em PDF</a>`);
    if (["pendente", "erro", "teste"].includes(t.nfse_status)) mais.push(it(`${ic("nota")}Emitir NFS-e`, `emitirTitulo(${t.id})`));
  }
  if (t.status == "pago") prin.push(`<button class="btn min sec" onclick="estornar(${t.id})">Estornar</button>`);
  mais.push(it(`${ic("relogio")}Histórico`, `historicoTitulo(${t.id})`));
  if (t.status == "aberto") mais.push(it(`${ic("x")}Cancelar título`, `cancelarTitulo(${t.id},'${t.nfse_status}')`).replace("<button", '<button class="perigo"'));
  return `<div class="acoes-linha">${prin.join("")}<details class="menu-acoes"><summary class="btn min sec" title="Mais ações">Mais</summary><div class="pop">${mais.join("")}</div></details></div>`;
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
    ${r.pdf ? `<p class="sub">PDF do boleto para anexar no WhatsApp: ${esc(r.pdf)} <button class="btn min sec" onclick="api('boletos/abrir_pasta')">Abrir pasta</button> <a class="btn min sec" href="/boleto/${id}.pdf" target="_blank">Ver PDF</a></p>` : ""}
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
  el.innerHTML = `<h1>Contratos recorrentes <span class="acoes"><button class="btn" id="nc">${ic("mais")}Novo contrato</button><button class="btn sec" id="hist">${ic("raio")}Criar a partir do histórico</button><button class="btn sec" id="gerar">Gerar títulos do mês</button></span></h1>
  <div class="kpis"><div class="kpi"><div class="r">Contratos ativos</div><div class="v">${ativos.length}</div></div><div class="kpi"><div class="r">MRR</div><div class="v">${brl(ativos.reduce((a, c) => a + c.valor_cent, 0))}</div></div></div>
  ${pend.length ? `<div class="card" style="border-color:var(--alerta)"><h2>${pend.length} contrato(s) detectado(s) automaticamente</h2><p>O robô encontrou cobrança mensal de mesmo valor nas suas notas. Confira e confirme: só depois disso eles passam a emitir NFS-e e cobrar. Começam no mês seguinte à última nota, para não cobrar em dobro.</p><button class="btn" onclick="confirmarTodos()">Confirmar todos</button></div>` : ""}
  <div class="card"><p class="sub">Todo mês, no dia configurado, o robô gera a conta a receber de cada contrato, emite a NFS-e, cria o PIX/boleto e coloca na régua de cobrança. Reajuste anual automático no mês escolhido.</p>
  ${tabela([{ t: "Cliente", f: c => `${esc(c.cliente_nome)}<div class="sub">${esc(c.descricao)}</div>` }, { t: "Valor", n: 1, f: c => num(c.valor_cent) }, { t: "Vence dia", f: c => c.dia_vencimento },
    { t: "Vigência", f: c => `${mes(c.inicio)} → ${c.fim ? mes(c.fim) : "sem fim"}` }, { t: "Reajuste", f: c => c.mes_reajuste ? `${c.reajuste_pct}% em ${String(c.mes_reajuste).padStart(2, "0")}` : "—" },
    { t: "NFS-e", f: c => c.emitir_nfse ? "automática" : "não emite" }, { t: "Situação", f: c => !c.ativo ? selo("cancelado").replace("Cancelado", "Encerrado") : c.confirmado ? selo("bom").replace("Bom", "Ativo") : selo("pendente").replace("Pendente", "A confirmar") + ` <button class="btn min" onclick="confirmarUm(${c.id})">Confirmar</button>` },
    { t: "", f: c => `<div class="acoes-linha"><button class="btn min sec" onclick='editarContrato(${JSON.stringify(c).replace(/'/g, "&#39;")})'>Editar</button>${c.ativo ? ` <button class="btn min sec" onclick="encerrar(${c.id})">Encerrar</button>` : ""}</div>` }], lst, "Nenhum contrato. Use “Criar a partir do histórico” para montar a carteira em um clique.")}</div>`;
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
  <div class="card"><h2>WhatsApp para enviar (${fila.length})</h2><p class="sub">Clique em “Enviar” para abrir a conversa com a mensagem pronta (linha digitável e PIX). O PDF do boleto está na pasta de boletos para anexar.</p>
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
  el.innerHTML = `<h1>Contas a pagar <span class="acoes"><button class="btn" id="nd">${ic("mais")}Nova despesa</button></span></h1>
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
    <label class="soltar" id="zona"><input type="file" id="ofx" accept=".ofx,.OFX" hidden>${ic("download")}<span><b>Selecione ou arraste o extrato .ofx</b><small>O robô também importa sozinho todo .ofx novo da pasta ${esc(ST.config.pastas.extratos || "")}${(ST.config.financeiro.contas_bancarias || []).length ? ` · conta vinculada: ${esc(ST.config.financeiro.contas_bancarias.join(", "))}` : ""}</small></span></label><div id="ofx_res"></div></div>
  <div class="card"><h2>Lançamentos não conciliados (${pend.length})</h2>
  ${tabela([{ t: "Data", f: m => dt(m.data) }, { t: "Histórico", f: m => esc(m.descricao) }, { t: "Valor", n: 1, f: m => num(m.valor_cent) },
    { t: "Sugestões", f: m => m.sugestoes.length ? m.sugestoes.map(s => `<button class="btn min sec" onclick="vincular(${m.id},${s.id})" title="Venc. ${dt(s.vencimento)}">${esc(s.cliente.slice(0, 28))} · ${num(s.valor_cent)}</button>`).join(" ") : '<span class="sub">—</span>' }], pend, "Tudo conciliado ✔")}</div>`;
  const zona = $("#zona");
  zona.ondragover = e => { e.preventDefault(); zona.classList.add("sobre"); };
  zona.ondragleave = () => zona.classList.remove("sobre");
  zona.ondrop = e => { e.preventDefault(); zona.classList.remove("sobre"); if (e.dataTransfer.files[0]) $("#ofx").onchange({ target: { files: e.dataTransfer.files } }); };
  $("#ofx").onchange = async e => { const f = e.target.files[0]; if (!f) return;
    const buf = await f.arrayBuffer(); let txt = new TextDecoder("utf-8").decode(buf); if (txt.includes("�")) txt = new TextDecoder("windows-1252").decode(buf);
    const r = await api("conciliacao/importar", { ofx: txt });
    $("#ofx_res").innerHTML = `<div class="msg ok">${r.lancamentos} lançamento(s) lidos · ${r.novos} novo(s) · <b>${r.titulos}</b> recebimento(s) baixado(s) · ${r.despesas} pagamento(s) conciliado(s)</div>`;
    setTimeout(() => ir("conciliacao"), 2500); };
};
async function vincular(movimento, titulo) { await api("conciliacao/vincular", { movimento, titulo }); aviso("Conciliado e baixado ✔"); ir("conciliacao"); }

// ---------------------------------------------------------------- relatórios
let ABA_REL = "indicadores";
const contab = c => { c = Number(c || 0); if (!c) return "–"; const v = num(Math.abs(c)); return c < 0 ? `(${v})` : v; };
function cabImpressao(titulo, periodo) {
  const e = ST.config.empresa || {};
  return `<div class="cab-impressao"><div><b>${esc(e.nome || "")}</b><span>CNPJ ${fmtDoc(ST.cnpj || "")}</span></div>
    <div class="ci-tit"><b>${esc(titulo)}</b><span>${esc(periodo)}</span></div><div class="ci-data">Emitido em ${dt(hojeISO())}</div></div>`;
}
PAGINAS.relatorios = async el => {
  const abas = [["indicadores", "Indicadores"], ["dre", "DRE"], ["fluxo", "Fluxo de caixa"], ["livro", "Livro caixa"],
    ["aging", "Inadimplência"], ["clientes", "Por cliente"], ["fechamento", "Fechamento mensal"], ["log", "Log do sistema"]];
  if (!abas.some(([k]) => k == ABA_REL)) ABA_REL = "indicadores";
  el.innerHTML = `<h1>Relatórios <span class="acoes"><a class="btn sec" href="/export/titulos.csv">${ic("download")}Contas a receber (CSV)</a><button class="btn sec" onclick="window.print()">${ic("imprimir")}Imprimir / PDF</button></span></h1>
    <div class="abas">${abas.map(([k, t]) => `<button data-a="${k}" class="${k == ABA_REL ? "on" : ""}">${t}</button>`).join("")}</div><div id="rel"><div class="card"><div class="vazio">Carregando…</div></div></div>`;
  $$(".abas button", el).forEach(b => b.onclick = () => { ABA_REL = b.dataset.a; ir("relatorios"); });
  const r = $("#rel");
  if (ABA_REL == "indicadores") {
    const i = await api("rel/indicadores"), pc = v => String(v).replace(".", ",") + "%";
    const card = (icone, rot, val, sub, cls = "") => `<div class="kpi ${cls}"><div class="r">${ic(icone)}${rot}</div><div class="v">${val}</div><div class="s">${sub}</div></div>`;
    const cresc = i.crescimento_pct == null ? "sem base anterior" : `${i.crescimento_pct >= 0 ? "▲" : "▼"} ${pc(Math.abs(i.crescimento_pct))} sobre os 12 meses anteriores`;
    r.innerHTML = cabImpressao("Indicadores de desempenho", `Posição em ${dt(hojeISO())}`) + `<div class="kpis">
      ${card("nota", "Faturamento 12 meses", brl(i.faturamento_12m), cresc, "destaque")}
      ${card("contratos", "Receita recorrente (MRR)", brl(i.mrr), `média faturada ${brl(i.receita_media_mensal)}/mês`, "destaque")}
      ${card("pagar", "Ponto de equilíbrio mensal", brl(i.ponto_equilibrio), `despesas ${brl(i.despesa_media_mensal)}/mês · folga ${pc(i.folga_equilibrio_pct)}`, i.folga_equilibrio_pct < 10 ? "critico" : "destaque")}
      ${card("alerta", "Inadimplência (90 dias)", pc(i.inadimplencia_90d), `${i.dias_a_receber} dias de faturamento a receber`, i.inadimplencia_90d > 5 ? "critico" : "destaque")}</div>
      <div class="kpis secundarios">
      ${card("relogio", "Atraso médio ponderado", `${String(i.atraso_medio_ponderado).replace(".", ",")} dias`, `${pc(i.recebido_em_dia_pct)} do valor recebido em dia`)}
      ${card("clientes", "Clientes ativos", i.clientes_ativos, i.clientes_perdidos.length ? `${i.clientes_perdidos.length} sem faturamento nos últimos 2 meses` : "nenhum cliente perdido")}
      ${card("relatorios", "Concentração (top 5)", pc(i.concentracao_top5), `${i.clientes_classe_a} cliente(s) fazem 80% da receita`)}
      ${card("receber", "Ticket médio por nota", brl(i.ticket_medio), "últimos 12 meses")}</div>
      <div class="grid2"><div class="card"><h2>${ic("clientes")}Maiores clientes — participação na receita de 12 meses</h2>${barrasH(i.top_clientes.map(c => ({ rot: c.cliente, v: c.valor, extra: pc(c.pct) })))}</div>
      <div class="card"><h2>${ic("alerta")}Clientes sem faturamento recente</h2>${i.clientes_perdidos.length ? `<p class="sub">Faturavam entre 3 e 6 meses atrás e não têm nota nos últimos 2 meses. Confirme se houve rescisão ou falta de emissão.</p><ul class="lista">${i.clientes_perdidos.map(n => `<li>${esc(n)}</li>`).join("")}</ul>` : `<div class="tudo-ok">${ic("ok")}Nenhum cliente parou de faturar</div>`}</div></div>`;
  } else if (ABA_REL == "dre") {
    const ano = el._ano || new Date().getFullYear(), d = await api("rel/dre", { ano }), R = d.resumo, pc = v => String(v).replace(".", ",") + "%";
    r.innerHTML = cabImpressao("Demonstração do Resultado do Exercício (DRE)", `Exercício de ${ano} · regime de competência · valores em R$`) +
      `<div class="card"><div class="barra"><label>Exercício<select id="ano">${[0, 1, 2].map(k => new Date().getFullYear() - k).map(a => `<option ${a == ano ? "selected" : ""}>${a}</option>`).join("")}</select></label></div>
      <div class="kpis">${[["Receita bruta", brl(R.receita_bruta), "nota"], ["Resultado líquido", brl(R.resultado_liquido), "relatorios"], ["Margem líquida", pc(R.margem_liquida), "receber"], ["Carga tributária", pc(R.carga_tributaria), "banco"]]
        .map(([t, v, i]) => `<div class="kpi"><div class="r">${ic(i)}${t}</div><div class="v">${v}</div></div>`).join("")}</div>
      <div class="tabela dre"><table><thead><tr><th>Conta</th>${d.meses.map(m => `<th class="n">${mes(m).slice(0, 2)}/${m.slice(2, 4)}</th>`).join("")}<th class="n">Total</th><th class="n">AV %</th></tr></thead>
      <tbody>${d.linhas.map(l => `<tr class="${l.tipo}"><td style="padding-left:${12 + l.nivel * 0 + (l.tipo == "item" ? 18 : 0)}px">${esc(l.conta)}</td>${l.valores.map(v => `<td class="n">${contab(v)}</td>`).join("")}<td class="n">${contab(l.total)}</td><td class="n">${l.total ? pc(l.av) : ""}</td></tr>`).join("")}</tbody></table></div>
      <p class="sub nota-rodape">${esc(d.nota)} AV % = análise vertical sobre a receita bruta. Valores entre parênteses são reduções.</p></div>
      <div class="card"><h2>${ic("relatorios")}Evolução mensal</h2><div id="g_dre"></div></div>`;
    const ateMes = ano < new Date().getFullYear() ? 12 : ano > new Date().getFullYear() ? 0 : new Date().getMonth() + 1;
    montarGrafico($("#g_dre"), d.serie.slice(0, ateMes), [{ k: "receita_liquida", rot: "Receita líquida", cor: "--serie-1" }, { k: "despesas", rot: "Despesas", cor: "--serie-2" }, { k: "resultado", rot: "Resultado", cor: "--serie-3", linha: true }], { aria: "Receita líquida, despesas e resultado por mês" });
    $("#ano").onchange = e => { el._ano = e.target.value; ir("relatorios"); };
  } else if (ABA_REL == "fluxo") {
    const [m, sem] = await Promise.all([api("rel/fluxo_mensal"), api("rel/fluxo", { dias: 90 })]);
    const proj = m.filter(x => x.tipo != "realizado");
    r.innerHTML = cabImpressao("Fluxo de caixa", "Realizado (6 meses) e projetado (3 meses)") +
      `<div class="kpis">${proj.map(x => `<div class="kpi ${x.saldo < 0 ? "critico" : "destaque"}"><div class="r">${ic(x.tipo == "atual" ? "relogio" : "relatorios")}${mes(x.mes)} · ${x.tipo == "atual" ? "mês atual" : "projetado"}</div><div class="v">${brl(x.saldo)}</div><div class="s">entradas ${brl(x.entradas)} · saídas ${brl(x.saidas)}${x.saidas_estimadas ? " (média)" : ""}</div></div>`).join("")}</div>
      <div class="card"><h2>${ic("relatorios")}Entradas x saídas por mês</h2><div id="g_fluxo"></div>
      <p class="sub">Realizado pelo caixa (pagamentos efetivos). Projeção: títulos em aberto (atrasos acima de 60 dias ficam de fora), contratos ainda não faturados e contas a pagar; sem despesas lançadas para o mês, usa a média dos últimos 3 meses.</p></div>
      <div class="card"><h2>${ic("relogio")}Próximas semanas</h2>${tabela([{ t: "Semana de", f: s => dt(s.semana) }, { t: "Entradas", n: 1, f: s => num(s.entradas) },
        { t: "Saídas", n: 1, f: s => num(s.saidas) }, { t: "Saldo acumulado", n: 1, f: s => `<b class="${s.saldo_acumulado < 0 ? "neg" : ""}">${contab(s.saldo_acumulado)}</b>` }], sem, "Nada previsto.")}</div>`;
    montarGrafico($("#g_fluxo"), m, [{ k: "entradas", rot: "Entradas", cor: "--serie-1" }, { k: "saidas", rot: "Saídas", cor: "--serie-2" }, { k: "saldo", rot: "Saldo do mês", cor: "--serie-3", linha: true }],
      { projetado: p => p.tipo == "projetado", aria: "Entradas, saídas e saldo por mês", legendaExtra: `<span><i class="proj-leg"></i>Projetado</span>` });
  } else if (ABA_REL == "livro") {
    const ini = el._ini || hojeISO().slice(0, 8) + "01", fim = el._fim || hojeISO();
    const lc = await api("rel/livro_caixa", { inicio: ini, fim });
    r.innerHTML = cabImpressao("Livro caixa", `De ${dt(ini)} a ${dt(fim)} · regime de caixa`) +
      `<div class="card"><div class="barra"><label>De<input type="date" id="lc_ini" value="${ini}"></label><label>Até<input type="date" id="lc_fim" value="${fim}"></label></div>
      <div class="kpis secundarios">${[["Entradas", lc.entradas, "receber"], ["Saídas", lc.saidas, "pagar"], ["Saldo do período", lc.saldo, "banco"]].map(([t, v, i]) => `<div class="kpi"><div class="r">${ic(i)}${t}</div><div class="v">${brl(v)}</div></div>`).join("")}</div>
      ${tabela([{ t: "Data", f: x => dt(x.data) }, { t: "Histórico", f: x => esc(x.historico) }, { t: "Documento", f: x => `<span class="sub">${esc(x.documento)}</span>` },
        { t: "Entrada", n: 1, f: x => x.entrada ? num(x.entrada) : "" }, { t: "Saída", n: 1, f: x => x.saida ? num(x.saida) : "" }, { t: "Saldo", n: 1, f: x => contab(x.saldo) }], lc.movimentos, "Nenhuma movimentação no período.")}</div>`;
    $("#lc_ini").onchange = e => { el._ini = e.target.value; ir("relatorios"); };
    $("#lc_fim").onchange = e => { el._fim = e.target.value; ir("relatorios"); };
  } else if (ABA_REL == "aging") {
    const a = await api("rel/aging"), f = a.faixas, nomes = [["a_vencer", "A vencer"], ["1_30", "1–30 dias"], ["31_60", "31–60 dias"], ["61_90", "61–90 dias"], ["90_mais", "Mais de 90 dias"]];
    r.innerHTML = cabImpressao("Inadimplência por faixa de atraso (aging)", `Posição em ${dt(hojeISO())}`) +
      `<div class="kpis">${nomes.map(([k, t], j) => `<div class="kpi ${j >= 3 && f[k] ? "critico" : ""}"><div class="r">${t}</div><div class="v">${brl(f[k])}</div></div>`).join("")}</div>
      <div class="card">${tabela([{ t: "Cliente", f: c => esc(c.cliente) }, ...nomes.map(([k, t]) => ({ t, n: 1, f: c => c[k] ? num(c[k]) : "" }))], a.clientes)}</div>`;
  } else if (ABA_REL == "clientes") {
    const l = await api("rel/clientes");
    r.innerHTML = cabImpressao("Análise por cliente", "Últimos 12 meses") + `<div class="card"><p class="sub">Score de pagamento: 100 = paga sempre em dia; cai com a média de dias de atraso e com títulos vencidos em aberto.</p>` + tabela([{ t: "Cliente", f: c => esc(c.cliente) }, { t: "Faturado 12m", n: 1, f: c => num(c.faturado_12m) },
      { t: "Recebido", n: 1, f: c => num(c.recebido_total) }, { t: "Em aberto", n: 1, f: c => num(c.em_aberto) }, { t: "Atrasado (atualizado)", n: 1, f: c => c.atrasado ? num(c.atrasado) : "" },
      { t: "Atraso médio", n: 1, f: c => c.media_atraso + " d" }, { t: "Score", n: 1, f: c => `${c.score} ${selo(c.faixa)}` }], l) + `</div>`;
  } else if (ABA_REL == "fechamento") {
    const meses = []; const h = new Date(hojeISO() + "T12:00"); for (let k = 1; k <= 12; k++) { const d = new Date(h.getFullYear(), h.getMonth() - k, 1); meses.push(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`); }
    const c = ST.config;
    r.innerHTML = `<div class="card"><h2>${ic("relatorios")}Fechamento mensal automático</h2>
      <p class="sub">Todo dia ${c.resumo.dia_fechamento || 3}, o robô gera o relatório gerencial do mês anterior (DRE do mês e acumulada, indicadores, inadimplência e maiores devedores), salva em <b>${esc(c.pastas.relatorios || "")}</b> e envia ao dono${c.resumo.email_dono ? ` (${esc(c.resumo.email_dono)})` : " (informe o e-mail em Configurações)"}. ${c.resumo.ultimo_fechamento ? "Último: " + mes(c.resumo.ultimo_fechamento) + "." : ""}</p>
      <p><button class="btn" id="fech">${ic("play")}Gerar e enviar o do mês passado agora</button> <button class="btn sec" onclick="api('relatorios/abrir_pasta')">${ic("download")}Abrir pasta</button></p>
      ${tabela([{ t: "Competência", f: m => mes(m) }, { t: "", f: m => `<a class="btn min sec" href="/fechamento/${m}.html" target="_blank">Abrir relatório</a>` }], meses)}</div>`;
    $("#fech").onclick = async () => { const x = await api("fechamento/gerar"); aviso(x.resultado, 6000); await carregarEstado(); };
  } else {
    const l = await api("log");
    r.innerHTML = `<div class="card">${tabela([{ t: "Quando", f: x => esc(x.quando) }, { t: "Tipo", f: x => esc(x.tipo) }, { t: "Mensagem", f: x => esc(x.mensagem) }], l)}</div>`;
  }
};
function barrasH(itens) {
  if (!itens.length) return '<div class="vazio">Sem dados.</div>';
  const max = Math.max(...itens.map(x => x.v));
  return `<div class="barras-h">${itens.map(x => `<div class="bh"><span class="bh-rot" title="${esc(x.rot)}">${esc(x.rot)}</span><span class="bh-trilho"><span class="bh-barra" style="width:${Math.max(1, x.v / max * 100)}%"></span></span><span class="bh-val">${brl(x.v)}<small>${esc(x.extra || "")}</small></span></div>`).join("")}</div>`;
}

// ---------------------------------------------------------------- clientes
PAGINAS.clientes = async el => {
  el.innerHTML = `<h1>Clientes</h1><div class="card"><div class="barra"><label>CNPJ / CPF<input id="c_doc" placeholder="só números"></label></div>
    <div class="campos" id="fcli"><label class="inteiro">Razão social / nome<input name="razao_social"></label>
    <label>Tipo logradouro<input name="tipo_logradouro" placeholder="RUA"></label><label>Logradouro<input name="logradouro"></label><label>Número<input name="numero"></label>
    <label>Complemento<input name="complemento"></label><label>Bairro<input name="bairro"></label><label>CEP<input name="cep"></label>
    <label>Cidade<input name="cidade" placeholder="automática pelo cód. IBGE"></label><label>Cód. IBGE município<input name="codigo_municipio"></label><label>UF<input name="uf" maxlength="2"></label>
    <label>Inscrição municipal<input name="inscricao_municipal"></label><label>E-mail (cobrança)<input name="email"></label><label>Telefone / WhatsApp<input name="telefone"></label></div>
    <p><button class="btn" id="sc">Salvar cliente</button> <button class="btn sec" id="lc">Novo</button></p></div>
    <div class="card"><div class="barra"><label style="flex:1">Procurar<input id="c_f" placeholder="nome ou CNPJ"></label></div><div id="c_tab"></div></div>`;
  const END = ["tipo_logradouro", "logradouro", "numero", "complemento", "bairro", "cep", "cidade", "codigo_municipio", "uf"];
  const preencher = c => { $("#c_doc").value = c.cpf_cnpj || ""; $$("#fcli [name]").forEach(i => i.value = (END.includes(i.name) ? (c.endereco || {})[i.name] : c[i.name]) || ""); };
  const desenhar = () => { const f = $("#c_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#c_tab").innerHTML = `<p class="sub">${ST.clientes.length} cliente(s). Sem e-mail ou telefone o cliente não recebe a régua de cobrança.</p>` + tabela([{ t: "Cliente", f: c => esc(c.razao_social) }, { t: "CPF/CNPJ", f: c => fmtDoc(c.cpf_cnpj) },
      { t: "Contato", f: c => (c.email ? `<span title="${esc(c.email)}">${ic("email")}</span> ` : "") + (c.telefone ? `<span title="${esc(c.telefone)}">${ic("fone")}</span>` : "") || '<span class="sub">sem contato</span>' }, { t: "Última nota", f: c => c.ultimo_valor ? `${dt(c.ultima_data)} · ${Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "" },
      { t: "", f: c => `<button class="btn min sec" data-ed="${c.cpf_cnpj}">Editar</button> <button class="btn min sec" data-ex="${c.cpf_cnpj}" title="Excluir">${ic("x")}</button>` }],
      ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)));
    $$("[data-ed]").forEach(b => b.onclick = () => { preencher(ST.clientes.find(c => c.cpf_cnpj == b.dataset.ed)); scrollTo(0, 0); });
    $$("[data-ex]").forEach(b => b.onclick = async () => { if (confirm("Excluir do cadastro?")) { await api("cliente/excluir", { cpf_cnpj: b.dataset.ex }); await carregarEstado(); desenhar(); } }); };
  $("#c_f").oninput = desenhar; desenhar();
  $("#lc").onclick = () => preencher({});
  $("#sc").onclick = async () => { const f = form($("#fcli")), e = {}; END.forEach(k => { e[k] = f[k]; delete f[k]; });
    await api("cliente/salvar", { ...f, cpf_cnpj: $("#c_doc").value, endereco: e }); aviso("Cliente salvo ✔"); await carregarEstado(); desenhar(); };
};

// ---------------------------------------------------------------- configurações
PAGINAS.config = async el => {
  const [c, cred] = await Promise.all([api("config"), api("empresa/credenciais")]);
  const sp = ST.padrao || {};
  const cr = (k, t, tipo = "text") => `<label>${t}<input type="${tipo}" data-cred="${k}" value="${esc(cred[k] || "")}"></label>`;
  const sv = (k, t) => `<label>${t}<input data-serv="${k}" value="${esc(sp[k] ?? "")}"></label>`;
  const ck = (s, k, t) => `<label class="chk"><input type="checkbox" data-s="${s}" data-k="${k}" ${c[s][k] ? "checked" : ""}> ${t}</label>`;
  const sl = (s, k, t, ops) => `<label>${t}<select data-s="${s}" data-k="${k}">${ops.map(([v, x]) => `<option value="${v}" ${String(c[s][k]) == v ? "selected" : ""}>${x}</option>`).join("")}</select></label>`;
  const tx = (s, k, t, tipo = "text", extra = "") => `<label>${t}<input type="${tipo}" data-s="${s}" data-k="${k}" value="${esc(Array.isArray(c[s][k]) ? c[s][k].join(", ") : c[s][k])}" ${extra}></label>`;
  el.innerHTML = `<h1>Configurações <span class="acoes"><button class="btn" id="salvar">Salvar tudo</button></span></h1>
  <div class="card"><h2>${ic("play")}Robô financeiro</h2><p class="sub">Com o robô ligado, o sistema roda sozinho ao abrir e a cada hora (e todo dia pelo Agendador do Windows, se você rodar INSTALAR.bat): gera os títulos dos contratos, emite as NFS-e (só em produção), cria o PIX/boleto, envia a régua de cobrança, dá baixa nos pagamentos e faz backup.</p>
    <div class="campos">${ck("automacao", "ativa", "<b>Robô ligado</b>")}${ck("automacao", "gerar_titulos", "Gerar títulos dos contratos")}${ck("automacao", "emitir_nfse", "Emitir NFS-e")}${ck("automacao", "criar_cobranca", "Criar PIX/boleto")}${ck("automacao", "baixar_boletos", "Salvar PDF dos boletos")}
    ${ck("automacao", "regua", "Régua de cobrança")}${ck("automacao", "sincronizar_banco", "Baixa automática dos boletos (Inter)")}${ck("automacao", "despesas_recorrentes", "Despesas recorrentes")}${ck("automacao", "backup", "Backup diário")}</div></div>
  <div class="card"><h2>${ic("clientes")}Empresa emissora e credenciais</h2><p class="sub">Dados da empresa em uso (${esc((ST.empresa || {}).nome || "")}). Ficam só neste computador, no arquivo .env da empresa.</p>
    <div class="campos">${cr("cnpj", "CNPJ")}${cr("im", "Inscrição municipal")}${cr("ie", "Inscrição estadual")}${cr("chave", "Chave do webservice (Itaboraí)", "password")}${cr("proximo_rps", "Próximo RPS", "number")}
    <label>Optante do Simples<select data-cred="simples"><option value="S" ${cred.simples != "N" ? "selected" : ""}>Sim</option><option value="N" ${cred.simples == "N" ? "selected" : ""}>Não</option></select></label></div></div>
  <div class="card"><h2>${ic("nota")}Serviço padrão das notas</h2><p class="sub">Usado em toda emissão desta empresa (avulsa, lote e recorrência). Confira com o cadastro municipal e a Tabela IBS x CBS.</p>
    <div class="campos"><label class="inteiro">Descrição padrão<input data-serv="descricao" value="${esc(sp.descricao || "")}"></label>${sv("item_lista_servico", "Item LC 116 (ex.: 17.19)")}${sv("codigo_desdobro", "Desdobro nacional (6 dígitos)")}${sv("codigo_nbs", "NBS (9 dígitos)")}${sv("cnae", "CNAE")}
    ${sv("aliquota_iss", "Alíquota ISS (%)")}${sv("tipo_tributacao", "Tipo de tributação (4 = Simples)")}${sv("iss_retido", "ISS retido (1 sim / 2 não)")}${sv("indicador_operacao", "IBS/CBS: cIndOp")}${sv("classificacao_tributaria", "IBS/CBS: cClassTrib")}${sv("ibpt_percentual", "Carga tributária IBPT (%)")}
    <label class="inteiro">Observações na nota<input data-serv="observacoes" value="${esc(sp.observacoes || "")}"></label></div></div>
  <div class="card"><h2>${ic("nota")}Emissão da NFS-e</h2><p class="sub">Escolha por onde as notas saem. <b>Itaboraí</b>: webservice da prefeitura (chave no .env). <b>Nacional</b>: Emissor Nacional da NFS-e (Sefin/ADN — nfse.gov.br), com o certificado digital A1 do escritório. A nota já emitida é sempre cancelada pelo canal em que saiu. Homologação no nacional = “Produção Restrita”.</p>
    <div class="campos"><label>Canal de emissão<select data-s="emissao" data-k="canal">${[["municipal", "Itaboraí (webservice)"], ["nacional", "Nacional (nfse.gov.br)"]].map(([v, t]) => `<option value="${v}" ${c.emissao.canal == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <div class="inteiro cert-box"><label class="soltar"><input type="file" id="cert_arq" accept=".pfx,.p12" hidden>${ic("download")}<span><b id="cert_nome">${c.emissao.certificado_pfx ? "Certificado A1 cadastrado nesta empresa — clique para trocar" : "Selecionar certificado digital A1 (.pfx)"}</b><small>O arquivo é copiado só para a pasta desta empresa; nenhuma outra empresa tem acesso.</small></span></label>
      <label>Senha do certificado<input type="password" id="cert_senha" autocomplete="new-password" placeholder="${c.emissao.certificado_senha ? "•••••• (já cadastrada)" : "senha do .pfx"}"></label>
      <button class="btn" id="cert_salvar" type="button">${ic("ok")}Salvar certificado</button></div>
    ${tx("emissao", "serie_dps", "Série da DPS")}${tx("emissao", "proximo_dps", "Próximo nº da DPS", "number")}
    ${sl("emissao", "op_simp_nac", "Situação no Simples Nacional", [["1", "Não optante"], ["2", "MEI"], ["3", "ME/EPP"]])}
    ${sl("emissao", "reg_ap_trib_sn", "Apuração no Simples", [["1", "Tudo no DAS"], ["2", "ISS fora do DAS (fixo)"], ["3", "Tudo fora do DAS"]])}
    ${sl("emissao", "reg_esp_trib", "Regime especial", [["0", "Nenhum"], ["1", "Ato cooperado"], ["2", "Estimativa"], ["3", "ME municipal"], ["4", "Notário/registrador"], ["5", "Autônomo"], ["6", "Soc. de profissionais"]])}
    ${ck("emissao", "informar_ibscbs", "Informar IBS/CBS (cIndOp/cClassTrib do serviço padrão)")}${ck("emissao", "informar_im", "Informar inscrição municipal")}</div>
    <p><button class="btn sec" id="teste_cert">Testar certificado e conexão</button> <span class="sub">Salve antes de testar.</span></p><div id="cert_res"></div></div>
  <div class="card"><h2>Automações de entrada</h2><div class="campos">${ck("automacao", "importar_xml", "Ler XML das notas (clientes, notas emitidas fora, contratos)")}${ck("automacao", "importar_extratos", "Importar extratos .ofx da pasta")}${ck("automacao", "despesas_do_extrato", "Débitos do extrato viram despesas")}${ck("automacao", "resumo_diario", "Resumo diário por e-mail")}${ck("automacao", "fechamento_mensal", "Fechamento mensal automático")}</div>
    <div class="campos" style="margin-top:12px">${tx("pastas", "xml_nfse", "Pasta dos XML de NFS-e")}${tx("pastas", "extratos", "Pasta dos extratos (.ofx)")}${tx("resumo", "email_dono", "E-mail do dono (resumo e fechamento)")}${tx("resumo", "dia_fechamento", "Dia do fechamento mensal", "number")}${tx("pastas", "relatorios", "Pasta dos relatórios")}${tx("financeiro", "inicio_financeiro", "Notas externas a partir de", "date")}</div>
    <p><button class="btn sec" id="imp_xml">Ler XML agora</button> <button class="btn sec" id="env_res">Enviar resumo agora</button></p></div>
  <div class="card"><h2>Regras de despesa do extrato</h2><p class="sub">Uma por linha: PALAVRA = Categoria. Débito cujo histórico contém a palavra entra nessa categoria.</p>
    <textarea id="regras" rows="6">${esc(c.regras_despesa.map(([p, k]) => `${p.trim()} = ${k}`).join("\n"))}</textarea></div>
  <div class="card"><h2>Empresa e PIX</h2><div class="campos">${tx("empresa", "nome", "Nome no PIX")}${tx("empresa", "pix_chave", "Chave PIX que recebe")}${tx("empresa", "pix_cidade", "Cidade (PIX)")}${tx("empresa", "whatsapp", "WhatsApp do escritório")}${tx("empresa", "assinatura", "Assinatura das mensagens")}</div></div>
  <div class="card"><h2>Cobrança</h2><div class="campos">
    <label>Meio de cobrança<select data-s="cobranca" data-k="provedor">${[["inter", "Inter: boleto + PIX"], ["pix", "Só PIX copia e cola"], ["nenhum", "Nenhum"]].map(([v, t]) => `<option value="${v}" ${c.cobranca.provedor == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <h3 class="bloco">Banco Inter (boletos)</h3>${tx("cobranca", "inter_client_id", "Inter: client_id")}${tx("cobranca", "inter_client_secret", "Inter: client_secret", "password")}
    ${["crt", "key"].map(t => `<label class="soltar mini"><input type="file" class="inter_arq" data-t="${t}" accept=".${t}" hidden>${ic("download")}<span><b>${(t == "crt" ? c.cobranca.inter_certificado : c.cobranca.inter_chave) ? `Inter: .${t} cadastrado ✔` : `Selecionar o .${t} do Inter`}</b><small>${t == "crt" ? "certificado da integração" : "chave privada da integração"}</small></span></label>`).join("")}
    ${tx("cobranca", "inter_conta", "Inter: conta corrente (opcional)")}${tx("cobranca", "inter_dias_agenda", "Aceitar pagamento até (dias após venc.)", "number")}${ck("cobranca", "inter_sandbox", "Inter em sandbox (teste)")}
    <h3 class="bloco">Encargos e régua de cobrança</h3>${tx("cobranca", "multa_pct", "Multa (%)")}${tx("cobranca", "juros_mes_pct", "Juros ao mês (%)")}${tx("cobranca", "regua_dias", "Régua (dias, ex.: -3, 0, 1, 5, 15, 30)")}
    ${ck("cobranca", "regua_email", "Régua por e-mail (automático)")}${ck("cobranca", "regua_whatsapp", "Régua por WhatsApp (fila com 1 clique)")}${ck("cobranca", "anexar_boleto", "Anexar o PDF do boleto no e-mail")}${tx("pastas", "boletos", "Pasta dos PDFs dos boletos")}${tx("cobranca", "bloquear_apos_dias", "Alerta de atraso crítico após (dias)", "number")}
    <h3 class="bloco">Cobrança recorrente dos atrasados</h3>${ck("cobranca", "recorrente_ativa", "<b>Cobrar atrasados de forma recorrente</b>")}${tx("cobranca", "recorrente_apos_dias", "Começar após quantos dias de atraso", "number", 'min="1"')}${tx("cobranca", "recorrente_a_cada_dias", "Repetir a cada quantos dias", "number", 'min="1"')}</div></div>
  <div class="card"><h2>Banco Inter — como obter as credenciais</h2><p class="sub">No Internet Banking PJ do Inter: <b>Soluções para sua empresa › Nova integração</b>, marque os escopos <b>Emissão e cancelamento de boletos</b> e <b>Consulta de boletos</b>. Baixe o certificado (.crt) e a chave (.key), copie client_id e client_secret para cá, salve e teste. Os boletos são registrados direto na conta do escritório, com PIX no próprio boleto; o sistema dá a baixa sozinho quando o cliente paga.</p>
    <p><button class="btn sec" id="teste_inter">Testar conexão com o Inter</button></p></div>
  <div class="card"><h2>E-mail (SMTP)</h2><p class="sub">Gmail: servidor smtp.gmail.com, porta 587, e uma “senha de app” da conta Google.</p><div class="campos">${tx("smtp", "host", "Servidor")}${tx("smtp", "porta", "Porta", "number")}${tx("smtp", "usuario", "Usuário")}${tx("smtp", "senha", "Senha", "password")}${tx("smtp", "remetente", "Remetente")}${tx("smtp", "copia_para", "Cópia oculta para")}${ck("smtp", "ssl", "SSL direto (porta 465)")}</div>
    <p><button class="btn sec" id="teste_email">Enviar e-mail de teste</button></p></div>
  <div class="card"><h2>${ic("contratos")}13º honorário</h2><p class="sub">Em novembro e dezembro, cobra o honorário mensal de cada contrato ativo em parcelas, com NFS-e e boleto, entrando na régua de cobrança.</p>
    <div class="campos">${ck("decimo_terceiro", "ativo", "<b>Cobrar 13º honorário</b>")}${ck("decimo_terceiro", "emitir_nfse", "Emitir NFS-e das parcelas")}
    <label>Descrição na nota<input data-s="decimo_terceiro" data-k="descricao" value="${esc(c.decimo_terceiro.descricao || "")}"></label>
    ${c.decimo_terceiro.parcelas.map((p, j) => `<label>Parcela ${j + 1}: % do honorário<input data-p13="${j}" data-c="percentual" value="${esc(p.percentual)}"></label><label>Parcela ${j + 1}: vencimento (dd/mm)<input data-p13="${j}" data-c="vencimento" value="${esc(p.vencimento)}" placeholder="30/11"></label>`).join("")}</div></div>
  <div class="card"><h2>Financeiro</h2><div class="campos">${tx("financeiro", "dia_vencimento_padrao", "Dia de vencimento padrão", "number")}${tx("financeiro", "dia_geracao", "Dia de gerar a recorrência", "number")}${tx("financeiro", "prazo_avulso_dias", "Prazo da nota avulsa (dias)", "number")}
    ${tx("financeiro", "aliquota_simples_pct", "Alíquota DAS sem histórico (%)")}${ck("financeiro", "iss_fixo", "ISS fixo fora do DAS (escritório contábil)")}${tx("financeiro", "iss_fixo_mensal", "ISS fixo por mês (R$, para a DRE)")}${tx("financeiro", "contas_bancarias", "Contas bancárias desta empresa (banco-agência-conta)")}${tx("financeiro", "categorias_despesa", "Categorias de despesa")}</div></div>`;
  $("#salvar").onclick = async () => {
    const novo = { empresa: {}, smtp: {}, cobranca: {}, financeiro: {}, automacao: {}, pastas: {}, resumo: {}, emissao: {}, decimo_terceiro: {} };
    const p13 = c.decimo_terceiro.parcelas.map(p => ({ ...p }));
    $$("[data-p13]").forEach(i => { p13[+i.dataset.p13][i.dataset.c] = i.dataset.c == "percentual" ? valorNum(i.value) : i.value.trim(); });
    if (p13.some(p => !/^\d{1,2}\/(11|12)$/.test(p.vencimento))) return aviso("Vencimento do 13º: use dd/mm em novembro ou dezembro (ex.: 30/11, 20/12).");
    if (Math.abs(p13.reduce((a, p) => a + p.percentual, 0) - 100) > 0.01) return aviso("As parcelas do 13º devem somar 100% do honorário.");
    novo.decimo_terceiro.parcelas = p13;
    novo.regras_despesa = $("#regras").value.split("\n").map(l => l.split("=")).filter(x => x.length == 2 && x[0].trim()).map(([p, k]) => [p.trim().toUpperCase() + (p.trim().length <= 3 ? " " : ""), k.trim()]);
    $$("[data-s]").forEach(i => { let v = i.type == "checkbox" ? i.checked : i.value;
      if (["regua_dias"].includes(i.dataset.k)) v = v.split(/[,;\s]+/).filter(Boolean).map(Number);
      else if (["categorias_despesa", "contas_bancarias"].includes(i.dataset.k)) v = v.split(",").map(s => s.trim()).filter(Boolean);
      else if (["multa_pct", "juros_mes_pct", "aliquota_simples_pct", "iss_fixo_mensal"].includes(i.dataset.k)) v = valorNum(v);
      else if (i.type == "number") v = Number(v);
      novo[i.dataset.s][i.dataset.k] = v; });
    const cred = {}, serv = {};
    $$("[data-cred]").forEach(i => cred[i.dataset.cred] = i.value);
    $$("[data-serv]").forEach(i => serv[i.dataset.serv] = i.value.trim());
    await api("config/salvar", novo); await api("empresa/credenciais/salvar", cred); await api("servico/salvar", serv);
    await carregarEstado(); aviso("Configurações salvas ✔");
  };
  $("#cert_arq").onchange = e => { const f = e.target.files[0]; if (f) { $("#cert_nome").textContent = "Selecionado: " + f.name + " — informe a senha e clique em Salvar certificado"; $("#cert_senha").focus(); } };
  const lerB64 = f => new Promise((ok, erro) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = erro; r.readAsDataURL(f); });
  $("#cert_salvar").onclick = async () => {
    const f = $("#cert_arq").files[0]; if (!f) return aviso("Selecione o arquivo do certificado (.pfx).");
    const senha = $("#cert_senha").value; if (!senha) return aviso("Informe a senha do certificado.");
    const r = await api("certificado/enviar", { arquivo: await lerB64(f), senha });
    $("#cert_res").innerHTML = `<div class="msg ${r.vencido ? "erro" : "ok"}"><b>${esc(r.titular)}</b> — CNPJ ${fmtDoc(r.cnpj || "")} — válido até ${r.validade} (${r.dias_restantes} dias). Certificado guardado nesta empresa.</div>`;
    $("#cert_senha").value = ""; $("#cert_nome").textContent = "Certificado A1 cadastrado nesta empresa — clique para trocar"; };
  $$(".inter_arq").forEach(i => i.onchange = async e => { const f = e.target.files[0]; if (!f) return;
    await api("inter/arquivo", { tipo: i.dataset.t, arquivo: await lerB64(f) }); aviso(`Arquivo .${i.dataset.t} do Inter guardado nesta empresa ✔`); ir("config"); });
  $("#teste_cert").onclick = async () => {
    $("#cert_res").innerHTML = '<div class="msg">Abrindo o certificado e consultando o ADN…</div>';
    try { const r = await api("nacional/testar");
      $("#cert_res").innerHTML = `<div class="msg ${r.conexao && !r.vencido ? "ok" : "erro"}"><b>${esc(r.titular)}</b> — CNPJ ${fmtDoc(r.cnpj || "")} — válido até ${r.validade} (${r.dias_restantes} dias)<br>${esc(r.mensagem)}${r.convenio ? "<br>Convênio do município: " + esc(JSON.stringify(r.convenio)) : ""}</div>`;
    } catch (e) { $("#cert_res").innerHTML = ""; }
  };
  $("#teste_inter").onclick = async () => { const r = await api("inter/testar"); aviso(r.mensagem || "OK", 6000); };
  $("#imp_xml").onclick = async () => { aviso("Lendo XML…"); const r = await api("importacao/xml"); aviso(`XML: ${JSON.stringify(r)}`, 8000); await carregarEstado(); };
  $("#env_res").onclick = async () => { const r = await api("resumo/enviar"); aviso("Resumo: " + r.resultado, 6000); };
  $("#teste_email").onclick = async () => { const p = prompt("Enviar teste para qual e-mail?"); if (!p) return; await api("email/testar", { para: p }); aviso("E-mail de teste enviado ✔"); };
};

// ---------------------------------------------------------------- início
(async () => { await carregarEstado(); const h = location.hash.slice(1); ir(h in PAGINAS ? h : "painel"); })();
