/*
 * Motor de apuração de créditos do Simples Nacional (Anexo I — comércio):
 *  1) PIS/COFINS sobre receitas de produtos monofásicos não segregadas no PGDAS-D;
 *  2) ICMS sobre receitas de mercadorias com ICMS-ST já retido (contribuinte substituído).
 * Valores nominais, sem atualização pela Selic (que aumenta o crédito).
 */
(function (global) {
  'use strict';

  var NS = global.RadarTributario = global.RadarTributario || {};
  var emNode = typeof module !== 'undefined' && module.exports;
  var simples = emNode ? require('./simples-nacional.js') : NS.simples;
  var ncm = emNode ? require('./ncm-monofasico.js') : NS.ncm;

  var PRAZO_PRESCRICIONAL_MESES = 60; // CTN, art. 168, I

  // Sufixos de CFOP que representam venda/receita de mercadorias.
  var CFOP_VENDA = {
    '101': 1, '102': 1, '103': 1, '104': 1, '105': 1, '106': 1, '109': 1, '110': 1,
    '115': 1, '117': 1, '118': 1, '119': 1, '120': 1, '122': 1, '123': 1,
    '401': 1, '402': 1, '403': 1, '405': 1,
    '651': 1, '652': 1, '653': 1, '654': 1, '655': 1, '656': 1, '667': 1
  };

  function ehVenda(cfop) {
    var c = String(cfop || '');
    return c.length === 4 && '567'.indexOf(c[0]) >= 0 && !!CFOP_VENDA[c.slice(1)];
  }

  // Contribuinte substituído: ICMS já recolhido por ST na etapa anterior.
  function ehIcmsSt(item) {
    var suf = String(item.cfop || '').slice(1);
    return item.csosn === '500' || item.cstIcms === '60' || suf === '405' || suf === '656' || suf === '667';
  }

  function somarMeses(comp, n) {
    var ano = parseInt(comp.slice(0, 4), 10);
    var mes = parseInt(comp.slice(5, 7), 10) - 1 + n;
    ano += Math.floor(mes / 12);
    mes = ((mes % 12) + 12) % 12;
    return ano + '-' + (mes < 9 ? '0' : '') + (mes + 1);
  }

  function arred(v) { return Math.round(v * 100) / 100; }

  function listarEmitentes(documentos) {
    var mapa = {};
    documentos.forEach(function (d) {
      if (d.tipo !== 'nfe' || d.tpNF !== '1') return;
      var e = mapa[d.emitente.cnpj] || (mapa[d.emitente.cnpj] = {
        cnpj: d.emitente.cnpj, nome: d.emitente.nome, crt: d.emitente.crt, notas: 0
      });
      e.notas++;
    });
    return Object.keys(mapa).map(function (k) { return mapa[k]; })
      .sort(function (a, b) { return b.notas - a.notas; });
  }

  /*
   * opcoes:
   *  cnpj             — emitente a analisar (padrão: o que tiver mais notas)
   *  hoje             — 'AAAA-MM-DD' (padrão: data atual)
   *  rbt12Padrao      — RBT12 usado quando não há 12 meses anteriores nos XMLs
   *  rbt12PorMes      — { 'AAAA-MM': valor } sobrepõe o cálculo automático
   *  percentualHonorarios — ex.: 0.20
   */
  function analisar(documentos, opcoes) {
    opcoes = opcoes || {};
    var alertas = [];
    var emitentes = listarEmitentes(documentos);
    var cnpj = opcoes.cnpj || (emitentes[0] && emitentes[0].cnpj);
    var emitente = emitentes.filter(function (e) { return e.cnpj === cnpj; })[0] || null;

    if (emitentes.length > 1) {
      alertas.push('Foram encontrados ' + emitentes.length + ' emitentes. A análise considera apenas o CNPJ ' + cnpj + '.');
    }
    if (emitente && emitente.crt && emitente.crt !== '1' && emitente.crt !== '4') {
      alertas.push('CRT do emitente = ' + emitente.crt + ': a empresa pode não ser optante pelo Simples Nacional nesse período.');
    }

    var cancelados = {};
    documentos.forEach(function (d) { if (d.tipo === 'cancelamento') cancelados[d.chave] = true; });

    var hoje = opcoes.hoje || new Date().toISOString().slice(0, 10);
    var limite = somarMeses(hoje.slice(0, 7), -(PRAZO_PRESCRICIONAL_MESES - 1));

    var meses = {}, grupos = {}, produtos = {}, vistos = {};
    var notasConsideradas = 0, notasCanceladas = 0, notasDuplicadas = 0;

    function mes(comp) {
      return meses[comp] || (meses[comp] = {
        competencia: comp, receitaTotal: 0, receitaMonofasica: 0, receitaIcmsSt: 0, porGrupo: {}
      });
    }

    documentos.forEach(function (d) {
      if (d.tipo !== 'nfe' || d.tpNF !== '1' || d.emitente.cnpj !== cnpj) return;
      if (cancelados[d.chave]) { notasCanceladas++; return; }
      if (vistos[d.chave]) { notasDuplicadas++; return; }
      vistos[d.chave] = true;
      notasConsideradas++;

      var m = mes(d.competencia);
      var ativo = d.competencia >= limite; // grupos e produtos só de meses não prescritos
      d.itens.forEach(function (it) {
        if (!ehVenda(it.cfop)) return;
        m.receitaTotal += it.valor;

        var cls = ncm.classificar(it.ncm);
        if (cls) {
          m.receitaMonofasica += it.valor;
          m.porGrupo[cls.grupo] = (m.porGrupo[cls.grupo] || 0) + it.valor;
        }
        if (cls && ativo) {
          var g = grupos[cls.grupo] || (grupos[cls.grupo] = {
            grupo: cls.grupo, nome: cls.nome, base: cls.base, receita: 0, credito: 0
          });
          g.receita += it.valor;
          var chaveProd = it.ncm + '|' + it.descricao;
          var p = produtos[chaveProd] || (produtos[chaveProd] = {
            ncm: it.ncm, descricao: it.descricao, grupo: cls.nome, receita: 0
          });
          p.receita += it.valor;
        }
        if (ehIcmsSt(it)) m.receitaIcmsSt += it.valor;
      });
    });

    var competencias = Object.keys(meses).sort();
    var primeira = competencias[0];
    var rbt12PorMes = opcoes.rbt12PorMes || {};
    var mesesSemRbt12 = [];

    var linhas = competencias.map(function (comp) {
      var m = meses[comp];
      var rbt12 = null, fonte = null;

      if (rbt12PorMes[comp] > 0) {
        rbt12 = rbt12PorMes[comp]; fonte = 'informado';
      } else if (somarMeses(comp, -12) >= primeira) {
        rbt12 = 0;
        for (var i = 1; i <= 12; i++) {
          var ant = meses[somarMeses(comp, -i)];
          if (ant) rbt12 += ant.receitaTotal;
        }
        fonte = 'xml';
      } else if (opcoes.rbt12Padrao > 0) {
        rbt12 = opcoes.rbt12Padrao; fonte = 'padrao';
      }

      var linha = {
        competencia: comp,
        receitaTotal: arred(m.receitaTotal),
        receitaMonofasica: arred(m.receitaMonofasica),
        receitaIcmsSt: arred(m.receitaIcmsSt),
        rbt12: rbt12 === null ? null : arred(rbt12),
        fonteRbt12: fonte,
        faixa: null, aliquotaEfetiva: null,
        creditoPisCofins: 0, creditoIcms: 0, total: 0,
        prescrito: comp < limite,
        status: 'ok'
      };

      if (linha.prescrito) { linha.status = 'prescrito'; return linha; }
      if (rbt12 === null) { linha.status = 'sem-rbt12'; mesesSemRbt12.push(comp); return linha; }

      var pct = simples.percentuaisRecuperaveis(rbt12);
      if (!pct) { linha.status = 'acima-limite'; return linha; }

      linha.faixa = pct.faixa;
      linha.aliquotaEfetiva = pct.aliquotaEfetiva;
      linha.creditoPisCofins = arred(m.receitaMonofasica * pct.pisCofins);
      linha.creditoIcms = arred(m.receitaIcmsSt * pct.icms);
      linha.total = arred(linha.creditoPisCofins + linha.creditoIcms);

      Object.keys(m.porGrupo).forEach(function (g) {
        grupos[g].credito += m.porGrupo[g] * pct.pisCofins;
      });
      return linha;
    });

    if (mesesSemRbt12.length) {
      alertas.push(mesesSemRbt12.length + ' competência(s) sem RBT12 (faltam 12 meses anteriores nos XMLs). ' +
        'Informe o RBT12 do extrato do PGDAS-D para incluí-las no cálculo.');
    }
    if (notasCanceladas) alertas.push(notasCanceladas + ' nota(s) cancelada(s) desconsiderada(s).');
    if (notasDuplicadas) alertas.push(notasDuplicadas + ' XML(s) duplicado(s) ignorado(s).');
    if (linhas.some(function (l) { return l.prescrito; })) {
      alertas.push('Competências anteriores a ' + limite + ' estão prescritas (CTN, art. 168) e foram excluídas.');
    }

    var totais = linhas.reduce(function (t, l) {
      if (l.prescrito) return t;
      t.receitaTotal += l.receitaTotal;
      t.receitaMonofasica += l.receitaMonofasica;
      t.receitaIcmsSt += l.receitaIcmsSt;
      t.creditoPisCofins += l.creditoPisCofins;
      t.creditoIcms += l.creditoIcms;
      return t;
    }, { receitaTotal: 0, receitaMonofasica: 0, receitaIcmsSt: 0, creditoPisCofins: 0, creditoIcms: 0 });
    Object.keys(totais).forEach(function (k) { totais[k] = arred(totais[k]); });
    totais.credito = arred(totais.creditoPisCofins + totais.creditoIcms);

    var pctHon = opcoes.percentualHonorarios > 0 ? opcoes.percentualHonorarios : 0;

    return {
      emitente: emitente,
      emitentes: emitentes,
      notasConsideradas: notasConsideradas,
      competenciaLimite: limite,
      meses: linhas,
      totais: totais,
      honorarios: arred(totais.credito * pctHon),
      percentualHonorarios: pctHon,
      grupos: Object.keys(grupos).map(function (k) {
        var g = grupos[k];
        return { grupo: g.grupo, nome: g.nome, base: g.base, receita: arred(g.receita), credito: arred(g.credito) };
      }).sort(function (a, b) { return b.receita - a.receita; }),
      produtos: Object.keys(produtos).map(function (k) {
        var p = produtos[k]; p.receita = arred(p.receita); return p;
      }).sort(function (a, b) { return b.receita - a.receita; }).slice(0, 20),
      alertas: alertas
    };
  }

  var api = { analisar: analisar, listarEmitentes: listarEmitentes, ehVenda: ehVenda, somarMeses: somarMeses };
  NS.analise = api;
  if (emNode) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
