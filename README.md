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
