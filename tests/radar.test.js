'use strict';
var test = require('node:test');
var assert = require('node:assert/strict');

var simples = require('../app/js/simples-nacional.js');
var ncm = require('../app/js/ncm-monofasico.js');
var nfe = require('../app/js/nfe-parser.js');
var analise = require('../app/js/analise.js');

function proximo(a, b, tol) { assert.ok(Math.abs(a - b) < (tol || 0.005), a + ' ≠ ' + b); }

test('alíquota efetiva do Anexo I', function () {
  proximo(simples.aliquotaEfetiva(150000), 0.04);
  // 4ª faixa: (1.200.000 × 10,7% − 22.500) / 1.200.000 = 8,825%
  proximo(simples.aliquotaEfetiva(1200000), 0.08825, 1e-9);
  assert.equal(simples.faixaPorRbt12(5000000), null);
});

test('percentual de PIS/COFINS e ICMS dentro do DAS', function () {
  var p = simples.percentuaisRecuperaveis(1200000);
  proximo(p.pisCofins, 0.08825 * 0.155, 1e-9);
  proximo(p.icms, 0.08825 * 0.335, 1e-9);
  assert.equal(simples.percentuaisRecuperaveis(4000000).icms, 0); // 6ª faixa
});

test('classificação de NCM monofásico', function () {
  assert.equal(ncm.classificar('3004.90.99').grupo, 'FARMA');
  assert.equal(ncm.classificar('33051000').grupo, 'HIGIENE');
  assert.equal(ncm.classificar('87089990').grupo, 'AUTOPECAS');
  assert.equal(ncm.classificar('22030000').grupo, 'BEBIDAS');
  assert.equal(ncm.classificar('30049046'), null, 'exceção legal');
  assert.equal(ncm.classificar('96190000'), null, 'fralda não é monofásica');
});

var XML = '<nfeProc><NFe><infNFe Id="NFe35250111222333000181650010000000011000000011" versao="4.00">' +
  '<ide><mod>65</mod><nNF>1</nNF><dhEmi>2025-01-15T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide>' +
  '<emit><CNPJ>11222333000181</CNPJ><xNome>FARMACIA &amp; CIA</xNome><CRT>1</CRT></emit>' +
  '<dest><CNPJ>99999999000199</CNPJ></dest>' +
  '<det nItem="1"><prod><cProd>1</cProd><xProd>DIPIRONA</xProd><NCM>30049099</NCM><CFOP>5405</CFOP>' +
  '<vProd>1000.00</vProd><vDesc>100.00</vDesc></prod><imposto><ICMS><ICMSSN500><CSOSN>500</CSOSN></ICMSSN500></ICMS>' +
  '<PIS><PISOutr><CST>49</CST></PISOutr></PIS></imposto></det>' +
  '<det nItem="2"><prod><cProd>2</cProd><xProd>FRALDA</xProd><NCM>96190000</NCM><CFOP>5102</CFOP>' +
  '<vProd>500.00</vProd></prod><imposto><ICMS><ICMSSN102><CSOSN>102</CSOSN></ICMSSN102></ICMS></imposto></det>' +
  '</infNFe></NFe></nfeProc>';

test('leitura de XML de NFC-e', function () {
  var d = nfe.lerXml(XML);
  assert.equal(d.tipo, 'nfe');
  assert.equal(d.emitente.cnpj, '11222333000181');
  assert.equal(d.emitente.nome, 'FARMACIA & CIA');
  assert.equal(d.competencia, '2025-01');
  assert.equal(d.itens.length, 2);
  assert.equal(d.itens[0].valor, 900);
  assert.equal(d.itens[0].csosn, '500');
});

test('leitura de evento de cancelamento', function () {
  var ev = nfe.lerXml('<procEventoNFe><evento><infEvento><chNFe>123</chNFe><tpEvento>110111</tpEvento></infEvento></evento></procEventoNFe>');
  assert.deepEqual(ev, { tipo: 'cancelamento', chave: '123' });
});

test('apuração do crédito com RBT12 informado', function () {
  var docs = [nfe.lerXml(XML)];
  var r = analise.analisar(docs, { hoje: '2026-10-10', rbt12Padrao: 1200000, percentualHonorarios: 0.2 });
  var m = r.meses[0];
  assert.equal(m.receitaTotal, 1400);
  assert.equal(m.receitaMonofasica, 900);
  assert.equal(m.receitaIcmsSt, 900);
  proximo(m.creditoPisCofins, 900 * 0.08825 * 0.155);
  proximo(m.creditoIcms, 900 * 0.08825 * 0.335);
  proximo(r.honorarios, r.totais.credito * 0.2);
});

test('cancelamento, duplicidade e prescrição', function () {
  var d = nfe.lerXml(XML);
  var cancel = { tipo: 'cancelamento', chave: d.chave };
  assert.equal(analise.analisar([d, cancel], { hoje: '2026-10-10', rbt12Padrao: 1e6 }).notasConsideradas, 0);
  assert.equal(analise.analisar([d, d], { hoje: '2026-10-10', rbt12Padrao: 1e6 }).notasConsideradas, 1);
  var r = analise.analisar([d], { hoje: '2030-10-10', rbt12Padrao: 1e6 });
  assert.equal(r.meses[0].status, 'prescrito');
  assert.equal(r.totais.credito, 0);
});

test('RBT12 calculado a partir dos próprios XMLs', function () {
  var docs = [];
  for (var i = 0; i < 13; i++) {
    var comp = analise.somarMeses('2025-01', i);
    docs.push(nfe.lerXml(XML.replace('2025-01-15', comp + '-15').replace('NFe352501', 'NFe35' + comp.slice(2, 4) + comp.slice(5, 7))
      .replace('0000000011"', String(i).padStart(10, '0') + '"')));
  }
  var r = analise.analisar(docs, { hoje: '2026-10-10' });
  var ultimo = r.meses[12];
  assert.equal(ultimo.fonteRbt12, 'xml');
  assert.equal(ultimo.rbt12, 1400 * 12);
  assert.equal(r.meses[0].status, 'sem-rbt12');
});

test('CFOP de venda', function () {
  assert.ok(analise.ehVenda('5102'));
  assert.ok(analise.ehVenda('6405'));
  assert.ok(!analise.ehVenda('5202'), 'devolução não é receita');
  assert.ok(!analise.ehVenda('5949'));
});
