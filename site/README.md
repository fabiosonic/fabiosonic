# Site — Moraes & Oliveira Contabilidade

Site estático (HTML, CSS e JavaScript puros, sem dependências). Abre direto no navegador e pode ser publicado em qualquer hospedagem.

## Arquivos

| Arquivo | O que é |
|---|---|
| `index.html` | Página principal |
| `privacidade.html` | Política de privacidade (LGPD) |
| `css/styles.css` | Visual |
| `js/config.js` | **Dados do escritório** — contatos, CNPJ, CRC, redes, envio de leads |
| `js/calculators.js` | Regras das calculadoras e do diagnóstico |
| `js/main.js` | Interações |
| `assets/` | Logotipo |

## Como publicar

1. Envie o conteúdo da pasta `site/` para a hospedagem (raiz do domínio).
2. Se a hospedagem for o WordPress atual, publique em um subdomínio para testar antes de trocar.

## Captação de leads

- Sem configuração extra, os formulários abrem o WhatsApp do escritório com a mensagem pronta.
- Para **gravar** os leads (planilha, CRM), preencha `leadEndpoint` em `js/config.js` com um webhook que aceite POST JSON (n8n, Formspree, Make ou API própria).
- A tag do Google Ads (`googleAdsId`) só carrega depois que o visitante permite os cookies. O evento enviado é `generate_lead`.

## Pendências para conferir antes de publicar

- Confirmar os números publicados: 25 anos de experiência e +600 clientes (vieram do site atual; o escritório deve manter a comprovação — NBC PG 01, item 13).
- Confirmar autorização para os trechos de avaliações do Google (exibidos com primeiro nome e inicial).
- Preencher `razaoSocial`, `responsavelTecnico` e `crcResponsavel` em `js/config.js`.
- Preencher `horario` para ativar o status "online agora" e `areaDoCliente` se houver portal/app.
- Revisar o cronograma da Reforma Tributária a cada nova regulamentação.
- A condição de abertura de empresa ("pagando somente as taxas com contrato de 13 meses") não foi publicada como oferta, por cautela com a vedação de publicidade de preço/promoção; ela pode constar na proposta escrita.
