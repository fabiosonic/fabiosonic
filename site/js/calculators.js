/*
 * Regras das calculadoras — funções puras, sem DOM, testáveis em Node.
 * Cada função devolve { ok: true, ... } ou { ok: false, erro: "mensagem" }.
 */
(function (root) {
  "use strict";

  function num(v) {
    return typeof v === "number" && Number.isFinite(v);
  }

  // LC 123/2006, art. 18, §§ 5º-J, 5º-M e 24.
  var FATOR_R_LIMITE = 0.28;

  function fatorR(folha12, receita12) {
    if (!num(folha12) || !num(receita12)) return { ok: false, erro: "Preencha a folha e a receita dos últimos 12 meses." };
    if (folha12 < 0 || receita12 < 0) return { ok: false, erro: "Os valores não podem ser negativos." };
    if (receita12 === 0) return { ok: false, erro: "Sem receita nos últimos 12 meses o Fator R não pode ser calculado." };
    var r = folha12 / receita12;
    var anexoIII = r >= FATOR_R_LIMITE;
    var folhaNecessaria = receita12 * FATOR_R_LIMITE;
    return {
      ok: true,
      fator: r,
      anexo: anexoIII ? "III" : "V",
      folhaParaAnexoIII: folhaNecessaria,
      diferencaFolha: Math.max(0, folhaNecessaria - folha12)
    };
  }

  function margem(receita, custos) {
    if (!num(receita) || !num(custos)) return { ok: false, erro: "Preencha a receita e os custos." };
    if (receita < 0 || custos < 0) return { ok: false, erro: "Os valores não podem ser negativos." };
    if (receita === 0) return { ok: false, erro: "Com receita zero não há margem a calcular." };
    var lucro = receita - custos;
    return {
      ok: true,
      lucro: lucro,
      margem: lucro / receita,
      markup: custos > 0 ? receita / custos : null,
      prejuizo: lucro < 0
    };
  }

  function pontoEquilibrio(fixos, receita, variaveis) {
    if (!num(fixos) || !num(receita) || !num(variaveis)) return { ok: false, erro: "Preencha os três campos do mesmo período." };
    if (fixos < 0 || receita < 0 || variaveis < 0) return { ok: false, erro: "Os valores não podem ser negativos." };
    if (receita === 0) return { ok: false, erro: "Informe a receita do período para calcular a margem de contribuição." };
    var imc = (receita - variaveis) / receita;
    if (imc <= 0) {
      return { ok: false, erro: "Os custos variáveis consomem toda a receita: a margem de contribuição é zero ou negativa, então não existe ponto de equilíbrio nessas condições." };
    }
    var pe = fixos / imc;
    return {
      ok: true,
      indiceMC: imc,
      receitaEquilibrio: pe,
      folga: receita - pe,
      acima: receita >= pe
    };
  }

  // Necessidade operacional de capital de giro (NCG).
  function capitalGiro(estoques, receber, pagar) {
    if (!num(estoques) || !num(receber) || !num(pagar)) return { ok: false, erro: "Preencha estoques, contas a receber e contas a pagar." };
    if (estoques < 0 || receber < 0 || pagar < 0) return { ok: false, erro: "Os valores não podem ser negativos." };
    var ncg = estoques + receber - pagar;
    return { ok: true, ncg: ncg, sobra: ncg < 0 };
  }

  /*
   * Diagnóstico: devolve pontos de atenção informativos conforme as respostas.
   * Não promete economia nem resultado — apenas indica temas a conversar.
   */
  function diagnostico(r) {
    var pontos = [];
    var momento = r.momento, atividade = r.atividade, equipe = r.equipe;

    if (momento === "abrir") {
      pontos.push("Escolha do enquadramento (MEI, Simples Nacional, Lucro Presumido ou Real) antes do registro — a decisão afeta tributos, obrigações e custos desde o primeiro mês.");
      pontos.push("Definição de CNAE, natureza jurídica e contrato social compatíveis com o que a empresa realmente vai fazer.");
    }
    if (momento === "trocar") {
      pontos.push("Transição organizada: levantamento de balancetes, livros, folha e parcelamentos com a contabilidade anterior, sem interromper as obrigações do mês.");
    }
    if (momento === "regularizar") {
      pontos.push("Levantamento de pendências no e-CAC, Simples Nacional, eSocial e prefeitura, com prioridade para o que gera multa ou impede certidões.");
    }
    if (momento === "mei") {
      pontos.push("Acompanhamento do limite anual do MEI: ultrapassá-lo leva ao desenquadramento e pode gerar tributos retroativos sobre o excesso.");
      pontos.push("Planejamento da migração para microempresa, incluindo o regime mais adequado para o novo porte.");
    }

    if (atividade === "servicos" || atividade === "liberal") {
      pontos.push("No Simples Nacional, várias atividades de serviço dependem do Fator R (folha ÷ receita) para serem tributadas no Anexo III ou no Anexo V. Vale simular abaixo.");
    }
    if (atividade === "comercio") {
      pontos.push("Produtos com PIS/COFINS monofásico ou ICMS-ST precisam ser segregados na apuração para não serem tributados de novo.");
    }
    if (atividade === "construcao") {
      pontos.push("Obras exigem cadastro no CNO, controle de retenções previdenciárias e apropriação de custos por obra.");
    }
    if (atividade === "industria") {
      pontos.push("Indústria envolve IPI, créditos de ICMS e controle de estoque e custo de produção — base para formar preço com segurança.");
    }

    if (equipe === "1-5" || equipe === "6-20" || equipe === "20+") {
      pontos.push("Folha com eSocial, DCTFWeb e FGTS Digital: prazos mensais rígidos e eventos que precisam estar coerentes entre si.");
    }
    if (equipe === "0") {
      pontos.push("Pró-labore dos sócios: definir valor e encargos com critério também influencia o Fator R e a previdência dos sócios.");
    }

    pontos.push("Transição da Reforma Tributária (EC 132/2023 e LC 214/2025): a CBS e o IBS passam a conviver com os tributos atuais e exigem revisão de preços, contratos e cadastros.");

    return pontos;
  }

  var api = {
    FATOR_R_LIMITE: FATOR_R_LIMITE,
    fatorR: fatorR,
    margem: margem,
    pontoEquilibrio: pontoEquilibrio,
    capitalGiro: capitalGiro,
    diagnostico: diagnostico
  };

  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.Calc = api;
})(this);
