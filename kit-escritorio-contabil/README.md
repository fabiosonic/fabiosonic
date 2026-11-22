# Kit OpenBot para escritório de contabilidade

```
agentes/   instruções prontas de 6 agentes (cole no OpenBot)
skills/    6 skills técnicas (CPC, Simples, Reforma, conciliação, obrigações, atendimento)
proxy/     proxy opcional: vários modelos gratuitos e Claude Haiku 5.5 por último
```

O OpenBot é um app de desktop com "colegas de IA". Cada agente tem nome, instruções, modelo e uma pasta de trabalho própria, e os agentes conversam entre si e passam tarefas uns para os outros. A configuração é feita **na interface do app**. Este guia traz o passo a passo e os textos prontos para colar.

> ⚠️ **Licença:** o uso pessoal é gratuito, mas a licença do OpenBot (PolyForm Noncommercial) **não cobre uso comercial**. Um escritório de contabilidade precisa da *Work license*. Segundo a página de preços, ela está **gratuita até 1º/12/2026** e depois custa a partir de €10/mês (Starter) ou €25/mês (Team, 2 membros). Ative em **Settings → Billing** antes de usar com clientes.

> ⚠️ **Segurança:** depois do consentimento inicial, os agentes do OpenBot rodam com acesso total (leem e alteram arquivos e executam comandos **sem pedir confirmação a cada ação**). Por isso:
> - use um **usuário do Windows exclusivo** para o OpenBot, ou deixe nele apenas as pastas de clientes necessárias;
> - **não** guarde certificados digitais A1 (.pfx) nem planilhas de senhas nesse usuário;
> - mantenha backup diário das pastas de clientes.

---

## 1. Instalação (Windows 10/11 x64)
1. Baixe em https://openbot.run/download/windows e execute o `OpenBot-*-x64.exe`.
2. Se o SmartScreen avisar: **Mais informações**, confira se o editor é **SYNTHETIFY LABS** e clique em **Executar assim mesmo**.
3. Instale o **Git for Windows** (https://git-scm.com), que o provedor Claude Code exige.

## 2. Provedores: gratuitos primeiro, Claude Haiku 5.5 por último

No assistente inicial (ou em **Settings → Providers**), conecte nesta ordem:

| Ordem | Provedor no OpenBot | Custo | Como conectar |
|---|---|---|---|
| 1 | **OpenCode** (modelos gratuitos) | grátis, sem conta | Clique em **Download/Add** na linha OpenCode |
| 2 | **Ollama** (local) | grátis, dados ficam no PC | Instale o https://ollama.com e rode `ollama pull qwen2.5:14b`. O OpenBot detecta em "Found on this computer". **Aumente o contexto do Ollama para pelo menos 64.000 tokens** e use um modelo com *tool calling* |
| 3 | **Servidor compatível com OpenAI** (opcional) | grátis | Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/`. Groq: `https://api.groq.com/openai/v1`. OpenRouter: `https://openrouter.ai/api/v1`. Em todos, use a sua chave |
| 4 | **Claude Code** → modelo **Haiku 5.5** | assinatura Claude (Pro/Max) | Clique em **Download** na linha Claude Code (ou instale o CLI `claude` e faça login), reinicie o OpenBot e escolha **Haiku** no seletor de modelos |

### Fallback (modelo reserva)
O OpenBot informa que o agente **muda para um modelo reserva** quando o plano atinge o limite ou o provedor cai, mantendo a conversa. Em cada agente:
- **Modelo principal:** um gratuito (OpenCode free, Ollama ou o servidor OpenAI-compatível).
- **Modelo reserva (backup):** **Claude Code / Haiku 5.5**.

> O site não documenta o nome exato desse campo. Procure "backup model" / "modelo reserva" nas configurações do agente ou no seletor de modelos.

### Alternativa mais robusta: proxy com várias camadas gratuitas
Se quiser que **vários** gratuitos sejam tentados antes do Haiku (Gemini → Groq → OpenRouter → Ollama → Haiku):
1. `python -m pip install "litellm[proxy]"`
2. Rode `.\proxy\iniciar-proxy.ps1` (na 1ª vez ele abre o `.env` para você colar as chaves; rode de novo) (deixe a janela aberta).
3. No OpenBot, adicione o **servidor compatível com OpenAI** com endereço `http://127.0.0.1:4000/v1`, chave `sk-escritorio-local` e modelo `contabil` (ou `contabil-sigiloso` para dados de clientes).

Nessa opção, o último degrau é o Haiku pela **API da Anthropic** (créditos pagos, separados da assinatura).

## 3. Crie a equipe de agentes
Em **New agent**, cole o texto do arquivo correspondente em `agentes/` como instruções do agente:

| Agente | Arquivo | Modelo sugerido |
|---|---|---|
| 🧑‍💼 **Coordenador** (recebe pedidos e distribui) | `agentes/00-coordenador.md` | gratuito → Haiku |
| 📒 **Contábil** (CPC, lançamentos, conciliação, fechamento) | `agentes/01-contabil.md` | Ollama (sigiloso) → Haiku |
| 🧾 **Fiscal/Tributário** (Simples, Presumido, Real, Reforma) | `agentes/02-fiscal.md` | gratuito → Haiku |
| 👥 **Departamento Pessoal** (folha, eSocial, FGTS Digital) | `agentes/03-dp.md` | Ollama (sigiloso) → Haiku |
| 💬 **Atendimento** (rascunhos para clientes) | `agentes/04-atendimento.md` | gratuito → Haiku |
| 💻 **Automações** (scripts Python, importação para o ERP) | `agentes/05-automacoes.md` | gratuito → Haiku |

Crie um **canal** "Escritório" com todos os agentes para que o Coordenador delegue as tarefas.

## 4. Skills (conhecimento técnico)
Em **Settings → Skills → Local skills**, adicione as pastas de `skills\` (cada uma tem um `SKILL.md`):
`lancamentos-cpc`, `simples-nacional`, `reforma-tributaria`, `conciliacao-bancaria`, `obrigacoes-acessorias`, `atendimento-cliente`.

## 5. Rotinas sugeridas
| Gatilho | Agente | Tarefa |
|---|---|---|
| Toda segunda, 8h | Fiscal | Montar a agenda de obrigações da semana por cliente (conferindo a agenda da RFB) |
| Dia 1º de cada mês | Atendimento | Rascunhar a cobrança de documentos do fechamento para cada cliente |
| Dia 5 de cada mês | Contábil | Checklist de fechamento: conciliações pendentes, provisões, depreciação |
| Toda sexta, 16h | Coordenador | Resumo da semana: o que foi entregue, o que está pendente e os riscos |

Coloque uma **etapa de aprovação** antes de qualquer envio a cliente.

## 6. Pastas
Coloque os documentos de cada cliente na pasta compartilhada do OpenBot (por exemplo `~/OpenBot/Shared/clientes/<cliente>/<AAAA-MM>/`). Confira o caminho exato no app.
