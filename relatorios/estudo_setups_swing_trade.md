# Estudo: setups de swing trade na B3, comprado e vendido (nov/2016 a nov/2026)

## Resposta curta

1. **Nenhum setup é lucrativo de forma confiável quando comparado ao CDI** (9,41% ao ano no período).
   Os melhores resultados ficaram longe de significância estatística: a estatística t foi de no máximo 1,9,
   depois de 34 testes. Isso é compatível com sorte.
2. **No lado vendido (short), todos os setups perderam para o CDI nas 44 ações.** A única exceção no Ibovespa
   (inside bar vendido, +1,3% ao ano) é ruído: o robô ficou exposto 6% do tempo.
3. **Os setups de tendência no lado comprado foram os melhores**: cruzamento MME 9/21, MACD, rompimento de Bollinger e Donchian.
   O mérito real deles foi **cortar a queda máxima** (de -45% para -13% a -20%), não ganhar mais.
   Nenhum superou o simples comprar e segurar as mesmas ações, e quase todos **perderam para o CDI de 2021 a 2026**.
4. **Os candidatos mais consistentes**, sem resultado negativo relevante em nenhuma metade do período nem em nenhum dos dois universos:
   - **MACD cruzamento, comprado**: +7,7% ao ano sobre o CDI nas ações e +6,5% ao ano no Ibovespa, com queda máxima de -13% a -17%.
     De 2021 a 2026 ficou empatado com o CDI nas ações (-0,1% ao ano) e acima dele no Ibovespa (+2,5% ao ano).
   - **Setup 9.1, comprado no Ibovespa**: +5,7% ao ano, positivo nas duas metades.
     Nas ações individuais, porém, foi negativo (-1,4% ao ano). Essa inconsistência pede cautela.
5. **Setups de reversão à média** (IFR2, Bollinger reversão, estocástico) e **padrões de candle** (inside bar, 123)
   não pagaram os custos nas ações.

## Metodologia

| Item | Premissa |
|---|---|
| Período | 07/11/2016 a 06/11/2026 (10 anos), mais 1 ano de aquecimento dos indicadores |
| Universo A | 44 ações líquidas do Ibovespa, com cotações ajustadas por proventos e desdobramentos (Yahoo Finance) |
| Universo B | Índice Ibovespa (negociável via BOVA11 ou WIN), **livre de viés de sobrevivência** |
| Carteira | Capital dividido igualmente entre os ativos, rebalanceado uma vez por ano. Cada ativo opera com 100% da sua fatia |
| Execução | Sinal no fechamento e execução no pregão seguinte: abertura, rompimento (ordem stop), stop ou alvo. Stop e alvo no mesmo candle contam como stop (premissa conservadora) |
| Custos | 0,10% por lado (emolumentos da B3 e *slippage*; corretagem zero) |
| Short | Espelho exato da lógica de compra. Aluguel (BTC) de 2% ao ano. A garantia rende CDI |
| Caixa | Dinheiro parado rende CDI (série 12 do BCB) |
| Parâmetros | Valores **clássicos de mercado, sem otimização**, para evitar *overfitting* |
| Excluídos | UGPA3 e JBSS32, por erro de ajuste nos dados (saltos falsos de +119% e +100%) |
| Validação | O simulador foi conferido com um cálculo independente (54 trades em PETR4, resultado idêntico) |

**Excesso sobre o CDI** é o retorno anual composto da carteira menos o CDI anual composto.
É a resposta à pergunta "valeu a pena em vez de deixar no CDI?".
Os resultados são **antes do IR**: 15% no swing e 20% no day trade, com isenção de R$ 20 mil por mês nas vendas de ações.

## Ranking A: 44 ações do Ibovespa

| # | Setup | Lado | Excesso s/ CDI (a.a.) | 2016–21 | 2021–26 | Queda máx. | Sharpe vs CDI | Trades | Acerto | Fator de lucro |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Buy & hold | Long | **+8,9%** | +21,5% | -3,0% | -45,1% | 0,46 | 44 | 89% | 133,78 |
| 2 | Cruzamento MME 9/21 | Long | **+8,1%** | +20,3% | -3,4% | -19,6% | 0,61 | 2332 | 34% | 1,83 |
| 3 | MACD cruzamento | Long | **+7,7%** | +15,6% | -0,1% | -12,9% | 0,61 | 4262 | 39% | 1,49 |
| 4 | Bollinger rompimento | Long | **+5,5%** | +13,1% | -2,0% | -16,5% | 0,57 | 2067 | 41% | 1,65 |
| 5 | Donchian 20/10 (Tartarugas) | Long | **+4,2%** | +12,4% | -3,8% | -19,2% | 0,39 | 2602 | 39% | 1,45 |
| 6 | Hilo Activator 8 | Long | **+4,0%** | +10,2% | -2,2% | -19,3% | 0,36 | 5071 | 37% | 1,33 |
| 7 | Donchian 55/20 (Tartarugas) | Long | **+2,9%** | +11,5% | -5,5% | -21,6% | 0,30 | 1315 | 36% | 1,55 |
| 8 | Cruzamento MMS 50/200 | Long | **+0,9%** | +7,6% | -5,8% | -37,8% | 0,13 | 341 | 41% | 1,90 |
| 9 | Momentum 6 meses | Long | **+0,5%** | +10,3% | -9,0% | -25,4% | 0,10 | 2314 | 33% | 1,47 |
| 10 | Estocástico lento 14,3 | Long | **-0,8%** | -1,3% | -0,3% | -18,3% | -0,04 | 3075 | 50% | 1,13 |
| 11 | ADX/DI 14 (ADX>25) | Long | **-0,9%** | -0,1% | -1,7% | -2,7% | -0,37 | 626 | 30% | 0,93 |
| 12 | IFR2 + filtro MMS200 | Long | **-1,0%** | +1,0% | -3,0% | -9,4% | -0,20 | 2822 | 63% | 1,01 |
| 13 | ADX/DI 14 (ADX>25) | Short | **-1,0%** | -1,0% | -0,9% | -3,8% | -0,22 | 834 | 30% | 0,75 |
| 14 | IFR2 (Connors) | Long | **-1,4%** | +1,0% | -3,9% | -25,9% | -0,08 | 5553 | 63% | 1,05 |
| 15 | Setup 9.1 (Larry Williams) | Long | **-1,4%** | +2,8% | -5,6% | -18,3% | -0,04 | 6983 | 29% | 1,12 |
| 16 | Pullback na MME21 | Long | **-1,6%** | -0,5% | -2,8% | -3,4% | -0,43 | 2691 | 38% | 0,98 |
| 17 | IFR2 + filtro MMS200 | Short | **-2,3%** | -1,3% | -3,3% | -6,3% | -0,69 | 1762 | 58% | 0,74 |
| 18 | Setup 123 | Long | **-2,7%** | +1,3% | -6,7% | -12,2% | -0,27 | 4759 | 42% | 1,02 |
| 19 | Bollinger rompimento | Short | **-2,7%** | -1,1% | -4,3% | -15,6% | -0,22 | 1672 | 33% | 0,80 |
| 20 | Bollinger reversão | Long | **-2,7%** | -3,7% | -1,7% | -36,3% | -0,17 | 1784 | 64% | 1,00 |
| 21 | Pullback na MME21 | Short | **-4,1%** | -4,1% | -4,1% | -14,2% | -1,00 | 2287 | 31% | 0,73 |
| 22 | Inside bar | Short | **-4,5%** | -4,9% | -4,1% | -10,8% | -1,33 | 3128 | 30% | 0,70 |
| 23 | Inside bar | Long | **-4,6%** | -3,8% | -5,4% | -4,1% | -1,54 | 4178 | 33% | 0,78 |
| 24 | Donchian 55/20 (Tartarugas) | Short | **-5,9%** | -5,0% | -7,0% | -19,9% | -0,54 | 1069 | 25% | 0,51 |
| 25 | IFR2 (Connors) | Short | **-6,3%** | -5,9% | -6,8% | -11,8% | -0,93 | 6430 | 59% | 0,78 |
| 26 | Cruzamento MME 9/21 | Short | **-7,5%** | -7,1% | -7,9% | -27,2% | -0,54 | 2322 | 26% | 0,64 |
| 27 | Setup 123 | Short | **-8,1%** | -8,0% | -8,3% | -28,6% | -0,79 | 3600 | 35% | 0,71 |
| 28 | Donchian 20/10 (Tartarugas) | Short | **-8,4%** | -8,3% | -8,6% | -26,0% | -0,71 | 2369 | 29% | 0,62 |
| 29 | MACD cruzamento | Short | **-9,5%** | -12,4% | -6,3% | -35,4% | -0,65 | 4240 | 31% | 0,70 |
| 30 | Bollinger reversão | Short | **-9,8%** | -13,1% | -6,1% | -35,3% | -1,03 | 2373 | 56% | 0,59 |
| 31 | Momentum 6 meses | Short | **-11,2%** | -10,4% | -12,0% | -37,6% | -0,96 | 2316 | 26% | 0,34 |
| 32 | Estocástico lento 14,3 | Short | **-11,3%** | -17,1% | -4,8% | -48,5% | -1,16 | 3676 | 38% | 0,60 |
| 33 | Cruzamento MMS 50/200 | Short | **-11,5%** | -14,0% | -8,8% | -40,4% | -0,93 | 355 | 14% | 0,13 |
| 34 | Hilo Activator 8 | Short | **-11,7%** | -15,5% | -7,5% | -45,6% | -0,82 | 5056 | 30% | 0,65 |
| 35 | Setup 9.1 (Larry Williams) | Short | **-12,9%** | -16,7% | -8,7% | -47,0% | -1,01 | 6905 | 24% | 0,63 |

> ⚠️ **Viés de sobrevivência.** As 44 ações são as grandes de **hoje**. Por isso o comprar e segurar delas rendeu
> +8,9% ao ano sobre o CDI, enquanto o Ibovespa rendeu só +1,3%. Esse viés **infla os setups comprados e pune os vendidos**.
> Por isso o ranking B, no Ibovespa, é o teste mais honesto.

## Ranking B: Ibovespa (sem viés de sobrevivência)

| # | Setup | Lado | Excesso s/ CDI (a.a.) | 2016–21 | 2021–26 | Queda máx. | Sharpe vs CDI | Trades | Acerto | Fator de lucro |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | MACD cruzamento | Long | **+6,5%** | +10,5% | +2,5% | -16,5% | 0,49 | 85 | 44% | 1,93 |
| 2 | Setup 9.1 (Larry Williams) | Long | **+5,7%** | +9,5% | +1,8% | -13,1% | 0,44 | 153 | 33% | 1,69 |
| 3 | Bollinger rompimento | Long | **+2,5%** | +7,0% | -2,2% | -15,6% | 0,26 | 38 | 53% | 2,03 |
| 4 | Donchian 20/10 (Tartarugas) | Long | **+2,4%** | +4,4% | +0,4% | -20,4% | 0,24 | 62 | 45% | 1,72 |
| 5 | Donchian 55/20 (Tartarugas) | Long | **+2,4%** | +9,1% | -4,3% | -17,2% | 0,24 | 31 | 52% | 2,39 |
| 6 | Estocástico lento 14,3 | Long | **+1,6%** | +1,1% | +2,2% | -19,6% | 0,18 | 72 | 44% | 1,51 |
| 7 | Inside bar | Short | **+1,3%** | +2,0% | +0,7% | -17,3% | 0,18 | 58 | 36% | 1,26 |
| 8 | Buy & hold | Long | **+1,3%** | +5,4% | -2,8% | -46,8% | 0,17 | 1 | 100% | – |
| 9 | Cruzamento MME 9/21 | Long | **+0,6%** | +6,2% | -5,1% | -16,8% | 0,11 | 55 | 38% | 1,67 |
| 10 | IFR2 + filtro MMS200 | Long | **+0,5%** | +4,8% | -3,9% | -9,2% | 0,10 | 79 | 63% | 1,30 |
| 11 | Bollinger reversão | Long | **+0,2%** | -5,3% | +6,3% | -40,7% | 0,09 | 49 | 78% | 1,54 |
| 12 | ADX/DI 14 (ADX>25) | Long | **-0,6%** | -1,6% | +0,4% | -7,2% | -0,10 | 19 | 32% | 1,14 |
| 13 | Inside bar | Long | **-0,8%** | +0,5% | -2,2% | -9,2% | -0,09 | 95 | 39% | 1,02 |
| 14 | Setup 123 | Long | **-1,1%** | -1,3% | -0,9% | -12,0% | -0,05 | 109 | 42% | 1,16 |
| 15 | Hilo Activator 8 | Long | **-1,7%** | +1,1% | -4,6% | -23,1% | -0,04 | 119 | 34% | 1,23 |
| 16 | IFR2 + filtro MMS200 | Short | **-2,7%** | +0,2% | -5,7% | -11,0% | -0,45 | 31 | 48% | 0,49 |
| 17 | ADX/DI 14 (ADX>25) | Short | **-2,9%** | -3,3% | -2,5% | -10,3% | -0,51 | 23 | 13% | 0,05 |
| 18 | Pullback na MME21 | Long | **-3,5%** | -3,7% | -3,2% | -7,9% | -0,51 | 51 | 33% | 0,71 |
| 19 | Pullback na MME21 | Short | **-3,6%** | -5,9% | -1,1% | -11,6% | -0,50 | 46 | 33% | 0,61 |
| 20 | MACD cruzamento | Short | **-3,7%** | -2,7% | -4,7% | -24,2% | -0,14 | 84 | 31% | 0,76 |
| 21 | IFR2 (Connors) | Long | **-3,9%** | -2,7% | -5,2% | -31,9% | -0,21 | 121 | 62% | 0,90 |
| 22 | Donchian 55/20 (Tartarugas) | Short | **-4,3%** | -0,8% | -7,8% | -22,5% | -0,30 | 27 | 22% | 0,51 |
| 23 | Momentum 6 meses | Long | **-4,8%** | +1,7% | -11,3% | -28,5% | -0,21 | 44 | 25% | 1,31 |
| 24 | Setup 123 | Short | **-4,8%** | -2,0% | -7,7% | -14,5% | -0,47 | 65 | 32% | 0,62 |
| 25 | Bollinger rompimento | Short | **-5,3%** | -0,5% | -10,1% | -14,9% | -0,36 | 46 | 20% | 0,54 |
| 26 | Setup 9.1 (Larry Williams) | Short | **-5,4%** | -3,6% | -7,2% | -21,9% | -0,29 | 153 | 24% | 0,74 |
| 27 | Estocástico lento 14,3 | Short | **-6,3%** | -13,4% | +1,9% | -38,9% | -0,41 | 78 | 40% | 0,54 |
| 28 | Donchian 20/10 (Tartarugas) | Short | **-8,0%** | -8,3% | -7,8% | -32,4% | -0,53 | 62 | 16% | 0,51 |
| 29 | Cruzamento MME 9/21 | Short | **-8,2%** | -7,0% | -9,4% | -35,7% | -0,47 | 55 | 18% | 0,50 |
| 30 | Bollinger reversão | Short | **-8,5%** | -9,8% | -7,1% | -35,7% | -0,68 | 44 | 45% | 0,44 |
| 31 | Cruzamento MMS 50/200 | Long | **-9,2%** | -5,3% | -13,2% | -47,9% | -0,35 | 8 | 50% | 0,83 |
| 32 | Momentum 6 meses | Short | **-10,5%** | -7,0% | -14,0% | -36,7% | -0,67 | 44 | 16% | 0,09 |
| 33 | Hilo Activator 8 | Short | **-11,1%** | -11,4% | -10,9% | -43,2% | -0,62 | 119 | 27% | 0,49 |
| 34 | IFR2 (Connors) | Short | **-11,6%** | -7,9% | -15,5% | -28,3% | -1,17 | 153 | 48% | 0,46 |
| 35 | Cruzamento MMS 50/200 | Short | **-17,0%** | -17,6% | -16,4% | -63,0% | -1,08 | 9 | 0% | 0,00 |

## Leitura técnica

- **Comprado contra vendido.** A bolsa brasileira subiu no período (o Ibovespa rendeu cerca de 10% ao ano) e o short paga o
  aluguel e perde os dias de alta. Setups vendidos só funcionariam como **hedge** em quedas fortes, não como fonte de lucro.
- **Tendência contra reversão.** Na B3, seguir tendência no lado comprado superou a reversão à média. Isso contraria a
  popularidade do IFR2 no mercado brasileiro: com os custos incluídos, ele perdeu para o CDI nas ações e no Ibovespa.
- **Regime de juros.** De 2021 a 2026, com a Selic subindo de cerca de 8% para 15% ao ano, praticamente todos os setups ficaram **abaixo do CDI**.
  Com Selic alta, o custo de oportunidade derruba o swing trade.
- **O ganho dos setups de tendência é de risco, não de retorno.** O MACD comprado nas ações rendeu perto do comprar e segurar
  (+7,7% contra +8,9% ao ano), mas com queda máxima de -13% contra -45%.

## Limitações

1. Os dados do Yahoo podem ter falhas pontuais. Antes de uma decisão com dinheiro, valide com dados da B3 ou de um fornecedor profissional.
2. As premissas de execução são diárias. O *slippage* real em papéis menos líquidos pode ser maior.
3. Não houve otimização de parâmetros. Valores otimizados ficariam melhores no papel e piores na vida real.
4. Foram 34 testes. Pela estatística, é esperado que algum pareça bom só por sorte.
5. Resultado passado não garante resultado futuro. Isto não é recomendação de investimento.

## Como reproduzir

```bash
python pesquisa/baixar.py          # baixa cotações ajustadas + CDI (BCB)
python pesquisa/rodar.py           # roda os 34 testes + Ibovespa (~10 s)
python pesquisa/gerar_relatorio.py # gera este relatório
```
Os resultados completos estão em `relatorios/ranking_setups.csv` e as curvas de patrimônio em `relatorios/curvas_patrimonio.csv`.
