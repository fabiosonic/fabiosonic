#!/usr/bin/env node
/*
 * Gera extratos fictícios (OFX e CSV) de uma padaria para demonstrar o Painel Financeiro.
 * Uso: node tools/gerar-exemplos.js
 */
'use strict';
var fs = require('fs');
var path = require('path');

var DESTINO = path.join(__dirname, '..', 'exemplos', 'extratos');
var MESES = ['2026-04', '2026-05', '2026-06', '2026-07', '2026-08', '2026-09'];

// Gerador pseudoaleatório determinístico
var semente = 42;
function aleatorio() { semente = (semente * 16807) % 2147483647; return semente / 2147483647; }
function entre(a, b) { return Math.round((a + (b - a) * aleatorio()) * 100) / 100; }

function lancamentosDoMes(comp, idx) {
  var l = [];
  function add(dia, hist, valor) { l.push({ data: comp + '-' + ('0' + dia).slice(-2), hist: hist, valor: valor }); }
  var cresc = 1 + idx * 0.04;
  for (var d = 1; d <= 28; d += 3) {
    add(d, 'CIELO VENDAS CARTAO', entre(2800, 4200) * cresc);
    add(d + 1, 'PIX RECEBIDO CLIENTE', entre(600, 1400) * cresc);
  }
  add(5, 'PAG BOLETO DISTRIB TRIGO SUL LTDA', -entre(9000, 11000) * cresc);
  add(12, 'PAG BOLETO LATICINIOS SERRA IND', -entre(4500, 6000) * cresc);
  add(19, 'PAG BOLETO ATACADAO EMBALAGENS', -entre(1200, 1800));
  add(5, 'PAGTO SALARIO FUNCIONARIOS', -14800);
  add(7, 'FGTS', -1184);
  add(20, 'DAS SIMPLES NACIONAL', -entre(3200, 3900) * cresc);
  add(10, 'ALUGUEL LOJA', -6500);
  add(15, 'ENEL ENERGIA', -entre(2100, 2900));
  add(15, 'SABESP AGUA', -entre(380, 520));
  add(18, 'VIVO INTERNET', -199.9);
  add(10, 'HONORARIOS CONTABEIS', -1200);
  add(2, 'TARIFA PACOTE DE SERVICOS', -89.9);
  add(25, 'JUROS CHEQUE ESPECIAL', -entre(150, 420));
  add(28, 'PARCELA CAPITAL DE GIRO', -3150);
  add(28, 'RETIRADA SOCIOS PRO LABORE', idx === 3 ? -16000 : -9000);
  add(22, 'PIX ENVIADO MANUTENCAO FORNO JOSE', -entre(300, 900));
  return l;
}

function ofx(lancs, saldo) {
  var cab = 'OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nENCODING:USASCII\n\n<OFX>\n<BANKMSGSRSV1><STMTTRNRS><STMTRS>\n' +
    '<CURDEF>BRL\n<BANKACCTFROM><BANKID>0341<ACCTID>12345-6</BANKACCTFROM>\n<BANKTRANLIST>\n';
  var corpo = lancs.map(function (l, i) {
    return '<STMTTRN>\n<TRNTYPE>' + (l.valor < 0 ? 'DEBIT' : 'CREDIT') + '\n<DTPOSTED>' + l.data.replace(/-/g, '') +
      '120000[-3:BRT]\n<TRNAMT>' + l.valor.toFixed(2) + '\n<FITID>' + l.data.replace(/-/g, '') + String(i).padStart(4, '0') +
      '\n<MEMO>' + l.hist + '\n</STMTTRN>';
  }).join('\n');
  return cab + corpo + '\n</BANKTRANLIST>\n<LEDGERBAL><BALAMT>' + saldo.toFixed(2) +
    '<DTASOF>20260930</LEDGERBAL>\n</STMTRS></STMTTRNRS></BANKMSGSRSV1>\n</OFX>\n';
}

fs.mkdirSync(DESTINO, { recursive: true });
fs.readdirSync(DESTINO).forEach(function (f) { fs.unlinkSync(path.join(DESTINO, f)); });

var todos = [];
MESES.forEach(function (comp, i) {
  var l = lancamentosDoMes(comp, i);
  l.forEach(function (x) { x.valor = Math.round(x.valor * 100) / 100; });
  l.sort(function (a, b) { return a.data < b.data ? -1 : 1; });
  todos = todos.concat(l);
});
var saldo = 95000 + todos.reduce(function (s, l) { return s + l.valor; }, 0);
fs.writeFileSync(path.join(DESTINO, 'itau-cc-12345-6.ofx'), ofx(todos, saldo));

// Segunda conta em CSV (formato brasileiro), com maquininha de outra bandeira
var csv = ['Data;Histórico;Valor'];
MESES.forEach(function (comp) {
  for (var d = 2; d <= 28; d += 7) csv.push(d + '/' + comp.slice(5, 7) + '/' + comp.slice(0, 4) + ';STONE PAGAMENTOS;' +
    entre(1500, 2500).toFixed(2).replace('.', ','));
  csv.push('15/' + comp.slice(5, 7) + '/' + comp.slice(0, 4) + ';TARIFA MANUTENCAO CONTA;-45,00');
});
fs.writeFileSync(path.join(DESTINO, 'banco-digital.csv'), '﻿' + csv.join('\r\n'));

console.log('Extratos gerados em ' + DESTINO);
