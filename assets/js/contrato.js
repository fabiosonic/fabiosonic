/* =========================================================
   Contrato — funções puras (sem DOM): validação de CPF/CNPJ,
   preenchimento do modelo e texto canônico para o código de
   integridade (SHA-256). Expostas em window.MOContratoUtil
   e em module.exports para testes.
   ========================================================= */
(function (root) {
  'use strict';

  function soDigitos(v) { return String(v || '').replace(/\D/g, ''); }

  function validaCPF(v) {
    var c = soDigitos(v);
    if (c.length !== 11 || /^(\d)\1{10}$/.test(c)) return false;
    for (var t = 9; t < 11; t++) {
      var s = 0;
      for (var i = 0; i < t; i++) s += parseInt(c[i], 10) * (t + 1 - i);
      var d = (s * 10) % 11 % 10;
      if (d !== parseInt(c[t], 10)) return false;
    }
    return true;
  }

  /** Normaliza CNPJ: maiúsculas, sem pontuação. Aceita o formato alfanumérico
   *  (IN RFB nº 2.229/2024): 12 posições [0-9A-Z] + 2 dígitos verificadores. */
  function normalizaCNPJ(v) { return String(v || '').toUpperCase().replace(/[^0-9A-Z]/g, ''); }

  function validaCNPJ(v) {
    var c = normalizaCNPJ(v);
    if (!/^[0-9A-Z]{12}\d{2}$/.test(c) || /^(\d)\1{13}$/.test(c)) return false;
    var val = function (ch) { return ch.charCodeAt(0) - 48; }; // ASCII − 48 (A = 17)
    var pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    for (var t = 12; t < 14; t++) {
      var s = 0;
      for (var i = 0; i < t; i++) s += val(c[i]) * pesos[i + (13 - t)];
      var r = s % 11;
      var d = r < 2 ? 0 : 11 - r;
      if (d !== parseInt(c[t], 10)) return false;
    }
    return true;
  }

  function formataCPF(v) { var c = soDigitos(v); return c.length === 11 ? c.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4') : v; }
  function formataCNPJ(v) { var c = normalizaCNPJ(v); return c.length === 14 ? c.replace(/(.{2})(.{3})(.{3})(.{4})(\d{2})/, '$1.$2.$3/$4-$5') : v; }

  /** Substitui {{CHAVE}} pelos dados; chaves ausentes ficam como "[a preencher]". */
  function preenche(texto, dados) {
    return String(texto).replace(/\{\{([A-Z_]+)\}\}/g, function (_, k) {
      var v = dados && dados[k];
      return v != null && String(v).trim() !== '' ? String(v).trim() : '[a preencher]';
    });
  }

  /** Devolve o contrato preenchido como estrutura (mesma forma do modelo). */
  function montaContrato(modelo, dados) {
    var f = function (t) { return preenche(t, dados); };
    return {
      versao: modelo.versao,
      dataVersao: modelo.dataVersao,
      destaques: (modelo.destaques || []).slice(),
      titulo: f(modelo.titulo),
      preambulo: (modelo.preambulo || []).map(f),
      clausulas: (modelo.clausulas || []).map(function (c) {
        return { numero: c.numero, titulo: f(c.titulo), itens: (c.itens || []).map(f) };
      }),
      anexos: (modelo.anexos || []).map(function (a) {
        return { titulo: f(a.titulo), itens: (a.itens || []).map(f) };
      }),
      fechamento: (modelo.fechamento || []).map(f)
    };
  }

  /** Texto canônico (UTF-8, \n) usado no hash de integridade. */
  function textoCanonico(c) {
    var out = [c.titulo, 'Versão ' + c.versao + ' de ' + c.dataVersao, ''];
    c.preambulo.forEach(function (p) { out.push(p); });
    c.clausulas.forEach(function (cl) {
      out.push('', 'CLÁUSULA ' + cl.numero + ' — ' + cl.titulo);
      cl.itens.forEach(function (i) { out.push(i); });
    });
    c.anexos.forEach(function (a) {
      out.push('', a.titulo);
      a.itens.forEach(function (i) { out.push(i); });
    });
    out.push('');
    c.fechamento.forEach(function (p) { out.push(p); });
    return out.join('\n').replace(/[ \t]+\n/g, '\n').trim();
  }

  /** SHA-256 em hexadecimal (Web Crypto; disponível no navegador e no Node 18+). */
  function sha256(texto) {
    var bytes = new TextEncoder().encode(texto);
    return root.crypto.subtle.digest('SHA-256', bytes).then(function (buf) {
      return Array.prototype.map.call(new Uint8Array(buf), function (b) { return ('0' + b.toString(16)).slice(-2); }).join('');
    });
  }

  var api = { soDigitos: soDigitos, normalizaCNPJ: normalizaCNPJ, validaCPF: validaCPF, validaCNPJ: validaCNPJ, formataCPF: formataCPF, formataCNPJ: formataCNPJ,
    preenche: preenche, montaContrato: montaContrato, textoCanonico: textoCanonico, sha256: sha256 };
  root.MOContratoUtil = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
