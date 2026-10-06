// Regras fiscais do tomador, campos da nota, faturamento e estado da tela.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- regras fiscais do tomador
// Visibilidade: cada campo declara quando é necessário (data-vis). Tokens separados por espaço = E;
// vírgula = OU. Tokens: regime (mei, simples, presumido, real), ibs (grupo IBS/CBS informado), nacional,
// obra / evento / deducao (pelo item da LC 116 do serviço), campo=valor e campo!=valor (outro campo do bloco).
function ctxFiscal(extra = {}) {
  const c = ST.fiscal_ctx || {};
  return { regime: c.regime || "simples", ibs: !!c.ibscbs, nacional: ST.canal == "nacional", item: "", ...extra };
}
function visivel(expr, ctx, box) {
  const item = String(ctx.item || "").replace(/^0/, "");
  const teste = t => {
    if (t.startsWith("!")) return !teste(t.slice(1));
    const m = t.match(/^([a-z_]+)(!?=)(.*)$/);
    if (m) { const el = box && $(`[data-fz="${m[1]}"],[data-nx="${m[1]}"],[data-k="${m[1]}"]`, box);
      const v = el ? (el.type == "checkbox" ? (el.checked ? "1" : "") : el.value) : "";
      return m[2] == "=" ? v == m[3] : v != m[3]; }
    if (["mei", "simples", "presumido", "real"].includes(t)) return ctx.regime == t;
    if (t == "regular") return ["presumido", "real"].includes(ctx.regime);
    if (t == "ibs") return ctx.ibs;
    if (t == "nacional") return ctx.nacional;
    if (t == "municipal") return !ctx.nacional;
    if (t == "obra") return /^7\./.test(item);
    if (t == "evento") return /^12\./.test(item) || item == "17.10";
    if (t == "deducao") return /^(7|9|12)\./.test(item);
    return true;
  };
  return expr.split(/\s+/).filter(Boolean).every(e => e.split(",").some(teste));
}
function aplicarVis(box, ctx) {
  if (!box) return;
  $$("[data-vis]", box).forEach(el => { el.hidden = !visivel(el.dataset.vis, ctx, box); });
  // grupo sem nenhum campo visível some inteiro
  $$("[data-grupo]", box).forEach(g => { const campos = $$("label", g); g.hidden = g.hidden || (campos.length && campos.every(l => l.hidden)); });
}
const RET_NOMES = [["ret_irrf_pct", "IRRF", "regular"], ["ret_pis_pct", "PIS", "regular"], ["ret_cofins_pct", "COFINS", "regular"],
  ["ret_csll_pct", "CSLL", "regular"], ["ret_inss_pct", "INSS/CP", "simples,regular"]];
function blocoFiscal(p) {
  const L = (vis, html) => `<label data-vis="${vis}">${html}</label>`;
  return `<div class="fiscal-tom" id="${p}_fz">
    <div class="opc-nfse" role="radiogroup" aria-label="Regras fiscais deste tomador"><b>Regras fiscais deste tomador:</b>
      <label class="chk"><input type="radio" name="${p}_fzg" value="1" checked> Usar regra geral</label>
      <label class="chk"><input type="radio" name="${p}_fzg" value="0"> Regra específica deste tomador</label></div>
    <p class="sub" data-fz-resumo></p>
    <div class="campos" data-fz-campos hidden>
      <label class="chk" data-vis="!mei"><input type="checkbox" data-fz="iss_retido"> <b>ISS retido pelo tomador</b></label>
      ${L("simples iss_retido=1", 'Alíquota do ISS retido (%)<input data-fz="aliquota_iss_retido" inputmode="decimal" placeholder="alíquota efetiva do PGDAS">')}
      ${L("!mei iss_retido=1", 'ISS retido por<select data-fz="ret_iss_por"><option value="tomador">Tomador</option><option value="intermediario">Intermediário</option></select>')}
      ${RET_NOMES.map(([k, t, vis]) => L(vis, `Retenção ${t} (%)<input data-fz="${k}" inputmode="decimal" placeholder="0">`)).join("")}
      ${L("regular", 'CST PIS/COFINS próprio<select data-fz="pis_cofins_cst"><option value="">Regra geral</option><option value="01">01 Tributável alíquota básica</option><option value="02">02 Tributável alíquota diferenciada</option><option value="06">06 Alíquota zero</option><option value="07">07 Isenta</option><option value="08">08 Sem incidência</option><option value="09">09 Suspensão</option><option value="49">49 Outras saídas</option><option value="99">99 Outras operações</option></select>')}
      ${L("ibs", 'Consumo pessoal (IBS/CBS)<select data-fz="ind_final"><option value="auto">Automático (CPF = sim)</option><option value="0">Não</option><option value="1">Sim</option></select>')}
      ${L("ibs", 'cClassTrib específico<input data-fz="class_trib" maxlength="6" inputmode="numeric" placeholder="vazio = do serviço">')}
      ${L("ibs", 'Órgão público<select data-fz="tp_ente_gov"><option value="">Não</option><option value="1">União</option><option value="2">Estado</option><option value="3">Distrito Federal</option><option value="4">Município</option></select>')}
      ${L("ibs tp_ente_gov!=", 'Tipo de operação com o órgão<select data-fz="tp_oper"><option value="">Não se aplica</option><option value="1">Fornecimento com pagamento posterior</option><option value="2">Recebimento com fornecimento já realizado</option><option value="3">Fornecimento com pagamento já realizado</option><option value="4">Recebimento com fornecimento posterior</option><option value="5">Fornecimento e pagamento concomitantes</option></select>')}
      <details class="inteiro mais-fz"><summary>Casos especiais do tomador (imunidade, exportação, ISS suspenso, benefício municipal, destinatário diferente)</summary><div class="campos">
        ${L("", 'Situação do ISS<select data-fz="trib_issqn"><option value="1">Operação tributável</option><option value="2">Imunidade</option><option value="3">Exportação de serviço</option><option value="4">Não incidência</option></select>')}
        ${L("trib_issqn=2", 'Tipo de imunidade<select data-fz="tp_imunidade"><option value="1">Patrimônio, renda ou serviços uns dos outros (art. 150, VI, a)</option><option value="2">Templos de qualquer culto (VI, b)</option><option value="3">Partidos, sindicatos, educação e assistência social (VI, c)</option><option value="4">Livros, jornais e periódicos (VI, d)</option><option value="5">Fonogramas e videofonogramas (VI, e)</option><option value="0">Não informado</option></select>')}
        ${L("trib_issqn=3", 'País do resultado (sigla ISO)<input data-fz="pais_result" maxlength="2" placeholder="ex.: US">')}
        ${L("!mei trib_issqn=1", 'Exigibilidade do ISS suspensa<select data-fz="exig_susp_tp"><option value="">Não</option><option value="1">Por decisão judicial</option><option value="2">Por processo administrativo</option></select>')}
        ${L("exig_susp_tp!=", 'Nº do processo (30 dígitos)<input data-fz="exig_susp_proc" maxlength="30" inputmode="numeric">')}
        ${L("!mei trib_issqn=1", 'Benefício municipal (nº de 14 dígitos)<input data-fz="n_bm" maxlength="14" inputmode="numeric" placeholder="opcional">')}
        ${L("n_bm!= v_red_bm=", 'Redução da base pelo benefício (%)<input data-fz="p_red_bm" inputmode="decimal">')}
        ${L("n_bm!= p_red_bm=", 'ou Redução da base em valor (R$)<input data-fz="v_red_bm" inputmode="decimal">')}
        ${L("ibs", 'Destinatário diferente: CPF/CNPJ<input data-fz="dest_doc" inputmode="numeric" placeholder="vazio = o próprio tomador">')}
        ${L("ibs dest_doc!=", 'Destinatário: nome<input data-fz="dest_nome" maxlength="150">')}
      </div></details>
    </div>
    <p class="sub" data-fz-dica hidden>A regra específica fica guardada neste tomador e vale nas próximas notas dele. Os demais seguem a regra geral (Configurações › Regras fiscais). Só aparecem os campos que o regime da empresa (${esc((ST.regimes || {})[(ST.fiscal_ctx || {}).regime] || "")}) exige.</p></div>`;
}
function preencherFiscal(p, f) {
  f = f || { usar_geral: true }; const box = $(`#${p}_fz`); if (!box) return;
  $$(`[name=${p}_fzg]`).forEach(r => r.checked = (r.value == "1") == (f.usar_geral !== false));
  $$("[data-fz]", box).forEach(i => { const v = f[i.dataset.fz];
    if (i.type == "checkbox") i.checked = !!v;
    else if (i.tagName == "SELECT") i.value = v != null && [...i.options].some(o => o.value == v) ? v : i.options[0].value;
    else i.value = v == null || v === "0" ? "" : String(v).replace(".", ","); });
  alternarFiscal(p);
}
function alternarFiscal(p) {
  const box = $(`#${p}_fz`), geral = ($(`[name=${p}_fzg]:checked`) || {}).value != "0";
  $("[data-fz-campos]", box).hidden = geral; $("[data-fz-dica]", box).hidden = geral;
  $("[data-fz-resumo]", box).textContent = geral ? "Regra geral: " + (ST.fiscal_resumo || "") : "";
  aplicarVis(box, ctxFiscal());
}
function ligarFiscal(p, aoMudar) {
  const box = $(`#${p}_fz`);
  $$(`[name=${p}_fzg]`).forEach(r => r.onchange = () => { alternarFiscal(p); aoMudar && aoMudar(); });
  $$("[data-fz]", box).forEach(i => { i.addEventListener("input", () => aplicarVis(box, ctxFiscal())); i.addEventListener("change", () => aplicarVis(box, ctxFiscal())); });
  alternarFiscal(p);
}
const oculto = el => !!el.closest("[hidden]");
function lerFiscal(p) {
  const box = $(`#${p}_fz`), f = { usar_geral: ($(`[name=${p}_fzg]:checked`) || {}).value != "0" };
  if (f.usar_geral) return f;
  // campo que não se aplica ao regime/caso (oculto) é gravado vazio: nada de valor esquecido indo para a nota
  $$("[data-fz]", box).forEach(i => { const esc_ = oculto(i);
    f[i.dataset.fz] = i.type == "checkbox" ? (!esc_ && i.checked) : (esc_ ? "" : i.value.trim().replace(",", ".")); });
  return f;
}
function mesmoFiscal(a, b) {
  const n = f => JSON.stringify(f && f.usar_geral === false ? Object.keys(f).sort().map(k => [k, String(f[k] ?? "").replace(/^0$/, "")]) : "geral");
  return n(a) == n(b);
}
function blocoNota() {
  const c = (k, t, extra = "", vis = "") => `<label${vis ? ` data-vis="${vis}"` : ""}>${t}<input data-nx="${k}" ${extra}></label>`;
  const G = (vis, titulo, corpo) => `<div class="grupo-nx" data-grupo${vis ? ` data-vis="${vis}"` : ""}><h3 class="bloco">${titulo}</h3><div class="campos">${corpo}</div></div>`;
  return `<details class="mais-nota"><summary>${ic("mais")}Mais campos da nota <span class="sub" data-nx-resumo></span></summary>
    ${G("", "Local e código", c("local_prestacao", "Município da prestação (IBGE)", 'inputmode="numeric" maxlength="7" placeholder="vazio = da empresa"') + c("local_recolhimento", "Município do recolhimento do ISS (IBGE)", 'inputmode="numeric" maxlength="7" placeholder="vazio = da empresa"', "local_prestacao!=") + c("c_trib_mun", "Código de tributação municipal", 'maxlength="9" placeholder="se o município exigir"'))}
    ${G("", "Descontos" + '<span data-vis="deducao"> e dedução/redução da base</span>', c("desc_incond", "Desconto incondicionado (R$)", 'inputmode="decimal"') + c("desc_cond", "Desconto condicionado (R$)", 'inputmode="decimal"') + c("ded_valor", "Dedução/redução (R$)", 'inputmode="decimal"', "deducao") + c("ded_pct", "ou Dedução/redução (%)", 'inputmode="decimal"', "deducao")
      + `<div class="inteiro ded-docs" data-vis="nacional deducao ded_valor= ded_pct="><p class="sub">Ou comprove a dedução por documentos (NF-e, NFS-e, recibos) — a soma vira a dedução da base:</p><div data-ded-docs></div><button class="btn min sec" type="button" data-ded-add>${ic("mais")}Adicionar documento</button></div>`)}
    ${G("obra", "Obra (construção civil)", c("obra_cno", "CNO / CEI da obra", 'maxlength="30"') + c("obra_cib", "ou CIB (8 caracteres)", 'maxlength="8"') + c("obra_insc_imob", "Inscrição imobiliária (opcional)", 'maxlength="30"'))}
    ${G("evento", "Evento", c("evento_nome", "Nome do evento", 'maxlength="255"') + c("evento_ini", "Início", 'type="date"') + c("evento_fim", "Fim", 'type="date"') + c("evento_id", "Código do evento (prefeitura)", 'maxlength="30"', "nacional") + c("evento_cep", "CEP do local", 'maxlength="8" inputmode="numeric"', "evento_id=") + c("evento_tipo_lgr", "Tipo (RUA, AV…)", 'maxlength="10"', "municipal") + c("evento_lgr", "Logradouro", "", "evento_id=") + c("evento_nro", "Número", "", "evento_id=") + c("evento_bairro", "Bairro", "", "evento_id=") + c("evento_cpl", "Complemento", "", "municipal"))}
    ${G("", "Pedido e documentos", c("pedido", "Nº do pedido / ordem de compra", 'maxlength="15"') + c("doc_ref", "Documento de referência (contrato, chave…)", 'maxlength="255"') + c("doc_tec", "ART / RRT / DRT", 'maxlength="40"', "obra"))}
    ${G("ibs,municipal", "Imóvel (IBS/CBS — serviços sobre bens imóveis, exceto obra)", c("imovel_cib", "CIB do imóvel", 'maxlength="8"', "nacional") + c("imovel_insc_imob", "Inscrição imobiliária", 'maxlength="30"', "nacional")
      + c("imovel_cep", "CEP do imóvel", 'maxlength="8" inputmode="numeric"', "municipal") + c("imovel_tipo_lgr", "Tipo (RUA, AV…)", 'maxlength="10"', "municipal imovel_cep!=") + c("imovel_lgr", "Logradouro", 'maxlength="80"', "municipal imovel_cep!=")
      + c("imovel_nro", "Número", 'maxlength="6"', "municipal imovel_cep!=") + c("imovel_cpl", "Complemento", 'maxlength="30"', "municipal imovel_cep!=") + c("imovel_bairro", "Bairro", 'maxlength="30"', "municipal imovel_cep!=")
      + c("imovel_cmun", "Município (IBGE)", 'maxlength="7" inputmode="numeric"', "municipal imovel_cep!=") + c("imovel_uf", "UF", 'maxlength="2"', "municipal imovel_cep!="))}
    ${G("ibs", "Reembolso, repasse ou ressarcimento (valores de terceiros já tributados)", c("ree_valor", "Valor (R$)", 'inputmode="decimal"')
      + `<label data-vis="ree_valor!=">Tipo<select data-nx="ree_tipo"><option value="99">99 Outros reembolsos/ressarcimentos</option><option value="01">01 Repasse a corretores (imóveis)</option><option value="02">02 Repasse a fornecedor (agência de turismo)</option><option value="03">03 Produção externa (publicidade)</option><option value="04">04 Mídia (publicidade)</option></select></label>`
      + c("ree_xtipo", "Descrição", 'maxlength="150"', "ree_valor!= ree_tipo=99") + c("ree_chave", "Chave do documento eletrônico (se houver)", 'maxlength="50" inputmode="numeric"', "ree_valor!=")
      + `<label data-vis="ree_valor!= ree_chave!=">Tipo do documento<select data-nx="ree_tipo_chave"><option value="1">NFS-e</option><option value="2">NF-e</option><option value="3">CT-e</option><option value="9">Outro</option></select></label>`
      + c("ree_ndoc", "Nº do documento", "", "ree_valor!= ree_chave=") + c("ree_xdoc", "Descrição do documento", "", "ree_valor!= ree_chave=")
      + c("ree_fornec_doc", "Fornecedor CPF/CNPJ", 'inputmode="numeric"', "ree_valor!=") + c("ree_fornec_nome", "Fornecedor nome", "", "ree_valor!= ree_fornec_doc!=")
      + c("ree_dt_emi", "Emissão do documento", 'type="date"', "ree_valor!=") + c("ree_dt_comp", "Competência do documento", 'type="date"', "ree_valor!="))}
    ${G("", "Intermediário e notas relacionadas", c("interm_doc", "Intermediário CPF/CNPJ", 'inputmode="numeric" placeholder="se houver"') + c("interm_nome", "Intermediário nome", "", "interm_doc!=") + c("v_receb", "Valor recebido pelo intermediário (R$)", 'inputmode="decimal"', "interm_doc!=") + c("ref_nfse", "NFS-e referenciada(s) — chaves", 'placeholder="separadas por vírgula"', "ibs"))}
    ${G("nacional", "Exterior — exportação ou serviço prestado fora do país", c("local_prestacao_pais", "País da prestação (se fora do Brasil)", 'maxlength="2" placeholder="sigla ISO, ex.: US"')
      + `<label>Moeda<select data-nx="comext_moeda"><option value="">Não se aplica</option>${Object.entries(ST.moedas || {}).map(([k, v]) => `<option value="${k}">${k} — ${esc(v)}</option>`).join("")}</select></label>`
      + c("comext_valor", "Valor na moeda estrangeira", 'inputmode="decimal"', "comext_moeda!=")
      + `<label data-vis="comext_moeda!=">Modo de prestação<select data-nx="comext_md"><option value="1">1 Transfronteiriço (do Brasil para o exterior)</option><option value="2">2 Consumo no Brasil (cliente estrangeiro aqui)</option><option value="3">3 Presença comercial no exterior</option><option value="4">4 Movimento temporário de pessoas físicas</option></select></label>`
      + `<label data-vis="comext_moeda!=">Vínculo com o cliente<select data-nx="comext_vinc"><option value="0">Sem vínculo</option><option value="1">Controlada</option><option value="2">Controladora</option><option value="3">Coligada</option><option value="4">Matriz</option><option value="5">Filial ou sucursal</option><option value="6">Outro vínculo</option></select></label>`
      + `<label data-vis="comext_moeda!=">Apoio ao comércio exterior (prestador)<select data-nx="comext_mec_p"><option value="01">Nenhum</option><option value="02">ACC</option><option value="03">ACE</option><option value="04">BNDES-Exim pós-embarque</option><option value="05">BNDES-Exim pré-embarque</option><option value="06">FGE</option><option value="07">PROEX equalização</option><option value="08">PROEX financiamento</option></select></label>`
      + c("comext_mec_t", "Apoio ao comércio exterior (tomador) — código", 'maxlength="2" inputmode="numeric" placeholder="01 = nenhum"', "comext_moeda!=")
      + `<label data-vis="comext_moeda!=">Movimentação temporária de bens<select data-nx="comext_mov"><option value="1">Não</option><option value="2">Vinculada a declaração de importação</option><option value="3">Vinculada a declaração de exportação</option></select></label>`
      + c("comext_di", "Nº da DI (se houver)", 'maxlength="12"', "comext_mov=2") + c("comext_re", "Nº do RE (se houver)", 'maxlength="12"', "comext_mov=3")
      + `<label data-vis="comext_moeda!=">Enviar ao MDIC (Comércio Exterior)<select data-nx="comext_mdic"><option value="0">Não</option><option value="1">Sim</option></select></label>`)}
    ${G("nacional", "Emissão pelo tomador ou intermediário (raro)", `<label>Quem emite<select data-nx="tp_emit"><option value="">Esta empresa como prestadora (normal)</option><option value="2">Esta empresa como TOMADORA (ex.: importação de serviço)</option><option value="3">Esta empresa como INTERMEDIÁRIA</option></select></label>`
      + `<label data-vis="tp_emit!=">Motivo<select data-nx="motivo_emis_ti"><option value="1">1 Importação de serviço</option><option value="2">2 Obrigado pela legislação municipal</option><option value="3">3 Prestador se recusou a emitir</option><option value="4">4 Rejeição da NFS-e emitida pelo prestador</option></select></label>`
      + `<label data-vis="tp_emit!=">Regime do prestador<select data-nx="prest_op_simp_nac"><option value="1">Não optante do Simples (ou do exterior)</option><option value="2">MEI</option><option value="3">ME/EPP do Simples</option></select></label>`
      + c("toma_doc", "Tomador final CPF/CNPJ", 'inputmode="numeric"', "tp_emit=3") + c("toma_nome", "Tomador final nome", 'maxlength="150"', "tp_emit=3")
      + `<p class="sub inteiro" data-vis="tp_emit!=">Nesse modo o <b>cliente escolhido acima é o PRESTADOR</b> do serviço. A nota não entra no contas a receber desta empresa.</p>`)}
    ${G("nacional", "Substituição de NFS-e", c("subst_chave", "Chave da NFS-e substituída", 'maxlength="50" inputmode="numeric"')
      + `<label data-vis="subst_chave!=">Motivo<select data-nx="subst_motivo"><option value="99">99 Outros</option><option value="01">01 Desenquadramento do Simples</option><option value="02">02 Enquadramento no Simples</option><option value="03">03 Inclusão retroativa de imunidade/isenção</option><option value="04">04 Exclusão retroativa de imunidade/isenção</option><option value="05">05 Rejeição pelo tomador/intermediário</option></select></label>`
      + c("subst_xmotivo", "Descrição do motivo", "", "subst_chave!="))}
  </details>`;
}
// Campos que se repetem em todas as notas do tomador (cadastro do cliente). Mesmos nomes de blocoNota (data-nx):
// a emissão junta estes com os da nota, e os da nota valem por cima.
function blocoFixos() {
  const c = (k, t, extra = "", vis = "") => `<label${vis ? ` data-vis="${vis}"` : ""}>${t}<input data-nx="${k}" ${extra}></label>`;
  const G = (vis, titulo, corpo) => `<div class="grupo-nx" data-grupo${vis ? ` data-vis="${vis}"` : ""}><h3 class="bloco">${titulo}</h3><div class="campos">${corpo}</div></div>`;
  return `<div id="cf_nx"><details class="mais-nota"><summary>${ic("nota")}Campos fixos das notas deste tomador <span class="sub" data-nx-resumo></span></summary>
    <p class="sub">Preenchidos sozinhos pela importação dos XML (o que se repete nas notas dele) e usados em toda nota deste tomador — manual, em lote, recorrência e robô. Na emissão, o que for preenchido na própria nota vale por cima.</p>
    ${G("", "Local e documentos", c("local_prestacao", "Município da prestação (IBGE)", 'inputmode="numeric" maxlength="7" placeholder="vazio = da empresa"') + c("local_recolhimento", "Município do recolhimento (IBGE)", 'inputmode="numeric" maxlength="7"', "municipal local_prestacao!=")
      + c("pedido", "Nº do pedido / ordem de compra", 'maxlength="15"') + c("pedido_item", "Item do pedido", 'maxlength="15"', "nacional pedido!=") + c("doc_ref", "Documento de referência (contrato…)", 'maxlength="255"') + c("doc_tec", "ART / RRT / DRT", 'maxlength="40"', "obra"))}
    ${G("deducao", "Dedução/redução da base", c("ded_pct", "Dedução/redução (%)", 'inputmode="decimal"'))}
    ${G("obra", "Obra (construção civil)", c("obra_cno", "CNO / CEI da obra", 'maxlength="30"') + c("obra_cib", "ou CIB (8 caracteres)", 'maxlength="8"') + c("obra_insc_imob", "Inscrição imobiliária (opcional)", 'maxlength="30"'))}
    ${G("ibs,municipal", "Imóvel (serviços sobre bens imóveis, exceto obra)", c("imovel_cib", "CIB do imóvel", 'maxlength="8"', "nacional") + c("imovel_insc_imob", "Inscrição imobiliária", 'maxlength="30"', "nacional")
      + c("imovel_cep", "CEP do imóvel", 'maxlength="8" inputmode="numeric"', "municipal") + c("imovel_lgr", "Logradouro", 'maxlength="80"', "municipal imovel_cep!=") + c("imovel_nro", "Número", 'maxlength="6"', "municipal imovel_cep!=")
      + c("imovel_bairro", "Bairro", 'maxlength="30"', "municipal imovel_cep!=") + c("imovel_cmun", "Município (IBGE)", 'maxlength="7" inputmode="numeric"', "municipal imovel_cep!=") + c("imovel_uf", "UF", 'maxlength="2"', "municipal imovel_cep!="))}
    ${G("", "Intermediário", c("interm_doc", "Intermediário CPF/CNPJ", 'inputmode="numeric" placeholder="se houver"') + c("interm_nome", "Intermediário nome", 'maxlength="150"', "interm_doc!="))}
    ${G("nacional", "Exterior — exportação (o valor na moeda vai em cada nota)", c("local_prestacao_pais", "País da prestação (se fora do Brasil)", 'maxlength="2" placeholder="sigla ISO, ex.: US"')
      + `<label>Moeda<select data-nx="comext_moeda"><option value="">Não se aplica</option>${Object.entries(ST.moedas || {}).map(([k, v]) => `<option value="${k}">${k} — ${esc(v)}</option>`).join("")}</select></label>`
      + `<label data-vis="comext_moeda!=">Modo de prestação<select data-nx="comext_md"><option value="1">1 Transfronteiriço</option><option value="2">2 Consumo no Brasil</option><option value="3">3 Presença comercial no exterior</option><option value="4">4 Movimento temporário de pessoas físicas</option></select></label>`
      + `<label data-vis="comext_moeda!=">Vínculo com o cliente<select data-nx="comext_vinc"><option value="0">Sem vínculo</option><option value="1">Controlada</option><option value="2">Controladora</option><option value="3">Coligada</option><option value="4">Matriz</option><option value="5">Filial ou sucursal</option><option value="6">Outro vínculo</option></select></label>`
      + c("comext_mec_p", "Apoio ao comércio exterior (prestador) — código", 'maxlength="2" inputmode="numeric" placeholder="01 = nenhum"', "comext_moeda!=")
      + c("comext_mec_t", "Apoio ao comércio exterior (tomador) — código", 'maxlength="2" inputmode="numeric" placeholder="01 = nenhum"', "comext_moeda!=")
      + `<label data-vis="comext_moeda!=">Movimentação temporária de bens<select data-nx="comext_mov"><option value="1">Não</option><option value="2">Vinculada a declaração de importação</option><option value="3">Vinculada a declaração de exportação</option></select></label>`
      + `<label data-vis="comext_moeda!=">Enviar ao MDIC<select data-nx="comext_mdic"><option value="0">Não</option><option value="1">Sim</option></select></label>`)}
  </details></div>`;
}
const TIPOS_DED = [["1", "Alimentação/frigobar"], ["2", "Materiais"], ["3", "Produção externa"], ["4", "Reembolso de despesas"], ["5", "Repasse consorciado"], ["6", "Repasse plano de saúde"], ["7", "Serviços"], ["8", "Subempreitada de mão de obra"], ["9", "Profissional parceiro"], ["99", "Outras deduções"]];
function linhaDed(d = {}) {
  const i = (k, t, extra = "") => `<label>${t}<input data-dd="${k}" value="${esc(d[k] || "")}" ${extra}></label>`;
  return `<div class="ded-linha campos">${i("chave", "Chave NF-e/NFS-e ou nº do documento", 'placeholder="44/50 dígitos ou nº do recibo"')}
    <label>Tipo<select data-dd="tp">${TIPOS_DED.map(([v, t]) => `<option value="${v}" ${d.tp == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${i("data", "Emissão", 'type="date"')}${i("valor_deducao", "Valor deduzido (R$)", 'inputmode="decimal"')}
    ${i("fornec_doc", "Fornecedor CPF/CNPJ", 'inputmode="numeric"')}${i("fornec_nome", "Fornecedor nome")}
    <button class="btn min sec" type="button" data-ded-rm title="Remover">${ic("x")}</button></div>`;
}
function ligarNota(el, item) {
  const box = $(".mais-nota", el); if (!box) return () => {};
  const add = $("[data-ded-add]", box);
  if (add) add.onclick = () => { $("[data-ded-docs]", box).insertAdjacentHTML("beforeend", linhaDed()); ligarDed(); atu(); };
  const ligarDed = () => $$("[data-ded-rm]", box).forEach(b => b.onclick = () => { b.closest(".ded-linha").remove(); atu(); });
  const atu = () => { aplicarVis(box, ctxFiscal({ item: item() }));
    const n = Object.keys(lerNota(el)).length; $("[data-nx-resumo]", box).textContent = n ? `· ${n} campo(s) preenchido(s)` : "· opcional"; };
  $$("[data-nx]", box).forEach(i => { i.addEventListener("input", atu); i.addEventListener("change", atu); });
  atu(); return atu;
}
function preencherNota(el, x) {
  $$("[data-nx]", el).forEach(i => { i.value = x[i.dataset.nx] ?? (i.tagName == "SELECT" ? i.options[0].value : ""); });
}
function lerNota(el) {
  const x = {}; $$("[data-nx]", el).forEach(i => { const v = i.value.trim(); if (v && !i.closest("[hidden]")) x[i.dataset.nx] = v.replace(/^(\d+),(\d+)$/, "$1.$2"); });
  if (!x.ree_valor) Object.keys(x).filter(k => k.startsWith("ree_")).forEach(k => delete x[k]);
  if (!x.subst_chave) { delete x.subst_motivo; delete x.subst_xmotivo; }
  if (!x.comext_moeda) Object.keys(x).filter(k => k.startsWith("comext_")).forEach(k => delete x[k]);
  if (!x.tp_emit) ["motivo_emis_ti", "prest_op_simp_nac", "toma_doc", "toma_nome"].forEach(k => delete x[k]);
  const docs = $$(".ded-linha", el).filter(l => !l.closest("[hidden]")).map(l => { const d = {}; $$("[data-dd]", l).forEach(i => { const v = i.value.trim(); if (v) d[i.dataset.dd] = v.replace(/^(\d+),(\d+)$/, "$1.$2"); });
    const dig = (d.chave || "").replace(/\D/g, "");
    if (dig.length == 44 || dig.length == 50) d.chave = dig; else if (d.chave) { d.numero = d.chave; d.tipo = "nDoc"; delete d.chave; }
    return d; }).filter(d => Object.keys(d).length > 1);
  if (docs.length) x.ded_docs = docs;
  return x;
}

function regraDe(doc) { return (doc && (ST.regras_nfse || {})[doc]) || ST.regra_geral || "geracao"; }
function nomeRegra(r) { return (ST.regras_nomes || {})[r] || r; }
function blocoFaturar(p) {
  return `<div class="faturar"><label class="chk"><input type="checkbox" id="${p}_cobrar" checked> <b>Gerar cobrança</b> <span class="sub">— boleto/PIX enviado ao cliente e régua de cobrança</span></label>
    <p class="regra-nfse" id="${p}_regra"></p><p class="sub" id="${p}_dica"></p></div>`;
}
function opcoesFaturar(p) { return { cobrar: $(`#${p}_cobrar`).checked }; }
function ligarFaturar(p, botao, docAtual, rotEmitir = "Emitir nota", rotCobrar = "Gerar cobrança", rotLancar = "Lançar conta a receber") {
  const atualizar = () => { const o = opcoesFaturar(p), doc = docAtual ? docAtual() : "", r = doc ? regraDe(doc) : ST.regra_geral || "geracao";
    const propria = doc && (ST.regras_nfse || {})[doc] && (ST.regras_nfse || {})[doc] != ST.regra_geral;
    $(`#${p}_regra`).innerHTML = `${ic("nota")}<span><b>Nota fiscal:</b> ${esc(nomeRegra(r))} <span class="sub">— ${doc ? (propria ? "regra da recorrência deste cliente" : "regra geral") : "regra geral; clientes com regra própria na recorrência seguem a deles"} · <a href="#${propria ? "contratos" : "config"}">alterar</a></span></span>`;
    $(botao).textContent = r == "baixa" ? rotCobrar : r == "geracao" ? rotEmitir : rotLancar;
    $(`#${p}_dica`).textContent = r == "baixa" ? (o.cobrar ? "Gera o boleto agora. Quando o Inter (ou o extrato) confirmar o pagamento, o sistema dá a baixa e emite a NFS-e sozinho." : "Sem boleto: a NFS-e sai quando você der a baixa do pagamento (manual ou pela conciliação do extrato).")
      : r == "geracao" ? (o.cobrar ? "Emite a nota agora e gera a conta a receber com boleto/PIX, que entra na régua de cobrança." : "Emite a nota e lança só o faturamento: sem boleto/PIX, fora da régua e fora do “a receber”.")
      : (o.cobrar ? "Lança a conta a receber com boleto/PIX, sem emitir NFS-e." : "Lança só o faturamento, sem NFS-e e sem cobrança."); };
  $(`#${p}_cobrar`).onchange = atualizar; atualizar(); return atualizar;
}
function opcoesClientes() { return ST.clientes.map(c => `<option value="${esc(c.razao_social)} — ${fmtDoc(c.cpf_cnpj)}">`).join(""); }
function docDe(txt) { const m = String(txt).match(/(\d[\d./-]{7,})\s*$/); return m ? m[1].replace(/\D/g, "") : String(txt).replace(/\D/g, ""); }
function form(el) { const o = {}; $$("[name]", el).forEach(i => o[i.name] = i.type == "checkbox" ? i.checked : i.value); return o; }
async function carregarEstado() {
  ST = await api("estado");
  if (ST.licenca && !ST.licenca.liberado) telaLicenca(ST.licenca);
  const b = $("#amb");
  b.innerHTML = `<span class="ponto"></span><span><b>${ST.producao ? "Produção" : "Homologação"}</b><small>${ST.producao ? "Notas com validade fiscal" : "Teste, sem validade"} · ${nomeCanal(true)} · v${esc(ST.versao || "")}</small></span>`;
  b.className = "amb " + (ST.producao ? "prod" : "hom");
  b.title = "Clique para trocar o ambiente";
  const e = ST.empresa || {}, nome = (e.nome || "Empresa").trim();
  const ini = nome.split(/\s+/).filter(w => w.length > 2 && !/^(ltda|me|epp|eireli|s\/a|de|da|do|e)$/i.test(w)).slice(0, 2).map(w => w[0]).join("").toUpperCase() || nome.slice(0, 2).toUpperCase();
  $("#empresa").innerHTML = `<span class="selo-marca">${esc(ini)}</span><span class="marca-txt">${esc(nomeCli(nome))}<small>${ST.empresas.length > 1 ? `${ST.empresas.length} empresas · trocar` : "Financeiro · NFS-e"}</small></span><svg class="ic seta"><use href="#i-contratos"/></svg>`;
  document.title = `${nome} · Financeiro e NFS-e`;
}
async function trocarEmpresa(pre) {
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
  if (pre) { $(".nova-emp").open = true; $("#f_emp [name=nome]").value = pre.nome || ""; $("#f_emp [name=cnpj]").value = fmtDoc(pre.cnpj || ""); }
  $$(".emp").forEach(b => b.onclick = async () => { await api("empresa/ativar", { id: b.dataset.id }); fechar(); await carregarEstado(); ir(PAG); aviso("Empresa em uso: " + b.querySelector("b").textContent); });
  $("#criar_emp").onclick = async () => { await api("empresa/criar", form($("#f_emp"))); fechar(); await carregarEstado(); ir("config"); aviso("Empresa cadastrada. Complete as configurações e o serviço padrão.", 7000); };
}
$("#amb").onclick = async () => {
  const p = !ST.producao;
  if (!confirm(p ? "Ativar PRODUÇÃO? As notas emitidas terão validade fiscal." : "Voltar para HOMOLOGAÇÃO (teste, sem validade)?")) return;
  await api("ambiente", { producao: p }); await carregarEstado(); ir(PAG);
};

function nomeCanal(curto) { return ST.canal == "nacional" ? (curto ? "Nacional" : "Emissor Nacional (nfse.gov.br)") : (curto ? "Itaboraí" : "Webservice da Prefeitura de Itaboraí"); }

// ---------------------------------------------------------------- nota que parece duplicada: o sistema pergunta
// lista = resultados de emissão com .duplicidade e .titulo_id; pergunta um a um e chama fim() no final
function confirmarDuplicidades(lista, fim = () => {}) {
  const pend = (lista || []).filter(r => r && r.duplicidade && r.duplicidade.length && r.titulo_id);
  if (!pend.length) return fim();
  const r = pend.shift(), seguir = () => confirmarDuplicidades(pend, fim);
  modal(`<h2>${ic("alerta")}Possível nota em duplicidade</h2>
    <p><b>${esc(r.cliente || "")}</b> — nota de <b>R$ ${esc(String(r.valor || ""))}</b>. Este cliente <b>já tem</b>:</p>
    <div class="tabela"><table><thead><tr><th>NFS-e</th><th>Emitida em</th><th>Competência</th><th class="n">Valor</th><th>Por que parece igual</th></tr></thead><tbody>
    ${r.duplicidade.map(d => `<tr><td><b>${esc(d.nfse)}</b></td><td>${dt(d.data)}</td><td>${esc((d.competencia || "").split("-").reverse().join("/"))}</td><td class="n">${num(d.valor_cent)}</td><td>${esc(d.motivo)}</td></tr>`).join("")}
    </tbody></table></div>
    <p>Está correto emitir <b>mais esta</b> nota? (ex.: serviços de meses diferentes, um serviço extra)</p>
    <p><button class="btn" id="dp_sim">${ic("nota")}Sim, está correto — emitir</button>
      <button class="btn sec perigo" id="dp_nao">${ic("x")}Não — é duplicada (não emitir e cancelar este lançamento)</button>
      <button class="btn sec" id="dp_dep">Decidir depois</button></p>
    <p class="sub">“Decidir depois”: o título fica em Contas a receber como <b>Possível duplicidade</b>, sem nota, até você confirmar no botão “Emitir NFS-e”.</p><div id="dp_res"></div>`);
  $("#dp_sim").onclick = async () => { $("#dp_res").innerHTML = '<p class="sub">Emitindo…</p>';
    const x = await api("titulo/forcar_nfse", { id: r.titulo_id, confirmar_duplicidade: true });
    aviso(x.sucesso ? `NFS-e ${x.nfse || ""} emitida ✔` : "Não emitiu: " + (x.erros || []).join("; "), 9000); fechar(); seguir(); };
  $("#dp_nao").onclick = async () => { await api("titulo/cancelar", { id: r.titulo_id, motivo: "Nota em duplicidade — não emitida" });
    aviso("Lançamento cancelado; nenhuma nota foi emitida ✔", 7000); fechar(); seguir(); };
  $("#dp_dep").onclick = () => { fechar(); seguir(); };
}
