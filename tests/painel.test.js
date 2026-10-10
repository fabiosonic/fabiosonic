'use strict';
var test = require('node:test');
var assert = require('node:assert/strict');

var extrato = require('../app/js/extrato.js');
var categorias = require('../app/js/categorias.js');
var relatorio = require('../app/js/relatorio.js');

var OFX = 'OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>' +
  '<BANKACCTFROM><BANKID>0341<ACCTID>999-1</BANKACCTFROM><BANKTRANLIST>\n' +
  '<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20260105120000[-3:BRT]<TRNAMT>10000.00<FITID>1<MEMO>CIELO VENDAS</STMTTRN>\n' +
  '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260106<TRNAMT>-4000.00<FITID>2<MEMO>PAG BOLETO DISTRIB ALFA</STMTTRN>\n' +
  '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260110<TRNAMT>-600,00<FITID>3<MEMO>DAS SIMPLES NACIONAL</STMTTRN>\n' +
  '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260110<TRNAMT>-2000.00<FITID>4<MEMO>ALUGUEL</STMTTRN>\n' +
  '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260111<TRNAMT>-5000.00<FITID>5<MEMO>RETIRADA SOCIO</STMTTRN>\n' +
  '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260112<TRNAMT>-300.00<FITID>6<MEMO>PIX ENVIADO JOAO</STMTTRN>\n' +
  '</BANKTRANLIST><LEDGERBAL><BALAMT>7100.00<DTASOF>20260131</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>';

test('leitura de OFX (SGML, vírgula decimal e saldo)', function () {
  var e = extrato.lerExtrato(OFX, 'arquivo.ofx');
  assert.equal(e.formato, 'ofx');
  assert.equal(e.conta, '999-1');
  assert.equal(e.lancamentos.length, 6);
  assert.equal(e.lancamentos[0].data, '2026-01-05');
  assert.equal(e.lancamentos[2].valor, -600);
  assert.equal(e.saldoFinal, 7100);
});

test('leitura de CSV brasileiro', function () {
  var csv = '﻿Data;Histórico;Valor\r\n02/01/2026;"PIX RECEBIDO; CLIENTE";1.234,56\r\n03/01/2026;TARIFA;-45,00\r\n03/01/2026;SALDO DO DIA;999,00';
  var e = extrato.lerExtrato(csv, 'banco.csv');
  assert.equal(e.lancamentos.length, 2);
  assert.equal(e.lancamentos[0].valor, 1234.56);
  assert.equal(e.lancamentos[0].historico, 'PIX RECEBIDO; CLIENTE');
  assert.equal(e.lancamentos[1].valor, -45);
});

test('CSV com colunas separadas de crédito e débito', function () {
  var e = extrato.lerCsv('Data,Descrição,Crédito,Débito\n05/02/2026,STONE,500.00,\n06/02/2026,ENEL,,120.50', 'b.csv');
  assert.deepEqual(e.lancamentos.map(function (l) { return l.valor; }), [500, -120.5]);
});

test('números em formatos variados', function () {
  assert.equal(extrato.numero('1.234,56'), 1234.56);
  assert.equal(extrato.numero('(100,00)'), -100);
  assert.equal(extrato.numero('250,00 D'), -250);
  assert.equal(extrato.numero('-1234.5'), -1234.5);
});

test('classificação automática e regra do usuário', function () {
  assert.equal(categorias.classificar({ historico: 'CIELO VENDAS', valor: 10 }), 'receita');
  assert.equal(categorias.classificar({ historico: 'DAS SIMPLES NACIONAL', valor: -1 }), 'impostos');
  assert.equal(categorias.classificar({ historico: 'Enel Distribuição', valor: -1 }), 'utilidades');
  assert.equal(categorias.classificar({ historico: 'PIX ENVIADO JOAO', valor: -1 }), 'a_classificar');
  assert.equal(categorias.classificar({ historico: 'PIX ENVIADO JOAO', valor: -1 },
    [{ termo: 'joao', categoria: 'terceiros' }]), 'terceiros');
});

test('DRE gerencial e alertas', function () {
  var r = relatorio.gerar([extrato.lerExtrato(OFX)]);
  var m = r.meses[0];
  assert.equal(m.receitaBruta, 10000);
  assert.equal(m.deducoes, -600);
  assert.equal(m.custos, -4000);
  assert.equal(m.despesas, -2000);
  assert.equal(m.resultadoOperacional, 3400);
  assert.equal(m.naoOperacional, -5000);
  assert.equal(m.pendente, -300);
  assert.equal(m.geracaoCaixa, -1900);
  assert.ok(r.alertas.some(function (a) { return /retiradas/.test(a.texto); }));
  assert.ok(r.alertas.some(function (a) { return /a classificar/.test(a.texto); }));
  assert.equal(r.contas[0].saldoFinal, 7100);
});

test('ajuste manual, duplicidade e transferências neutras', function () {
  var e = extrato.lerExtrato(OFX);
  var r = relatorio.gerar([e, e], { ajustes: { '999-1|6': 'terceiros' } });
  assert.equal(r.meses[0].pendente, 0);
  assert.equal(r.meses[0].despesas, -2300);
  assert.ok(r.alertas.some(function (a) { return /duplicado/.test(a.texto); }));

  var t = extrato.lerCsv('Data;Hist;Valor\n01/03/2026;TRANSF ENTRE CONTAS;-1000,00\n01/03/2026;CIELO;500,00', 'x');
  var rt = relatorio.gerar([t]);
  assert.equal(rt.meses[0].saidas, 0, 'transferência não conta como saída');
  assert.equal(rt.meses[0].geracaoCaixa, 500);
});

test('ponto de equilíbrio', function () {
  var r = relatorio.gerar([extrato.lerExtrato(OFX)]);
  // margem de contribuição = (10000 - 600 - 4000) / 10000 = 54%; despesas fixas = 2000
  assert.ok(Math.abs(r.indicadores.margemContribuicao - 0.54) < 1e-9);
  assert.equal(r.indicadores.pontoEquilibrio, 3703.7);
});
