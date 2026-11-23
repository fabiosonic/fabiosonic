"""Motor de auditoria: executa todas as regras sobre um lote importado."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..modelos import PESO_SEVERIDADE, SEVERIDADES, Achado, Empresa, Lote
from . import regras_documentos, regras_nfe, regras_nfse, regras_simples
from .consolidacao import consolidar
from .conciliacao import ResultadoConciliacao, conciliar, regra_conciliacao
from .contexto import Contexto, inferir_empresa, montar_contexto
from .regras_simples import LinhaApuracao, apuracao_mensal

TODAS_AS_REGRAS = (regras_documentos.REGRAS + regras_nfe.REGRAS + regras_nfse.REGRAS
                   + regras_simples.REGRAS)


@dataclass
class Resultado:
    empresa: Empresa
    contexto: Contexto
    achados: list[Achado]
    apuracao: list[LinhaApuracao]
    conciliacao: ResultadoConciliacao
    indicadores: dict = field(default_factory=dict)
    achados_detalhados: list[Achado] = field(default_factory=list)

    @property
    def indice_conformidade(self) -> int:
        penalidade = sum(PESO_SEVERIDADE[a.severidade] for a in self.achados)
        return max(0, 100 - penalidade)

    def por_severidade(self) -> dict[str, int]:
        cont = {s: 0 for s in SEVERIDADES}
        for a in self.achados:
            cont[a.severidade] += 1
        return cont


def auditar(lote: Lote, cnpj: str | None = None, regime: str | None = None) -> Resultado:
    empresa = inferir_empresa(lote, cnpj, regime)
    ctx = montar_contexto(lote, empresa)
    achados: list[Achado] = []
    for regra in TODAS_AS_REGRAS:
        achados.extend(regra(ctx))
    conc = conciliar(ctx)
    achados.extend(regra_conciliacao(ctx, conc))

    if empresa.regime_inferido:
        achados.append(Achado(
            "CFG001", "INFO", "Configuração",
            f"Regime tributário inferido: {empresa.regime}",
            "O regime foi deduzido do CRT/opção pelo Simples informado nas notas emitidas.",
            "Confirme o regime no cadastro da empresa para que as regras específicas sejam aplicadas corretamente."))

    ordem = {s: i for i, s in enumerate(SEVERIDADES)}
    achados.sort(key=lambda a: (ordem[a.severidade], a.codigo, a.referencia))
    detalhados = list(achados)
    achados = consolidar(achados)

    datas = [d.data_emissao for d in lote.documentos if d.data_emissao]
    indicadores = {
        "arquivos_lidos": lote.arquivos_lidos,
        "documentos": len(lote.documentos),
        "emitidas": len(ctx.emitidas),
        "recebidas": len(ctx.recebidas),
        "terceiros": len(ctx.terceiros),
        "lancamentos": len(lote.lancamentos),
        "competencias_folha": len(lote.folha),
        "erros": len(lote.erros),
        "periodo_inicio": min(datas) if datas else None,
        "periodo_fim": max(datas) if datas else None,
        "receita_total": sum(ctx.receita_mensal.values()) if ctx.receita_mensal else 0,
        "conciliados": len(conc.conciliados),
    }
    return Resultado(empresa, ctx, achados, apuracao_mensal(ctx), conc, indicadores, detalhados)


__all__ = ["auditar", "Resultado", "inferir_empresa"]
