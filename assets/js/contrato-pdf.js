/* =========================================================
   Gera o PDF do contrato preenchido, no navegador, para
   assinatura no Assinador gov.br. Carrega o jsPDF (MIT,
   assets/vendor) somente quando o PDF é solicitado.
   Exposto em window.MOContratoPDF.gerar(contrato, registro).
   ========================================================= */
(function () {
  'use strict';

  var VENDOR = (document.currentScript && document.currentScript.src || '').replace(/js\/contrato-pdf\.js.*$/, 'vendor/jspdf.umd.min.js');

  function carregaJsPDF() {
    if (window.jspdf && window.jspdf.jsPDF) return Promise.resolve(window.jspdf.jsPDF);
    return new Promise(function (ok, falha) {
      var s = document.createElement('script');
      s.src = VENDOR; s.async = true;
      s.onload = function () { window.jspdf && window.jspdf.jsPDF ? ok(window.jspdf.jsPDF) : falha(new Error('jsPDF indisponível')); };
      s.onerror = function () { falha(new Error('Falha ao carregar o gerador de PDF')); };
      document.head.appendChild(s);
    });
  }

  // As fontes padrão do PDF usam WinAnsi: troca caracteres fora dessa tabela.
  function seguro(t) {
    return String(t).replace(/[→⇒]/g, '->').replace(/≥/g, '>=').replace(/≤/g, '<=')
      .replace(/[‐‑]/g, '-').replace(/ /g, ' ');
  }

  function gerar(c, reg) {
    return carregaJsPDF().then(function (JsPDF) {
      var doc = new JsPDF({ unit: 'mm', format: 'a4' });
      var M = 20, L = 210 - 2 * M, Y0 = 22, YMAX = 297 - 22;
      var y = Y0;
      doc.setProperties({ title: c.titulo, subject: 'Contrato versão ' + c.versao, author: 'Moraes e Oliveira Contabilidade Ltda', keywords: 'sha256:' + reg.hash });

      function quebra(alt) { if (y + alt > YMAX) { doc.addPage(); y = Y0; } }
      function texto(t, tam, estilo, cor, espaco) {
        doc.setFont('helvetica', estilo || 'normal'); doc.setFontSize(tam);
        doc.setTextColor.apply(doc, cor || [11, 23, 48]);
        var linhas = doc.splitTextToSize(seguro(t), L);
        var lh = tam * 0.42;
        linhas.forEach(function (ln) { quebra(lh); doc.text(ln, M, y); y += lh; });
        y += espaco == null ? 2 : espaco;
      }

      // CDC, art. 54, § 3º: contrato de adesão em fonte não inferior ao corpo 12.
      texto('MORAES E OLIVEIRA CONTABILIDADE LTDA · CNPJ 24.875.410/0001-44 · CRC RJ-007873/O', 12, 'bold', [0, 86, 167], 1);
      texto('Responsável técnico: Fábio Moraes — CRC RJ-118632/O-1', 12, 'normal', [78, 91, 115], 5);
      texto(c.titulo, 16, 'bold', [0, 19, 48], 1);
      texto('Versão ' + c.versao + ' de ' + c.dataVersao, 12, 'normal', [78, 91, 115], 5);
      c.preambulo.forEach(function (p) { texto(p, 12); });
      if ((c.destaques || []).length) {
        y += 1;
        texto('PONTOS DE ATENÇÃO (CDC, art. 54, § 4º): ' + c.clausulas.filter(function (cl) { return c.destaques.indexOf(cl.numero) !== -1; })
          .map(function (cl) { return 'Cláusula ' + cl.numero + ' — ' + cl.titulo; }).join('; ') + '. Estas cláusulas aparecem destacadas no texto.', 12, 'bold', [146, 64, 14], 3);
      }
      c.clausulas.forEach(function (cl) {
        y += 2; quebra(12);
        var dz = (c.destaques || []).indexOf(cl.numero) !== -1;
        texto('CLÁUSULA ' + cl.numero + ' — ' + cl.titulo.toUpperCase() + (dz ? '  [ATENÇÃO]' : ''), 13, 'bold', dz ? [146, 64, 14] : [0, 19, 48], 1.5);
        cl.itens.forEach(function (i) { texto(i, 12, dz ? 'bold' : 'normal'); });
      });
      c.anexos.forEach(function (a) {
        y += 3; quebra(12);
        texto(a.titulo.toUpperCase(), 13, 'bold', [0, 19, 48], 1.5);
        a.itens.forEach(function (i) { texto(i, 12); });
      });
      y += 2;
      c.fechamento.forEach(function (p) { texto(p, 12); });

      // Registro do aceite eletrônico e espaço das assinaturas digitais
      y += 4; quebra(95);
      doc.setDrawColor(24, 99, 220); doc.setLineWidth(0.5);
      var yBox = y;
      y += 6;
      texto('REGISTRO DO ACEITE ELETRÔNICO NO SITE', 13, 'bold', [0, 19, 48], 2);
      texto('Contratante: ' + reg.contratante + ' — ' + reg.documento, 12);
      texto('Representante: ' + reg.assinante + ' — CPF ' + reg.cpf, 12);
      texto('Data e hora do aceite: ' + reg.data, 12);
      texto('Versão do contrato: ' + reg.versao, 12);
      texto('Código de integridade do texto (SHA-256): ' + reg.hash, 12);
      y += 2;
      texto('ASSINATURAS ELETRÔNICAS', 13, 'bold', [0, 19, 48], 2);
      texto('Este documento deve ser assinado eletronicamente pelo CONTRATANTE no Assinador gov.br (assinador.iti.br), com conta gov.br nível prata ou ouro, e pela CONTRATADA pelo gov.br ou com certificado digital ICP-Brasil. A autenticidade das assinaturas pode ser conferida em validar.iti.gov.br.', 12);
      doc.rect(M - 3, yBox, L + 6, y - yBox + 2);

      var n = doc.getNumberOfPages();
      for (var p = 1; p <= n; p++) {
        doc.setPage(p);
        doc.setFont('helvetica', 'normal'); doc.setFontSize(7.5); doc.setTextColor(120, 130, 150);
        doc.text(seguro('Contrato v' + c.versao + ' · SHA-256 ' + reg.hash.slice(0, 16) + '… · Página ' + p + ' de ' + n), M, 297 - 10);
      }
      var nome = 'contrato-mo-contabil-' + reg.hash.slice(0, 8) + '.pdf';
      doc.save(nome);
      return nome;
    });
  }

  window.MOContratoPDF = { gerar: gerar };
})();
