/*
 * Consolidação mensal: fluxo de caixa, DRE gerencial (regime de caixa), indicadores e alertas.
 * Valores com sinal: entradas positivas, saídas negativas.
 */
(function (global) {
  'use strict';

  var NS = global.PainelFinanceiro = global.PainelFinanceiro || {};
  var emNode = typeof module !== 'undefined' && module.exports;
  var cat = emNode ? require('./categorias.js') : NS.categorias;

  function arred(v) { return Math.round(v * 100) / 100; }

  /*
   * Junta os lançamentos de vários extratos, remove duplicidades (mesma conta + FITID)
   * e aplica a classificação: ajuste manual > regra do usuário > regra padrão.
   */
  function consolidarLancamentos(extratos, regrasUsuario, ajustes) {
    var vistos = {}, lista = [], duplicados = 0;
    ajustes = ajustes || {};
    extratos.forEach(function (e) {
      e.lancamentos.forEach(function (l) {
        var chave = l.conta + '|' + l.id;
        if (vistos[chave]) { duplicados++; return; }
        vistos[chave] = true;
        var c = ajustes[chave] || cat.classificar(l, regrasUsuario);
        lista.push({
          chave: chave, conta: l.conta, data: l.data, historico: l.historico,
          valor: l.valor, categoria: c, competencia: l.data.slice(0, 7)
        });
      });
    });
    lista.sort(function (a, b) { return a.data < b.data ? -1 : a.data > b.data ? 1 : 0; });
    return { lancamentos: lista, duplicados: duplicados };
  }

  function linhaVazia(comp) {
    var l = { competencia: comp, porCategoria: {}, entradas: 0, saidas: 0 };
    cat.CATEGORIAS.forEach(function (c) { l.porCategoria[c.id] = 0; });
    return l;
  }

  function fecharLinha(l) {
    var g = function (grupo) {
      return cat.CATEGORIAS.filter(function (c) { return c.grupo === grupo; })
        .reduce(function (s, c) { return s + l.porCategoria[c.id]; }, 0);
    };
    l.receitaBruta = arred(g('RECEITA'));
    l.deducoes = arred(g('DEDUCOES'));
    l.receitaLiquida = arred(l.receitaBruta + l.deducoes);
    l.custos = arred(g('CUSTOS'));
    l.lucroBruto = arred(l.receitaLiquida + l.custos);
    l.despesas = arred(g('DESPESAS'));
    l.resultadoOperacional = arred(l.lucroBruto + l.despesas);
    l.naoOperacional = arred(g('NAO_OPERACIONAL'));
    l.pendente = arred(g('PENDENTE'));
    l.geracaoCaixa = arred(l.resultadoOperacional + l.naoOperacional + l.pendente);
    l.margemOperacional = l.receitaBruta > 0 ? l.resultadoOperacional / l.receitaBruta : null;
    l.entradas = arred(l.entradas);
    l.saidas = arred(l.saidas);
    Object.keys(l.porCategoria).forEach(function (k) { l.porCategoria[k] = arred(l.porCategoria[k]); });
    return l;
  }

  function moeda(v) {
    return 'R$ ' + Math.abs(v).toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  }

  function gerar(extratos, opcoes) {
    opcoes = opcoes || {};
    var base = consolidarLancamentos(extratos, opcoes.regrasUsuario, opcoes.ajustes);
    var meses = {}, total = linhaVazia('total'), contas = {};

    base.lancamentos.forEach(function (l) {
      var m = meses[l.competencia] || (meses[l.competencia] = linhaVazia(l.competencia));
      var neutro = cat.porId(l.categoria).grupo === 'NEUTRO';
      [m, total].forEach(function (alvo) {
        alvo.porCategoria[l.categoria] += l.valor;
        if (!neutro) { if (l.valor >= 0) alvo.entradas += l.valor; else alvo.saidas += l.valor; }
      });
      var c = contas[l.conta] || (contas[l.conta] = { conta: l.conta, entradas: 0, saidas: 0, saldoFinal: null });
      if (l.valor >= 0) c.entradas += l.valor; else c.saidas += l.valor;
    });

    extratos.forEach(function (e) {
      if (contas[e.conta] && e.saldoFinal != null && !isNaN(e.saldoFinal)) contas[e.conta].saldoFinal = e.saldoFinal;
    });

    var linhas = Object.keys(meses).sort().map(function (k) { return fecharLinha(meses[k]); });
    fecharLinha(total);

    // Indicadores médios
    var n = linhas.length || 1;
    var margemContribuicao = total.receitaBruta > 0 ? (total.receitaLiquida + total.custos) / total.receitaBruta : null;
    var despesasFixasMes = -total.despesas / n;
    var indicadores = {
      meses: linhas.length,
      receitaMedia: arred(total.receitaBruta / n),
      margemContribuicao: margemContribuicao,
      margemOperacional: total.margemOperacional,
      pesoPessoal: total.receitaBruta > 0 ? -total.porCategoria.pessoal / total.receitaBruta : null,
      pesoFinanceiro: total.receitaBruta > 0 ? -total.porCategoria.financeiras / total.receitaBruta : null,
      pontoEquilibrio: margemContribuicao > 0 ? arred(despesasFixasMes / margemContribuicao) : null
    };

    // Alertas: são a pauta da reunião mensal com o cliente
    var alertas = [];
    var pendentes = base.lancamentos.filter(function (l) { return l.categoria === 'a_classificar'; });
    if (pendentes.length) {
      alertas.push({ nivel: 'info', texto: pendentes.length + ' lançamento(s) a classificar, somando ' +
        moeda(pendentes.reduce(function (s, l) { return s + Math.abs(l.valor); }, 0)) + '.' });
    }
    if (base.duplicados) alertas.push({ nivel: 'info', texto: base.duplicados + ' lançamento(s) duplicado(s) ignorado(s).' });
    linhas.forEach(function (l) {
      var mes = l.competencia.slice(5, 7) + '/' + l.competencia.slice(0, 4);
      if (l.resultadoOperacional < 0) {
        alertas.push({ nivel: 'alto', texto: mes + ': resultado operacional negativo (' + moeda(l.resultadoOperacional) + ').' });
      }
      var ret = -l.porCategoria.retiradas;
      if (ret > 0 && ret > Math.max(l.resultadoOperacional, 0)) {
        alertas.push({ nivel: 'alto', texto: mes + ': retiradas dos sócios (' + moeda(ret) +
          ') maiores que o resultado operacional (' + moeda(Math.max(l.resultadoOperacional, 0)) + ').' });
      }
    });
    if (indicadores.pesoFinanceiro > 0.02) {
      alertas.push({ nivel: 'medio', texto: 'Tarifas e juros consomem ' + (indicadores.pesoFinanceiro * 100).toFixed(1).replace('.', ',') +
        '% da receita: vale renegociar o pacote bancário, as taxas de cartão e as linhas de crédito.' });
    }
    if (indicadores.pesoPessoal > 0.35) {
      alertas.push({ nivel: 'medio', texto: 'A folha representa ' + (indicadores.pesoPessoal * 100).toFixed(1).replace('.', ',') +
        '% da receita.' });
    }

    return {
      lancamentos: base.lancamentos,
      meses: linhas,
      total: total,
      contas: Object.keys(contas).map(function (k) {
        var c = contas[k];
        return { conta: c.conta, entradas: arred(c.entradas), saidas: arred(c.saidas), saldoFinal: c.saldoFinal };
      }),
      indicadores: indicadores,
      alertas: alertas
    };
  }

  var api = { gerar: gerar, consolidarLancamentos: consolidarLancamentos };
  NS.relatorio = api;
  if (emNode) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
