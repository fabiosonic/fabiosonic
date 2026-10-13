/* =========================================================
   M&O Contábil DIGITAL — interações e animações
   ========================================================= */
(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var finePointer = window.matchMedia('(pointer: fine)').matches;
  var WHATSAPP = '5521998806423';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  /* ---------- Ano no rodapé ---------- */
  $$('[data-year]').forEach(function (el) { el.textContent = new Date().getFullYear(); });

  /* ---------- Cabeçalho, progresso de rolagem e linha do tempo ---------- */
  var header = $('.site-header');
  var progress = $('.scroll-progress span');
  var timeline = $('[data-timeline]');
  var steps = timeline ? $$('.step', timeline) : [];
  var ticking = false;

  function onScroll() {
    var y = window.scrollY;
    var max = document.documentElement.scrollHeight - window.innerHeight;
    header.classList.toggle('scrolled', y > 30);
    if (progress) progress.style.transform = 'scaleX(' + (max > 0 ? y / max : 0) + ')';

    if (timeline) {
      var r = timeline.getBoundingClientRect();
      var p = Math.min(1, Math.max(0, (window.innerHeight * 0.75 - r.top) / r.height));
      timeline.style.setProperty('--progress', p.toFixed(3));
      steps.forEach(function (s, i) { s.classList.toggle('done', p >= (i + 0.5) / steps.length || p === 1); });
    }
    ticking = false;
  }
  window.addEventListener('scroll', function () { if (!ticking) { ticking = true; requestAnimationFrame(onScroll); } }, { passive: true });
  onScroll();

  /* ---------- Menu móvel ---------- */
  var toggle = $('.nav-toggle');
  var nav = $('#menu-principal');
  function closeMenu() { nav.classList.remove('open'); toggle.setAttribute('aria-expanded', 'false'); toggle.querySelector('.sr-only').textContent = 'Abrir menu'; }
  toggle.addEventListener('click', function () {
    var open = !nav.classList.contains('open');
    nav.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.querySelector('.sr-only').textContent = open ? 'Fechar menu' : 'Abrir menu';
  });
  $$('a', nav).forEach(function (a) { a.addEventListener('click', closeMenu); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && nav.classList.contains('open')) { closeMenu(); toggle.focus(); } });

  /* ---------- Link ativo no menu ---------- */
  var navLinks = $$('.main-nav ul a');
  if ('IntersectionObserver' in window) {
    var secObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        navLinks.forEach(function (a) { a.classList.toggle('active', a.getAttribute('href') === '#' + en.target.id); });
      });
    }, { rootMargin: '-45% 0px -50% 0px' });
    // observa todas as seções: se a seção visível não tem link no menu, nenhum item fica ativo
    $$('main section[id]').forEach(function (s) { secObs.observe(s); });
  }

  /* ---------- Revelação na rolagem (escalonada) ---------- */
  var reveals = $$('.reveal');
  // atraso escalonado entre irmãos
  reveals.forEach(function (el) {
    var sibs = Array.prototype.filter.call(el.parentElement.children, function (c) { return c.classList.contains('reveal'); });
    var idx = sibs.indexOf(el);
    if (idx > 0) el.style.setProperty('--d', Math.min(idx * 0.08, 0.5) + 's');
  });
  $$('.bars span, .mini-bars span').forEach(function (b, i, arr) { b.style.animationDelay = (i % 10) * 70 + 'ms'; });

  if (!('IntersectionObserver' in window) || reduceMotion) {
    reveals.forEach(function (el) { el.classList.add('visible', 'in-view'); });
    $$('.hero-visual, .bento-item').forEach(function (el) { el.classList.add('in-view'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add('visible', 'in-view');
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });
    reveals.forEach(function (el) { io.observe(el); });
  }

  /* ---------- Contadores do painel ---------- */
  function countUp(el) {
    var to = parseInt(el.getAttribute('data-to'), 10) || 0;
    if (reduceMotion) { el.textContent = to; return; }
    var start = null, dur = 1600;
    function step(t) {
      if (!start) start = t;
      var p = Math.min(1, (t - start) / dur);
      el.textContent = Math.round(to * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }
  setTimeout(function () { $$('.ticker').forEach(countUp); }, reduceMotion ? 0 : 700);

  /* ---------- Palavra rotativa no título ---------- */
  var rot = $('[data-rotator]');
  if (rot && !reduceMotion) {
    var words = rot.getAttribute('data-rotator').split('|');
    var span = rot.querySelector('.gradient-text');
    // A lista pode já começar pelo texto inicial do span; evita repetir a mesma palavra.
    if (words.indexOf(span.textContent) === -1) words.unshift(span.textContent);
    var wi = 0;
    setInterval(function () {
      if (document.hidden) return;
      rot.classList.add('out');
      setTimeout(function () {
        wi = (wi + 1) % words.length;
        span.textContent = words[wi];
        rot.classList.remove('out'); rot.classList.add('in');
        void span.offsetWidth;
        rot.classList.remove('in');
      }, 450);
    }, 2800);
  }

  /* ---------- Inclinação 3D do painel e brilho dos cartões ---------- */
  if (finePointer && !reduceMotion) {
    var dash = $('.dash.tilt');
    var hv = $('.hero-visual');
    if (dash && hv) {
      hv.addEventListener('mousemove', function (e) {
        var r = hv.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5;
        var y = (e.clientY - r.top) / r.height - 0.5;
        dash.style.transform = 'rotateY(' + (x * 14 - 6) + 'deg) rotateX(' + (-y * 10 + 4) + 'deg)';
      });
      hv.addEventListener('mouseleave', function () { dash.style.transform = ''; });
    }
    $$('.card-glow').forEach(function (c) {
      c.addEventListener('mousemove', function (e) {
        var r = c.getBoundingClientRect();
        c.style.setProperty('--mx', (e.clientX - r.left) + 'px');
        c.style.setProperty('--my', (e.clientY - r.top) + 'px');
      });
    });
    $$('.magnetic').forEach(function (b) {
      b.addEventListener('mousemove', function (e) {
        var r = b.getBoundingClientRect();
        b.style.transform = 'translate(' + (e.clientX - r.left - r.width / 2) * 0.18 + 'px,' + (e.clientY - r.top - r.height / 2) * 0.3 + 'px)';
      });
      b.addEventListener('mouseleave', function () { b.style.transform = ''; });
    });
  }

  /* ---------- Gráfico do painel: dica por mês (hover/foco) ---------- */
  var dchart = $('.dash-chart');
  if (dchart) {
    var tip = $('.dc-tip', dchart);
    $$('.dchart .col', dchart).forEach(function (g) {
      function mostra() {
        $$('.dchart .col', dchart).forEach(function (o) { o.classList.toggle('dim', o !== g); });
        $('.t-mes', tip).textContent = g.getAttribute('data-mes');
        $('.t-rec', tip).textContent = g.getAttribute('data-rec') + ' mil';
        $('.t-desp', tip).textContent = g.getAttribute('data-desp') + ' mil';
        tip.hidden = false;
        var gr = g.getBoundingClientRect(), cr = dchart.getBoundingClientRect();
        var x = gr.left - cr.left + gr.width / 2;
        tip.style.left = Math.max(70, Math.min(cr.width - 70, x)) + 'px';
      }
      function esconde() { tip.hidden = true; $$('.dchart .col', dchart).forEach(function (o) { o.classList.remove('dim'); }); }
      g.addEventListener('pointerenter', mostra);
      g.addEventListener('pointerleave', esconde);
    });
  }

  /* ---------- Rede de partículas no hero (desktop) ---------- */
  var canvas = $('#hero-canvas');
  if (canvas && !reduceMotion && window.innerWidth > 720) {
    var ctx = canvas.getContext('2d');
    var pts = [], W, H, dpr = Math.min(window.devicePixelRatio || 1, 2), running = true;
    function size() {
      W = canvas.offsetWidth; H = canvas.offsetHeight;
      canvas.width = W * dpr; canvas.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      var n = Math.round(W * H / 26000);
      pts = [];
      for (var i = 0; i < n; i++) pts.push({ x: Math.random() * W, y: Math.random() * H, vx: (Math.random() - .5) * .25, vy: (Math.random() - .5) * .25 });
    }
    function draw() {
      if (!running) return;
      ctx.clearRect(0, 0, W, H);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        p.x += p.vx; p.y += p.vy;
        if (p.x < 0 || p.x > W) p.vx *= -1;
        if (p.y < 0 || p.y > H) p.vy *= -1;
        ctx.fillStyle = 'rgba(127,211,255,.55)';
        ctx.beginPath(); ctx.arc(p.x, p.y, 1.4, 0, 6.283); ctx.fill();
        for (var j = i + 1; j < pts.length; j++) {
          var q = pts[j], dx = p.x - q.x, dy = p.y - q.y, d = dx * dx + dy * dy;
          if (d < 14000) {
            ctx.strokeStyle = 'rgba(0,157,246,' + (0.18 * (1 - d / 14000)) + ')';
            ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(q.x, q.y); ctx.stroke();
          }
        }
      }
      requestAnimationFrame(draw);
    }
    size(); draw();
    window.addEventListener('resize', size);
    // pausa quando o hero sai da tela
    new IntersectionObserver(function (en) {
      var vis = en[0].isIntersecting;
      if (vis && !running) { running = true; draw(); } else if (!vis) running = false;
    }).observe(canvas);
  }

  /* ---------- Abas acessíveis ---------- */
  $$('[data-tabs]').forEach(function (wrap) {
    var list = $('[role="tablist"]', wrap);
    var tabs = $$('[role="tab"]', list);
    var ink = $('.tab-ink', list);
    function moveInk(tab) {
      if (!ink) return;
      ink.style.width = tab.offsetWidth + 'px';
      ink.style.transform = 'translate(' + tab.offsetLeft + 'px,' + (tab.offsetTop - 6) + 'px)';
    }
    function select(tab, focus) {
      tabs.forEach(function (t) {
        var on = t === tab;
        t.setAttribute('aria-selected', String(on));
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
      });
      moveInk(tab);
      if (focus) tab.focus();
    }
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(t); });
      t.addEventListener('keydown', function (e) {
        var k = e.key, n = null;
        if (k === 'ArrowRight') n = tabs[(i + 1) % tabs.length];
        if (k === 'ArrowLeft') n = tabs[(i - 1 + tabs.length) % tabs.length];
        if (k === 'Home') n = tabs[0];
        if (k === 'End') n = tabs[tabs.length - 1];
        if (n) { e.preventDefault(); select(n, true); }
      });
    });
    var cur = tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0] || tabs[0];
    requestAnimationFrame(function () { moveInk(cur); });
    window.addEventListener('resize', function () { moveInk(tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0]); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { moveInk(tabs.filter(function (t) { return t.getAttribute('aria-selected') === 'true'; })[0]); });
  });

  /* ---------- Calculadoras ---------- */
  var C = window.MOCalc;
  function showError(form, msg) {
    var rt = $('.result-text', form);
    rt.textContent = msg; rt.classList.add('error');
    var main = $('.bf-main, .g-num', form); if (main) { main.textContent = '—'; main.classList.remove('neg'); }
    var mf = $('.m-fill', form); if (mf) mf.style.width = '0';
  }
  function readFields(form, names) {
    var vals = {}, bad = null;
    names.forEach(function (n) {
      var input = form.elements[n];
      var v = C.parseBRL(input.value);
      var invalid = !isFinite(v);
      input.setAttribute('aria-invalid', String(invalid));
      if (invalid && !bad) bad = input;
      vals[n] = v;
    });
    if (bad) bad.focus();
    return vals;
  }

  var handlers = {
    fatorR: function (form) {
      var v = readFields(form, ['folha', 'receita']);
      var r = C.fatorR(v.folha, v.receita);
      if (!r.ok) return showError(form, r.erro);
      var rt = $('.result-text', form); rt.classList.remove('error');
      $('.g-num', form).textContent = C.pct(r.fator);
      // Medidor horizontal: escala 0–50%, limite fixo em 28% (56% da largura)
      var pos = Math.min(r.fator / 0.5, 1);
      $('.m-fill', form).style.width = (pos * 100) + '%';
      $('.m-fill', form).classList.toggle('over', r.fator > 0.5);
      rt.innerHTML = r.anexo === 'III'
        ? 'Fator R de <strong>' + C.pct(r.fator) + '</strong>, igual ou acima de 28%: a atividade sujeita ao Fator R tende a ser tributada pelo <strong>Anexo III</strong>.'
        : 'Fator R de <strong>' + C.pct(r.fator) + '</strong>, abaixo de 28%: a atividade sujeita ao Fator R tende a ser tributada pelo <strong>Anexo V</strong>. A folha de 12 meses necessária para atingir 28% seria de ' + C.brl(r.folhaNecessaria) + '.';
    },
    margem: function (form) {
      var v = readFields(form, ['receita', 'custos']);
      var r = C.margem(v.receita, v.custos);
      if (!r.ok) return showError(form, r.erro);
      var rt = $('.result-text', form); rt.classList.remove('error');
      var main = $('.bf-main', form);
      main.textContent = C.pct(r.margem); main.classList.toggle('neg', r.prejuizo);
      rt.innerHTML = r.prejuizo
        ? 'Resultado negativo: <strong>prejuízo de ' + C.brl(Math.abs(r.lucro)) + '</strong> no período. Os custos superam a receita.'
        : 'Lucro de <strong>' + C.brl(r.lucro) + '</strong> no período.' + (r.markup !== null ? ' Markup equivalente sobre o custo: ' + C.pct(r.markup) + '.' : '');
    },
    equilibrio: function (form) {
      var v = readFields(form, ['fixos', 'receita', 'variaveis']);
      var r = C.pontoEquilibrio(v.fixos, v.receita, v.variaveis);
      var fill = $('.be-fill', form), mark = $('.be-mark', form);
      if (!r.ok) { fill.style.width = '0'; mark.style.opacity = 0; $('.be-rec', form).textContent = '—'; $('.be-pe', form).textContent = '—'; return showError(form, r.erro); }
      var rt = $('.result-text', form); rt.classList.remove('error');
      $('.bf-main', form).textContent = C.brl(r.receitaEquilibrio);
      var scale = Math.max(v.receita, r.receitaEquilibrio) || 1;
      fill.style.width = (v.receita / scale * 100) + '%';
      mark.style.left = (r.receitaEquilibrio / scale * 100) + '%'; mark.style.opacity = 1;
      $('.be-rec', form).textContent = C.brl(v.receita); $('.be-pe', form).textContent = C.brl(r.receitaEquilibrio);
      rt.innerHTML = 'Índice de margem de contribuição: <strong>' + C.pct(r.imc) + '</strong>. ' + (r.atingido
        ? 'A receita informada supera o ponto de equilíbrio em ' + C.brl(r.folga) + '.'
        : 'Faltam <strong>' + C.brl(-r.folga) + '</strong> de receita para cobrir os custos fixos.');
    },
    giro: function (form) {
      var v = readFields(form, ['estoques', 'receber', 'pagar']);
      var r = C.capitalGiro(v.estoques, v.receber, v.pagar);
      if (!r.ok) return showError(form, r.erro);
      var rt = $('.result-text', form); rt.classList.remove('error');
      $('.bf-main', form).textContent = C.brl(r.ncg);
      rt.innerHTML = r.ncg > 0
        ? 'O ciclo operacional consome <strong>' + C.brl(r.ncg) + '</strong>, que precisam ser financiados por capital próprio ou de terceiros.'
        : r.ncg < 0
          ? 'NCG negativa: os prazos com fornecedores e obrigações <strong>financiam a operação</strong> neste momento. Acompanhe para que isso não mascare problemas de caixa.'
          : 'NCG igual a zero: o ciclo operacional está equilibrado nesta data.';
    }
  };

  $$('form[data-calc]').forEach(function (form) {
    form.addEventListener('submit', function (e) { e.preventDefault(); handlers[form.getAttribute('data-calc')](form); });
    $$('input', form).forEach(function (i) { i.addEventListener('input', function () { i.removeAttribute('aria-invalid'); }); });
  });

  /* ---------- Checklist com progresso local ---------- */
  $$('[data-checklist]').forEach(function (box) {
    var key = 'mo-checklist-' + box.getAttribute('data-checklist');
    var inputs = $$('input[type="checkbox"]', box);
    var bar = $('.ck-bar i', box), count = $('.ck-count', box);
    var saved = [];
    try { saved = JSON.parse(localStorage.getItem(key) || '[]'); } catch (e) { saved = []; }
    inputs.forEach(function (inp, i) { inp.checked = saved.indexOf(i) !== -1; });
    function update(persist) {
      var done = inputs.filter(function (i) { return i.checked; }).length;
      bar.style.width = (done / inputs.length * 100) + '%';
      count.textContent = done + ' de ' + inputs.length;
      if (persist) {
        var idx = []; inputs.forEach(function (inp, i) { if (inp.checked) idx.push(i); });
        try { localStorage.setItem(key, JSON.stringify(idx)); } catch (e) { /* armazenamento indisponível */ }
      }
    }
    inputs.forEach(function (i) { i.addEventListener('change', function () { update(true); }); });
    $('[data-ck-clear]', box).addEventListener('click', function () {
      inputs.forEach(function (i) { i.checked = false; });
      try { localStorage.removeItem(key); } catch (e) { /* ignora */ }
      update(false);
    });
    $('[data-ck-print]', box).addEventListener('click', function () {
      document.body.classList.add('print-checklist');
      window.print();
      setTimeout(function () { document.body.classList.remove('print-checklist'); }, 500);
    });
    update(false);
  });

  /* ---------- Atalhos de jornada (abrir empresa / trocar de contador) ---------- */
  $$('[data-assunto]').forEach(function (a) {
    a.addEventListener('click', function () {
      var sel = $('#f-assunto');
      if (sel) sel.value = a.getAttribute('data-assunto');
    });
  });

  /* ---------- Pacotes: botão "Contratar" pré-seleciona no formulário ---------- */
  var hire = $('#form-contratacao');
  $$('[data-pacote]').forEach(function (a) {
    a.addEventListener('click', function () {
      if (!hire) return;
      var r = $$('input[name="pacote"]', hire).filter(function (i) { return i.value === a.getAttribute('data-pacote'); })[0];
      if (r) { r.checked = true; }
      hire.classList.remove('pkg-pulse'); void hire.offsetWidth; hire.classList.add('pkg-pulse');
    });
  });

  /* ---------- Contratação em etapas + contrato assinado no ato ---------- */
  if (hire) {
    var U = window.MOContratoUtil, MODELO = window.MOContrato;
    var steps = $$('.hire-step', hire);
    var cur = 0;
    // Status do formulário (filho direto); o do dialog vem antes no DOM e não pode ser capturado aqui.
    var hStatus = $(':scope > .form-status', hire);
    var bar = $('.hire-bar i', hire), cnt = $('.hire-count', hire);
    var box = $('[data-contract-box]', hire);
    var aceite = $('#h-aceite'), assinatura = hire.elements.assinatura;
    var hashEl = $('[data-contract-hash]', hire), verEl = $('[data-contract-version]', hire);
    var receipt = $('[data-contract-receipt]', hire);
    var dlg = $('[data-contract-dialog]', hire), signBtn = $('[data-contract-sign]', hire);
    var dStatus = $('[data-dialog-status]', hire), signState = $('[data-sign-state]', hire);
    var readBar = $('[data-read-bar]', hire), readPct = $('[data-read-pct]', hire);
    var leuAteOFim = false, contratoAtual = null, textoAtual = '', hashAtual = '', assinado = false;

    function val(n) { var el = $('[name="' + n + '"]:checked', hire); return el ? el.value : ''; }
    function extras() { return $$('input[name="extras"]:checked', hire).map(function (c) { return c.value; }); }
    function dadosContrato() {
      var f = hire.elements;
      var emConst = f.constituicao.checked;
      var doc = f.documento.value.trim();
      var docFmt = emConst && !doc ? 'empresa em constituição' : (U.soDigitos(doc).length === 11 && !/[A-Za-z]/.test(doc) ? 'CPF ' + U.formataCPF(doc) : 'CNPJ ' + U.formataCNPJ(doc)) + (emConst ? ' (empresa em constituição)' : '');
      return {
        CONTRATANTE_NOME: f.contratante.value.trim(),
        CONTRATANTE_DOC: docFmt,
        REPRESENTANTE_NOME: f.nome.value.trim(),
        REPRESENTANTE_CPF: U.formataCPF(f.cpf.value),
        CONTRATANTE_EMAIL: f.email.value.trim(),
        CONTRATANTE_MUNICIPIO: f.municipio.value.trim(),
        PACOTE: val('pacote'),
        COMPLEMENTARES: extras().join(', ') || 'nenhum',
        PAGAMENTO: val('pagamento'),
        DATA_ACEITE: 'na data e hora indicadas no comprovante de aceite eletrônico'
      };
    }

    function escapa(t) { return String(t).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function contratoHTML(c) {
      var h = '<h3>' + escapa(c.titulo) + '</h3><p class="c-ver">Versão ' + escapa(c.versao) + ' de ' + escapa(c.dataVersao) + '</p>';
      var dest = c.destaques || [];
      if (dest.length) {
        h += '<div class="c-alert" role="note"><b>Pontos de atenção — cláusulas que limitam direitos ou atribuem responsabilidades a você</b><ul>' +
          c.clausulas.filter(function (cl) { return dest.indexOf(cl.numero) !== -1; }).map(function (cl) {
            return '<li><a href="#c-cl-' + cl.numero + '">Cláusula ' + cl.numero + ' — ' + escapa(cl.titulo) + '</a></li>';
          }).join('') + '</ul></div>';
      }
      c.preambulo.forEach(function (p) { h += '<p>' + escapa(p) + '</p>'; });
      c.clausulas.forEach(function (cl) {
        var dz = (c.destaques || []).indexOf(cl.numero) !== -1;
        h += (dz ? '<div class="c-dest">' : '') + '<h4 id="c-cl-' + cl.numero + '">Cláusula ' + cl.numero + ' — ' + escapa(cl.titulo) + (dz ? ' <span class="c-badge">atenção</span>' : '') + '</h4>';
        cl.itens.forEach(function (i) { h += '<p>' + escapa(i) + '</p>'; });
        if (dz) h += '</div>';
      });
      c.anexos.forEach(function (a) {
        h += '<h4>' + escapa(a.titulo) + '</h4>';
        a.itens.forEach(function (i) { h += '<p>' + escapa(i) + '</p>'; });
      });
      c.fechamento.forEach(function (p) { h += '<p>' + escapa(p) + '</p>'; });
      return h.replace(/\[a preencher\]/g, '<mark>[a preencher]</mark>');
    }

    function renderContrato() {
      if (!U || !MODELO) { box.innerHTML = '<p>Não foi possível carregar o contrato. <a href="contrato/condicoes-gerais.html">Abra as condições gerais</a> ou fale conosco pelo WhatsApp.</p>'; return; }
      var novo = U.montaContrato(MODELO, dadosContrato());
      var novoTexto = U.textoCanonico(novo);
      if (novoTexto === textoAtual) return; // mesmo texto: mantém o progresso de leitura
      contratoAtual = novo; textoAtual = novoTexto;
      box.innerHTML = contratoHTML(contratoAtual);
      readBar.style.width = '0'; readPct.textContent = '0% lido'; signBtn.disabled = true; dlg.classList.remove('read');
      box.scrollTop = 0;
      verEl.textContent = MODELO.versao + ' de ' + MODELO.dataVersao;
      leuAteOFim = false; aceite.checked = false; aceite.disabled = true; assinatura.disabled = true;
      $('[data-scroll-hint]', hire).hidden = false;
      hashEl.textContent = 'calculando…';
      U.sha256(textoAtual).then(function (h) { hashAtual = h; hashEl.textContent = h; });
    }
    function progressoLeitura() {
      var max = box.scrollHeight - box.clientHeight;
      var pct = max <= 0 ? 100 : Math.min(100, Math.round(box.scrollTop / max * 100));
      if (!leuAteOFim) {
        readBar.style.width = pct + '%';
        readPct.textContent = pct + '% lido';
      }
      if (!leuAteOFim && box.scrollTop + box.clientHeight >= box.scrollHeight - 8) {
        leuAteOFim = true; aceite.disabled = false; assinatura.disabled = false; signBtn.disabled = false; dlg.classList.add('read');
        readBar.style.width = '100%'; readPct.textContent = '100% lido';
        $('[data-scroll-hint]', hire).hidden = true;
      }
    }
    box.addEventListener('scroll', progressoLeitura, { passive: true });
    box.addEventListener('click', function (e) {
      var l = e.target.closest('a[href^="#c-cl-"]');
      if (!l) return;
      e.preventDefault();
      var alvo = box.querySelector(l.getAttribute('href'));
      if (alvo) box.scrollTop = alvo.offsetTop - box.offsetTop - 8;
    });
    [aceite, assinatura].forEach(function (el) { el.addEventListener('input', function () { dStatus.textContent = ''; el.removeAttribute('aria-invalid'); }); });

    function abrirContrato() {
      if (assinado) return;
      renderContrato();
      dStatus.textContent = ''; dStatus.className = 'form-status';
      if (dlg.showModal) { if (!dlg.open) dlg.showModal(); } else { dlg.setAttribute('open', ''); }
      requestAnimationFrame(function () { progressoLeitura(); box.focus(); });
    }
    function fecharContrato() { if (dlg.open) { dlg.close ? dlg.close() : dlg.removeAttribute('open'); } $('[data-contract-open]', hire).focus(); }
    // Esc (fechamento nativo do dialog) também devolve o foco ao botão que o abriu.
    dlg.addEventListener('close', function () { if (!assinado) $('[data-contract-open]', hire).focus(); });
    $('[data-contract-open]', hire).addEventListener('click', abrirContrato);
    $$('[data-contract-close]', hire).forEach(function (b) { b.addEventListener('click', fecharContrato); });

    function show(i) {
      cur = i;
      steps.forEach(function (s, k) { s.classList.toggle('active', k === i); });
      hire.classList.toggle('first', i === 0);
      hire.classList.toggle('last', i === steps.length - 1);
      bar.style.width = ((i + 1) / steps.length * 100) + '%';
      cnt.textContent = 'Etapa ' + (i + 1) + ' de ' + steps.length;
      hStatus.textContent = ''; hStatus.className = 'form-status';
      if (steps[i].getAttribute('data-step') === '5') abrirContrato();
    }
    function marca(el) { el.setAttribute('aria-invalid', 'true'); return el; }
    function normaliza(t) { return t.trim().replace(/\s+/g, ' ').toLocaleLowerCase('pt-BR'); }
    function validStep(i) {
      var s = steps[i], first = null, msg = 'Preencha os campos desta etapa para continuar.';
      s.removeAttribute('aria-invalid');
      $$('[aria-invalid]', s).forEach(function (el) { el.removeAttribute('aria-invalid'); });
      var radios = {};
      $$('input[required][type="radio"]', s).forEach(function (r) { radios[r.name] = true; });
      Object.keys(radios).forEach(function (n) {
        if (!$$('input[name="' + n + '"]', s).some(function (r) { return r.checked; })) { s.setAttribute('aria-invalid', 'true'); first = first || $('input[name="' + n + '"]', s); }
      });
      $$('select[required], input[required]:not([type="radio"]):not([type="checkbox"])', s).forEach(function (el) {
        if (el.disabled) return;
        if (el.name === 'documento' && hire.elements.constituicao.checked && !el.value.trim()) return;
        if (!el.value.trim()) first = first || marca(el);
      });
      $$('input[required][type="checkbox"]', s).forEach(function (el) { if (!el.checked && !el.disabled) first = first || marca(el); });
      if (!first && s.getAttribute('data-step') === '4') {
        var f = hire.elements, doc = f.documento.value.trim();
        if (doc && !(U.validaCNPJ(doc) || (!/[A-Za-z]/.test(doc) && U.validaCPF(doc)))) { first = marca(f.documento); msg = 'CNPJ ou CPF do contratante inválido. Confira os dígitos.'; }
        else if (!U.validaCPF(f.cpf.value)) { first = marca(f.cpf); msg = 'CPF do representante inválido. Confira os dígitos.'; }
        else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(f.email.value.trim())) { first = marca(f.email); msg = 'Informe um e-mail válido.'; }
      }
      if (!first && s.getAttribute('data-step') === '5') {
        if (!leuAteOFim) { first = box; msg = 'Role o contrato até o final antes de assinar.'; }
        else if (!aceite.checked) { first = marca(aceite); msg = 'Marque o aceite das Condições Gerais.'; }
        else if (normaliza(assinatura.value) !== normaliza(hire.elements.nome.value)) { first = marca(assinatura); msg = 'O nome digitado deve ser igual ao nome do representante informado na etapa anterior.'; }
        else if (!hashAtual) { first = box; msg = 'Aguarde o cálculo do código de integridade e tente novamente.'; }
      }
      if (first) {
        var alvo = (dlg.open && s.getAttribute('data-step') === '5') ? dStatus : hStatus;
        alvo.className = 'form-status error'; alvo.textContent = msg; first.focus(); return false;
      }
      return true;
    }
    $('[data-hire-next]', hire).addEventListener('click', function () {
      if (validStep(cur)) { show(cur + 1); var el = steps[cur].querySelector('input:not([disabled]), select, [data-contract-box]'); if (el) el.focus(); }
    });
    $('[data-hire-prev]', hire).addEventListener('click', function () { if (cur > 0) show(cur - 1); });
    hire.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && e.target.tagName !== 'TEXTAREA' && e.target.type !== 'submit' && !hire.classList.contains('last')) { e.preventDefault(); $('[data-hire-next]', hire).click(); }
    });

    function dataHora(d) {
      var p = function (n) { return ('0' + n).slice(-2); };
      var off = -d.getTimezoneOffset(), sinal = off >= 0 ? '+' : '-';
      return p(d.getDate()) + '/' + p(d.getMonth() + 1) + '/' + d.getFullYear() + ' ' + p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) +
        ' (UTC' + sinal + p(Math.floor(Math.abs(off) / 60)) + ':' + p(Math.abs(off) % 60) + ')';
    }

    hire.addEventListener('submit', function (e) {
      e.preventDefault();
      if (assinado) return;
      for (var i = 0; i < steps.length - 1; i++) { if (!validStep(i)) { fecharContrato(); show(i); validStep(i); return; } }
      if (!dlg.open) { abrirContrato(); return; }
      if (!validStep(steps.length - 1)) return;
      var f = hire.elements, d = dadosContrato();
      var quando = dataHora(new Date());
      var registro = {
        data: quando, versao: MODELO.versao + ' de ' + MODELO.dataVersao, hash: hashAtual,
        assinante: d.REPRESENTANTE_NOME, cpf: d.REPRESENTANTE_CPF, contratante: d.CONTRATANTE_NOME, documento: d.CONTRATANTE_DOC
      };
      var txt = 'Olá! Li e aceitei no site M&O Contábil DIGITAL as Condições Gerais do contrato. Segue o registro do aceite.\n' +
        'Pacote: ' + d.PACOTE + '\n' +
        'Contratante: ' + d.CONTRATANTE_NOME + ' — ' + d.CONTRATANTE_DOC + '\n' +
        'Representante: ' + d.REPRESENTANTE_NOME + ' — CPF ' + d.REPRESENTANTE_CPF + '\n' +
        'E-mail: ' + d.CONTRATANTE_EMAIL + '\n' +
        'Atividade: ' + f.atividade.value + ' | Regime: ' + f.regime.value + ' | Colaboradores: ' + f.funcionarios.value + ' | Notas/mês: ' + f.notas.value + ' | Sócios: ' + f.socios.value + '\n' +
        (d.CONTRATANTE_MUNICIPIO ? 'Município: ' + d.CONTRATANTE_MUNICIPIO + '\n' : '') +
        'Pagamento preferido: ' + d.PAGAMENTO + '\n' +
        'Complementares: ' + d.COMPLEMENTARES + '\n' +
        '— Aceite eletrônico —\n' +
        'Contrato: versão ' + registro.versao + '\n' +
        'Data/hora: ' + registro.data + '\n' +
        'Aceite dado por: ' + registro.assinante + ' — CPF ' + registro.cpf + '\n' +
        'Código de integridade (SHA-256): ' + registro.hash + '\n' +
        'Vou assinar o PDF do contrato no gov.br e enviar por aqui. Aguardo a Proposta Comercial (Anexo I).';
      var url = 'https://api.whatsapp.com/send?phone=' + WHATSAPP + '&text=' + encodeURIComponent(txt);

      $('[data-r-data]', receipt).textContent = registro.data;
      $('[data-r-versao]', receipt).textContent = registro.versao;
      $('[data-r-hash]', receipt).textContent = registro.hash;
      $('[data-contract-wa]', receipt).href = url;
      assinado = true;
      fecharContrato();
      signState.classList.add('partial'); signState.lastChild.textContent = ' Aceite registrado em ' + registro.data + ' · falta assinar com o gov.br';
      $('[data-contract-open]', hire).hidden = true;
      receipt.hidden = false;
      $('.hire-nav', hire).hidden = true;
      steps.forEach(function (s) { $$('input, select, textarea', s).forEach(function (el) { el.disabled = true; }); });

      $('[data-contract-download]', receipt).onclick = function () {
        var doc = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>' + escapa(contratoAtual.titulo) + '</title>' +
          '<style>body{font:16px/1.6 system-ui,sans-serif;max-width:820px;margin:40px auto;padding:0 20px;color:#0B1730}h3{font-size:1.4rem}h4{margin-top:1.6em}.c-ver{color:#4E5B73}mark{background:#FFF3BF}.reg{margin-top:40px;padding:18px;border:2px solid #1863DC;border-radius:12px}code{word-break:break-all}</style></head><body>' +
          contratoHTML(contratoAtual) +
          '<div class="reg"><h4>Registro do aceite eletrônico</h4><p>Aceite dado por: ' + escapa(registro.assinante) + ' — CPF ' + escapa(registro.cpf) + '</p><p>Contratante: ' + escapa(registro.contratante) + ' — ' + escapa(registro.documento) + '</p><p>Data e hora: ' + escapa(registro.data) + '</p><p>Versão do contrato: ' + escapa(registro.versao) + '</p><p>Código de integridade (SHA-256 do texto acima): <code>' + escapa(registro.hash) + '</code></p></div></body></html>';
        var blob = new Blob([doc], { type: 'text/html;charset=utf-8' });
        var a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = 'contrato-mo-contabil-' + registro.hash.slice(0, 8) + '.html';
        document.body.appendChild(a); a.click(); a.remove();
        setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
      };

      var mail = 'mailto:moraes@moraeseoliveiracontabil.com.br?subject=' + encodeURIComponent('Contrato assinado gov.br — ' + d.CONTRATANTE_NOME + ' — ' + registro.hash.slice(0, 8)) +
        '&body=' + encodeURIComponent(txt + '\n\nSegue em anexo o contrato em PDF assinado no Assinador gov.br.');
      $('[data-contract-mail]', receipt).href = mail;
      var pdfBtn = $('[data-contract-pdf]', receipt);
      pdfBtn.onclick = function () {
        if (!window.MOContratoPDF) { $('[data-contract-download]', receipt).click(); return; }
        pdfBtn.disabled = true; pdfBtn.textContent = 'Gerando PDF…';
        window.MOContratoPDF.gerar(contratoAtual, registro).then(function () {
          pdfBtn.disabled = false; pdfBtn.textContent = 'Baixar o PDF novamente';
        }, function () {
          pdfBtn.disabled = false; pdfBtn.textContent = 'Baixar contrato em PDF';
          hStatus.className = 'form-status error';
          hStatus.textContent = 'Não foi possível gerar o PDF neste navegador. Baixe a via em HTML e use "Imprimir > Salvar como PDF".';
        });
      };
      var win = window.open(url, '_blank');
      if (win) win.opener = null;
      hStatus.className = 'form-status ok';
      hStatus.textContent = win
        ? 'Aceite registrado. Abrimos o WhatsApp com o registro pronto: toque em enviar para que ele chegue ao escritório. Depois, baixe o PDF e assine com o gov.br (passos abaixo).'
        : 'Aceite registrado. O navegador bloqueou o WhatsApp: use o botão WhatsApp ou E-mail abaixo para enviar o registro ao escritório e siga os passos para assinar com o gov.br.';
      receipt.setAttribute('tabindex', '-1'); receipt.focus({ preventScroll: true });
      receipt.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'center' });
    });
    show(0);
  }

  /* ---------- Formulário de contato → WhatsApp ---------- */
  var form = $('#form-contato');
  if (form) {
    var status = $('.form-status', form);
    function fieldError(input, msg) {
      input.setAttribute('aria-invalid', 'true');
      var wrap = input.closest('.field');
      var em = $('.error-msg', wrap);
      if (!em) { em = document.createElement('span'); em.className = 'error-msg'; em.id = input.id + '-erro'; wrap.appendChild(em); }
      em.textContent = msg;
      input.setAttribute('aria-describedby', em.id);
    }
    function clearErrors() {
      $$('.error-msg', form).forEach(function (e) { e.remove(); });
      $$('[aria-invalid]', form).forEach(function (i) { i.removeAttribute('aria-invalid'); i.removeAttribute('aria-describedby'); });
    }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      clearErrors();
      status.className = 'form-status'; status.textContent = '';
      var nome = form.elements.nome, assunto = form.elements.assunto, lgpd = form.elements.lgpd;
      var first = null;
      if (nome.value.trim().length < 2) { fieldError(nome, 'Informe seu nome.'); first = first || nome; }
      if (!assunto.value) { fieldError(assunto, 'Selecione o assunto.'); first = first || assunto; }
      if (!lgpd.checked) { fieldError(lgpd, 'É preciso concordar para continuar.'); first = first || lgpd; }
      if (first) { status.classList.add('error'); status.textContent = 'Revise os campos destacados.'; first.focus(); return; }

      var txt = 'Olá! Vim pelo site M&O Contábil DIGITAL.\n' +
        'Nome: ' + nome.value.trim() + '\n' +
        (form.elements.empresa.value.trim() ? 'Empresa: ' + form.elements.empresa.value.trim() + '\n' : '') +
        'Assunto: ' + assunto.value +
        (form.elements.mensagem.value.trim() ? '\nMensagem: ' + form.elements.mensagem.value.trim() : '');
      var url = 'https://api.whatsapp.com/send?phone=' + WHATSAPP + '&text=' + encodeURIComponent(txt);
      var win = window.open(url, '_blank');
      if (win) win.opener = null;
      status.classList.add('ok');
      status.textContent = win === null
        ? 'Seu navegador bloqueou a nova janela. '
        : 'Abrimos o WhatsApp com sua mensagem pronta — é só tocar em enviar por lá.';
      if (win === null) {
        var a = document.createElement('a'); a.href = url; a.target = '_blank'; a.rel = 'noopener'; a.textContent = 'Clique aqui para abrir o WhatsApp.';
        status.appendChild(a);
      }
    });
  }
})();
