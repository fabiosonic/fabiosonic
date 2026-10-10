/*
 * Tabela de referência de NCMs sujeitos à tributação concentrada (monofásica)
 * de PIS/COFINS. Para o revendedor optante pelo Simples Nacional, a receita
 * dessas mercadorias deve ser segregada no PGDAS-D, zerando PIS e COFINS
 * (LC 123/2006, art. 18, §4º-A, I; Resolução CGSN 140/2018, art. 25, §8º).
 *
 * ATENÇÃO: lista de triagem, não exaustiva. Antes de protocolar qualquer pedido,
 * confirme NCM e eventuais "Ex" da TIPI na legislação vigente na competência
 * (alterações de NCM de 2017 e 2022 mudaram códigos de alguns produtos).
 */
(function (global) {
  'use strict';

  var GRUPOS = {
    FARMA: {
      nome: 'Produtos farmacêuticos',
      base: 'Lei 10.147/2000, art. 1º, I, "a"'
    },
    HIGIENE: {
      nome: 'Perfumaria, toucador e higiene pessoal',
      base: 'Lei 10.147/2000, art. 1º, I, "b"'
    },
    AUTOPECAS: {
      nome: 'Autopeças',
      base: 'Lei 10.485/2002, art. 3º e Anexos I e II'
    },
    PNEUS: {
      nome: 'Pneus e câmaras de ar',
      base: 'Lei 10.485/2002, art. 5º'
    },
    VEICULOS: {
      nome: 'Máquinas e veículos',
      base: 'Lei 10.485/2002, art. 1º'
    },
    BEBIDAS: {
      nome: 'Bebidas frias (água, refrigerante, cerveja)',
      base: 'Lei 13.097/2015, arts. 14 a 36'
    },
    COMBUSTIVEIS: {
      nome: 'Combustíveis',
      base: 'Lei 9.718/1998, arts. 4º a 6º; Lei 10.865/2004'
    }
  };

  // Prefixos de NCM (somente dígitos). Vence o prefixo mais longo.
  var PREFIXOS = {
    // Farmacêuticos
    '3001': 'FARMA', '3003': 'FARMA', '3004': 'FARMA',
    '300210': 'FARMA', '300212': 'FARMA', '300213': 'FARMA', '300214': 'FARMA', '300215': 'FARMA',
    '300220': 'FARMA', '30029020': 'FARMA', '30029092': 'FARMA', '30029099': 'FARMA',
    '30051010': 'FARMA', '300630': 'FARMA', '30066000': 'FARMA',
    // Higiene pessoal e perfumaria
    '3303': 'HIGIENE', '3304': 'HIGIENE', '3305': 'HIGIENE', '3306': 'HIGIENE', '3307': 'HIGIENE',
    '34011190': 'HIGIENE', '34012010': 'HIGIENE', '96032100': 'HIGIENE',
    // Pneus
    '4011': 'PNEUS', '4013': 'PNEUS',
    // Autopeças (principais posições)
    '40161010': 'AUTOPECAS', '40169990': 'AUTOPECAS', '6813': 'AUTOPECAS',
    '70071100': 'AUTOPECAS', '70072100': 'AUTOPECAS', '70091000': 'AUTOPECAS', '7320': 'AUTOPECAS',
    '83012000': 'AUTOPECAS', '83017000': 'AUTOPECAS',
    '84073': 'AUTOPECAS', '840820': 'AUTOPECAS', '84099': 'AUTOPECAS', '841330': 'AUTOPECAS',
    '84152': 'AUTOPECAS', '84212300': 'AUTOPECAS', '84213100': 'AUTOPECAS',
    '848310': 'AUTOPECAS', '848320': 'AUTOPECAS', '848330': 'AUTOPECAS', '848340': 'AUTOPECAS',
    '848350': 'AUTOPECAS', '85071000': 'AUTOPECAS', '8511': 'AUTOPECAS',
    '851220': 'AUTOPECAS', '851230': 'AUTOPECAS', '851240': 'AUTOPECAS', '851290': 'AUTOPECAS',
    '852721': 'AUTOPECAS', '853910': 'AUTOPECAS', '85443000': 'AUTOPECAS',
    '8707': 'AUTOPECAS', '8708': 'AUTOPECAS', '9029': 'AUTOPECAS', '91040000': 'AUTOPECAS',
    // Veículos
    '8701': 'VEICULOS', '8702': 'VEICULOS', '8703': 'VEICULOS', '8704': 'VEICULOS',
    '8705': 'VEICULOS', '8706': 'VEICULOS', '8711': 'VEICULOS',
    // Bebidas frias
    '2201': 'BEBIDAS', '2202': 'BEBIDAS', '2203': 'BEBIDAS', '21069010': 'BEBIDAS',
    // Combustíveis
    '271012': 'COMBUSTIVEIS', '271019': 'COMBUSTIVEIS', '271020': 'COMBUSTIVEIS',
    '27111': 'COMBUSTIVEIS', '220710': 'COMBUSTIVEIS', '2207201': 'COMBUSTIVEIS',
    '38260000': 'COMBUSTIVEIS'
  };

  // Exceções expressas (NCM completo, 8 dígitos).
  var EXCECOES = {
    '30039056': 'Excluído pela Lei 10.147/2000',
    '30049046': 'Excluído pela Lei 10.147/2000'
  };

  function normalizar(ncm) {
    return String(ncm || '').replace(/\D/g, '');
  }

  function classificar(ncm) {
    var n = normalizar(ncm);
    if (n.length < 4 || EXCECOES[n]) return null;
    for (var len = Math.min(n.length, 8); len >= 4; len--) {
      var grupo = PREFIXOS[n.slice(0, len)];
      if (grupo) {
        return { grupo: grupo, nome: GRUPOS[grupo].nome, base: GRUPOS[grupo].base };
      }
    }
    return null;
  }

  var api = { GRUPOS: GRUPOS, classificar: classificar, normalizar: normalizar };

  var NS = global.RadarTributario = global.RadarTributario || {};
  NS.ncm = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
