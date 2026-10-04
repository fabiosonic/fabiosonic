// Contas a receber, recorrência, cobrança, contas a pagar e conciliação.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- contas a receber
let FILTRO_REC = "a_receber";
PAGINAS.receber = async el => {
  const comp = (el._comp ?? "");
  const lst = await api("titulos", { filtro: FILTRO_REC, competencia: comp });
  const soma = lst.reduce((a, t) => a + (t.status == "aberto" ? t.total_cent : t.status == "pago" ? t.valor_pago_cent : 0), 0);
  el.innerHTML = `<h1>Contas a receber <span class="acoes"><button class="btn" id="novo_t">${ic("mais")}Título avulso</button><button class="btn sec" id="imp_nitrus" title="Lança os títulos em aberto do relatório de Inadimplência do Nitrus (PDF)">${ic("download")}Importar do Nitrus</button><button class="btn sec" id="pdf_bol">${ic("download")}PDFs dos boletos</button><a class="btn sec" href="/export/titulos.csv">${ic("download")}Exportar CSV</a></span></h1>
  <div class="card"><div class="abas">${[["a_receber", "A receber"], ["atrasado", "Atrasados"], ["juridico", "Jurídico"], ["pago", "Pagos"], ["sem_cobranca", "Sem cobrança"], ["sem_nfse", "Sem NFS-e"], ["cancelado", "Cancelados"], ["todos", "Todos"]].map(([k, t]) => `<button data-f="${k}" class="${k == FILTRO_REC ? "on" : ""}">${t}</button>`).join("")}
    <label style="flex-direction:row;align-items:center;gap:6px;margin-left:auto">Competência <input type="month" id="r_comp" value="${comp}" style="width:160px"></label></div>
    <p class="sub">${lst.length} título(s) · ${brl(soma)}${FILTRO_REC == "juridico" ? " · cobrança jurídica: nenhuma mensagem de cobrança sai para estes títulos; multa e juros continuam correndo e a baixa funciona normalmente" : ""}</p>
    ${tabela([
      { t: "Cliente", f: t => celNome(t.cliente_nome, esc(frase(t.descricao))) },
      { t: "Vencimento", f: t => `<span class="nw">${dt(t.vencimento)}</span><div class="sub nw">comp. ${mes(t.competencia)}</div>` },
      { t: "Valor", n: 1, f: t => num(t.valor_cent) + (t.situacao == "atrasado" ? `<div class="sub">atualizado ${num(t.total_cent)}</div>` : t.status == "pago" ? `<div class="sub">pago ${num(t.valor_pago_cent)} em ${dt(t.data_pagamento)}</div>` : "") },
      { t: "Situação", fsel: 1, fv: t => textoDe(selo(t.situacao)), f: t => selo(t.situacao) + (t.dias_atraso ? `<div class="sub">${t.dias_atraso} dia(s)</div>` : "")
        + (t.situacao == "juridico" ? `<div class="sub">no jurídico desde ${dt(t.juridico_em)}</div>${t.juridico_obs ? `<div class="sub quebra" title="${esc(t.juridico_obs)}">${esc(t.juridico_obs.slice(0, 80))}</div>` : ""}` : "")
        + (t.status == "aberto" && t.cobrar && t.boleto_situacao == "dispensado" ? `<div class="sub">cobrança sem boleto (PIX do escritório)</div>`
          : t.status == "aberto" && t.cobrar && !t.banco_id && !t.pix_copia_cola && !t.linha_digitavel
          ? `<div class="sub neg quebra" title="${esc(t.cobranca_erro || "")}">${t.cobranca_erro ? "boleto não gerado: " + esc(t.cobranca_erro.slice(0, 90)) : "boleto ainda não gerado"}</div>` : "")
        + (t.parcial_status == "pendente" ? `<div>${estadoSelo("atencao", "Pagamento parcial")}</div><div class="sub">faltaram ${brl(t.parcial_dif_cent)}</div>`
          : t.parcial_status == "desconto" ? `<div class="sub">desconto de ${brl(t.parcial_dif_cent)}</div>`
          : t.parcial_status == "cobrar" ? `<div class="sub">saldo de ${brl(t.parcial_dif_cent)} em novo título</div>` : "") },
      { t: "NFS-e", fsel: 1, fv: t => textoDe(selo(t.nfse_status)), f: t => selo(t.nfse_status) + (t.nfse_numero ? `<div class="sub">${t.nfse_link && t.nfse_link.startsWith("http") ? `<a href="${esc(t.nfse_link)}" target="_blank">${esc(t.nfse_numero)}</a>` : esc(t.nfse_numero)}</div>` : "") + (t.nfse_erro ? `<div class="sub" title="${esc(t.nfse_erro)}">${esc(t.nfse_erro.slice(0, 60))}…</div>` : "") },
      { t: "Ações", f: t => acoesTitulo(t) }], lst, "Nada por aqui.",
      { filtros: "receber", soma: t => t.status == "aberto" ? t.total_cent : t.status == "pago" ? t.valor_pago_cent : 0 })}</div>`;
  $$(".abas button", el).forEach(b => b.onclick = () => { FILTRO_REC = b.dataset.f; ir("receber"); });
  $("#r_comp").onchange = e => { el._comp = e.target.value; ir("receber"); };
  $("#novo_t").onclick = novoTitulo;
  $("#imp_nitrus").onclick = importarNitrus;
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
  if (t.parcial_status == "pendente") prin.push(`<button class="btn min" onclick="decidirParcial(${t.id})" title="O cliente pagou menos que o devido">Decidir diferença</button>`);
  if (t.status == "aberto" && t.situacao == "juridico") {
    prin.push(`<button class="btn min" onclick="baixar(${t.id},${t.total_cent})">Baixar</button>`);
    mais.push(it(`${ic("receber")}Voltar do jurídico (retomar a cobrança)`, `voltarJuridico(${t.id})`));
    if (t.banco_id) mais.push(`<a href="/boleto/${t.id}.pdf" target="_blank">${ic("download")}Boleto em PDF</a>`);
  } else if (t.status == "aberto") {
    prin.push(`<button class="btn min" onclick="baixar(${t.id},${t.total_cent})">Baixar</button>`);
    if (t.situacao != "sem_cobranca") mais.push(it(`${ic("bloqueio")}Enviar para o jurídico (suspende a cobrança)`, `enviarJuridico(${t.id},'${esc(t.cliente_nome).replace(/'/g, "\\'")}')`));
    const semBoleto = !t.banco_id && !t.pix_copia_cola && !t.linha_digitavel && t.boleto_situacao != "dispensado";
    if (t.boleto_situacao == "dispensado") mais.push(it(`${ic("receber")}Gerar boleto (registra no banco)`, `gerarCobranca(${t.id})`));
    if (t.situacao != "sem_cobranca" && semBoleto) prin.push(`<button class="btn min" onclick="gerarCobranca(${t.id})" title="O boleto ainda não foi gerado: gera agora (boleto/PIX) e coloca na régua">Gerar boleto</button>`)
      && mais.push(it(`${ic("bloqueio")}Tirar da cobrança (manter a nota)`, `tirarDaCobranca(${t.id})`));
    else if (t.situacao == "sem_cobranca") prin.push(`<button class="btn min sec" onclick="gerarCobranca(${t.id})" title="Gera boleto/PIX e coloca na régua">Gerar cobrança</button>`);
    else { prin.push(`<button class="btn min sec" onclick="cobrar(${t.id})">Cobrar</button>`);
      mais.push(it(`${ic("bloqueio")}Tirar da cobrança (manter a nota)`, `tirarDaCobranca(${t.id})`)); }
    if (t.banco_id) mais.push(`<a href="/boleto/${t.id}.pdf" target="_blank">${ic("download")}Boleto em PDF</a>`);
    if (ST.config.cobranca.cartao_provedor) { mais.push(it(`${ic("receber")}Pagar com cartão (link)`, `linkCartao(${t.id},${t.valor_cent})`));
      if (t.cartao_link) prin.push(`<button class="btn min sec" onclick="pagoCartao(${t.id})" title="O cliente pagou pelo link da InfinitePay">Pago no cartão</button>`); }
    if (["pendente", "erro", "teste"].includes(t.nfse_status)) mais.push(it(`${ic("nota")}Emitir NFS-e`, `emitirTitulo(${t.id})`));
  }
  if (t.status == "pago") prin.push(`<button class="btn min sec" onclick="estornar(${t.id})">Estornar</button>`);
  if (t.status == "aberto") mais.unshift(it(`${ic("editar")}Editar título (valor, vencimento…)`, `editarTitulo(${t.id})`));
  mais.push(it(`${ic("relogio")}Histórico`, `historicoTitulo(${t.id})`));
  if (t.status == "aberto") mais.push(it(`${ic("x")}Cancelar título`, `cancelarTitulo(${t.id},'${t.nfse_status}')`).replace("<button", '<button class="perigo"'));
  return `<div class="acoes-linha">${prin.join("")}<details class="menu-acoes"><summary class="btn min sec" title="Mais ações">Mais</summary><div class="pop">${mais.join("")}</div></details></div>`;
}
async function baixar(id, total) {
  modal(`<h2>Dar baixa</h2><p class="sub">Valor devido hoje: <b>${brl(total)}</b></p><div class="campos" id="fb"><label>Data do pagamento<input type="date" name="data" value="${hojeISO()}"></label>
    <label>Valor recebido (R$)<input name="valor" value="${num(total)}"></label>
    <label>Forma<select name="forma"><option>pix</option><option>boleto</option><option>transferencia</option><option>dinheiro</option><option>cartao</option></select></label></div>
    <div id="fb_parcial" class="bloco-modal" hidden><b>Pagamento parcial</b> — faltam <b id="fb_dif"></b>. O que fazer com a diferença?
      <label class="chk"><input type="radio" name="fb_dec" value="cobrar" checked> Gerar uma conta a receber com a diferença e continuar cobrando (novo boleto atualizado)</label>
      <label class="chk"><input type="radio" name="fb_dec" value="desconto"> Conceder a diferença como desconto</label>
      <div class="sub">A nota fiscal sai só pelo valor pago; cobrando a diferença, o restante dos honorários sai na nota do saldo.</div></div>
    <p class="sub">Se a nota fiscal deste título ainda não saiu (emissão após o pagamento), ela é emitida na hora, ao confirmar.</p>
    <p><button class="btn" id="ok">Confirmar baixa</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  const dif = () => total - Math.round(parseFloat(String($("#fb [name=valor]").value).replace(/\./g, "").replace(",", ".")) * 100 || 0);
  const ver = () => { const d = dif(); $("#fb_parcial").hidden = !(d > 1); $("#fb_dif").textContent = brl(d); };
  $("#fb [name=valor]").oninput = ver; ver();
  $("#ok").onclick = async () => { $("#ok").disabled = true; $("#ok").textContent = "Registrando a baixa e emitindo a nota…";
    const parcial = dif() > 1 ? ($("[name=fb_dec]:checked") || {}).value : "";
    const r = await api("titulo/baixar", { id, ...form($("#fb")), parcial }); fechar();
    aviso("Baixa registrada ✔" + (r.aviso ? " " + r.aviso : "") + (r.nfse_resultado ? " " + r.nfse_resultado : ""), r.nfse_resultado || r.aviso ? 10000 : 4000); ir(PAG); };
}
function notaTxt(t, cobrar) {      // o que acontece com a NFS-e: só o valor pago entra na nota
  if (t.nfse_status == "emitida") return " (a nota já emitida não muda)";
  const base = t.nota_cent || t.valor_cent, nota = Math.min(t.valor_pago_cent, base), resto = base - nota;
  return ` (a nota sai por ${brl(nota)}, o valor pago${cobrar && resto > 0 ? `; os ${brl(resto)} restantes dos honorários saem na nota do saldo, quando ele for pago` : ""})`;
}
async function decidirParcial(id) {
  const t = (await api("titulos", { filtro: "todos" })).find(x => x.id == id);
  modal(`<h2>Pagamento parcial</h2>
    <p>${esc(nomeCli(t.cliente_nome))} pagou <b>${brl(t.valor_pago_cent)}</b> em ${dt(t.data_pagamento)}, mas o devido era <b>${brl(t.valor_pago_cent + t.parcial_dif_cent)}</b>.
      Faltaram <b>${brl(t.parcial_dif_cent)}</b>. O que fazer com a diferença?</p>
    <div class="bloco-modal"><label class="chk"><input type="radio" name="pd" value="cobrar" checked> <span><b>Cobrar a diferença</b>: cria uma conta a receber de ${brl(t.parcial_dif_cent)} e continua cobrando o cliente com boleto atualizado${notaTxt(t, true)}</span></label>
      <label class="chk"><input type="radio" name="pd" value="desconto"> <span><b>Conceder desconto</b>: a diferença é perdoada${notaTxt(t, false)}</span></label></div>
    <p><button class="btn" id="pd_ok">Confirmar</button> <button class="btn sec" onclick="fechar()">Decidir depois</button></p>`);
  $("#pd_ok").onclick = async () => { $("#pd_ok").disabled = true;
    const r = await api("titulo/parcial", { id, decisao: $("[name=pd]:checked").value }); fechar();
    aviso([r.aviso, r.nfse_resultado].filter(Boolean).join(" "), 10000); ir(PAG); };
}
async function linkCartao(id, valor) {
  modal(`<h2>Pagamento com cartão de crédito</h2>
    <div id="lc_sim" class="msg">Calculando…</div><p class="sub">As taxas ficam por conta do cliente: a do crédito à vista já está no valor; no parcelamento, ele escolhe as parcelas na InfinitePay e paga os juros.</p>
    <p><button class="btn" id="lc_ok">Gerar link</button> <button class="btn sec" onclick="fechar()">Fechar</button></p><div id="lc_res"></div>`);
  const x = await api("cartao/simular", { valor: valor / 100 });
  $("#lc_sim").innerHTML = `Honorário ${brl(x.valor_cent)} · no cartão <b>${brl(x.total_cent)}</b> · acréscimo ${brl(x.acrescimo_cent)} (taxa ${String(x.taxa_pct).replace(".", ",")}%${x.taxa_fixa_cent ? " + " + brl(x.taxa_fixa_cent) : ""})`;
  $("#lc_ok").onclick = async () => { $("#lc_ok").disabled = true;
    try { const r = await api("titulo/cartao", { id });
      $("#lc_res").innerHTML = `<div class="msg ok">Link ${r.reaproveitado ? "(já existia)" : "criado"}: <a href="${esc(r.link)}" target="_blank">${esc(r.link)}</a>
        <p><button class="btn min sec" type="button" onclick="navigator.clipboard.writeText('${esc(r.link)}');aviso('Link copiado')">Copiar link</button></p></div>`;
    } finally { $("#lc_ok").disabled = false; } };
}
async function pagoCartao(id) {
  const t = (await api("titulos", { filtro: "todos" })).find(x => x.id == id) || {};
  modal(`<h2>Pago no cartão (InfinitePay)</h2><p class="sub">${esc(t.cliente_nome || "")} — honorário ${brl(t.valor_cent)}${t.cartao_total_cent ? ` · valor do link ${brl(t.cartao_total_cent)}` : ""}</p>
    <div class="campos" id="fpc"><label>Data do pagamento<input type="date" name="data" value="${hojeISO()}"></label>
    <label>Valor pago no cartão (R$)<input name="valor" value="${num(t.cartao_total_cent || t.valor_cent)}"></label>
    <label class="inteiro">Link do comprovante (opcional — com ele o sistema confere o pagamento na InfinitePay)<input name="comprovante" placeholder="cole aqui o link recebido da InfinitePay"></label></div>
    <p class="sub">A taxa do cartão é lançada em contas pagas (Bancárias), o boleto é cancelado e, se a nota ainda não saiu, ela é emitida pelo valor pago.</p>
    <p><button class="btn" id="ok">Confirmar pagamento</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { const r = await api("titulo/pago_cartao", { id, ...form($("#fpc")) }); fechar();
    aviso(`Pagamento no cartão registrado ✔ Taxa ${brl(r.taxa_cent)} lançada em despesas${r.conferido ? " · conferido na InfinitePay" : ""}.`, 8000); ir(PAG); };
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
async function enviarJuridico(id, nome) {
  modal(`<h2>Enviar para o jurídico</h2><p>Cliente: <b>${esc(nome)}</b></p>
    <p class="sub">A cobrança por e-mail e WhatsApp é <b>suspensa na hora</b> (mensagens pendentes são canceladas e a régua não mexe mais no título). O valor continua registrado, com multa e juros correndo, na aba <b>Jurídico</b> do contas a receber. O boleto que já existe não é cancelado: se o cliente pagar, a baixa cai normalmente.</p>
    <div class="campos" id="fj"><label class="chk"><input type="checkbox" name="todos" checked> Enviar <b>todos os títulos em aberto</b> deste cliente</label>
    <label>Observação (advogado, nº do processo, acordo…)<input name="obs" maxlength="300" placeholder="opcional"></label></div>
    <p><button class="btn" id="ok">Enviar para o jurídico</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { $("#ok").disabled = true;
    const r = await api("titulo/juridico", { id, obs: $("#fj [name=obs]").value, todos: $("#fj [name=todos]").checked }); fechar();
    aviso(`${r.titulos} título(s) enviado(s) ao jurídico ✔ Cobrança suspensa${r.suspensos ? ` (${r.suspensos} mensagem(ns) pendente(s) cancelada(s))` : ""}.`, 8000);
    FILTRO_REC = "juridico"; ir("receber"); };
}
async function voltarJuridico(id) {
  if (!confirm("Tirar este título do jurídico e voltar a cobrar normalmente por e-mail e WhatsApp?")) return;
  await api("titulo/juridico_voltar", { id }); aviso("Título voltou para a cobrança normal ✔", 5000); ir(PAG);
}
async function gerarCobranca(id) {
  if (!confirm("Gerar a cobrança (boleto/PIX) deste título e colocá-lo na régua?")) return;
  const t = await api("titulo/gerar_cobranca", { id });
  aviso(t.banco_id ? "Boleto gerado ✔" : t.pix_copia_cola ? "PIX gerado ✔ (configure o Inter para boleto)" : "Não foi possível gerar: configure o Banco Inter ou a chave PIX em Configurações.", 8000); ir(PAG);
}
async function cobrar(id) {
  const r = await api("titulo/cobrar", { id });
  modal(`<h2>Cobrança</h2>${r.email ? `<div class="msg ok">E-mail enviado para ${esc(r.email)}</div>` : '<div class="msg">E-mail não enviado (cliente sem e-mail ou SMTP não configurado).</div>'}
    ${r.whatsapp_enviado ? `<div class="msg ok">WhatsApp enviado automaticamente para ${esc(r.whatsapp_enviado)}</div>` : r.whatsapp_erro ? `<div class="msg erro">WhatsApp não enviado: ${esc(r.whatsapp_erro)}</div>` : ""}
    ${r.whatsapp && !r.whatsapp_enviado ? `<p><a class="btn" href="${esc(r.whatsapp)}" target="_blank">Abrir no WhatsApp</a></p>` : !r.whatsapp ? '<p class="sub">Cliente sem telefone para WhatsApp.</p>' : ""}
    ${r.pdf ? `<p class="sub">PDF do boleto para anexar no WhatsApp: ${esc(r.pdf)} <button class="btn min sec" onclick="api('boletos/abrir_pasta')">Abrir pasta</button> <a class="btn min sec" href="/boleto/${id}.pdf" target="_blank">Ver PDF</a></p>` : ""}
    <label>Mensagem<textarea rows="12" id="txt">${esc(r.texto)}</textarea></label>
    <p><button class="btn sec" onclick="navigator.clipboard.writeText($('#txt').value);aviso('Copiado')">Copiar texto</button> <button class="btn sec" onclick="fechar()">Fechar</button></p>`);
}
async function historicoTitulo(id) {
  const h = await api("titulo/historico", { id });
  modal(`<h2>Histórico de cobrança</h2>${tabela([{ t: "Data", f: e => dt(e.data) }, { t: "Etapa", f: e => e.etapa < 0 ? `${-e.etapa} dia(s) antes` : e.etapa == 0 ? "no vencimento" : `${e.etapa} dia(s) após` }, { t: "Canal", f: e => e.canal }, { t: "Status", f: e => selo(e.status) }], h, "Nenhuma cobrança enviada ainda.")}<p><button class="btn sec" onclick="fechar()">Fechar</button></p>`);
}
async function editarTitulo(id) {
  const t = (await api("titulos", { filtro: "todos" })).find(x => x.id == id); if (!t) return aviso("Título não encontrado.");
  const temBoleto = !!t.banco_id, temPix = !!t.pix_copia_cola && !temBoleto;
  modal(`<h2>Editar título</h2><p class="sub">${esc(t.cliente_nome)} · ${esc(frase(t.descricao))}</p><div class="campos" id="fe">
    <label>Valor (R$)<input name="valor" value="${num(t.valor_cent)}" ${t.nfse_status == "emitida" ? 'disabled title="NFS-e já emitida com este valor"' : ""}></label>
    <label>Vencimento<input type="date" name="vencimento" value="${t.vencimento}"></label>
    <label>Competência<input type="month" name="competencia" value="${t.competencia}" ${t.nfse_status == "emitida" ? "disabled" : ""}></label>
    <label class="inteiro">Descrição<input name="descricao" value="${esc(t.descricao)}"></label></div>
    ${t.nfse_status == "emitida" ? '<p class="sub">A NFS-e deste título já foi emitida: o valor e a competência não mudam (cancele ou substitua a nota primeiro).</p>' : ""}
    ${temBoleto ? '<p class="sub"><b>Boleto:</b> se o valor ou o vencimento mudar, o boleto atual é <b>cancelado no banco</b> (o cliente não pode pagar o valor antigo) e um novo é registrado com os dados corretos. O PDF antigo é descartado e a próxima cobrança já vai com o boleto novo.</p>' : temPix ? '<p class="sub">O PIX copia e cola é regerado com o novo valor.</p>' : ""}
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button></p>`);
  $("#ok").onclick = async () => { $("#ok").disabled = true; $("#ok").textContent = temBoleto ? "Salvando e refazendo o boleto…" : "Salvando…";
    const f = form($("#fe")); const r = await api("titulo/editar", { id, ...f }); fechar();
    aviso(!r.mudou.length ? "Nada mudou." : "Título atualizado ✔" + (r.boleto_refeito ? " Boleto antigo cancelado e novo boleto registrado no Inter." : r.refazer && temBoleto ? " O boleto antigo foi cancelado; o novo ainda não foi registrado (veja a situação na lista)." : ""), 9000); ir(PAG); };
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
  L.forEach(l => { l.valor_original = l.valor_cent; });     // para saber, ao salvar, quais valores mudaram
  const CURTO = { geracao: "Emitir na geração", baixa: "Emitir na baixa (pago)", lancar: "Só lançar, sem NFS-e", nada: "Não emitir e não lançar" };
  const regraOpts = sel => `<option value="" ${!sel ? "selected" : ""} title="Regra geral: ${esc(CURTO[r.regra_geral] || r.regra_geral)}">Regra geral</option>` + Object.entries(r.regras).map(([v, t]) => `<option value="${v}" title="${esc(t)}" ${sel == v ? "selected" : ""}>${CURTO[v] || t}</option>`).join("");
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
      { t: "Cliente", f: l => celNome(l.cliente_nome, `${fmtDoc(l.cpf_cnpj)}${l.id && !l.repetir ? " · a confirmar" : ""}${l.fim ? " · até " + mes(l.fim) : ""}`) },
      { t: "Valor mensal (R$)", f: l => `<input class="rc" data-c="valor" data-k="${chave(l)}" inputmode="decimal" style="width:96px" value="${l.valor_cent ? num(l.valor_cent) : ""}" placeholder="0,00">${l.ajustes_mes ? `<div class="sub nw" title="Acréscimos e descontos deste mês (botão Mais)">${l.ajustes_mes > 0 ? "+" : "−"} ${num(Math.abs(l.ajustes_mes))} este mês</div>` : ""}` },
      { t: "Início · Fim", f: l => `<div class="par"><label><small>início</small>${`<input class="rc" data-c="inicio" data-k="${chave(l)}" type="month" value="${l.inicio || ""}" title="Mês do primeiro título">`}</label><label><small>fim</small>${`<input class="rc" data-c="fim" data-k="${chave(l)}" type="month" value="${l.fim || ""}" title="Último mês cobrado: depois dele não gera mais títulos">`}</label></div>` },
      { t: "Vence dia", f: l => `<input class="rc" data-c="dia_vencimento" data-k="${chave(l)}" type="number" min="1" max="31" style="width:58px" value="${l.dia_vencimento}">` },
      { t: "Serviço · Nota fiscal", f: l => `<div class="par">${`<select class="rc" style="width:120px" data-c="servico_id" data-k="${chave(l)}">${(ST.servicos || []).length > 1 ? opcoesServ(l.servico_id || "", "Habitual do cliente") : opcoesServ(l.servico_id || "", "Padrão")}</select>`}${`<select class="rc" style="width:150px" data-c="nfse_quando" data-k="${chave(l)}">${regraOpts(l.nfse_quando || "")}</select>`}</div>` },
      { t: "Boleto/PIX", f: l => `<input type="checkbox" class="rc" data-c="cobrar" data-k="${chave(l)}" ${l.cobrar === 0 ? "" : "checked"} aria-label="Gerar cobrança (boleto/PIX)">` },
      { t: "", f: l => l.id ? `<button class="btn min sec" data-ed="${l.id}" title="Início, fim, reajuste, descrição">Mais</button>` : "" }],
      vis, "Nenhum cliente neste filtro.");
    $$(".rc", el).forEach(i => i.onchange = i.oninput = () => { const l = L.find(x => chave(x) == i.dataset.k);
      l[i.dataset.c] = i.type == "checkbox" ? i.checked : i.value; if (i.dataset.c == "valor") l.valor_cent = Math.round(valorNum(i.value) * 100);
      if (i.dataset.c == "repetir" && i.checked && !l.valor_cent) aviso("Informe o valor mensal deste cliente.");
      alterados.add(i.dataset.k); $("#rc_alt").textContent = `${alterados.size} alteração(ões) não salva(s) — clique em “Salvar alterações”.`; });
    if ($("#rc_todos")) $("#rc_todos").onclick = e => { $$('.rc[data-c="repetir"]', el).forEach(x => { if (x.checked != e.target.checked) { x.checked = e.target.checked; x.onchange(); } }); };
    $$("[data-ed]", el).forEach(b => b.onclick = () => editarContrato(L.find(l => l.id == b.dataset.ed)));
  };
  $("#rc_f").oninput = desenhar; desenhar();
  $$("[data-rf]", el).forEach(b => b.onclick = () => { FILTRO_RECOR = b.dataset.rf; $$("[data-rf]", el).forEach(x => x.classList.toggle("on", x == b)); desenhar(); });
  $("#rc_salvar").onclick = async () => {
    const linhas = L.filter(l => alterados.has(chave(l))).map(l => ({ id: l.id, cpf_cnpj: l.cpf_cnpj, valor_cent: l.valor_cent, dia_vencimento: Number(l.dia_vencimento),
      servico_id: l.servico_id || "", nfse_quando: l.nfse_quando || "", cobrar: l.cobrar !== false && l.cobrar !== 0, repetir: !!l.repetir,
      inicio: l.inicio || "", fim: l.fim || "" }));
    if (!linhas.length) return aviso("Nada para salvar.");
    if (linhas.some(l => l.repetir && !l.valor_cent)) return aviso("Há cliente marcado para repetir sem valor mensal.");
    const novos = linhas.filter(l => l.repetir && !(L.find(x => x.id && x.id == l.id) || {}).confirmado).length;
    if (novos && !confirm(`${novos} cliente(s) passam a ser faturados todo mês a partir deste mês. Confirmar?`)) return;
    const mudouValor = linhas.filter(l => l.id && (L.find(x => x.id == l.id) || {}).valor_original !== undefined && L.find(x => x.id == l.id).valor_original != l.valor_cent).length;
    const aplicar = mudouValor > 0 && confirm(`${mudouValor} recorrência(s) com valor alterado. Aplicar o novo valor também aos títulos EM ABERTO já gerados deste mês em diante?\n\nO boleto desses títulos é cancelado no banco e refeito com o valor novo. Títulos com NFS-e emitida não mudam.`);
    const x = await api("recorrencia/salvar", { linhas, aplicar_abertos: aplicar }); aviso(`${x.salvos} recorrência(s) salva(s) ✔` + (x.titulos_ajustados && x.titulos_ajustados.length ? ` ${x.titulos_ajustados.length} título(s) em aberto atualizado(s) com boleto refeito.` : ""), 8000); await carregarEstado(); ir("contratos"); };
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
    ${c.id ? `<h3 class="bloco-modal">Acréscimos e descontos</h3><p class="sub">Somados ao valor mensal no título do mês (e na NFS-e). Único = só no mês de início; recorrente = do início ao fim (sem fim = até ser excluído).</p>
      <div id="aj_lista"><p class="sub">Carregando…</p></div>
      <div class="campos aj-novo"><label>Tipo<select id="aj_tipo"><option value="acrescimo">Acréscimo (+)</option><option value="desconto">Desconto (−)</option></select></label>
        <label>Descrição<input id="aj_desc" maxlength="80" placeholder="ex.: Alteração contratual"></label><label>Valor (R$)<input id="aj_valor" inputmode="decimal" placeholder="0,00"></label>
        <label>Lançamento<select id="aj_unico"><option value="1">Único (só no mês de início)</option><option value="0">Recorrente</option></select></label>
        <label>Mês de início<input id="aj_ini" type="month" value="${hojeISO().slice(0, 7)}"></label><label>Mês final<input id="aj_fim" type="month" disabled></label>
        <p class="inteiro" style="margin:0"><button class="btn sec" id="aj_add" type="button">${ic("mais")}Incluir</button></p></div>` : `<p class="sub">Depois de salvar, abra em “Mais” para incluir acréscimos e descontos.</p>`}
    <p><button class="btn" id="ok">Salvar</button> <button class="btn sec" onclick="fechar()">Voltar</button>${c.id ? ` <button class="btn sec" onclick="fechar();encerrar(${c.id})">${ic("x")}Tirar da recorrência</button>` : ""}</p>`);
  $("#fc_serv").onchange = e => { if (e.target.value) $("#fc [name=descricao]").value = servDe(e.target.value).descricao || ""; };
  if (c.id) {
    const lista = async () => { const a = await api("contrato/ajustes", { id: c.id });
      $("#aj_lista").innerHTML = tabela([{ t: "Tipo", f: x => x.tipo == "acrescimo" ? '<span class="selo alerta">+ acréscimo</span>' : '<span class="selo bom">− desconto</span>' },
        { t: "Descrição", f: x => esc(x.descricao) }, { t: "Valor", n: 1, f: x => num(x.valor_cent) },
        { t: "Período", f: x => x.fim == x.inicio ? `só ${mes(x.inicio)}` : `${mes(x.inicio)} → ${x.fim ? mes(x.fim) : "sem fim"}` },
        { t: "", f: x => `<button class="btn min sec ico perigo-txt" type="button" data-ajx="${x.id}" title="Excluir" aria-label="Excluir">${ic("lixeira")}</button>` }], a, "Nenhum acréscimo ou desconto.");
      $$("[data-ajx]").forEach(b => b.onclick = async () => { await api("contrato/ajuste_excluir", { id: b.dataset.ajx }); lista(); }); };
    lista();
    $("#aj_unico").onchange = e => { $("#aj_fim").disabled = e.target.value == "1"; if (e.target.value == "1") $("#aj_fim").value = ""; };
    $("#aj_add").onclick = async () => {
      await api("contrato/ajuste_salvar", { contrato_id: c.id, tipo: $("#aj_tipo").value, descricao: $("#aj_desc").value, valor: $("#aj_valor").value,
        unico: $("#aj_unico").value == "1", inicio: $("#aj_ini").value, fim: $("#aj_fim").value });
      $("#aj_desc").value = ""; $("#aj_valor").value = ""; aviso("Incluído ✔"); lista(); };
  }
  $("#ok").onclick = async () => { const f = form($("#fc")); f.cpf_cnpj = docDe(f.cliente); if (c.id) f.id = c.id; const k = await api("contrato/salvar", f); fechar();
    let extra = "";
    if (c.id && c.valor_cent && k.valor_cent != c.valor_cent) {
      const ab = await api("contrato/abertos", { id: c.id });
      if (ab.titulos.length && confirm(`Há ${ab.titulos.length} título(s) em aberto já gerado(s) com o valor antigo. Aplicar o novo valor a eles (boleto cancelado no banco e refeito)?`)) {
        const r = await api("contrato/aplicar_abertos", { id: c.id }); extra = ` ${r.titulos.length} título(s) atualizado(s)${r.boletos ? `, ${r.boletos} boleto(s) refeito(s)` : ""}.`; } }
    aviso("Recorrência salva ✔" + extra, 8000); await carregarEstado(); ir("contratos"); };
}
async function encerrar(id) { if (confirm("Tirar este cliente da recorrência? Ele deixa de gerar cobranças.")) { await api("contrato/excluir", { id }); ir("contratos"); } }

// ---------------------------------------------------------------- cobrança
PAGINAS.cobranca = async el => {
  const [fila, hist, ww] = await Promise.all([api("whatsapp/fila"), api("regua/historico"), api("whatsapp_web/estado")]);
  const c = ST.config.cobranca;
  el.innerHTML = `<h1>Cobrança <span class="acoes"><button class="btn" id="rr">Rodar régua agora</button></span></h1>
  <div class="card"><h2>Régua automática</h2><p>Etapas (dias em relação ao vencimento): <b>${c.regua_dias.map(d => d < 0 ? d : d == 0 ? "0 (vencimento)" : "+" + d).join(" · ")}</b> —
    e-mail ${c.regua_email ? "<b>ligado</b>" : "desligado"}, WhatsApp ${c.regua_whatsapp ? (c.whatsapp_api ? "<b>automático (API oficial)</b>" : ww.ativo ? "<b>automático</b> (WhatsApp do escritório conectado) para os clientes marcados em Clientes › “Cobrar por WhatsApp”" : "<b>ligado</b>, mas o WhatsApp <b>não está conectado</b> — <a href=\"#\" onclick=\"ir('config');return false\">conectar</a>; até lá as mensagens ficam na fila abaixo") : "desligado"}. Multa ${c.multa_pct}% + juros ${c.juros_mes_pct}% a.m. pro rata.
    ${c.envio_horario_comercial !== false ? `Envios só de segunda a sexta, das ${esc(c.envio_hora_inicio || "08:00")} às ${esc(c.envio_hora_fim || "18:00")}.` : "Envios a qualquer hora."}
    <a href="#" onclick="ir('config');return false">Alterar</a></p></div>
  <div class="card"><h2>WhatsApp ainda não enviado (${fila.length}) ${fila.length && ww.ativo ? '<button class="btn" id="wa_auto">Enviar agora</button>' : ""} ${fila.length ? '<button class="btn sec" id="wa_seq">Enviar manualmente em sequência</button>' : ""}</h2>
    <p class="sub">${ww.ativo ? (ww.enviando ? "<b>Enviando agora pelo WhatsApp…</b> " : "") + "O robô envia esta fila sozinho a cada rodada (de hora em hora) e logo depois de “Rodar régua agora”." : "O WhatsApp do escritório não está conectado: estas mensagens saem sozinhas assim que você conectar em Configurações › WhatsApp. Enquanto isso, dá para enviar manualmente em sequência."} Só entram os clientes marcados em Clientes › “Cobrar por WhatsApp”.</p>
    ${tabela([{ t: "Cliente", f: e => celNome(e.cliente_nome) }, { t: "Venc.", f: e => dt(e.vencimento) }, { t: "Valor", n: 1, f: e => num(e.valor_cent) },
      { t: "Etapa", fsel: 1, fv: e => textoDe(nomeEtapa(e.etapa)), f: e => nomeEtapa(e.etapa) },
      { t: "", f: e => `<a class="btn min" href="${esc(e.detalhe)}" target="_blank" onclick="setTimeout(()=>feito(${e.id}),800)">Enviar</a> <button class="btn min sec" onclick="feito(${e.id})">Marcar feito</button>` }], fila, "Nenhuma mensagem pendente ✔", { filtros: "cob_fila" })}</div>
  <div class="card"><h2>Últimos envios</h2>${tabela([{ t: "Data", f: e => dt(e.data) }, { t: "Cliente", f: e => celNome(e.cliente_nome) }, { t: "Etapa", fsel: 1, fv: e => textoDe(nomeEtapa(e.etapa)), f: e => nomeEtapa(e.etapa) }, { t: "Canal", fsel: 1, f: e => e.canal }, { t: "Status", fsel: 1, fv: e => textoDe(selo(e.status)), f: e => selo(e.status) }, { t: "Detalhe", f: e => `<span class="sub">${esc(e.canal == "whatsapp" ? "" : e.detalhe)}</span>` }], hist, "Nenhum envio ainda.", { filtros: "cob_hist" })}</div>`;
  if ($("#wa_seq")) $("#wa_seq").onclick = () => enviarSequencia(fila);
  if ($("#wa_auto")) $("#wa_auto").onclick = async () => { await api("whatsapp_web/enviar_fila"); aviso("Enviando a fila pelo WhatsApp em segundo plano…", 6000); setTimeout(() => ir("cobranca"), 4000); };
  $("#rr").onclick = async () => { const r = await api("regua/rodar"); if (r.fora_do_horario) return aviso(r.fora_do_horario, 9000);
    aviso(`Régua: ${r.email} e-mail(s), ${r.whatsapp} WhatsApp${r.whatsapp_automatico ? " (saindo sozinhos agora)" : ""}, ${r.sem_contato} sem contato, ${r.erros} erro(s)`, 6000); ir("cobranca"); };
};
const nomeEtapa = e => e == -100 ? "envio do boleto" : e == 1001 ? "agradecimento (pago)" : e == 1002 ? "nota fiscal (pago)"
  : e < 0 ? "lembrete" : e == 0 ? "vence hoje" : `+${e} dias`;
function enviarSequencia(fila, i = 0) {
  if (i >= fila.length) { fechar(); aviso("WhatsApp: todas as mensagens da fila foram abertas ✔", 6000); return ir("cobranca"); }
  const e = fila[i];
  modal(`<h2>WhatsApp ${i + 1} de ${fila.length}</h2><p><b>${esc(e.cliente_nome)}</b> — ${brl(e.valor_cent)}, vencimento ${dt(e.vencimento)} (${nomeEtapa(e.etapa)})</p>
    <p class="sub">1) Clique em “Abrir conversa”: o WhatsApp abre com a mensagem pronta. 2) Aperte Enviar lá. 3) Volte e clique em “Enviado, próximo”.</p>
    <p><a class="btn" id="seq_abrir" href="${esc(e.detalhe)}" target="_blank">${ic("fone")}Abrir conversa</a>
      <button class="btn sec" id="seq_ok" type="button">Enviado, próximo</button> <button class="btn sec" id="seq_pula" type="button">Pular</button>
      <button class="btn sec" type="button" onclick="fechar();ir('cobranca')">Parar</button></p>`);
  $("#seq_ok").onclick = async () => { await api("whatsapp/feito", { id: e.id }); enviarSequencia(fila, i + 1); };
  $("#seq_pula").onclick = () => enviarSequencia(fila, i + 1);
}
async function feito(id) { await api("whatsapp/feito", { id }); if (PAG == "cobranca") ir("cobranca"); }

// ---------------------------------------------------------------- contas a pagar
let FILTRO_PAG = "a_pagar";
PAGINAS.pagar = async el => {
  const lst = await api("despesas", { filtro: FILTRO_PAG });
  el.innerHTML = `<h1>Contas a pagar <span class="acoes"><button class="btn" id="nd">${ic("mais")}Nova despesa</button></span></h1>
  <div class="card"><div class="abas">${[["a_pagar", "A pagar"], ["atrasado", "Vencidas"], ["pago", "Pagas"], ["todos", "Todas"]].map(([k, t]) => `<button data-f="${k}" class="${k == FILTRO_PAG ? "on" : ""}">${t}</button>`).join("")}</div>
  <p class="sub">${lst.length} despesa(s) · ${brl(lst.reduce((a, d) => a + d.valor_cent, 0))}</p>
  ${tabela([{ t: "Descrição", f: d => `${esc(d.descricao)}<div class="sub">${esc(d.fornecedor)}${d.recorrente ? " · recorrente" : ""}</div>` }, { t: "Categoria", fsel: 1, fv: d => d.categoria, f: d => esc(d.categoria) },
    { t: "Vencimento", f: d => dt(d.vencimento) }, { t: "Valor", n: 1, f: d => num(d.valor_cent) }, { t: "Situação", fsel: 1, fv: d => textoDe(selo(d.situacao)), f: d => selo(d.situacao) },
    { t: "", f: d => d.status == "aberto" ? `<button class="btn min" onclick="pagarDesp(${d.id})">Pagar</button> <button class="btn min sec ico" title="Editar" aria-label="Editar" onclick='editarDesp(${JSON.stringify(d).replace(/'/g, "&#39;")})'>${ic("editar")}</button> <button class="btn min sec ico perigo-txt" title="Excluir" aria-label="Excluir" onclick="excluirDesp(${d.id})">${ic("lixeira")}</button>` : "" }], lst, "Nada por aqui.", { filtros: "pagar", soma: d => d.valor_cent })}</div>`;
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
let ULTIMO_EXTRATO = "";       // resultado da última importação, mostrado depois que a lista é atualizada
PAGINAS.conciliacao = async el => {
  const pend = await api("conciliacao/pendentes");
  const res = ULTIMO_EXTRATO; ULTIMO_EXTRATO = "";
  el.innerHTML = `<h1>Conciliação bancária</h1>${res}
  <div class="card"><h2>Importar extrato (OFX)</h2><p class="sub">Exporte o extrato em OFX no internet banking e selecione aqui. Os recebimentos são casados com as contas a receber e baixados sozinhos; pagamentos casam com contas a pagar.</p>
    <label class="soltar" id="zona"><input type="file" id="ofx" accept=".ofx,.OFX" hidden>${ic("download")}<span><b>Selecione ou arraste o extrato .ofx</b><small>O robô também importa sozinho todo .ofx novo da pasta ${esc(ST.config.pastas.extratos || "")}${(ST.config.financeiro.contas_bancarias || []).length ? ` · conta vinculada: ${esc(ST.config.financeiro.contas_bancarias.join(", "))}` : ""}</small></span></label><div id="ofx_res"></div></div>
  ${ST.config.cobranca.provedor == "inter" ? `<div class="card"><h2>${ic("banco")}Extrato do Banco Inter (automático)</h2>
    <p class="sub">O robô baixa o extrato da conta Inter direto do banco (sem arquivo) e concilia sozinho, de hora em hora${ST.config.financeiro.extrato_inter_ate ? ` — último dia baixado: <b>${dt(ST.config.financeiro.extrato_inter_ate)}</b>` : ""}. Lançamentos que já vieram por OFX não são duplicados. A integração do Inter precisa da permissão <b>“Consultar extrato e saldo”</b>.</p>
    <div class="barra"><label>Período<select id="ext_dias"><option value="7">Últimos 7 dias</option><option value="30" selected>Últimos 30 dias</option><option value="60">Últimos 60 dias</option><option value="90">Últimos 90 dias</option></select></label>
    <button class="btn" id="ext_baixar">${ic("download")}Baixar extrato agora</button></div><div id="ext_res" class="sub"></div></div>` : ""}
  <div class="card"><div class="card-cab"><h2>${ic("alerta")}Lançamentos não conciliados (${pend.length})</h2><span class="sub">vincule ao título, classifique ou lance como despesa</span></div>
  ${tabela([{ t: "Data", f: m => dt(m.data) }, { t: "Histórico", f: m => esc(m.descricao) }, { t: "Valor", n: 1, f: m => `<span class="${m.valor_cent < 0 ? "neg" : ""}">${num(m.valor_cent)}</span>` },
    { t: "O que é", f: m => `<div class="acoes-linha" style="justify-content:flex-start;flex-wrap:wrap">${m.sugestoes.map(s => `<button class="btn min sec" onclick="vincular(${m.id},${s.id})" title="Venc. ${dt(s.vencimento)}">${esc(nomeCli(s.cliente).slice(0, 28))} · ${num(s.valor_cent)}</button>`).join("")}
      <select class="classif" data-m="${m.id}" data-v="${m.valor_cent}"><option value="">${m.valor_cent > 0 ? "Classificar entrada…" : "Classificar saída…"}</option>${m.valor_cent > 0
        ? '<option value="transferencia">Transferência entre contas</option><option value="aporte">Aporte / dinheiro do sócio</option><option value="outra_receita">Outra receita (não é honorário)</option>'
        : '<option value="despesa">Lançar como despesa paga</option><option value="transferencia">Transferência entre contas</option><option value="outra_saida">Saída sem despesa (retirada, estorno…)</option>'}</select></div>`, filtro: false }], pend, "Tudo conciliado ✔", { filtros: "conc_pend", soma: m => m.valor_cent })}</div>
  <div class="card"><div class="card-cab"><h2>${ic("banco")}Extrato da conta</h2><span class="sub">todos os lançamentos importados — entradas e saídas</span></div>
    <div class="barra"><label>Período<select id="ex_per">${(() => { const h = new Date(hojeISO() + "T12:00"), o = [];
      for (let k = 0; k < 12; k++) { const d = new Date(h.getFullYear(), h.getMonth() - k, 1), v = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`; o.push(`<option value="${v}" ${v == EXT_PER ? "selected" : ""}>${mesExtenso(v)}</option>`); }
      return `<option value="" ${!EXT_PER ? "selected" : ""}>Todo o período</option>` + o.join(""); })()}</select></label>
      <div class="abas">${[["todos", "Todos"], ["entradas", "Entradas"], ["saidas", "Saídas"], ["pendente", "Pendentes"]].map(([k, t]) => `<button data-ef="${k}" class="${k == EXT_FIL ? "on" : ""}">${t}</button>`).join("")}</div></div>
    <div id="ex_tab"><div class="vazio">Carregando…</div></div></div>`;
  $$(".classif", el).forEach(sel => sel.onchange = () => { const v = sel.value; if (!v) return;
    if (v == "despesa") { const c = prompt("Categoria da despesa (ex.: Pessoal, Ocupação, Tecnologia, Tributos, Serviços, Bancárias, Outras):", "Outras"); if (c === null) { sel.value = ""; return; } return classificarMov(+sel.dataset.m, v, c); }
    classificarMov(+sel.dataset.m, v); });
  $("#ex_per").onchange = e => { EXT_PER = e.target.value; extratoConta(); };
  $$("[data-ef]", el).forEach(b => b.onclick = () => { EXT_FIL = b.dataset.ef; $$("[data-ef]", el).forEach(x => x.classList.toggle("on", x == b)); extratoConta(); });
  extratoConta();
  if ($("#ext_baixar")) $("#ext_baixar").onclick = async () => { const b = $("#ext_baixar"); b.disabled = true; b.textContent = "Baixando…";
    try { const r = await api("conciliacao/inter", { dias: $("#ext_dias").value });
      ULTIMO_EXTRATO = `<div class="msg ok">Extrato do Inter: ${r.lancamentos} lançamento(s) de ${dt(r.periodo.slice(0, 10))} a ${dt(r.periodo.slice(-10))} (${r.entradas} entrada(s) e ${r.saidas} saída(s)) · ${r.novos} novo(s) · <b>${r.titulos}</b> recebimento(s) baixado(s) · ${r.despesas} pagamento(s) conciliado(s)${r.lancamentos === 0 ? " · a conta não teve movimento no período" : ""}</div>`;
      await carregarEstado(); ir("conciliacao");
    } catch (e) { b.disabled = false; b.innerHTML = `${ic("download")}Baixar extrato agora`; } };
  const zona = $("#zona");
  zona.ondragover = e => { e.preventDefault(); zona.classList.add("sobre"); };
  zona.ondragleave = () => zona.classList.remove("sobre");
  zona.ondrop = e => { e.preventDefault(); zona.classList.remove("sobre"); if (e.dataTransfer.files[0]) $("#ofx").onchange({ target: { files: e.dataTransfer.files } }); };
  $("#ofx").onchange = async e => { const f = e.target.files[0]; if (!f) return;
    const buf = await f.arrayBuffer(); let txt = new TextDecoder("utf-8").decode(buf); if (txt.includes("�")) txt = new TextDecoder("windows-1252").decode(buf);
    const r = await api("conciliacao/importar", { ofx: txt });
    ULTIMO_EXTRATO = `<div class="msg ok">Extrato OFX: ${r.lancamentos} lançamento(s) lidos · ${r.novos} novo(s) · <b>${r.titulos}</b> recebimento(s) baixado(s) · ${r.despesas} pagamento(s) conciliado(s)</div>`;
    ir("conciliacao"); };
};
let EXT_PER = hojeISO().slice(0, 7), EXT_FIL = "todos";
async function extratoConta() {
  const box = $("#ex_tab"); if (!box) return;
  const ini = EXT_PER ? EXT_PER + "-01" : "", fim = EXT_PER ? EXT_PER + "-31" : "";
  let e = await api("conciliacao/extrato", { inicio: ini, fim });
  let nota = "";
  const f = e.fontes || {}, ult = Object.values(f).map(x => x.ate).sort().pop() || "";
  if (!e.movimentos.length && EXT_PER && ult && ult.slice(0, 7) < EXT_PER && !extratoConta.pulou) {   // mês atual sem movimento: abre no último mês com lançamentos
    extratoConta.pulou = true; const mesVazio = EXT_PER; EXT_PER = ult.slice(0, 7);
    const sel = $("#ex_per"); if (sel) sel.value = EXT_PER;
    e = await api("conciliacao/extrato", { inicio: EXT_PER + "-01", fim: EXT_PER + "-31" });
    nota = `<div class="msg">Nenhum lançamento em ${mesExtenso(mesVazio)}: mostrando ${mesExtenso(EXT_PER)}, mês do último lançamento (${dt(ult)}).</div>`;
  }
  const res = $("#ext_res");
  if (res) res.innerHTML = f.inter ? `Já importados do Inter: <b>${f.inter.n}</b> lançamento(s) de ${dt(f.inter.de)} a ${dt(f.inter.ate)} — <b>${f.inter.entradas}</b> entrada(s) e <b>${f.inter.saidas}</b> saída(s)${f.inter.pendentes ? `, ${f.inter.pendentes} ainda não conciliado(s)` : ", todos conciliados"}. As saídas viram despesas pagas e as entradas baixam os títulos; por isso em “não conciliados” só fica o que o sistema não reconheceu.` : "Nenhum lançamento importado do Inter ainda.";
  const vis = e.movimentos.filter(m => EXT_FIL == "todos" || (EXT_FIL == "entradas" ? m.valor_cent > 0 : EXT_FIL == "saidas" ? m.valor_cent < 0 : m.situacao == "pendente"));
  const cls = { titulo: "bom", despesa: "neutro", classificado: "neutro", pendente: "alerta" };
  box.innerHTML = nota + `<section class="stats" style="margin-top:4px">${statTile({ rot: "Entradas", icone: "receber", valor: brl(e.entradas) })}${statTile({ rot: "Saídas", icone: "pagar", valor: brl(e.saidas) })}
    ${statTile({ rot: "Resultado do período", icone: "banco", valor: `<span class="${e.resultado < 0 ? "neg" : ""}">${brl(e.resultado)}</span>` })}${statTile({ rot: "Pendentes", icone: "alerta", valor: e.pendentes, estado: e.pendentes ? estadoSelo("atencao", "conciliar") : estadoSelo("bom", "tudo certo") })}</section>`
    + tabela([{ t: "Data", f: m => dt(m.data) }, { t: "Histórico", f: m => esc(m.descricao) },
      { t: "Entrada", n: 1, f: m => m.valor_cent > 0 ? num(m.valor_cent) : "" }, { t: "Saída", n: 1, f: m => m.valor_cent < 0 ? `<span class="neg">${num(-m.valor_cent)}</span>` : "" },
      { t: "No sistema", fsel: 1, fv: m => m.situacao == "titulo" ? "Recebimento de título" : m.situacao == "despesa" ? "Despesa" : m.detalhe, f: m => `<span class="selo ${cls[m.situacao]}">${esc(m.detalhe)}</span>${m.situacao == "classificado" ? ` <button class="btn min sec" onclick="classificarMov(${m.id},'')" title="Volta para os não conciliados">Desfazer</button>` : ""}` }],
      vis, "Nenhum lançamento neste período.", { filtros: "conc_extrato", soma: m => m.valor_cent });
}
async function classificarMov(id, tipo, categoria = "") {
  const r = await api("conciliacao/classificar", { movimento: id, tipo, categoria });
  aviso(tipo ? (r.aplicados > 1 ? `${r.aplicados} lançamentos da mesma origem classificados ✔` : "Lançamento classificado ✔") : "Classificação desfeita", 5000);
  ir("conciliacao");
}
async function vincular(movimento, titulo) { await api("conciliacao/vincular", { movimento, titulo }); aviso("Conciliado e baixado ✔"); ir("conciliacao"); }

// ---------------------------------------------------------------- importar inadimplência do Nitrus (PDF)
function importarNitrus() {
  modal(`<h2>Importar inadimplência do Nitrus</h2>
    <p class="sub">No Nitrus, gere o relatório <b>Inadimplência</b> em PDF e escolha o arquivo aqui. O sistema mostra a conferência antes de lançar:
    cada título entra no Contas a receber com o vencimento original (multa e juros calculados pelo atraso) e continua na régua de cobrança, sem gerar boleto (o cliente paga pelo PIX do escritório; se quiser, gere o boleto pelo título); a NFS-e sai quando o cliente pagar.
    Títulos que já estiverem no sistema não são lançados de novo.</p>
    <label class="soltar"><input type="file" id="nt_pdf" accept=".pdf,application/pdf" hidden>${ic("download")}<span><b>Escolher o PDF de Inadimplência</b><small>nitrus-inadimplencia.pdf</small></span></label>
    <div id="nt_res"></div>`);
  $("#nt_pdf").onchange = e => {
    const f = e.target.files[0]; if (!f) return;
    $("#nt_res").innerHTML = '<p class="sub">Lendo o relatório…</p>';
    const r = new FileReader();
    r.onload = async () => { try { mostrarNitrus(await api("nitrus/analisar", { pdf: r.result })); } catch (x) { $("#nt_res").innerHTML = `<p class="neg">${esc(x.message)}</p>`; } };
    r.readAsDataURL(f);
  };
}
function mostrarNitrus(a) {
  const G = a.grupos, opcCli = sel => `<option value="">— escolher cliente do cadastro —</option><option value="novo" ${sel == "novo" ? "selected" : ""}>Cadastrar novo: informe o CPF/CNPJ →</option><option value="nao">Não lançar este cliente</option>`
    + ST.clientes.slice().sort((x, y) => x.razao_social.localeCompare(y.razao_social)).map(c => `<option value="${c.cpf_cnpj}" ${c.cpf_cnpj == sel ? "selected" : ""}>${esc(nomeCli(c.razao_social))} — ${fmtDoc(c.cpf_cnpj)}</option>`).join("");
  const novos = g => g.titulos.filter(t => !t.existe), fora = g => g.titulos.filter(t => t.estado == "fora"), S = a.situacao || {};
  const ESTADO = { "": ["novo", "ainda não está no sistema: será lançado"], cobranca: ["em cobrança", "já está no sistema e sendo cobrado"],
    fora: ["fora da cobrança", "está no sistema, mas não estava sendo cobrado: volta para a cobrança"], pago: ["pago", "já está pago no sistema"] };
  modal(`<h2>Importar inadimplência do Nitrus</h2>
    <div class="imp-tot">${a.conferido ? estadoSelo("bom", "Leitura conferida com os totais do relatório") : estadoSelo("critico", "A leitura não bateu com os totais do relatório — confira antes de lançar")}
      <span>${a.titulos} título(s) de ${G.length} cliente(s) · original <b>${brl(a.lidos.original)}</b> · com juros e multa no Nitrus <b>${brl(a.lidos.total)}</b></span></div>
    <p class="sub">Cada título entra com o vencimento original e continua na régua de cobrança, sem gerar boleto (PIX do escritório); a <b>NFS-e só sai quando o cliente pagar</b>.</p>
    <div class="imp-sit">${[["novos", "a lançar", "alerta"], ["fora_da_cobranca", "no sistema, fora da cobrança (voltam a ser cobrados)", "atencao"], ["em_cobranca", "já em cobrança", "bom"], ["pagos", "já pagos", "bom"]]
      .filter(([k]) => S[k]).map(([k, t, c]) => `<span class="selo ${c}">${S[k]} ${t}</span>`).join(" ") || ""}</div>
    <div class="imp-grupos">${G.map((g, i) => `<div class="imp-g ${g.cpf_cnpj ? "" : "sem"}" data-i="${i}">
      <div class="imp-cab"><div><div class="nome">${esc(nomeCli(g.nome))}</div><div class="sub">${g.codigo ? `código ${esc(g.codigo)} no Nitrus · ` : ""}${esc(g.email || "sem e-mail")} · ${esc(g.telefone || "sem telefone")}</div></div>
        <div class="imp-vinc"><select data-v="${i}">${opcCli(g.cpf_cnpj || "novo")}</select><input data-n="${i}" placeholder="CPF/CNPJ" inputmode="numeric" ${g.cpf_cnpj ? "hidden" : ""}></div>
        <div class="imp-soma"><b>${brl(g.titulos.reduce((s, t) => s + t.valor_cent, 0))}</b><div class="sub">${g.titulos.length} título(s)${g.titulos.some(t => t.existe) ? ` · ${g.titulos.filter(t => t.existe).length} já no sistema` : ""}${fora(g).length ? ` · <b>${fora(g).length} fora da cobrança</b>` : ""}</div></div></div>
      ${!g.cpf_cnpj ? `<div class="sub" style="margin-top:6px">${esc(g.motivo)}: escolha o cliente no cadastro ou informe o CPF/CNPJ para cadastrar.</div>` : ""}
      <div class="imp-tits">${g.titulos.map(t => `<span class="${t.estado == "fora" ? "fora" : t.existe ? "ja" : ""}" title="${ESTADO[t.estado || ""][1]} · ${t.dias} dia(s) de atraso · ${brl(t.total_cent)} no Nitrus">${dt(t.vencimento)} · ${num(t.valor_cent)}${t.existe ? ` <small>${ESTADO[t.estado || ""][0]}</small>` : ""}</span>`).join("")}</div></div>`).join("")}</div>
    <label class="chk"><input type="checkbox" id="nt_cobrar" checked> Incluir na régua de cobrança — sem gerar boleto, o cliente paga pelo PIX do escritório (desmarcado: só controle)</label>
    <p><button class="btn" id="nt_ok">Lançar</button> <button class="btn sec" onclick="fechar()">Cancelar</button></p>`, true);
  const atu = () => { let n = 0; G.forEach((g, i) => { const v = $(`[data-v="${i}"]`).value; $(`[data-n="${i}"]`).hidden = v != "novo";
      if (v && v != "nao" && (v != "novo" || clientesDig($(`[data-n="${i}"]`).value).length >= 11)) n += novos(g).length + fora(g).length; });
    $("#nt_ok").textContent = `Lançar / recolocar ${n} título(s)`; $("#nt_ok").disabled = !n; };
  $$("[data-v],[data-n]").forEach(x => x.oninput = x.onchange = atu); atu();
  $("#nt_ok").onclick = async ev => {
    const grupos = G.map((g, i) => { const v = $(`[data-v="${i}"]`).value;
      return v && v != "nao" ? { ...g, titulos: [...novos(g), ...fora(g)], cpf_cnpj: v == "novo" ? "" : v, cnpj_novo: v == "novo" ? $(`[data-n="${i}"]`).value : "" } : null; }).filter(g => g && g.titulos.length);
    if (!confirm(`Lançar/recolocar ${grupos.reduce((s, g) => s + g.titulos.length, 0)} título(s) no Contas a receber${$("#nt_cobrar").checked ? " e incluir na cobrança" : ""}?`)) return;
    ev.target.disabled = true; ev.target.textContent = "Lançando…";
    try {
      const r = await api("nitrus/lancar", { grupos, cobrar: $("#nt_cobrar").checked });
      modal(`<h2>Inadimplência do Nitrus lançada</h2><p><b>${r.lancados}</b> título(s) lançado(s)${r.recolocados ? ` · <b>${r.recolocados}</b> recolocado(s) em cobrança` : ""}${r.clientes_novos ? ` · ${r.clientes_novos} cliente(s) cadastrado(s)` : ""}${r.ja_existiam ? ` · ${r.ja_existiam} já estavam no sistema` : ""}.</p>
        ${r.avisos.length ? `<ul class="lista">${r.avisos.map(x => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}
        <p><button class="btn" onclick="fechar();FILTRO_REC='atrasado';ir('receber')">Ver os atrasados</button></p>`);
      await carregarEstado();
    } catch (x) { ev.target.disabled = false; atu(); }
  };
}
const clientesDig = s => String(s || "").replace(/\D/g, "");
