# Estudo: setups de swing trade na B3, comprado e vendido (nov/2016 a nov/2026)

## Resposta curta

1. **Nenhum setup é lucrativo de forma confiável quando comparado ao CDI** ({{CDI}} ao ano no período).
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

{{TABELA_ACOES}}

> ⚠️ **Viés de sobrevivência.** As 44 ações são as grandes de **hoje**. Por isso o comprar e segurar delas rendeu
> +8,9% ao ano sobre o CDI, enquanto o Ibovespa rendeu só +1,3%. Esse viés **infla os setups comprados e pune os vendidos**.
> Por isso o ranking B, no Ibovespa, é o teste mais honesto.

## Ranking B: Ibovespa (sem viés de sobrevivência)

{{TABELA_IBOV}}

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
