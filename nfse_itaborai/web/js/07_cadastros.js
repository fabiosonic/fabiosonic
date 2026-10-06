// Clientes e serviços.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- clientes
PAGINAS.clientes = async el => {
  el.innerHTML = `<h1>Clientes <span class="acoes"><button class="btn sec" id="imp_cont">${ic("download")}Importar e-mails e WhatsApp (CSV)</button><button class="btn" id="imp_xml">${ic("download")}Importar clientes dos XML</button></span></h1><div id="imp_area"></div><div class="card"><div class="card-cab"><h2 id="c_tit">${ic("clientes")}Novo cliente</h2><span class="sub">endereço completo é exigido na NFS-e e no boleto</span></div><div class="barra"><label data-br>CNPJ / CPF<input id="c_doc" placeholder="só números"></label>
      <label class="chk"><input type="checkbox" id="c_ext"> Cliente do exterior <span class="sub">(sem CPF/CNPJ — exportação de serviço)</span></label></div>
    <div class="campos" id="fcli"><label class="inteiro">Razão social / nome<input name="razao_social"></label>
    <label data-ex hidden>País<select id="ce_pais"><option value="">Escolha…</option>${Object.entries(ST.paises || {}).map(([k, v]) => `<option value="${k}">${esc(v[0])} (${k})</option>`).join("")}<option value="outro">Outro país…</option></select></label>
    <label data-ex hidden data-outro>Sigla ISO do país<input id="ce_iso" maxlength="2" placeholder="ex.: NZ"></label>
    <label data-ex hidden data-outro>Código BACEN do país<input id="ce_bacen" maxlength="4" inputmode="numeric" placeholder="4 dígitos"></label>
    <label data-ex hidden>NIF (identificação fiscal no país)<input id="ce_nif" maxlength="40"></label>
    <label data-ex hidden>Sem NIF? Motivo<select id="ce_sem"><option value="">Tem NIF</option><option value="1">Dispensado do NIF</option><option value="2">País não exige NIF</option></select></label>
    <label data-ex hidden>Pessoa<select id="ce_pessoa"><option value="1">Jurídica (empresa)</option><option value="2">Física</option></select></label>
    <h3 class="bloco">Endereço</h3><label>Tipo logradouro<input name="tipo_logradouro" placeholder="RUA"></label><label>Logradouro<input name="logradouro"></label><label>Número<input name="numero"></label>
    <label>Complemento<input name="complemento"></label><label>Bairro<input name="bairro"></label><label data-br>CEP<input name="cep"></label>
    <label data-ex hidden>Cidade (exterior)<input id="ce_cidade" maxlength="55"></label><label data-ex hidden>Estado / província<input id="ce_estado" maxlength="60"></label><label data-ex hidden>Código postal<input id="ce_postal" maxlength="11"></label>
    <label data-br>Cidade<input name="cidade" placeholder="automática pelo cód. IBGE"></label><label data-br>Cód. IBGE município<input name="codigo_municipio"></label><label data-br>UF<input name="uf" maxlength="2"></label>
    <label data-br>Inscrição municipal<input name="inscricao_municipal"></label><h3 class="bloco">Contato e cobrança</h3><label>E-mail principal (vai na NFS-e e no boleto)<input name="email"></label><label>Telefone / WhatsApp principal<input name="telefone"></label>
    <label style="grid-column:span 2">Outros e-mails que recebem as mensagens<input name="emails_extras" placeholder="financeiro@cliente.com; socio@cliente.com"></label><label style="grid-column:span 2">Outros WhatsApp que recebem as mensagens<input name="whatsapps_extras" placeholder="(21) 99999-0000; (21) 98888-0000"></label>
    <p class="sub inteiro" style="margin:-4px 0 4px">Cobranças, boletos, notas fiscais e avisos vão para <b>todos</b> os e-mails (numa mesma mensagem) e para <b>todos</b> os WhatsApp cadastrados. Separe por ponto e vírgula.</p>
    <label class="chk inteiro"><input type="checkbox" id="c_wa"> <b>Enviar cobrança por WhatsApp</b> <span class="sub">— para clientes que já conversam com o escritório pelo WhatsApp</span></label>
    <h3 class="bloco">Emissão</h3><label class="inteiro">Serviço habitual (vem selecionado ao emitir)<select name="servico_id">${opcoesServ("", "Padrão da empresa")}</select></label></div>
    ${blocoFiscal("cf")}
    ${blocoFixos()}
    <p><button class="btn" id="sc">Salvar cliente</button> <button class="btn sec" id="lc">Novo</button></p></div>
    <div class="card"><div class="barra"><label style="flex:1">Procurar<input id="c_f" placeholder="nome ou CNPJ"></label></div><div id="c_tab"></div></div>`;
  const END = ["tipo_logradouro", "logradouro", "numero", "complemento", "bairro", "cep", "cidade", "codigo_municipio", "uf"];
  let chaveExt = "";
  const modoExt = () => { const ext = $("#c_ext").checked, outro = $("#ce_pais").value == "outro";
    $$("[data-ex]", el).forEach(l => l.hidden = !ext || (l.hasAttribute("data-outro") && !outro)); $$("[data-br]", el).forEach(l => l.hidden = ext); };
  const preencher = c => { $("#c_tit").innerHTML = `${ic("clientes")}${c.cpf_cnpj ? "Editar cliente: " + esc(nomeCli(c.razao_social)) : "Novo cliente"}`; preencherFiscal("cf", c.fiscal); preencherNota($("#cf_nx"), c.padroes_nota || {}); atuFixos(); $("#c_doc").value = c.estrangeiro ? "" : c.cpf_cnpj || ""; $$("#fcli [name]").forEach(i => i.value = (END.includes(i.name) ? (c.endereco || {})[i.name] : c[i.name]) || "");
    const x = c.estrangeiro || {}; chaveExt = c.estrangeiro ? c.cpf_cnpj : ""; $("#c_ext").checked = !!c.estrangeiro;
    $("#ce_pais").value = x.pais_iso ? ((ST.paises || {})[x.pais_iso] ? x.pais_iso : "outro") : ""; $("#ce_iso").value = x.pais_iso || ""; $("#ce_bacen").value = x.pais_bacen || "";
    $("#ce_nif").value = x.nif || ""; $("#ce_sem").value = x.sem_nif || ""; $("#ce_pessoa").value = x.pessoa || "1";
    $("#ce_cidade").value = x.cidade || ""; $("#ce_estado").value = x.estado || ""; $("#ce_postal").value = x.cod_postal || ""; modoExt();
    $("#c_wa").checked = !!c.whatsapp_cobranca;
    $("#fcli [name=emails_extras]").value = (c.emails_extras || []).join("; "); $("#fcli [name=whatsapps_extras]").value = (c.whatsapps_extras || []).map(fone).join("; "); };
  $("#c_ext").onchange = modoExt; $("#ce_pais").onchange = modoExt;
  const desenhar = () => { const f = $("#c_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#c_tab").innerHTML = `<p class="sub">${ST.clientes.length} cliente(s). Sem e-mail ou telefone o cliente não recebe a régua de cobrança.</p>` + tabela([{ t: "Cliente", f: c => celNome(c.razao_social, fmtDoc(c.cpf_cnpj)) },
      { t: "Contato", fv: c => [c.email, c.telefone, ...(c.emails_extras || []), ...(c.whatsapps_extras || [])].filter(Boolean).join(" ") || "sem contato", f: c => { const em = [c.email, ...(c.emails_extras || [])].filter(Boolean), wa = [c.telefone, ...(c.whatsapps_extras || [])].filter(Boolean);
        return (em.length ? `<span title="${esc(em.join("\n"))}">${ic("email")}${em.length > 1 ? `<small>${em.length}</small>` : ""}</span> ` : "") + (wa.length ? `<span title="${esc(wa.join("\n"))}">${ic("fone")}${wa.length > 1 ? `<small>${wa.length}</small>` : ""}</span>` : "") || '<span class="sub">sem contato</span>'; } },
      { t: "Cobrar por WhatsApp", fsel: 1, fv: c => !c.telefone ? "sem telefone" : c.whatsapp_cobranca ? "sim" : "não", f: c => c.telefone ? `<label class="chk" title="Entra na fila de WhatsApp da régua"><input type="checkbox" data-wa="${c.cpf_cnpj}" ${c.whatsapp_cobranca ? "checked" : ""}> sim</label>` : '<span class="sub">sem telefone</span>' }, { t: "Última nota", f: c => c.ultimo_valor ? `${dt(c.ultima_data)} · ${Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "" },
      { t: "", f: c => `<button class="btn min sec" data-ed="${c.cpf_cnpj}">Editar</button> <button class="btn min sec" data-ex="${c.cpf_cnpj}" title="Excluir">${ic("x")}</button>` }],
      ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)), "Nada por aqui.", { filtros: "clientes" });
    $$("[data-ed]").forEach(b => b.onclick = () => { preencher(ST.clientes.find(c => c.cpf_cnpj == b.dataset.ed)); scrollTo(0, 0); });
    $$("[data-wa]").forEach(b => b.onchange = async () => { await api("cliente/whatsapp", { cpf_cnpj: b.dataset.wa, ativo: b.checked });
      const c = ST.clientes.find(x => x.cpf_cnpj == b.dataset.wa); if (c) c.whatsapp_cobranca = b.checked;
      aviso(b.checked ? "Cliente vai receber a cobrança por WhatsApp ✔" : "Cliente fora da cobrança por WhatsApp"); });
    $$("[data-ex]").forEach(b => b.onclick = async () => { if (confirm("Excluir do cadastro?")) { await api("cliente/excluir", { cpf_cnpj: b.dataset.ex }); await carregarEstado(); desenhar(); } }); };
  $("#c_f").oninput = desenhar; desenhar();
  $("#lc").onclick = () => preencher({});
  $("#imp_cont").onclick = importarContatos;
  $("#imp_xml").onclick = () => importarXml($("#imp_area"));
  ligarFiscal("cf");
  const atuFixos = ligarNota($("#cf_nx"), () => (servDe($("#fcli [name=servico_id]").value) || {}).item_lista_servico || "");
  $("#sc").onclick = async () => { const f = form($("#fcli")), e = {}; END.forEach(k => { e[k] = f[k]; delete f[k]; });
    const ext = $("#c_ext").checked, pais = $("#ce_pais").value;
    const estrangeiro = ext ? { pais_iso: pais == "outro" ? $("#ce_iso").value.trim() : pais, pais_bacen: pais == "outro" ? $("#ce_bacen").value.trim() : "",
      nif: $("#ce_nif").value.trim(), sem_nif: $("#ce_sem").value, pessoa: $("#ce_pessoa").value, cidade: $("#ce_cidade").value.trim(),
      estado: $("#ce_estado").value.trim(), cod_postal: $("#ce_postal").value.trim() } : null;
    const r = await api("cliente/salvar", { ...f, cpf_cnpj: ext ? chaveExt : $("#c_doc").value, endereco: e, fiscal: lerFiscal("cf"), padroes_nota: lerNota($("#cf_nx")), whatsapp_cobranca: $("#c_wa").checked, ...(estrangeiro ? { estrangeiro } : {}) });
    if (ext) chaveExt = r.cpf_cnpj; aviso("Cliente salvo ✔"); await carregarEstado(); desenhar(); };
};

async function importarXml(area) {
  area.innerHTML = '<div class="card"><div class="vazio">Lendo a pasta IMPORTAR XML…</div></div>';
  const a = await api("importador/analisar");
  const rot = { descricao: "Descrição", item_lista_servico: "Item LC 116", codigo_desdobro: "Desdobro", codigo_nbs: "NBS", cnae: "CNAE",
    aliquota_iss: "Alíquota ISS (%)", tipo_tributacao: "Tipo de tributação", iss_retido: "ISS retido (1/2)", indicador_operacao: "IBS/CBS cIndOp", classificacao_tributaria: "IBS/CBS cClassTrib",
    codigo_tributacao_municipio: "Código tributação municipal", ibpt_percentual: "Carga tributária aprox. (%)", codigo_interno: "Código interno" };
  const opcoes = sel => a.empresas.map(e => `<option value="${esc(e.id)}" ${e.id == sel ? "selected" : ""}>${esc(e.nome)} — ${fmtDoc(e.cnpj)}</option>`).join("");
  area.innerHTML = `<div class="card"><h2>${ic("download")}Importar clientes dos XML</h2>
    <p class="sub">Coloque os XML (ou ZIP) das notas emitidas na pasta <b>${esc(a.pasta)}</b>, de qualquer empresa. Cada nota é ligada à empresa que a emitiu (CNPJ do prestador): os clientes de uma empresa nunca vão para outra. Depois de importados, os arquivos ficam guardados em “importados”, separados por empresa. O robô também importa sozinho as notas novas que você colocar na pasta.</p>
    <p><button class="btn sec" onclick="api('importador/abrir_pasta')">${ic("download")}Abrir a pasta</button> <button class="btn sec" id="imp_reler">Ler a pasta de novo</button></p>
    ${a.grupos.length ? "" : '<div class="vazio">Nenhum XML novo na pasta.</div>'}
    ${a.grupos.map((g, j) => `<div class="imp-grupo" data-j="${j}"><div class="imp-cab"><div><b>${esc(g.nome || "Prestador sem nome")}</b><span class="sub">CNPJ ${fmtDoc(g.cnpj)} · ${g.notas} nota(s) · ${g.clientes} cliente(s), ${g.clientes_novos} novo(s)</span>
        ${g.fiscal ? `<span class="sub">Lido das notas: ${g.fiscal.regime ? "regime <b>" + esc(g.fiscal.regime) + "</b>" : "regime não identificado"}${g.fiscal.tomadores_especiais ? ` · ${g.fiscal.tomadores_especiais} tomador(es) com regra própria (ISS retido, retenções, órgão público…)` : ""}${g.fiscal.ibscbs ? " · notas com IBS/CBS" : ""}</span>` : ""}</div>
      ${g.empresa_id ? `<label>Cadastrar os clientes na empresa<select class="imp-emp">${opcoes(g.empresa_id)}</select></label>` : `<div class="msg erro">Nenhuma empresa cadastrada com este CNPJ. <a href="#" class="imp-nova">Cadastrar esta empresa</a> e depois leia a pasta de novo.</div>`}</div>
      ${g.empresa_id ? `<details class="imp-padroes" open><summary><b>${(g.servicos || []).length} serviço(s) / atividade(s) encontrados nas notas</b> — marque os que devem ficar cadastrados para emitir</summary>
        ${(g.servicos || []).map((sv, k) => `<div class="imp-serv" data-k="${k}"><div class="imp-serv-cab"><label class="chk"><input type="checkbox" class="imp-sv-usar" ${sv.existente_id ? "" : "checked"}> Cadastrar</label>
          <label>Nome da atividade<input class="imp-sv-nome" value="${esc(sv.nome)}" maxlength="60"></label>
          <label class="chk"><input type="radio" name="imp_pad_${j}" class="imp-sv-pad" ${k == 0 && !(g.servicos || []).some(x => x.existente_id) ? "checked" : ""}> Tornar padrão</label>
          <span class="sub">${sv.notas} nota(s)${sv.existente_id ? " · já cadastrado (completa só o que faltar)" : ""}</span></div>
          <div class="campos">${Object.entries(rot).map(([c, t]) => `<label class="${c == "descricao" ? "inteiro" : ""}">${t}<input data-pad="${c}" value="${esc(sv.campos[c] || "")}"></label>`).join("")}</div></div>`).join("")}
        <p class="sub">Códigos detectados nas notas (valor mais frequente de cada atividade). Confira com o cadastro municipal antes de emitir. Cada cliente fica ligado à atividade que mais aparece nas notas dele.</p></details>
        <p><button class="btn imp-ok">${ic("ok")}Importar ${g.clientes} cliente(s)</button></p>` : ""}</div>`).join("")}</div>`;
  $("#imp_reler").onclick = () => importarXml(area);
  $$(".imp-grupo", area).forEach(div => { const g = a.grupos[div.dataset.j], b = $(".imp-ok", div), nv = $(".imp-nova", div);
    if (nv) nv.onclick = e => { e.preventDefault(); trocarEmpresa({ nome: g.nome, cnpj: g.cnpj }); };
    if (!b) return;
    b.onclick = async () => {
      const servicos = $$(".imp-serv", div).filter(x => $(".imp-sv-usar", x).checked).map(x => {
        const campos = {}; $$("[data-pad]", x).forEach(i => campos[i.dataset.pad] = i.value.trim());
        return { nome: $(".imp-sv-nome", x).value.trim(), campos, padrao: $(".imp-sv-pad", x).checked }; });
      const r = await api("importador/importar", { empresa_id: $(".imp-emp", div).value, cnpj: g.cnpj, servicos });
      if (r.erro) return;
      aviso(`${r.empresa}: ${r.xml} XML importado(s), ${r.clientes_novos} cliente(s) novo(s)${r.servicos ? ` · ${r.servicos} serviço(s) cadastrado(s)` : ""}${r.clientes_com_servico ? ` · ${r.clientes_com_servico} cliente(s) ligados ao serviço habitual` : ""}${(r.regra_geral || []).length ? " · regra geral completada pelas notas (" + r.regra_geral.length + " campo(s))" : ""}${r.regras_tomadores ? ` · ${r.regras_tomadores} tomador(es) com regra fiscal própria` : ""}${(r.empresa_completada || []).length ? " · empresa completada: " + r.empresa_completada.join("; ") : ""} ✔`, 15000);
      await carregarEstado(); ir("clientes"); }; });
}

async function mostrarMigracao(alvo, sempre) {
  let l; try { l = await api("migracao/procurar"); } catch (e) { return; }
  if (!alvo) return;
  if (!l.length) { if (sempre) alvo.innerHTML = '<div class="msg">Nenhuma versão anterior com dados foi encontrada nas pastas Downloads, Documentos e Área de Trabalho.</div>'; return; }
  alvo.innerHTML = l.map((v, j) => `<div class="card migra"><h2>${ic("download")}Versão anterior encontrada</h2>
    <p class="sub">Em <b>${esc(v.pasta)}</b> há: ${Object.keys(v.itens).map(esc).join(" · ")}. Copio para cá só o que ainda está vazio nesta versão; a pasta antiga não é alterada. ${v.ambiente_producao ? "A versão antiga estava em produção: confirme a produção aqui pelo botão do ambiente." : ""}</p>
    <button class="btn" data-j="${j}">${ic("ok")}Trazer para esta versão</button></div>`).join("");
  $$(".migra .btn", alvo).forEach(b => b.onclick = async () => {
    const r = await api("migracao/importar", { pasta: l[b.dataset.j].pasta });
    aviso(r.importado.length ? "Trazido da versão anterior: " + r.importado.join(", ") : "Nada novo para trazer.", 9000);
    await carregarEstado(); ir(PAG); });
}

// ---------------------------------------------------------------- serviços (atividades)
function tabelaServicos() {
  return tabela([{ t: "Serviço", f: s => `<b>${esc(s.nome)}</b>${s.padrao ? " " + selo("bom").replace("Bom", "Padrão") : ""}<div class="sub">${esc(s.descricao)}</div>` },
    { t: "Item LC 116", f: s => esc(s.item_lista_servico) }, { t: "Desdobro / NBS", f: s => `${esc(s.codigo_desdobro || "—")} / ${esc(s.codigo_nbs || "—")}` },
    { t: "ISS", n: 1, f: s => s.aliquota_iss ? esc(s.aliquota_iss) + "%" : "—" },
    { t: "", f: s => `<div class="acoes-linha"><button class="btn min sec" type="button" data-sv-ed="${esc(s.id)}">Editar</button>${s.padrao ? "" : ` <button class="btn min sec" type="button" data-sv-pd="${esc(s.id)}">Tornar padrão</button> <button class="btn min sec" type="button" data-sv-ex="${esc(s.id)}" title="Excluir">${ic("x")}</button>`}</div>` }],
    ST.servicos || [], "Nenhum serviço cadastrado.");
}
async function recarregarServicos() {
  await carregarEstado(); const l = $("#lista_serv"); if (!l) return;
  l.innerHTML = tabelaServicos(); ligarServicos();
}
function ligarServicos() {
  $$("[data-sv-ed]").forEach(b => b.onclick = () => editarServico(servDe(b.dataset.svEd)));
  $$("[data-sv-pd]").forEach(b => b.onclick = async () => { const r = await api("servico/salvar", { ...servDe(b.dataset.svPd), padrao: true }); if (r.erro) return; aviso("Serviço padrão alterado ✔"); recarregarServicos(); });
  $$("[data-sv-ex]").forEach(b => b.onclick = async () => { if (!confirm(`Excluir o serviço ${servDe(b.dataset.svEx).nome}? Clientes e contratos que usavam ele passam a usar o padrão.`)) return;
    const r = await api("servico/excluir", { id: b.dataset.svEx }); if (r.erro) return; aviso("Serviço excluído ✔"); recarregarServicos(); });
}
function editarServico(s) {
  const base = s.id ? s : { ibpt_percentual: servPadrao().ibpt_percentual || "", tipo_tributacao: servPadrao().tipo_tributacao || "", iss_retido: servPadrao().iss_retido || "2",
    indicador_operacao: servPadrao().indicador_operacao || "", classificacao_tributaria: servPadrao().classificacao_tributaria || "", cnae: servPadrao().cnae || "" };
  const f = (k, t, extra = "") => `<label>${t}<input name="${k}" value="${esc(base[k] ?? "")}" ${extra}></label>`;
  modal(`<h2>${s.id ? "Editar serviço" : "Novo serviço"}</h2><div class="campos" id="fsv">
    ${f("nome", "Nome da atividade", 'placeholder="ex.: Consultoria" maxlength="60"')}<label class="chk"><input type="checkbox" name="padrao" ${s.padrao ? "checked" : ""}> Serviço padrão da empresa</label>
    <label class="inteiro">Descrição que vai na nota<input name="descricao" maxlength="190" value="${esc(base.descricao || "")}"></label>
    ${f("item_lista_servico", "Item LC 116 (ex.: 17.19)")}${f("codigo_desdobro", "Desdobro nacional (6 dígitos)")}${f("codigo_nbs", "NBS (9 dígitos)")}${f("codigo_tributacao_municipio", "Código de tributação municipal", 'maxlength="9" placeholder="se o município exigir"')}${f("cnae", "CNAE")}
    ${f("aliquota_iss", "Alíquota ISS (%)")}${f("tipo_tributacao", "Tipo de tributação (4 = Simples)")}${f("iss_retido", "ISS retido (1 sim / 2 não)")}${f("indicador_operacao", "IBS/CBS: cIndOp")}${f("classificacao_tributaria", "IBS/CBS: cClassTrib")}${f("ibpt_percentual", "Carga tributária IBPT (%)")}${f("codigo_interno", "Código interno (opcional)", 'maxlength="20" placeholder="só letras e números"')}
    <label class="inteiro">Observações na nota<input name="observacoes" value="${esc(base.observacoes || "")}"></label></div>
    <p class="sub">Confira os códigos com o cadastro municipal da empresa e a Tabela IBS x CBS. Item, NBS e alíquota errados geram rejeição da nota.</p>
    <p><button class="btn" id="ok">Salvar serviço</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const d = form($("#fsv")); if (s.id) d.id = s.id; if (s.padrao) d.padrao = true;
    if (!d.nome.trim()) return aviso("Dê um nome ao serviço (ex.: Consultoria).");
    const r = await api("servico/salvar", d); if (r.erro) return; fechar(); aviso("Serviço salvo ✔"); recarregarServicos(); };
}

// ---------------------------------------------------------------- contatos (e-mail e WhatsApp) da planilha do escritório
function importarContatos() {
  modal(`<h2>Importar e-mails e WhatsApp dos clientes</h2>
    <p class="sub">Escolha a planilha de contatos (CSV separado por ponto e vírgula, com as colunas <b>CPF/CNPJ</b>, <b>Celular</b> e <b>E-mail</b>
    — ou a exportação de contatos com Departamentos, da qual entra o contato do <b>Financeiro</b>). Só clientes <b>já cadastrados</b> são
    atualizados; como WhatsApp, só celular; e-mails provisórios ("aguardando@…") e do próprio escritório são ignorados.
    Nada é gravado antes da sua conferência.</p>
    <label class="soltar"><input type="file" id="ct_csv" accept=".csv,text/csv" hidden>${ic("download")}<span><b>Escolher a planilha (.csv)</b><small>empresas_contatos.csv</small></span></label>
    <div id="ct_res"></div>`, true);
  $("#ct_csv").onchange = e => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = async () => {
      const a = await api("contatos/analisar", { arquivo: r.result });
      const L = a.itens, troca = L.filter(i => (i.email_novo && i.email_atual) || (i.fone_novo && i.fone_atual && !i.fixo)).length;
      const cel = (atual, novo, fmt) => novo ? `${atual ? `<s class="sub">${esc(fmt(atual))}</s><br>` : ""}<b>${esc(fmt(novo))}</b>` : `<span class="sub">${esc(fmt(atual) || "—")}</span>`;
      $("#ct_res").innerHTML = `<p>${a.empresas} empresa(s) no arquivo · <b>${L.length}</b> cliente(s) com e-mail/WhatsApp novo · ${a.sem_mudanca} já estavam iguais
        ${a.fora_do_cadastro.length ? ` · ${a.fora_do_cadastro.length} não estão no cadastro (não são incluídas)` : ""}</p>
        ${L.length ? tabela([{ t: "Cliente", f: i => celNome(i.razao_social, i.contato ? "contato: " + esc(i.contato) : "") },
          { t: "E-mail", f: i => cel(i.email_atual, i.email_novo, x => x) },
          { t: "WhatsApp", f: i => cel(i.fone_atual, i.fone_novo, fone) }], L) : ""}
        ${troca ? `<label class="chk"><input type="checkbox" id="ct_subst"> Substituir também os ${troca} cliente(s) que já têm e-mail/telefone cadastrado (riscados acima)</label>` : ""}
        ${a.fora_do_cadastro.length ? `<details><summary class="sub">Empresas do arquivo que não estão no cadastro</summary><p class="sub">${a.fora_do_cadastro.map(x => esc(x.razao_social) + " (" + fmtDoc(x.cpf_cnpj) + ")").join("; ")}</p></details>` : ""}
        <p><button class="btn" id="ct_ok" ${L.length ? "" : "disabled"}>Gravar os contatos</button> <button class="btn sec" onclick="fechar()">Cancelar</button></p>
        <p class="sub">A cobrança por WhatsApp continua só para os clientes que você marcar em Clientes (coluna WhatsApp).</p>`;
      if ($("#ct_ok")) $("#ct_ok").onclick = async () => { $("#ct_ok").disabled = true;
        const x = await api("contatos/aplicar", { arquivo: r.result, substituir: !!($("#ct_subst") || {}).checked });
        fechar(); aviso(`Contatos gravados ✔ ${x.clientes} cliente(s): ${x.emails} e-mail(s) e ${x.whatsapp} WhatsApp.`, 9000);
        await carregarEstado(); ir("clientes"); };
    };
    r.readAsDataURL(f);
  };
}
