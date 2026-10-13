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
| `index.html` | Página principal: hero, como funciona, serviços, plataforma, segmentos, Reforma, ferramentas, quem somos, avaliações, FAQ, contato |
| `assets/css/style.css` | Tokens da marca, layout, animações, responsivo, movimento reduzido, impressão |
| `assets/js/calculadoras.js` | Regras das calculadoras em funções puras, testadas |
| `assets/js/main.js` | Interações: reveal, abas, menu, partículas, palavra rotativa, formulário |
| `politica-de-privacidade.html` | Política conforme o funcionamento real do site (LGPD) |
| `links.html` | Página de links para a bio, com UTMs |
| `docs/benchmark-contabilidade-digital.md` | Engenharia reversa de 22 sites de contabilidade digital |

## Paleta

`#00102E` / `#001330` (marinho) · `#0056A7` / `#1863DC` (azul) · `#009DF6` (ciano) · fonte de títulos **Chivo**

## Pendências antes de publicar

- [ ] Confirmar autorização dos clientes citados nas avaliações (NBC PG 01, sigilo) e atualizar a nota e o total do Google.
- [ ] Informar nome e CRC do **responsável técnico** para o rodapé.
- [ ] Guardar a comprovação do "atendimento rápido em horário comercial" (NBC PG 01, item 13).
- [ ] Informar o nome e o link do aplicativo de documentos usado pelo escritório. O bento do site fala dele de forma genérica.
- [ ] Revisar o cronograma da Reforma (EC 132/2023 e LC 214/2025) e a base legal do Fator R antes de cada publicação.
- [ ] Usar fotos reais da equipe e do escritório, se desejado (hoje o site usa apenas ilustrações em CSS).
- [ ] Se for adicionar Google Analytics ou Meta Pixel, implementar o consentimento e atualizar a política de privacidade.
