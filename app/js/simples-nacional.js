/*
 * Simples Nacional — Anexo I (Comércio), LC 123/2006 com redação da LC 155/2016.
 * Alíquota efetiva = (RBT12 × Aliq − PD) / RBT12
 * Percentuais de repartição dos tributos por faixa (Anexo I).
 */
(function (global) {
  'use strict';

  var ANEXO_I = [
    { faixa: 1, ate: 180000.00,  aliquota: 0.040, deducao: 0,
      partilha: { irpj: 0.055, csll: 0.035, cofins: 0.1274, pis: 0.0276, cpp: 0.415, icms: 0.340 } },
    { faixa: 2, ate: 360000.00,  aliquota: 0.073, deducao: 5940,
      partilha: { irpj: 0.055, csll: 0.035, cofins: 0.1274, pis: 0.0276, cpp: 0.415, icms: 0.340 } },
    { faixa: 3, ate: 720000.00,  aliquota: 0.095, deducao: 13860,
      partilha: { irpj: 0.055, csll: 0.035, cofins: 0.1274, pis: 0.0276, cpp: 0.420, icms: 0.335 } },
    { faixa: 4, ate: 1800000.00, aliquota: 0.107, deducao: 22500,
      partilha: { irpj: 0.055, csll: 0.035, cofins: 0.1274, pis: 0.0276, cpp: 0.420, icms: 0.335 } },
    { faixa: 5, ate: 3600000.00, aliquota: 0.143, deducao: 87300,
      partilha: { irpj: 0.055, csll: 0.035, cofins: 0.1274, pis: 0.0276, cpp: 0.420, icms: 0.335 } },
    { faixa: 6, ate: 4800000.00, aliquota: 0.190, deducao: 378000,
      // Na 6ª faixa o ICMS é recolhido fora do DAS (sublimite estadual).
      partilha: { irpj: 0.135, csll: 0.100, cofins: 0.2827, pis: 0.0613, cpp: 0.421, icms: 0 } }
  ];

  function faixaPorRbt12(rbt12) {
    if (!(rbt12 > 0)) return ANEXO_I[0];
    for (var i = 0; i < ANEXO_I.length; i++) {
      if (rbt12 <= ANEXO_I[i].ate) return ANEXO_I[i];
    }
    return null; // acima do limite do Simples Nacional
  }

  function aliquotaEfetiva(rbt12) {
    var f = faixaPorRbt12(rbt12);
    if (!f) return null;
    if (f.faixa === 1) return f.aliquota;
    return (rbt12 * f.aliquota - f.deducao) / rbt12;
  }

  /*
   * Percentual da receita que corresponde a cada tributo dentro do DAS.
   * Ex.: pisCofins = alíquota efetiva × (%PIS + %COFINS da faixa).
   */
  function percentuaisRecuperaveis(rbt12) {
    var f = faixaPorRbt12(rbt12);
    if (!f) return null;
    var ef = aliquotaEfetiva(rbt12);
    return {
      faixa: f.faixa,
      aliquotaEfetiva: ef,
      pisCofins: ef * (f.partilha.pis + f.partilha.cofins),
      icms: ef * f.partilha.icms
    };
  }

  var api = {
    ANEXO_I: ANEXO_I,
    faixaPorRbt12: faixaPorRbt12,
    aliquotaEfetiva: aliquotaEfetiva,
    percentuaisRecuperaveis: percentuaisRecuperaveis
  };

  var NS = global.RadarTributario = global.RadarTributario || {};
  NS.simples = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
