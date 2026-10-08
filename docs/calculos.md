# Cálculos do simulador

Código: `src/lib/options/payoff.ts` (função pura, a mesma no servidor e no navegador).
Testes: `tests/unit/payoff.test.ts` (valores calculados à mão, comentados em cada caso).

## Convenções

| Item | Convenção |
| --- | --- |
| Sinal | Compra (`BUY`) = **+1**; venda (`SELL`) = **−1** |
| Quantidade | Em **unidades** do ativo-objeto. Na B3, uma opção de ação refere-se a 1 ação; lote padrão de 100 |
| Multiplicador | `multiplier` multiplica todas as pernas (padrão 1). Útil para contratos com tamanho diferente |
| Prêmio | Por unidade, em R$. Para a perna `STOCK` (ação), é o preço de entrada |
| Custos | Valor **total fixo** em R$ (corretagem, emolumentos), cobrado uma vez e subtraído do resultado |
| Precisão | `decimal.js` com 40 dígitos significativos e arredondamento bancário; exibição com 2 casas |
| Domínio de preço | S ≥ 0 |
| Momento | **Somente no vencimento.** Não há modelo de precificação antes do vencimento |

## Fórmulas

Para cada perna *i* com sinal sᵢ, unidades uᵢ = quantidade × multiplicador, prêmio pᵢ e strike Kᵢ:

- Valor intrínseco no vencimento:
  - CALL: max(S − K, 0)
  - PUT: max(K − S, 0)
  - Ação: S
- **Fluxo inicial** = −Σ sᵢ·uᵢ·pᵢ − custos → positivo = **crédito**, negativo = **débito**
- **Resultado no vencimento** R(S) = Σ sᵢ·uᵢ·(intrínsecoᵢ(S) − pᵢ) − custos

## Algoritmo de análise

R(S) é linear por partes, com mudanças de inclinação apenas nos strikes.

1. Pontos de quebra: {0} ∪ {strikes}, ordenados.
2. **Pontos de equilíbrio**: em cada segmento [a, b] com sinais opostos em R(a) e R(b), raiz por interpolação linear exata; pontos com R = 0 também entram (exceto S = 0). À direita do maior strike, a inclinação é σ = Σ sᵢ·uᵢ para CALL e ações (PUT tem inclinação 0); se R(último) e σ têm sinais opostos, raiz = último − R(último)/σ. Estratégias podem ter **vários** equilíbrios (borboleta, straddle, ratio).
3. **Ganho máximo**: se σ > 0 → **teoricamente ilimitado**; caso contrário, o maior R nos pontos de quebra.
4. **Perda máxima**: se σ < 0 → **teoricamente ilimitada** (ex.: venda de CALL a descoberto); caso contrário, o menor R nos pontos de quebra (inclui S = 0 — por isso a perda da venda de PUT é limitada).
5. Cenários padrão: −20% a +20% em passos de 5% sobre o preço de referência, mais os equilíbrios.

> Observação de implementação: em `decimal.js`, `isPos()` é verdadeiro para zero; o código usa `gt(0)`/`lt(0)`. Um teste unitário detectou esse problema durante o desenvolvimento.

## Exemplos validados (calculados à mão)

| Estratégia | Dados | Fluxo | Equilíbrio(s) | Ganho máx. | Perda máx. |
| --- | --- | --- | --- | --- | --- |
| Compra de CALL | K 36, prêmio 1,85, 100 un. | −185 | 37,85 | ilimitado | −185 |
| Venda de CALL | K 64, 1,10, 100 | +110 | 65,10 | 110 | **ilimitada** |
| Compra de PUT | K 33, 1,05 | −105 | 31,95 | 3.195 (S=0) | −105 |
| Venda de PUT | K 26, 0,48 | +48 | 25,52 | 48 | −2.552 (S=0) |
| Trava de alta | +C36 @1,85, −C39 @0,72 | −113 | 37,13 | 187 | −113 |
| Borboleta | +C120 @7,40, −2×C125 @4,30, +C130 @2,20 | −100 | 121 e 129 | 400 (S=125) | −100 |
| Straddle comprado | +C33 @1,20, +P33 @1,05 | −225 | 30,75 e 35,25 | ilimitado | −225 |
| Venda coberta | +100 ações @61,20, −C64 @1,10 | −6.010 | 60,10 | 390 | −6.010 (S=0) |
| Ratio 1×2 | +100 C30 @3, −200 C35 @1 | −100 | 31 e 39 | 400 (S=35) | **ilimitada** |
| Custos | Compra de CALL acima + R$ 10 | −195 | 37,95 | ilimitado | −195 |

## O que não é calculado

- Preço da opção antes do vencimento, gregas e volatilidade implícita.
- Probabilidades de cenários (a visão de Previsões usa apenas preços informados pelo usuário).
- Tributação (IR, swing trade/day trade), margem/garantias exigidas pela B3, ajustes de proventos, exercício antecipado de opções americanas, liquidez e slippage.

Os prêmios dos contratos demonstrativos do seed são gerados com uma fórmula de Black-Scholes simplificada **apenas** para produzir valores plausíveis; essa fórmula não faz parte do simulador.
