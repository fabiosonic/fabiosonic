# E-mail: configuração e entregabilidade

## Conta

Use uma caixa **exclusiva do comercial** (ex.: `comercial@seudominio.com.br`) no Google Workspace, Microsoft 365, Zoho ou similar. O sistema envia por SMTP e lê as respostas por IMAP nessa mesma caixa.

| Provedor | SMTP | IMAP |
| --- | --- | --- |
| Google Workspace | `smtp.gmail.com:587` (senha de app) | `imap.gmail.com:993` |
| Microsoft 365 | `smtp.office365.com:587` | `outlook.office365.com:993` |
| Zoho | `smtp.zoho.com:587` | `imap.zoho.com:993` |

## Domínio (obrigatório para não cair no spam)

1. **SPF:** registro TXT autorizando o provedor (ex.: `v=spf1 include:_spf.google.com ~all`).
2. **DKIM:** ative no painel do provedor e publique a chave no DNS.
3. **DMARC:** comece com `v=DMARC1; p=none; rua=mailto:dmarc@seudominio.com.br` e endureça depois.

## Aquecimento

| Semana | E-mails/dia (Configurações › Cadência e limites) |
| --- | --- |
| 1 | 10 |
| 2 | 20 |
| 3 | 30 |
| 4+ | 40–60, se a taxa de resposta estiver saudável e não houver devoluções |

O sistema já espalha os envios ao longo do dia: um envio de prospecção por rodada, com intervalo mínimo configurável. Também respeita o horário comercial e coloca `List-Unsubscribe` em todas as mensagens, o que Gmail e Outlook exigem para remetentes em volume.
