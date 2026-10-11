/* Comportamento do site — sem dependências. */
(function () {
  "use strict";

  var C = window.SITE_CONFIG || {};
  var Calc = window.Calc;
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(pointer: fine)").matches;

  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); }

  var brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  var pct = new Intl.NumberFormat("pt-BR", { style: "percent", minimumFractionDigits: 1, maximumFractionDigits: 1 });
  function money(v) { return brl.format(v); }

  function store(key, val) {
    try {
      if (val === undefined) return window.localStorage.getItem(key);
      if (val === null) window.localStorage.removeItem(key);
      else window.localStorage.setItem(key, val);
    } catch (e) { return null; }
  }

  /* ---------- WhatsApp ---------- */
  function waUrl(text) {
    if (!C.whatsapp) return null;
    return "https://wa.me/" + C.whatsapp + "?text=" + encodeURIComponent(text);
  }
  function wireWa(a, text) {
    var url = waUrl(text);
    if (!url) return;
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener";
  }
  $$("[data-wa]").forEach(function (a) { wireWa(a, a.getAttribute("data-wa")); });

  /* ---------- Dados institucionais ---------- */
  var ICON = {
    wa: '<svg viewBox="0 0 24 24"><path d="M21 12a9 9 0 0 1-13.4 7.9L3 21l1.2-4.4A9 9 0 1 1 21 12Z"/></svg>',
    mail: '<svg viewBox="0 0 24 24"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>',
    pin: '<svg viewBox="0 0 24 24"><path d="M12 21s-7-6.1-7-11a7 7 0 0 1 14 0c0 4.9-7 11-7 11Z"/><circle cx="12" cy="10" r="2.5"/></svg>',
    app: '<svg viewBox="0 0 24 24"><rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/></svg>'
  };
  var SOCIAL = {
    instagram: '<svg viewBox="0 0 24 24"><path d="M12 7.3A4.7 4.7 0 1 0 16.7 12 4.7 4.7 0 0 0 12 7.3Zm0 7.7a3 3 0 1 1 3-3 3 3 0 0 1-3 3Zm6-7.9a1.1 1.1 0 1 1-1.1-1.1A1.1 1.1 0 0 1 18 7.1ZM21.9 8a5.4 5.4 0 0 0-1.5-3.9A5.4 5.4 0 0 0 16.6 2.6C15 2.5 9 2.5 7.4 2.6a5.4 5.4 0 0 0-3.9 1.5A5.4 5.4 0 0 0 2.1 8C2 9.6 2 14.4 2.1 16a5.4 5.4 0 0 0 1.5 3.9 5.4 5.4 0 0 0 3.9 1.5c1.6.1 7.6.1 9.2 0a5.4 5.4 0 0 0 3.9-1.5 5.4 5.4 0 0 0 1.5-3.9c.1-1.6.1-6.4 0-8Zm-2.1 9.7a3.2 3.2 0 0 1-1.8 1.8c-1.2.5-4.2.4-5.6.4s-4.4.1-5.6-.4a3.2 3.2 0 0 1-1.8-1.8c-.5-1.2-.4-4.2-.4-5.6s-.1-4.4.4-5.6a3.2 3.2 0 0 1 1.8-1.8C8 4.3 11 4.4 12.4 4.4s4.4-.1 5.6.4a3.2 3.2 0 0 1 1.8 1.8c.5 1.2.4 4.2.4 5.6s.1 4.4-.4 5.6Z"/></svg>',
    linkedin: '<svg viewBox="0 0 24 24"><path d="M6.9 21H2.6V8.9h4.3V21ZM4.8 7.2a2.5 2.5 0 1 1 2.5-2.5 2.5 2.5 0 0 1-2.5 2.5ZM21.4 21h-4.3v-5.9c0-1.4 0-3.2-2-3.2s-2.2 1.5-2.2 3.1V21H8.6V8.9h4.1v1.7a4.5 4.5 0 0 1 4-2.2c4.3 0 5.1 2.8 5.1 6.5V21Z"/></svg>',
    facebook: '<svg viewBox="0 0 24 24"><path d="M14 8.5V6.6c0-.9.6-1.1 1-1.1h2.6V1.6L14 1.6c-4 0-4.8 3-4.8 4.9v2H6.4v4h2.8V22.4h4.8V12.5h3.3l.4-4Z"/></svg>'
  };

  var list = $("#contact-list");
  if (list) {
    var items = [];
    if (C.whatsapp && C.telefone) items.push('<li><a href="' + waUrl("Olá! Vim pelo site e quero falar com um contador.") + '" target="_blank" rel="noopener">' + ICON.wa + '<span><small>WhatsApp</small>' + C.telefone + "</span></a></li>");
    if (C.email) items.push('<li><a href="mailto:' + C.email + '">' + ICON.mail + "<span><small>E-mail</small>" + C.email + "</span></a></li>");
    if (C.endereco) items.push("<li>" + (C.mapa ? '<a href="' + C.mapa + '" target="_blank" rel="noopener">' : "<span>") + ICON.pin + "<span><small>Endereço</small>" + C.endereco + "</span>" + (C.mapa ? "</a>" : "</span>") + "</li>");
    if (C.areaDoCliente) items.push('<li><a href="' + C.areaDoCliente + '" target="_blank" rel="noopener">' + ICON.app + "<span><small>Clientes</small>Área do cliente</span></a></li>");
    list.innerHTML = items.join("");
  }
  var socials = $("#socials");
  if (socials && C.redes) {
    socials.innerHTML = Object.keys(SOCIAL).filter(function (k) { return C.redes[k]; }).map(function (k) {
      return '<a href="' + C.redes[k] + '" target="_blank" rel="noopener" aria-label="' + k.charAt(0).toUpperCase() + k.slice(1) + '">' + SOCIAL[k] + "</a>";
    }).join("");
  }
  var legal = $("#legal");
  if (legal) {
    legal.innerHTML = [
      C.razaoSocial,
      C.cnpj && "CNPJ " + C.cnpj,
      C.crcEscritorio,
      C.responsavelTecnico && "Responsável técnico: " + C.responsavelTecnico + (C.crcResponsavel ? " – " + C.crcResponsavel : ""),
      C.endereco
    ].filter(Boolean).join("<br>");
  }
  var ano = $("#ano");
  if (ano) ano.textContent = new Date().getFullYear();

  /* ---------- Cabeçalho, menu e progresso ---------- */
  var topbar = $(".topbar");
  var bar = $(".progress span");
  var ticking = false;
  function onScroll() {
    var y = window.scrollY;
    topbar.classList.toggle("is-solid", y > 30);
    var h = document.documentElement.scrollHeight - window.innerHeight;
    if (bar) bar.style.transform = "scaleX(" + (h > 0 ? y / h : 0) + ")";
    ticking = false;
  }
  window.addEventListener("scroll", function () {
    if (!ticking) { window.requestAnimationFrame(onScroll); ticking = true; }
  }, { passive: true });
  onScroll();

  var toggle = $(".nav__toggle");
  var menu = $("#menu");
  function closeMenu() { menu.classList.remove("is-open"); toggle.setAttribute("aria-expanded", "false"); }
  toggle.addEventListener("click", function () {
    var open = !menu.classList.contains("is-open");
    menu.classList.toggle("is-open", open);
    toggle.setAttribute("aria-expanded", String(open));
  });
  $$("#menu a").forEach(function (a) { a.addEventListener("click", closeMenu); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeMenu(); });

  /* ---------- Revelação e contadores ---------- */
  function countUp(el) {
    var end = +el.getAttribute("data-count");
    var prefix = el.getAttribute("data-prefix") || "";
    if (el.hasAttribute("data-plain") || reduceMotion) { el.textContent = prefix + end; return; }
    var start = performance.now(), dur = 1400;
    (function step(t) {
      var k = Math.min(1, (t - start) / dur);
      el.textContent = prefix + Math.round(end * (1 - Math.pow(1 - k, 3)));
      if (k < 1) requestAnimationFrame(step);
    })(start);
  }
  if ("IntersectionObserver" in window) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("is-in");
        $$("[data-count]", en.target).forEach(countUp);
        io.unobserve(en.target);
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -40px 0px" });
    $$(".reveal").forEach(function (el, i) {
      el.style.transitionDelay = (i % 4) * 70 + "ms";
      io.observe(el);
    });
  } else {
    $$(".reveal").forEach(function (el) { el.classList.add("is-in"); });
    $$("[data-count]").forEach(countUp);
  }

  /* ---------- Microinterações (apenas mouse) ---------- */
  if (finePointer && !reduceMotion) {
    document.addEventListener("pointermove", function (e) {
      var t = e.target.closest && e.target.closest(".spot");
      if (!t) return;
      var r = t.getBoundingClientRect();
      t.style.setProperty("--mx", e.clientX - r.left + "px");
      t.style.setProperty("--my", e.clientY - r.top + "px");
    }, { passive: true });

    $$(".magnetic").forEach(function (b) {
      b.addEventListener("pointermove", function (e) {
        var r = b.getBoundingClientRect();
        b.style.transform = "translate(" + (e.clientX - r.left - r.width / 2) * 0.15 + "px," + (e.clientY - r.top - r.height / 2) * 0.25 + "px)";
      });
      b.addEventListener("pointerleave", function () { b.style.transform = ""; });
    });

    var card = $(".live-card");
    if (card) {
      card.addEventListener("pointermove", function (e) {
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = "perspective(900px) rotateY(" + x * 6 + "deg) rotateX(" + -y * 6 + "deg)";
      });
      card.addEventListener("pointerleave", function () { card.style.transform = ""; });
    }
  }

  /* ---------- Simulador vivo do Fator R ---------- */
  var lvRec = $("#lv-rec"), lvFol = $("#lv-fol");
  var arc = $("#lv-arc"), arcLen = arc ? arc.getTotalLength() : 0;
  var SCALE = 0.56; // o arco vai de 0% a 56%; 28% fica no topo
  (function placeMark() {
    var m = $("#lv-mark");
    if (!m || !arc) return;
    var p = arc.getPointAtLength(arcLen * (Calc.FATOR_R_LIMITE / SCALE));
    m.setAttribute("x1", p.x); m.setAttribute("y1", p.y - 12);
    m.setAttribute("x2", p.x); m.setAttribute("y2", p.y + 12);
  })();
  function fillRange(r) {
    r.style.setProperty("--p", ((r.value - r.min) / (r.max - r.min)) * 100 + "%");
  }
  function updateLive() {
    if (!lvRec) return;
    var rec = +lvRec.value, fol = +lvFol.value;
    fillRange(lvRec); fillRange(lvFol);
    $("#lv-rec-out").textContent = money(rec).replace(",00", "");
    $("#lv-fol-out").textContent = money(fol).replace(",00", "");
    var res = Calc.fatorR(fol, rec);
    if (!res.ok) return;
    var k = Math.min(1, res.fator / SCALE);
    arc.style.strokeDasharray = arcLen;
    arc.style.strokeDashoffset = arcLen * (1 - k);
    arc.style.stroke = res.anexo === "III" ? "#2BE38B" : "#009DF6";
    $("#lv-pct").textContent = pct.format(res.fator);
    var tag = $("#lv-anexo");
    tag.textContent = "Anexo " + res.anexo;
    tag.classList.toggle("is-good", res.anexo === "III");
    $("#lv-msg").textContent = res.anexo === "III"
      ? "Folha acima de 28% da receita: tributação pelo Anexo III."
      : "Faltariam cerca de " + money(res.diferencaFolha).replace(",00", "") + " em folha nos 12 meses para chegar a 28%. Vale conversar antes de decidir.";
  }
  if (lvRec) {
    lvRec.addEventListener("input", updateLive);
    lvFol.addEventListener("input", updateLive);
    updateLive();
  }

  /* ---------- Abas acessíveis ---------- */
  function setupTabs(tablist, onChange) {
    var tabs = $$("[role=tab]", tablist);
    var ink = $(".tabs__ink", tablist);
    function moveInk(t) {
      if (!ink) return;
      ink.style.width = t.offsetWidth + "px";
      ink.style.transform = "translateX(" + t.offsetLeft + "px)";
    }
    function select(t, focus) {
      tabs.forEach(function (x) {
        var on = x === t;
        x.setAttribute("aria-selected", String(on));
        x.tabIndex = on ? 0 : -1;
        document.getElementById(x.getAttribute("aria-controls")).hidden = !on;
      });
      moveInk(t);
      if (focus) t.focus();
      if (onChange) onChange(t);
    }
    tabs.forEach(function (t, i) {
      t.addEventListener("click", function () { select(t); });
      t.addEventListener("keydown", function (e) {
        var d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
        if (!d) return;
        e.preventDefault();
        select(tabs[(i + d + tabs.length) % tabs.length], true);
      });
    });
    var current = tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0] || tabs[0];
    moveInk(current);
    window.addEventListener("resize", function () {
      moveInk(tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0]);
    });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () {
      moveInk(tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0]);
    });
    return select;
  }
  $$(".tabs").forEach(function (tl) {
    var select = setupTabs(tl);
    tl._select = select;
  });

  /* ---------- Serviços ---------- */
  var svcBtns = $$("[data-svc]");
  var svcCta = $("[data-wa-svc]");
  function pickSvc(btn) {
    svcBtns.forEach(function (b) { b.setAttribute("aria-expanded", String(b === btn)); });
    var i = btn.getAttribute("data-svc");
    $$("[data-detail]").forEach(function (d) { d.classList.toggle("is-on", d.getAttribute("data-detail") === i); });
    if (svcCta) wireWa(svcCta, "Olá! Quero saber mais sobre o serviço de " + $("span", btn).textContent + ".");
  }
  svcBtns.forEach(function (b) { b.addEventListener("click", function () { pickSvc(b); }); });
  if (svcBtns[0]) pickSvc(svcBtns[0]);

  /* ---------- Segmentos ---------- */
  var segs = $$(".seg");
  function openSeg(s) { segs.forEach(function (x) { x.classList.toggle("is-open", x === s); }); }
  segs.forEach(function (s) {
    s.addEventListener("click", function () { openSeg(s); });
    s.addEventListener("focus", function () { openSeg(s); });
    if (finePointer) s.addEventListener("mouseenter", function () { openSeg(s); });
  });

  /* ---------- Máscaras ---------- */
  function parseMoney(s) {
    var d = String(s || "").replace(/\D/g, "");
    return d ? parseInt(d, 10) / 100 : NaN;
  }
  $$("input.money").forEach(function (inp) {
    inp.addEventListener("input", function () {
      var v = parseMoney(inp.value);
      inp.value = isNaN(v) ? "" : money(v);
    });
  });
  function maskPhone(inp) {
    inp.addEventListener("input", function () {
      var d = inp.value.replace(/\D/g, "").slice(0, 11);
      var out = d;
      if (d.length > 2) out = "(" + d.slice(0, 2) + ") " + d.slice(2);
      if (d.length > 7) out = "(" + d.slice(0, 2) + ") " + d.slice(2, d.length - 4) + "-" + d.slice(-4);
      inp.value = out;
    });
  }
  $$("input[type=tel]").forEach(maskPhone);

  /* ---------- Envio de leads ---------- */
  function track() {
    if (window.gtag) window.gtag("event", "generate_lead");
  }
  function sendLead(form, payload, waText) {
    var msg = $(".form-msg", form);
    var btn = $("button[type=submit]", form);
    msg.className = "form-msg";

    if (C.leadEndpoint) {
      btn.disabled = true;
      msg.textContent = "Enviando…";
      fetch(C.leadEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(payload)
      }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        msg.className = "form-msg is-ok";
        msg.innerHTML = "Recebemos sua solicitação. Um contador vai chamar você em breve." +
          (C.whatsapp ? ' Se preferir, <a href="' + waUrl(waText) + '" target="_blank" rel="noopener">fale agora pelo WhatsApp</a>.' : "");
        track();
        form.reset();
      }).catch(function () {
        msg.className = "form-msg is-err";
        msg.innerHTML = "Não foi possível enviar agora. Seus dados continuam preenchidos." +
          (C.whatsapp ? ' Tente de novo ou <a href="' + waUrl(waText) + '" target="_blank" rel="noopener">envie pelo WhatsApp</a>.' : " Tente novamente.");
      }).then(function () { btn.disabled = false; });
      return;
    }

    if (C.whatsapp) {
      var url = waUrl(waText);
      var w = window.open(url, "_blank");
      if (w) w.opener = null;
      msg.className = "form-msg is-ok";
      msg.innerHTML = w
        ? "Abrimos o WhatsApp com a sua mensagem pronta — é só tocar em enviar."
        : 'Toque aqui para <a href="' + url + '" target="_blank" rel="noopener">abrir o WhatsApp com a sua mensagem</a>.';
      track();
      return;
    }
    if (C.email) {
      window.location.href = "mailto:" + C.email + "?subject=" + encodeURIComponent("Contato pelo site") + "&body=" + encodeURIComponent(waText);
      return;
    }
    msg.className = "form-msg is-err";
    msg.textContent = "Canal de contato ainda não configurado.";
  }

  function validate(form) {
    var ok = true, first = null;
    $$("input[required]", form).forEach(function (inp) {
      var bad = inp.type === "checkbox" ? !inp.checked
        : inp.type === "tel" ? inp.value.replace(/\D/g, "").length < 10
        : !inp.value.trim();
      inp.setAttribute("aria-invalid", String(bad));
      if (bad) { ok = false; first = first || inp; }
    });
    if (!ok) {
      var m = $(".form-msg", form);
      m.className = "form-msg is-err";
      m.textContent = first.type === "checkbox" ? "Para enviarmos, marque a autorização de contato."
        : first.type === "tel" ? "Informe um WhatsApp com DDD." : "Preencha o seu nome.";
      first.focus();
    }
    return ok;
  }

  var leadForm = $("#lead");
  if (leadForm) {
    leadForm.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!validate(leadForm)) return;
      var f = leadForm.elements;
      var assunto = f.assunto.value || "Solicitar proposta";
      sendLead(leadForm, {
        origem: "site-formulario", nome: f.nome.value.trim(), whatsapp: f.whats.value, assunto: assunto, consentimento: true, data: new Date().toISOString()
      }, "Olá! Sou " + f.nome.value.trim() + " e quero uma proposta. Assunto: " + assunto + ". Meu WhatsApp: " + f.whats.value + ".");
    });
  }

  /* ---------- Diagnóstico ---------- */
  var quiz = $("#quiz");
  if (quiz) {
    var qs = $$(".q", quiz);
    var dots = $$(".diag__steps li");
    var back = $("[data-quiz=back]", quiz);
    var count = $(".quiz__count", quiz);
    var at = 0;
    var LABELS = {};
    $$("input[type=radio]", quiz).forEach(function (r) { LABELS[r.name + ":" + r.value] = r.nextElementSibling.textContent; });

    function answers() {
      var o = {};
      ["momento", "atividade", "faturamento", "equipe"].forEach(function (k) {
        var c = $("input[name=" + k + "]:checked", quiz);
        o[k] = c ? c.value : "";
      });
      return o;
    }
    function go(i, focus) {
      at = Math.max(0, Math.min(qs.length - 1, i));
      qs.forEach(function (q, j) { q.classList.toggle("is-on", j === at); });
      dots.forEach(function (d, j) { d.classList.toggle("is-on", j <= at); });
      back.disabled = at === 0;
      count.textContent = at < 4 ? at + 1 + " de 4" : "Resultado";
      if (at === 4) {
        var pts = Calc.diagnostico(answers());
        $("#diag-result").innerHTML = pts.map(function (p, k) { return '<li style="animation-delay:' + k * 90 + 'ms">' + p + "</li>"; }).join("");
      }
      if (focus) {
        var t = qs[at].querySelector("input:checked") || qs[at].querySelector("input, h3");
        if (t) { if (t.tagName === "H3") t.tabIndex = -1; t.focus({ preventScroll: true }); }
      }
    }
    quiz.addEventListener("change", function (e) {
      if (e.target.type !== "radio") return;
      var idx = qs.indexOf(e.target.closest(".q"));
      setTimeout(function () { if (idx === at) go(at + 1, true); }, reduceMotion ? 0 : 320);
    });
    back.addEventListener("click", function () { go(at - 1, true); });
    quiz.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!validate(quiz)) return;
      var a = answers();
      var resumo = ["momento", "atividade", "faturamento", "equipe"].map(function (k) { return LABELS[k + ":" + a[k]] || "-"; });
      sendLead(quiz, {
        origem: "site-diagnostico", nome: quiz.elements.nome.value.trim(), whatsapp: quiz.elements.whats.value,
        respostas: a, consentimento: true, data: new Date().toISOString()
      }, "Olá! Sou " + quiz.elements.nome.value.trim() + " e fiz o diagnóstico no site.\n• Momento: " + resumo[0] +
        "\n• Atividade: " + resumo[1] + "\n• Faturamento mensal: " + resumo[2] + "\n• Funcionários: " + resumo[3] +
        "\nQuero conversar sobre os pontos de atenção.");
    });

    $$("[data-path]").forEach(function (b) {
      b.addEventListener("click", function () {
        var r = $("input[name=momento][value=" + b.getAttribute("data-path") + "]", quiz);
        r.checked = true;
        go(1);
        $("#diagnostico").scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth" });
        setTimeout(function () { go(1, true); }, reduceMotion ? 0 : 600);
      });
    });
  }

  /* ---------- Calculadoras ---------- */
  function out(form) { return form.parentElement.querySelector(".tool__out"); }
  function ctaHtml(text) {
    var url = waUrl(text);
    return url ? '<a class="btn btn--glow" href="' + url + '" target="_blank" rel="noopener">Analisar este resultado com um contador</a>'
      : '<a class="btn btn--glow" href="#contato">Analisar este resultado com um contador</a>';
  }
  function err(o, m) { o.innerHTML = '<p class="err">' + m + "</p>"; }

  var RENDER = {
    fator: function (v, o) {
      var r = Calc.fatorR(v.folha, v.receita);
      if (!r.ok) return err(o, r.erro);
      var w = Math.min(100, (r.fator / 0.56) * 100);
      o.innerHTML = '<p class="lbl">Fator R</p><p class="big">' + pct.format(r.fator) + "</p>" +
        '<div class="bar"><i style="width:0"></i><s style="left:50%"></s></div>' +
        '<div class="row"><span>Tributação no Simples</span><b>Anexo ' + r.anexo + "</b></div>" +
        '<div class="row"><span>Folha para atingir 28%</span><b>' + money(r.folhaParaAnexoIII) + "</b></div>" +
        (r.anexo === "V" ? '<p class="note">Faltam ' + money(r.diferencaFolha) + " de folha nos 12 meses para chegar a 28%. Ajustes de pró-labore podem mudar o resultado, mas precisam ser avaliados junto com INSS e IRPF.</p>"
          : '<p class="note">Acima de 28%: a atividade é tributada pelo Anexo III. O Fator R é recalculado todo mês.</p>') +
        ctaHtml("Olá! Calculei meu Fator R no site: " + pct.format(r.fator) + " (Anexo " + r.anexo + "). Quero conversar sobre isso.");
      requestAnimationFrame(function () { $(".bar i", o).style.width = w + "%"; });
    },
    margem: function (v, o) {
      var r = Calc.margem(v.receita, v.custos);
      if (!r.ok) return err(o, r.erro);
      o.innerHTML = '<p class="lbl">' + (r.prejuizo ? "Prejuízo no período" : "Margem de lucro") + '</p><p class="big">' + pct.format(r.margem) + "</p>" +
        '<div class="row"><span>' + (r.prejuizo ? "Prejuízo" : "Lucro") + "</span><b>" + money(Math.abs(r.lucro)) + "</b></div>" +
        (r.markup ? '<div class="row"><span>Markup (receita ÷ custos)</span><b>' + r.markup.toFixed(2).replace(".", ",") + "×</b></div>" : "") +
        '<p class="note">' + (r.prejuizo ? "Os custos superaram a receita. Vale revisar preço, mix de produtos e despesas fixas." : "De cada R$ 100 vendidos, sobram " + money(r.margem * 100) + ".") + "</p>" +
        ctaHtml("Olá! Calculei minha margem no site: " + pct.format(r.margem) + ". Quero ajuda para melhorar esse número.");
    },
    pe: function (v, o) {
      var r = Calc.pontoEquilibrio(v.fixos, v.receita, v.variaveis);
      if (!r.ok) return err(o, r.erro);
      o.innerHTML = '<p class="lbl">Receita de equilíbrio no período</p><p class="big">' + money(r.receitaEquilibrio) + "</p>" +
        '<div class="row"><span>Índice de margem de contribuição</span><b>' + pct.format(r.indiceMC) + "</b></div>" +
        '<div class="row"><span>' + (r.acima ? "Folga sobre o equilíbrio" : "Falta para o equilíbrio") + "</span><b>" + money(Math.abs(r.folga)) + "</b></div>" +
        '<p class="note">' + (r.acima ? "Sua receita atual está acima do ponto de equilíbrio." : "Com a receita atual, a empresa opera abaixo do ponto de equilíbrio.") + " Premissa: a proporção de custos variáveis se mantém.</p>" +
        ctaHtml("Olá! Calculei meu ponto de equilíbrio no site: " + money(r.receitaEquilibrio) + " por período. Quero conversar sobre isso.");
    },
    giro: function (v, o) {
      var r = Calc.capitalGiro(v.estoques, v.receber, v.pagar);
      if (!r.ok) return err(o, r.erro);
      o.innerHTML = '<p class="lbl">Necessidade de capital de giro</p><p class="big">' + money(r.ncg) + "</p>" +
        '<p class="note">' + (r.sobra ? "Resultado negativo: os fornecedores financiam a sua operação — o ciclo gera caixa." : "É o valor que a operação consome entre comprar, vender e receber. Precisa vir de caixa próprio ou de financiamento.") + "</p>" +
        ctaHtml("Olá! Calculei minha necessidade de capital de giro no site: " + money(r.ncg) + ". Quero conversar sobre o caixa da empresa.");
    }
  };
  $$("[data-calc]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var v = {};
      $$("input", form).forEach(function (i) { v[i.name] = parseMoney(i.value); });
      RENDER[form.getAttribute("data-calc")](v, out(form));
    });
  });

  var openTool = $("[data-open-tool]");
  if (openTool && lvRec) {
    openTool.addEventListener("click", function () {
      var tl = $(".tabs--pill");
      tl._select($("#tt-fator"));
      var f = $("[data-calc=fator]");
      f.elements.receita.value = money(+lvRec.value);
      f.elements.folha.value = money(+lvFol.value);
      f.requestSubmit ? f.requestSubmit() : f.dispatchEvent(new Event("submit"));
    });
  }

  /* ---------- Checklists ---------- */
  $$(".checklist").forEach(function (cl) {
    var key = "mo-check-" + cl.getAttribute("data-list");
    var boxes = $$("input", cl);
    var saved = (store(key) || "").split(",");
    boxes.forEach(function (b, i) { b.checked = saved[i] === "1"; });
    function paint() {
      var n = boxes.filter(function (b) { return b.checked; }).length;
      var p = Math.round((n / boxes.length) * 100);
      $(".checklist__pct", cl).textContent = p + "%";
      $(".ring__v", cl).style.strokeDashoffset = 100 - p;
      store(key, boxes.map(function (b) { return b.checked ? "1" : "0"; }).join(","));
    }
    boxes.forEach(function (b) { b.addEventListener("change", paint); });
    paint();
    cl._reset = function () { boxes.forEach(function (b) { b.checked = false; }); paint(); store(key, null); };
  });
  var pr = $("[data-print]");
  if (pr) pr.addEventListener("click", function () { window.print(); });
  var clr = $("[data-clear-checks]");
  if (clr) clr.addEventListener("click", function () { $$(".checklist").forEach(function (c) { c._reset(); }); });

  /* ---------- Botão flutuante ---------- */
  var fab = $(".fab");
  if (fab && !store("mo-fab-hint")) {
    setTimeout(function () {
      fab.classList.add("is-hint");
      setTimeout(function () { fab.classList.remove("is-hint"); store("mo-fab-hint", "1"); }, 5000);
    }, 9000);
  }

  /* ---------- Consentimento (Google Ads) ---------- */
  function loadAds() {
    if (!C.googleAdsId || window.gtag) return;
    var s = document.createElement("script");
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + C.googleAdsId;
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", C.googleAdsId);
  }
  var consent = $("#consent");
  if (C.googleAdsId && consent) {
    var choice = store("mo-consent");
    if (choice === "yes") loadAds();
    else if (!choice) consent.hidden = false;
    $$("[data-consent]", consent).forEach(function (b) {
      b.addEventListener("click", function () {
        var v = b.getAttribute("data-consent");
        store("mo-consent", v);
        consent.hidden = true;
        if (v === "yes") loadAds();
      });
    });
  }
})();
