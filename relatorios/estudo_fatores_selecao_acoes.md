# Estudo: a melhor maneira de lucrar com ações na B3 (nov/2016 a nov/2026)

## Conclusão

**Selecionar QUAIS ações comprar e rebalancear periodicamente funcionou muito melhor do que tentar acertar
QUANDO entrar e sair.** O estudo anterior, de timing com 17 setups de swing trade, não superou o CDI.

| Abordagem | Retorno a.a. | 2016–21 | 2021–26 | Queda máx. | Veredito |
|---|---|---|---|---|---|
| **Dividendos: top 10 por dividend yield, mensal** | **+18,0%** | **+17,2%** | **+18,9%** | -41% | ✅ **mais consistente**: acima do CDI nas duas metades e em todas as variações |
| Momentum 12-1: top 10, mensal | +25,3% | +46,4% | +7,9% | -48% | ⚠️ excelente até 2021, **abaixo do CDI** desde então |
| Mix: 50% momentum + 50% dividendos | +22,2% | +32,3% | +13,4% | -42% | ✅ bom equilíbrio entre os dois regimes |
| Todas as 44 ações, peso igual | +17,9% | +27,4% | +9,3% | -45% | referência (com viés de sobrevivência) |
| Ibovespa | +10,3% | — | — | -47% | referência |
| CDI | +9,4% | +6,0% | +12,8% | 0% | referência |
| Melhor setup de swing (MACD comprado) | ~+17% | — | ~CDI | -13% | estudo anterior |

### Por que dividendos
- Ficou acima do CDI em **7 de 10 anos**: perdeu em 2021 e 2024, e ficou ligeiramente abaixo em 2026 até novembro.
- **Funcionou nos dois regimes de juros**: com Selic baixa (2017–2021) e com Selic de 10% a 15% (2022–2026).
  Empresas maduras e boas pagadoras resistem melhor ao juro alto.
- **Robusto à configuração**: top 5, top 10, top 15, mensal ou trimestral, todas as versões ficaram acima do CDI nas duas metades.
- **Giro baixo**: cerca de 3,6 vezes o capital por ano, o que significa poucas ordens e pouco custo.

### Por que momentum isolado não
O momentum ganhou 58 pontos do universo em 2017 e 26 pontos em 2020, mas perdeu em 2023, 2025 e 2026.
Desde 2021 rende menos que o CDI. Esse comportamento é típico do fator: fases muito boas seguidas de quedas fortes.
Na combinação 50/50, ele ajuda nos anos de mercado em alta sem dominar o risco.

## Riscos (leia antes de operar)
1. **Viés de sobrevivência.** O universo são as grandes empresas de **hoje**. Sem as 8 maiores vencedoras do período
   (PRIO3, BPAC11, CPLE3, BRAP4, PETR4, PETR3, WEGE3, ENEV3), a carteira de dividendos cai para +11,2% ao ano
   e o momentum para +16,0%. Os dois continuam acima do CDI total, mas com folga menor.
   Parte do ganho dos dividendos veio de Petrobras, Bradespar e Copel.
2. **Significância.** A melhor estatística foi t = 2,1 contra o CDI, no momentum. Nada é prova definitiva:
   dez anos de mercado são pouco tempo para fatores de ações.
3. **Queda de 40% a 50%** pode acontecer, como em 2020. Só opere com dinheiro que possa ficar investido por anos.
4. Os dados vêm do Yahoo Finance e a premissa de execução usa o fechamento do pregão seguinte ao sinal, com custo de 0,10% sobre o giro.

## O que NÃO funcionou
- Baixa volatilidade: +15,0% ao ano, abaixo do universo, embora com queda máxima menor (-36%).
- Reversão de 1 mês (comprar as que mais caíram no mês): +10,8% ao ano, com giro alto.
- Filtro de mercado (só comprado quando o Ibovespa está acima da MM200): **reduz a queda máxima pela metade
  (-48% para -24%) mas corta o retorno**. Serve para quem prioriza dormir tranquilo.

## Metodologia
- 44 ações líquidas do Ibovespa, com cotações ajustadas e dividendos do Yahoo. CDI da série 12 do BCB.
- A cada fim de mês: ranqueia, compra as N melhores com peso igual e executa no fechamento do pregão seguinte, sem olhar o futuro.
- Dividend yield = dividendos e JCP pagos nos últimos 12 meses ÷ preço não ajustado.
- Momentum 12-1 = retorno dos últimos 12 meses, excluindo o último mês.
- Custo de 0,10% sobre o valor girado. **Impostos não considerados** neste estudo.
- Resultados completos: `relatorios/ranking_fatores.csv` e `relatorios/curvas_fatores.csv`.
- Reproduzir: `python pesquisa/baixar_dividendos.py`, `python pesquisa/fatores_rodar.py` e `python pesquisa/fatores_robustez.py`.

*Resultado passado não garante resultado futuro. Isto não é recomendação de investimento.*
