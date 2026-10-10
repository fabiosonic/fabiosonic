#!/usr/bin/env node
/*
 * Gera XMLs fictícios de NFC-e de uma farmácia optante pelo Simples Nacional,
 * para demonstração do Radar Tributário. Uso: node tools/gerar-exemplos.js
 */
'use strict';
var fs = require('fs');
var path = require('path');

var DESTINO = path.join(__dirname, '..', 'exemplos', 'xml');
var CNPJ = '11222333000181';

var PRODUTOS = [
  { cod: '001', desc: 'DIPIRONA SODICA 500MG 10CP', ncm: '30049099', csosn: '500', cfop: '5405', preco: 8.90 },
  { cod: '002', desc: 'AMOXICILINA 500MG 21CAP', ncm: '30041011', csosn: '500', cfop: '5405', preco: 32.50 },
  { cod: '003', desc: 'SHAMPOO ANTICASPA 200ML', ncm: '33051000', csosn: '500', cfop: '5405', preco: 24.90 },
  { cod: '004', desc: 'CREME DENTAL 90G', ncm: '33061000', csosn: '500', cfop: '5405', preco: 6.50 },
  { cod: '005', desc: 'FRALDA INFANTIL G 30UN', ncm: '96190000', csosn: '102', cfop: '5102', preco: 54.90 },
  { cod: '006', desc: 'AGUA MINERAL 500ML', ncm: '22011000', csosn: '500', cfop: '5405', preco: 3.00 },
  { cod: '007', desc: 'TERMOMETRO DIGITAL', ncm: '90251190', csosn: '102', cfop: '5102', preco: 29.90 }
];

function competencias() { // jan/2025 a set/2026
  var out = [];
  for (var i = 0; i < 21; i++) {
    var a = 2025 + Math.floor(i / 12), m = (i % 12) + 1;
    out.push(a + '-' + (m < 10 ? '0' : '') + m);
  }
  return out;
}

function chave(comp, n) {
  var base = '35' + comp.slice(2, 4) + comp.slice(5, 7) + CNPJ + '65' + '001' +
    String(n).padStart(9, '0') + '1' + String(n).padStart(8, '0');
  return base + String(n % 10); // DV fictício
}

function det(i, p, qtd) {
  var v = (p.preco * qtd).toFixed(2);
  return '<det nItem="' + i + '"><prod><cProd>' + p.cod + '</cProd><cEAN>SEM GTIN</cEAN><xProd>' + p.desc +
    '</xProd><NCM>' + p.ncm + '</NCM><CFOP>' + p.cfop + '</CFOP><uCom>UN</uCom><qCom>' + qtd +
    '</qCom><vUnCom>' + p.preco.toFixed(2) + '</vUnCom><vProd>' + v + '</vProd><indTot>1</indTot></prod>' +
    '<imposto><ICMS><ICMSSN' + p.csosn + '><orig>0</orig><CSOSN>' + p.csosn + '</CSOSN></ICMSSN' + p.csosn +
    '></ICMS><PIS><PISOutr><CST>49</CST><vBC>0.00</vBC><pPIS>0.00</pPIS><vPIS>0.00</vPIS></PISOutr></PIS>' +
    '<COFINS><COFINSOutr><CST>49</CST><vBC>0.00</vBC><pCOFINS>0.00</pCOFINS><vCOFINS>0.00</vCOFINS></COFINSOutr></COFINS>' +
    '</imposto></det>';
}

function nota(comp, n, itens) {
  var ch = chave(comp, n);
  return '<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">' +
    '<NFe><infNFe Id="NFe' + ch + '" versao="4.00"><ide><cUF>35</cUF><mod>65</mod><serie>1</serie><nNF>' + n +
    '</nNF><dhEmi>' + comp + '-15T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide>' +
    '<emit><CNPJ>' + CNPJ + '</CNPJ><xNome>FARMACIA EXEMPLO LTDA</xNome><CRT>1</CRT></emit>' +
    itens.join('') + '</infNFe></NFe></nfeProc>';
}

fs.mkdirSync(DESTINO, { recursive: true });
fs.readdirSync(DESTINO).forEach(function (f) { fs.unlinkSync(path.join(DESTINO, f)); });

var n = 0;
competencias().forEach(function (comp, idx) {
  var fator = 1 + idx * 0.03; // faturamento crescente
  for (var k = 0; k < 3; k++) {
    n++;
    var itens = PRODUTOS.map(function (p, i) {
      return det(i + 1, p, Math.round((40 + 13 * ((i + k) % 5)) * fator));
    });
    fs.writeFileSync(path.join(DESTINO, 'NFCe-' + n + '.xml'), nota(comp, n, itens));
  }
});

// Um cancelamento para demonstrar a exclusão
fs.writeFileSync(path.join(DESTINO, 'cancelamento-NFCe-' + n + '.xml'),
  '<?xml version="1.0" encoding="UTF-8"?><procEventoNFe versao="1.00"><evento><infEvento Id="ID110111' +
  chave(competencias().slice(-1)[0], n) + '01"><chNFe>' + chave(competencias().slice(-1)[0], n) +
  '</chNFe><tpEvento>110111</tpEvento></infEvento></evento></procEventoNFe>');

console.log(n + ' NFC-e + 1 cancelamento gerados em ' + DESTINO);
