// Backup, configurações, PIN de acesso e atualização.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
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

// ---------------------------------------------------------------- dados da empresa de uma versão anterior
async function dadosAnteriores() {
  const r = await api("migracao/dados_anteriores");
  const fontes = r.fontes.filter(f => f.diferencas.length);
  if (!fontes.length) return modal(`<h2>Dados da empresa</h2><p>Nenhuma versão anterior deste CNPJ${r.cnpj ? " (" + fmtDoc(r.cnpj) + ")" : ""} tem dados diferentes dos atuais. Se precisar, corrija à mão em Configurações.</p><p><button class="btn" onclick="fechar()">Fechar</button></p>`);
  const linha = f => `<option value="${esc(f.id)}" ${f.id == r.sugerida ? "selected" : ""}>${esc(f.tipo)} · ${dt(f.quando.slice(0, 10))} ${f.quando.slice(11, 16)}${f.versao ? " · versão " + esc(f.versao) : ""}${f.id == r.sugerida ? " — sugerida (a mais recente com os dados desta empresa)" : ""}${f.suspeita ? " — ⚠ já estava com o nome de outra empresa" : ""}</option>`;
  const tabela = id => { const f = fontes.find(x => x.id == id); const sus = f.suspeita;
    return `<p class="sub">${esc(f.origem)}</p><div class="tabela"><table><thead><tr><th></th><th>Dado</th><th>Hoje</th><th>Nesta versão</th></tr></thead><tbody>${f.diferencas.map(d => `<tr><td><input type="checkbox" data-campo="${esc(d.campo)}" ${sus ? "" : "checked"}></td><td>${esc(d.rotulo)}</td><td>${esc(fmtValor(d.atual))}</td><td><b>${esc(fmtValor(d.valor))}</b></td></tr>`).join("")}</tbody></table></div>`; };
  modal(`<h2>Trazer os dados da empresa de uma versão anterior</h2>
    <p class="sub">Só versões com o <b>mesmo CNPJ</b> (${fmtDoc(r.cnpj)}). Vêm apenas os dados cadastrais marcados; <b>notas emitidas, títulos, faturamento, clientes e numeração do RPS/DPS não são tocados</b>. Antes de aplicar o sistema faz um backup.</p>
    <label>Versão<select id="da_fonte">${fontes.map(linha).join("")}</select></label>
    <div id="da_tab">${tabela(r.sugerida || fontes[0].id)}</div>
    <p><button class="btn" id="da_ok">${ic("ok")}Trazer os dados marcados</button> <button class="btn sec" onclick="fechar()">Cancelar</button></p>`, true);
  if (!r.sugerida) $("#da_fonte").value = fontes[0].id;
  $("#da_fonte").onchange = e => $("#da_tab").innerHTML = tabela(e.target.value);
  $("#da_ok").onclick = async () => {
    const campos = $$("[data-campo]").filter(i => i.checked).map(i => i.dataset.campo);
    if (!campos.length) return aviso("Marque ao menos um dado.");
    const x = await api("migracao/trazer_dados", { fonte: $("#da_fonte").value, campos });
    fechar(); aviso(`Dados trazidos: ${x.trazidos.join(", ")}`, 6000); await carregarEstado(); ir("config");
  };
}
function fmtValor(v) { return v === true ? "Sim" : v === false ? "Não" : Array.isArray(v) ? v.join(", ") : (v ?? "") === "" ? "—" : String(v); }

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
  <div class="card" id="card_lic"><h2>${ic("cadeado")}Licença de uso</h2></div>
  <div class="card" id="card_pin"></div>
  <div class="card" id="card_atual"></div>
  <div class="card"><h2>${ic("play")}Robô financeiro</h2><p class="sub">Com o robô ligado, o sistema roda sozinho ao abrir e a cada hora (e todo dia pelo Agendador do Windows, se você rodar INSTALAR.bat): gera os títulos dos contratos, emite as NFS-e (só em produção), cria o PIX/boleto, envia a régua de cobrança, dá baixa nos pagamentos e faz backup.</p>
    <div class="campos">${ck("automacao", "ativa", "<b>Robô ligado</b>")}${ck("automacao", "gerar_titulos", "Gerar títulos dos contratos")}${ck("automacao", "emitir_nfse", "Emitir NFS-e")}${ck("automacao", "criar_cobranca", "Criar PIX/boleto")}${ck("automacao", "baixar_boletos", "Salvar PDF dos boletos")}
    ${ck("automacao", "regua", "Régua de cobrança")}${ck("automacao", "sincronizar_banco", "Baixa automática dos boletos (Inter)")}${ck("automacao", "despesas_recorrentes", "Despesas recorrentes")}${ck("automacao", "backup", "Backup diário")}</div></div>
  <div class="card"><h2>${ic("clientes")}Empresa emissora e credenciais</h2><p class="sub">Dados da empresa em uso (${esc((ST.empresa || {}).nome || "")}). Ficam só neste computador, no arquivo .env da empresa.</p>
    <div class="campos"><label class="inteiro">Razão social (nome da empresa)<input data-s="empresa" data-k="nome" value="${esc(c.empresa.nome || "")}" maxlength="150" placeholder="como no cartão CNPJ"></label>${cr("cnpj", "CNPJ")}${cr("im", "Inscrição municipal")}${cr("ie", "Inscrição estadual")}${cr("chave", "Chave do webservice (Itaboraí)", "password")}${cr("proximo_rps", "Próximo RPS", "number")}
    <label>Optante do Simples<select data-cred="simples"><option value="S" ${cred.simples != "N" ? "selected" : ""}>Sim</option><option value="N" ${cred.simples == "N" ? "selected" : ""}>Não</option></select></label>
    ${tx("emissao", "municipio_emissor", "Município da empresa (código IBGE)", "text", 'maxlength="7" inputmode="numeric" placeholder="Itaboraí = 3301900"')}
    ${tx("empresa", "email", "E-mail da empresa (aparece na nota)", "email", 'maxlength="80" placeholder="contato@empresa.com.br"')}
    ${tx("empresa", "telefone", "Telefone da empresa (aparece na nota)", "tel", 'maxlength="15" placeholder="(21) 99999-9999"')}
    ${c.emissao.canal == "nacional" ? "" : ck("empresa", "contato_na_nota", "Itaboraí: incluir e-mail e telefone nas observações da nota <span class=\"sub\">(o webservice da prefeitura não tem campo de contato do prestador)</span>")}</div>
    <p class="sub">Todos os dados acima podem ser corrigidos. Por segurança, o CNPJ não pode ser trocado depois que a empresa já tem títulos ou notas (isso misturaria o histórico com outra empresa) e o próximo RPS/DPS nunca fica abaixo de um número já usado em produção. Notas emitidas, títulos e faturamento nunca são alterados por esta tela.</p>
    <p><button class="btn sec" id="dados_ant" type="button">${ic("download")}Trazer os dados da empresa de uma versão anterior…</button></p></div>
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
  <div class="card"><h2>Empresa e PIX</h2><div class="campos">${tx("empresa", "pix_chave", "Chave PIX que recebe")}${tx("empresa", "pix_cidade", "Cidade (PIX)")}${tx("empresa", "whatsapp", "WhatsApp do escritório")}${tx("empresa", "assinatura", "Assinatura das mensagens")}</div></div>
  <div class="card"><h2>Cobrança</h2><div class="campos">
    <label>Meio de cobrança<select data-s="cobranca" data-k="provedor">${[["inter", "Inter: boleto + PIX"], ["pix", "Só PIX copia e cola"], ["nenhum", "Nenhum"]].map(([v, t]) => `<option value="${v}" ${c.cobranca.provedor == v ? "selected" : ""}>${t}</option>`).join("")}</select></label>
    <h3 class="bloco">Banco Inter (boletos)</h3>${tx("cobranca", "inter_client_id", "Inter: client_id")}${tx("cobranca", "inter_client_secret", "Inter: client_secret", "password")}
    ${["crt", "key"].map(t => `<label class="soltar mini"><input type="file" class="inter_arq" data-t="${t}" accept=".${t}" hidden>${ic("download")}<span><b>${(t == "crt" ? c.cobranca.inter_certificado : c.cobranca.inter_chave) ? `Inter: .${t} cadastrado ✔` : `Selecionar o .${t} do Inter`}</b><small>${t == "crt" ? "certificado da integração" : "chave privada da integração"}</small></span></label>`).join("")}
    ${tx("cobranca", "inter_conta", "Inter: conta corrente (opcional)")}${tx("cobranca", "inter_dias_agenda", "Aceitar pagamento até (dias após venc.)", "number")}${ck("cobranca", "inter_sandbox", "Inter em sandbox (teste)")}
    <h3 class="bloco">Encargos e régua de cobrança</h3>${tx("cobranca", "multa_pct", "Multa (%)")}${tx("cobranca", "juros_mes_pct", "Juros ao mês (%)")}${tx("cobranca", "regua_dias", "Régua (dias, ex.: -3, 0, 1, 5, 15, 30)")}
    <p class="sub inteiro" style="margin:4px 0 0">${ic("relogio")} E-mails e mensagens a clientes saem <b>só de segunda a sexta</b>, no horário abaixo (padrão 08:00 às 18:00). Nunca em fim de semana — essa regra é fixa.</p>${tx("cobranca", "envio_hora_inicio", "Envios a partir de", "time")}${tx("cobranca", "envio_hora_fim", "Envios até", "time")}
    ${ck("cobranca", "enviar_ao_gerar", "<b>Enviar o boleto assim que a cobrança for gerada</b> (e-mail e WhatsApp)")}${ck("cobranca", "agradecer_pagamento", "Pagamento recebido: enviar mensagem de agradecimento")}${ck("cobranca", "enviar_nfse_paga", "Depois do agradecimento, enviar a nota fiscal (NFS-e) emitida")}
    ${ck("cobranca", "regua_email", "Régua por e-mail (automático)")}${ck("cobranca", "regua_whatsapp", "Régua por WhatsApp")}${ck("cobranca", "anexar_boleto", "Anexar o PDF do boleto no e-mail")}${ck("cobranca", "pix_nas_mensagens", "Repetir o PIX copia e cola no texto (o boleto do Inter já traz o QR Code do PIX)")}${tx("pastas", "boletos", "Pasta dos PDFs dos boletos")}${tx("cobranca", "bloquear_apos_dias", "Alerta de atraso crítico após (dias)", "number")}
    <h3 class="bloco">Cobrança recorrente dos atrasados</h3>${ck("cobranca", "recorrente_ativa", "<b>Cobrar atrasados de forma recorrente</b>")}${tx("cobranca", "recorrente_apos_dias", "Começar após quantos dias de atraso", "number", 'min="1"')}${tx("cobranca", "recorrente_a_cada_dias", "Repetir a cada quantos dias", "number", 'min="1"')}</div></div>
  <div class="card"><h2>Banco Inter — como obter as credenciais</h2><p class="sub">No Internet Banking PJ do Inter: <b>Soluções para sua empresa › Nova integração</b>, marque os escopos <b>Emissão e cancelamento de boletos</b> e <b>Consulta de boletos</b>. Baixe o certificado (.crt) e a chave (.key), copie client_id e client_secret para cá, salve e teste. Os boletos são registrados direto na conta do escritório, com PIX no próprio boleto; o sistema dá a baixa sozinho quando o cliente paga.</p>
    <p><button class="btn sec" id="teste_inter">Salvar e testar conexão com o Inter</button></p></div>
  <div class="card"><h2>${ic("fone")}WhatsApp do escritório</h2>
    <p class="sub">A cobrança por WhatsApp <b>sai sozinha</b>, pelo número do escritório, para os clientes marcados em <b>Clientes › “Cobrar por WhatsApp”</b>. Basta conectar <b>uma vez</b>: clique em “Conectar”, e no celular do escritório abra o WhatsApp › <b>Aparelhos conectados › Conectar um aparelho</b> e leia o QR Code da janela que abrir. Depois disso o robô, a régua e o botão “Cobrar” enviam sem você precisar fazer nada (o computador precisa estar ligado).</p>
    <div id="ww_estado" class="msg">Verificando…</div>
    <div class="campos">${ck("cobranca", "whatsapp_web", "<b>Enviar a cobrança por WhatsApp automaticamente</b>")}${tx("cobranca", "whatsapp_web_intervalo", "Intervalo médio entre mensagens (segundos)", "number", 'min="5"')}${ck("cobranca", "whatsapp_web_pdf", "Enviar também o <b>boleto em PDF</b> logo depois da mensagem")}${ck("cobranca", "whatsapp_web_visivel", "Mostrar a janela do WhatsApp Web durante o envio")}</div>
    <p><button class="btn" id="ww_conectar" type="button">${ic("fone")}Conectar (ler QR Code)</button>
      <button class="btn sec" id="ww_desconectar" type="button">Desconectar</button></p>
    <div class="campos"><label>Celular para teste<input id="ww_tel" placeholder="(21) 9xxxx-xxxx"></label></div>
    <p><button class="btn sec" id="ww_teste" type="button">Enviar mensagem de teste (modelo da cobrança)</button></p>
    <details><summary class="sub">Envio automático pela API oficial da Meta (opcional — não usado)</summary>
    <div class="campos">${ck("cobranca", "whatsapp_api", "<b>Enviar automaticamente pela API oficial</b>")}
      ${tx("cobranca", "whatsapp_token", "Token de acesso (permanente)", "password", 'autocomplete="new-password" placeholder="EAAG… (usuário do sistema no Gerenciador de Negócios)"')}
      ${tx("cobranca", "whatsapp_phone_id", "ID do número de telefone", "text", 'placeholder="WhatsApp Manager › API › ID do número"')}
      ${tx("cobranca", "whatsapp_modelo_lembrete", "Modelo: lembrete")}${tx("cobranca", "whatsapp_modelo_hoje", "Modelo: vence hoje")}${tx("cobranca", "whatsapp_modelo_atraso", "Modelo: em atraso")}</div>
    <details><summary class="sub"><b>Textos dos 3 modelos para cadastrar na Meta</b> (categoria Utilidade, idioma Português (BR))</summary><div id="wa_modelos"></div></details>
    <p><button class="btn sec" id="teste_wa" type="button">Salvar e testar a API</button></p></details></div>
  <div class="card"><h2>${ic("receber")}Cartão de crédito (InfinitePay)</h2>
    <p class="sub">O cliente que preferir pagar com cartão recebe, junto com o boleto/PIX, o link “Pagar com cartão” da InfinitePay. As taxas ficam por conta do cliente: o valor no cartão já inclui a taxa (Lei 13.455/2017 permite preço diferente por meio de pagamento) e o escritório recebe o honorário cheio. Quando o pagamento aparecer no app da InfinitePay, clique em <b>Pago no cartão</b> no título: o sistema dá a baixa, lança a taxa em despesas (Bancárias), cancela o boleto e, se a NFS-e ainda não saiu, emite pelo valor cobrado no cartão.</p>
    <div class="campos">${sl("cobranca", "cartao_provedor", "Cartão de crédito", [["", "Desligado"], ["infinitepay", "InfinitePay"]])}
      ${tx("cobranca", "cartao_infinitepay_tag", "Sua InfiniteTag", "text", 'placeholder="no app, canto superior esquerdo, sem o $"')}
      ${ck("cobranca", "cartao_oferecer", "Oferecer o cartão em todas as cobranças")}
      ${tx("cobranca", "cartao_taxa_1x", "Taxa do crédito à vista do seu plano (%)")}${tx("cobranca", "cartao_taxa_fixa", "Taxa fixa por venda (R$)")}</div>
    <p class="sub"><b>As taxas do cartão ficam sempre por conta do cliente:</b> a taxa do crédito à vista é somada ao valor do link e, no parcelamento, o cliente escolhe as parcelas na tela da InfinitePay e paga os juros. <b>No app da InfinitePay, deixe ligado “juros do parcelamento por conta do cliente”</b> (link de pagamento › parcelamento).</p>
    <p class="sub"><b>Confira as taxas do SEU plano no app da InfinitePay</b> (Perfil › Taxas) e ajuste aqui: elas definem o acréscimo cobrado do cliente. A InfinitePay não cancela links pela API: se o cliente pagar por boleto e também pelo cartão, estorne pelo app.</p>
    <p class="sub" id="cartao_sim"></p>
    <p><button class="btn sec" id="teste_cartao" type="button">Salvar e testar conexão com a InfinitePay</button></p></div>
  <div class="card"><h2>E-mail (SMTP)</h2><p class="sub">Gmail: servidor smtp.gmail.com, porta 587, e uma “senha de app” da conta Google.</p><div class="campos">${tx("smtp", "host", "Servidor")}${tx("smtp", "porta", "Porta", "number")}${tx("smtp", "usuario", "Usuário")}${tx("smtp", "senha", "Senha", "password")}${tx("smtp", "remetente", "Remetente")}${tx("smtp", "copia_para", "Cópia oculta para")}${ck("smtp", "ssl", "SSL direto (porta 465)")}</div>
    <p><button class="btn sec" id="teste_email">Salvar e enviar e-mail de teste</button></p></div>
  <div class="card"><h2>${ic("contratos")}13º honorário</h2><p class="sub">Em novembro e dezembro, cobra o honorário mensal de cada contrato ativo em parcelas, com NFS-e e boleto, entrando na régua de cobrança.</p>
    <div class="campos">${ck("decimo_terceiro", "ativo", "<b>Cobrar 13º honorário</b>")}${ck("decimo_terceiro", "emitir_nfse", "Emitir NFS-e das parcelas")}
    <label>Descrição na nota<input data-s="decimo_terceiro" data-k="descricao" value="${esc(c.decimo_terceiro.descricao || "")}"></label>
    ${c.decimo_terceiro.parcelas.map((p, j) => `<label>Parcela ${j + 1}: % do honorário<input data-p13="${j}" data-c="percentual" value="${esc(p.percentual)}"></label><label>Parcela ${j + 1}: vencimento (dd/mm)<input data-p13="${j}" data-c="vencimento" value="${esc(p.vencimento)}" placeholder="30/11"></label>`).join("")}</div></div>
  <div class="card"><h2>Financeiro</h2><div class="campos">${tx("financeiro", "dia_vencimento_padrao", "Dia de vencimento padrão", "number")}${tx("financeiro", "dia_geracao", "Dia de gerar a recorrência", "number")}${tx("financeiro", "prazo_avulso_dias", "Prazo da nota avulsa (dias)", "number")}
    ${tx("financeiro", "aliquota_simples_pct", "Alíquota DAS sem histórico (%)")}${ck("financeiro", "iss_fixo", "ISS fixo fora do DAS (escritório contábil)")}${tx("financeiro", "iss_fixo_mensal", "ISS fixo por mês (R$, para a DRE)")}${tx("financeiro", "contas_bancarias", "Contas bancárias desta empresa (banco-agência-conta)")}${tx("financeiro", "categorias_despesa", "Categorias próprias de despesa (além do plano da DRE; separe por vírgula)")}</div></div>`;
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
      else if (["multa_pct", "juros_mes_pct", "aliquota_simples_pct", "iss_fixo_mensal", "cartao_taxa_1x", "cartao_taxa_fixa"].includes(i.dataset.k)) v = valorNum(v);
      else if (i.type == "number") v = Number(v);
      (novo[i.dataset.s] ||= {})[i.dataset.k] = v; });   // qualquer seção (ex.: seguranca) entra no que é salvo
    const cred = {};
    $$("[data-cred]").forEach(i => cred[i.dataset.cred] = i.value);
    await api("config/salvar", novo); await api("empresa/credenciais/salvar", cred);
    await carregarEstado(); return true;
  };
  $("#salvar").onclick = async () => { if (await salvarTudo()) aviso("Configurações salvas ✔"); };
  $("#dados_ant").onclick = () => dadosAnteriores();
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
  listarBackups(); cartaoLicenca($("#card_lic")); cartaoPin($("#card_pin")); cartaoAtualizacao($("#card_atual"));
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
  const wwMostrar = async () => {
    const e = await api("whatsapp_web/estado"); const box = $("#ww_estado"); if (!box) return e;
    box.className = "msg " + (e.ativo ? "ok" : e.conectando ? "" : "erro");
    box.innerHTML = !e.disponivel ? "Falta o componente do WhatsApp Web neste computador: feche o sistema e abra pelo <b>INICIAR.bat</b> (ele instala sozinho)."
      : e.conectando ? "Janela do WhatsApp Web aberta: leia o QR Code com o celular do escritório (WhatsApp › Aparelhos conectados)…"
      : e.enviando ? "Enviando mensagens pelo WhatsApp…"
      : e.ativo ? `WhatsApp conectado ✔ desde ${dt(e.desde.slice(0, 10))} — a cobrança sai sozinha.`
      : e.conectado ? "WhatsApp conectado, mas o envio automático está desligado (marque a opção abaixo e salve)."
      : "WhatsApp não conectado. Clique em “Conectar” e leia o QR Code." + (e.mensagem ? ` <br><small>${esc(e.mensagem)}</small>` : "");
    return e;
  };
  wwMostrar();
  $("#ww_conectar").onclick = async () => {
    await api("whatsapp_web/conectar"); aviso("Abrindo o WhatsApp Web: leia o QR Code com o celular do escritório.", 8000);
    for (let i = 0; i < 100; i++) { await new Promise(r => setTimeout(r, 2500)); const e = await wwMostrar(); if (!e || (!e.conectando && i > 1)) break; }
    const e = await api("whatsapp_web/estado"); if (e.conectado) { aviso("WhatsApp conectado ✔ A cobrança agora sai sozinha.", 8000); ST.config = (await api("estado")).config || ST.config; ir("config"); }
  };
  $("#ww_desconectar").onclick = async () => { if (!confirm("Desconectar o WhatsApp deste computador? A cobrança por WhatsApp para de sair sozinha.")) return;
    const r = await api("whatsapp_web/desconectar"); aviso(r.mensagem, 8000); wwMostrar(); };
  $("#ww_teste").onclick = async () => { const tel = $("#ww_tel").value.trim(); if (!tel) return aviso("Informe o celular para o teste.");
    aviso("Enviando a mensagem de teste pelo WhatsApp…", 20000); const r = await api("whatsapp_web/teste", { telefone: tel }); aviso(r.mensagem || "OK", 8000); };
  $("#teste_wa").onclick = async () => { if (!await salvarTudo()) return; const r = await api("whatsapp/testar"); aviso(r.mensagem || "OK", 6000); };
  api("whatsapp/modelos").then(m => { $("#wa_modelos").innerHTML = Object.values(m).map(x => `<div class="wa-modelo"><p><b>Nome do modelo:</b> <code>${esc(x.nome)}</code> <button class="btn min sec" type="button" data-copia="${esc(x.texto)}">Copiar texto</button></p><pre>${esc(x.texto)}</pre></div>`).join("")
    + '<p class="sub">Exemplos para a Meta: {{1}} Empresa Exemplo Ltda · {{2}} R$ 374,40 · {{3}} Honorários contábeis - competência 10/2026 · {{4}} 10/10/2026 · {{5}} 07790.00116 12345.678901 · {{6}} 00020101021226… · {{7}} Também aceitamos PIX e boleto, sem acréscimo. · {{8}} Escritório Exemplo Contabilidade</p>';
    $$("[data-copia]").forEach(b => b.onclick = () => { navigator.clipboard.writeText(b.dataset.copia); aviso("Texto copiado"); }); });
  $("#teste_cartao").onclick = async () => { if (!await salvarTudo()) return; const r = await api("cartao/testar"); aviso(r.mensagem || "OK", 6000); };
  const simCartao = async () => { const x = await api("cartao/simular", { valor: "1000", parcelas: 1 });
    $("#cartao_sim").innerHTML = `Exemplo com as taxas salvas: honorário de <b>${brl(x.valor_cent)}</b> → no cartão à vista o cliente paga <b>${brl(x.total_cent)}</b> (acréscimo de ${brl(x.acrescimo_cent)}); descontada a taxa, o escritório recebe o honorário cheio. Parcelado: juros pagos pelo cliente na InfinitePay.`; };
  simCartao();
  $("#imp_xml").onclick = async () => { aviso("Lendo XML…"); const r = await api("importacao/xml"); aviso(`XML: ${JSON.stringify(r)}`, 8000); await carregarEstado(); };
  $("#env_res").onclick = async () => { const r = await api("resumo/enviar"); aviso("Resumo: " + r.resultado, 6000); };
  $("#teste_email").onclick = async () => { const p = prompt("Enviar teste para qual e-mail?", (c.resumo || {}).email_dono || ""); if (!p) return;
    if (!await salvarTudo()) return; aviso("Configurações salvas. Enviando o e-mail de teste…", 20000);
    await api("email/testar", { para: p }); aviso("E-mail de teste enviado ✔ Confira a caixa de entrada (e o spam).", 7000); };
};

// ---------------------------------------------------------------- PIN de acesso
// ---------------------------------------------------------------- licença de uso
function contatoFornecedor(f) {
  f = f || {};
  const partes = [f.nome && `<b>${esc(f.nome)}</b>`, f.whatsapp && `WhatsApp ${esc(f.whatsapp)}`, f.email && esc(f.email)].filter(Boolean);
  return partes.length ? `<p class="sub">Fornecedor: ${partes.join(" · ")}</p>` : "";
}
function formLicenca(id) {
  return `<label class="inteiro">Serial de liberação<textarea id="${id}_chave" rows="3" placeholder="NFSE1-…" spellcheck="false" style="font-family:Consolas,Menlo,monospace;font-size:12px"></textarea></label>
    <p style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><button class="btn" id="${id}_ok" type="button">${ic("ok")}Ativar serial</button>
    <label class="btn sec" style="cursor:pointer">${ic("download")}Abrir arquivo .lic<input type="file" id="${id}_arq" accept=".lic,.txt" hidden></label></p><p id="${id}_msg" class="sub"></p>`;
}
function ligarFormLicenca(id, depois) {
  $(`#${id}_arq`).onchange = async e => { const f = e.target.files[0]; if (f) $(`#${id}_chave`).value = (await f.text()).trim(); };
  $(`#${id}_ok`).onclick = async () => {
    const chave = $(`#${id}_chave`).value.trim(); if (!chave) return;
    const r = await (await fetch("/api/licenca/ativar", { method: "POST", headers: API_CAB, body: JSON.stringify({ chave }) })).json();
    if (r.erro) { $(`#${id}_msg`).innerHTML = `<span class="neg">${esc(r.erro)}</span>`; return; }
    $(`#${id}_msg`).textContent = r.mensagem; aviso("Licença ativada ✔ " + r.mensagem, 8000); depois(r);
  };
}
function telaLicenca(lic) {
  lic = lic || {};
  if ($("#tela_lic")) return;
  const d = document.createElement("div");
  d.id = "tela_lic"; d.className = "tela-pin";
  const novo = lic.status == "sem_licenca";
  d.innerHTML = `<div class="caixa-pin" style="max-width:560px"><h1>${ic("cadeado")} ${novo ? "Serial de liberação" : "Licença"}</h1>
    <p>${esc(lic.mensagem || "Informe o serial de liberação para usar o sistema.")}</p>
    <p class="sub">O sistema é licenciado por <b>mensalidade</b> ou <b>anuidade</b>. ${lic.cnpj_instalacao ? `CNPJ desta instalação: <b>${fmtDoc(lic.cnpj_instalacao)}</b>.` : "Informe ao fornecedor o CNPJ da sua empresa: o serial vem para ele e já configura a instalação."}${novo ? "" : " Seus dados continuam guardados; consultas e backup seguem disponíveis."}</p>
    ${contatoFornecedor(lic.fornecedor)}${formLicenca("tl")}</div>`;
  document.body.appendChild(d);
  ligarFormLicenca("tl", r => { if (r.liberado) location.reload(); });
}
async function cartaoLicenca(box) {
  const s = await api("licenca/status");
  const cls = { ativa: "bom", aviso: "atencao", carencia: "critico", teste: "info", bloqueada: "critico", sem_licenca: "critico" }[s.status] || "neutro";
  const rot = { ativa: "Ativa", aviso: "Vence em breve", carencia: "Vencida (carência)", teste: "Avaliação", bloqueada: "Bloqueada", sem_licenca: "Sem serial" }[s.status] || s.status;
  box.innerHTML = `<h2>${ic("cadeado")}Licença de uso</h2>
    <p>${estadoSelo(cls, rot)} ${esc(s.mensagem)}</p>
    ${s.cliente ? `<p class="sub">Licenciado: <b>${esc(s.cliente)}</b>${s.plano_nome ? ` · plano <b>${esc(s.plano_nome)}</b>` : ""} · CNPJ ${fmtDoc(s.cnpj || "")}${s.empresas ? ` · até ${s.empresas} empresa(s)` : " · empresas ilimitadas"}${s.id ? ` · licença ${esc(s.id)}` : ""}</p>` : ""}
    <p class="sub">CNPJ desta instalação: <b>${s.cnpj_instalacao ? fmtDoc(s.cnpj_instalacao) : "não configurado"}</b>. Para renovar (mensalidade ou anuidade), cole o novo serial abaixo.</p>
    ${contatoFornecedor(s.fornecedor)}${formLicenca("cl")}`;
  ligarFormLicenca("cl", () => { carregarEstado(); cartaoLicenca(box); });
}
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
    const r = await (await fetch("/api/acesso/entrar", { method: "POST", headers: API_CAB, body: JSON.stringify({ pin: $("#pin_v").value }) })).json();
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

// ---------------------------------------------------------------- atualização do sistema
async function cartaoAtualizacao(box) {
  const r = await api("atualizacao/versoes");
  box.innerHTML = `<h2>${ic("download")}Atualizar o sistema</h2>
    <p class="sub">Versão instalada: <b>${esc(r.versao)}</b>. Recebeu um ZIP novo do sistema? Selecione-o aqui: o sistema faz backup de todas as empresas, troca só os arquivos do programa (dados, senhas, certificados e notas ficam intactos) e reabre sozinho.</p>
    <p><label class="btn"><input type="file" id="at_arq" accept=".zip" hidden>${ic("download")}Selecionar o ZIP da versão nova…</label></p>
    ${r.versoes.length ? `<details><summary class="sub">Voltar para uma versão anterior (${r.versoes.length} guardada(s))</summary><div class="acoes-linha" style="margin-top:8px">${r.versoes.map(v => `<button class="btn min sec" type="button" data-volta="${esc(v.nome)}">Versão ${esc(v.versao)} — ${esc(v.nome.slice(-21, -4).replace("_", " "))}</button>`).join(" ")}</div></details>` : ""}`;
  const lerB64 = f => new Promise((ok, erro) => { const x = new FileReader(); x.onload = () => ok(x.result); x.onerror = erro; x.readAsDataURL(f); });
  const inicioAtual = (await (await fetch("/api/versao")).json()).inicio;
  const esperarNova = async () => {
    modal(`<h2>Atualizando…</h2><p>Backup feito e arquivos trocados. O sistema está reabrindo — esta tela recarrega sozinha.</p>`);
    for (let i = 0; i < 90; i++) { await new Promise(ok => setTimeout(ok, 2000));
      try { const v = await (await fetch("/api/versao")).json(); if (v.inicio && v.inicio != inicioAtual) { location.reload(); return; } } catch (e) { /* reiniciando */ } }
    $("#modal_corpo").innerHTML = `<h2>Quase lá</h2><p>Se a tela não voltar, abra pelo atalho “Sistema Financeiro NFS-e” na área de trabalho.</p>`;
  };
  $("#at_arq", box).onchange = async e => { const f = e.target.files[0]; e.target.value = ""; if (!f) return;
    const arquivo = await lerB64(f); const a = await api("atualizacao/analisar", { arquivo });
    const txt = a.mais_nova ? `Atualizar da versão ${a.versao_atual} para a ${a.versao_nova}?` : `Este ZIP é da versão ${a.versao_nova}${a.mesma ? " (a mesma instalada)" : ", ANTERIOR à instalada (" + a.versao_atual + ")"}. Instalar mesmo assim?`;
    if (!confirm(txt + "\n\nAntes, o sistema faz backup de todas as empresas. Seus dados não são alterados.")) return;
    aviso("Fazendo backup e atualizando…", 60000);
    await api("atualizacao/aplicar", { arquivo, permitir_anterior: !a.mais_nova }); esperarNova(); };
  $$("[data-volta]", box).forEach(b => b.onclick = async () => {
    if (!confirm(`Voltar o programa para a ${b.textContent}? Os dados não mudam (antes é feito backup).`)) return;
    await api("atualizacao/voltar", { nome: b.dataset.volta }); esperarNova(); });
}
