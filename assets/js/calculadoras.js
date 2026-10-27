/* =========================================================
   Regras das calculadoras — funções puras, sem DOM.
   Expostas em window.MOCalc (e module.exports para testes).
   ========================================================= */
(function (root) {
  'use strict';

  var FATOR_R_LIMITE = 0.28; // LC 123/2006, art. 18, § 5º-J

  /** Converte "1.234,56", "1234.56" ou "R$ 1.234" em número. Retorna NaN se inválido. */
  function parseBRL(valor) {
    if (typeof valor === 'number') return valor;
    if (valor == null) return NaN;
    var s = String(valor).replace(/[R$\s]/g, '').trim();
    if (s === '') return NaN;
    if (s.indexOf(',') !== -1) {
      s = s.replace(/\./g, '').replace(',', '.');
    } else if (/^\d{1,3}(\.\d{3})+$/.test(s)) {
      s = s.replace(/\./g, ''); // "84.000" = oitenta e quatro mil
    }
    if (!/^-?\d+(\.\d+)?$/.test(s)) return NaN;
    return parseFloat(s);
  }

  var fmtBRL = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  var fmtPct = new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 2 });

  function brl(n) { return fmtBRL.format(n); }
  function pct(n) { return fmtPct.format(n); }

  function erro(msg) { return { ok: false, erro: msg }; }

  function fatorR(folha, receita) {
    if (!isFinite(folha) || !isFinite(receita)) return erro('Preencha os dois campos com valores numéricos.');
    if (folha < 0 || receita < 0) return erro('Os valores não podem ser negativos.');
    if (receita === 0) return erro('Com receita bruta zero não é possível calcular o Fator R. Para empresas em início de atividade há regras próprias de proporcionalização — fale com um contador.');
    var fr = folha / receita;
    // compara em base inteira para evitar erro de ponto flutuante no limite exato de 28%
    var atinge = Math.round(folha * 100) * 100 >= Math.round(receita * 100) * Math.round(FATOR_R_LIMITE * 100);
    return { ok: true, fator: fr, anexo: atinge ? 'III' : 'V', limite: FATOR_R_LIMITE,
      folhaNecessaria: Math.round(receita * FATOR_R_LIMITE * 100) / 100 };
  }

  function margem(receita, custos) {
    if (!isFinite(receita) || !isFinite(custos)) return erro('Preencha os dois campos com valores numéricos.');
    if (receita < 0 || custos < 0) return erro('Os valores não podem ser negativos.');
    if (receita === 0) return erro('Sem receita no período não há margem a calcular.');
    var lucro = receita - custos;
    return { ok: true, lucro: lucro, margem: lucro / receita, markup: custos > 0 ? lucro / custos : null, prejuizo: lucro < 0 };
  }

  function pontoEquilibrio(fixos, receita, variaveis) {
    if (![fixos, receita, variaveis].every(isFinite)) return erro('Preencha os três campos com valores numéricos.');
    if (fixos < 0 || receita < 0 || variaveis < 0) return erro('Os valores não podem ser negativos.');
    if (receita === 0) return erro('Informe a receita do período para calcular a margem de contribuição.');
    var imc = (receita - variaveis) / receita;
    if (imc <= 0) return erro('O índice de margem de contribuição é zero ou negativo: os custos variáveis consomem toda a receita. Nessas condições o ponto de equilíbrio não pode ser obtido — é preciso rever preços ou custos variáveis.');
    var pe = fixos / imc;
    return { ok: true, imc: imc, receitaEquilibrio: pe, folga: receita - pe, atingido: receita >= pe };
  }

  function capitalGiro(estoques, receber, pagar) {
    if (![estoques, receber, pagar].every(isFinite)) return erro('Preencha os três campos com valores numéricos.');
    if (estoques < 0 || receber < 0 || pagar < 0) return erro('Os valores não podem ser negativos.');
    var ncg = estoques + receber - pagar;
    return { ok: true, ncg: ncg };
  }

  var api = { parseBRL: parseBRL, brl: brl, pct: pct, fatorR: fatorR, margem: margem, pontoEquilibrio: pontoEquilibrio, capitalGiro: capitalGiro };
  root.MOCalc = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
