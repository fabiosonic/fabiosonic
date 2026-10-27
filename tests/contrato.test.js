// Execute com: node --test tests/*.test.js
const test = require('node:test');
const assert = require('node:assert');
const U = require('../assets/js/contrato.js');

test('CPF', () => {
  assert.ok(U.validaCPF('529.982.247-25'));
  assert.ok(!U.validaCPF('529.982.247-24'));
  assert.ok(!U.validaCPF('111.111.111-11'));
  assert.ok(!U.validaCPF('123'));
  assert.strictEqual(U.formataCPF('52998224725'), '529.982.247-25');
});

test('CNPJ numérico e alfanumérico (IN RFB 2.229/2024)', () => {
  assert.ok(U.validaCNPJ('24.875.410/0001-44'));        // CNPJ do escritório
  assert.ok(!U.validaCNPJ('24.875.410/0001-45'));
  assert.ok(!U.validaCNPJ('00.000.000/0000-00'));
  assert.ok(U.validaCNPJ('12.ABC.345/01DE-35'));        // exemplo da Receita Federal
  assert.ok(U.validaCNPJ('12abc34501de35'));
  assert.ok(!U.validaCNPJ('12.ABC.345/01DE-36'));
  assert.strictEqual(U.formataCNPJ('12ABC34501DE35'), '12.ABC.345/01DE-35');
});

test('preenchimento e texto canônico', async () => {
  const modelo = { versao: '1.0', dataVersao: '13/10/2026', titulo: 'Contrato', preambulo: ['Contratante: {{CONTRATANTE_NOME}}'],
    clausulas: [{ numero: 1, titulo: 'Objeto', itens: ['1.1 Pacote {{PACOTE}} em {{CONTRATANTE_MUNICIPIO}}'] }], anexos: [], fechamento: ['Fim'] };
  const c = U.montaContrato(modelo, { CONTRATANTE_NOME: 'Empresa X', PACOTE: 'Essencial' });
  assert.strictEqual(c.preambulo[0], 'Contratante: Empresa X');
  assert.strictEqual(c.clausulas[0].itens[0], '1.1 Pacote Essencial em [a preencher]');
  const t = U.textoCanonico(c);
  assert.ok(t.includes('CLÁUSULA 1 — Objeto'));
  const h1 = await U.sha256(t), h2 = await U.sha256(t), h3 = await U.sha256(t + ' ');
  assert.match(h1, /^[0-9a-f]{64}$/);
  assert.strictEqual(h1, h2);
  assert.notStrictEqual(h1, h3);
});

test('modelo do contrato: coerência com o fluxo real do site', () => {
  const fs = require('node:fs'), vm = require('node:vm'), path = require('node:path');
  const ctx = { window: {} };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/js/contrato-modelo.js'), 'utf8'), ctx);
  const M = ctx.window.MOContrato;
  assert.strictEqual(M.clausulas.length, 27);
  assert.strictEqual(M.anexos.length, 3);
  const nums = M.clausulas.map((c) => c.numero);
  M.destaques.forEach((n) => assert.ok(nums.includes(n), `destaque ${n} inexistente`));
  // O preâmbulo deve listar exatamente as cláusulas destacadas (CDC, art. 54, § 4º).
  const lista = M.destaques.slice(0, -1).join(', ') + ' e ' + M.destaques.slice(-1);
  assert.ok(M.preambulo.join(' ').includes('Cláusulas ' + lista), 'preâmbulo diverge dos destaques');
  const tudo = JSON.stringify(M);
  // O site é estático: não registra IP nem envia e-mail automaticamente.
  assert.ok(!/endereço IP/i.test(tudo), 'o site não registra IP');
  assert.ok(!/CONTRATADA envia ao e-mail/i.test(tudo), 'não há envio automático de e-mail');
  // Ética (NBC PG 01): nenhum valor monetário nas Condições Gerais.
  assert.ok(!/R\$\s*\d/.test(tudo), 'honorários só no Anexo I preenchido pelo escritório');
  assert.ok(tudo.includes('MORAES E OLIVEIRA CONTABILIDADE LTDA'));
});
