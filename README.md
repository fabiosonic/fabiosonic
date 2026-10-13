# M&O Contábil DIGITAL

Site institucional e de captação do projeto digital da **Moraes e Oliveira Contabilidade** (Itaboraí/RJ, desde 2015). Cores e logotipo seguem a identidade de moraeseoliveiracontabil.com.br.

HTML, CSS e JavaScript puros, sem build. A única biblioteca de terceiros é o jsPDF (licença MIT), vendorizado em `assets/vendor/` e carregado só quando o cliente pede o PDF do contrato. Basta publicar a pasta em qualquer hospedagem estática.

```bash
python3 -m http.server 8000   # http://localhost:8000
node --test tests/*.test.js   # testes das calculadoras e do contrato
node scripts/gerar-contrato.mjs  # regenera contrato/condicoes-gerais.html após mudar o modelo
```

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `index.html` | Página principal: hero, como funciona, serviços, **pacotes e contratação em 5 etapas com leitura, aceite e assinatura do contrato** (`#pacotes` / `#contratar`), plataforma, "Para cada porte de empresa" (`#porte`), Reforma (qualitativa, com link para o guia), ferramentas, quem somos, FAQ, contato |
| `servicos.html` | Serviços detalhados (contábil, fiscal, DP, legalização, planejamento tributário, consultoria financeira), adicionais com parceiros, FAQ |
| `contabilidade-itaborai.html` | Página da sede em Itaboraí: endereço, como chegar (mapa por link externo), atendimento presencial e digital |
| `atendimento-regiao-metropolitana-rj.html` | Atendimento em São Gonçalo, Niterói e Rio de Janeiro (uma seção por cidade, sem endereços fictícios) |
| `guias/index.html` | Hub de guias |
| `guias/fator-r.html` · `guias/pro-labore.html` · `guias/mei-para-me.html` | Guias tributários (LC 123/2006 e normas citadas) |
| `guias/abrir-empresa.html` · `guias/reforma-tributaria.html` | Abertura de empresa e Reforma Tributária (EC 132/2023, LC 214/2025) |
| `porte/index.html` | Hub "Porte da empresa": fases e tabela porte × limite de receita bruta × base legal (LC 123/2006) |
| `porte/comecando.html` · `mei.html` · `microempresa.html` · `empresa-de-pequeno-porte.html` · `empresas-em-crescimento.html` | Páginas por porte/fase. Limites: MEI até R$ 81.000,00 (art. 18-A, § 1º); ME até R$ 360.000,00 (art. 3º, I); EPP acima de R$ 360.000,00 até R$ 4.800.000,00 (art. 3º, II); acima disso, tratamento qualitativo (sem limite do Lucro Presumido nem alíquotas) |
| `politica-de-privacidade.html` | Política conforme o funcionamento real do site (LGPD), com cabeçalho e rodapé padrão |
| `links.html` | Página de links para a bio, com UTMs (noindex, fora do sitemap) |
| `404.html` | Página de erro (noindex, fora do sitemap) |
| `sitemap.xml` · `robots.txt` | 17 URLs indexáveis com lastmod 2026-10-13; robots aponta para o sitemap |
| `llms.txt` | Resumo factual da entidade, respostas rápidas e lista de páginas para buscadores de IA |
| `assets/css/style.css` | Tokens da marca, layout, animações, responsivo, movimento reduzido, impressão |
| `assets/js/calculadoras.js` | Regras das calculadoras em funções puras, testadas em `tests/` |
| `assets/js/main.js` | Interações: reveal, abas, menu, partículas, palavra rotativa, formulários; contratação em etapas com o contrato em `<dialog>` (leitura integral obrigatória, aceite, assinatura digitando o nome, comprovante, PDF, passos do Assinador gov.br, envio por WhatsApp/e-mail) |
| `assets/js/contrato-modelo.js` | **Fonte única** do contrato (27 cláusulas + 3 anexos, campo `destaques` com as cláusulas limitativas). Mudou o texto? Altere `versao`, espelhe em `docs/contrato-modelo.md` e rode `node scripts/gerar-contrato.mjs` |
| `assets/js/contrato.js` | Funções puras: validação de CPF e CNPJ (inclusive alfanumérico, IN RFB 2.229/2024), preenchimento, texto canônico e hash SHA-256 |
| `assets/js/contrato-pdf.js` | Gera o PDF do contrato no navegador (fonte ≥ 12 pt, CDC art. 54, § 3º) |
| `assets/vendor/jspdf.umd.min.js` | jsPDF (MIT), carregado sob demanda |
| `contrato/condicoes-gerais.html` | Versão pública e estática das Condições Gerais (gerada por `scripts/gerar-contrato.mjs`) |
| `scripts/gerar-contrato.mjs` | Gera a página pública do contrato a partir do modelo |
| `tests/contrato.test.js` | Testes de CPF/CNPJ, preenchimento, hash e coerência do modelo (destaques × preâmbulo, sem IP/e-mail automático, sem valores) |
| `docs/contrato-modelo.md` · `docs/contrato-notas-juridicas.md` | Texto do contrato para revisão e notas jurídicas (fontes, riscos e pendências P1–P22, D1–D9) |
| `scripts/verificar-site.mjs` | Verificação estática: H1, title, description, canonical, JSON-LD, links internos, termos proibidos, nota legal, sitemap |
| `docs/benchmark-contabilidade-digital.md` | Engenharia reversa de 22 sites de contabilidade digital |
| `docs/seo-relatorio.md` | Relatório de SEO: palavras-chave por página e próximos passos |
| `docs/benchmark-pacotes.md` | Estrutura de pacotes de 10 empresas de contabilidade digital (sem preços) |
| `docs/benchmark-pacotes-porte.md` | Estudo de pacotes de contabilidades online por porte e fase da empresa (sem preços) |
| `assets/img/fabio-ilustracao.webp` | Personagem ilustrado do Fábio (contador responsável), sempre identificado como ilustração |

Todas as páginas com afirmação tributária citam a norma, trazem "Revisado em 13/10/2026" e a ressalva "Conteúdo informativo. Cada caso depende de atividade, faturamento e estrutura societária."

## Paleta

`#00102E` / `#001330` (marinho) · `#0056A7` / `#1863DC` (azul) · `#009DF6` (ciano) · fonte de títulos **Chivo**

## Pendências antes de publicar

- [ ] Avaliações do Google: a nota, o total de avaliações e os depoimentos com nome foram **retirados** do index (hero, seção de depoimentos e schema) em 13/10/2026. Só voltam com autorização escrita de cada cliente (NBC PG 01, sigilo) e conferência da nota no dia da publicação.
- [x] Responsável técnico: **Fábio Moraes — CRC RJ-118632/O-1**. Aparece no rodapé de todas as páginas, nos dados estruturados (`employee`), na legenda do personagem e no llms.txt.
- [x] "Atendimento rápido" e "contador de verdade" foram retirados (afirmação sem lastro e comparação indireta com colegas). O texto agora diz "atendimento por WhatsApp, telefone e e-mail em horário comercial".
- [ ] Informar o nome e o link do aplicativo de documentos usado pelo escritório. O bento do site fala dele de forma genérica.
- [ ] Revisar o cronograma da Reforma (EC 132/2023 e LC 214/2025) e a base legal do Fator R antes de cada publicação.
- [ ] Usar fotos reais da equipe e do escritório, se desejado. Hoje o site usa ilustrações em CSS e o personagem ilustrado do Fábio, com legenda e texto alternativo de "ilustração".
- [ ] Pacotes: o Fábio deve validar o escopo de cada pacote, em especial as obrigações do Lucro Presumido. Os honorários **nunca** vão para o site: só na proposta escrita (NBC PG 01).
- [ ] Pagamento: definir no modelo de proposta e contrato as condições de Pix e do parcelamento no cartão (número de parcelas, encargos). No site fica só "com opção de parcelamento", sem "sem juros" nem número de parcelas.
- [x] Contrato: assinatura definida — aceite no site + Assinador gov.br (ou ICP-Brasil). Pendências consolidadas na seção "Contrato" abaixo.
- [ ] Se for adicionar Google Analytics ou Meta Pixel, implementar o consentimento e atualizar a política de privacidade.

### Pendências registradas pelo gestor de qualidade (13/10/2026)

Itens que **não** foram publicados como fato ou que precisam de conferência antes de publicar:

- [ ] NBC PG 01: confirmar no portal do CFC a numeração e o título oficial ("Código de Ética Profissional do Contador").
- [ ] Reforma Tributária: o index e o guia descrevem o cronograma só de forma qualitativa (início em 2026, fim previsto em 2033). Alíquotas de teste, anos intermediários e regras de compensação foram retirados até conferência no texto da EC 132/2023 (ADCT) e da LC 214/2025.
- [ ] Fator R: limite de 28% e janela de 12 meses conferidos na LC 123/2006, art. 18, §§ 5º-J, 5º-K, 5º-M e 24 (a definição de folha com pró-labore está no § 24). Reconferir a cada publicação.
- [ ] Pró-labore: percentual de INSS e tributação da distribuição de lucros (Lei 9.249/1995, art. 10, e alterações posteriores, como a Lei 15.270/2025) não publicados. Conferir antes de detalhar.
- [x] Limites de porte conferidos no texto vigente da LC 123/2006 (planalto.gov.br, 13/10/2026) e publicados em `porte/`: MEI até R$ 81.000,00 no ano-calendário anterior (art. 18-A, § 1º); ME até R$ 360.000,00 (art. 3º, I); EPP acima de R$ 360.000,00 até R$ 4.800.000,00 (art. 3º, II). Reconferir a cada publicação.
- [ ] MEI: número de empregados e valor do DAS-MEI continuam não publicados (LC 123/2006, art. 18-A, e resolução do CGSN vigente).
- [ ] Lucro Presumido e Lucro Real: percentuais de presunção, limite de receita e prazos de obrigações acessórias não publicados. Normas citadas: Lei 9.249/1995, Lei 9.430/1996, Lei 9.718/1998 (arts. 13 e 14), Decreto-Lei 1.598/1977, Decreto 9.580/2018 e Decreto 6.022/2007.
- [x] Posicionamento por porte (diretriz do Fábio, 13/10/2026): o site não se vincula a nenhuma atividade. Os links para `segmentos/` foram retirados de menus, rodapés, "Leia também", sitemap, llms.txt e docs; a seção do index virou "Para cada porte de empresa" (`#porte`) e o 4º pacote virou "Empresa em crescimento" (Lucro Presumido). Contrato atualizado para a versão 1.1 (só o nome e o escopo genérico desse pacote).
- [x] Pasta `segmentos/` removida do repositório (13/10/2026). Se as URLs `/segmentos/*` chegaram a ser publicadas ou indexadas, configurar 301 para `/porte/` no servidor.
- [ ] Pacote "Empresa em crescimento": o Fábio deve validar o escopo genérico (IRPJ, CSLL, PIS, Cofins e tributos estaduais ou municipais conforme a atividade).
- [ ] Abertura de empresa: conferir JUCERJA, REDESIM (Lei 11.598/2007), registro da sociedade simples em cartório e a sociedade limitada unipessoal (Lei 13.874/2019).
- [ ] Área de atendimento: confirmar a frase "empresas de todo o Brasil" (index, llms.txt e página de Itaboraí). Nas páginas novas de serviços o texto diz "empresas de outras cidades".
- [ ] "Quem somos" (index): confirmar a frase sobre o fundador ("depois de anos em grandes escritórios") (responsável técnico já informado: Fábio Moraes, CRC RJ-118632/O-1).
- [ ] Rotina descrita nas páginas: reunião por vídeo, visita na sede com agendamento e envio de documentos por celular ou e-mail. Confirmar com o escritório. Horário de funcionamento e coordenadas geográficas não publicados.
- [ ] São Gonçalo: o portal oficial da prefeitura não respondeu na verificação. A página cita o portal sem link.
- [ ] Hospedagem: configurar o servidor para devolver o status HTTP 404 com o `404.html`.
- [ ] Antes de publicar: `node scripts/verificar-site.mjs` (0 erros) e `node --test tests/*.test.js`.

### Contrato: pendências consolidadas (revisão de qualidade de 13/10/2026)

Detalhes em `docs/contrato-notas-juridicas.md`, seção 5.

- [x] Razão social: **MORAES E OLIVEIRA CONTABILIDADE LTDA** (sociedade limitada) — no contrato, no cabeçalho do PDF, nos rodapés e no `legalName` do JSON-LD.
- [x] Responsável técnico: **Fábio Moraes, sócio e contador, CRC RJ-118632/O-1** — no preâmbulo e no `jobTitle` do JSON-LD.
- [ ] **Valores entre colchetes** no contrato (prazos, multa, reajuste, aviso prévio, teto de indenização, prazos do Anexo II): P4 a P15 e D8 das notas jurídicas. Enquanto não forem definidos, aparecem entre colchetes no texto aceito.
- [ ] **Nome e endereço da Plataforma** (Cl. 1.2 e Anexo I) — P3.
- [ ] **Certificado da contratada**: definir se o escritório assina com e-CNPJ ou com gov.br/e-CPF do Fábio, quem confere no validador do ITI e onde a via é arquivada — D1.
- [ ] **Anexo I (Proposta Comercial)**: criar o modelo com honorários, pagamento, reajuste, vigência e início. Honorários só nele, nunca no site (NBC PG 01).
- [ ] **Revisão por advogado inscrito na OAB** antes do uso (P19), em especial as Cl. 11, 12, 14 e 24.
- [ ] **Limitação do site estático** (P21): o site não tem servidor — não recebe arquivos, não registra IP, não envia e-mail e não guarda o aceite. O registro e o PDF assinado só chegam se o cliente os enviar (WhatsApp ou e-mail). O escritório deve **confirmar o recebimento** de cada aceite pelo mesmo canal e arquivar a mensagem e o PDF assinado.
- [ ] Modelos operacionais: Carta de Responsabilidade, distrato, comunicação ao novo responsável técnico, notificação de suspensão (D6).
- [ ] Qualquer mudança no texto: alterar `versao` em `assets/js/contrato-modelo.js`, espelhar em `docs/contrato-modelo.md` e rodar `node scripts/gerar-contrato.mjs` e os testes.

### Pendências de SEO e publicação

- [ ] Google Search Console e Bing Webmaster Tools: verificar o domínio e enviar o `sitemap.xml`.
- [ ] Perfil da Empresa no Google com o NAP idêntico ao do site: Av. Vinte e Dois de Maio, 4845, Sala 908 - Rio Várzea, Itaboraí/RJ, CEP 24812-086 · (21) 99880-6423. Repetir o mesmo NAP nas redes e diretórios.
- [ ] Servidor: redirecionamento 301 de http e de www para https://moraeseoliveiracontabil.com.br/.
- [ ] Medir no PageSpeed Insights após publicar; avaliar hospedar as fontes localmente.
- [ ] Validar o volume de busca das palavras-chave de `docs/seo-relatorio.md`.
- [ ] Buscar backlinks locais legítimos (associação comercial/CDL de Itaboraí, entidades contábeis, parceiros, imprensa local).

### Validação do fechamento (13/10/2026)

- `node --test tests/*.test.js`: 9 de 9 testes passam (calculadoras e contrato).
- `node scripts/verificar-site.mjs` (após a troca de segmentos por porte e a remoção de `segmentos/`): 20 páginas, 0 erros. Avisos: `R$` nos rótulos das calculadoras e nos limites de porte da LC 123/2006 em `porte/`, e "garant" em sentido jurídico no contrato (ex.: "não garante funcionamento ininterrupto") — não são promessa de resultado.
- Contratação (13/10/2026, Playwright/Chromium, 1440 px e 390 px com movimento reduzido): fluxo completo sem erro de console e sem rolagem horizontal; assinatura bloqueada antes de 100% de leitura; foco inicial no texto do contrato; Esc fecha e devolve o foco ao botão; PDF gerado com o hash e a razão social.
- Playwright (Chromium) em 1440 px e 390 px, todas as 18 páginas: sem erro de console, sem recurso ou link interno com 404, sem âncora inexistente e sem rolagem horizontal.
- Todos os blocos JSON-LD fazem parse.
- Revisão de qualidade do posicionamento por porte (13/10/2026, Playwright/Chromium, 1440 px e 390 px): index e as 6 páginas de `porte/` sem erro de console, sem rolagem horizontal, links internos com status 200 e âncoras existentes; fluxo de contratação com o pacote "Empresa em crescimento" até a abertura do contrato (versão 1.1). Em `porte/`: um H1 por página, nota legal com a norma, "Revisado em 13/10/2026" e a ressalva padrão, FAQPage igual aos `summary` visíveis.

### Ocorrências justificadas na varredura de termos

- `R$` no index: aparece apenas nos rótulos dos campos das calculadoras, como unidade de entrada. Não há preço nem honorários no site.
- `R$` em `porte/` e no llms.txt: apenas os limites de receita bruta da LC 123/2006 (MEI, ME e EPP), com o artigo citado.
- Nenhuma ocorrência de grátis, gratuito, desconto, promoção, melhor, nº 1, número 1, garant, econom, últimas vagas ou Franklin em `.html` e `.txt`.

### Pacotes por porte (13/10/2026)

- [ ] O Fábio deve validar o escopo dos 5 pacotes (Começando, MEI, Microempresa, Empresa de Pequeno Porte, Empresa em crescimento) e os gatilhos de "Quando mudar de pacote".
- [ ] Pacote Começando: definir como o acompanhamento dos 12 primeiros meses entra na proposta (Cláusula 15.3 do contrato, versão 1.2).
- [ ] Rever os limites de porte (LC 123/2006) a cada publicação: MEI R$ 81 mil, ME R$ 360 mil, EPP R$ 4,8 milhões.
