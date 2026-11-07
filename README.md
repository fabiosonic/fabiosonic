# SwingBot — robô de swing trade para o Home Broker da Clear

O robô abre o site da Clear, entra no Home Broker, analisa os ativos no gráfico diário e opera sozinho
um **capital de teste**. Tem gestão de risco, stop sempre registrado na corretora e apuração do IR.

> ⚠️ **Leia antes de usar dinheiro real**
> - A Clear **não oferece API** para o Home Broker. O robô opera a tela do navegador como uma pessoa.
>   Isso pode contrariar os termos de uso e quebra quando o layout muda. **O risco é seu.**
> - O backtest com parâmetros padrão (12 ações do IBOV, jun/2019 a nov/2026) **não superou o CDI**
>   (tabela abaixo). Use o modo simulado por semanas antes de ligar o modo real.
> - Isto é uma ferramenta, não uma recomendação de investimento.

## Como funciona

```
 ┌───────────┐   ┌──────────┐   ┌────────┐   ┌────────────────┐   ┌──────────────────┐
 │ Cotações  │──▶│Estratégia│──▶│ Risco  │──▶│ Travas fiscais │──▶│ Simulado / Clear │
 │ (Yahoo)   │   │ MME+ATR  │   │ 1%/op. │   │ anti-DT, 20 mil│   │ (Playwright)     │
 └───────────┘   └──────────┘   └────────┘   └────────────────┘   └──────────────────┘
                                                                          │
                                         estado/carteira_*.json ◀─────────┘ ──▶ apuração IR / DARF
```

| Módulo | Função |
|---|---|
| `estrategia.py` | Compra quando a MME9 cruza a MME21 para cima, com o preço acima da MMS200. Stop de 3×ATR, alvo de 3R, trailing stop, saída por perda de tendência ou por tempo |
| `risco.py` | Risco de 1% do capital por trade, no máximo 40% num ativo, lote padrão e fracionário (sufixo `F`), *kill switch* (-10%) e arquivo `PARAR` |
| `fiscal.py` | Apuração mensal: 15% swing, 20% day trade, isenção de R$ 20 mil em ações, compensação de prejuízo, IRRF, DARF 6015 e regra do mínimo de R$ 10 |
| `motor.py` | O mesmo motor de decisão no backtest, no simulado e no real |
| `corretoras/clear_homebroker.py` | Abre o site da Clear, entra no Home Broker, aguarda o login, lê a custódia, envia e cancela ordens e tira um *print* de cada passo |
| `executor.py` | Ciclo diário: reconcilia com a corretora, protege as posições com stop e executa o plano |

## Instalação (no seu computador, Windows/Mac/Linux)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Painel Quant B3 (dashboard com IA)

```bash
python pesquisa/baixar.py && python pesquisa/baixar_dividendos.py && python pesquisa/baixar_consenso.py   # 1ª vez
export ANTHROPIC_API_KEY=...        # opcional: ativa o Analista IA e o assistente (Windows: set ANTHROPIC_API_KEY=...)
python -m swingbot painel          # abre http://127.0.0.1:8050 (só na sua máquina)
```

| Aba | O que tem |
|---|---|
| **Visão geral** | KPIs do robô, gráfico profissional (MMs, MACD, volume, sinais), **Analista IA**, **consenso das casas de análise** com convergência, scanner e posições |
| **Oportunidades** | Rastreador de setups com a evidência de 10 anos de cada setup |
| **Ranking & carteiras** | Ranking por dividendos, momentum e mix, alerta de armadilha de dividendos, rebalanceamento para a fila |
| **Carteira & risco** | Risco aberto até os stops, concentração, orçamento de perda, custódia da Clear |
| **Laboratório** | Curvas de patrimônio e resultados dos estudos |
| **Fiscal** | Apuração mensal e DARF |
| **Robô Clear** | Fila de ordens, **proteções** (stop loss, take profit, trailing, breakeven, OCO) e log |

A IA usa o Claude (`claude-opus-5-5`) e se baseia **só** nos dados do painel. O assistente pode pesquisar notícias
e as carteiras recomendadas do mês na web, citando as fontes. Se o modelo recusar, a API refaz a pergunta num modelo alternativo (*fallback*).
O consenso de analistas vem do Yahoo Finance (estimativas LSEG de bancos e corretoras). Não é a carteira oficial de nenhuma casa.

### Stop loss, take profit e trailing stop
Na boleta de compra do painel:
- **Stop loss**: fica **sempre registrado na Clear** como ordem stop. Continua protegendo mesmo com o computador desligado.
- **Take profit**: executado pelo monitor quando o preço chega ao alvo. Com **OCO** calibrado, o stop e o alvo ficam juntos na Clear.
- **Trailing stop**: em % da máxima ou em múltiplos de ATR, com ganho mínimo para ativar. O stop nunca desce.
- **Breakeven**: depois de X% de ganho, o stop sobe para o preço de entrada (+0,2% de custos).

```bash
python -m swingbot executar-fila --real   # envia as compras da fila; as proteções ficam registradas
python -m swingbot monitorar              # simulação: mostra o que o monitor faria
python -m swingbot monitorar --real       # pregão: registra stops, faz trailing e take profit na Clear
```
O preço vem da custódia da Clear (seletor `custodia.preco_atual`) ou, sem ele, do Yahoo com ~15 min de atraso.
Para ter stop e alvo juntos na Clear, calibre os seletores de OCO em `config/seletores_clear.yaml`.

### Alerta de reversão de tendência (saída)
Depois da entrada, o painel e o monitor avaliam a tendência de cada posição a cada minuto (painel) ou a cada 15 min (monitor):

| Sinal | Peso |
|---|---|
| MME9 virou para baixo | 1 |
| MACD cruzou abaixo do sinal (ou está abaixo e caindo) | 2 (1) |
| Fechamento abaixo da MME21 | 1 |
| MME9 cruzou abaixo da MME21 | 2 |
| Rompeu a mínima de 10 pregões | 2 |
| Perdeu a MMS200 (ou já estava abaixo) | 3 (1) |
| Devolveu 2 ATR ou mais desde a máxima | 2 |

**1 a 2 pontos = ATENÇÃO; 3 ou mais = SAIR.** No nível SAIR o painel mostra um alerta e envia uma notificação no navegador.
Se a proteção estiver com **"sair automaticamente"**, o monitor cancela o stop e vende.

### Quanto custa a IA (API da Anthropic)
A API é cobrada **à parte** da assinatura do claude.ai: é paga por uso, com créditos pré-pagos no Claude Console.
O painel registra o gasto de cada chamada, mostra o total do mês e **desliga a IA ao atingir o teto** (`ia.orcamento_mensal_usd`).

| Uso (Claude Opus 5.5, US$ 4 / 20 por milhão de tokens) | Custo estimado |
|---|---|
| Análise do dia (~5 mil tokens de entrada + raciocínio e resposta) | US$ 0,10 – 0,20 |
| Pergunta ao assistente | US$ 0,03 – 0,08 |
| Pergunta com notícias da web | US$ 0,15 – 0,40 |
| Pesquisa das carteiras das casas (1x por mês) | US$ 0,30 – 1,00 |
| **Uso diário típico no mês** (1 análise e 5 perguntas por pregão) | **US$ 5 – 10** |

Para gastar menos, use `claude-sonnet-5-5` (cerca de metade) ou `claude-haiku-5-5` (bem menos) em `ia.modelo_chat`.

## Passo a passo

### 1. Backtest
```bash
python -m swingbot backtest --inicio 2019-06-01 --trades
```

### 2. Modo simulado (paper trading com dados reais), por algumas semanas
```bash
python -m swingbot rodar            # 1x por dia, após o fechamento
python -m swingbot apuracao         # IR mensal da carteira simulada
```

### 3. Calibrar a tela da Clear (uma vez)
```bash
python -m swingbot calibrar
```
O navegador abre no site da Clear junto com o **Playwright Inspector**. Faça login, abra o Home Broker,
clique em *Pick locator*, aponte cada elemento (boleta, campos, botões, tabela de custódia e de ordens)
e copie o seletor para `config/seletores_clear.yaml`. O modo real **se recusa a rodar** enquanto houver `PREENCHER`.

Depois teste **sem enviar nada**:
```bash
python -m swingbot ensaio PETR4 --preco 10.00
```
Esse comando preenche as boletas de compra e de stop, não envia e salva capturas de tela em `logs/AAAA-MM-DD/`.

### 4. Modo real com o capital de teste
1. Em `config/config.yaml`, defina `modo: real` e o `capital_teste`.
2. Use uma conta ou um saldo separado, se possível, e **não opere manualmente os mesmos ativos**.
   O robô bloqueia ativos com posição que ele não abriu.
3. Rode no pregão, entre 10h15 e 16h45:
```bash
python -m swingbot rodar --real
```
O robô abre o site da Clear, vai ao Home Broker e **espera você fazer o login** (senha, 2FA e captcha nunca
passam por ele). Em seguida pede a assinatura eletrônica, que fica só na memória, e pede que você digite
`OPERAR REAL`.

**Recomendado:** rodar 2 vezes por dia, por exemplo às 10h30 e às 16h30. A segunda execução não abre
posições novas: só confere execuções e registra stops pendentes.

Para agendar sem o prompt de confirmação (no Agendador do Windows ou no cron), use `--sem-confirmacao`.
A sessão do navegador fica salva em `.sessao_clear/`, mas a Clear pode pedir login de novo.

**Parada de emergência:** crie um arquivo chamado `PARAR` na pasta do projeto.

## Travas de segurança

- Modo **simulado por padrão**. O real exige `modo: real`, `--real`, seletores calibrados e confirmação digitada.
- O robô nunca usa mais que `capital_teste`.
- **Stop sempre na corretora** (protege mesmo se o PC desligar). Antes de vender ou ajustar, o robô cancela o stop antigo.
- Limite de ordens por dia, horário permitido, trava contra duas execuções simultâneas e *kill switch*.
- Cada envio gera uma captura de tela e é registrado em `logs/AAAA-MM-DD/relatorio.txt`.
- Se a ordem não for confirmada na tela, o robô registra **FALHA** e não assume que ela foi executada.

## Aspectos tributários (PF, Lei 11.033/2004 e IN RFB 1.585/2015)

- **Anti-day-trade:** o robô nunca faz uma saída discricionária no mesmo dia da entrada.
  Só o stop, por proteção, pode virar day trade (20%, compensável somente com day trade).
- **Isenção de R$ 20 mil/mês** (só ações, não vale para ETF, BDR e FII): o robô avisa quando uma venda vai estourar o limite.
  Com `bloquear_venda_acima_isencao: true`, ele adia saídas com lucro.
  Critério conservador: todas as vendas de ações do mês entram na soma.
- **Finais 11** (FII, ETF ou unit) são tratados como ETF, sem isenção. Classifique-os em `fiscal.tipos_ativo`.
- `apuracao` calcula o resultado mensal, o prejuízo a compensar, o IRRF (0,005% e 1%) e o DARF 6015
  (o valor abaixo de R$ 10 acumula para o mês seguinte).
- Preços e datas de stops detectados na reconciliação ficam marcados como **estimados**.
  **A apuração oficial deve ser conferida com as notas de corretagem.**
- DIRPF: posições em Bens e Direitos (custo), ganhos isentos em Rendimentos Isentos e
  apuração mensal em Renda Variável.

## Backtest de referência (12 ações do IBOV, 06/2019 a 11/2026, capital de R$ 5 mil)

| Configuração | Retorno total | Drawdown máx. | Trades | Acerto | Fator de lucro |
|---|---|---|---|---|---|
| stop 2 ATR, alvo 2R, trailing | -11,0% | -17,1% | 179 | 31% | 0,84 |
| **stop 3 ATR, alvo 3R, trailing (padrão)** | +12,2% | -9,8% | 196 | 30% | 1,20 |
| stop 2,5 ATR, alvo 4R, trailing | +17,6% | -10,8% | 199 | 30% | 1,24 |
| MME 21/50, stop 2 ATR, alvo 3R, sem trailing | +20,1% | -11,6% | 107 | 36% | 1,30 |

Nenhuma configuração bateu o CDI do período, e escolher a melhor linha da tabela é *overfitting*.
Os preços **não são ajustados** por proventos: dividendos causam gaps que penalizam o resultado.
Antes de operar real, vale melhorar a estratégia: filtros de volume ou de regime de mercado, outros setups.

## Testes
```bash
pytest -q
```
