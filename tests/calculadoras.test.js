// Execute com: node --test tests/
const test = require('node:test');
const assert = require('node:assert');
const C = require('../assets/js/calculadoras.js');

test('parseBRL aceita formatos brasileiros', () => {
  assert.strictEqual(C.parseBRL('84.000,50'), 84000.5);
  assert.strictEqual(C.parseBRL('R$ 1.234'), 1234);
  assert.strictEqual(C.parseBRL('84.000'), 84000);
  assert.strictEqual(C.parseBRL('1234.56'), 1234.56);
  assert.ok(Number.isNaN(C.parseBRL('')));
  assert.ok(Number.isNaN(C.parseBRL('abc')));
});

test('Fator R: limite de 28% define Anexo III ou V', () => {
  assert.strictEqual(C.fatorR(84000, 300000).anexo, 'III'); // exatamente 28%
  assert.strictEqual(C.fatorR(83999, 300000).anexo, 'V');
  assert.strictEqual(C.fatorR(60000, 300000).folhaNecessaria, 84000);
  assert.strictEqual(C.fatorR(1000, 0).ok, false);
  assert.strictEqual(C.fatorR(-1, 10).ok, false);
});

test('Margem e markup', () => {
  const r = C.margem(50000, 40000);
  assert.strictEqual(r.lucro, 10000);
  assert.strictEqual(r.margem, 0.2);
  assert.strictEqual(r.markup, 0.25);
  assert.strictEqual(C.margem(1000, 1500).prejuizo, true);
  assert.strictEqual(C.margem(0, 10).ok, false);
});

test('Ponto de equilíbrio', () => {
  const r = C.pontoEquilibrio(18000, 60000, 33000); // IMC 45%
  assert.ok(Math.abs(r.imc - 0.45) < 1e-12);
  assert.ok(Math.abs(r.receitaEquilibrio - 40000) < 1e-6);
  assert.strictEqual(r.atingido, true);
  assert.strictEqual(C.pontoEquilibrio(1000, 500, 500).ok, false); // IMC zero
  assert.strictEqual(C.pontoEquilibrio(1000, 500, 800).ok, false); // IMC negativo
  assert.strictEqual(C.pontoEquilibrio(1000, 0, 0).ok, false);
});

test('NCG', () => {
  assert.strictEqual(C.capitalGiro(25000, 40000, 30000).ncg, 35000);
  assert.strictEqual(C.capitalGiro(0, 10000, 30000).ncg, -20000);
});
