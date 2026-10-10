#!/usr/bin/env python3
"""Simulador simples de economia de token de jogo (faucets x sinks).

Objetivo: testar, ANTES de lançar, se a oferta circulante e o preço implícito
se sustentam sob diferentes cenários de crescimento de jogadores.

Modelo (diário, por jogador ativo):
  - faucet: cada jogador ganha `recompensa` tokens/dia (limitado pelo teto
    diário do contrato, `dailyMintLimit`);
  - sink: cada jogador queima `sink` tokens/dia (crafting, upgrades, taxas);
  - o excedente (recompensa - sink) é parcialmente vendido (`fracao_vendida`);
  - a demanda em R$ vem de (a) novos jogadores comprando o "ingresso" e
    (b) gasto recorrente de jogadores pagantes.

Preço de equilíbrio do dia = R$ que entram / tokens vendidos (suavizado).
É um indicador didático, NÃO uma previsão de preço.

Lição que o modelo evidencia: se o preço depende de novos entrantes para
absorver a venda das recompensas, a economia é estruturalmente frágil (o
"ingresso" do novato paga o saque do veterano). Sinks fortes e receita
recorrente real são o que sustentam o valor.

Uso:
  python3 tools/simulacao_tokenomics.py
"""

from dataclasses import dataclass


@dataclass
class Cenario:
    nome: str
    jogadores_iniciais: int = 10_000
    crescimento_diario: float = 0.01  # +1% ao dia
    recompensa: float = 50.0  # tokens/jogador/dia (faucet)
    sink: float = 20.0  # tokens/jogador/dia queimados
    teto_diario: float = 2_000_000.0  # dailyMintLimit do contrato
    fracao_vendida: float = 0.40  # parte do excedente que vai a mercado
    ingresso_brl: float = 20.0  # R$ gastos em tokens por novo jogador
    gasto_recorrente_brl: float = 0.50  # R$/jogador/dia (média, incl. não pagantes)
    dias: int = 365


def simular(c: Cenario) -> list[dict]:
    jogadores = float(c.jogadores_iniciais)
    oferta = 0.0
    preco = None
    historico = []

    for dia in range(1, c.dias + 1):
        novos = max(jogadores * c.crescimento_diario, 0.0)
        jogadores = max(jogadores * (1 + c.crescimento_diario), 0.0)

        emitido = min(jogadores * c.recompensa, c.teto_diario)
        ganho_por_jogador = emitido / jogadores if jogadores else 0.0
        queimado = min(jogadores * c.sink, oferta + emitido)
        oferta += emitido - queimado

        excedente = max(ganho_por_jogador - c.sink, 0.0)
        vendido = jogadores * excedente * c.fracao_vendida
        entrada_brl = novos * c.ingresso_brl + jogadores * c.gasto_recorrente_brl

        sem_venda = vendido <= 0
        if not sem_venda:
            preco_dia = entrada_brl / vendido
            preco = preco_dia if preco is None else 0.9 * preco + 0.1 * preco_dia

        historico.append(
            {
                "dia": dia,
                "jogadores": jogadores,
                "emitido": emitido,
                "queimado": queimado,
                "oferta": oferta,
                "sink_faucet": queimado / emitido if emitido else 0.0,
                "preco": None if sem_venda else preco,
                "oferta_por_jogador": oferta / jogadores if jogadores else 0.0,
                "entrada_brl": entrada_brl,
            }
        )
    return historico


def resumo(c: Cenario) -> None:
    h = simular(c)
    print(f"\n=== {c.nome} ===")
    print(f"{'dia':>5} {'jogadores':>10} {'emitido/dia':>12} {'queimado/dia':>13} "
          f"{'oferta':>13} {'oferta/jog.':>11} {'sink/faucet':>11} {'R$ entra/dia':>13} {'preço R$':>9}")
    for r in h:
        if r["dia"] in (1, 30, 90, 180, 365):
            preco = "s/ venda" if r["preco"] is None else f"{r['preco']:.4f}"
            print(f"{r['dia']:>5} {r['jogadores']:>10,.0f} {r['emitido']:>12,.0f} "
                  f"{r['queimado']:>13,.0f} {r['oferta']:>13,.0f} {r['oferta_por_jogador']:>11,.0f} "
                  f"{r['sink_faucet']:>11.2f} {r['entrada_brl']:>13,.0f} {preco:>9}")


if __name__ == "__main__":
    resumo(Cenario("A) Crescimento +1%/dia (o teto diário passa a limitar a emissão)"))
    resumo(Cenario("B) Estagnação (0%/dia)", crescimento_diario=0.0))
    resumo(Cenario("C) Queda -1%/dia (sem novos entrantes)", crescimento_diario=-0.01))
    resumo(Cenario("D) Queda -1%/dia com sinks fortes (40/50) e menos venda",
                   crescimento_diario=-0.01, sink=40.0, fracao_vendida=0.25))
