/*
 * Plano de categorias do DRE gerencial (regime de caixa) e regras automáticas de classificação.
 * Regras do usuário (termo → categoria) têm prioridade sobre as regras padrão.
 */
(function (global) {
  'use strict';

  // grupo: posição no DRE gerencial
  var CATEGORIAS = [
    { id: 'receita',        nome: 'Receita de vendas e serviços',   grupo: 'RECEITA' },
    { id: 'outras_rec',     nome: 'Outras receitas',                grupo: 'RECEITA' },
    { id: 'impostos',       nome: 'Impostos sobre o faturamento',   grupo: 'DEDUCOES' },
    { id: 'fornecedores',   nome: 'Fornecedores e mercadorias',     grupo: 'CUSTOS' },
    { id: 'pessoal',        nome: 'Salários e encargos',            grupo: 'DESPESAS' },
    { id: 'ocupacao',       nome: 'Aluguel e condomínio',           grupo: 'DESPESAS' },
    { id: 'utilidades',     nome: 'Energia, água e telecom',        grupo: 'DESPESAS' },
    { id: 'terceiros',      nome: 'Serviços de terceiros e sistemas', grupo: 'DESPESAS' },
    { id: 'administrativas', nome: 'Outras despesas administrativas', grupo: 'DESPESAS' },
    { id: 'financeiras',    nome: 'Tarifas bancárias e juros',      grupo: 'DESPESAS' },
    { id: 'retiradas',      nome: 'Pró-labore e retiradas dos sócios', grupo: 'NAO_OPERACIONAL' },
    { id: 'emprestimos',    nome: 'Empréstimos e financiamentos',   grupo: 'NAO_OPERACIONAL' },
    { id: 'investimentos',  nome: 'Aplicações e investimentos',     grupo: 'NAO_OPERACIONAL' },
    { id: 'transferencias', nome: 'Transferências entre contas',    grupo: 'NEUTRO' },
    { id: 'a_classificar',  nome: 'A classificar',                  grupo: 'PENDENTE' }
  ];

  var POR_ID = {};
  CATEGORIAS.forEach(function (c) { POR_ID[c.id] = c; });

  // [expressão, categoria, sinal opcional: 'C' só créditos, 'D' só débitos]
  var REGRAS_PADRAO = [
    [/TRANSF.*(MESMA TITULAR|ENTRE CONTAS|MESMO TITULAR)/, 'transferencias'],
    [/APLICACAO|RESGATE|CDB|POUPANCA|INVEST|FUNDO/, 'investimentos'],
    [/EMPRESTIMO|FINANCIAMENTO|CAPITAL DE GIRO|PARC.*CRED|PRONAMPE|CONSORCIO/, 'emprestimos'],
    [/PRO.?LABORE|RETIRADA|DISTRIB.*LUCRO|LUCROS/, 'retiradas', 'D'],
    [/\bDAS\b|SIMPLES NAC|\bDARF\b|\bICMS\b|\bISS\b|GNRE|\bDAM\b/, 'impostos', 'D'],
    [/SALARIO|FOLHA|FGTS|\bGPS\b|\bDAE\b|ESOCIAL|FERIAS|RESCIS|VALE TRANSP|VALE REF|VALE ALIM|BENEFICIO/, 'pessoal', 'D'],
    [/ALUGUEL|CONDOMINIO|IPTU|LOCACAO/, 'ocupacao', 'D'],
    [/ENERGIA|ELETRIC|CEMIG|ENEL|COPEL|CPFL|LIGHT|COELBA|CELPE|EQUATORIAL|SABESP|COPASA|SANEAG|CEDAE|AGUA|SANEAMENTO|VIVO|CLARO|\bTIM\b|\bOI\b|INTERNET|TELEFON|TELECOM/, 'utilidades', 'D'],
    [/TARIFA|\bTAR\b|JUROS|\bIOF\b|ENCARGO|PACOTE DE SERV|ANUIDADE|CESTA|MANUT.*CONTA/, 'financeiras', 'D'],
    [/CONTAB|HONORARIO|ADVOCACIA|ADVOGAD|SISTEMA|SOFTWARE|ASSINATURA|MENSALIDADE|MARKETING|PUBLICIDADE/, 'terceiros', 'D'],
    [/FORNEC|DISTRIB|ATACAD|INDUSTRIA|\bIND\b|COMERCIO DE|MERCADORIA/, 'fornecedores', 'D'],
    [/CIELO|STONE|\bREDE\b|GETNET|PAGSEGURO|PAGBANK|MERCADO ?PAGO|SUMUP|SAFRAPAY|VENDAS? CART|ANTECIP/, 'receita', 'C'],
    [/PIX RECEB|TED RECEB|DOC RECEB|CRED.*PIX|DEPOSITO|BOLETO RECEB|LIQUIDACAO|COBRANCA/, 'receita', 'C'],
    [/ESTORNO|DEVOLUCAO|REEMBOLSO|RENDIMENTO/, 'outras_rec', 'C']
  ];

  function normalizar(s) {
    return String(s || '').toUpperCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
      .replace(/\s+/g, ' ').trim();
  }

  /* regrasUsuario: [{ termo: 'PADARIA X', categoria: 'fornecedores' }] */
  function classificar(lancamento, regrasUsuario) {
    var h = normalizar(lancamento.historico);
    var sinal = lancamento.valor >= 0 ? 'C' : 'D';
    var lista = regrasUsuario || [];
    for (var i = 0; i < lista.length; i++) {
      var termo = normalizar(lista[i].termo);
      if (termo && h.indexOf(termo) >= 0 && POR_ID[lista[i].categoria]) return lista[i].categoria;
    }
    for (var j = 0; j < REGRAS_PADRAO.length; j++) {
      var r = REGRAS_PADRAO[j];
      if ((!r[2] || r[2] === sinal) && r[0].test(h)) return r[1];
    }
    return 'a_classificar';
  }

  var api = {
    CATEGORIAS: CATEGORIAS,
    porId: function (id) { return POR_ID[id]; },
    classificar: classificar,
    normalizar: normalizar
  };

  var NS = global.PainelFinanceiro = global.PainelFinanceiro || {};
  NS.categorias = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
