# Treino do swing trade — walk-forward

Gerado em 2026-10-26 com 148 ativos do IBRA, pregões de 2001 a 2026 (preços ajustados por proventos).
Treino de 8 anos, teste nos 2 seguintes, de 2 em 2 anos. Custos de 0,03% por perna, 0,05% de escorregamento nas ordens stop, aluguel de 2% a.a. no vendido.

## Fora da amostra: padrão atual × treinado

| setup | lado | padrão: n | padrão: acerto | padrão: R médio | treinado: n | treinado: acerto | treinado: R médio | treinado: t | fator de lucro | status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| bandeira_alta | compra | 4759 | 40,9% | 0,038 | 4425 | 52,3% | 0,148 | 9,31 | 1,40 | **ATIVO** |
| retomou_mm20 | compra | 11618 | 45,1% | 0,046 | 9538 | 40,3% | 0,145 | 7,93 | 1,25 | **ATIVO** |
| rompimento_20d | compra | 10829 | 49,8% | 0,092 | 10672 | 52,7% | 0,119 | 12,20 | 1,31 | **ATIVO** |
| sobrevendido | compra | 3881 | 33,0% | -0,113 | 780 | 51,8% | 0,021 | 0,80 | 1,07 | desativado |
| repique | compra | 3377 | 39,4% | 0,001 | 597 | 35,2% | -0,133 | -2,35 | 0,78 | desativado |
| perdeu_mm20 | venda | 11390 | 41,2% | -0,099 | 2745 | 47,2% | 0,005 | 0,29 | 1,01 | desativado |
| repique_baixa | venda | 5984 | 30,9% | -0,243 | 1247 | 42,7% | -0,045 | -1,31 | 0,92 | desativado |
| perdeu_20d | venda | 8951 | 44,0% | -0,077 | 2280 | 48,6% | -0,056 | -4,00 | 0,82 | desativado |
| bandeira_baixa | venda | 2800 | 36,8% | -0,065 | 930 | 34,2% | -0,232 | -7,48 | 0,57 | desativado |
| sobrecomprado | venda | 7032 | 24,9% | -0,374 | 0 | - | - | - | - | desativado |

## Parâmetros adotados (treino nos 10 anos mais recentes)

| setup | parâmetros | n treino | acerto | R médio | t | pregões |
|---|---|---:|---:|---:|---:|---:|
| bandeira_alta | abertura, stop atr:3, alvo 2R, 15 pregões, filtro tendencia | 3038 | 55,8% | 0,146 | 9,34 | 13,7 |
| retomou_mm20 | abertura, stop atr:2, sem alvo, 30 pregões, filtro nenhum | 7949 | 39,4% | 0,183 | 9,28 | 19,9 |
| rompimento_20d | abertura, stop atr:3, alvo 3R, 20 pregões, filtro nenhum | 7440 | 52,0% | 0,150 | 12,01 | 17,3 |

## Carteira fora da amostra (setups ativos, combo escolhido em cada janela)

24643 operações, 3.312,7 R no total, maior queda acumulada de 900,5 R, 10 de 18 anos positivos.

| ano | operações | acerto | R |
|---|---:|---:|---:|
| 2009 | 511 | 64,0% | 227,0 |
| 2010 | 602 | 40,9% | -43,3 |
| 2011 | 278 | 38,8% | -44,3 |
| 2012 | 560 | 51,8% | 106,5 |
| 2013 | 771 | 43,3% | -23,0 |
| 2014 | 932 | 45,3% | -14,2 |
| 2015 | 801 | 45,8% | -28,0 |
| 2016 | 1167 | 56,5% | 251,6 |
| 2017 | 1595 | 53,7% | 363,5 |
| 2018 | 1747 | 50,6% | 584,3 |
| 2019 | 1846 | 58,8% | 723,3 |
| 2020 | 1872 | 52,2% | 380,6 |
| 2021 | 2003 | 36,4% | -173,8 |
| 2022 | 2296 | 35,6% | -198,2 |
| 2023 | 1855 | 51,9% | 505,0 |
| 2024 | 1852 | 34,6% | -373,1 |
| 2025 | 2163 | 54,5% | 643,3 |
| 2026 | 1792 | 49,9% | 425,5 |

## Carteira realista fora da amostra

Até 5 posições, um ativo por vez, sem alavancagem, risco fixo por operação sobre o patrimônio, sinais do mesmo pregão em ordem de menor volatilidade (ATR %); o caixa livre rende CDI.

| cenário | operações | acerto | R médio | retorno ao ano | maior queda | anos positivos |
|---|---:|---:|---:|---:|---:|---:|
| skill antes do treino (padrão, 10 setups, 1% de risco) | 2238 | 42,4% | -0,039 | -0,9% | 47,6% | 5 de 18 |
| treinada, risco 0.5%, máx. 5 posições | 1314 | 50,5% | 0,133 | 11,1% | 8,5% | 17 de 18 |
| treinada, risco 1%, máx. 5 posições | 1314 | 50,5% | 0,133 | 11,2% | 15,4% | 15 de 18 |
| Ibovespa (pontos, sem proventos) | - | - | - | 9,0% | 48,6% | - |
| CDI | - | - | - | 9,9% | 0,0% | - |

## Excesso de ajuste

Escolhendo a melhor combinação olhando o período inteiro (retrospecto) o resultado parece melhor do que o walk-forward entrega. A diferença é o quanto a otimização se engana sozinha:

| setup | retrospecto: R médio | fora da amostra: R médio |
|---|---:|---:|
| bandeira_alta | 0,172 | 0,148 |
| bandeira_baixa | - | -0,232 |
| perdeu_20d | - | -0,056 |
| perdeu_mm20 | - | 0,005 |
| repique | 0,149 | -0,133 |
| repique_baixa | - | -0,045 |
| retomou_mm20 | 0,186 | 0,145 |
| rompimento_20d | 0,191 | 0,119 |
| sobrecomprado | - | - |
| sobrevendido | 0,051 | 0,021 |

## Janelas do walk-forward

**bandeira_alta** (compra)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | gatilho, stop atr:3, alvo 1R, 15 pregões, filtro regime | 214 | 0,187 |
| 2003-2010 | 2011-2012 | abertura, stop atr:3, alvo 1R, 20 pregões, filtro tendencia | 271 | 0,044 |
| 2005-2012 | 2013-2014 | abertura, stop atr:3, alvo 1R, 30 pregões, filtro tendencia | 252 | -0,147 |
| 2007-2014 | 2015-2016 | abertura, stop atr:3, alvo 3R, 30 pregões, filtro nenhum | 371 | 0,340 |
| 2009-2016 | 2017-2018 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro nenhum | 523 | 0,309 |
| 2011-2018 | 2019-2020 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro nenhum | 743 | 0,409 |
| 2013-2020 | 2021-2022 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro nenhum | 819 | -0,102 |
| 2015-2022 | 2023-2024 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro tendencia | 542 | 0,090 |
| 2017-2024 | 2025-2026 | abertura, stop atr:3, alvo 3R, 15 pregões, filtro tendencia | 690 | 0,121 |

**bandeira_baixa** (venda)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | gatilho, stop swing:10, alvo 3R, 15 pregões, filtro nenhum | 70 | -0,377 |
| 2003-2010 | 2011-2012 | nenhuma passou | 0 | - |
| 2005-2012 | 2013-2014 | nenhuma passou | 0 | - |
| 2007-2014 | 2015-2016 | nenhuma passou | 0 | - |
| 2009-2016 | 2017-2018 | nenhuma passou | 0 | - |
| 2011-2018 | 2019-2020 | abertura, stop swing:10, alvo 1.5R, 10 pregões, filtro tendencia | 206 | -0,307 |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | nenhuma passou | 0 | - |
| 2017-2024 | 2025-2026 | abertura, stop atr:2, alvo 1.5R, 15 pregões, filtro nenhum | 654 | -0,193 |

**perdeu_20d** (venda)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | abertura, stop swing:5, alvo 1R, 10 pregões, filtro nenhum | 597 | -0,165 |
| 2003-2010 | 2011-2012 | nenhuma passou | 0 | - |
| 2005-2012 | 2013-2014 | nenhuma passou | 0 | - |
| 2007-2014 | 2015-2016 | nenhuma passou | 0 | - |
| 2009-2016 | 2017-2018 | nenhuma passou | 0 | - |
| 2011-2018 | 2019-2020 | nenhuma passou | 0 | - |
| 2013-2020 | 2021-2022 | abertura, stop atr:3, alvo 1R, 10 pregões, filtro regime | 1683 | -0,018 |
| 2015-2022 | 2023-2024 | nenhuma passou | 0 | - |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

**perdeu_mm20** (venda)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | nenhuma passou | 0 | - |
| 2003-2010 | 2011-2012 | abertura, stop swing:3, alvo 2R, 5 pregões, filtro tendencia | 615 | 0,097 |
| 2005-2012 | 2013-2014 | abertura, stop swing:3, alvo 2R, 5 pregões, filtro tendencia | 791 | 0,072 |
| 2007-2014 | 2015-2016 | abertura, stop swing:3, alvo 1.5R, 5 pregões, filtro tendencia | 749 | -0,054 |
| 2009-2016 | 2017-2018 | abertura, stop swing:3, alvo 3R, 5 pregões, filtro tendencia | 590 | -0,104 |
| 2011-2018 | 2019-2020 | nenhuma passou | 0 | - |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | nenhuma passou | 0 | - |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

**repique** (compra)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro regime | 56 | -0,039 |
| 2003-2010 | 2011-2012 | abertura, stop atr:3, alvo 2R, 30 pregões, filtro regime | 40 | -0,272 |
| 2005-2012 | 2013-2014 | nenhuma passou | 0 | - |
| 2007-2014 | 2015-2016 | nenhuma passou | 0 | - |
| 2009-2016 | 2017-2018 | nenhuma passou | 0 | - |
| 2011-2018 | 2019-2020 | nenhuma passou | 0 | - |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | gatilho, stop atr:2, sem alvo, 30 pregões, filtro nenhum | 501 | -0,133 |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

**repique_baixa** (venda)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | abertura, stop swing:10, alvo 1.5R, 5 pregões, filtro nenhum | 625 | 0,022 |
| 2003-2010 | 2011-2012 | abertura, stop swing:10, alvo 2R, 5 pregões, filtro nenhum | 597 | -0,087 |
| 2005-2012 | 2013-2014 | nenhuma passou | 0 | - |
| 2007-2014 | 2015-2016 | nenhuma passou | 0 | - |
| 2009-2016 | 2017-2018 | nenhuma passou | 0 | - |
| 2011-2018 | 2019-2020 | nenhuma passou | 0 | - |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | abertura, stop atr:1.5, alvo 1.5R, 5 pregões, filtro ambos | 25 | -0,697 |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

**retomou_mm20** (compra)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | gatilho, stop swing:3, alvo 2R, 15 pregões, filtro regime | 528 | 0,043 |
| 2003-2010 | 2011-2012 | gatilho, stop atr:2, alvo 2R, 30 pregões, filtro regime | 218 | 0,114 |
| 2005-2012 | 2013-2014 | abertura, stop swing:3, alvo 1.5R, 30 pregões, filtro tendencia | 677 | -0,023 |
| 2007-2014 | 2015-2016 | abertura, stop swing:3, alvo 1R, 20 pregões, filtro tendencia | 717 | 0,004 |
| 2009-2016 | 2017-2018 | abertura, stop swing:3, sem alvo, 30 pregões, filtro nenhum | 1245 | 0,471 |
| 2011-2018 | 2019-2020 | abertura, stop swing:10, sem alvo, 30 pregões, filtro nenhum | 1385 | 0,256 |
| 2013-2020 | 2021-2022 | abertura, stop swing:10, sem alvo, 30 pregões, filtro nenhum | 1931 | -0,113 |
| 2015-2022 | 2023-2024 | gatilho, stop swing:10, sem alvo, 30 pregões, filtro nenhum | 1485 | -0,006 |
| 2017-2024 | 2025-2026 | gatilho, stop swing:10, sem alvo, 30 pregões, filtro nenhum | 1352 | 0,468 |

**rompimento_20d** (compra)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | abertura, stop swing:10, sem alvo, 30 pregões, filtro regime | 422 | 0,277 |
| 2003-2010 | 2011-2012 | abertura, stop swing:10, sem alvo, 20 pregões, filtro regime | 384 | 0,188 |
| 2005-2012 | 2013-2014 | abertura, stop swing:10, alvo 1.5R, 10 pregões, filtro regime | 710 | -0,046 |
| 2007-2014 | 2015-2016 | abertura, stop swing:10, alvo 1.5R, 20 pregões, filtro nenhum | 918 | 0,170 |
| 2009-2016 | 2017-2018 | abertura, stop swing:5, alvo 1R, 30 pregões, filtro nenhum | 1645 | 0,210 |
| 2011-2018 | 2019-2020 | abertura, stop swing:10, alvo 1R, 30 pregões, filtro nenhum | 1667 | 0,185 |
| 2013-2020 | 2021-2022 | abertura, stop atr:3, alvo 1.5R, 30 pregões, filtro nenhum | 1485 | -0,080 |
| 2015-2022 | 2023-2024 | abertura, stop atr:3, alvo 1.5R, 30 pregões, filtro nenhum | 1577 | 0,036 |
| 2017-2024 | 2025-2026 | abertura, stop atr:3, alvo 1.5R, 20 pregões, filtro nenhum | 1864 | 0,195 |

**sobrecomprado** (venda)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | nenhuma passou | 0 | - |
| 2003-2010 | 2011-2012 | nenhuma passou | 0 | - |
| 2005-2012 | 2013-2014 | nenhuma passou | 0 | - |
| 2007-2014 | 2015-2016 | nenhuma passou | 0 | - |
| 2009-2016 | 2017-2018 | nenhuma passou | 0 | - |
| 2011-2018 | 2019-2020 | nenhuma passou | 0 | - |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | nenhuma passou | 0 | - |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

**sobrevendido** (compra)

| treino | teste | combinação escolhida | teste: n | teste: R médio |
|---|---|---|---:|---:|
| 2001-2008 | 2009-2010 | abertura, stop atr:2, alvo 1R, 5 pregões, filtro nenhum | 134 | 0,159 |
| 2003-2010 | 2011-2012 | abertura, stop atr:2, alvo 1R, 5 pregões, filtro nenhum | 438 | -0,014 |
| 2005-2012 | 2013-2014 | abertura, stop atr:2, alvo 1R, 30 pregões, filtro tendencia | 44 | 0,352 |
| 2007-2014 | 2015-2016 | abertura, stop atr:2, alvo 1R, 30 pregões, filtro tendencia | 34 | 0,009 |
| 2009-2016 | 2017-2018 | abertura, stop atr:3, alvo 1.5R, 5 pregões, filtro tendencia | 63 | -0,009 |
| 2011-2018 | 2019-2020 | abertura, stop atr:3, alvo 1R, 5 pregões, filtro tendencia | 67 | -0,214 |
| 2013-2020 | 2021-2022 | nenhuma passou | 0 | - |
| 2015-2022 | 2023-2024 | nenhuma passou | 0 | - |
| 2017-2024 | 2025-2026 | nenhuma passou | 0 | - |

## Limites

- Viés de sobrevivência: o universo é a carteira atual do IBRA; empresas que quebraram ou saíram do índice não estão nos dados, o que favorece o comprado.
- R por operação, sem limite de posições simultâneas nem de caixa.
- Dados gratuitos do Yahoo; o gatilho e o stop usam 0,05% além da máxima/mínima.
- Resultado passado não garante resultado futuro. Não é recomendação de investimento.

## Day trade (ORB) — avaliação curta, sem mudança de parâmetros

O Yahoo só guarda 60 dias de candles de 5 minutos, então o ORB não pode ser
treinado como o swing. Avaliação em 148 ativos do IBRA, 56 pregões
(30/07/2026 a 23/10/2026), custos de 0,03% por perna, saída até 16h45:

| variante | metade 1: R médio | metade 2 (teste): n | acerto | R médio | t por dia |
|---|---:|---:|---:|---:|---:|
| padrão (faixa 15 min, stop no meio, 2R) | +0,016 | 1.949 | 40,0% | −0,039 | −1,36 |
| melhor da metade 1 (faixa 30 min, stop no meio, 3R) | +0,132 | 1.716 | 44,2% | +0,070 | −0,33 |

Medido por dia (os ativos rompem juntos nos dias de alta geral), nenhuma
variante teve significância positiva: o ganho aparente vem de poucos dias. Os
parâmetros do day trade NÃO foram alterados; trate o ORB como experimental e
reavalie quando houver mais histórico de 5 minutos acumulado.
