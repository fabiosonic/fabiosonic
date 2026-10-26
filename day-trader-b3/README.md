# day-trader-b3

Catorze skills do Claude para **day trade e swing trade, comprado ou vendido**, na
**bolsa brasileira (B3)**. É uma
adaptação do [day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill),
de Jake Schincariol (MIT), refeita para o pregão, os dados públicos e a
tributação do Brasil.

> Não é recomendação de investimento. A maioria das pessoas que faz day trade
> perde dinheiro. As ferramentas leem dados públicos e fazem contas; nenhuma
> envia ordem. Comece pela conta simulada da sua corretora.

## As skills

| Comando | O que faz | Fonte |
|---|---|---|
| `/b3-scanner` | Universo do IBRA/IBXX/IBOV, setups diários (rompimento de 20 pregões, bandeira, MM20, IFR) e ORB de 5 min | B3 (carteira do índice), Yahoo |
| `/b3-noticias` | Fatos relevantes, comunicados e avisos da CVM com link, variação do dia e manchetes | CVM (IPE), Yahoo, Google Notícias |
| `/b3-entrada` | Cronometra a entrada candle a candle (ORB ou nível) dentro da janela de entradas | Yahoo |
| `/b3-saida` | Stop (faixa, preço, %, ATR) e alvo em R, horário de zerar | — |
| `/b3-maquina-do-tempo` | 10.000 simulações do resto do pregão + a regra nos pregões passados | Yahoo (60 dias, 5 min) |
| `/b3-backtest` | Treina o swing no histórico diário desde 2000 (IBRA + Ibovespa): 10 setups × 1.200 combinações, walk-forward 8+2 anos, carteira realista com CDI; grava os parâmetros que as outras skills usam | Yahoo (diário desde 2000), BCB (CDI) |
| `/b3-swing` | Swing trade comprado ou vendido: plano com gatilho, stop swing/ATR, alvo em R e prazo; 10.000 caminhos diários com gap e aluguel; histórico da regra; acompanhamento das posições | Yahoo (2 anos, diário) |
| `/b3-orcamento` | Quantidade pela perda máxima com custos; lote padrão + fracionário | — |
| `/b3-risco` | APROVADA/BLOQUEADA: perdas, caixa, horário, feriado, lote, duplicidade... | — |
| `/b3-boleta` | Boleta para digitar no home broker, sim explícito, execuções e zeragem | — |
| `/b3-alertas` | Relógio da B3, cotações e alertas de preço, abertura e zerar | Yahoo |
| `/b3-analista` | Receita, EBIT, lucro, margens e crescimento por trimestre | CVM (ITR/DFP) |
| `/b3-insiders` | Compras e vendas de administradores e controladores (Res. CVM 44, art. 11) | CVM (VLMO) |
| `/b3-fiscal` | Separa day trade de operação comum e apura IR/DARF 6015 com a skill `traders` | — |

Fluxo de day trade (só comprado, zera no dia):

```
b3-scanner orb -> b3-noticias -> b3-entrada -> b3-saida -> b3-maquina-do-tempo
               -> b3-orcamento -> b3-risco -> b3-boleta (seu "sim") -> b3-alertas
```

Fluxo de swing trade (comprado ou vendido, alguns pregões):

```
b3-scanner diario [--lado venda] -> b3-swing plano -> b3-swing simular
    -> b3-orcamento -> b3-risco -> b3-boleta (seu "sim") -> b3-alertas from-plan
    -> todo dia: b3-swing acompanhar (stop, alvo, prazo, aluguel, mover-stop)
```

Fim do mês: `b3-fiscal apurar` → DARF 6015 (day trade 20%, swing 15%; venda a
descoberto apurada no mês da recompra).

### Treino no histórico (b3-backtest)

Último treino (resumo de `b3-backtest/RELATORIO.md`), fora da amostra
2009–2026, carteira de até 5 posições com CDI no caixa livre:

| | acerto | retorno ao ano | maior queda | anos positivos |
|---|---:|---:|---:|---:|
| skill antes do treino (padrão, 10 setups) | 42,4% | −0,9% | 47,6% | 5 de 18 |
| treinada, risco 0,5% por operação | 50,5% | 11,1% | 8,5% | 17 de 18 |
| treinada, risco 1% por operação | 50,5% | 11,2% | 15,4% | 15 de 18 |
| CDI | – | 9,9% | 0% | – |
| Ibovespa (retorno total) | – | 9,0% | 48,6% | – |

Ficaram ativos só setups de compra a favor da tendência; nenhum de venda teve
vantagem. Resultado passado, com viés de sobrevivência; não é promessa.

O day trade (ORB) só tem 60 dias de candles de 5 minutos no Yahoo: na
avaliação de 56 pregões no IBRA nenhuma variante teve vantagem confiável
(detalhes no relatório). Os parâmetros do day trade não mudaram; trate-o como
experimental.

### Vendido (venda a descoberto)

Desligado por padrão: ligue `"permitir_vendido": true` no config. O pacote
trata o vendido como a B3 exige: só lote padrão (`vendido_somente_lote`),
aluguel (BTC) estimado em `aluguel_taxa_aa_pct` somado à perda no stop,
garantia (`garantia_vendido_pct` do valor vendido) checada contra o caixa
livre, teto de exposição vendida (`max_exposicao_vendida_pct`) e carteira com
quantidade negativa. A perda no vendido não tem teto teórico, e o doador pode
pedir as ações de volta (recall).

As skills conversam por arquivos na pasta `trader-b3/` do diretório atual
(mude com a variável `B3_DIR`): `watchlist.json`, `entrada.json`,
`plano.json`, `ordens.json`, `estado/risco.json`, `estado/boleta.json`,
`carteira.json`, `execucoes.csv`, `operacoes_ir.csv`.

## O que mudou em relação ao original

| Original (EUA) | day-trader-b3 |
|---|---|
| NYSE 9h30–16h00 ET, horário de verão americano | Mercado à vista 10h00–16h55 (horário de verão nos EUA) ou 10h00–17h55; call de fechamento de 5 min; Quarta-feira de Cinzas às 13h (Ofícios B3 050/2026 e 041/2026) |
| Feriados da NYSE | Feriados nacionais, Carnaval, Sexta-feira Santa, Corpus Christi, 24/12 e 31/12; 2026 conferido com o ofício da B3 |
| Lista da Nasdaq Trader | Carteira teórica dos índices da B3 |
| Tickers `AAPL`, `BRK.B` | `PETR4`, `B3SA3`, `TAEE11`, fracionário `PETR4F` |
| Ações inteiras na Alpaca | Lote padrão de 100 + mercado fracionário; custos da B3 na perda máxima |
| Regra de pattern day trader | Sem PDT; horário limite de entradas e de zerar ligado ao fim do pregão |
| Alpaca (MCP) envia a ordem | Boleta para digitar no home broker/plataforma, com OCO de stop e alvo |
| SEC XBRL (analyst) | CVM ITR/DFP, com 4º trimestre derivado |
| 8-K e RSS do Yahoo (news) | Documentos IPE da CVM e Google Notícias |
| Pelosi tracker | Negociações de administradores e controladores (VLMO, Res. CVM 44) |
| Lotes fiscais e wash sale dos EUA | Custo médio, day trade 20%, IRRF 1%, prejuízos segregados, DARF 6015 (IN RFB 1.585/2015) |
| Só comprado e só intradiário | Também swing trade de vários pregões, comprado ou vendido com aluguel e garantia |

## Instalação

No Claude Code, como plugin a partir deste repositório:

```
/plugin marketplace add fabiosonic/fabiosonic
/plugin install day-trader-b3@fabiosonic
```

Os comandos ficam com prefixo (`/day-trader-b3:b3-scanner`). Para instalar à mão, copie as
pastas `b3-*` **e** `b3-comum` para `~/.claude/skills/` ou para
`.claude/skills/` do projeto: todas as skills importam `b3-comum`.

Requisitos: Python 3.8+ só com biblioteca padrão. Nenhuma chave de API.
Copie `config.example.json` para `trader-b3/config.json` e ajuste orçamento,
limites, custos e os `tipos` dos ativos com final 11.

## Limitações honestas

- **Dados do Yahoo** são gratuitos, não oficiais e podem atrasar até 15 minutos.
  Não há dados de mini-índice e mini-dólar (WIN/WDO): este pacote cobre
  ações, units, ETFs, BDRs e FIIs.
- **CVM é D-1**: os arquivos abertos são atualizados uma vez por dia. Para o
  que saiu hoje, consulte o RAD da CVM.
- **Calendários futuros** são calculados: confira o ofício de feriados que a
  B3 publica no fim de cada ano e ajuste `sessoes` no config se a B3 mudar
  um horário.
- **Custos**: `custos_pct` é uma estimativa; confira a tabela vigente da B3 e
  da corretora. Para o IR, valem as notas de corretagem.
- **Uma corretora por pasta**: day trade é apurado por corretora.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Rodam sem rede, com dados reais salvos em `tests/fixtures`: candles do Yahoo
(5 minutos de outubro de 2026 e diários de 2 anos), a carteira do IBRA e
recortes dos arquivos da CVM.

## Licença

MIT. Veja [LICENSE](LICENSE): mantém o aviso do projeto original.
