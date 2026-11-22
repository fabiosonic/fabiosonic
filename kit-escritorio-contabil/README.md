# Kit Escritório Contábil com IA (OpenClaw + OpenClaude)

Este kit configura um agente de IA para trabalhar em um escritório de contabilidade:
- **Primeiro, LLMs gratuitas:** Gemini, Groq, OpenRouter e Ollama local.
- **Último recurso, Claude Haiku 5.5 (pago):** entra quando os gratuitos ficam sem cota ou sem crédito, ou caem.
- **Conhecimento técnico já incluído:** CPCs e NBC, Simples Nacional, Reforma Tributária (LC 214/2025), conciliação, obrigações acessórias e atendimento, com regras de LGPD e do Código de Ética.

| Ferramenta | Para quê | Fallback automático |
|---|---|---|
| **OpenClaw** (recomendado) | Assistente 24h com painel web e opção de WhatsApp/Telegram, memória e skills | Nativo (`agents.defaults.model.fallbacks`) |
| **OpenClaude** (opcional) | Agente de terminal para planilhas, scripts e arquivos | Via proxy LiteLLM incluso |

```
openclaw/      config (openclaw.json), instalador e alternância do modo sigiloso
openclaude/    proxy LiteLLM, instalador e inicializador
workspace/     "cérebro" comum: AGENTS.md, SOUL.md, USER.md, IDENTITY.md e skills/
```

## 1. Chaves de API
| Provedor | Custo | Onde criar |
|---|---|---|
| Google Gemini | grátis, com limite diário | https://aistudio.google.com/apikey |
| Groq | grátis, com limite por minuto | https://console.groq.com/keys |
| OpenRouter | modelos `:free` | https://openrouter.ai/keys |
| Ollama (local) | grátis, roda no seu PC (ideal com 16 GB+ de RAM) | https://ollama.com, depois `ollama pull qwen2.5:14b` |
| Anthropic (Haiku 5.5) | **pago**, com créditos de API | https://console.anthropic.com |

> Os créditos de API da Anthropic são **separados** da assinatura Claude Pro/Max. Defina um limite de gasto mensal no console.

## 2. Instalar o OpenClaw (Windows)
```powershell
cd kit-escritorio-contabil\openclaw
powershell -ExecutionPolicy Bypass -File .\instalar.ps1   # 1ª vez: cria o .env, preencha as chaves
powershell -ExecutionPolicy Bypass -File .\instalar.ps1   # 2ª vez: instala e configura
```
O script faz backup do `openclaw.json` e do workspace antes de substituir, copia as skills, roda `openclaw doctor` e instala o serviço. Painel: http://127.0.0.1:18789
Linux, macOS ou WSL2: `bash instalar.sh`.

Depois da instalação, preencha `~/.openclaw/workspace/USER.md` com os dados do escritório: UF, sistema contábil e perfil da carteira.

Para conferir os modelos: `openclaw models list --provider google`. Os nomes de modelos gratuitos mudam; se algum não aparecer, ajuste em `openclaw.json`.

## 3. Modo sigiloso (LGPD)
Os planos **gratuitos** de IA podem usar o que você envia para treinar modelos. Para extratos, folha, CPF/CNPJ e dados de clientes:
```powershell
.\modo-sigiloso.ps1          # Ollama local -> Haiku (nada passa pelos gratuitos na nuvem)
.\modo-sigiloso.ps1 -Normal  # volta para gratuitos -> Haiku
```

## 4. WhatsApp / Telegram (opcional)
Configure com `openclaw onboard` ou pelo painel. **Use `dmPolicy: "allowlist"` só com os números da equipe.** Nunca use `"open"`. Há um exemplo comentado no `openclaw.json`. Teste no painel antes de ligar o canal.

## 5. OpenClaude (opcional, terminal)
```powershell
cd kit-escritorio-contabil\openclaude
copy .env.exemplo .env   # preencha
powershell -ExecutionPolicy Bypass -File .\scripts\instalar.ps1
.\scripts\iniciar.bat            # modo normal
.\scripts\iniciar.bat -Sigiloso  # modo sigiloso
```

## Limitações importantes
- Modelos gratuitos erram mais em cálculo e no uso de ferramentas. **A conferência e a assinatura são sempre do contador responsável.**
- Legislação, alíquotas e prazos mudam. O agente foi instruído a citar a fonte e a mandar conferir nos sites oficiais.
- Sem sandbox, o agente pode acessar arquivos fora do workspace. Mantenha os documentos de clientes em `~/.openclaw/workspace/clientes/` e, se quiser isolamento, avalie `agents.defaults.sandbox`.
