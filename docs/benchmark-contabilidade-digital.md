# Benchmark (engenharia reversa) — sites de contabilidade digital

Coleta em 13/10/2026: homepages baixadas com curl e WebFetch, com análise do HTML, dos textos e das bibliotecas de animação presentes no código. As animações foram **deduzidas das bibliotecas** encontradas, não observadas visualmente. Quando uma página falhou, o caso está indicado.

## Sites analisados (22)

| Site | País | Hero / CTA | Ferramentas | Animação/visual detectado | Onboarding |
|---|---|---|---|---|---|
| Contabilizei | BR | "Cuidar de notas e impostos nunca foi tão fácil" | Custo de abrir CNPJ, PJ x CLT, Fator R, RPA, Reforma, CNAE | Tabela comparativa, carrossel | Plano pré-selecionado, WhatsApp |
| Agilize | BR | "Você cuida da sua empresa. A gente cuida da sua contabilidade" | CLT x PJ, Reforma Tributária | Next.js, acordeões | Formulário + especialista, WhatsApp |
| Conube | BR | Abrir empresa / Trocar de contador | Impostos, CLT x PJ | Gatsby, acordeões, vídeo | Formulário, WhatsApp |
| Contabilivre | BR | "Seja #livre…" | Simulador, Fator R, tabela do Simples | Não verificado (403) | Simulador → formulário → chat |
| Nibo | BR | "Simplificamos a rotina de contadores e empresas" | Calculadoras | Webflow, abas | Teste |
| Omie | BR | ERP + conta PJ | Simulador, Radar da Reforma | Swiper, Rive | Teste, parceiros |
| Bench | EUA | "Bookkeeping done for you." | Calculadoras, modelos | Contadores animados, abas | Ligação → bookkeeper (4 passos) |
| Pilot | EUA | "…who's leading the company?" | Burn rate, calendário fiscal | GSAP, Swiper | Demo |
| Kruze | EUA | "Expert Accounting for VC-Funded Startups" | Crédito de P&D | Contador animado | Formulário qualificador |
| inDinero | EUA | "Expert-led. AI-accelerated" | Quiz de P&D | Splide, Vimeo | Quiz + cotação |
| Collective | EUA | Profissões rotativas no título | Calendário fiscal, preço/hora | Marquee, palavras rotativas | Consulta |
| Xero | Global | "Know your numbers." | Calculadoras | Abas por estágio | Cadastro |
| QuickBooks Live | EUA | "…trusted experts" | Folha, faturas | Vídeo | Quiz "find a plan" |
| Accountable | DE/BE | "Deine Finanzen. Im Griff." | Consultor de IA | Marquee | Cadastro, coach |
| Keobiz | FR | "…en ligne mais pas que !" | IVA, preço de venda | Swiper, Framer | Orçamento em 4 etapas |
| Qonto | FR | Conta + faturação | ROI, IVA | GSAP ScrollTrigger, Lottie | Fluxo guiado |
| Crunch | UK | Quiz no próprio hero | Calculadoras fiscais | GSAP ScrollTrigger | Quiz → cotação |
| Tide | UK | Accounting | Estimativa de imposto | Contadores, abas | App |
| Holded | ES | "Factura, cobra y cierra el mes." | — | Marquee, abas por módulo | Demo |
| Fiskl | Global | "AI does the accounting." | — | Lottie, palavras rotativas | Cadastro |
| Osome | SG/UK | Experts + software | Margem, IVA, nome de empresa | Lottie | Ligação |
| Sleek | SG/AU | "Start, Run & Grow…" | Nome de empresa | Lottie, contadores | Agendamento em 3 passos |

Limites: na Omie, a página /contabilidade/ deu 404, então analisei a home. Na Qonto, /fr/accounting deu 404 e analisei /fr. A Tide redirecionou para a página de software contábil. A Contabilivre bloqueou o curl (403).

## Padrões adotados no M&O Contábil DIGITAL

| # | Padrão recorrente | Onde está no site |
|---|---|---|
| 1 | Duas jornadas separadas: abrir empresa e trocar de contador | Links no hero, que preenchem o assunto do formulário |
| 2 | Promessa de alívio no hero | "Contabilidade digital, com contador de verdade do seu lado" |
| 3 | Palavra rotativa por segmento (Collective, Fiskl) | "Feita para [segmento]" |
| 4 | Mockup animado de painel (Holded, Qonto, Pilot) | Painel com barras, linha de tendência, contadores e cartões flutuantes |
| 5 | Prova social logo abaixo do hero | Ano de fundação, CRC e nota no Google com nota de fonte |
| 6 | Marquee (Collective, Holded) | Faixa de serviços e carrossel de avaliações |
| 7 | "Como funciona" em 4 passos (Bench, Sleek) | Linha do tempo que se preenche com a rolagem |
| 8 | Serviços em abas (Xero, Holded) | Consultoria contábil / Serviços adicionais |
| 9 | Bento da plataforma | Documentos pelo celular, chat, prazos, relatórios |
| 10 | Hub de calculadoras (padrão mais forte no Brasil) | Fator R, margem, ponto de equilíbrio, NCG e checklist |
| 11 | Conteúdo regulatório em destaque (Reforma) | Seção com cronograma 2026–2033 e fontes |
| 12 | Credencial regulatória visível | CRC e CNPJ no hero, no "Quem somos" e no rodapé |
| 13 | FAQ em acordeão, com schema FAQPage | 6 perguntas |
| 14 | WhatsApp como canal principal | Botão flutuante e formulário que abre o WhatsApp |
| 15 | Movimento discreto (scroll reveal, contadores) | IntersectionObserver em CSS e JS puros, sem GSAP, respeitando `prefers-reduced-motion` |

## O que NÃO foi copiado (NBC PG 01 — Código de Ética Profissional do Contador)

- Preço publicado, "a partir de R$", "grátis", desconto, preço riscado e campanhas com prazo (Contabilizei, Contabilivre, Conube, Bench, Collective, Accountable). No site, os honorários são tratados como **proposta escrita**.
- Comparação com outros contadores ou concorrentes (Contabilizei, inDinero, Fiskl).
- Promessa de economia ou garantia de resultado (Collective, Crunch, Accountable, Sleek). O planejamento tributário é descrito como "estudo documentado".
- Superlativos sem lastro ("nº 1", "1ª contabilidade online").
- Do site atual também ficaram de fora: "abrir empresa pagando somente as taxas" (promoção vinculada a fidelidade), "planejamento tributário sem custos adicionais" e um depoimento que cita redução de alíquotas.

> Nota: a equipe de pesquisa não conseguiu abrir o texto oficial da NBC PG 01 no portal do CFC. Confira os itens na fonte primária antes de citar a numeração.
