/*
 * Leitor de XML de NF-e (modelo 55) e NFC-e (modelo 65), layout 3.10/4.00.
 * Também reconhece eventos de cancelamento (tpEvento 110111).
 * Implementado sem DOMParser para funcionar igualmente no navegador e no Node.
 */
(function (global) {
  'use strict';

  function bloco(xml, tag) {
    var re = new RegExp('<' + tag + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + tag + '>');
    var m = re.exec(xml);
    return m ? m[1] : '';
  }

  function blocos(xml, tag) {
    var re = new RegExp('<' + tag + '(?:\\s[^>]*)?>([\\s\\S]*?)</' + tag + '>', 'g');
    var out = [], m;
    while ((m = re.exec(xml))) out.push(m[1]);
    return out;
  }

  function texto(xml, tag) {
    return decodificar(bloco(xml, tag).trim());
  }

  function numero(xml, tag) {
    var v = parseFloat(texto(xml, tag));
    return isNaN(v) ? 0 : v;
  }

  function decodificar(s) {
    return s.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
      .replace(/&apos;/g, "'").replace(/&amp;/g, '&');
  }

  function lerItem(det) {
    var prod = bloco(det, 'prod');
    var imposto = bloco(det, 'imposto');
    var icms = bloco(imposto, 'ICMS');
    var pis = bloco(imposto, 'PIS');
    var vProd = numero(prod, 'vProd');
    var vDesc = numero(prod, 'vDesc');
    return {
      codigo: texto(prod, 'cProd'),
      descricao: texto(prod, 'xProd'),
      ncm: texto(prod, 'NCM'),
      cfop: texto(prod, 'CFOP'),
      cest: texto(prod, 'CEST'),
      valor: Math.round((vProd - vDesc) * 100) / 100,
      csosn: texto(icms, 'CSOSN'),
      cstIcms: texto(icms, 'CST'),
      cstPis: texto(pis, 'CST')
    };
  }

  /*
   * Retorna:
   *  { tipo: 'nfe', chave, modelo, numero, tpNF, dataEmissao, competencia,
   *    emitente: {cnpj, nome, crt}, itens: [...] }
   *  { tipo: 'cancelamento', chave }
   *  { tipo: 'desconhecido' }
   */
  function lerXml(xml) {
    xml = String(xml || '');

    var evento = bloco(xml, 'infEvento');
    if (evento) {
      if (texto(evento, 'tpEvento') === '110111') {
        return { tipo: 'cancelamento', chave: texto(evento, 'chNFe') };
      }
      return { tipo: 'desconhecido' };
    }

    var infMatch = /<infNFe[^>]*Id="NFe(\d{44})"[^>]*>([\s\S]*?)<\/infNFe>/.exec(xml);
    if (!infMatch) return { tipo: 'desconhecido' };
    var inf = infMatch[2];
    var ide = bloco(inf, 'ide');
    var emit = bloco(inf, 'emit');
    var data = texto(ide, 'dhEmi') || texto(ide, 'dEmi');

    return {
      tipo: 'nfe',
      chave: infMatch[1],
      modelo: texto(ide, 'mod'),
      numero: texto(ide, 'nNF'),
      tpNF: texto(ide, 'tpNF'),
      dataEmissao: data.slice(0, 10),
      competencia: data.slice(0, 7),
      emitente: {
        cnpj: texto(emit, 'CNPJ') || texto(emit, 'CPF'),
        nome: texto(emit, 'xNome'),
        crt: texto(emit, 'CRT')
      },
      itens: blocos(inf, 'det').map(lerItem)
    };
  }

  var api = { lerXml: lerXml };

  var NS = global.RadarTributario = global.RadarTributario || {};
  NS.nfe = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
