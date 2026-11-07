# Benchmarking: plataformas de análise e trading (engenharia reversa funcional)

Analisamos **o que** os sistemas líderes entregam ao usuário (funcionalidades, fluxo, densidade de informação)
para decidir as ferramentas do painel. Nada de código, marca ou identidade visual foi copiado. O painel tem identidade própria.

## Sistemas analisados

| Sistema | Público | Pontos fortes (o que vale a pena trazer) |
|---|---|---|
| **Bloomberg Terminal** | Institucional | Painel de carteira com risco e atribuição, *screener* de ações com qualquer critério, notícias integradas, alta densidade de dados, atalhos de teclado |
| **TradingView** | Varejo e profissional | Gráfico de referência no mercado, indicadores sobrepostos, testador de estratégias, alertas, *screener* |
| **Profit Pro/Ultra (Nelogica)** | Trader B3 | Rastreador de setups em tempo real, boleta rápida, book e *times & trades*, estratégias automatizadas, *replay* |
| **Koyfin** | Investidor avançado | Dashboards configuráveis, comparação de ativos, gráficos de fundamentos, visual limpo |
| **Status Invest / Investidor10** | Investidor B3 | Rankings por indicador (DY, P/L, ROE), histórico de proventos, carteira com dividendos |
| **TradeMap** | Investidor B3 | Consolidação da carteira, rentabilidade contra benchmarks, cotações e notícias |
| **Interactive Brokers (TWS)** | Trader global | *Risk Navigator*: exposição, cenários e concentração; dezenas de tipos de ordem; fila de ordens |
| **TrendSpider / Tickeron / Danelfin** | Varejo com IA | Detecção automática de padrões, *score* de IA por ativo e explicação dos motivos |

## Matriz: o que o painel entrega

| Ferramenta | Inspiração funcional | No painel | Observação |
|---|---|---|---|
| KPIs da carteira (patrimônio, P&L, exposição, risco em stop) | Bloomberg, TradeMap | ✅ | Comparado com o CDI |
| Gráfico profissional com MMs, MACD, volume e sinais marcados | TradingView, Profit | ✅ | TradingView Lightweight Charts (código aberto, Apache 2.0) |
| *Screener*/ranking por fatores (DY, momentum, volatilidade) | Status Invest, Koyfin, Bloomberg | ✅ | Os fatores que **venceram** no nosso estudo de 10 anos |
| Rastreador de setups (MACD, 9.1, IFR2, tendência) | Profit, TrendSpider | ✅ | Cada sinal mostra a **evidência histórica** do setup (diferencial) |
| Carteira-alvo e ordens de rebalanceamento | Ferramentas de *robo-advisor* | ✅ | Estratégia de dividendos e mix com momentum |
| Analista de IA: leitura de mercado e ideias de operação | Danelfin, Bloomberg | ✅ | Claude, baseado **somente** em dados quantitativos fornecidos |
| Assistente de IA conversacional com notícias da web | Bloomberg, IBKR | ✅ | Pesquisa na web opcional |
| Gestão de risco (concentração, risco aberto, *kill switch*) | IBKR Risk Navigator | ✅ | Integrado às travas do robô |
| Laboratório de backtests | TradingView, Profit | ✅ | Os 34 setups e os fatores, com curvas contra CDI e Ibovespa |
| Fila de ordens e execução no Home Broker | IBKR, Profit | ✅ | Via robô Playwright, com confirmação humana |
| Apuração de IR e DARF | **Nenhum dos grandes faz bem** | ✅ | Diferencial brasileiro |
| Book de ofertas e *times & trades* | Profit, Tryd | ❌ | Exige feed da B3 em tempo real (pago). A Clear não oferece API |
| Cotação em tempo real | Todos | ⚠️ | Yahoo com atraso. Para tempo real, use o Profit da Clear |

## Princípios de design adotados
1. **Densidade com hierarquia**, como no Bloomberg: muitos dados, mas os KPIs e as decisões vêm primeiro.
2. **Cor com significado**: verde e vermelho só para resultado. A cor de destaque é usada para ação.
3. **Fonte tabular nos números**, para alinhar valores em tabelas.
4. **Toda ideia de operação vem com a evidência histórica e o risco**: entrada, stop e quanto se perde se der errado.
5. **A IA explica e não decide**: a execução sempre passa pela fila e pela confirmação humana.
