/* Interface do Radar Tributário. */
(function () {
  'use strict';

  var RT = window.RadarTributario;
  var $ = function (id) { return document.getElementById(id); };

  var documentos = [];
  var rbt12PorMes = {};
  var ultimo = null;

  var moeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  var pct = new Intl.NumberFormat('pt-BR', { style: 'percent', minimumFractionDigits: 2 });
  function brl(v) { return moeda.format(v || 0); }
  function mesAno(c) { return c.slice(5, 7) + '/' + c.slice(0, 4); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function lerArquivos(lista) {
    var arquivos = Array.prototype.filter.call(lista, function (f) { return /\.xml$/i.test(f.name); });
    if (!arquivos.length) { $('progresso').textContent = 'Nenhum arquivo .xml encontrado.'; return; }
    $('progresso').textContent = 'Lendo ' + arquivos.length + ' arquivo(s)...';

    Promise.all(arquivos.map(function (f) { return f.text(); })).then(function (textos) {
      var ignorados = 0;
      textos.forEach(function (t) {
        var d = RT.nfe.lerXml(t);
        if (d.tipo === 'desconhecido') ignorados++; else documentos.push(d);
      });
      $('progresso').textContent = documentos.length + ' documento(s) carregado(s)' +
        (ignorados ? ' · ' + ignorados + ' arquivo(s) não reconhecido(s) como NF-e' : '') + '.';
      calcular();
    });
  }

  function opcoes() {
    return {
      rbt12Padrao: parseFloat($('rbt12').value) || 0,
      rbt12PorMes: rbt12PorMes,
      percentualHonorarios: (parseFloat($('honorarios').value) || 0) / 100
    };
  }

  function calcular() {
    if (!documentos.length) return;
    ultimo = RT.analise.analisar(documentos, opcoes());
    renderizar(ultimo);
  }

  var STATUS = { prescrito: 'prescrito', 'sem-rbt12': 'informe o RBT12', 'acima-limite': 'acima do limite' };

  function renderizar(r) {
    $('resultado').hidden = false;
    var cliente = $('cliente').value || (r.emitente && r.emitente.nome) || '';
    var cnpj = r.emitente ? r.emitente.cnpj.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5') : '';
    $('identificacao').textContent = [cliente, cnpj && 'CNPJ ' + cnpj,
      r.notasConsideradas + ' notas analisadas', $('escritorio').value && 'Elaborado por ' + $('escritorio').value,
      new Date().toLocaleDateString('pt-BR')].filter(Boolean).join(' · ');

    $('kTotal').textContent = brl(r.totais.credito);
    $('kPis').textContent = brl(r.totais.creditoPisCofins);
    $('kIcms').textContent = brl(r.totais.creditoIcms);
    $('kHon').textContent = brl(r.honorarios);

    $('alertas').innerHTML = r.alertas.map(function (a) { return '<div class="alerta">' + esc(a) + '</div>'; }).join('');

    $('tMeses').tBodies[0].innerHTML = r.meses.map(function (m) {
      var inativo = m.status !== 'ok';
      return '<tr class="' + (inativo ? 'inativo' : '') + '">' +
        '<td>' + mesAno(m.competencia) + '</td>' +
        '<td>' + brl(m.receitaTotal) + '</td>' +
        '<td>' + brl(m.receitaMonofasica) + '</td>' +
        '<td>' + brl(m.receitaIcmsSt) + '</td>' +
        '<td><input type="number" step="1000" data-comp="' + m.competencia + '" value="' +
          (m.rbt12 == null ? '' : Math.round(m.rbt12)) + '" title="Fonte: ' + (m.fonteRbt12 || '-') + '"' +
          (m.prescrito ? ' disabled' : '') + '></td>' +
        '<td>' + (m.faixa ? m.faixa + 'ª' : (STATUS[m.status] || '-')) + '</td>' +
        '<td>' + (m.aliquotaEfetiva ? pct.format(m.aliquotaEfetiva) : '-') + '</td>' +
        '<td>' + brl(m.creditoPisCofins) + '</td>' +
        '<td>' + brl(m.creditoIcms) + '</td>' +
        '<td><strong>' + brl(m.total) + '</strong></td></tr>';
    }).join('');

    $('tMeses').tFoot.innerHTML = '<tr><td>Total</td><td>' + brl(r.totais.receitaTotal) + '</td><td>' +
      brl(r.totais.receitaMonofasica) + '</td><td>' + brl(r.totais.receitaIcmsSt) +
      '</td><td></td><td></td><td></td><td>' + brl(r.totais.creditoPisCofins) + '</td><td>' +
      brl(r.totais.creditoIcms) + '</td><td>' + brl(r.totais.credito) + '</td></tr>';

    $('tGrupos').tBodies[0].innerHTML = r.grupos.map(function (g) {
      return '<tr><td>' + esc(g.nome) + '</td><td>' + esc(g.base) + '</td><td>' + brl(g.receita) +
        '</td><td>' + brl(g.credito) + '</td></tr>';
    }).join('') || '<tr><td colspan="4">Nenhum produto monofásico identificado.</td></tr>';

    $('tProdutos').tBodies[0].innerHTML = r.produtos.map(function (p) {
      return '<tr><td>' + esc(p.ncm) + '</td><td>' + esc(p.descricao) + '</td><td>' + esc(p.grupo) +
        '</td><td>' + brl(p.receita) + '</td></tr>';
    }).join('') || '<tr><td colspan="4">-</td></tr>';
  }

  function exportarCsv() {
    if (!ultimo) return;
    var linhas = [['Competencia', 'Receita', 'Receita monofasica', 'Receita ICMS-ST', 'RBT12', 'Faixa',
      'Aliquota efetiva', 'Credito PIS/COFINS', 'Credito ICMS', 'Total', 'Situacao']];
    ultimo.meses.forEach(function (m) {
      linhas.push([mesAno(m.competencia), m.receitaTotal, m.receitaMonofasica, m.receitaIcmsSt, m.rbt12 || '',
        m.faixa || '', m.aliquotaEfetiva ? (m.aliquotaEfetiva * 100).toFixed(4) : '', m.creditoPisCofins,
        m.creditoIcms, m.total, m.status]);
    });
    var csv = linhas.map(function (l) {
      return l.map(function (v) { return typeof v === 'number' ? String(v).replace('.', ',') : v; }).join(';');
    }).join('\r\n');
    var blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'radar-tributario-' + ((ultimo.emitente && ultimo.emitente.cnpj) || 'cliente') + '.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }

  $('arquivos').addEventListener('change', function (e) { lerArquivos(e.target.files); e.target.value = ''; });
  $('pasta').addEventListener('change', function (e) { lerArquivos(e.target.files); e.target.value = ''; });

  var zona = $('soltar');
  ['dragenter', 'dragover'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) { e.preventDefault(); zona.classList.add('ativo'); });
  });
  ['dragleave', 'drop'].forEach(function (ev) {
    zona.addEventListener(ev, function (e) { e.preventDefault(); zona.classList.remove('ativo'); });
  });
  zona.addEventListener('drop', function (e) { lerArquivos(e.dataTransfer.files); });

  ['honorarios', 'rbt12', 'cliente', 'escritorio'].forEach(function (id) {
    $(id).addEventListener('input', calcular);
  });

  $('tMeses').addEventListener('change', function (e) {
    var comp = e.target.getAttribute('data-comp');
    if (!comp) return;
    var v = parseFloat(e.target.value);
    if (v > 0) rbt12PorMes[comp] = v; else delete rbt12PorMes[comp];
    calcular();
  });

  $('imprimir').addEventListener('click', function () { window.print(); });
  $('csv').addEventListener('click', exportarCsv);
})();
