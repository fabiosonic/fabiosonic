# Estudo: como criar uma criptomoeda para um jogo

> Visão integrada de **engenharia de software**, **economia do jogo (tokenomics)**, **regulação brasileira**, **tributação** e **contabilidade (CPCs/NBCs)**.
> Data-base: outubro/2026. Normas mudam rápido nesse tema — os itens marcados com ⚠️ devem ser confirmados no texto oficial vigente antes de qualquer decisão.
> Este estudo é técnico-informativo e não substitui parecer jurídico formal.

Artefatos que acompanham o estudo:

| Arquivo | O que é |
|---|---|
| `contracts/GameToken.sol` | Contrato ERC-20 de referência (OpenZeppelin 5.x) com teto de emissão, limite diário, vouchers EIP-712, queima rastreável e pausa. Compila com solc 0.8.24; **não auditado**. |
| `tools/simulacao_tokenomics.py` | Simulador de faucets × sinks para testar a economia antes do lançamento. |

---

## 1. A primeira pergunta: o jogo precisa de blockchain?

Antes de escrever uma linha de Solidity, responda com honestidade. A maioria dos jogos de sucesso (Fortnite, Roblox, Free Fire) usa **moeda virtual centralizada** — um saldo no banco de dados do estúdio. É mais barato, mais rápido, reversível em caso de fraude e juridicamente muito mais simples.

Blockchain só agrega valor quando ao menos um destes pontos é **requisito de produto**:

1. **Propriedade real do jogador** — o item/moeda continua existindo mesmo se o estúdio fechar ou banir a conta.
2. **Mercado secundário aberto** — jogadores negociam entre si fora da loja oficial, e o estúdio aceita isso.
3. **Interoperabilidade** — a moeda/itens são usados em outros jogos ou plataformas.
4. **Transparência verificável** — a comunidade precisa auditar emissão, queima e tesouraria.

Se nenhum é essencial, a recomendação técnica é: **moeda off-chain**. Se algum é, siga o estudo.

### 1.1 Três modelos possíveis

| Modelo | Como funciona | Complexidade | Risco regulatório |
|---|---|---|---|
| **A. Off-chain (tradicional)** | Saldo em banco de dados; compra via loja (cartão/Pix) | Baixa | Baixo (CDC, LGPD, ECA Digital) |
| **B. Híbrido (recomendado)** | Moeda *soft* off-chain para o dia a dia + token *hard* on-chain resgatável (ou só itens NFT on-chain) | Média | Médio |
| **C. Totalmente on-chain / "play-to-earn"** | Toda a economia em token negociável em corretoras | Alta | **Alto** (CVM, BCB, prevenção à lavagem) |

O modelo **B** é o padrão de mercado pós-2022: o jogador joga sem gás e sem carteira; só quem quer "sacar" para a blockchain interage com ela.

---

## 2. Lições de mercado (o que deu errado e por quê)

- **Axie Infinity (2021–2022)** — modelo dual-token: AXS (governança) + SLP (moeda de recompensa, sem teto). O SLP era emitido muito mais rápido do que era queimado; a renda dos jogadores dependia de **novos entrantes comprando** os ativos. Quando o crescimento parou, o SLP perdeu mais de 99% do valor. Somou-se o hack da ponte Ronin (~US$ 600 milhões, março/2022) causado por comprometimento de chaves de validadores.
- **STEPN (2022)** — mesmo padrão: GST com emissão alta, espiral quando a entrada de novos usuários desacelerou.
- **Lição central:** se a moeda é vendida pelos jogadores mais rápido do que é demandada por **uso real** (sinks) e por **receita real** (pessoas pagando para se divertir), o preço depende de novos entrantes — economicamente, uma estrutura de pirâmide. Além de quebrar o jogo, isso atrai enquadramento como **oferta de valor mobiliário** (ver §6).

O simulador (`tools/simulacao_tokenomics.py`) reproduz o fenômeno. Saída com os parâmetros padrão:

| Cenário | Preço implícito (R$) | Oferta por jogador ativo no dia 365 |
|---|---|---|
| Crescimento +1%/dia (até o teto) | 0,0582 → sobe quando o teto limita a emissão | — (oferta esgotada) |
| Estagnação | **0,0417 (−28%)** só por faltar novatos | 10.950 |
| Queda −1%/dia | 0,0417 | **113.419** (oferta "parada" pronta para ser despejada) |
| Queda com sinks fortes (40 de 50 queimados) e menos venda | **0,2000 (~5×)** | 37.806 (~3× menor) |

Leitura: **sinks fortes valem mais que crescimento**. O sistema deve ser desenhado para funcionar com zero crescimento.

---

## 3. Tokenomics: desenhando a economia

### 3.1 Vocabulário

- **Faucet** — tudo que cria moeda: recompensa de partida, missão diária, evento, venda primária.
- **Sink** — tudo que destrói moeda: crafting, upgrade, reparo, taxa de marketplace, aluguel, entrada em torneio, cosméticos.
- **Razão sink/faucet** — meta de longo prazo entre 0,8 e 1,0. Abaixo disso = inflação; acima por muito tempo = escassez que afasta novos jogadores.

### 3.2 Decisões de desenho

1. **Um token ou dois?**
   - *Single-token*: simples, mas o mesmo ativo serve para especulação e para gastar no jogo — conflito.
   - *Dual-token*: moeda de jogo inflacionária e controlada (soft) + token com oferta fixa (hard/governança). Separa "gasolina" de "patrimônio", mas dobra a complexidade regulatória se ambos forem negociáveis.
   - Recomendação: **soft off-chain + hard on-chain com teto (cap)**.
2. **Oferta máxima (cap)** — defina e codifique no contrato (`ERC20Capped`). Oferta infinita só para moeda soft off-chain controlada pelo servidor.
3. **Emissão diária com teto** — o contrato de referência limita via `dailyMintLimit`: mesmo que o servidor seja invadido, o prejuízo diário é limitado.
4. **Alocação e vesting** — distribuição típica: comunidade/recompensas 40–55%, tesouraria/ecossistema 15–25%, equipe 10–20% (vesting de 3–4 anos com *cliff* de 12 meses), investidores 10–20% (vesting), liquidez 3–5%. Vesting deve ser **on-chain** (ex.: `VestingWallet` da OpenZeppelin) para ser verificável.
5. **Sinks desejáveis** — o jogador deve *querer* gastar (cosmético raro, conveniência, competição), não ser forçado. Sinks punitivos aceleram a saída.
6. **Fonte de receita real** — a economia se sustenta se houver dinheiro novo entrando por **diversão** (passe de temporada, cosméticos, torneios), não por expectativa de lucro.
7. **Anti-bot / anti-Sybil** — recompensas on-chain atraem *farms* de bots. Use: limites por conta, prova de humanidade, recompensas decrescentes, *cooldown* de saque, detecção de padrões no servidor.

### 3.3 Processo recomendado

1. Modelar em planilha/simulador (faucets, sinks, cohorts de jogadores).
2. Rodar cenários de estresse: crescimento zero, queda de 50% na base, ataque de bots, "baleia" despejando 5% da oferta.
3. Testnet com jogadores reais (beta fechado), medindo a razão sink/faucet real.
4. Lançamento com parâmetros **ajustáveis** (limite diário, recompensas) via governança com timelock — nunca ajuste silencioso.

---

## 4. Arquitetura técnica

### 4.1 Escolha da blockchain

| Rede | Pontos fortes para jogos | Atenção |
|---|---|---|
| **Ethereum L2 (Base, Arbitrum, Optimism)** | Taxas de centavos, ecossistema EVM maduro, segurança ancorada no Ethereum | Sequenciador ainda centralizado na maioria |
| **Immutable zkEVM** | Focada em jogos, carteira/passport e marketplace prontos | Ecossistema mais nichado |
| **Ronin** | Comunidade gamer (Axie, Pixels) | Histórico do hack de 2022 (ponte) |
| **Polygon PoS** | Barata, amplamente suportada | Mudanças frequentes de roadmap |
| **Solana** | Alto throughput, taxas muito baixas, Token-2022 com extensões (taxa de transferência, hooks) | Stack diferente (Rust), sem EVM |
| **BNB Chain** | Barata, grande base de usuários | Maior centralização |

Recomendação prática para um estúdio brasileiro iniciando: **L2 EVM (Base ou Arbitrum) ou Immutable zkEVM** — Solidity tem a maior oferta de profissionais, auditores e bibliotecas auditadas.

### 4.2 Padrões de token

- **ERC-20** — moeda fungível (o token deste estudo).
- **ERC-721** — item único (personagem, terreno).
- **ERC-1155** — vários tipos de itens no mesmo contrato, fungíveis ou não (ideal para inventário: 1.000 poções + 1 espada lendária).
- **ERC-2612 (permit)** — aprovação por assinatura, sem gás para o jogador.
- **ERC-4337 (account abstraction)** — carteiras inteligentes com *paymaster* (o estúdio paga o gás), login social, chaves de sessão.

### 4.3 Componentes do sistema

```
┌─────────────┐   ações    ┌──────────────────────┐
│ Cliente do  │──────────▶│ Backend autoritativo  │  regras, anti-cheat,
│ jogo (Unity │◀──────────│ (estado do jogo,      │  moeda SOFT off-chain
│ / Unreal)   │  estado    │  ledger off-chain)    │
└──────┬──────┘            └─────────┬────────────┘
       │ login social              │ pede assinatura
       ▼                            ▼
┌─────────────┐            ┌──────────────────────┐
│ Carteira    │            │ Serviço de assinatura │  chave em HSM/KMS,
│ embutida    │            │ (vouchers EIP-712)    │  limites por conta
│ (MPC / 4337)│            └─────────┬────────────┘
└──────┬──────┘                      │ voucher
       │  claimReward(voucher)       ▼
       │            ┌──────────────────────────────┐
       └───────────▶│ Relayer / Paymaster (gás)    │
                    └─────────┬────────────────────┘
                              ▼
                    ┌──────────────────────────────┐
                    │ Contratos: GameToken (ERC-20)│
                    │ Itens (ERC-1155), Vesting,   │
                    │ Marketplace, Tesouraria Safe │
                    └─────────┬────────────────────┘
                              ▼ eventos
                    ┌──────────────────────────────┐
                    │ Indexador (The Graph/próprio)│──▶ backend, BI,
                    └──────────────────────────────┘    contabilidade
```

Pontos-chave:

1. **O servidor é a autoridade** sobre "quem ganhou o quê". O contrato não sabe se a partida foi legítima — por isso o padrão **voucher assinado**: o backend valida e assina; o contrato apenas verifica assinatura, nonce, prazo e teto diário (`claimReward` em `contracts/GameToken.sol`).
2. **Chave de assinatura em HSM/KMS** (AWS KMS, GCP KMS, Azure Key Vault), nunca em variável de ambiente. Rotação periódica: o contrato aceita qualquer endereço com `SIGNER_ROLE`, então basta conceder a nova e revogar a antiga.
3. **Carteira invisível** — o jogador entra com Google/Apple/e-mail; a carteira é criada por MPC ou smart account (ERC-4337). Exportar a chave deve ser opcional.
4. **Gás patrocinado** — o paymaster paga as taxas; o custo vai para o orçamento do estúdio (e para a contabilidade, ver §8).
5. **Indexador** — eventos `RewardClaimed`, `Sink` e `Transfer` alimentam o backend, o anti-fraude e a **conciliação contábil**.
6. **Conciliação off-chain × on-chain** — rotina diária comparando o ledger interno com o saldo on-chain; divergência = alerta.

### 4.4 Segurança (não negociável)

- Usar **OpenZeppelin Contracts** (auditados), nunca reimplementar ERC-20.
- **Admin em multisig** (Safe, 3 de 5 por exemplo) + **timelock** (24–72 h) para mudanças de parâmetros.
- **Pausable** para emergências, com papel separado (`PAUSER_ROLE`).
- **Contratos imutáveis por padrão.** Proxy atualizável só se necessário, e com timelock — upgrade é o maior vetor de "rug pull".
- **Testes**: unitários, *fuzzing* e testes de invariantes (Foundry), análise estática (Slither), cobertura ≥ 95%.
- **Auditoria independente** antes da mainnet (custo típico: US$ 10 mil a US$ 80 mil+ conforme escopo) e **bug bounty** (Immunefi) após o lançamento.
- **Pontes (bridges) são o ponto mais atacado** do setor — evite depender de ponte própria.
- Ameaças específicas de jogos: bots, multi-contas, exploração de bugs de duplicação off-chain que viram tokens on-chain (por isso o teto diário), *front-running* em marketplaces.

### 4.5 Stack sugerida

| Camada | Ferramentas |
|---|---|
| Contratos | Solidity 0.8.x, OpenZeppelin 5.x, Foundry (testes/fuzz), Slither |
| Deploy/ops | Safe (multisig), OpenZeppelin Defender ou equivalente para monitoramento, timelock |
| Backend | Node.js/TypeScript (viem/ethers) ou Go; fila para assinatura; KMS |
| Carteira | SDKs de carteira embutida (MPC) ou ERC-4337 com paymaster |
| Indexação | The Graph, Ponder ou indexador próprio |
| Cliente | Unity/Unreal com SDK web3 apenas na camada de "saque/loja" |

### 4.6 Sobre o contrato de referência

`contracts/GameToken.sol` implementa:

- `ERC20Capped` — oferta máxima imutável;
- `claimReward(...)` — resgate de recompensa com **voucher EIP-712** (assinatura do servidor, nonce único, prazo, teto diário global);
- `spend(amount, reason)` — sink com **motivo rastreável** em evento (útil para BI e para a contabilidade separar queima por natureza);
- `treasuryMint` — emissão primária da tesouraria, limitada pelo cap;
- `ERC20Permit`, `Pausable`, `AccessControl` com papéis separados.

Limitações conscientes (para a versão de produção): sem timelock embutido (deve ficar no endereço admin), nonce global (em escala, usar nonce por jogador), sem testes automatizados ainda.

---

## 5. Roteiro de execução

| Fase | Duração típica | Entregas |
|---|---|---|
| 0. Viabilidade | 2–4 semanas | Decisão do modelo (A/B/C), parecer jurídico preliminar, estrutura societária |
| 1. Design econômico | 4–6 semanas | Whitepaper/litepaper, simulações, política de emissão e sinks |
| 2. Protótipo | 6–10 semanas | Contratos em testnet, backend de vouchers, carteira embutida |
| 3. Testes e auditoria | 4–8 semanas | Fuzzing, auditoria externa, correções, beta fechado em testnet |
| 4. Compliance | em paralelo | Termos de uso, política de privacidade (LGPD), KYC/PLD se houver saque, controles de idade |
| 5. Lançamento | — | Mainnet com limites baixos, bug bounty, monitoramento 24/7 |
| 6. Operação | contínuo | Ajuste de parâmetros via governança, relatórios de transparência, fechamento contábil mensal |

Equipe mínima: 1–2 devs de smart contract, 2 backend, 1 economista de jogos/analista de dados, 1 segurança (pode ser consultoria), apoio jurídico e contábil especializado.

---

## 6. Regulação no Brasil

### 6.1 Marco legal dos ativos virtuais — Lei 14.478/2022

- Define **ativo virtual** como representação digital de valor negociável ou transferível eletronicamente, usada para pagamento ou investimento (art. 3º).
- **Exclusões relevantes para jogos** (art. 3º, parágrafo único): não são ativos virtuais, entre outros, *instrumentos que provejam ao seu titular acesso a produtos ou serviços especificados ou a benefício proveniente desses produtos ou serviços, a exemplo de pontos e recompensas de programas de fidelidade*, e representações de ativos cuja emissão já seja regulada (ex.: valores mobiliários).
  - **Implicação de desenho:** uma moeda de **circuito fechado** (só serve dentro do jogo, sem conversão garantida em reais) tende a ficar fora do conceito. Quanto mais o token for **negociável livremente e usado como investimento**, mais perto do regime de ativo virtual.
- O **Banco Central** foi designado regulador das prestadoras de serviços de ativos virtuais (Decreto 11.563/2023). Em novembro/2025 o BCB publicou a regulamentação das **Sociedades Prestadoras de Serviços de Ativos Virtuais (SPSAV)** — Resoluções BCB 519, 520 e 521/2025 ⚠️ (autorização, governança, câmbio e transferências internacionais com ativos virtuais), com entrada em vigor a partir de fevereiro/2026 e prazos de adequação para quem já operava.
  - **O emissor do token, por si só, não é necessariamente uma SPSAV.** Mas se o estúdio **custodiar** tokens de jogadores, **intermediar** compra/venda por reais, ou operar **exchange** interna, pode cair no perímetro. Arquitetura que evita isso: carteira não custodial (o jogador controla a chave) e conversão em reais feita por **SPSAV autorizada parceira**.
- Crime de fraude com ativos virtuais (art. 171-A do Código Penal, incluído pela mesma lei).

### 6.2 CVM — o token é valor mobiliário?

- **Parecer de Orientação CVM 40/2022**: criptoativos podem ser valores mobiliários conforme sua essência econômica. O teste central é o de **contrato de investimento coletivo** (art. 2º, IX, Lei 6.385/1976): investimento em dinheiro, empreendimento comum, **expectativa de lucro** derivada do **esforço de terceiros** (o estúdio).
- **Sinais de alerta** que aproximam o token de valor mobiliário: promessa de valorização, "rendimento" por *staking* pago pelo estúdio, divisão de receitas do jogo, recompra programada para sustentar preço, marketing focado em ganho financeiro, venda pública (ICO/IDO) para financiar o desenvolvimento.
- **Como reduzir o risco:** utilidade real e imediata no jogo no momento da venda; nenhum discurso de investimento; sem participação em receitas; sem *staking* remunerado pela empresa; oferta inicial distribuída por jogo/uso e não vendida a investidores; documentação e termos coerentes com isso.
- Se o modelo **for** de investimento, o caminho é a regulação da CVM (ex.: crowdfunding pela Resolução CVM 88/2022, com limites), não um lançamento informal.

### 6.3 Jogos de azar, apostas e proteção de menores

- **Contravenção de jogo de azar** (Decreto-Lei 3.688/1941, art. 50): ganho que depende principalmente da sorte + prêmio com valor econômico é zona de risco. Loot box paga com token **resgatável em reais** é o cenário mais sensível.
- **Apostas de quota fixa** (Lei 14.790/2023): exigem autorização do Ministério da Fazenda; um "torneio com aposta em token" pode ser enquadrado aí.
- **Marco Legal dos Games** (Lei 14.852/2024): define jogos eletrônicos e os separa expressamente de jogos de azar/apostas — um jogo que vire plataforma de aposta perde esse enquadramento.
- **ECA Digital** (Lei 15.211/2025) ⚠️: proíbe *loot boxes* em jogos destinados a ou com acesso provável por crianças e adolescentes e reforça verificação de idade e salvaguardas. Recomenda-se **bloquear funcionalidades de token/negociação para menores de 18 anos**.
- **CDC**: transparência sobre o que é comprado, direito de arrependimento em compras online (art. 49), cláusulas claras sobre encerramento do jogo.

### 6.4 Prevenção à lavagem de dinheiro e dados

- Lei 9.613/1998: prestadoras de serviços de ativos virtuais são sujeitas a deveres de PLD/FT (cadastro, monitoramento, comunicação ao COAF). Mesmo fora do perímetro, **economias de jogo com saque em reais são vetor conhecido de lavagem** — KYC no saque, limites e monitoramento são boas práticas.
- **LGPD** (Lei 13.709/2018): blockchain é pública e imutável — **nunca grave dados pessoais on-chain**. Endereço de carteira vinculado a uma pessoa no seu backend é dado pessoal; trate com base legal, minimização e política de privacidade.

---

## 7. Tributação

### 7.1 Do lado do estúdio (pessoa jurídica emissora)

| Evento | Tratamento tributário (visão atual) |
|---|---|
| **Venda primária de tokens/moeda** por reais | Receita bruta da atividade (venda de bem/direito de uso no jogo). Base de IRPJ/CSLL (Lucro Real/Presumido) e PIS/COFINS; no Simples Nacional, entra na receita bruta conforme o anexo da atividade. A natureza (cessão de direito/conteúdo digital × serviço) define ISS — o subitem 1.09 da LC 116/2003 (disponibilização de conteúdos de áudio, vídeo, imagem e texto por internet) é frequentemente invocado para jogos, mas a classificação de token é controversa ⚠️. |
| **Distribuição gratuita como recompensa** | Sem receita no momento da emissão; tokens próprios ainda não vendidos não geram ganho tributável. Atenção à documentação: o controle de emissão/queima suporta a apuração. |
| **Tokens em tesouraria vendidos depois** | Receita (se atividade operacional) ou ganho de capital — depende da política e da classificação contábil; definir com o contador antes. |
| **Tokens de terceiros (ex.: USDC, ETH) recebidos** | Ativos da empresa; variações e alienações geram resultado tributável (ganho de capital em PJ integra a base de IRPJ/CSLL). |
| **Gás pago (paymaster)** | Despesa operacional; dedutibilidade depende de documentação (relatórios on-chain + conciliação). |
| **Remuneração de equipe em tokens** | Natureza salarial — incidência de INSS, FGTS e IRRF sobre o valor justo na data do pagamento. |

**Reforma Tributária (EC 132/2023, LC 214/2025):** a partir de 2026 há a fase de teste de **CBS (0,9%) e IBS (0,1%)** destacados em documento fiscal; a CBS substitui PIS/COFINS em 2027 e o IBS substitui ICMS/ISS gradualmente até 2033. A LC 214/2025 trata o fornecimento de **bens imateriais e direitos** como operação tributável, o que simplifica a discussão "ISS × ICMS" no futuro, mas exige revisar o enquadramento de operações com ativos virtuais (inclusive a eventual aplicação do regime específico de serviços financeiros) ⚠️.

### 7.2 Do lado do jogador (pessoa física)

- **Ganho de capital** na alienação de criptoativos: alíquotas progressivas de 15% a 22,5% (Lei 13.259/2016), com **isenção para alienações de até R$ 35 mil por mês** (soma de todos os criptoativos alienados no mês), apuração mensal via GCAP e pagamento até o último dia útil do mês seguinte. ⚠️ A MP 1.303/2025 propôs alíquota única de 17,5% sem a isenção, mas **perdeu a vigência** sem conversão em lei — acompanhe novas propostas.
- **Ativos em exchanges/carteiras no exterior**: Lei 14.754/2023 — tributação anual de 15% sobre rendimentos de aplicações financeiras no exterior, abrangendo ativos virtuais ⚠️ (há discussão sobre o alcance para carteiras autocustodiadas).
- **Declaração anual (DIRPF)**: bens e direitos, grupo 08 (criptoativos), pelo custo de aquisição.
- **Recompensas ganhas jogando**: tratamento não pacificado ⚠️. Interpretação conservadora: o valor na data do recebimento compõe rendimento/custo de aquisição; na venda, apura-se o ganho. Seu termo de uso e comunicação devem orientar o jogador a procurar um contador, sem dar consultoria.

### 7.3 Obrigações acessórias

- **IN RFB 1.888/2019** — declaração mensal de operações com criptoativos (exchanges brasileiras sempre; PF/PJ que operam fora de exchange brasileira acima de R$ 30 mil/mês).
- **DeCripto** ⚠️ — a Receita Federal instituiu em 2025 nova declaração alinhada ao padrão da OCDE (*Crypto-Asset Reporting Framework*, CARF), substituindo a IN 1.888 a partir de 2026, com abrangência maior para prestadoras de serviços e operações no exterior. Confirme número da IN, vigência e leiaute antes de parametrizar o sistema.
- Se a empresa for SPSAV, somam-se as obrigações regulatórias do BCB e de PLD (COAF).

**Requisito de software que decorre daqui:** o sistema precisa gerar, por jogador e por empresa, um **extrato fiscal** com data/hora, quantidade, valor em reais na data (fonte de cotação documentada), custo médio e hash da transação — sem isso, nem o estúdio nem o jogador conseguem cumprir as obrigações.

---

## 8. Contabilidade (CPCs / NBCs)

Não há, até a data-base, CPC específico para criptoativos; aplica-se o arcabouço geral, alinhado à **decisão de agenda do IFRS Interpretations Committee (junho/2019)** sobre *holdings of cryptocurrencies*.

### 8.1 Criptoativos mantidos pela empresa (tokens de terceiros ou tokens próprios recomprados/em tesouraria após emissão)

| Situação | Norma | Mensuração |
|---|---|---|
| Mantidos para venda no curso normal dos negócios (atividade de trading/corretagem) | **CPC 16 (R1) – Estoques** | Custo ou valor realizável líquido; *broker-traders* podem usar valor justo menos custo de venda |
| Demais casos (regra geral) | **CPC 04 (R1) – Ativo Intangível** | Custo menos *impairment* (**CPC 01**), ou modelo de reavaliação **somente** se houver mercado ativo — e no Brasil a reavaliação de ativos é vedada pela Lei 11.638/2007, então, na prática, **custo menos impairment** |
| Stablecoins com direito contratual a resgate em moeda | Avaliar **CPC 48 – Instrumentos Financeiros** | Conforme classificação (custo amortizado/valor justo) |

Valor justo, quando aplicável, segue o **CPC 46** (mercado principal, hierarquia de níveis). Nota: nos EUA o FASB (ASU 2023-08) passou a exigir valor justo no resultado para criptoativos, mas **excluiu tokens emitidos pela própria entidade** — não se aplica ao Brasil, mas é referência útil em discussões com auditores.

### 8.2 Tokens emitidos e vendidos pelo próprio estúdio — o ponto mais importante

A venda de moeda de jogo/tokens com utilidade é, na essência, **receita de contrato com cliente** — **CPC 47 (IFRS 15)**:

1. **Contrato**: termos de uso + compra.
2. **Obrigação de desempenho**: permitir o uso dos tokens no jogo (bens/serviços virtuais) — o estúdio **ainda deve algo** ao jogador.
3. **Reconhecimento**: no recebimento, registra-se **passivo de contrato** (receita diferida). A receita é reconhecida quando o jogador **consome** a moeda (compra item consumível, usa em serviço) ou ao longo da vida estimada do item durável.
4. **Breakage** (tokens que nunca serão usados): reconhece-se proporcionalmente ao padrão de uso, se houver base estatística confiável (CPC 47, itens B44–B47).
5. **Emissão gratuita** (recompensas): sem receita; avaliar se cria obrigação a ser **provisionada** (**CPC 25**) — por exemplo, compromisso de resgatar tokens por itens com custo relevante.

Lançamentos ilustrativos:

```
Venda de 1.000 tokens por R$ 100,00 (Pix)
  D  Bancos ......................................... 100,00
  C  Passivo de contrato – moeda virtual ............ 100,00

Jogador gasta 400 tokens em item consumível
  D  Passivo de contrato – moeda virtual ............  40,00
  C  Receita de vendas de bens virtuais .............  40,00

Tributos sobre a receita (ex.: PIS/COFINS/ISS ou CBS/IBS, conforme regime)
  D  Deduções da receita bruta ...................... x
  C  Tributos a recolher ............................ x
```

⚠️ Ponto de atenção fiscal × contábil: a receita contábil é diferida, mas a legislação pode exigir tributação no **recebimento** (dependendo do tributo e do regime). Isso gera diferenças temporárias e, no Lucro Real, controle na parte B do e-Lalur e eventual tributo diferido (**CPC 32**).

**Se o token tiver características de investimento** (direito a lucros, resgate obrigatório, governança sobre a empresa), a classificação pode migrar para **instrumento financeiro (CPC 39/48)** ou até **patrimônio líquido** — mais um motivo para evitar esse desenho.

### 8.3 Custos de desenvolvimento

- Pesquisa (estudos, protótipos de viabilidade): **despesa** (CPC 04, itens 54–56).
- Desenvolvimento dos contratos, backend e do jogo: **capitalizável como intangível** se atendidos todos os critérios do item 57 do CPC 04 (viabilidade técnica, intenção, capacidade, benefício provável, recursos, mensuração confiável). Amortização pela vida útil a partir da entrada em operação.
- Auditoria de contratos: integra o custo do desenvolvimento se ocorrer na fase capitalizável.
- Gás pago em produção: despesa operacional.

### 8.4 Divulgação e controles

- Notas explicativas (**CPC 26** e políticas, **CPC 23**): política de emissão, oferta total/circulante, tokens em tesouraria, passivo de contrato, julgamentos significativos (classificação, breakage), riscos (preço, custódia, regulação).
- **Partes relacionadas (CPC 05)**: tokens alocados a sócios/equipe e vesting.
- **Evento subsequente (CPC 24)**: hacks e variações relevantes após o balanço.
- Controles internos para a auditoria independente (NBC TA): prova de existência e titularidade (assinatura de mensagem pela carteira da empresa), conciliação diária indexador × razão contábil, segregação de funções nas chaves do multisig, política de cotação (fonte, horário, conversão BRL).

**Requisito de software que decorre daqui:** um **subledger de tokens** integrado ao ERP contábil — cada evento on-chain (`Transfer`, `RewardClaimed`, `Sink`) mapeado para um lançamento ou para o controle do passivo de contrato, com trilha de auditoria até o hash da transação.

---

## 9. Checklist de decisão

**Produto e economia**
- [ ] Blockchain é requisito real (propriedade, mercado aberto, interoperabilidade, transparência)?
- [ ] Modelo escolhido: off-chain, híbrido ou on-chain total?
- [ ] Economia simulada com crescimento zero e queda — se sustenta?
- [ ] Razão sink/faucet alvo definida e monitorada?
- [ ] Receita do estúdio vem de diversão (não da venda contínua de token)?

**Técnico**
- [ ] Contratos baseados em OpenZeppelin, cap e limite diário de emissão?
- [ ] Admin em multisig + timelock; chave do servidor em KMS/HSM?
- [ ] Testes com fuzzing, Slither, auditoria externa e bug bounty?
- [ ] Nenhum dado pessoal on-chain?
- [ ] Indexador + conciliação diária off-chain × on-chain?

**Jurídico/regulatório**
- [ ] Parecer sobre enquadramento: ativo virtual (Lei 14.478) × utilidade de circuito fechado × valor mobiliário (CVM)?
- [ ] Custódia e conversão em reais fora do estúdio (ou estúdio autorizado como SPSAV)?
- [ ] Sem mecânicas de azar com prêmio resgatável; bloqueio para menores (ECA Digital)?
- [ ] Termos de uso, política de privacidade (LGPD), KYC/PLD nos saques?

**Fiscal/contábil**
- [ ] Natureza da receita da venda de tokens definida (tributos incidentes, regime, CBS/IBS na transição)?
- [ ] Política contábil aprovada: CPC 47 (passivo de contrato, breakage), CPC 04/16 para ativos mantidos, CPC 25 para obrigações?
- [ ] Subledger de tokens integrado ao ERP e extrato fiscal para jogadores?
- [ ] Obrigações acessórias (IN 1.888 / DeCripto) mapeadas?

---

## 10. Recomendação final

Para um estúdio no Brasil, o caminho de menor risco e maior chance de sucesso é:

1. **Moeda soft off-chain** para toda a jogabilidade (rápida, sem gás, controlável);
2. **Itens raros como NFT (ERC-1155)** e, se houver demanda real, um **token hard com oferta fixa**, distribuído por jogo e não vendido a investidores;
3. **Carteira não custodial embutida + conversão em reais por SPSAV parceira autorizada**, mantendo o estúdio fora do perímetro de prestador de serviços de ativos virtuais;
4. **Comunicação sem promessa de ganho financeiro**, bloqueio de menores e KYC no saque;
5. **Contabilidade pelo CPC 47 desde o dia 1**, com subledger de tokens e conciliação diária — é isso que permite ao auditor, ao fisco e aos investidores confiarem nos números.

Próximos passos sugeridos neste repositório: suíte de testes Foundry para `GameToken.sol`, contrato ERC-1155 de itens, serviço de assinatura de vouchers (TypeScript + KMS) e o modelo de dados do subledger contábil de tokens.
