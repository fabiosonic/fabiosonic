# Relatório de SEO: M&O Contábil DIGITAL

Gestor de SEO · revisado em 13/10/2026 · domínio canônico `https://moraeseoliveiracontabil.com.br/`

Este relatório registra o que foi feito para o site ser encontrado e entendido pelo Google, pelo Bing e pelos buscadores de IA. **Não há promessa de posição em resultados de busca.** O ranqueamento depende de fatores externos, como concorrência, autoridade do domínio e comportamento dos usuários.

Todos os dados da empresa usados nas páginas e nos dados estruturados vêm da lista de dados verificados: razão social, CNPJ, CRC, fundação em 2015, endereço, telefone, e-mail e redes. Nenhuma nota, avaliação, depoimento, número de clientes, horário ou coordenada foi publicado.

## 1. O que foi feito

### 1.1 Arquitetura e links internos

- **Menu do index:** Serviços (`servicos.html`), Segmentos (`segmentos/`) e Guias (`guias/`), além das âncoras da própria página.
- **Rodapé de todas as páginas:** Início, Serviços, Segmentos, Guias, Contabilidade em Itaboraí, Região Metropolitana do RJ e Política de Privacidade, com o NAP completo.
- **Seções do index com links contextuais:**
  - os cartões de segmento passaram a ser clicáveis e levam a cada página de segmento (o cartão inteiro é a área de clique, com foco visível);
  - "Ver todos os segmentos atendidos" e "Ver todos os serviços em detalhe";
  - Departamento pessoal → guia de pró-labore;
  - Legalização → guias de abertura de empresa e de MEI para ME;
  - calculadora do Fator R → guia do Fator R;
  - checklist de abertura → guia de abertura;
  - a seção da Reforma e o FAQ → guias correspondentes.
- **Ligação entre as páginas:** cada guia tem uma área "Leia também" e links para os serviços e segmentos relacionados. Cada segmento tem "Guias relacionados". As páginas locais apontam para serviços, segmentos e guias.
- **Breadcrumb visível** (`nav.breadcrumb` com `aria-current`) e `BreadcrumbList` em todas as páginas internas indexáveis. A Política de Privacidade passou a ter o mesmo cabeçalho, breadcrumb e rodapé das páginas novas.

### 1.2 Indexação

- O `sitemap.xml` lista as **16 URLs indexáveis**, todas com `lastmod` 2026-10-13. Ficam de fora `links.html` (página de bio, `noindex`) e `404.html` (`noindex, follow`).
- O `robots.txt` libera todo o site e aponta o sitemap. As páginas `noindex` continuam rastreáveis de propósito, porque o buscador precisa ler a tag `noindex`.
- Toda página indexável tem canonical absoluto no domínio canônico. Os diretórios usam a barra final (`/guias/`, `/segmentos/`).

### 1.3 Metadados por página

- `title` com até 60 caracteres e `meta description` com até 155, ambos únicos. O `scripts/verificar-site.mjs` confere esses limites.
- Open Graph em todas as páginas (`og:title`, `og:description`, `og:url`, `og:image` 1200×630, `og:locale` pt_BR, `og:site_name`) e `twitter:card` `summary_large_image`.

### 1.4 Dados estruturados (JSON-LD)

| Tipo | Onde | Observação |
|---|---|---|
| `AccountingService` (`@id` `/#organizacao`) | index e todas as páginas novas | O mesmo bloco em todas as páginas: endereço, telefone, e-mail, CNPJ (`taxID` e `identifier`), CRC, `foundingDate` 2015, `sameAs` com as 3 redes, `areaServed` |
| `WebSite` (`@id` `/#site`) | index | Os artigos e a Política o referenciam por `isPartOf` |
| `Article` com `datePublished`/`dateModified` 2026-10-13 | os 5 guias | Agora todos têm `@id`, `image`, `inLanguage` e `isPartOf`. Autor e publicador apontam para a organização, porque não há nome de pessoa verificado |
| `Service` | servicos.html e páginas de segmento | `provider` aponta para a organização |
| `CollectionPage` + `ItemList` | guias/ e segmentos/ | |
| `WebPage` | páginas locais e Política | |
| `FAQPage` | index, servicos, guias, segmentos e páginas locais | Só onde há FAQ visível. As perguntas são idênticas às dos `<summary>`, e o verificador confere isso |
| `BreadcrumbList` | todas as internas indexáveis | |

Não foram usados `AggregateRating`, `Review`, `openingHours`, `geo`, `priceRange` nem `Person`, porque não há dado verificado para nenhum deles.

### 1.5 SEO local

- **NAP idêntico** no rodapé e no schema de todas as páginas: *Moraes e Oliveira Contabilidade · Av. Vinte e Dois de Maio, 4845, Sala 908 - Rio Várzea, Itaboraí/RJ, CEP 24812-086 · (21) 99880-6423*. A grafia do endereço na Política de Privacidade foi padronizada: antes era "Sala 908, Rio Várzea".
- **`areaServed`** igual em todas as páginas: Itaboraí, São Gonçalo, Niterói, Rio de Janeiro (City) e Brasil (Country). Isso combina com o texto "sede em Itaboraí, atendimento digital".
- Páginas locais: `contabilidade-itaborai.html` (sede, como chegar, atendimento presencial e digital) e `atendimento-regiao-metropolitana-rj.html` (São Gonçalo, Niterói e Rio de Janeiro).

### 1.6 Otimização para buscadores de IA (AEO/GEO)

- Toda página nova abre com uma **resposta direta** (`p.answer`) logo abaixo do H1, que já é uma pergunta nos guias.
- Os H2 dos guias e dos segmentos foram reescritos **em forma de pergunta**, mantendo os mesmos `id`. Exemplos: "Como se calcula o Fator R?", "O que é distribuição de lucros?", "Quais documentos separar?". O primeiro parágrafo de cada seção responde à pergunta.
- Cada afirmação tributária traz a norma, "revisado em 13/10/2026" e a ressalva obrigatória.
- O `/llms.txt` descreve a entidade, lista todas as páginas com um resumo e traz respostas rápidas qualitativas, com norma, data de revisão e ressalva. Os textos foram alinhados ao que está publicado nos guias.

### 1.7 Desempenho

- Todas as imagens têm `width`/`height`, o que evita deslocamento de layout. O logo do cabeçalho tem `fetchpriority="high"`, e os logos fora da dobra têm `loading="lazy"`.
- Imagens leves: `logo-mo.webp` com 8 KB e `og-image.jpg` com 41 KB.
- Os scripts usam `defer` e só são carregados no index. As páginas internas não usam JS.
- Há `preconnect` para o Google Fonts, que carrega apenas os pesos usados, com `display=swap`. Não foi incluído `preload` extra: o único recurso de imagem crítico já tem `fetchpriority`, e um preload de fonte exigiria hospedar as fontes localmente (ver próximos passos).

## 2. Palavras-chave-alvo por página

Estes são termos de intenção, sem volume de busca medido (é preciso validar no Search Console ou no Planejador de Palavras-chave). A ideia é que cada página tenha um tema principal, para que as páginas do site não disputem o mesmo termo entre si.

| Página | Principal | Secundárias |
|---|---|---|
| `/` | contabilidade em Itaboraí | contabilidade digital RJ, escritório de contabilidade Itaboraí |
| `servicos.html` | serviços de contabilidade | departamento pessoal, planejamento tributário, legalização de empresa, holding familiar |
| `contabilidade-itaborai.html` | contador em Itaboraí | escritório contábil Itaboraí, abrir empresa em Itaboraí, contabilidade Rio Várzea |
| `atendimento-regiao-metropolitana-rj.html` | contabilidade em São Gonçalo | contador em Niterói, contabilidade online no Rio de Janeiro |
| `segmentos/` | contabilidade por segmento | contabilidade especializada |
| `segmentos/prestadores-de-servico.html` | contabilidade para prestadores de serviço | ISS, nota fiscal de serviço, Fator R para prestador |
| `segmentos/comercio.html` | contabilidade para comércio | contabilidade para loja, ICMS no comércio, substituição tributária |
| `segmentos/atletas-e-esporte.html` | contabilidade para atletas | direito de imagem de atleta, contador para jogador |
| `segmentos/lucro-presumido-e-lucro-real.html` | contabilidade Lucro Presumido | contabilidade Lucro Real, obrigações acessórias |
| `guias/` | guias de contabilidade para empresas | dúvidas de contabilidade |
| `guias/fator-r.html` | Fator R Simples Nacional | como calcular o Fator R, Anexo III ou Anexo V |
| `guias/pro-labore.html` | pró-labore e distribuição de lucros | INSS sobre pró-labore, retirada do sócio |
| `guias/mei-para-me.html` | MEI para ME | desenquadramento do MEI, MEI estourou o faturamento |
| `guias/abrir-empresa.html` | como abrir empresa | documentos para abrir empresa, abrir CNPJ |
| `guias/reforma-tributaria.html` | reforma tributária para empresas | CBS e IBS, reforma tributária e Simples Nacional |
| `politica-de-privacidade.html` | não se aplica (página institucional) | |

## 3. Próximos passos (para o escritório)

1. **Google Search Console:** verificar a propriedade de domínio (registro DNS TXT), enviar `https://moraeseoliveiracontabil.com.br/sitemap.xml` e acompanhar o relatório de Páginas, os Resultados aprimorados (FAQ, breadcrumb) e as consultas que trazem impressões. Repetir no **Bing Webmaster Tools**, que pode importar a configuração do Search Console.
2. **Perfil da Empresa no Google:** reivindicar ou verificar o perfil com o NAP **idêntico** ao do site, caractere por caractere: "Av. Vinte e Dois de Maio, 4845, Sala 908 - Rio Várzea, Itaboraí/RJ, CEP 24812-086" e "(21) 99880-6423". Usar a categoria de contabilidade adequada, o site no campo de URL e a área de atendimento compatível com o `areaServed`. Avaliações só devem ir para o site com autorização escrita de cada cliente (ver README).
3. **Consistência de citações:** usar o mesmo NAP no Instagram, no Facebook, no LinkedIn, no cadastro do CRC-RJ e em diretórios locais e de classe. Não criar cadastros com variações como "Avenida", "Sl." ou outro telefone.
4. **Backlinks locais legítimos:** associação comercial ou CDL de Itaboraí, entidades contábeis, parceiros (os advogados da assessoria jurídica), palestras ou capacitações sobre a Reforma Tributária e imprensa local com conteúdo informativo. Não comprar links nem trocar links em massa.
5. **Conteúdo:** publicar novos guias só depois de conferir a norma, sempre com a data de revisão e a ressalva. Atualizar `dateModified`, a data visível e o `lastmod` do sitemap a cada revisão real. Os temas pendentes estão no README (alíquotas da Reforma, limites do MEI, percentuais de presunção).
6. **Desempenho:** depois de publicar, medir no PageSpeed Insights (Core Web Vitals de campo). Considerar hospedar as fontes Chivo e Inter localmente (`woff2` com `preload`) para tirar a dependência do Google Fonts, o que também simplifica a Política de Privacidade.
7. **Servidor:** configurar o status HTTP 404 real para o `404.html`, fazer redirecionamento 301 de `http://` e de `www` para o domínio canônico, e definir se `/index.html` redireciona para `/`.
8. **Medição:** se for instalar Google Analytics ou Meta Pixel, implementar o consentimento antes e atualizar a Política de Privacidade (LGPD).
9. **Validação:** antes de cada publicação, rodar `node scripts/verificar-site.mjs` e `node --test tests/*.test.js` e testar algumas URLs no Teste de Pesquisa Aprimorada do Google.

Conteúdo informativo. Cada caso depende de atividade, faturamento e estrutura societária.
