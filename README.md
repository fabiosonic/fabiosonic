# M&O Contábil DIGITAL

Site institucional e de captação do projeto digital da **Moraes e Oliveira Contabilidade** (Itaboraí/RJ, desde 2015). Cores e logotipo seguem a identidade de moraeseoliveiracontabil.com.br.

HTML, CSS e JavaScript puros, sem build e sem dependências em produção. Basta publicar a pasta em qualquer hospedagem estática.

```bash
python3 -m http.server 8000   # http://localhost:8000
node --test tests/*.test.js   # testes das calculadoras
```

## Estrutura

| Arquivo | Conteúdo |
|---|---|
| `index.html` | Página principal: hero, como funciona, serviços, plataforma, segmentos, Reforma (qualitativa, com link para o guia), ferramentas, quem somos, FAQ, contato |
| `servicos.html` | Serviços detalhados (contábil, fiscal, DP, legalização, planejamento tributário, consultoria financeira), adicionais com parceiros, FAQ |
| `contabilidade-itaborai.html` | Página da sede em Itaboraí: endereço, como chegar (mapa por link externo), atendimento presencial e digital |
| `atendimento-regiao-metropolitana-rj.html` | Atendimento em São Gonçalo, Niterói e Rio de Janeiro (uma seção por cidade, sem endereços fictícios) |
| `guias/index.html` | Hub de guias |
| `guias/fator-r.html` · `guias/pro-labore.html` · `guias/mei-para-me.html` | Guias tributários (LC 123/2006 e normas citadas) |
| `guias/abrir-empresa.html` · `guias/reforma-tributaria.html` | Abertura de empresa e Reforma Tributária (EC 132/2023, LC 214/2025) |
| `segmentos/index.html` | Hub de segmentos |
| `segmentos/prestadores-de-servico.html` · `comercio.html` · `atletas-e-esporte.html` · `lucro-presumido-e-lucro-real.html` | Páginas por segmento |
| `politica-de-privacidade.html` | Política conforme o funcionamento real do site (LGPD), com cabeçalho e rodapé padrão |
| `links.html` | Página de links para a bio, com UTMs (noindex, fora do sitemap) |
| `404.html` | Página de erro (noindex, fora do sitemap) |
| `sitemap.xml` · `robots.txt` | 16 URLs indexáveis com lastmod 2026-10-13; robots aponta para o sitemap |
| `llms.txt` | Resumo factual da entidade, respostas rápidas e lista de páginas para buscadores de IA |
| `assets/css/style.css` | Tokens da marca, layout, animações, responsivo, movimento reduzido, impressão |
| `assets/js/calculadoras.js` | Regras das calculadoras em funções puras, testadas em `tests/` |
| `assets/js/main.js` | Interações: reveal, abas, menu, partículas, palavra rotativa, formulário |
| `scripts/verificar-site.mjs` | Verificação estática: H1, title, description, canonical, JSON-LD, links internos, termos proibidos, nota legal, sitemap |
| `docs/benchmark-contabilidade-digital.md` | Engenharia reversa de 22 sites de contabilidade digital |
| `docs/seo-relatorio.md` | Relatório de SEO: palavras-chave por página e próximos passos |

Todas as páginas com afirmação tributária citam a norma, trazem "Revisado em 13/10/2026" e a ressalva "Conteúdo informativo. Cada caso depende de atividade, faturamento e estrutura societária."

## Paleta

`#00102E` / `#001330` (marinho) · `#0056A7` / `#1863DC` (azul) · `#009DF6` (ciano) · fonte de títulos **Chivo**

## Pendências antes de publicar

- [ ] Avaliações do Google: a nota, o total de avaliações e os depoimentos com nome foram **retirados** do index (hero, seção de depoimentos e schema) em 13/10/2026. Só voltam com autorização escrita de cada cliente (NBC PG 01, sigilo) e conferência da nota no dia da publicação.
- [ ] Informar nome e CRC do **responsável técnico** para o rodapé.
- [ ] Guardar a comprovação do "atendimento rápido em horário comercial" (NBC PG 01, item 13).
- [ ] Informar o nome e o link do aplicativo de documentos usado pelo escritório. O bento do site fala dele de forma genérica.
- [ ] Revisar o cronograma da Reforma (EC 132/2023 e LC 214/2025) e a base legal do Fator R antes de cada publicação.
- [ ] Usar fotos reais da equipe e do escritório, se desejado (hoje o site usa apenas ilustrações em CSS).
- [ ] Se for adicionar Google Analytics ou Meta Pixel, implementar o consentimento e atualizar a política de privacidade.

### Pendências registradas pelo gestor de qualidade (13/10/2026)

Itens que **não** foram publicados como fato ou que precisam de conferência antes de publicar:

- [ ] NBC PG 01: confirmar no portal do CFC a numeração e o título oficial ("Código de Ética Profissional do Contador").
- [ ] Reforma Tributária: o index e o guia descrevem o cronograma só de forma qualitativa (início em 2026, fim previsto em 2033). Alíquotas de teste, anos intermediários e regras de compensação foram retirados até conferência no texto da EC 132/2023 (ADCT) e da LC 214/2025.
- [ ] Fator R: limite de 28% e janela de 12 meses conferidos na LC 123/2006, art. 18, §§ 5º-J, 5º-K, 5º-M e 24 (a definição de folha com pró-labore está no § 24). Reconferir a cada publicação.
- [ ] Pró-labore: percentual de INSS e tributação da distribuição de lucros (Lei 9.249/1995, art. 10, e alterações posteriores, como a Lei 15.270/2025) não publicados. Conferir antes de detalhar.
- [ ] MEI: limite de faturamento e número de empregados não publicados (LC 123/2006, art. 18-A, e resolução do CGSN vigente).
- [ ] Lucro Presumido e Lucro Real: percentuais de presunção, limite de receita e prazos de obrigações acessórias não publicados. Normas citadas: Lei 9.249/1995, Lei 9.430/1996, Lei 9.718/1998 (arts. 13 e 14), Decreto-Lei 1.598/1977, Decreto 9.580/2018 e Decreto 6.022/2007.
- [ ] Atletas: confirmar quais dispositivos da Lei 9.615/1998 seguem em vigor após a Lei 14.597/2023 (Lei Geral do Esporte).
- [ ] Abertura de empresa: conferir JUCERJA, REDESIM (Lei 11.598/2007), registro da sociedade simples em cartório e a sociedade limitada unipessoal (Lei 13.874/2019).
- [ ] Área de atendimento: confirmar a frase "empresas de todo o Brasil" (index, llms.txt e página de Itaboraí). Nas páginas novas de serviços o texto diz "empresas de outras cidades".
- [ ] "Quem somos" (index): confirmar a frase sobre o fundador ("depois de anos em grandes escritórios") e, se for o caso, informar nome e CRC do responsável técnico.
- [ ] Rotina descrita nas páginas: reunião por vídeo, visita na sede com agendamento e envio de documentos por celular ou e-mail. Confirmar com o escritório. Horário de funcionamento e coordenadas geográficas não publicados.
- [ ] São Gonçalo: o portal oficial da prefeitura não respondeu na verificação. A página cita o portal sem link.
- [ ] Hospedagem: configurar o servidor para devolver o status HTTP 404 com o `404.html`.
- [ ] Antes de publicar: `node scripts/verificar-site.mjs` (0 erros) e `node --test tests/*.test.js`.

### Pendências de SEO e publicação

- [ ] Google Search Console e Bing Webmaster Tools: verificar o domínio e enviar o `sitemap.xml`.
- [ ] Perfil da Empresa no Google com o NAP idêntico ao do site: Av. Vinte e Dois de Maio, 4845, Sala 908 - Rio Várzea, Itaboraí/RJ, CEP 24812-086 · (21) 99880-6423. Repetir o mesmo NAP nas redes e diretórios.
- [ ] Servidor: redirecionamento 301 de http e de www para https://moraeseoliveiracontabil.com.br/.
- [ ] Medir no PageSpeed Insights após publicar; avaliar hospedar as fontes localmente.
- [ ] Validar o volume de busca das palavras-chave de `docs/seo-relatorio.md`.
- [ ] Buscar backlinks locais legítimos (associação comercial/CDL de Itaboraí, entidades contábeis, parceiros, imprensa local).

### Validação do fechamento (13/10/2026)

- `node --test tests/*.test.js`: 5 de 5 testes passam.
- `node scripts/verificar-site.mjs`: 18 páginas, 0 erros (avisos apenas de `R$` nos rótulos das calculadoras).
- Playwright (Chromium) em 1440 px e 390 px, todas as 18 páginas: sem erro de console, sem recurso ou link interno com 404, sem âncora inexistente e sem rolagem horizontal.
- Todos os blocos JSON-LD fazem parse.

### Ocorrências justificadas na varredura de termos

- `R$` no index: aparece apenas nos rótulos dos campos das calculadoras, como unidade de entrada. Não há preço nem honorários no site.
- Nenhuma ocorrência de grátis, gratuito, desconto, promoção, melhor, nº 1, número 1, garant, econom, últimas vagas ou Franklin em `.html` e `.txt`.
