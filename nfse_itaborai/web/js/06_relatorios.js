// Relatórios.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
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
