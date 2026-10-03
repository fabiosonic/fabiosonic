// Início da tela.
// Os arquivos de js/ são carregados em ordem pelo index.html e compartilham o escopo global.
"use strict";
// ---------------------------------------------------------------- início
(async () => {
  const st = await (await fetch("/api/acesso/estado", { method: "POST", body: "{}" })).json();
  if (st.ativo && !st.logado) return telaPin();
  await carregarEstado(); const h = location.hash.slice(1); ir(h in PAGINAS ? h : "painel");
})();
