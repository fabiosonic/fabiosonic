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
        ${L("n_bm!=", 'Redução da base pelo benefício (%)<input data-fz="p_red_bm" inputmode="decimal">')}
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
    ${G("", "Descontos" + '<span data-vis="deducao"> e dedução/redução da base</span>', c("desc_incond", "Desconto incondicionado (R$)", 'inputmode="decimal"') + c("desc_cond", "Desconto condicionado (R$)", 'inputmode="decimal"') + c("ded_valor", "Dedução/redução (R$)", 'inputmode="decimal"', "deducao") + c("ded_pct", "ou Dedução/redução (%)", 'inputmode="decimal"', "deducao"))}
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
    ${G("nacional", "Substituição de NFS-e", c("subst_chave", "Chave da NFS-e substituída", 'maxlength="50" inputmode="numeric"')
      + `<label data-vis="subst_chave!=">Motivo<select data-nx="subst_motivo"><option value="99">99 Outros</option><option value="01">01 Desenquadramento do Simples</option><option value="02">02 Enquadramento no Simples</option><option value="03">03 Inclusão retroativa de imunidade/isenção</option><option value="04">04 Exclusão retroativa de imunidade/isenção</option><option value="05">05 Rejeição pelo tomador/intermediário</option></select></label>`
      + c("subst_xmotivo", "Descrição do motivo", "", "subst_chave!="))}
  </details>`;
}
function ligarNota(el, item) {
  const box = $(".mais-nota", el); if (!box) return () => {};
  const atu = () => { aplicarVis(box, ctxFiscal({ item: item() }));
    const n = Object.keys(lerNota(el)).length; $("[data-nx-resumo]", box).textContent = n ? `· ${n} campo(s) preenchido(s)` : "· opcional"; };
  $$("[data-nx]", box).forEach(i => { i.addEventListener("input", atu); i.addEventListener("change", atu); });
  atu(); return atu;
}
function lerNota(el) {
  const x = {}; $$("[data-nx]", el).forEach(i => { const v = i.value.trim(); if (v && !i.closest("[hidden]")) x[i.dataset.nx] = v.replace(/^(\d+),(\d+)$/, "$1.$2"); });
  if (!x.ree_valor) Object.keys(x).filter(k => k.startsWith("ree_")).forEach(k => delete x[k]);
  if (!x.subst_chave) { delete x.subst_motivo; delete x.subst_xmotivo; }
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
function docDe(txt) { const m = String(txt).match(/(\d[\d./-]{10,})\s*$/); return m ? m[1].replace(/\D/g, "") : String(txt).replace(/\D/g, ""); }
function form(el) { const o = {}; $$("[name]", el).forEach(i => o[i.name] = i.type == "checkbox" ? i.checked : i.value); return o; }
async function carregarEstado() {
  ST = await api("estado");
  const b = $("#amb");
  b.innerHTML = `<span class="ponto"></span><span><b>${ST.producao ? "Produção" : "Homologação"}</b><small>${ST.producao ? "Notas com validade fiscal" : "Teste, sem validade"} · ${nomeCanal(true)} · v${esc(ST.versao || "")}</small></span>`;
  b.className = "amb " + (ST.producao ? "prod" : "hom");
  b.title = "Clique para trocar o ambiente";
  const e = ST.empresa || {}, nome = (e.nome || "Empresa").trim();
  const ini = nome.split(/\s+/).filter(w => w.length > 2 && !/^(ltda|me|epp|eireli|s\/a|de|da|do|e)$/i.test(w)).slice(0, 2).map(w => w[0]).join("").toUpperCase() || nome.slice(0, 2).toUpperCase();
  $("#empresa").innerHTML = `<span class="selo-marca">${esc(ini)}</span><span class="marca-txt">${esc(nome)}<small>${ST.empresas.length > 1 ? `${ST.empresas.length} empresas · trocar` : "Financeiro · NFS-e"}</small></span><svg class="ic seta"><use href="#i-contratos"/></svg>`;
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

// ---------------------------------------------------------------- emitir / lote
function linhaRes(r) {
  if (r.contrato_id) r.alertas = [...(r.alertas || []), "Repetição mensal ativada: contrato nº " + r.contrato_id + " (veja em Contratos)."];
  if (r.sucesso && r.sem_nota) return `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · conta a receber lançada, sem NFS-e (regra da nota)${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`;
  if (r.sucesso && r.aguardando_pagamento) return `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · ${r.boleto ? "boleto gerado" : "conta a receber criada"}${r.link && r.link.startsWith("http") ? ` · <a href="${esc(r.link)}" target="_blank">abrir cobrança</a>` : ""} · a NFS-e será emitida automaticamente quando o pagamento for confirmado${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`;
  return r.sucesso ? `<div class="msg ok"><span class="t">✔ ${esc(r.cliente)} — ${esc(r.valor)}</span> · NFS-e <b>${esc(r.nfse)}</b> · ${r.canal == "nacional" ? "Nacional · chave " + esc(r.chave) : "RPS " + esc(r.rps)}${r.link && r.link.startsWith("http") ? ` · <a href="${esc(r.link)}" target="_blank">abrir nota</a>` : ""}${(r.alertas || []).map(a => `<div class="sub">${esc(a)}</div>`).join("")}</div>`
    : `<div class="msg erro"><span class="t">✖ ${esc(r.cliente)} — ${esc(r.valor)}</span>${(r.erros || []).map(e => `<div>${esc(e)}</div>`).join("")}</div>`;
}
PAGINAS.emitir = async el => {
  el.innerHTML = `<h1>Emitir nota</h1><div class="card"><div class="campos">
    <label class="inteiro">Cliente<input id="e_cli" list="dl_cli" placeholder="Digite o nome ou CNPJ e escolha"></label>
    <label>Valor (R$)<input id="e_valor" inputmode="decimal" placeholder="0,00"></label>
    <label>Vencimento<input id="e_venc" type="date"></label>
    <label class="inteiro">Serviço (atividade)<select id="e_serv">${opcoesServ(servPadrao().id)}</select></label>
    <label class="inteiro">Descrição<input id="e_desc" maxlength="190" value="${esc(servPadrao().descricao || "")}"></label></div>
    <datalist id="dl_cli">${opcoesClientes()}</datalist>
    ${blocoFiscal("ef")}
    ${blocoNota()}
    ${blocoFaturar("e")}
    <p class="sub">Emitindo por: <b>${nomeCanal()}</b> — troque em <a href="#config">Configurações › Emissão</a>.</p>
    <button class="btn" id="e_btn">Emitir nota</button><div id="e_res"></div></div>`;
  const atuRegra = ligarFaturar("e", "#e_btn", () => (ST.clientes.find(c => c.cpf_cnpj == docDe($("#e_cli").value)) || {}).cpf_cnpj || "");
  const trocaServ = id => { $("#e_serv").value = servDe(id).id; $("#e_desc").value = servDe(id).descricao || ""; };
  $("#e_serv").onchange = () => trocaServ($("#e_serv").value);
  $("#e_cli").oninput = () => { const c = ST.clientes.find(x => x.cpf_cnpj == docDe($("#e_cli").value)); if (c && c.ultimo_valor && !$("#e_valor").value) $("#e_valor").value = Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 });
    if (c && c.servico_id) trocaServ(c.servico_id); atuRegra(); if (c) preencherFiscal("ef", c.fiscal); };
  ligarFiscal("ef");
  const atuNota = ligarNota(el, () => servDe($("#e_serv").value).item_lista_servico);
  $("#e_serv").addEventListener("change", atuNota);
  const cliInput = $("#e_cli").oninput; $("#e_cli").oninput = () => { cliInput(); atuNota(); };
  if (PREENCHER) { const p = PREENCHER; PREENCHER = null; const c = ST.clientes.find(x => x.cpf_cnpj == p.doc);
    if (c) { $("#e_cli").value = `${c.razao_social} — ${fmtDoc(c.cpf_cnpj)}`; $("#e_cli").oninput(); }
    $("#e_valor").value = p.valor; if (p.servico_id) trocaServ(p.servico_id); $("#e_desc").value = p.desc || $("#e_desc").value;
    $(".mais-nota").open = true; $('[data-nx="subst_chave"]').value = p.subst_chave;
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
      { t: "Cliente", f: c => `${esc(c.razao_social)}<div class="sub">${fmtDoc(c.cpf_cnpj)}</div>` },
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
      { t: "Emissão", f: n => dt(n.data) }, { t: "Comp.", f: n => mes(n.competencia) },
      { t: "Cliente", f: n => `${esc(n.cliente_nome)}<div class="sub">${fmtDoc(n.cpf_cnpj)}</div>` },
      { t: "Serviço", f: n => `<span class="sub">${esc(n.descricao)}</span>` },
      { t: "Valor", n: 1, f: n => num(n.valor_cent) },
      { t: "Situação", f: n => n.nfse_status == "emitida" ? selo("emitida") : n.nfse_status == "cancelada" ? selo("nf_cancelada") : selo("teste") },
      { t: "Origem", f: n => `<span class="sub">${n.origem == "importado" ? "importada (XML)" : n.nfse_canal == "nacional" ? "sistema · Nacional" : "sistema · Itaboraí"}</span>` },
      { t: "", f: n => n.pode_cancelar ? `<div class="acoes-linha">${n.nfse_canal == "nacional" && n.nfse_chave ? `<button class="btn min sec" data-sb="${n.id}" title="Emite uma nova nota que substitui esta">Substituir</button> ` : ""}<button class="btn min sec perigo-txt" data-cn="${n.id}">${ic("x")}Cancelar NFS-e</button></div>` : n.nfse_status == "emitida" && n.origem == "importado" ? '<span class="sub" title="Emitida fora do sistema">cancelar no portal</span>' : "" }],
      r.notas, FILTRO_NF.competencia ? `Nenhuma nota em ${mes(FILTRO_NF.competencia)} com esses filtros.` : "Nenhuma nota com esses filtros.");
    $$("[data-cn]", el).forEach(b => b.onclick = () => cancelarNota(r.notas.find(n => n.id == b.dataset.cn)));
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

// ---------------------------------------------------------------- contas a receber
let FILTRO_REC = "a_receber";
PAGINAS.receber = async el => {
  const comp = (el._comp ?? "");
  const lst = await api("titulos", { filtro: FILTRO_REC, competencia: comp });
  const soma = lst.reduce((a, t) => a + (t.status == "aberto" ? t.total_cent : t.status == "pago" ? t.valor_pago_cent : 0), 0);
  el.innerHTML = `<h1>Contas a receber <span class="acoes"><button class="btn" id="novo_t">${ic("mais")}Título avulso</button><button class="btn sec" id="pdf_bol">${ic("download")}PDFs dos boletos</button><a class="btn sec" href="/export/titulos.csv">${ic("download")}Exportar CSV</a></span></h1>
  <div class="card"><div class="abas">${[["a_receber", "A receber"], ["atrasado", "Atrasados"], ["pago", "Pagos"], ["sem_cobranca", "Sem cobrança"], ["sem_nfse", "Sem NFS-e"], ["cancelado", "Cancelados"], ["todos", "Todos"]].map(([k, t]) => `<button data-f="${k}" class="${k == FILTRO_REC ? "on" : ""}">${t}</button>`).join("")}
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
    if (t.situacao == "sem_cobranca") prin.push(`<button class="btn min sec" onclick="gerarCobranca(${t.id})" title="Gera boleto/PIX e coloca na régua">Gerar cobrança</button>`);
    else { prin.push(`<button class="btn min sec" onclick="cobrar(${t.id})">Cobrar</button>`);
      mais.push(it(`${ic("bloqueio")}Tirar da cobrança (manter a nota)`, `tirarDaCobranca(${t.id})`)); }
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
    modal(`<h2>Cancelar título</h2><p>Esta conta tem <b>NFS-e emitida</b>. O que você quer fazer?</p>
      <div class="opcoes-cancel"><button class="btn" id="cx_cob">${ic("ok")}Só tirar da cobrança — a nota fiscal continua válida</button>
      <p class="sub">Cancela o boleto (se houver) e tira da régua e do “a receber”. O valor continua como faturado. Use quando não for cobrar por aqui.</p>
      <button class="btn sec perigo" id="cx_nfse">${ic("x")}Cancelar a NFS-e na prefeitura e o título</button>
      <p class="sub">Só quando a nota foi emitida por engano. Pede justificativa e é enviado ao canal em que a nota saiu.</p></div>
      <p><button class="btn sec" onclick="fechar()">Voltar</button></p>`);
    $("#cx_cob").onclick = async () => { await api("titulo/sem_cobranca", { id }); fechar(); aviso("Título retirado da cobrança ✔ A NFS-e continua válida.", 6000); ir(PAG); };
    $("#cx_nfse").onclick = async () => {
      const j = prompt("Justificativa do cancelamento da NFS-e (mín. 15 caracteres):"); if (!j) return;
      if (j.trim().length < 15) return aviso("A justificativa precisa ter pelo menos 15 caracteres.");
      if (!confirm("Confirma o CANCELAMENTO DA NOTA FISCAL na prefeitura? Não dá para desfazer.")) return;
      const r = await api("titulo/cancelar_nfse", { id, justificativa: j }); fechar();
      aviso(r.sucesso ? "NFS-e e título cancelados ✔" : "A NFS-e NÃO foi cancelada: " + (r.erros || []).join("; "), 10000); ir(PAG); };
    return;
  }
  const m = prompt("Motivo do cancelamento do título:"); if (m === null) return; await api("titulo/cancelar", { id, motivo: m }); aviso("Título cancelado ✔"); ir(PAG);
}
async function tirarDaCobranca(id) {
  if (!confirm("Tirar este título da cobrança? O boleto (se houver) é cancelado e ele sai da régua e do “a receber”. A NFS-e continua válida.")) return;
  await api("titulo/sem_cobranca", { id }); aviso("Título retirado da cobrança ✔", 5000); ir(PAG);
}
async function gerarCobranca(id) {
  if (!confirm("Gerar a cobrança (boleto/PIX) deste título e colocá-lo na régua?")) return;
  const t = await api("titulo/gerar_cobranca", { id });
  aviso(t.banco_id ? "Boleto gerado ✔" : t.pix_copia_cola ? "PIX gerado ✔ (configure o Inter para boleto)" : "Não foi possível gerar: configure o Banco Inter ou a chave PIX em Configurações.", 8000); ir(PAG);
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
    <label class="inteiro">Serviço<select name="servico_id">${opcoesServ("", "Serviço habitual do cliente")}</select></label>
    <label class="inteiro">Descrição<input name="descricao" placeholder="em branco = descrição do serviço"></label>
    <label>Nota fiscal<select name="nfse"><option value="agora" ${nfseAposPagamento() ? "" : "selected"}>Emitir agora</option><option value="pagamento" ${nfseAposPagamento() ? "selected" : ""}>Emitir quando o cliente pagar</option><option value="nao">Não emitir</option></select></label>
    <label class="chk"><input type="checkbox" name="cobrar" checked> Gerar cobrança (boleto/PIX e régua)</label></div>
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const f = form($("#fn")); f.cpf_cnpj = docDe(f.cliente); const r = await api("titulo/novo", f); fechar();
    aviso(!r.sucesso ? "Título criado, mas a NFS-e falhou: " + (r.erros || []).join("; ") : f.nfse == "pagamento" ? "Título criado ✔ A NFS-e sai quando o pagamento for confirmado." : "Título criado ✔", 7000); ir(PAG); };
}

// ---------------------------------------------------------------- contratos
let FILTRO_RECOR = "todos";
PAGINAS.contratos = async el => {
  const r = await api("recorrencia");
  const L = r.linhas, total = L.filter(l => l.repetir);
  const CURTO = { geracao: "Emitir na geração", baixa: "Emitir na baixa (pago)", lancar: "Só lançar, sem NFS-e", nada: "Não emitir e não lançar" };
  const regraOpts = sel => `<option value="" ${!sel ? "selected" : ""}>Regra geral: ${esc(CURTO[r.regra_geral] || r.regra_geral)}</option>` + Object.entries(r.regras).map(([v, t]) => `<option value="${v}" title="${esc(t)}" ${sel == v ? "selected" : ""}>${CURTO[v] || t}</option>`).join("");
  el.innerHTML = `<h1>Recorrência mensal <span class="acoes"><button class="btn" id="rc_salvar">${ic("ok")}Salvar alterações</button><button class="btn sec" id="nc">${ic("mais")}Outra recorrência</button><button class="btn sec" id="gerar">Gerar títulos do mês</button></span></h1>
  <div class="kpis"><div class="kpi"><div class="r">Clientes na recorrência</div><div class="v">${total.length}</div></div><div class="kpi"><div class="r">Receita recorrente (MRR)</div><div class="v">${brl(total.reduce((a, c) => a + c.valor_cent, 0))}</div></div>
    <div class="kpi"><div class="r">A confirmar</div><div class="v">${L.filter(l => l.id && !l.repetir).length}</div></div></div>
  <div class="card"><p class="sub">Todos os clientes estão aqui, com o valor da última nota. Marque <b>Repetir todo mês</b> nos que pagam mensalmente: todo mês, no dia configurado, o robô gera o título${""} e segue a regra da nota fiscal (a do cliente, se escolhida, ou a regra geral de Configurações). Nada é cobrado de quem não estiver marcado. ${r.preenchidos ? `<b>${r.preenchidos} cliente(s) acabaram de ser trazidos com o valor da última nota.</b>` : ""}</p>
    <div class="barra"><label style="flex:1">Procurar<input id="rc_f" placeholder="nome ou CNPJ"></label>
    <div class="abas">${[["todos", "Todos"], ["sim", "Na recorrência"], ["confirmar", "A confirmar"], ["sem_valor", "Sem valor"]].map(([k, t]) => `<button data-rf="${k}" class="${k == FILTRO_RECOR ? "on" : ""}">${t}</button>`).join("")}</div></div>
    <div id="rc_tab" class="recor"></div><p class="sub" id="rc_alt"></p></div>`;
  const chave = l => l.id ? "k" + l.id : "c" + l.cpf_cnpj;
  const alterados = new Set();
  const desenhar = () => { const f = $("#rc_f").value.toLowerCase().replace(/[./-]/g, "");
    const vis = L.filter(l => (!f || l.cliente_nome.toLowerCase().includes(f) || l.cpf_cnpj.includes(f))
      && (FILTRO_RECOR == "todos" || (FILTRO_RECOR == "sim" ? l.repetir : FILTRO_RECOR == "confirmar" ? l.id && !l.repetir : !l.valor_cent)));
    $("#rc_tab").innerHTML = tabela([
      { t: '<label class="chk" title="Repetir todo mês — marcar todos os visíveis"><input type="checkbox" id="rc_todos"> Repetir</label>', f: l => `<input type="checkbox" class="rc" data-c="repetir" data-k="${chave(l)}" ${l.repetir ? "checked" : ""} aria-label="Repetir todo mês">` },
      { t: "Cliente", f: l => `${esc(l.cliente_nome)}<div class="sub">${fmtDoc(l.cpf_cnpj)}${l.id && !l.repetir ? " · a confirmar" : ""}${l.fim ? " · até " + mes(l.fim) : ""}</div>` },
      { t: "Valor mensal (R$)", f: l => `<input class="rc" data-c="valor" data-k="${chave(l)}" inputmode="decimal" style="width:96px" value="${l.valor_cent ? num(l.valor_cent) : ""}" placeholder="0,00">` },
      { t: "Vence dia", f: l => `<input class="rc" data-c="dia_vencimento" data-k="${chave(l)}" type="number" min="1" max="31" style="width:58px" value="${l.dia_vencimento}">` },
      { t: "Serviço", f: l => `<select class="rc" style="min-width:130px;max-width:170px" data-c="servico_id" data-k="${chave(l)}">${(ST.servicos || []).length > 1 ? opcoesServ(l.servico_id || "", "Habitual do cliente") : opcoesServ(l.servico_id || "", "Padrão")}</select>` },
      { t: "Nota fiscal", f: l => `<select class="rc" style="min-width:180px" data-c="nfse_quando" data-k="${chave(l)}">${regraOpts(l.nfse_quando || "")}</select>` },
      { t: "Boleto/PIX", f: l => `<input type="checkbox" class="rc" data-c="cobrar" data-k="${chave(l)}" ${l.cobrar === 0 ? "" : "checked"} aria-label="Gerar cobrança (boleto/PIX)">` },
      { t: "", f: l => l.id ? `<button class="btn min sec" data-ed="${l.id}" title="Início, fim, reajuste, descrição">Mais</button>` : "" }],
      vis, "Nenhum cliente neste filtro.");
    $$(".rc", el).forEach(i => i.onchange = i.oninput = () => { const l = L.find(x => chave(x) == i.dataset.k);
      l[i.dataset.c] = i.type == "checkbox" ? i.checked : i.value; if (i.dataset.c == "valor") l.valor_cent = Math.round(valorNum(i.value) * 100);
      if (i.dataset.c == "repetir" && i.checked && !l.valor_cent) aviso("Informe o valor mensal deste cliente.");
      alterados.add(i.dataset.k); $("#rc_alt").textContent = `${alterados.size} alteração(ões) não salva(s) — clique em “Salvar alterações”.`; });
    $("#rc_todos").onclick = e => { $$('.rc[data-c="repetir"]', el).forEach(x => { if (x.checked != e.target.checked) { x.checked = e.target.checked; x.onchange(); } }); };
    $$("[data-ed]", el).forEach(b => b.onclick = () => editarContrato(L.find(l => l.id == b.dataset.ed)));
  };
  $("#rc_f").oninput = desenhar; desenhar();
  $$("[data-rf]", el).forEach(b => b.onclick = () => { FILTRO_RECOR = b.dataset.rf; $$("[data-rf]", el).forEach(x => x.classList.toggle("on", x == b)); desenhar(); });
  $("#rc_salvar").onclick = async () => {
    const linhas = L.filter(l => alterados.has(chave(l))).map(l => ({ id: l.id, cpf_cnpj: l.cpf_cnpj, valor_cent: l.valor_cent, dia_vencimento: Number(l.dia_vencimento),
      servico_id: l.servico_id || "", nfse_quando: l.nfse_quando || "", cobrar: l.cobrar !== false && l.cobrar !== 0, repetir: !!l.repetir }));
    if (!linhas.length) return aviso("Nada para salvar.");
    if (linhas.some(l => l.repetir && !l.valor_cent)) return aviso("Há cliente marcado para repetir sem valor mensal.");
    const novos = linhas.filter(l => l.repetir && !(L.find(x => x.id && x.id == l.id) || {}).confirmado).length;
    if (novos && !confirm(`${novos} cliente(s) passam a ser faturados todo mês a partir deste mês. Confirmar?`)) return;
    const x = await api("recorrencia/salvar", { linhas }); aviso(`${x.salvos} recorrência(s) salva(s) ✔`); await carregarEstado(); ir("contratos"); };
  $("#nc").onclick = () => editarContrato({});
  $("#gerar").onclick = async () => { const c = prompt("Competência (AAAA-MM):", hojeISO().slice(0, 7)); if (!c) return;
    const x = await api("recorrencia/gerar", { competencia: c }); aviso(`${x.gerados} título(s) gerado(s) ✔`); };
};
async function confirmarTodos() {
  if (!confirm("Confirmar todos os contratos detectados? A partir do próximo vencimento o robô passa a emitir a NFS-e e cobrar esses clientes todo mês.")) return;
  const r = await api("contratos/confirmar", {}); aviso(`${r.confirmados} contrato(s) confirmado(s) ✔`); ir(PAG);
}
async function confirmarUm(id) { await api("contratos/confirmar", { ids: [id] }); aviso("Contrato confirmado ✔"); ir("contratos"); }
function editarContrato(c) {
  const cli = ST.clientes.find(x => x.cpf_cnpj == c.cpf_cnpj);
  modal(`<h2>${c.id ? "Recorrência de " + esc(c.cliente_nome || "") : "Nova recorrência"}</h2><div class="campos" id="fc">
    <label class="inteiro">Cliente<input name="cliente" list="dl_cli3" value="${cli ? esc(cli.razao_social + " — " + fmtDoc(cli.cpf_cnpj)) : ""}"></label><datalist id="dl_cli3">${opcoesClientes()}</datalist>
    <label class="inteiro">Serviço da nota<select name="servico_id" id="fc_serv">${opcoesServ(c.servico_id || "", "Serviço habitual do cliente")}</select></label>
    <label class="inteiro">Descrição<input name="descricao" value="${esc(c.descricao || "")}" placeholder="em branco = descrição do serviço"></label>
    <label>Valor mensal (R$)<input name="valor" value="${c.valor_cent ? num(c.valor_cent) : ""}"></label>
    <label>Dia do vencimento<input name="dia_vencimento" type="number" min="1" max="31" value="${c.dia_vencimento || ST.config.financeiro.dia_vencimento_padrao}"></label>
    <label>Início<input name="inicio" type="month" value="${c.inicio || hojeISO().slice(0, 7)}"></label><label>Fim (opcional)<input name="fim" type="month" value="${c.fim || ""}"></label>
    <label>Mês do reajuste<select name="mes_reajuste">${["Sem reajuste", "Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"].map((m, i) => `<option value="${i}" ${i == (c.mes_reajuste || 0) ? "selected" : ""}>${m}</option>`).join("")}</select></label>
    <label>Reajuste (%)<input name="reajuste_pct" value="${c.reajuste_pct || ""}" placeholder="ex.: 4,5 (IPCA)"></label>
    <label class="inteiro">Lançamento de serviços / emissão de NFS-e<select name="nfse_quando">${[["", `Regra geral (${nomeRegra(ST.regra_geral)})`], ...Object.entries(ST.regras_nomes || {})].map(([v, t]) => `<option value="${v}" ${((c.emitir_nfse === 0 && !c.nfse_quando) ? "lancar" : ({ agora: "geracao", pagamento: "baixa" }[c.nfse_quando] || c.nfse_quando || "")) == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <input type="hidden" name="emitir_nfse" value="1">
    <label class="chk"><input type="checkbox" name="cobrar" ${c.cobrar === 0 ? "" : "checked"}> Gerar cobrança (boleto/PIX e régua)</label>
    <label class="chk"><input type="checkbox" name="confirmado" ${c.id && !c.confirmado ? "" : "checked"}> <b>Repetir todo mês</b></label></div>
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button>${c.id ? ` <button class="btn sec" onclick="fechar();encerrar(${c.id})">${ic("x")}Tirar da recorrência</button>` : ""}</p>`);
  $("#fc_serv").onchange = e => { if (e.target.value) $("#fc [name=descricao]").value = servDe(e.target.value).descricao || ""; };
  $("#ok").onclick = async () => { const f = form($("#fc")); f.cpf_cnpj = docDe(f.cliente); if (c.id) f.id = c.id; await api("contrato/salvar", f); fechar(); aviso("Recorrência salva ✔"); await carregarEstado(); ir("contratos"); };
}
async function encerrar(id) { if (confirm("Tirar este cliente da recorrência? Ele deixa de gerar cobranças.")) { await api("contrato/excluir", { id }); ir("contratos"); } }

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
  ${ST.config.cobranca.provedor == "inter" ? `<div class="card"><h2>${ic("banco")}Extrato do Banco Inter (automático)</h2>
    <p class="sub">O robô baixa o extrato da conta Inter direto do banco (sem arquivo) e concilia sozinho, de hora em hora${ST.config.financeiro.extrato_inter_ate ? ` — último dia baixado: <b>${dt(ST.config.financeiro.extrato_inter_ate)}</b>` : ""}. Lançamentos que já vieram por OFX não são duplicados. A integração do Inter precisa da permissão <b>“Consultar extrato e saldo”</b>.</p>
    <div class="barra"><label>Período<select id="ext_dias"><option value="7">Últimos 7 dias</option><option value="30" selected>Últimos 30 dias</option><option value="60">Últimos 60 dias</option><option value="90">Últimos 90 dias</option></select></label>
    <button class="btn" id="ext_baixar">${ic("download")}Baixar extrato agora</button></div><div id="ext_res"></div></div>` : ""}
  <div class="card"><h2>Lançamentos não conciliados (${pend.length})</h2>
  ${tabela([{ t: "Data", f: m => dt(m.data) }, { t: "Histórico", f: m => esc(m.descricao) }, { t: "Valor", n: 1, f: m => num(m.valor_cent) },
    { t: "Sugestões", f: m => m.sugestoes.length ? m.sugestoes.map(s => `<button class="btn min sec" onclick="vincular(${m.id},${s.id})" title="Venc. ${dt(s.vencimento)}">${esc(s.cliente.slice(0, 28))} · ${num(s.valor_cent)}</button>`).join(" ") : '<span class="sub">—</span>' }], pend, "Tudo conciliado ✔")}</div>`;
  if ($("#ext_baixar")) $("#ext_baixar").onclick = async () => { const b = $("#ext_baixar"); b.disabled = true; b.textContent = "Baixando…";
    try { const r = await api("conciliacao/inter", { dias: $("#ext_dias").value });
      $("#ext_res").innerHTML = `<div class="msg ok">${r.lancamentos} lançamento(s) de ${dt(r.periodo.slice(0, 10))} a ${dt(r.periodo.slice(-10))} · ${r.novos} novo(s) · <b>${r.titulos}</b> recebimento(s) baixado(s) · ${r.despesas} pagamento(s) conciliado(s)</div>`;
      await carregarEstado(); setTimeout(() => ir("conciliacao"), 3000);
    } catch (e) { b.disabled = false; b.innerHTML = `${ic("download")}Baixar extrato agora`; } };
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
  el.innerHTML = `<h1>Clientes <span class="acoes"><button class="btn" id="imp_xml">${ic("download")}Importar clientes dos XML</button></span></h1><div id="imp_area"></div><div class="card"><div class="barra"><label>CNPJ / CPF<input id="c_doc" placeholder="só números"></label></div>
    <div class="campos" id="fcli"><label class="inteiro">Razão social / nome<input name="razao_social"></label>
    <label>Tipo logradouro<input name="tipo_logradouro" placeholder="RUA"></label><label>Logradouro<input name="logradouro"></label><label>Número<input name="numero"></label>
    <label>Complemento<input name="complemento"></label><label>Bairro<input name="bairro"></label><label>CEP<input name="cep"></label>
    <label>Cidade<input name="cidade" placeholder="automática pelo cód. IBGE"></label><label>Cód. IBGE município<input name="codigo_municipio"></label><label>UF<input name="uf" maxlength="2"></label>
    <label>Inscrição municipal<input name="inscricao_municipal"></label><label>E-mail (cobrança)<input name="email"></label><label>Telefone / WhatsApp<input name="telefone"></label>
    <label class="inteiro">Serviço habitual (vem selecionado ao emitir)<select name="servico_id">${opcoesServ("", "Padrão da empresa")}</select></label></div>
    ${blocoFiscal("cf")}
    <p><button class="btn" id="sc">Salvar cliente</button> <button class="btn sec" id="lc">Novo</button></p></div>
    <div class="card"><div class="barra"><label style="flex:1">Procurar<input id="c_f" placeholder="nome ou CNPJ"></label></div><div id="c_tab"></div></div>`;
  const END = ["tipo_logradouro", "logradouro", "numero", "complemento", "bairro", "cep", "cidade", "codigo_municipio", "uf"];
  const preencher = c => { preencherFiscal("cf", c.fiscal); $("#c_doc").value = c.cpf_cnpj || ""; $$("#fcli [name]").forEach(i => i.value = (END.includes(i.name) ? (c.endereco || {})[i.name] : c[i.name]) || ""); };
  const desenhar = () => { const f = $("#c_f").value.toLowerCase().replace(/[./-]/g, "");
    $("#c_tab").innerHTML = `<p class="sub">${ST.clientes.length} cliente(s). Sem e-mail ou telefone o cliente não recebe a régua de cobrança.</p>` + tabela([{ t: "Cliente", f: c => esc(c.razao_social) }, { t: "CPF/CNPJ", f: c => fmtDoc(c.cpf_cnpj) },
      { t: "Contato", f: c => (c.email ? `<span title="${esc(c.email)}">${ic("email")}</span> ` : "") + (c.telefone ? `<span title="${esc(c.telefone)}">${ic("fone")}</span>` : "") || '<span class="sub">sem contato</span>' }, { t: "Última nota", f: c => c.ultimo_valor ? `${dt(c.ultima_data)} · ${Number(c.ultimo_valor).toLocaleString("pt-BR", { minimumFractionDigits: 2 })}` : "" },
      { t: "", f: c => `<button class="btn min sec" data-ed="${c.cpf_cnpj}">Editar</button> <button class="btn min sec" data-ex="${c.cpf_cnpj}" title="Excluir">${ic("x")}</button>` }],
      ST.clientes.filter(c => !f || c.razao_social.toLowerCase().includes(f) || c.cpf_cnpj.includes(f)));
    $$("[data-ed]").forEach(b => b.onclick = () => { preencher(ST.clientes.find(c => c.cpf_cnpj == b.dataset.ed)); scrollTo(0, 0); });
    $$("[data-ex]").forEach(b => b.onclick = async () => { if (confirm("Excluir do cadastro?")) { await api("cliente/excluir", { cpf_cnpj: b.dataset.ex }); await carregarEstado(); desenhar(); } }); };
  $("#c_f").oninput = desenhar; desenhar();
  $("#lc").onclick = () => preencher({});
  $("#imp_xml").onclick = () => importarXml($("#imp_area"));
  ligarFiscal("cf");
  $("#sc").onclick = async () => { const f = form($("#fcli")), e = {}; END.forEach(k => { e[k] = f[k]; delete f[k]; });
    await api("cliente/salvar", { ...f, cpf_cnpj: $("#c_doc").value, endereco: e, fiscal: lerFiscal("cf") }); aviso("Cliente salvo ✔"); await carregarEstado(); desenhar(); };
};

async function importarXml(area) {
  area.innerHTML = '<div class="card"><div class="vazio">Lendo a pasta IMPORTAR XML…</div></div>';
  const a = await api("importador/analisar");
  const rot = { descricao: "Descrição", item_lista_servico: "Item LC 116", codigo_desdobro: "Desdobro", codigo_nbs: "NBS", cnae: "CNAE",
    aliquota_iss: "Alíquota ISS (%)", tipo_tributacao: "Tipo de tributação", iss_retido: "ISS retido (1/2)", indicador_operacao: "IBS/CBS cIndOp", classificacao_tributaria: "IBS/CBS cClassTrib" };
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
          <label class="chk"><input type="radio" name="imp_pad_${j}" class="imp-sv-pad"> Tornar padrão</label>
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
      aviso(`${r.empresa}: ${r.xml} XML importado(s), ${r.clientes_novos} cliente(s) novo(s)${r.servicos ? ` · ${r.servicos} serviço(s) cadastrado(s)` : ""}${r.clientes_com_servico ? ` · ${r.clientes_com_servico} cliente(s) ligados ao serviço habitual` : ""}${(r.regra_geral || []).length ? " · regra geral completada pelas notas (" + r.regra_geral.length + " campo(s))" : ""}${r.regras_tomadores ? ` · ${r.regras_tomadores} tomador(es) com regra fiscal própria` : ""} ✔`, 12000);
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
    ${f("item_lista_servico", "Item LC 116 (ex.: 17.19)")}${f("codigo_desdobro", "Desdobro nacional (6 dígitos)")}${f("codigo_nbs", "NBS (9 dígitos)")}${f("cnae", "CNAE")}
    ${f("aliquota_iss", "Alíquota ISS (%)")}${f("tipo_tributacao", "Tipo de tributação (4 = Simples)")}${f("iss_retido", "ISS retido (1 sim / 2 não)")}${f("indicador_operacao", "IBS/CBS: cIndOp")}${f("classificacao_tributaria", "IBS/CBS: cClassTrib")}${f("ibpt_percentual", "Carga tributária IBPT (%)")}
    <label class="inteiro">Observações na nota<input name="observacoes" value="${esc(base.observacoes || "")}"></label></div>
    <p class="sub">Confira os códigos com o cadastro municipal da empresa e a Tabela IBS x CBS. Item, NBS e alíquota errados geram rejeição da nota.</p>
    <p><button class="btn" id="ok">Salvar serviço</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const d = form($("#fsv")); if (s.id) d.id = s.id; if (s.padrao) d.padrao = true;
    if (!d.nome.trim()) return aviso("Dê um nome ao serviço (ex.: Consultoria).");
    const r = await api("servico/salvar", d); if (r.erro) return; fechar(); aviso("Serviço salvo ✔"); recarregarServicos(); };
}

// ---------------------------------------------------------------- backup
async function listarBackups() {
  const el = $("#bk_lista"); if (!el) return;
  const r = await api("backup/listar");
  const mot = { manual: "Manual", automatico: "Automático (robô)", antes_da_restauracao: "Antes de uma restauração", arquivo: "Enviado de arquivo" };
  el.innerHTML = tabela([{ t: "Backup", f: b => `<b>${esc(b.criado_em ? dtHora(b.criado_em) : b.nome)}</b><div class="sub">${esc(b.nome)}</div>` },
    { t: "Tipo", f: b => esc(mot[b.motivo] || b.motivo || "—") + (b.protegido ? ' <span class="selo bom" title="Protegido por senha (AES-256)">🔒 com senha</span>' : "") }, { t: "Tamanho", n: 1, f: b => tamanho(b.tamanho) },
    { t: "", f: b => `<div class="acoes-linha"><a class="btn min sec" href="/backup/${encodeURIComponent(b.nome)}" download>${ic("download")}Baixar</a>${b.valido ? ` <button class="btn min sec" type="button" data-bk="${esc(b.nome)}">Restaurar</button>` : ""}</div>` }],
    r.backups.slice(0, 15), "Nenhum backup ainda. Clique em “Fazer backup agora”.") + (r.backups.length > 15 ? `<p class="sub">Mostrando os 15 mais recentes de ${r.backups.length}. Todos estão em ${esc(r.pasta)}.</p>` : "");
  $$("[data-bk]", el).forEach(b => b.onclick = async () => {
    const x = r.backups.find(k => k.nome == b.dataset.bk);
    if (!confirm(`Restaurar o backup de ${dtHora(x.criado_em)}?\n\nTudo desta empresa (financeiro, clientes, configurações) volta ao estado desse dia. Antes, o estado atual é salvo num backup automático.`)) return;
    const senha = x.protegido ? prompt("Senha deste backup (deixe em branco para usar a senha configurada):") : "";
    if (senha === null) return;
    aviso("Restaurando…", 60000); await posRestauracao(await api("backup/restaurar", { nome: x.nome, senha })); });
}
function tamanho(n) { return n < 1048576 ? Math.max(1, Math.round(n / 1024)) + " KB" : (n / 1048576).toFixed(1).replace(".", ",") + " MB"; }
function dtHora(s) { const [d, h] = String(s).split(" "); return dt(d) + (h ? " " + h.slice(0, 5) : ""); }
async function posRestauracao(r) {
  await carregarEstado();
  aviso(`Backup de ${dtHora(r.criado_em)} restaurado ✔${r.empresa_nome ? " na empresa " + r.empresa_nome : ""}${r.senhas_restauradas ? ` (com ${r.senhas_restauradas} senha(s))` : ""}. O estado anterior ficou salvo em ${r.backup_anterior || "—"}.`, 12000);
  ir(PAG);
}

// ---------------------------------------------------------------- configurações
PAGINAS.config = async el => {
  const [c, cred] = await Promise.all([api("config"), api("empresa/credenciais")]);
  const cr = (k, t, tipo = "text") => `<label>${t}<input type="${tipo}" data-cred="${k}" value="${esc(cred[k] || "")}"></label>`;
  const ck = (s, k, t) => `<label class="chk"><input type="checkbox" data-s="${s}" data-k="${k}" ${c[s][k] ? "checked" : ""}> ${t}</label>`;
  const sl = (s, k, t, ops) => `<label>${t}<select data-s="${s}" data-k="${k}">${ops.map(([v, x]) => `<option value="${v}" ${String(c[s][k]) == v ? "selected" : ""}>${x}</option>`).join("")}</select></label>`;
  const tx = (s, k, t, tipo = "text", extra = "") => `<label>${t}<input type="${tipo}" data-s="${s}" data-k="${k}" value="${esc(Array.isArray(c[s][k]) ? c[s][k].join(", ") : c[s][k])}" ${extra}></label>`;
  el.innerHTML = `<h1>Configurações <span class="acoes"><button class="btn" id="salvar">Salvar tudo</button></span></h1>
  <div class="card"><h2>${ic("download")}Versão anterior</h2><p class="sub">Traz da instalação antiga deste computador o que ainda estiver vazio aqui: e-mail de envio, Banco Inter, chave PIX, certificado, clientes, financeiro e outras empresas.</p>
    <p><button class="btn sec" id="busca_ant">Procurar versão anterior</button></p><div id="migra_cfg"></div></div>
  <div class="card"><h2>${ic("download")}Backup e restauração</h2><p class="sub">O backup guarda tudo desta empresa (financeiro, clientes, configurações, serviços, numeração, certificados e XML das notas) num arquivo .zip. O robô faz um por dia (guarda os 30 últimos); você pode fazer um agora a qualquer momento. Para proteger contra perda do computador, informe uma segunda pasta (pendrive, HD externo ou pasta sincronizada com a nuvem).</p>
    <div class="campos">${tx("pastas", "backup_copia", "Cópia extra dos backups em (pasta)", "text", 'placeholder="ex.: E:\\Backup ou G:\\Meu Drive\\Backup"')}
      ${tx("seguranca", "backup_senha", "Senha do backup (recomendado)", "password", 'autocomplete="new-password" placeholder="mínimo 6 caracteres — vazio = sem senha"')}</div>
    <p class="sub">${c.seguranca.backup_senha ? "🔒 Backups <b>protegidos por senha</b> (AES-256): levam também as senhas da empresa, para restaurar em outro computador já funcionando." : "Sem senha, o backup é um .zip comum: quem tiver o arquivo vê os dados (as senhas ficam fora dele). Com senha, ele fica ilegível sem ela."} <b>Anote a senha em local seguro: sem ela o backup protegido não pode ser aberto.</b></p>
    <p><button class="btn" id="bk_criar" type="button">${ic("download")}Fazer backup agora</button> <button class="btn sec" id="bk_pasta" type="button">Abrir a pasta dos backups</button>
      <label class="btn sec"><input type="file" id="bk_arq" accept=".zip,.protegido" hidden>Restaurar de um arquivo…</label></p>
    <p class="sub">Restaurar volta a empresa ao estado do backup. Antes, o sistema faz um backup do estado atual (dá para desfazer). A numeração do RPS/DPS nunca volta atrás e o ambiente (homologação/produção) não muda. Backup de uma empresa nunca é restaurado em outra.</p>
    <div id="bk_lista"><div class="vazio">Carregando…</div></div></div>
  <div class="card" id="card_pin"></div>
  <div class="card"><h2>${ic("play")}Robô financeiro</h2><p class="sub">Com o robô ligado, o sistema roda sozinho ao abrir e a cada hora (e todo dia pelo Agendador do Windows, se você rodar INSTALAR.bat): gera os títulos dos contratos, emite as NFS-e (só em produção), cria o PIX/boleto, envia a régua de cobrança, dá baixa nos pagamentos e faz backup.</p>
    <div class="campos">${ck("automacao", "ativa", "<b>Robô ligado</b>")}${ck("automacao", "gerar_titulos", "Gerar títulos dos contratos")}${ck("automacao", "emitir_nfse", "Emitir NFS-e")}${ck("automacao", "criar_cobranca", "Criar PIX/boleto")}${ck("automacao", "baixar_boletos", "Salvar PDF dos boletos")}
    ${ck("automacao", "regua", "Régua de cobrança")}${ck("automacao", "sincronizar_banco", "Baixa automática dos boletos (Inter)")}${ck("automacao", "despesas_recorrentes", "Despesas recorrentes")}${ck("automacao", "backup", "Backup diário")}</div></div>
  <div class="card"><h2>${ic("clientes")}Empresa emissora e credenciais</h2><p class="sub">Dados da empresa em uso (${esc((ST.empresa || {}).nome || "")}). Ficam só neste computador, no arquivo .env da empresa.</p>
    <div class="campos">${cr("cnpj", "CNPJ")}${cr("im", "Inscrição municipal")}${cr("ie", "Inscrição estadual")}${cr("chave", "Chave do webservice (Itaboraí)", "password")}${cr("proximo_rps", "Próximo RPS", "number")}
    <label>Optante do Simples<select data-cred="simples"><option value="S" ${cred.simples != "N" ? "selected" : ""}>Sim</option><option value="N" ${cred.simples == "N" ? "selected" : ""}>Não</option></select></label></div></div>
  <div class="card"><h2>${ic("nota")}Serviços (atividades) da empresa <span class="acoes"><button class="btn min" id="novo_serv" type="button">${ic("mais")}Novo serviço</button></span></h2>
    <p class="sub">Cada atividade (contabilidade, consultoria, treinamento…) tem o próprio item da LC 116, NBS, alíquota e descrição. Na emissão você escolhe o serviço; o <b>padrão</b> vem selecionado quando o cliente não tem serviço habitual. Os serviços também são criados sozinhos ao importar os XML das notas.</p>
    <div id="lista_serv">${tabelaServicos()}</div></div>
  <div class="card" id="regras_fiscais"><h2>${ic("nota")}Regras fiscais (regra geral)</h2><p class="sub">Valem para todos os tomadores. Um tomador com regra diferente (ex.: órgão público que retém ISS e tributos federais) tem a regra própria no cadastro dele — “Regra específica deste tomador” —, que vale primeiro. O regime define como a nota é montada: Lucro Real/Presumido informam PIS/COFINS próprios; Simples informa o percentual do Simples; MEI não informa ISS nem tributos federais.</p>
    <div class="campos">${sl("fiscal", "regime", "Regime tributário da empresa", Object.entries(ST.regimes || {}).map(([v, t]) => [v, t]))}
    <label id="ap_sn">Apuração no Simples<select data-s="emissao" data-k="reg_ap_trib_sn">${[["1", "Tudo no DAS"], ["2", "ISS fora do DAS (fixo)"], ["3", "Tudo fora do DAS"]].map(([v, t]) => `<option value="${v}" ${String(c.emissao.reg_ap_trib_sn) == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    ${sl("emissao", "reg_esp_trib", "Regime especial", [["0", "Nenhum"], ["1", "Ato cooperado"], ["2", "Estimativa"], ["3", "ME municipal"], ["4", "Notário/registrador"], ["5", "Autônomo"], ["6", "Soc. de profissionais"]])}
    ${ck("fiscal", "iss_retido", "ISS retido pelo tomador (regra geral)")}${tx("fiscal", "aliquota_iss_retido", "Alíquota do ISS retido (%)")}
    ${RET_NOMES.map(([k, t]) => tx("fiscal", k, `Retenção ${t} (%)`)).join("")}
    ${sl("fiscal", "ibscbs", "Informar IBS/CBS na nota", [["auto", "Automático (regime regular já; Simples/MEI a partir de 2027)"], ["sempre", "Sempre"], ["nunca", "Nunca"]])}
    ${sl("fiscal", "ind_final", "Consumo pessoal (IBS/CBS)", [["auto", "Automático (CPF = sim)"], ["0", "Não"], ["1", "Sim"]])}
    ${sl("fiscal", "incentivo_fiscal", "Incentivo fiscal / imunidade do prestador", [["", "Não (padrão)"], ["sim", "Sim — incentivo fiscal"], ["imune", "Imunidade / isenção"], ["nao", "Não"]])}
    ${tx("financeiro", "das_mei_mensal", "DAS-MEI do mês (R$, para a DRE)")}${tx("financeiro", "presuncao_pct", "Presunção do IRPJ/CSLL (%) — serviços: 32")}</div>
    <details class="mais-fz"><summary>Campos avançados (carga aproximada, PIS/COFINS próprio, IBS/CBS: tributação regular, diferimento e crédito presumido)</summary><div class="campos">
    ${sl("fiscal", "tot_trib_modo", "Carga aproximada (Lei 12.741)", [["auto", "Automático pelo regime"], ["valor", "Valor (IBPT do serviço)"], ["percentual", "Percentuais federal/estadual/municipal"], ["simples", "Percentual do Simples"], ["nao", "Não informar"]])}
    ${tx("fiscal", "p_tot_fed", "% federal")}${tx("fiscal", "p_tot_est", "% estadual")}${tx("fiscal", "p_tot_mun", "% municipal")}
    ${sl("fiscal", "pis_cofins_cst", "CST PIS/COFINS próprio (Real/Presumido)", [["", "01 Alíquota básica (padrão)"], ["02", "02 Alíquota diferenciada"], ["06", "06 Alíquota zero"], ["07", "07 Isenta"], ["08", "08 Sem incidência"], ["09", "09 Suspensão"], ["49", "49 Outras saídas"], ["99", "99 Outras operações"]])}
    ${tx("fiscal", "p_pis", "Alíquota PIS (%) — vazio = pelo regime")}${tx("fiscal", "p_cofins", "Alíquota COFINS (%) — vazio = pelo regime")}
    ${tx("fiscal", "cst_reg", "IBS/CBS: CST da tributação regular")}${tx("fiscal", "class_trib_reg", "IBS/CBS: cClassTrib da tributação regular")}
    ${tx("fiscal", "c_cred_pres", "IBS/CBS: código do crédito presumido")}
    ${tx("fiscal", "p_dif_uf", "Diferimento IBS UF (%)")}${tx("fiscal", "p_dif_mun", "Diferimento IBS Município (%)")}${tx("fiscal", "p_dif_cbs", "Diferimento CBS (%)")}</div>
    <p class="sub">Tributação regular de referência: para optante do Simples que recolhe IBS/CBS pelo regime regular ou situações especiais. Deixe em branco o que não se aplica.</p></details>
    <p class="sub" data-vis="regular">Retenções usuais de serviços profissionais para Lucro Real/Presumido: IRRF 1,5% · PIS 0,65% · COFINS 3% · CSLL 1% · INSS 11% (cessão de mão de obra). Optante do Simples, em regra, não sofre retenção federal. Retenções de até R$ 10,00 são dispensadas automaticamente.</p></div>
  <div class="card"><h2>${ic("nota")}Emissão da NFS-e</h2><p class="sub">Escolha por onde as notas saem. <b>Itaboraí</b>: webservice da prefeitura (chave no .env). <b>Nacional</b>: Emissor Nacional da NFS-e (Sefin/ADN — nfse.gov.br), com o certificado digital A1 do escritório. A nota já emitida é sempre cancelada pelo canal em que saiu. Homologação no nacional = “Produção Restrita”.</p>
    <div class="campos"><label>Canal de emissão<select data-s="emissao" data-k="canal">${[["municipal", "Itaboraí (webservice)"], ["nacional", "Nacional (nfse.gov.br)"]].map(([v, t]) => `<option value="${v}" ${c.emissao.canal == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <div class="inteiro cert-box"><label class="soltar"><input type="file" id="cert_arq" accept=".pfx,.p12" hidden>${ic("download")}<span><b id="cert_nome">${c.emissao.certificado_pfx ? "Certificado A1 cadastrado nesta empresa — clique para trocar" : "Selecionar certificado digital A1 (.pfx)"}</b><small>O arquivo é copiado só para a pasta desta empresa; nenhuma outra empresa tem acesso.</small></span></label>
      <label>Senha do certificado<input type="password" id="cert_senha" autocomplete="new-password" placeholder="${c.emissao.certificado_senha ? "•••••• (já cadastrada)" : "senha do .pfx"}"></label>
      <button class="btn" id="cert_salvar" type="button">${ic("ok")}Salvar certificado</button></div>
    ${tx("emissao", "serie_dps", "Série da DPS")}${tx("emissao", "proximo_dps", "Próximo nº da DPS", "number")}
    ${ck("emissao", "informar_im", "Informar inscrição municipal")}<label class="inteiro"><span>Lançamento de serviços / emissão de NFS-e — <b>regra geral</b> (a recorrência do cliente pode ter regra própria, que vale primeiro)</span><select data-s="emissao" data-k="nfse_quando">${Object.entries(ST.regras_nomes || {}).map(([v, t]) => `<option value="${v}" ${(ST.regra_geral || "geracao") == v ? "selected" : ""}>${t}</option>`).join("")}</select></label></div>
    <p><button class="btn sec" id="teste_cert">Salvar e testar certificado e conexão</button></p><div id="cert_res"></div></div>
  <div class="card"><h2>Automações de entrada</h2><div class="campos">${ck("automacao", "importar_xml", "Ler XML das notas (clientes, notas emitidas fora, contratos)")}${ck("automacao", "importar_extratos", "Importar extratos .ofx da pasta")}${ck("automacao", "extrato_inter", "Baixar o extrato do Inter pela API")}${ck("automacao", "despesas_do_extrato", "Débitos do extrato viram despesas")}${ck("automacao", "resumo_diario", "Resumo diário por e-mail")}${ck("automacao", "fechamento_mensal", "Fechamento mensal automático")}</div>
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
    <p><button class="btn sec" id="teste_inter">Salvar e testar conexão com o Inter</button></p></div>
  <div class="card"><h2>E-mail (SMTP)</h2><p class="sub">Gmail: servidor smtp.gmail.com, porta 587, e uma “senha de app” da conta Google.</p><div class="campos">${tx("smtp", "host", "Servidor")}${tx("smtp", "porta", "Porta", "number")}${tx("smtp", "usuario", "Usuário")}${tx("smtp", "senha", "Senha", "password")}${tx("smtp", "remetente", "Remetente")}${tx("smtp", "copia_para", "Cópia oculta para")}${ck("smtp", "ssl", "SSL direto (porta 465)")}</div>
    <p><button class="btn sec" id="teste_email">Salvar e enviar e-mail de teste</button></p></div>
  <div class="card"><h2>${ic("contratos")}13º honorário</h2><p class="sub">Em novembro e dezembro, cobra o honorário mensal de cada contrato ativo em parcelas, com NFS-e e boleto, entrando na régua de cobrança.</p>
    <div class="campos">${ck("decimo_terceiro", "ativo", "<b>Cobrar 13º honorário</b>")}${ck("decimo_terceiro", "emitir_nfse", "Emitir NFS-e das parcelas")}
    <label>Descrição na nota<input data-s="decimo_terceiro" data-k="descricao" value="${esc(c.decimo_terceiro.descricao || "")}"></label>
    ${c.decimo_terceiro.parcelas.map((p, j) => `<label>Parcela ${j + 1}: % do honorário<input data-p13="${j}" data-c="percentual" value="${esc(p.percentual)}"></label><label>Parcela ${j + 1}: vencimento (dd/mm)<input data-p13="${j}" data-c="vencimento" value="${esc(p.vencimento)}" placeholder="30/11"></label>`).join("")}</div></div>
  <div class="card"><h2>Financeiro</h2><div class="campos">${tx("financeiro", "dia_vencimento_padrao", "Dia de vencimento padrão", "number")}${tx("financeiro", "dia_geracao", "Dia de gerar a recorrência", "number")}${tx("financeiro", "prazo_avulso_dias", "Prazo da nota avulsa (dias)", "number")}
    ${tx("financeiro", "aliquota_simples_pct", "Alíquota DAS sem histórico (%)")}${ck("financeiro", "iss_fixo", "ISS fixo fora do DAS (escritório contábil)")}${tx("financeiro", "iss_fixo_mensal", "ISS fixo por mês (R$, para a DRE)")}${tx("financeiro", "contas_bancarias", "Contas bancárias desta empresa (banco-agência-conta)")}${tx("financeiro", "categorias_despesa", "Categorias de despesa")}</div></div>`;
  const salvarTudo = async () => {
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
    const cred = {};
    $$("[data-cred]").forEach(i => cred[i.dataset.cred] = i.value);
    await api("config/salvar", novo); await api("empresa/credenciais/salvar", cred);
    await carregarEstado(); return true;
  };
  $("#salvar").onclick = async () => { if (await salvarTudo()) aviso("Configurações salvas ✔"); };
  $("#novo_serv").onclick = () => editarServico({}); ligarServicos();
  // Regras fiscais: só os campos que o regime escolhido exige (atualiza ao trocar o regime)
  const VIS_CFG = { reg_ap_trib_sn: "simples", reg_esp_trib: "!mei", iss_retido: "!mei", aliquota_iss_retido: "simples iss_retido=1",
    ret_irrf_pct: "regular", ret_pis_pct: "regular", ret_cofins_pct: "regular", ret_csll_pct: "regular", ret_inss_pct: "simples,regular",
    p_tot_fed: "tot_trib_modo=percentual", p_tot_est: "tot_trib_modo=percentual", p_tot_mun: "tot_trib_modo=percentual",
    pis_cofins_cst: "regular", p_pis: "regular", p_cofins: "regular", cst_reg: "simples", class_trib_reg: "simples",
    c_cred_pres: "regular", p_dif_uf: "regular", p_dif_mun: "regular", p_dif_cbs: "regular", incentivo_fiscal: "municipal", das_mei_mensal: "mei", presuncao_pct: "presumido" };
  const rf = $("#regras_fiscais"), selReg = $('[data-s="fiscal"][data-k="regime"]', rf);
  $$("[data-k]", rf).forEach(i => { const v = VIS_CFG[i.dataset.k]; if (v) (i.closest("label") || i).dataset.vis = v; });
  const atuReg = () => aplicarVis(rf, ctxFiscal({ regime: selReg.value }));
  $$("[data-k]", rf).forEach(i => i.addEventListener("change", atuReg)); atuReg();
  listarBackups(); cartaoPin($("#card_pin"));
  $("#bk_criar").onclick = async () => { if (!await salvarTudo()) return; aviso("Gerando o backup…", 30000); const r = await api("backup/criar");
    aviso(`Backup criado ✔ ${r.nome} (${tamanho(r.tamanho)})${r.copia ? " · cópia em " + r.copia : ""}`, 8000); listarBackups(); };
  $("#bk_pasta").onclick = () => api("backup/abrir_pasta");
  $("#bk_arq").onchange = async e => { const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    if (!confirm(`Restaurar o backup ${f.name}?\n\nOs dados da empresa dona deste backup voltam ao estado dele. Antes disso, o estado atual é salvo num backup automático.`)) return;
    const senha = f.name.endsWith(".protegido") ? prompt("Senha deste backup:") : "";
    if (senha === null) return;
    aviso("Restaurando…", 60000); const b64 = await new Promise((ok, erro) => { const r = new FileReader(); r.onload = () => ok(r.result); r.onerror = erro; r.readAsDataURL(f); });
    const r = await api("backup/restaurar_arquivo", { arquivo: b64, senha }); await posRestauracao(r); };
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
  $("#busca_ant").onclick = () => { $("#migra_cfg").innerHTML = '<div class="msg">Procurando…</div>'; mostrarMigracao($("#migra_cfg"), true); };
  $("#teste_cert").onclick = async () => { if (!await salvarTudo()) return;
    $("#cert_res").innerHTML = '<div class="msg">Abrindo o certificado e consultando o ADN…</div>';
    try { const r = await api("nacional/testar");
      $("#cert_res").innerHTML = `<div class="msg ${r.conexao && !r.vencido ? "ok" : "erro"}"><b>${esc(r.titular)}</b> — CNPJ ${fmtDoc(r.cnpj || "")} — válido até ${r.validade} (${r.dias_restantes} dias)<br>${esc(r.mensagem)}${r.convenio ? "<br>Convênio do município: " + esc(JSON.stringify(r.convenio)) : ""}</div>`;
    } catch (e) { $("#cert_res").innerHTML = ""; }
  };
  $("#teste_inter").onclick = async () => { if (!await salvarTudo()) return; const r = await api("inter/testar"); aviso(r.mensagem || "OK", 6000); };
  $("#imp_xml").onclick = async () => { aviso("Lendo XML…"); const r = await api("importacao/xml"); aviso(`XML: ${JSON.stringify(r)}`, 8000); await carregarEstado(); };
  $("#env_res").onclick = async () => { const r = await api("resumo/enviar"); aviso("Resumo: " + r.resultado, 6000); };
  $("#teste_email").onclick = async () => { const p = prompt("Enviar teste para qual e-mail?", (c.resumo || {}).email_dono || ""); if (!p) return;
    if (!await salvarTudo()) return; aviso("Configurações salvas. Enviando o e-mail de teste…", 20000);
    await api("email/testar", { para: p }); aviso("E-mail de teste enviado ✔ Confira a caixa de entrada (e o spam).", 7000); };
};

// ---------------------------------------------------------------- PIN de acesso
function telaPin() {
  if ($("#tela_pin")) return;
  const d = document.createElement("div");
  d.id = "tela_pin"; d.className = "tela-pin";
  d.innerHTML = `<form class="caixa-pin" autocomplete="off"><h1>${ic("cadeado")} Sistema bloqueado</h1>
    <p class="sub">Digite o PIN de acesso para abrir o financeiro e as notas fiscais.</p>
    <label>PIN<input id="pin_v" type="password" inputmode="numeric" maxlength="8" autocomplete="current-password" autofocus></label>
    <p id="pin_msg" class="sub"></p><button class="btn" type="submit">Entrar</button></form>`;
  document.body.appendChild(d);
  $("#pin_v").focus();
  $("form", d).onsubmit = async e => { e.preventDefault();
    const r = await (await fetch("/api/acesso/entrar", { method: "POST", body: JSON.stringify({ pin: $("#pin_v").value }) })).json();
    if (r.ok) location.reload(); else { $("#pin_msg").textContent = r.erro; $("#pin_v").value = ""; $("#pin_v").focus(); } };
}
async function cartaoPin(box) {
  const st = await api("acesso/estado");
  box.innerHTML = `<h2>${ic("cadeado")}Acesso à tela (PIN)</h2>
    <p class="sub">${st.ativo ? `🔒 PIN <b>ativo</b>: a tela pede o PIN ao abrir e depois de ${st.minutos} minutos sem uso. Vale para todas as empresas deste computador; o robô continua rodando normalmente.` : "Sem PIN: qualquer pessoa com acesso a este computador abre o sistema. Defina um PIN de 4 a 8 números para proteger os dados."}</p>
    <div class="campos">${st.ativo ? '<label>PIN atual<input type="password" id="pin_atual" inputmode="numeric" maxlength="8" autocomplete="off"></label>' : ""}
      <label>${st.ativo ? "Novo PIN" : "PIN"}<input type="password" id="pin_novo" inputmode="numeric" maxlength="8" autocomplete="new-password" placeholder="4 a 8 números"></label>
      <label>Bloquear após (minutos sem uso)<input type="number" id="pin_min" min="5" max="1440" value="${st.minutos}"></label></div>
    <p><button class="btn" type="button" id="pin_salvar">${st.ativo ? "Trocar PIN" : "Ativar PIN"}</button>
      ${st.ativo ? '<button class="btn sec" type="button" id="pin_remover">Remover PIN</button> <button class="btn sec" type="button" id="pin_bloq">Bloquear agora</button>' : ""}</p>`;
  const enviar = async novo => { const r = await api("acesso/definir", { atual: ($("#pin_atual") || {}).value || "", novo, minutos: $("#pin_min").value });
    if (r.sucesso === false) return aviso("⚠ " + r.erro, 6000);
    aviso(r.ativo ? "PIN salvo ✔" : "PIN removido", 5000); cartaoPin(box); };
  $("#pin_salvar", box).onclick = () => { const n = $("#pin_novo").value.trim(); if (!/^\d{4,8}$/.test(n)) return aviso("O PIN deve ter de 4 a 8 números."); enviar(n); };
  if ($("#pin_remover", box)) $("#pin_remover", box).onclick = () => { if (confirm("Remover o PIN? O sistema abre sem pedir senha.")) enviar(""); };
  if ($("#pin_bloq", box)) $("#pin_bloq", box).onclick = async () => { await api("acesso/sair"); location.reload(); };
}

// ---------------------------------------------------------------- início
(async () => {
  const st = await (await fetch("/api/acesso/estado", { method: "POST", body: "{}" })).json();
  if (st.ativo && !st.logado) return telaPin();
  await carregarEstado(); const h = location.hash.slice(1); ir(h in PAGINAS ? h : "painel");
})();
