// Teste funcional de ponta a ponta, em MODO DE TESTE, clicando nas telas como um usuário.
// Pré-requisito: python tests/ui/servidor_completo.py <pasta> <porta>  (prefeitura, Sefin, Inter e e-mail simulados)
// Uso: node tests/ui/funcional.js <porta> <pasta>
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const { chromium } = require('playwright');

const porta = process.argv[2] || '8796', pasta = process.argv[3];
const URL = `http://127.0.0.1:${porta}`;
const exe = process.env.CHROMIUM_PATH || (fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined);
const RPS = 'RPS CONSULTORIA E SERVICOS DE ENGENHARIA LTDA — 32.396.063/0001-03';
const PORTAL = 'PORTAL RESOLVE ATIVIDADES DE INTERNET LTDA — 35.979.895/0001-32';
const resultados = [];
let p, respostas = [], errosJS = [];

const espera = ms => new Promise(r => setTimeout(r, ms));
const api = (rota, corpo) => p.evaluate(([r, c]) => fetch('/api/' + r, { method: 'POST', headers: API_CAB, body: JSON.stringify(c || {}) }).then(x => x.json()), [rota, corpo || {}]);
const ir = async (pg, ms = 1000) => { await p.goto(`${URL}/#${pg}`); await p.reload(); await espera(ms); };
const aviso = () => p.evaluate(() => { const a = document.querySelector('#aviso'); return a && !a.hidden ? a.textContent : ''; });
const certo = (cond, msg) => { if (!cond) throw new Error(msg); };
async function passo(nome, fn) {
  errosJS = [];
  try {
    const det = await fn();
    if (errosJS.length) throw new Error('erro de JavaScript: ' + errosJS.join(' | '));
    resultados.push({ nome, ok: true, det: det || '' });
  } catch (e) { resultados.push({ nome, ok: false, det: String(e.message || e).slice(0, 300) }); }
  process.stdout.write(`${resultados.at(-1).ok ? 'OK   ' : 'FALHA'} ${nome}${resultados.at(-1).det ? ' — ' + resultados.at(-1).det : ''}\n`);
}
async function escolherCliente(sel, texto) { await p.fill(sel, texto); await p.dispatchEvent(sel, 'input'); await espera(700); }

(async () => {
  const b = await chromium.launch(exe ? { executablePath: exe } : {});
  const ctx = await b.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true });
  p = await ctx.newPage();
  p.on('pageerror', e => errosJS.push(e.message));
  p.on('dialog', d => d.type() === 'prompt' ? d.accept(respostas.length ? respostas.shift() : d.defaultValue()) : d.accept());

  // ------------------------------------------------------------ painel e saúde
  await passo('Painel abre com indicadores e checklist', async () => {
    await ir('painel', 1500);
    certo(await p.isVisible('h1'), 'painel sem título');
    const s = await api('saude'); certo(s.itens && s.itens.length, 'checklist vazio');
    return `${s.itens.filter(i => i.ok).length}/${s.itens.length} itens do checklist ok`;
  });
  await passo('Robô: "Rodar robô agora"', async () => {
    await p.click('#robo'); await espera(4000);
    const log = await api('log'); certo(log.some(l => l.tipo === 'robo'), 'robô não registrou execução');
  });

  // ------------------------------------------------------------ clientes
  await passo('Clientes: cadastrar cliente novo (PJ)', async () => {
    await ir('clientes');
    await p.fill('#c_doc', '54399432000146'); await p.fill('[name=razao_social]', 'ESPACO CULTIVAR FONOAUDIOLOGIA LTDA');
    await p.fill('[name=tipo_logradouro]', 'RUA'); await p.fill('[name=logradouro]', 'DAS FLORES'); await p.fill('[name=numero]', '10');
    await p.fill('[name=bairro]', 'Centro'); await p.fill('[name=cep]', '24800000'); await p.fill('[name=codigo_municipio]', '3301900');
    await p.fill('[name=email]', 'contato@cultivar.teste'); await p.fill('[name=telefone]', '21977776666');
    await p.click('#sc'); await espera(1000);
    const c = (await api('estado')).clientes.find(x => x.cpf_cnpj === '54399432000146'); certo(c && c.endereco.uf === 'RJ', 'cliente não salvo');
  });
  await passo('Clientes: editar e regra fiscal específica do tomador', async () => {
    await ir('clientes');
    await p.click('[data-ed="54399432000146"]'); await espera(300);
    await p.fill('[name=complemento]', 'SALA 2');
    await p.check('input[name="cf_fzg"][value="0"]'); await espera(200);
    await p.check('[data-fz="iss_retido"]'); await p.fill('[data-fz="aliquota_iss_retido"]', '2');
    await p.click('#sc'); await espera(1000);
    const c = (await api('estado')).clientes.find(x => x.cpf_cnpj === '54399432000146');
    certo(c.endereco.complemento === 'SALA 2' && c.fiscal && !c.fiscal.usar_geral && c.fiscal.iss_retido, 'edição/regra não salva');
  });
  await passo('Clientes: cliente do exterior', async () => {
    await ir('clientes'); await p.click('#lc');
    await p.check('#c_ext'); await p.selectOption('#ce_pais', 'US');
    await p.fill('[name=razao_social]', 'ACME CORPORATION'); await p.fill('#ce_nif', '98-7654321'); await p.fill('#ce_cidade', 'Miami');
    await p.fill('[name=logradouro]', 'BRICKELL AVE'); await p.fill('[name=numero]', '100');
    await p.click('#sc'); await espera(1000);
    const c = (await api('estado')).clientes.find(x => x.estrangeiro); certo(c && c.cpf_cnpj.startsWith('99') && c.estrangeiro.pais_bacen === '2496', 'exterior não salvo');
  });
  await passo('Clientes: excluir', async () => {
    await api('cliente/salvar', { cpf_cnpj: '11444777000161', razao_social: 'CLIENTE PARA EXCLUIR' });
    await ir('clientes'); await p.click('[data-ex="11444777000161"]'); await espera(800);
    certo(!(await api('estado')).clientes.some(x => x.cpf_cnpj === '11444777000161'), 'cliente não excluído');
  });
  await passo('Clientes: importar clientes e notas dos XML (pasta IMPORTAR XML)', async () => {
    const caixa = path.join(pasta, 'IMPORTAR XML'); fs.mkdirSync(caixa, { recursive: true });
    fs.copyFileSync(path.join(__dirname, '..', 'dados', 'retorno_nfse_real.xml'), path.join(caixa, 'nota.xml'));
    await ir('clientes'); await p.click('#imp_xml'); await espera(1500);
    certo(await p.isVisible('.imp-ok'), 'importador não encontrou a nota');
    await p.click('.imp-ok'); await espera(2000);
    certo(/importado/.test(await aviso()), 'importação sem confirmação: ' + await aviso());
  });

  // ------------------------------------------------------------ serviços e configurações
  await passo('Configurações: cadastrar serviço (atividade)', async () => {
    const antes = (await api('servicos')).length;
    await api('servico/salvar', { nome: 'Consultoria', descricao: 'CONSULTORIA EMPRESARIAL', item_lista_servico: '17.01', codigo_desdobro: '170101',
      codigo_nbs: '113011000', cnae: '7020400', aliquota_iss: '2.00', tipo_tributacao: '4', iss_retido: '2', indicador_operacao: '100301', classificacao_tributaria: '200052' });
    await ir('config', 1500); certo(await p.isVisible('#lista_serv'), 'lista de serviços não aparece');
    certo((await api('servicos')).length === antes + 1, 'serviço não cadastrado');
  });
  await passo('Licença: avaliação, chave adulterada recusada e ativação pela tela', async () => {
    let s = await api('licenca/status');
    certo(s.liberado && s.status === 'teste', 'instalação nova deveria estar em avaliação: ' + JSON.stringify(s));
    await ir('config', 1500);
    certo(/Licença de uso/.test(await p.textContent('#card_lic')), 'cartão da licença não apareceu');
    const { chave } = await api('teste/licenca', { validade: '2027-10-31' });
    const adulterada = chave.replace(/\.(.)/, (m, c) => '.' + (c === 'A' ? 'B' : 'A'));
    await p.fill('#cl_chave', adulterada); await p.click('#cl_ok'); await espera(800);
    certo(/inválida/.test(await p.textContent('#cl_msg')), 'chave adulterada não foi recusada: ' + await p.textContent('#cl_msg'));
    await p.fill('#cl_chave', chave); await p.click('#cl_ok'); await espera(1200);
    s = await api('licenca/status');
    certo(s.liberado && s.status === 'ativa' && s.validade === '2027-10-31' && s.cliente === 'ESCRITORIO DE TESTE' && s.plano_nome === 'Anuidade', JSON.stringify(s));
    certo(/Anuidade/.test(await p.textContent('#card_lic')), 'o cartão não mostra o plano');
    return 'serial anual ativo até 31/10/2027';
  });
  await passo('Configurações: salvar tudo', async () => {
    await ir('config', 1500); await p.click('#salvar'); await espera(1200);
    certo(/salv/i.test(await aviso()), 'sem confirmação: ' + await aviso());
  });
  await passo('Configurações: testar e-mail (SMTP)', async () => {
    await ir('config', 1500); respostas = ['dono@moraes.teste'];
    await p.click('#teste_email'); await espera(2500);
    const cx = JSON.parse(fs.readFileSync(path.join(pasta, 'dados', 'emails_enviados.json'), 'utf8'));
    certo(cx.some(m => m.para === 'dono@moraes.teste'), 'e-mail não enviado');
  });
  await passo('Configurações: testar Banco Inter', async () => {
    await ir('config', 1500); await p.click('#teste_inter'); await espera(2500);
    certo(/Inter OK/.test(await aviso()), 'teste do Inter: ' + await aviso());
  });
  await passo('Configurações: testar certificado e conexão (Sefin/ADN)', async () => {
    await ir('config', 1500); await p.click('#teste_cert'); await espera(3000);
    certo(/ADN OK/.test(await p.textContent('#cert_res')), await p.textContent('#cert_res'));
  });

  // ------------------------------------------------------------ emissão em homologação (Itaboraí)
  await passo('Emitir nota em HOMOLOGAÇÃO (Itaboraí)', async () => {
    await ir('emitir', 1500); await escolherCliente('#e_cli', RPS);
    await p.fill('#e_valor', '374,40'); await p.click('#e_btn'); await espera(3500);
    const r = await p.textContent('#e_res'); certo(/✔/.test(r), r);
    return r.slice(0, 80);
  });
  await passo('Conferir RPS (sem enviar)', async () => {
    const d = { numero: '', itens: [{ descricao: 'TESTE', valor_unitario: '100' }], tomador: { cpf_cnpj: '32396063000103', razao_social: 'RPS',
      endereco: { logradouro: 'AV X', numero: '1', bairro: 'C', codigo_municipio: '3304557', uf: 'RJ', cep: '20071904', tipo_logradouro: 'AV' } },
      item_lista_servico: '17.19', codigo_nbs: '113022100', codigo_desdobro: '171901', cnae: '6920601', aliquota_iss: '0', tipo_tributacao: '4',
      indicador_operacao: '100301', classificacao_tributaria: '200052' };
    const r = await api('conferir', d); certo(r.sucesso && r.xml.includes('<RpsNfse'), JSON.stringify(r).slice(0, 200));
  });

  // ------------------------------------------------------------ produção SIMULADA
  await passo('Trocar para PRODUÇÃO (no simulador)', async () => {
    await ir('painel'); await p.click('#amb'); await espera(1500);
    certo((await api('estado')).producao, 'não ativou produção');
  });
  await passo('Emitir nota válida + boleto (Itaboraí, regra geral)', async () => {
    await ir('emitir', 1500); await escolherCliente('#e_cli', RPS);
    await p.fill('#e_valor', '374,40'); await p.click('#e_btn'); await espera(5000);
    const r = await p.textContent('#e_res'); certo(/NFS-e/.test(r) && /✔/.test(r), r);
    const t = await api('titulos', { filtro: 'todos' }); certo(t.some(x => x.nfse_status === 'emitida' && x.banco_id), 'título sem NFS-e/boleto');
  });
  await passo('Copiar dados da última nota do tomador', async () => {
    await ir('emitir', 1500); await escolherCliente('#e_cli', RPS); await espera(800);
    await p.fill('#e_valor', ''); await p.click('#e_copiar'); await espera(500);
    certo((await p.inputValue('#e_valor')) === '374,40', 'valor não copiado');
    await p.fill('#e_desc', 'HONORARIOS CONTABEIS OUTUBRO/2026'); await p.click('#e_btn'); await espera(5000);
    certo(/✔/.test(await p.textContent('#e_res')), await p.textContent('#e_res'));
  });
  await passo('Emitir em lote (2 clientes)', async () => {
    await ir('lote', 1500);
    await p.check('.lc[data-doc="32396063000103"]'); await p.check('.lc[data-doc="35979895000132"]');
    await p.fill('.lv[data-doc="35979895000132"]', '1.000,00'); await p.dispatchEvent('.lv[data-doc="35979895000132"]', 'input');
    await p.click('#l_btn'); await espera(9000);
    let r = await p.textContent('#l_res');
    // mesmo cliente, serviço e competência de uma nota já emitida: o sistema pergunta antes (proteção de duplicidade)
    if (/possível duplicidade/.test(r)) { certo(await p.$('#dp_sim'), 'a pergunta da duplicidade não apareceu'); await p.click('#dp_sim'); await espera(5000); }
    const ts = await api('titulos', { filtro: 'todos' });
    certo(['32396063000103', '35979895000132'].every(d => ts.some(x => x.cpf_cnpj === d && x.nfse_status === 'emitida')), r.slice(0, 300));
    return /possível duplicidade/.test(r) ? 'com confirmação de duplicidade' : '';
  });
  await passo('Emitir com ISS retido (regra específica do tomador)', async () => {
    await ir('emitir', 1500); await escolherCliente('#e_cli', 'ESPACO CULTIVAR FONOAUDIOLOGIA LTDA — 54.399.432/0001-46');
    await p.fill('#e_valor', '500,00'); await p.click('#e_btn'); await espera(5000);
    const r = await p.textContent('#e_res'); certo(/✔/.test(r), r);
  });
  await passo('Notas emitidas: lista, filtros e busca', async () => {
    await ir('notas', 1500); await p.click('#nf_todas'); await espera(800);
    const n = await p.$$eval('[data-cp]', x => x.length); certo(n >= 4, `só ${n} nota(s) na lista`);
    await p.fill('#nf_busca', 'PORTAL'); await espera(800);
    certo((await p.$$eval('[data-cp]', x => x.length)) >= 1, 'busca não achou');
    return `${n} notas`;
  });
  await passo('Notas emitidas: cancelar NFS-e com justificativa', async () => {
    await ir('notas', 1500); await p.click('#nf_todas'); await espera(800);
    await p.click('[data-cn]'); await espera(300);
    await p.fill('#cn_just', 'Nota emitida com valor incorreto no teste'); await p.dispatchEvent('#cn_just', 'input');
    await p.click('#cn_ok'); await espera(4000);
    certo(/cancelada/.test(await aviso()), await aviso());
  });
  await passo('Notas emitidas: botão Copiar abre Emitir nota preenchida', async () => {
    await ir('notas', 1500); await p.click('#nf_todas'); await espera(800);
    await p.click('[data-cp]'); await espera(2000);
    certo((await p.inputValue('#e_valor')) !== '' && (await p.inputValue('#e_cli')) !== '', 'não preencheu');
  });

  // ------------------------------------------------------------ contas a receber
  await passo('Contas a receber: título avulso com NFS-e após o pagamento', async () => {
    await ir('receber', 1500); await p.click('#novo_t'); await espera(300);
    await p.fill('#fn [name=cliente]', PORTAL); await p.fill('#fn [name=valor]', '250,00');
    await p.fill('#fn [data-de], #fn .data-pt input[type=text]', '20/10/2026'); await p.selectOption('#fn [name=nfse]', 'pagamento');
    await p.click('#ok'); await espera(4000);
    const t = (await api('titulos', { filtro: 'todos' })).find(x => x.valor_cent === 25000);
    certo(t && t.nfse_status === 'apos_pagamento' && t.banco_id, 'título/boleto não criado: ' + JSON.stringify(t || {}).slice(0, 200));
  });
  await passo('Contas a receber: dar baixa (emite a NFS-e sozinho)', async () => {
    const t = (await api('titulos', { filtro: 'todos' })).find(x => x.valor_cent === 25000);
    await ir('receber', 1500); await p.evaluate(([id, v]) => baixar(id, v), [t.id, t.total_cent]); await espera(300);
    await p.click('#ok'); await espera(5000);
    let d = (await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id);
    if (d.nfse_status === 'duplicidade') {            // mesma competência e serviço de outra nota do cliente: confirma
      await api('titulo/forcar_nfse', { id: t.id, confirmar_duplicidade: true });
      d = (await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id);
    }
    certo(d.status === 'pago' && d.nfse_status === 'emitida', `status ${d.status}, NFS-e ${d.nfse_status}`);
  });
  await passo('Contas a receber: estornar pagamento', async () => {
    const t = (await api('titulos', { filtro: 'pago' }))[0];
    await ir('receber'); await p.evaluate(id => estornar(id), t.id); await espera(1500);
    certo((await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id).status === 'aberto', 'não estornou');
  });
  await passo('Contas a receber: cobrar (e-mail + WhatsApp)', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' }))[0];
    await ir('receber'); await p.evaluate(id => cobrar(id), t.id); await espera(2500);
    certo(/E-mail enviado/.test(await p.textContent('#modal_corpo')), (await p.textContent('#modal_corpo')).slice(0, 200));
    await p.evaluate(() => fechar());
  });
  await passo('WhatsApp: marcar o cliente que recebe cobrança por WhatsApp', async () => {
    await ir('clientes', 1200);
    const marca = '[data-wa="32396063000103"]';
    if (!(await p.isChecked(marca))) await p.click(marca);
    await espera(1000);
    const c = (await api('estado')).clientes.find(x => x.cpf_cnpj === '32396063000103');
    certo(c && c.whatsapp_cobranca === true, 'marcação não gravada');
    certo(!(await api('estado')).clientes.find(x => x.cpf_cnpj === '35979895000132').whatsapp_cobranca, 'cliente sem marcação ficou marcado');
  });
  await passo('Contas a receber: boleto em PDF', async () => {
    const t = (await api('titulos', { filtro: 'todos' })).find(x => x.banco_id && x.status === 'aberto');
    const r = await p.evaluate(id => fetch(`/boleto/${id}.pdf`).then(async x => [x.status, (await x.text()).slice(0, 4)]), t.id);
    certo(r[0] === 200 && r[1] === '%PDF', 'PDF: ' + r);
  });
  await passo('Contas a receber: PDFs dos boletos e exportar CSV', async () => {
    const r = await api('boletos/baixar', {}); certo(r.baixados + r.ja_existiam >= 1, JSON.stringify(r));
    const csv = await p.evaluate(() => fetch('/export/titulos.csv').then(x => x.text())); certo(csv.split('\n').length > 2, 'CSV vazio');
  });
  await passo('Contas a receber: editar título (vencimento) refaz o boleto no banco', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' })).find(x => x.banco_id);
    certo(t, 'nenhum título em aberto com boleto');
    await ir('receber'); await p.evaluate(id => editarTitulo(id), t.id); await espera(1200);
    certo(/Editar título/.test(await p.textContent('#modal_corpo')), 'modal de edição não abriu');
    const novoVenc = new Date(t.vencimento + 'T12:00:00'); novoVenc.setDate(novoVenc.getDate() + 3);
    const iso = novoVenc.toISOString().slice(0, 10);
    await p.fill('#fe [name=vencimento]', iso); await p.click('#modal_corpo #ok'); await espera(4000);
    const d = (await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id);
    certo(d.vencimento === iso, 'vencimento não mudou: ' + d.vencimento);
    certo(d.banco_id && d.banco_id !== t.banco_id, 'boleto não foi refeito: ' + d.banco_id);
    certo(/atualizado/.test(await aviso()), await aviso());
  });
  await passo('Contas a receber: filtro por coluna (texto e lista), contagem e limpar', async () => {
    await ir('receber'); await p.click('.abas button[data-f="todos"]'); await espera(1500);
    const B = '.tabela-bloco[data-flt="receber"]';
    const total = await p.$$eval(B + ' tbody tr[data-fv]', r => r.length);
    const nome = (await p.$$eval(B + ' tbody tr[data-fv] td:first-child .nome', t => t.map(x => x.textContent)))[0].split(' ')[0];
    await p.fill(B + ' input.flt[data-i="0"]', nome.toLowerCase()); await espera(400);
    const vis = await p.$$eval(B + ' tbody tr[data-fv]:not([hidden])', r => r.length);
    certo(vis > 0 && vis < total, `filtro de cliente não filtrou: ${vis} de ${total}`);
    certo(/de \d+ com os filtros/.test(await p.textContent(B + ' .flt-cont')), 'contagem do filtro não apareceu');
    await p.fill(B + ' input.flt[data-i="0"]', ''); await espera(300);
    const opcao = await p.$eval(B + ' select.flt[data-i="3"]', s => s.options[1].text);    // primeira situação da lista
    await p.selectOption(B + ' select.flt[data-i="3"]', { index: 1 }); await espera(400);
    const sit = await p.$$eval(B + ' tbody tr[data-fv]:not([hidden]) td:nth-child(4) .selo', t => t.map(x => x.textContent.trim()));
    certo(sit.length > 0 && sit.every(x => x === opcao), `filtro de situação "${opcao}" deixou passar: ${[...new Set(sit)].join(', ')}`);
    await p.click(B + ' .flt-limpar'); await espera(400);
    certo((await p.$$eval(B + ' tbody tr[data-fv]:not([hidden])', r => r.length)) === total, 'limpar filtros não voltou tudo');
    await p.click('.abas button[data-f="a_receber"]'); await espera(1200);
  });
  await passo('Contas a receber: histórico de cobrança', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' }))[0];
    await ir('receber'); await p.evaluate(id => historicoTitulo(id), t.id); await espera(800);
    certo(/Histórico/.test(await p.textContent('#modal_corpo')), 'histórico não abriu'); await p.evaluate(() => fechar());
  });
  await passo('Contas a receber: tirar da cobrança (nota continua válida)', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' })).find(x => x.nfse_status === 'emitida');
    await ir('receber'); await p.evaluate(id => tirarDaCobranca(id), t.id); await espera(2000);
    const d = (await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id);
    certo(d.situacao === 'sem_cobranca' && d.nfse_status === 'emitida', d.situacao);
  });
  await passo('Contas a receber: gerar cobrança de novo', async () => {
    const t = (await api('titulos', { filtro: 'sem_cobranca' }))[0];
    await ir('receber'); await p.evaluate(id => gerarCobranca(id), t.id); await espera(4000);
    certo(/gerad/.test(await aviso()), await aviso());
  });
  await passo('Contas a receber: pagamento parcial (nota do valor pago + saldo cobrado)', async () => {
    const r = await api('titulo/novo', { cpf_cnpj: '35979895000132', valor: '300,00', nfse: 'pagamento', vencimento: '2027-01-20' });
    await ir('receber', 1200); await p.evaluate(id => baixar(id, 30000), r.titulo_id); await espera(300);
    await p.fill('#fb [name=valor]', '200,00'); await p.dispatchEvent('#fb [name=valor]', 'input');
    certo(!(await p.isHidden('#fb_parcial')), 'a pergunta do pagamento parcial não apareceu');
    await p.check('[name=fb_dec][value=cobrar]'); await p.click('#ok'); await espera(5000);
    if ((await api('titulos', { filtro: 'todos' })).find(x => x.id === r.titulo_id).nfse_status === 'duplicidade')
      await api('titulo/forcar_nfse', { id: r.titulo_id, confirmar_duplicidade: true });
    const ts = await api('titulos', { filtro: 'todos' }), t = ts.find(x => x.id === r.titulo_id);
    certo(t.parcial_status === 'cobrar' && t.nota_cent === 20000 && t.nfse_status === 'emitida', JSON.stringify(t).slice(0, 300));
    const saldo = ts.find(x => x.id === t.saldo_titulo_id);
    certo(saldo && saldo.valor_cent === 10000 && saldo.nfse_status === 'apos_pagamento' && saldo.nota_cent === 10000, 'saldo: ' + JSON.stringify(saldo || {}).slice(0, 200));
    await api('titulo/baixar', { id: saldo.id, valor: '100,00', forma: 'pix' });
    certo((await api('titulos', { filtro: 'todos' })).find(x => x.id === saldo.id).nfse_status === 'emitida', 'nota do saldo não saiu');
  });
  await passo('Contas a receber: título sem NFS-e e cancelar título', async () => {
    const r = await api('titulo/novo', { cpf_cnpj: '35979895000132', valor: '99,00', nfse: 'nao', cobrar: false });
    await ir('receber'); respostas = ['Lançado em duplicidade'];
    await p.evaluate(id => cancelarTitulo(id, 'nao_emitir'), r.titulo_id); await espera(1500);
    certo((await api('titulos', { filtro: 'todos' })).find(x => x.id === r.titulo_id).status === 'cancelado', 'não cancelou');
  });
  await passo('Contas a receber: cancelar título COM NFS-e (cancela a nota)', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' })).find(x => x.nfse_status === 'emitida');
    await ir('receber'); await p.evaluate(([id]) => cancelarTitulo(id, 'emitida'), [t.id]); await espera(400);
    respostas = ['Serviço não prestado, cancelamento solicitado pelo cliente']; await p.click('#cx_nfse'); await espera(4000);
    const d = (await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id);
    certo(d.status === 'cancelado' && d.nfse_status === 'cancelada', `${d.status}/${d.nfse_status}`);
  });
  await passo('Contas a receber: todas as abas abrem', async () => {
    await ir('receber'); for (const f of ['a_receber', 'atrasado', 'juridico', 'pago', 'sem_cobranca', 'sem_nfse', 'cancelado', 'todos']) { await p.click(`.abas button[data-f="${f}"]`); await espera(500); }
  });

  await passo('Cartão de crédito (InfinitePay): link com a taxa repassada e "Pago no cartão"', async () => {
    const r0 = await api('titulo/novo', { cpf_cnpj: '35979895000132', valor: '1.000,00', nfse: 'pagamento', cobrar: true });
    let t = (await api('titulos', { filtro: 'todos' })).find(x => x.id === r0.titulo_id);
    certo(t.cartao_link && t.cartao_total_cent > t.valor_cent, 'cobrança sem link de cartão');
    await ir('receber', 1200); await p.evaluate(([id, v]) => linkCartao(id, v), [t.id, t.valor_cent]); await espera(1200);
    certo(/no cartão/.test(await p.textContent('#lc_sim')), await p.textContent('#lc_sim'));
    await p.click('#lc_ok'); await espera(1500); certo(/Link/.test(await p.textContent('#lc_res')), await p.textContent('#lc_res'));
    await p.evaluate(() => fechar());
    await api('teste/infinitepay_pagar', { order_nsu: t.cartao_id, transaction_nsu: '9f1c2d3e-0000-4000-8000-123456789abc', slug: 'rec1', valor: t.cartao_total_cent });
    await ir('receber', 1200); await p.evaluate(id => pagoCartao(id), t.id); await espera(1000);
    await p.fill('#fpc [name=comprovante]', `https://checkout.infinitepay.io/retorno?order_nsu=${t.cartao_id}&slug=rec1&transaction_nsu=9f1c2d3e-0000-4000-8000-123456789abc`);
    await p.click('#ok'); await espera(4000);
    certo(/conferido na InfinitePay/.test(await aviso()), await aviso());
    t = (await api('titulos', { filtro: 'todos' })).find(x => x.id === r0.titulo_id);
    certo(t.status === 'pago' && t.forma_pagamento === 'cartao' && t.nfse_status === 'emitida', `${t.status}/${t.forma_pagamento}/${t.nfse_status}`);
    certo((await api('despesas', { filtro: 'pago' })).some(d => /Taxa do cartão/.test(d.descricao)), 'taxa não lançada em despesas');
    return `cliente pagou ${(t.valor_pago_cent / 100).toFixed(2)} no cartão`;
  });
  await passo('Configurações: testar InfinitePay e simulação da taxa', async () => {
    await ir('config', 1500); certo(/no cartão à vista/.test(await p.textContent('#cartao_sim')), 'simulação não apareceu');
    await p.click('#teste_cartao'); await espera(2000); certo(/InfinitePay OK/.test(await aviso()), await aviso());
  });

  // ------------------------------------------------------------ recorrência
  await passo('Recorrência: marcar "Repetir todo mês" e salvar', async () => {
    const l0 = (await api('recorrencia')).linhas.find(x => x.cpf_cnpj === '35979895000132');
    const k = l0.id ? 'k' + l0.id : 'c' + l0.cpf_cnpj;
    await ir('contratos', 1500);
    await p.fill(`.rc[data-c="valor"][data-k="${k}"]`, '1.000,00'); await p.dispatchEvent(`.rc[data-c="valor"][data-k="${k}"]`, 'input');
    await p.check(`.rc[data-c="repetir"][data-k="${k}"]`);
    await p.click('#rc_salvar'); await espera(1500);
    const l = (await api('recorrencia')).linhas.find(x => x.cpf_cnpj === '35979895000132'); certo(l && l.repetir && l.valor_cent === 100000, 'não salvou');
  });
  await passo('Recorrência: nova recorrência (formulário)', async () => {
    await ir('contratos', 1500); await p.click('#nc'); await espera(300);
    await p.fill('#fc [name=cliente]', 'ESPACO CULTIVAR FONOAUDIOLOGIA LTDA — 54.399.432/0001-46');
    await p.fill('#fc [name=valor]', '450,00'); await p.click('#ok'); await espera(1500);
    certo((await api('contratos')).some(x => x.cpf_cnpj === '54399432000146'), 'não criou');
  });
  await passo('Recorrência: gerar títulos do mês', async () => {
    const antes = (await api('titulos', { filtro: 'todos' })).filter(t => t.competencia === '2026-11').length;
    await ir('contratos', 1500); respostas = ['2026-11']; await p.click('#gerar');
    for (let i = 0; i < 30 && !/gerado/.test(await aviso()); i++) await espera(500);
    const depois = (await api('titulos', { filtro: 'todos' })).filter(t => t.competencia === '2026-11').length;
    certo(depois > antes, `nenhum título gerado para 2026-11 (${antes} → ${depois})`);
    return `${depois - antes} título(s) gerado(s)`;
  });
  await passo('Recorrência: tirar da recorrência', async () => {
    const k = (await api('contratos')).find(x => x.cpf_cnpj === '54399432000146');
    await ir('contratos'); await p.evaluate(id => encerrar(id), k.id); await espera(1500);
    const k2 = (await api('contratos')).find(x => x.id === k.id); certo(!k2 || !k2.ativo, 'continua ativo');
  });

  // ------------------------------------------------------------ cobrança
  await passo('Cobrança: rodar régua e fila de WhatsApp', async () => {
    await ir('cobranca', 1200); await p.click('#rr'); await espera(3000);
    certo(/Régua/.test(await aviso()), await aviso());
    await api('whatsapp/fila');
  });
  await passo('Cobrança: WhatsApp em sequência (só clientes marcados)', async () => {
    const hoje = (await api('painel')).hoje;                // data do sistema (Brasília), não a do navegador
    for (const doc of ['32396063000103', '35979895000132'])
      await api('titulo/novo', { cpf_cnpj: doc, valor: '123,45', descricao: 'HONORARIOS TESTE WHATSAPP', vencimento: hoje, nfse: 'nao' });
    await ir('cobranca', 1200); await p.click('#rr'); await espera(3500);
    const fila = await api('whatsapp/fila');
    certo(fila.length >= 1 && fila.every(e => /RPS/.test(e.cliente_nome)), 'fila: ' + fila.map(e => e.cliente_nome).join(', '));
    await ir('cobranca', 1200); await p.click('#wa_seq'); await espera(400);
    for (let i = 0; i < fila.length; i++) {
      const href = await p.getAttribute('#seq_abrir', 'href');
      certo(/^https:\/\/wa\.me\/5521988887777\?text=/.test(href), 'link ' + href);
      await p.click('#seq_ok'); await espera(900);
    }
    certo((await api('whatsapp/fila')).length === 0, 'fila não esvaziou');
    return `${fila.length} mensagem(ns) aberta(s) em sequência`;
  });
  await passo('WhatsApp automático: conectar (QR Code) pela tela', async () => {
    await ir('config', 1500);
    certo(/não conectado/.test(await p.textContent('#ww_estado')), await p.textContent('#ww_estado'));
    await p.click('#ww_conectar'); await espera(3000);
    certo((await api('whatsapp_web/estado')).conectando, 'janela do QR Code não abriu');
    await api('teste/whatsapp_web_logar');                    // "celular leu o QR Code"
    let e; for (let i = 0; i < 30 && !(e = await api('whatsapp_web/estado')).ativo; i++) await espera(1000);
    certo(e.ativo, JSON.stringify(e)); await espera(3000);
    certo(/conectado ✔/.test(await p.textContent('#ww_estado')), await p.textContent('#ww_estado'));
  });
  await passo('WhatsApp automático: régua envia sozinha (só cliente marcado)', async () => {
    const h = (await api('painel')).hoje, d = new Date(Date.parse(h + 'T12:00:00Z') + 3 * 864e5).toISOString().slice(0, 10);   // data do sistema (Brasília)
    for (const doc of ['32396063000103', '35979895000132'])
      await api('titulo/novo', { cpf_cnpj: doc, valor: '222,22', descricao: 'HONORARIOS WHATSAPP AUTOMATICO', vencimento: d, nfse: 'nao' });
    await ir('cobranca', 1200); await p.click('#rr'); await espera(1500);
    certo(/saindo sozinhos/.test(await aviso()), await aviso());
    let env = []; for (let i = 0; i < 40 && !(env = (await api('teste/whatsapp_web_enviados')).enviados).length; i++) await espera(1000);
    for (let i = 0; i < 30 && !env.some(e => e.arquivo); i++) { await espera(1000); env = (await api('teste/whatsapp_web_enviados')).enviados; }
    await espera(2000); env = (await api('teste/whatsapp_web_enviados')).enviados;   // o PDF sai logo depois do texto
    const txt = env.filter(e => e.texto && !/^Boleto com vencimento em/.test(e.texto)), docs = env.filter(e => e.arquivo);   // legenda de cada PDF extra não conta
    certo(txt.length === 1 && txt[0].fone === '5521988887777' && /222,22/.test(txt[0].texto) && !/anexo/.test(txt[0].texto),
      JSON.stringify(env).slice(0, 300));
    certo(docs.length >= 1 && docs.every(d => /\.pdf$/i.test(d.arquivo)), 'boleto em PDF não foi junto: ' + JSON.stringify(docs));
    certo(/títulos|Total/.test(txt[0].texto) || docs.length === 1, 'cliente com vários títulos deveria receber a cobrança somada: ' + txt[0].texto.slice(0, 200));
    for (let i = 0; i < 40 && (await api('whatsapp/fila')).length; i++) await espera(1000);
    certo((await api('whatsapp/fila')).length === 0, 'fila não esvaziou: ' + JSON.stringify(await api('whatsapp/fila')).slice(0, 300));
    return `lembrete e boleto em PDF (${docs[0].arquivo}) enviados sozinhos para 5521988887777`;
  });
  await passo('WhatsApp automático: mensagem de teste para 21 97186-7366', async () => {
    await ir('config', 1500); await p.fill('#ww_tel', '21 97186-7366'); await p.click('#ww_teste');
    for (let i = 0; i < 40 && !/Mensagem de teste enviada|não|erro/i.test(await aviso()); i++) await espera(1000);   // espera o WhatsApp terminar a fila
    certo(/Mensagem de teste enviada/.test(await aviso()), await aviso());
    const env = (await api('teste/whatsapp_web_enviados')).enviados.at(-1);
    certo(env.fone === '5521971867366' && /TESTE/.test(env.texto), JSON.stringify(env).slice(0, 200));
  });

  // ------------------------------------------------------------ contas a pagar
  await passo('Contas a pagar: nova, editar, pagar e excluir', async () => {
    await ir('pagar'); await p.click('#nd'); await espera(900);
    await p.fill('#fd [name=descricao]', 'ALUGUEL OUTUBRO'); await p.fill('#fd [name=valor]', '1.500,00'); await p.check('#fd [name=recorrente]');
    await p.click('#ok'); await espera(1000);
    let d = (await api('despesas', { filtro: 'todos' })).find(x => x.descricao === 'ALUGUEL OUTUBRO'); certo(d, 'não criou');
    await p.evaluate(x => editarDesp(x), d); await p.fill('#fd [name=valor]', '1.600,00'); await p.click('#ok'); await espera(800);
    d = (await api('despesas', { filtro: 'todos' })).find(x => x.id === d.id); certo(d.valor_cent === 160000, 'não editou');
    await p.evaluate(id => pagarDesp(id), d.id); await espera(800);
    certo((await api('despesas', { filtro: 'pago' })).some(x => x.id === d.id), 'não pagou');
    const n = await api('despesa/salvar', { descricao: 'EXCLUIR', valor: '10' });
    await p.evaluate(id => excluirDesp(id), n.id); await espera(800);
    certo(!(await api('despesas', { filtro: 'todos' })).some(x => x.id === n.id), 'não excluiu');
  });

  // ------------------------------------------------------------ conciliação
  await passo('Conciliação: importar extrato OFX (baixa automática)', async () => {
    const t = (await api('titulos', { filtro: 'a_receber' }))[0];
    const v = (t.valor_cent / 100).toFixed(2);
    const ofx = path.join(pasta, 'extrato.ofx');
    fs.writeFileSync(ofx, `<OFX><BANKACCTFROM><BANKID>077<BRANCHID>0001<ACCTID>12345</BANKACCTFROM><BANKTRANLIST>
<STMTTRN><DTPOSTED>20261015<TRNAMT>${v}<FITID>F1<MEMO>PIX RECEBIDO T${t.id} ${t.cliente_nome}</STMTTRN>
<STMTTRN><DTPOSTED>20261016<TRNAMT>-35.00<FITID>F2<MEMO>TARIFA BANCARIA</STMTTRN></BANKTRANLIST></OFX>`);
    await ir('conciliacao', 1200); await p.setInputFiles('#ofx', ofx); await espera(3000);
    const r = await p.textContent('#conteudo'); certo(/Extrato OFX: 2 lançamento/.test(r) && /<b>1<\/b> recebimento/.test(await p.innerHTML('#conteudo')), `tela: ${r.slice(0, 200)}`);
    certo((await api('titulos', { filtro: 'todos' })).find(x => x.id === t.id).status === 'pago', 'título não baixado');
  });
  await passo('Conciliação: baixar extrato do Inter pela API', async () => {
    await ir('conciliacao', 1200); await p.click('#ext_baixar'); await espera(3000);
    certo(/Extrato do Inter: \d+ lançamento/.test(await p.textContent('#conteudo')), (await p.textContent('#conteudo')).slice(0, 200));
  });
  await passo('Conciliação: vincular lançamento manualmente', async () => {
    const t = (await api('titulo/novo', { cpf_cnpj: '35979895000132', valor: '77,77', nfse: 'nao', cobrar: false }));
    await api('conciliacao/importar', { ofx: '<OFX><BANKACCTFROM><BANKID>077<BRANCHID>0001<ACCTID>12345</BANKACCTFROM><STMTTRN><DTPOSTED>20261017<TRNAMT>77.77<FITID>F9<MEMO>DEPOSITO</STMTTRN><STMTTRN><DTPOSTED>20261017<TRNAMT>77.77<FITID>F10<MEMO>DEPOSITO 2</STMTTRN></OFX>' });
    const pend = await api('conciliacao/pendentes'); const m = pend.find(x => x.valor_cent === 7777);
    if (m && m.sugestoes.length) { await ir('conciliacao'); await p.evaluate(([a, b2]) => vincular(a, b2), [m.id, m.sugestoes[0].id]); await espera(1500); }
    certo((await api('titulos', { filtro: 'todos' })).find(x => x.id === t.titulo_id).status === 'pago', 'não vinculou');
  });

  // ------------------------------------------------------------ relatórios
  await passo('Relatórios: todas as abas', async () => {
    await ir('relatorios', 1200);
    for (const a of ['indicadores', 'dre', 'fluxo', 'livro', 'aging', 'clientes', 'fechamento', 'log']) { await p.click(`.abas button[data-a="${a}"]`); await espera(700); }
    for (const r of ['rel/aging', 'rel/clientes', 'rel/fluxo', 'rel/dre', 'rel/indicadores', 'rel/fluxo_mensal', 'rel/livro_caixa']) {
      const x = await api(r); certo(!x.erro, `${r}: ${x.erro}`); }
  });
  await passo('Relatórios: fechamento mensal e página do relatório', async () => {
    const r = await api('fechamento/gerar'); certo(r.resultado, 'sem resultado');
    const h = await p.evaluate(() => fetch('/fechamento/2026-10.html').then(x => x.status)); certo(h === 200, 'HTTP ' + h);
  });
  await passo('Resumo diário por e-mail', async () => { const r = await api('resumo/enviar'); certo(!r.erro, r.erro); return r.resultado; });

  // ------------------------------------------------------------ canal nacional
  await passo('Trocar canal para NFS-e Nacional e emitir', async () => {
    await api('config/salvar', { emissao: { canal: 'nacional' } });
    await ir('emitir', 1500); await escolherCliente('#e_cli', RPS);
    await p.fill('#e_valor', '374,40'); await p.click('#e_btn'); await espera(6000);
    let r = await p.textContent('#e_res');
    if (await p.$('#dp_sim')) { await p.click('#dp_sim'); await espera(6000); r = await aviso(); }   // confirma a duplicidade
    const t = (await api('titulos', { filtro: 'todos' })).filter(x => x.cpf_cnpj === '32396063000103' && x.nfse_canal === 'nacional' && x.nfse_status === 'emitida');
    certo(t.length, r);
  });
  await passo('Nacional: exportação para cliente do exterior', async () => {
    const c = (await api('estado')).clientes.find(x => x.estrangeiro);
    const r = await api('emitir', { cpf_cnpj: c.cpf_cnpj, valor: '500', cobrar: false, extras: { comext_moeda: '220', comext_valor: '95' } });
    certo(r.sucesso, (r.erros || []).join('; '));
  });
  await passo('Nacional: substituir nota', async () => {
    await ir('notas', 1500); await p.click('#nf_todas'); await espera(800);
    await p.click('[data-sb]'); await espera(2000);
    await p.selectOption('[data-nx="subst_motivo"]', '99'); await p.fill('[data-nx="subst_xmotivo"]', 'Correção do valor');
    await p.click('#e_btn'); await espera(6000);
    certo(/✔/.test(await p.textContent('#e_res')), await p.textContent('#e_res'));
  });
  await passo('Nacional: cancelar NFS-e', async () => {
    await ir('notas', 1500); await p.click('#nf_todas'); await espera(800);
    const n = await p.$$('[data-cn]'); await n[0].click(); await espera(300);
    await p.fill('#cn_just', 'Cancelamento de teste no ambiente nacional'); await p.dispatchEvent('#cn_just', 'input');
    await p.click('#cn_ok'); await espera(4000); certo(/cancelada/.test(await aviso()), await aviso());
  });
  await passo('Nacional: emissão pelo tomador (importação de serviço)', async () => {
    const c = (await api('estado')).clientes.find(x => x.estrangeiro);
    const r = await api('emitir', { cpf_cnpj: c.cpf_cnpj, valor: '300', extras: { tp_emit: '2', motivo_emis_ti: '1', comext_moeda: '220', comext_valor: '60' } });
    certo(r.sucesso && (r.alertas || []).some(a => /tomadora/.test(a)), JSON.stringify(r).slice(0, 300));
    await api('config/salvar', { emissao: { canal: 'municipal' } });
  });

  // ------------------------------------------------------------ backup
  await passo('Backup: fazer backup agora', async () => {
    await ir('config', 1500); await p.click('#bk_criar'); await espera(3000);
    certo(/Backup criado/.test(await aviso()), await aviso());
  });
  await passo('Backup: protegido por senha e restauração', async () => {
    await api('config/salvar', { seguranca: { backup_senha: 'senha-forte-1' } });
    const b2 = await api('backup/criar'); certo(b2.nome.endsWith('.protegido'), b2.nome);
    await ir('config', 1500); respostas = ['senha-forte-1'];
    await p.click(`[data-bk="${b2.nome}"]`); await espera(5000);
    certo(/restaurado/.test(await aviso()), await aviso());
    await api('config/salvar', { seguranca: { backup_senha: '' } });
  });
  await passo('Backup: restaurar de um arquivo', async () => {
    const b3 = await api('backup/criar');
    const arq = path.join(pasta, 'dados', 'backup', b3.nome);
    await ir('config', 1500); await p.setInputFiles('#bk_arq', arq); await espera(5000);
    certo(/restaurado/.test(await aviso()), await aviso());
  });

  // ------------------------------------------------------------ PIN
  await passo('PIN: ativar, bloquear, entrar e remover', async () => {
    await ir('config', 1500); await p.fill('#pin_novo', '2468'); await p.click('#pin_salvar'); await espera(800);
    const outra = await (await b.newContext()).newPage(); await outra.goto(URL); await espera(1200);
    certo(await outra.isVisible('#pin_v'), 'tela não bloqueou');
    await outra.fill('#pin_v', '1111'); await outra.press('#pin_v', 'Enter'); await espera(800);
    certo(/incorreto/.test(await outra.textContent('#pin_msg')), 'PIN errado aceito');
    await outra.fill('#pin_v', '2468'); await outra.press('#pin_v', 'Enter'); await espera(1500);
    certo(!(await outra.isVisible('#pin_v')), 'PIN certo não entrou');
    await outra.close();
    await ir('config', 1500); await p.fill('#pin_atual', '2468'); await p.click('#pin_remover'); await espera(800);
    certo(!(await api('acesso/estado')).ativo, 'PIN não removido');
  });

  // ------------------------------------------------------------ multiempresa
  await passo('Multiempresa: cadastrar, trocar e isolamento dos dados', async () => {
    await p.evaluate(() => trocarEmpresa()); await espera(600);
    await p.click('.nova-emp summary'); await p.fill('#f_emp [name=nome]', 'PADARIA BOM PAO LTDA'); await p.fill('#f_emp [name=cnpj]', '11222333000181');
    await p.click('#criar_emp'); await espera(2000);
    const e = await api('estado'); certo(e.empresa.cnpj === '11222333000181' && e.clientes.length === 0, 'nova empresa não isolada');
    await p.evaluate(() => trocarEmpresa()); await espera(600);
    await p.click('.emp[data-id="24875410000144"]'); await espera(2000);
    certo((await api('estado')).clientes.length >= 3, 'não voltou para a empresa principal');
  });

  // ------------------------------------------------------------ validação e atualização
  await passo('Validação: "Testar tudo" com as integrações (simuladas)', async () => {
    await api('ambiente', { producao: false });
    await ir('validacao', 1500); await p.click('#val_todos'); await espera(25000);
    const s = await api('validacao'); const ruins = s.passos.filter(x => !x.ultimo || !(['ok', 'alerta'].includes(x.ultimo.situacao)));
    certo(!ruins.length, ruins.map(x => `${x.id}: ${x.ultimo ? x.ultimo.situacao + ' ' + x.ultimo.mensagem : 'não rodou'}`).join(' | '));
    return `${s.concluidos}/${s.total} aprovados`;
  });
  await passo('Atualização: analisar ZIP e atualizar (sem reiniciar)', async () => {
    const zip = path.join(pasta, 'nova.zip');
    execSync(`git -C "${path.join(__dirname, '..', '..')}" archive --prefix=EmissorItaborai/ -o "${zip}" HEAD`);
    const b64 = fs.readFileSync(zip).toString('base64');
    const a = await api('atualizacao/analisar', { arquivo: b64 }); certo(a.versao_nova && a.arquivos > 50, JSON.stringify(a));
    const r = await api('atualizacao/aplicar', { arquivo: b64, permitir_anterior: true, reiniciar: false });
    certo(r.ok && r.backups.length >= 1, JSON.stringify(r).slice(0, 200));
    const v = await api('atualizacao/versoes'); certo(v.versoes.length >= 1, 'versão anterior não guardada');
  });

  // ------------------------------------------------------------ varredura final e encerrar
  await passo('Todas as páginas abrem sem erro depois de tudo', async () => {
    for (const pg of ['painel', 'emitir', 'lote', 'notas', 'receber', 'contratos', 'cobranca', 'pagar', 'conciliacao', 'relatorios', 'clientes', 'config', 'validacao']) {
      await ir(pg, 900); const a = await aviso(); certo(!/⚠/.test(a), `${pg}: ${a}`); }
  });
  await passo('Encerrar o sistema', async () => {
    await p.click('#sair'); await espera(2500);
    certo(/Sistema encerrado/.test(await p.textContent('body')), 'tela de encerramento não apareceu');
    const vivo = await fetch(`${URL}/api/versao`).then(() => true).catch(() => false); certo(!vivo, 'servidor continua no ar');
  });

  await b.close();
  const falhas = resultados.filter(r => !r.ok);
  console.log(`\n${resultados.length - falhas.length} de ${resultados.length} funções OK`);
  fs.writeFileSync(path.join(pasta, 'resultado_funcional.json'), JSON.stringify(resultados, null, 2));
  process.exit(falhas.length ? 1 : 0);
})();
