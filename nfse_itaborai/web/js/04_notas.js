// Emitir nota, lote, notas emitidas e assistente de validação.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- emitir / lote
function linhaRes(r) {
  if (r.contrato_id) r.alertas = [...(r.alertas || []), "Repetição mensal ativada: contrato nº " + r.contrato_id + " (veja em Contratos)."];
  if (r.sucesso && r.sem_nota) return `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · conta a receber lançada, sem NFS-e (regra da nota)${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`;
  if (r.sucesso && r.aguardando_pagamento) return `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · ${r.boleto ? "boleto gerado" : "conta a receber criada"}${r.link && r.link.startsWith("http") ? ` · <a href="${esc(r.link)}" target="_blank">abrir cobrança</a>` : ""} · a NFS-e será emitida automaticamente quando o pagamento for confirmado${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`;
  return r.sucesso ? `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · NFS-e <b>${esc(r.nfse)}</b> · ${r.canal == "nacional" ? "Nacional · chave " + esc(r.chave) : "RPS " + esc(r.rps)}${r.boleto ? " · boleto gerado" : ""}${r.link && r.link.startsWith("http") ? ` · <a href="${esc(r.link)}" target="_blank">abrir nota</a>` : ""}${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`
    : `<div class="msg erro"><span class="t">✖ ${esc(r.cliente)} — ${esc(r.valor)}</span>${(r.erros || []).map(e => `<div>${esc(e)}</div>`).join("")}</div>`;
}
PAGINAS.emitir = async el => {
  el.innerHTML = `<h1>Emitir nota</h1><div class="emitir-layout"><div class="card emitir-form"><div class="campos">
    <label class="inteiro">Cliente<input id="e_cli" list="dl_cli" placeholder="Digite o nome ou CNPJ e escolha"></label>
    <div class="inteiro ultima-nota" id="e_ultima" hidden></div>
    <label>Valor (R$)<input id="e_valor" inputmode="decimal" placeholder="0,00"></label>
    <label>Vencimento<input id="e_venc" type="date"></label>
    <label class="inteiro">Serviço (atividade)<select id="e_serv">${opcoesServ(servPadrao().id)}</select></label>
    <label class="inteiro">Descrição<input id="e_desc" maxlength="190" value="${esc(servPadrao().descricao || "")}"></label></div>
    <datalist id="dl_cli">${opcoesClientes()}</datalist>
    ${blocoFiscal("ef")}
    ${blocoNota()}
    ${blocoFaturar("e")}
    <p class="sub">Emitindo por: <b>${nomeCanal()}</b> — troque em <a href="#config">Configurações › Emissão</a>.</p>
    <button class="btn" id="e_btn">Emitir nota</button><div id="e_res"></div></div>
    <aside class="card resumo-nota" id="e_resumo" aria-live="polite"></aside></div>`;
  // resumo ao lado do formulário: o que vai sair na nota, atualizado a cada campo preenchido
  const resumo = () => {
    const c = ST.clientes.find(x => x.cpf_cnpj == docDe($("#e_cli").value)), sv = servDe($("#e_serv").value), e = (c || {}).endereco || {};
    const v = Math.round(Number(String($("#e_valor").value || "0").replace(/\./g, "").replace(",", ".")) * 100) || 0;
    const linha = (rot, val) => `<div class="rn-l"><dt>${rot}</dt><dd>${val}</dd></div>`;
    $("#e_resumo").innerHTML = `<div class="rn-cab"><span>Resumo da nota</span><span class="estado ${ST.producao ? "critico" : "atencao"}">${ic(ST.producao ? "alerta" : "relogio")}${ST.producao ? "Produção · com validade fiscal" : "Homologação · teste"}</span></div>
      <div class="rn-valor">${v ? brl(v) : '<span class="sub">R$ 0,00</span>'}</div>
      <dl>${linha("Tomador", c ? `<b>${esc(nomeCli(c.razao_social))}</b><span>${[c.estrangeiro ? "exterior" : fmtDoc(c.cpf_cnpj), [e.cidade, e.uf].filter(Boolean).map(esc).join("/")].filter(Boolean).join(" · ")}</span>${c.email ? `<span>${esc(c.email.split(";")[0])}</span>` : '<span class="neg">sem e-mail para a cobrança</span>'}` : '<span class="sub">escolha o cliente</span>')}
        ${linha("Serviço", `<b>${esc(sv.nome || "")}</b><span>item ${esc(sv.item_lista_servico || "?")} · ${esc(frase($("#e_desc").value).slice(0, 80))}</span>`)}
        ${linha("Vencimento", $("#e_venc").value ? dt($("#e_venc").value) : '<span class="sub">prazo padrão do sistema</span>')}
        ${linha("Cobrança", $("#e_cobrar").checked ? "boleto/PIX + régua de cobrança" : '<span class="sub">sem cobrança (só a nota)</span>')}
        ${linha("Emissão", esc(nomeCanal()))}</dl>`;
  };
  el.addEventListener("input", resumo); el.addEventListener("change", resumo); setTimeout(resumo);
  const atuRegra = ligarFaturar("e", "#e_btn", () => (ST.clientes.find(c => c.cpf_cnpj == docDe($("#e_cli").value)) || {}).cpf_cnpj || "");
  const trocaServ = id => { $("#e_serv").value = servDe(id).id; $("#e_desc").value = servDe(id).descricao || ""; };
  $("#e_serv").onchange = () => trocaServ($("#e_serv").value);
  $("#e_cli").oninput = () => { const c = ST.clientes.find(x => x.cpf_cnpj == docDe($("#e_cli").value)); if (c && c.ultimo_valor && !$("#e_valor").value) $("#e_valor").value = Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
    if (c && c.servico_id) trocaServ(c.servico_id); atuRegra(); if (c) preencherFiscal("ef", c.fiscal);
    // campos fixos das notas deste tomador (cadastro): entram já preenchidos em "Mais campos da nota"
    if (c && c.padroes_nota) { Object.entries(c.padroes_nota).forEach(([k, v]) => { const i = $(`.mais-nota [data-nx="${k}"]`, el); if (i && !i.value) i.value = v; }); atuNota(); } };
  ligarFiscal("ef");
  const atuNota = ligarNota(el, () => servDe($("#e_serv").value).item_lista_servico);
  $("#e_serv").addEventListener("change", atuNota);
  // última nota do tomador: mostra e permite copiar valor, serviço, descrição e os campos extras da nota
  let docUltima = "";
  const copiar = n => {
    $("#e_valor").value = num(n.valor_cent); if (n.servico_id) trocaServ(n.servico_id); $("#e_desc").value = n.descricao || $("#e_desc").value;
    preencherNota(el, n.extras || {}); atuNota(); atuRegra();
    if (Object.keys(n.extras || {}).length) $(".mais-nota", el).open = true;
    aviso(`Dados da nota ${n.nfse_numero ? "nº " + n.nfse_numero : ""} copiados — confira o valor e a descrição antes de emitir.`, 6000); };
  const mostrarUltima = async () => {
    const doc = docDe($("#e_cli").value), c = ST.clientes.find(x => x.cpf_cnpj == doc), box = $("#e_ultima");
    if (!c) { docUltima = ""; box.hidden = true; return; }
    if (doc == docUltima) return; docUltima = doc;
    const { nota } = await api("nfse/ultima", { cpf_cnpj: doc });
    if (docDe($("#e_cli").value) != doc) return;          // o usuário já trocou de cliente
    if (!nota) { box.hidden = true; return; }
    box.innerHTML = `${ic("nota")}<span><b>Última nota:</b> nº ${esc(nota.nfse_numero)} em ${dt(nota.data)} · competência ${mes(nota.competencia)} · <b>${brl(nota.valor_cent)}</b><span class="sub"> — ${esc(nota.descricao).slice(0, 90)}</span></span>
      <button class="btn min sec" type="button" id="e_copiar">${ic("lista")}Copiar dados da última nota</button>`;
    box.hidden = false; $("#e_copiar").onclick = () => copiar(nota); };
  const cliInput = $("#e_cli").oninput; $("#e_cli").oninput = () => { cliInput(); atuNota(); mostrarUltima(); };
  if (PREENCHER && PREENCHER.copiar) { const id = PREENCHER.copiar; PREENCHER = null; const n = await api("nfse/dados", { id });
    const c = ST.clientes.find(x => x.cpf_cnpj == n.cpf_cnpj);
    if (c) { $("#e_cli").value = `${c.razao_social} — ${fmtDoc(c.cpf_cnpj)}`; $("#e_cli").oninput(); }
    copiar(n); }
  if (PREENCHER) { const p = PREENCHER; PREENCHER = null; const c = ST.clientes.find(x => x.cpf_cnpj == p.doc);
    if (c) { $("#e_cli").value = `${c.razao_social} — ${fmtDoc(c.cpf_cnpj)}`; $("#e_cli").oninput(); }
    $("#e_valor").value = p.valor; if (p.servico_id) trocaServ(p.servico_id); $("#e_desc").value = p.desc || $("#e_desc").value;
    $(".mais-nota").open = true; $('[data-nx="subst_chave"]').value = p.subst_chave; atuNota();   // mostra motivo/descrição
    aviso("Substituição: confira os dados, escolha o motivo e emita. A nota antiga fica cancelada por substituição.", 9000); }
  $("#e_btn").onclick = async () => {
    const doc = docDe($("#e_cli").value), cli = ST.clientes.find(c => c.cpf_cnpj == doc);
    if (!cli) return aviso("Escolha um cliente da lista (ou cadastre em Clientes).");
    const v = $("#e_valor").value.trim(); if (!valorNum(v)) return aviso("Informe o valor.");
    const fz = lerFiscal("ef");
    if (!fz.usar_geral && [fz.aliquota_iss_retido, ...RET_NOMES.map(([k]) => fz[k])].some(x => x && isNaN(Number(x)))) return aviso("Percentual inválido nas regras fiscais do tomador.");
    const fat = opcoesFaturar("e"), regra = regraDe(cli.cpf_cnpj);
    if (!confirm(`${regra == "geracao" ? (ST.producao ? "EMITIR NOTA VÁLIDA" : "Teste em homologação") + " — " + nomeCanal() : regra == "baixa" ? "GERAR COBRANÇA — a NFS-e sai sozinha quando o pagamento for confirmado" : "LANÇAR CONTA A RECEBER — sem NFS-e"}`
      + `\n\n${cli.razao_social}\nServiço: ${servDe($("#e_serv").value).nome}\nR$ ${v}\nCobrança: ${fat.cobrar ? "sim (boleto/PIX + régua)" : "não"}\nRegras fiscais: ${fz.usar_geral ? "regra geral" : "específicas deste tomador (ficam guardadas nele)"}`)) return;
    if (!mesmoFiscal(fz, cli.fiscal)) { await api("cliente/fiscal", { cpf_cnpj: cli.cpf_cnpj, fiscal: fz }); await carregarEstado(); }
    $("#e_btn").disabled = true; $("#e_res").innerHTML = '<div class="msg">Enviando…</div>';
    try { const r = await api("emitir", { cpf_cnpj: doc, valor: v, descricao: $("#e_desc").value, servico_id: $("#e_serv").value, vencimento: $("#e_venc").value, ...fat, extras: lerNota(el) }); $("#e_res").innerHTML = linhaRes(r); if (r.sucesso) $("#e_valor").value = ""; }
    finally { $("#e_btn").disabled = false; }
  };
};
PAGINAS.lote = async el => {
  el.innerHTML = `<h1>Emitir em lote</h1><div class="card"><div class="barra"><label>Filtrar<input id="l_f" placeholder="nome ou CNPJ"></label>
    <label>Serviço<select id="l_serv">${opcoesServ("", "Serviço habitual de cada cliente")}</select></label>
    <label style="flex:1">Descrição para todas<input id="l_desc" maxlength="190" placeholder="em branco = descrição do serviço de cada cliente"></label></div>
    ${blocoFaturar("l")}
    <p class="sub">Marque os clientes. O valor vem da última nota — ajuste se precisar. Cada nota já gera a conta a receber.</p>
    <div id="l_tab"></div><p><button class="btn" id="l_btn">Emitir selecionadas</button> <span id="l_tot" class="sub"></span></p><div id="l_res"></div></div>`;
  const desenhar = () => { const f = $("#l_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#l_tab").innerHTML = tabela([{ t: '<input type="checkbox" id="l_todos">', f: c => `<input type="checkbox" class="lc" data-doc="${c.cpf_cnpj}">` },
      { t: "Cliente", f: c => celNome(c.razao_social, fmtDoc(c.cpf_cnpj)) },
      { t: "Valor (R$)", f: c => `<input class="lv" data-doc="${c.cpf_cnpj}" style="width:120px" value="${c.ultimo_valor ? Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 }) : ""}">` },
      { t: "Última nota", f: c => dt(c.ultima_data) }], ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)));
    $("#l_todos") && ($("#l_todos").onclick = e => { $$(".lc").forEach(x => x.checked = e.target.checked); somar(); });
    $$(".lc,.lv").forEach(x => x.oninput = x.onchange = somar); somar(); };
  const sel = () => $$(".lc:checked").map(x => ({ cpf_cnpj: x.dataset.doc, valor: $(`.lv[data-doc="${x.dataset.doc}"]`).value, descricao: $("#l_desc").value, servico_id: $("#l_serv").value || (ST.clientes.find(c => c.cpf_cnpj == x.dataset.doc) || {}).servico_id || "", ...opcoesFaturar("l") }));
  const somar = () => { const s = sel(); $("#l_tot").textContent = s.length ? `${s.length} nota(s) · total ${brl(Math.round(s.reduce((a, b) => a + valorNum(b.valor), 0) * 100))}` : ""; };
  ligarFaturar("l", "#l_btn", null, "Emitir selecionadas", "Gerar cobranças selecionadas", "Lançar selecionadas");
  $("#l_serv").onchange = () => { $("#l_desc").value = $("#l_serv").value ? servDe($("#l_serv").value).descricao || "" : ""; };
  $("#l_f").oninput = desenhar; desenhar();
  $("#l_btn").onclick = async () => {
    const itens = sel(); if (!itens.length) return aviso("Marque ao menos um cliente.");
    if (itens.some(i => !valorNum(i.valor))) return aviso("Há cliente marcado sem valor.");
    if (!confirm(`${itens.length} cliente(s) — ${nomeCanal()}\nNota fiscal: regra de cada cliente (geral: ${nomeRegra(ST.regra_geral)})\n${ST.producao ? "Notas com validade fiscal" : "Teste em homologação"}\n${$("#l_tot").textContent}`)) return;
    $("#l_btn").disabled = true; $("#l_res").innerHTML = '<div class="msg">Enviando, aguarde…</div>';
    try { const r = await api("lote", { itens }); $("#l_res").innerHTML = `<div class="msg"><b>${r.filter(x => x.sucesso).length} de ${r.length} emitida(s).</b></div>` + r.map(linhaRes).join(""); }
    finally { $("#l_btn").disabled = false; }
  };
};

// ---------------------------------------------------------------- notas fiscais emitidas
let PREENCHER = null;
const FILTRO_NF = { competencia: null, situacao: "validas", busca: "", servico_id: "" };
PAGINAS.notas = async el => {
  if (FILTRO_NF.competencia === null) FILTRO_NF.competencia = hojeISO().slice(0, 7);
  el.innerHTML = `<h1>Notas fiscais (NFS-e) <span class="acoes"><button class="btn" onclick="ir('emitir')">${ic("mais")}Emitir nota</button></span></h1>
  <div class="kpis" id="nf_kpis"></div>
  <div class="card"><div class="barra filtros-nf">
    <label>Competência<input type="month" id="nf_comp" value="${FILTRO_NF.competencia}"></label>
    <label>Situação<select id="nf_sit">${[["validas", "Emitidas e canceladas"], ["emitida", "Só emitidas"], ["cancelada", "Só canceladas"], ["teste", "Testes de homologação"], ["todas", "Todas"]].map(([v, t]) => `<option value="${v}" ${FILTRO_NF.situacao == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${(ST.servicos || []).length > 1 ? `<label>Serviço<select id="nf_serv">${opcoesServ(FILTRO_NF.servico_id, "Todos")}</select></label>` : ""}
    <label style="flex:1">Procurar<input id="nf_busca" placeholder="cliente, CNPJ ou nº da nota" value="${esc(FILTRO_NF.busca)}"></label>
    <button class="btn sec" id="nf_todas" title="Mostrar todas as competências">Todas as competências</button></div>
    <div id="nf_tab"><div class="vazio">Carregando…</div></div></div>`;
  let tmr;
  const carregar = async () => {
    const r = await api("nfse/listar", FILTRO_NF);
    $("#nf_kpis").innerHTML = `<div class="kpi"><div class="r">Notas emitidas ${FILTRO_NF.competencia ? "em " + mes(FILTRO_NF.competencia) : "(todas as competências)"}</div><div class="v">${r.qtd}</div></div>
      <div class="kpi"><div class="r">Valor das notas emitidas</div><div class="v">${brl(r.total_cent)}</div></div>
      <div class="kpi"><div class="r">Canceladas</div><div class="v">${r.canceladas}</div></div>`;
    $("#nf_tab").innerHTML = tabela([
      { t: "Nº NFS-e", f: n => `<b>${esc(n.nfse_numero)}</b>${n.nfse_link && n.nfse_link.startsWith("http") ? `<div class="sub"><a href="${esc(n.nfse_link)}" target="_blank">abrir nota</a></div>` : ""}` },
      { t: "Emissão", f: n => `<span class="nw">${dt(n.data)}</span><div class="sub nw">comp. ${mes(n.competencia)}</div>` },
      { t: "Cliente", f: n => celNome(n.cliente_nome, `${fmtDoc(n.cpf_cnpj)} · ${esc(frase(n.descricao))}`) },
      { t: "Valor", n: 1, f: n => num(n.valor_cent) },
      { t: "Situação", fsel: 1, fv: n => textoDe(n.nfse_status == "emitida" ? selo("emitida") : n.nfse_status == "cancelada" ? selo("nf_cancelada") : selo("teste")), f: n => n.nfse_status == "emitida" ? selo("emitida") : n.nfse_status == "cancelada" ? selo("nf_cancelada") : selo("teste") },
      { t: "Origem", fsel: 1, f: n => `<span class="sub nw">${n.origem == "importado" ? "importada (XML)" : n.nfse_canal == "nacional" ? "Nacional" : "Itaboraí"}</span>` },
      { t: "", f: n => `<div class="acoes-linha"><button class="btn min sec" data-cp="${n.id}" title="Abre Emitir nota com os dados desta nota">${ic("copiar")}Copiar</button>` + (n.pode_cancelar ? `${n.nfse_canal == "nacional" && n.nfse_chave ? `<button class="btn min sec" data-sb="${n.id}" title="Emite uma nova nota que substitui esta">Substituir</button>` : ""}<button class="btn min sec ico perigo-txt" data-cn="${n.id}" title="Cancelar esta NFS-e" aria-label="Cancelar esta NFS-e">${ic("x")}</button>` : n.nfse_status == "emitida" && n.origem == "importado" ? '<span class="sub nw" title="Emitida fora do sistema">cancelar no portal</span>' : "") + "</div>" }],
      r.notas, FILTRO_NF.competencia ? `Nenhuma nota em ${mes(FILTRO_NF.competencia)} com esses filtros.` : "Nenhuma nota com esses filtros.",
      { filtros: "notas", soma: n => n.valor_cent });
    $$("[data-cn]", el).forEach(b => b.onclick = () => cancelarNota(r.notas.find(n => n.id == b.dataset.cn)));
    $$("[data-cp]", el).forEach(b => b.onclick = () => { PREENCHER = { copiar: Number(b.dataset.cp) }; ir("emitir"); });
    $$("[data-sb]", el).forEach(b => b.onclick = () => { const n = r.notas.find(x => x.id == b.dataset.sb);
      PREENCHER = { doc: n.cpf_cnpj, valor: num(n.valor_cent), desc: n.descricao, servico_id: n.servico_id, subst_chave: n.nfse_chave }; ir("emitir"); });
  };
  $("#nf_comp").onchange = () => { FILTRO_NF.competencia = $("#nf_comp").value; carregar(); };
  $("#nf_sit").onchange = () => { FILTRO_NF.situacao = $("#nf_sit").value; carregar(); };
  if ($("#nf_serv")) $("#nf_serv").onchange = () => { FILTRO_NF.servico_id = $("#nf_serv").value; carregar(); };
  $("#nf_busca").oninput = () => { clearTimeout(tmr); tmr = setTimeout(() => { FILTRO_NF.busca = $("#nf_busca").value.trim(); carregar(); }, 250); };
  $("#nf_todas").onclick = () => { FILTRO_NF.competencia = ""; $("#nf_comp").value = ""; carregar(); };
  carregar();
};
function cancelarNota(n) {
  modal(`<h2>Cancelar NFS-e nº ${esc(n.nfse_numero)}</h2>
    <p><b>${esc(n.cliente_nome)}</b> — ${brl(n.valor_cent)} — competência ${mes(n.competencia)}</p>
    <div class="msg erro">O cancelamento é enviado ${n.nfse_canal == "nacional" ? "ao Emissor Nacional (Sefin)" : "à Prefeitura de Itaboraí"} e <b>não pode ser desfeito</b>. A conta a receber desta nota também é cancelada (e o boleto, se houver).</div>
    <div class="campos"><label class="inteiro">Justificativa (mínimo 15 caracteres)<textarea id="cn_just" rows="3" maxlength="255" placeholder="ex.: Nota emitida com valor incorreto"></textarea></label></div>
    <p class="sub" id="cn_cont">0 de 15 caracteres</p>
    <p><button class="btn perigo" id="cn_ok" disabled>${ic("x")}Cancelar a nota fiscal</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#cn_just").oninput = () => { const k = $("#cn_just").value.trim().length; $("#cn_cont").textContent = `${k} de 15 caracteres`; $("#cn_ok").disabled = k < 15; };
  $("#cn_ok").onclick = async () => {
    if (!confirm(`Confirma o CANCELAMENTO da NFS-e ${n.nfse_numero}?`)) return;
    $("#cn_ok").disabled = true; $("#cn_ok").textContent = "Enviando…";
    const r = await api("titulo/cancelar_nfse", { id: n.id, justificativa: $("#cn_just").value.trim() });
    if (r.sucesso) { fechar(); aviso(`NFS-e ${n.nfse_numero} cancelada ✔`, 7000); ir("notas"); }
    else { $("#cn_ok").disabled = false; $("#cn_ok").innerHTML = `${ic("x")}Cancelar a nota fiscal`; aviso("A nota NÃO foi cancelada: " + (r.erros || []).join("; "), 12000); }
  };
}

// ---------------------------------------------------------------- assistente de validação
const SIT_VAL = { ok: ["bom", "Aprovado"], alerta: ["alerta", "Aprovado com ressalva"], erro: ["critico", "Falhou"], pulado: ["neutro", "Não configurado"] };
PAGINAS.validacao = async el => {
  const r = await api("validacao");
  const cliPadrao = (r.clientes[0] || {}).cpf_cnpj || "";
  el.innerHTML = `<h1>Validação com credenciais reais <span class="acoes"><button class="btn" id="val_todos">${ic("play")}Testar tudo</button></span></h1>
  <div class="msg">Cada teste usa as credenciais verdadeiras desta empresa. <b>Nenhuma nota vale de verdade:</b> as emissões saem em
  <b>homologação</b> (Itaboraí) ou na <b>Produção Restrita</b> (Nacional) e são canceladas em seguida, sem usar a numeração real.
  O boleto de teste só é criado no <b>sandbox</b> do Inter. ${r.concluidos} de ${r.total} testes aprovados.</div>
  <div class="card"><div class="campos">
    <label>Cliente usado nas notas de teste<select id="val_cli">${r.clientes.map(c => `<option value="${esc(c.cpf_cnpj)}">${esc(c.razao_social)} — ${fmtDoc(c.cpf_cnpj)}</option>`).join("")}</select></label>
    <label>E-mail que recebe o teste<input id="val_para" type="email" placeholder="vazio = o usuário do SMTP" value="${esc(((ST.config || {}).smtp || {}).usuario || "")}"></label>
  </div></div>
  <div class="val-lista">${r.passos.map(p => { const u = p.ultimo; const [c, t] = u ? SIT_VAL[u.situacao] || ["neutro", u.situacao] : ["neutro", "Ainda não testado"];
    return `<div class="card val-passo" data-passo="${p.id}"><div class="val-topo"><div><h2>${esc(p.titulo)}</h2><p class="sub">${esc(p.descricao)}</p></div>
      <div class="val-acao"><span class="selo ${c}">${t}</span><button class="btn sec" data-rodar="${p.id}">${ic("play")}Testar</button></div></div>
      <div class="val-res">${u ? `<p><b>${esc(u.mensagem)}</b> <span class="sub">— ${esc(u.quando.slice(8, 10) + "/" + u.quando.slice(5, 7) + "/" + u.quando.slice(0, 4) + " " + u.quando.slice(11, 16))}</span></p>${u.detalhes.length ? `<ul class="sub">${u.detalhes.map(d => `<li>${esc(d)}</li>`).join("")}</ul>` : ""}` : ""}</div></div>`; }).join("")}</div>`;
  if (cliPadrao) $("#val_cli").value = cliPadrao;
  const rodar = async id => {
    const b = $(`[data-rodar="${id}"]`, el); b.disabled = true; b.textContent = "Testando…";
    try { await api("validacao/rodar", { passo: id, cpf_cnpj: $("#val_cli").value, para: $("#val_para").value.trim() }); }
    catch (e) { /* o erro já foi avisado */ }
  };
  $$("[data-rodar]", el).forEach(b => b.onclick = async () => { await rodar(b.dataset.rodar); ir("validacao"); });
  $("#val_todos").onclick = async () => {
    if (!confirm("Rodar todos os testes? Serão emitidas e canceladas notas de TESTE (homologação/Produção Restrita) e enviado um e-mail de teste.")) return;
    $("#val_todos").disabled = true;
    for (const p of r.passos) await rodar(p.id);
    ir("validacao");
  };
};
