/*
 * Leitura de extratos bancários: OFX (1.x SGML e 2.x XML) e CSV (data; histórico; valor).
 * Implementado sem DOMParser para funcionar igualmente no navegador e no Node.
 */
(function (global) {
  'use strict';

  // Valor de uma tag OFX: aceita <TAG>valor</TAG> e o formato SGML sem fechamento.
  function tag(bloco, nome) {
    var m = new RegExp('<' + nome + '>([^<\\r\\n]*)', 'i').exec(bloco);
    return m ? m[1].trim() : '';
  }

  function dataOfx(s) {
    var d = String(s).replace(/\D/g, '').slice(0, 8);
    return d.length === 8 ? d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6, 8) : '';
  }

  function numero(s) {
    s = String(s || '').trim().replace(/[R$\s]/g, '');
    if (!s) return NaN;
    var neg = /^\(.*\)$/.test(s) || /-$/.test(s) || /D$/i.test(s); // (100,00) 100,00- 100,00D
    s = s.replace(/[()]/g, '').replace(/[-+]$/, '').replace(/[DC]$/i, '');
    // Formato brasileiro (1.234,56) ou internacional (1234.56)
    if (s.indexOf(',') >= 0) s = s.replace(/\./g, '').replace(',', '.');
    var v = parseFloat(s);
    return neg ? -Math.abs(v) : v;
  }

  function lerOfx(texto, origem) {
    var conta = tag(texto, 'ACCTID') || origem || 'conta';
    var banco = tag(texto, 'BANKID') || tag(texto, 'ORG');
    var saldoBloco = /<LEDGERBAL>([\s\S]*?)(<\/LEDGERBAL>|<AVAILBAL>|<\/STMTRS>)/i.exec(texto);
    var lancamentos = [];
    var partes = texto.split(/<STMTTRN>/i).slice(1);
    partes.forEach(function (p) {
      p = p.split(/<\/STMTTRN>/i)[0];
      var valor = numero(tag(p, 'TRNAMT'));
      if (isNaN(valor)) return;
      lancamentos.push({
        conta: conta,
        id: tag(p, 'FITID'),
        data: dataOfx(tag(p, 'DTPOSTED')),
        historico: tag(p, 'MEMO') || tag(p, 'NAME') || tag(p, 'TRNTYPE'),
        valor: Math.round(valor * 100) / 100
      });
    });
    return {
      formato: 'ofx',
      conta: conta,
      banco: banco,
      saldoFinal: saldoBloco ? numero(tag(saldoBloco[1], 'BALAMT')) : null,
      dataSaldo: saldoBloco ? dataOfx(tag(saldoBloco[1], 'DTASOF')) : null,
      lancamentos: lancamentos
    };
  }

  function dataCsv(s) {
    s = String(s || '').trim();
    var m = /^(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})/.exec(s);
    if (m) {
      var ano = m[3].length === 2 ? '20' + m[3] : m[3];
      return ano + '-' + ('0' + m[2]).slice(-2) + '-' + ('0' + m[1]).slice(-2);
    }
    m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
    return m ? m[0] : '';
  }

  function dividir(linha, sep) {
    var out = [], atual = '', aspas = false;
    for (var i = 0; i < linha.length; i++) {
      var c = linha[i];
      if (c === '"') aspas = !aspas;
      else if (c === sep && !aspas) { out.push(atual); atual = ''; }
      else atual += c;
    }
    out.push(atual);
    return out.map(function (s) { return s.trim(); });
  }

  function lerCsv(texto, origem) {
    var linhas = texto.replace(/^﻿/, '').split(/\r?\n/).filter(function (l) { return l.trim(); });
    if (!linhas.length) return { formato: 'csv', conta: origem, lancamentos: [] };
    var sep = (linhas[0].match(/;/g) || []).length >= (linhas[0].match(/,/g) || []).length ? ';' : ',';
    var cab = dividir(linhas[0], sep).map(function (c) {
      return c.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    });
    function col(re) { for (var i = 0; i < cab.length; i++) if (re.test(cab[i])) return i; return -1; }
    var iData = col(/^data|^dt/), iHist = col(/hist|descr|memo|lancamento/), iValor = col(/^valor|^vlr|^montante/);
    var iCred = col(/credito|entrada/), iDeb = col(/debito|saida/);
    var temCabecalho = iData >= 0;
    if (!temCabecalho) { iData = 0; iHist = 1; iValor = 2; }

    var lancamentos = [];
    linhas.slice(temCabecalho ? 1 : 0).forEach(function (l, n) {
      var c = dividir(l, sep);
      var data = dataCsv(c[iData]);
      if (!data) return;
      var valor = iValor >= 0 ? numero(c[iValor])
        : (numero(c[iCred]) || 0) - Math.abs(numero(c[iDeb]) || 0);
      if (isNaN(valor) || valor === 0) return;
      var historico = iHist >= 0 ? c[iHist] : '';
      if (/saldo/i.test(historico)) return;
      lancamentos.push({
        conta: origem || 'csv', id: data + '|' + n + '|' + valor,
        data: data, historico: historico, valor: Math.round(valor * 100) / 100
      });
    });
    return { formato: 'csv', conta: origem || 'csv', saldoFinal: null, lancamentos: lancamentos };
  }

  function lerExtrato(texto, nomeArquivo) {
    texto = String(texto || '');
    if (/<OFX>|OFXHEADER|<STMTTRN>/i.test(texto)) return lerOfx(texto, nomeArquivo);
    return lerCsv(texto, nomeArquivo);
  }

  var api = { lerExtrato: lerExtrato, lerOfx: lerOfx, lerCsv: lerCsv, numero: numero };

  var NS = global.PainelFinanceiro = global.PainelFinanceiro || {};
  NS.extrato = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
