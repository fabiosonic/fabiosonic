# WhatsApp: configuração

## Opção recomendada: API oficial (WhatsApp Business Cloud)

1. Em [business.facebook.com](https://business.facebook.com), crie (ou use) a conta empresarial do escritório e verifique a empresa.
2. Em [developers.facebook.com](https://developers.facebook.com), crie um app do tipo **Business** e adicione o produto **WhatsApp**.
3. Cadastre o número comercial. Ele não pode estar em uso no aplicativo WhatsApp comum.
4. Gere um **token permanente** (usuário do sistema com permissão `whatsapp_business_messaging`).
5. No `.env`:
   ```
   WHATSAPP_PROVEDOR=cloud
   WA_CLOUD_TOKEN=...
   WA_CLOUD_ID_NUMERO=...           # Phone number ID
   WA_CLOUD_TOKEN_VERIFICACAO=...   # texto inventado por você
   WA_CLOUD_SEGREDO_APP=...         # App secret (valida a assinatura dos webhooks)
   ```
6. **Webhook:** no app, em WhatsApp › Configuração:
   - URL de retorno: `https://SEU_DOMINIO/webhooks/whatsapp`;
   - token de verificação: o mesmo de `WA_CLOUD_TOKEN_VERIFICACAO`;
   - assine o campo `messages`.
7. **Modelo de primeiro contato.** Cadastre em Gerenciador do WhatsApp › Modelos (categoria **Marketing**, idioma pt_BR) com o nome `primeiro_contato_escritorio`:

   > Olá, {{1}}! Aqui é da {{2}}. {{3}} Podemos conversar? Se preferir não receber mensagens, responda PARAR.

   - `{{1}}`: primeiro nome do sócio;
   - `{{2}}`: nome do escritório;
   - `{{3}}`: frase personalizada que a IA escreve para cada lead.

   Depois da aprovação, defina `WA_NOME_MODELO=primeiro_contato_escritorio`.

**Avisos para você.** Para receber os avisos de "lead quer falar com você" no seu WhatsApp pela API oficial, mande um "oi" para o número da empresa uma vez por dia (abre a janela de 24 h). Outra opção é criar um segundo modelo do tipo **Utilidade** só para avisos. O aviso por e-mail chega sempre.

## Opção alternativa: Evolution API (não oficial)

Usa um número comum, conectado por QR Code. **Viola os termos do WhatsApp e o número pode ser banido.** Se usar, use um número separado e volume baixo.

```
WHATSAPP_PROVEDOR=evolution
EVOLUTION_URL=http://localhost:8080
EVOLUTION_CHAVE_API=...
EVOLUTION_INSTANCIA=comercial
EVOLUTION_TOKEN_WEBHOOK=um-token-seu
```

Na Evolution, configure o webhook `https://SEU_DOMINIO/webhooks/evolution?token=um-token-seu` com os eventos `MESSAGES_UPSERT` e `MESSAGES_UPDATE`.
