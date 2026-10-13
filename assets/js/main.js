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
    navLinks.forEach(function (a) { var s = $(a.getAttribute('href')); if (s) secObs.observe(s); });
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
    words.unshift(span.textContent);
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
      var arc = $('.g-val', form);
      var len = arc.getTotalLength ? arc.getTotalLength() : 283;
      arc.style.strokeDasharray = len;
      arc.style.strokeDashoffset = len * (1 - Math.min(r.fator / 0.56, 1)); // 28% no meio do arco
      arc.style.stroke = r.anexo === 'III' ? '#18B36B' : '#009DF6';
      var mark = $('.g-mark', form);
      mark.setAttribute('x1', 100); mark.setAttribute('y1', 4); mark.setAttribute('x2', 100); mark.setAttribute('y2', 30);
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
      if (!r.ok) { fill.style.width = '0'; mark.style.opacity = 0; return showError(form, r.erro); }
      var rt = $('.result-text', form); rt.classList.remove('error');
      $('.bf-main', form).textContent = C.brl(r.receitaEquilibrio);
      var scale = Math.max(v.receita, r.receitaEquilibrio) || 1;
      fill.style.width = (v.receita / scale * 100) + '%';
      mark.style.left = (r.receitaEquilibrio / scale * 100) + '%'; mark.style.opacity = 1;
      rt.innerHTML = 'Índice de margem de contribuição: <strong>' + C.pct(r.imc) + '</strong>. ' + (r.atingido
        ? 'A receita informada supera o ponto de equilíbrio em ' + C.brl(r.folga) + '.'
        : 'Faltam <strong>' + C.brl(-r.folga) + '</strong> de receita para cobrir os custos fixos.') +
        ' <small>(barra = receita atual; marcador = equilíbrio)</small>';
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
