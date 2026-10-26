---
name: b3-swing
description: >-
  Swing trade de ações na B3, COMPRADO ou VENDIDO (venda a descoberto):
  monta o plano a partir do último pregão (gatilho na máxima ou mínima,
  stop swing/ATR/percentual, alvo em R, prazo em pregões), simula 10.000
  caminhos diários com gaps e custo de aluguel, reaplica a regra no
  histórico de 2 anos e acompanha as posições abertas (resultado, R,
  stop/alvo tocado, prazo, aluguel acumulado, sugestão de mover o stop).
  Use quando o usuário disser "swing trade", "operar por alguns dias",
  "posição de vários dias", "quero shortear", "vender a descoberto",
  "operar vendido", "plano de swing em PETR4", "como estão minhas posições".
argument-hint: "plano PETR4 --lado compra|venda | simular | acompanhar | mover-stop PETR4 59.10"
---

# b3-swing

Swing trade = posição mantida por alguns pregões (padrão: até 15). Funciona
nos dois lados. Nunca envia ordem: o fluxo continua em `/b3-orcamento`,
`/b3-risco` e `/b3-boleta`, que já tratam vendido, ordem stop e prazo.

```bash
python3 "${CLAUDE_SKILL_DIR}/swing.py" plano PETR4 --lado compra --write
python3 "${CLAUDE_SKILL_DIR}/swing.py" plano B3SA3 --lado venda --stop atr:2 --target 3R --prazo 20 --write
python3 "${CLAUDE_SKILL_DIR}/swing.py" plano VALE3 --lado compra --entrada fechamento --stop pct:4
python3 "${CLAUDE_SKILL_DIR}/swing.py" simular            # do trader-b3/plano.json
python3 "${CLAUDE_SKILL_DIR}/swing.py" acompanhar         # posições abertas com plano
python3 "${CLAUDE_SKILL_DIR}/swing.py" mover-stop PETR4 59.10
```

## Fluxo

1. `/b3-scanner diario` (com `--lado venda` para setups de venda:
   perdeu_20d, bandeira_baixa, perdeu_mm20, sobrecomprado, repique_baixa).
2. `swing.py plano SYM --lado ... --write` → plano.json e swing/planos.json.
3. `swing.py simular` → probabilidades com gap e o histórico da regra.
4. `/b3-orcamento --write` → quantidade (no vendido: só lote padrão, aluguel
   na perda, tetos de garantia e de exposição vendida) e ordem stop de entrada.
5. `/b3-risco` → APROVADA/BLOQUEADA (vendido exige `"permitir_vendido": true`).
6. `/b3-boleta` → mostra, pergunta, registra o sim, o envio e as execuções.
7. Todo dia: `swing.py acompanhar`; no fim do mês, `/b3-fiscal apurar`.

## Regras do plano

- Entrada `gatilho` (padrão): compra 1 centavo acima da máxima do pregão de
  sinal, venda 1 centavo abaixo da mínima, como ordem stop válida no dia (se
  não disparar, refaça o plano no dia seguinte). `fechamento` ou um preço
  viram ordem limitada.
- Stop `swing:N` (padrão 5 pregões), `atr:K` (ATR 14 diário), `pct:X`,
  `preco:X`; arredondado para longe da entrada.
- O stop só anda a favor (`mover-stop`); a ferramenta recusa afrouxar.

## O que dizer sempre ao usuário

- Gap: no swing a abertura pode pular o stop; a simulação mostra quantas
  vezes isso deu perda maior que 1R.
- Vendido na B3: exige aluguel (BTC) com taxa paga por quem vende, garantia
  depositada, reembolso de proventos ao doador e risco de recall do aluguel.
  A perda no vendido não tem teto teórico.
- IR: swing é operação comum (15%, IRRF 0,005% na venda, isenção de R$ 20 mil
  só para venda de ações compradas). Na venda a descoberto o resultado é
  apurado no mês da recompra; a taxa de aluguel pode ser incluída nos custos.
- Simulação com o histórico do próprio ativo não é previsão.
