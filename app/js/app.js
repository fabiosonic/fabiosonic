/* Interface do Painel Financeiro. */
(function () {
  'use strict';

  var PF = window.PainelFinanceiro;
  var $ = function (id) { return document.getElementById(id); };
  var CHAVE_REGRAS = 'painel-financeiro:regras';

  var extratos = [];
  var ajustes = {};
  var regras = carregarRegras();
  var ultimo = null;

  var moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  var pct = new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 1, maximumFractionDigits: 1 });
  function brl(v) { return moeda.format(v || 0); }
  function mesAno(c) { return c.slice(5, 7) + '/' + c.slice(0, 4); }
  function dataBr(d) { return d.slice(8, 10) + '/' + d.slice(5, 7) + '/' + d.slice(0, 4); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  // As regras ficam só neste navegador; se o armazenamento estiver bloqueado, o painel funciona sem elas.
  function carregarRegras() {
    try { return JSON.parse(localStorage.getItem(CHAVE_REGRAS)) || []; } catch (e) { return []; }
  }
  function salvarRegras() {
    try { localStorage.setItem(CHAVE_REGRAS, JSON.stringify(regras)); } catch (e) { /* sem armazenamento */ }
  }

  function lerArquivos(lista) {
    var arquivos = Array.prototype.filter.call(lista, function (f) { return /\.(ofx|csv|txt)$/i.test(f.name); });
    if (!arquivos.length) { $('progresso').textContent = 'Nenhum arquivo OFX ou CSV encontrado.'; return; }
    Promise.all(arquivos.map(function (f) {
      // OFX de bancos brasileiros costuma vir em Latin-1
      return f.arrayBuffer().then(function (buf) {
        var txt = new TextDecoder('utf-8').decode(buf);
        if (txt.indexOf('�') >= 0) txt = new TextDecoder('windows-1252').decode(buf);
        return { nome: f.name, texto: txt };
      });
    })).then(function (lidos) {
      lidos.forEach(function (a) {
        var e = PF.extrato.lerExtrato(a.texto, a.nome);
        if (e.lancamentos.length) extratos.push(e);
      });
      var total = extratos.reduce(function (s, e) { return s + e.lancamentos.length; }, 0);
      $('progresso').textContent = extratos.length + ' extrato(s) carregado(s), ' + total + ' lançamento(s).';
      calcular();
    });
  }

  function calcular() {
    if (!extratos.length) { $('resultado').hidden = true; return; }
    ultimo = PF.relatorio.gerar(extratos, { regrasUsuario: regras, ajustes: ajustes });
    renderizar(ultimo);
  }

  function linhaDre(rotulo, valores, classe) {
    return '<tr class="' + (classe || '') + '"><td>' + rotulo + '</td>' +
      valores.map(function (v) { return '<td>' + (typeof v === 'string' ? v : brl(v)) + '</td>'; }).join('') + '</tr>';
  }

  function renderDre(r) {
    var cols = r.meses.concat([r.total]);
    $('tDre').tHead.innerHTML = '<tr><th>Conta</th>' + r.meses.map(function (m) {
      return '<th>' + mesAno(m.competencia) + '</th>';
    }).join('') + '<th>Total</th></tr>';

    function v(campo) { return cols.map(function (c) { return c[campo]; }); }
    function catv(id) { return cols.map(function (c) { return c.porCategoria[id]; }); }
    function detalhe(grupo) {
      return PF.categorias.CATEGORIAS.filter(function (c) { return c.grupo === grupo; })
        .filter(function (c) { return r.total.porCategoria[c.id] !== 0; })
        .map(function (c) { return linhaDre(esc(c.nome), catv(c.id), 'detalhe'); }).join('');
    }

    var html = linhaDre('Receita bruta', v('receitaBruta'), 'grupo') + detalhe('RECEITA') +
      linhaDre('(−) Impostos sobre o faturamento', v('deducoes')) +
      linhaDre('= Receita líquida', v('receitaLiquida'), 'subtotal') +
      linhaDre('(−) Fornecedores e mercadorias', v('custos')) +
      linhaDre('= Lucro bruto', v('lucroBruto'), 'subtotal') +
      linhaDre('(−) Despesas operacionais', v('despesas'), 'grupo') + detalhe('DESPESAS') +
      linhaDre('= Resultado operacional', v('resultadoOperacional'), 'subtotal') +
      linhaDre('Margem operacional', cols.map(function (c) {
        return c.margemOperacional == null ? '-' : pct.format(c.margemOperacional);
      }), 'detalhe') +
      linhaDre('(±) Movimentos não operacionais', v('naoOperacional'), 'grupo') + detalhe('NAO_OPERACIONAL') +
      (r.total.pendente !== 0 ? linhaDre('(±) A classificar', v('pendente'), 'pendente') : '') +
      linhaDre('= Geração de caixa', v('geracaoCaixa'), 'total');
    $('tDre').tBodies[0].innerHTML = html;
  }

  function opcoesCategoria(sel) {
    return PF.categorias.CATEGORIAS.map(function (c) {
      return '<option value="' + c.id + '"' + (c.id === sel ? ' selected' : '') + '>' + esc(c.nome) + '</option>';
    }).join('');
  }

  function renderLancamentos(r) {
    var so = $('soPendentes').checked;
    var lista = r.lancamentos.filter(function (l) { return !so || l.categoria === 'a_classificar'; });
    $('tLanc').tBodies[0].innerHTML = lista.map(function (l) {
      return '<tr class="' + (l.categoria === 'a_classificar' ? 'pendente' : '') + '"><td>' + dataBr(l.data) +
        '</td><td>' + esc(l.conta) + '</td><td>' + esc(l.historico) + '</td><td class="' + (l.valor < 0 ? 'neg' : 'pos') +
        '">' + brl(l.valor) + '</td><td><select data-chave="' + esc(l.chave) + '">' + opcoesCategoria(l.categoria) +
        '</select></td></tr>';
    }).join('') || '<tr><td colspan="5">Nenhum lançamento a classificar. 👍</td></tr>';
  }

  function renderizar(r) {
    $('resultado').hidden = false;
    var periodo = r.meses.length ? mesAno(r.meses[0].competencia) + ' a ' + mesAno(r.meses[r.meses.length - 1].competencia) : '';
    $('identificacao').textContent = [$('cliente').value, periodo && 'Período: ' + periodo,
      $('escritorio').value && 'Elaborado por ' + $('escritorio').value,
      new Date().toLocaleDateString('pt-BR')].filter(Boolean).join(' · ');

    var ind = r.indicadores;
    $('kReceita').textContent = brl(r.total.receitaBruta);
    $('kResultado').textContent = brl(r.total.resultadoOperacional);
    $('kMargem').textContent = ind.margemOperacional == null ? '' : 'Margem ' + pct.format(ind.margemOperacional);
    $('kCaixa').textContent = brl(r.total.geracaoCaixa);
    $('kEquilibrio').textContent = ind.pontoEquilibrio == null ? '-' : brl(ind.pontoEquilibrio);
    $('kEquilibrioObs').textContent = ind.pontoEquilibrio == null ? '' :
      'Receita média atual: ' + brl(ind.receitaMedia);

    $('alertas').innerHTML = r.alertas.map(function (a) {
      return '<div class="alerta ' + a.nivel + '">' + esc(a.texto) + '</div>';
    }).join('');

    renderDre(r);
    $('tContas').tBodies[0].innerHTML = r.contas.map(function (c) {
      return '<tr><td>' + esc(c.conta) + '</td><td>' + brl(c.entradas) + '</td><td>' + brl(c.saidas) + '</td><td>' +
        (c.saldoFinal == null ? 'não informado' : brl(c.saldoFinal)) + '</td></tr>';
    }).join('');
    renderLancamentos(r);
  }

  function exportarCsv() {
    if (!ultimo) return;
    var linhas = [['Data', 'Conta', 'Historico', 'Valor', 'Categoria', 'Grupo DRE']];
    ultimo.lancamentos.forEach(function (l) {
      var c = PF.categorias.porId(l.categoria);
      linhas.push([dataBr(l.data), l.conta, '"' + String(l.historico).replace(/"/g, '""') + '"',
        String(l.valor).replace('.', ','), c.nome, c.grupo]);
    });
    var blob = new Blob(['﻿' + linhas.map(function (l) { return l.join(';'); }).join('\r\n')],
      { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'lancamentos-' + ($('cliente').value || 'cliente').replace(/\W+/g, '-').toLowerCase() + '.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  $('tLanc').addEventListener('change', function (e) {
    var chave = e.target.getAttribute('data-chave');
    if (!chave) return;
    var l = ultimo.lancamentos.filter(function (x) { return x.chave === chave; })[0];
    if ($('lembrar').checked && l) {
      var termo = PF.categorias.normalizar(l.historico);
      regras = regras.filter(function (r) { return PF.categorias.normalizar(r.termo) !== termo; });
      regras.unshift({ termo: termo, categoria: e.target.value });
      salvarRegras();
      ultimo.lancamentos.forEach(function (x) {
        if (PF.categorias.normalizar(x.historico) === termo) delete ajustes[x.chave];
      });
    } else {
      ajustes[chave] = e.target.value;
    }
    calcular();
  });

  $('arquivos').addEventListener('change', function (e) { lerArquivos(e.target.files); e.target.value = ''; });
  var zona = $('soltar');
  ['dragenter', 'dragover'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) { e.preventDefault(); zona.classList.add('ativo'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) { e.preventDefault(); zona.classList.remove('ativo'); });
  });
  zona.addEventListener('drop', function (e) { lerArquivos(e.dataTransfer.files); });

  $('limpar').addEventListener('click', function () {
    extratos = []; ajustes = {}; ultimo = null;
    $('progresso').textContent = '';
    calcular();
  });
  ['cliente', 'escritorio'].forEach(function (id) { $(id).addEventListener('input', calcular); });
  $('soPendentes').addEventListener('change', function () { if (ultimo) renderLancamentos(ultimo); });
  $('imprimir').addEventListener('click', function () { window.print(); });
  $('csv').addEventListener('click', exportarCsv);
})();
