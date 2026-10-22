# Plano: Open Finance no portal do escritório

> Data: 22/10/2026. Base: análise com o REA da página https://tecnospeed.com.br/plugbank/api-open-finance/
> (sem parâmetros de rastreamento), estudo da API (`docs/estudo-openfinance-tecnospeed.md`), arquitetura observada
> (`docs/rea-openfinance-tecnospeed-arquitetura.md`) e pacote `mo_openfinance/`.
>
> **Portal considerado:** Monitor de Obrigações (`mo_obrigacoes`, FastAPI + SQLAlchemy, branch
> `ccr-80dc22dc-51a6xx`). É o painel web com cadastro de empresas e com a obrigação **DOC_EXTRATOS**
> ("Extratos bancários (cliente)"), justamente a que o Open Finance passa a cumprir sozinho.

---

## 1. O que o REA encontrou na página

Execução: `rea analyze-web-bundle` (REA 6.7.0) sobre um Chromium headless na URL limpa, com 8 s de observação.

| Achado | Evidência | Conclusão |
|---|---|---|
| 28 scripts analisados, 0 falhas, 85.251 nós de AST | `completeness.status = complete` | Página analisada por inteiro |
| 0 rotas e 0 endpoints de aplicação | `observations.routes = []`, `endpoints = []` | **É só uma landing page.** O produto vive na API (`api.pagamentobancario.com.br`), já mapeada. |
| Candidatos `post_id` / `form_id` (baixa confiança) | `formData.get`, script de 18.957 bytes | Formulário de contato WordPress/Elementor (captação de lead) |
| Terceiros: GTM, Google Ads/reCAPTCHA, Meta, TikTok, Bing, LinkedIn, Hotjar, Leadster | hosts dos `<script src>` | Rastreamento de marketing. Nada disso existe no produto. |

O conteúdo da página acrescenta ao que já sabíamos:
- público-alvo: software houses **e** empresas com TI interna. O formulário tem o segmento "Contabilidade" e a opção "Não, mas tenho uma equipe de T.I. interna", então **o escritório pode contratar como integrador do próprio portal**;
- "integração ativa no mesmo dia da autorização", "sandbox imediato", "≤30 dias de zero a produção", suporte dev para dev;
- **servidor MCP nativo** para agentes de IA, útil numa fase 2 (consultar extratos pelo assistente interno);
- os números da página estão desatualizados ("+47" e "+35 bancos"). A central de ajuda lista 136 instituições, 68 delas para PJ.

## 2. Fluxo no portal

```
Analista (portal)                      Cliente (celular)                 TecnoSpeed / Pluggy
──────────────────                     ─────────────────                 ───────────────────
Empresa › Open Finance › "Conectar conta"
  informa banco/agência/conta ───────────────────────────────────────▶ POST /payer (1ª vez, statementActived)
                                                                        POST /account → accountHash + openfinanceLink
"Enviar link" (WhatsApp/e-mail) ──▶ abre link → widget Pluggy →
                                    escolhe banco → app do banco → autoriza
                                                                   ◀── webhook STATEMENT_OPENFINANCE
status da conta = ATIVA  ◀─────────────────────────────────────────────
worker (07h e 19h): solicitar_extratos (D-3..hoje, janela de 6 h) ──▶ POST /statement/openfinance
                                                                   ◀── webhook ..._PROCESSED (ou polling)
recolher_protocolos → transações no banco do mo_openfinance (idempotente)
  ├─ baixa automática da tarefa DOC_EXTRATOS da competência
  ├─ tela "Lançamentos": pendências de classificação + TXT para o Domínio
  └─ revogação/expiração → status INATIVA → cobrança do cliente com link novo
```

## 3. Mudanças no código do portal

### 3.1 Configuração (`.env`, `config.py`)
```
OPENFINANCE_PROVEDOR=tecnospeed            # ou pluggy
TECNOSPEED_CNPJ_SH=...  TECNOSPEED_TOKEN_SH=...  TECNOSPEED_AMBIENTE=homologacao
OPENFINANCE_WEBHOOK_SEGREDO=<32+ caracteres aleatórios>
OPENFINANCE_DB=data/openfinance.db         # banco do mo_openfinance (transações)
```

### 3.2 Modelo (`models.py`): uma tabela nova
```python
class ContaOpenFinance(Base):
    __tablename__ = "contas_openfinance"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    banco: Mapped[str] = mapped_column(String(3))          # COMPE ou código do conector (9xx)
    agencia: Mapped[str] = mapped_column(String(10))
    conta: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(12), default="BANK")   # BANK | CREDIT_CARD
    cartao_final: Mapped[str] = mapped_column(String(4), default="")
    account_hash: Mapped[str] = mapped_column(String(40), unique=True)
    link_consentimento: Mapped[str] = mapped_column(String(300), default="")
    openfinance_id: Mapped[str] = mapped_column(String(60), default="")
    status: Mapped[str] = mapped_column(String(12), default="PENDENTE")  # PENDENTE|ATIVA|INATIVA
    conta_contabil: Mapped[str] = mapped_column(String(20), default="")  # código reduzido no Domínio
    ultimo_extrato_ate: Mapped[date | None] = mapped_column(Date, nullable=True)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```
A configuração contábil da empresa (sócios, documentos de cliente/fornecedor com conta própria, contas de
juros/multa/desconto, regras de texto) fica em `Empresa.personalizacoes["openfinance"]`, no mesmo formato do
`exemplos/openfinance/config_empresa.json`, e é lida por `mo_openfinance.contabil.Configuracao`.

### 3.3 Rotas (`web/app.py`)
| Rota | Função |
|---|---|
| `GET /empresas/{id}` | Novo card "Open Finance": contas, status, último extrato, botões |
| `POST /empresas/{id}/openfinance/contas` | Cria payer (se preciso) e account na TecnoSpeed e grava o link |
| `POST /openfinance/contas/{cid}/enviar-link` | Envia o link pelo `Notificador` existente (e-mail + webhook WhatsApp) e registra `Evento` |
| `GET /empresas/{id}/openfinance/lancamentos?competencia=` | Pendências de classificação e prévia das partidas |
| `GET /empresas/{id}/openfinance/dominio.txt?competencia=` | Download do TXT, que marca as transações como exportadas |
| `POST /webhooks/openfinance` | Recebe os webhooks da TecnoSpeed (detalhes abaixo) |

**Webhook seguro.** A rota fica fora do HTTP Basic, mas exige o header `X-MO-Segredo`, cadastrado na TecnoSpeed
em `POST /notification` (`"headers": {"X-MO-Segredo": "..."}`) e comparado com `secrets.compare_digest`.
Ela responde 200 rápido e passa o corpo para `mo_openfinance.sincronizar.processar_webhook`, que já é
idempotente. Na TecnoSpeed, assinar `STATEMENT_OPENFINANCE`, `STATEMENT_OPENFINANCE_PROCESSED`,
`STATEMENT_OPENFINANCE_REVOKED` e `STATEMENT_OPENFINANCE_UPDATED`. Webhook só funciona em **produção**; em
homologação o worker faz polling.

### 3.4 Worker (`__main__.py`, comando `openfinance`)
Roda no mesmo agendamento do `sync`:
1. `solicitar_extratos(...)` para as contas ATIVAS. O limite de 6 h já é respeitado; o ideal é rodar às 07h e às 19h.
2. `recolher_protocolos(...)` como fallback do webhook.
3. **Baixa automática da DOC_EXTRATOS**: quando *todas* as contas ATIVAS da empresa têm protocolo SUCCESS com
   `dateEnd ≥ último dia da competência`, executar `dar_baixa(sessao, tarefa, agora, origem="openfinance")`.
   Isso ajusta a regra de `reabrir_baixa_automatica`, que hoje só reabre `origem="drive"`, para também reabrir
   quando uma conta for revogada antes de cobrir o mês.
4. Conta INATIVA: a cobrança diária ao cliente (já existente em `alertas.py`, no máximo uma a cada 3 dias)
   passa a mandar "renove a autorização do Open Finance: <link>" em vez de "envie o extrato".

### 3.5 Duas datas que não podem ser confundidas
- **Obrigação do cliente (DOC_EXTRATOS)**: cumprida quando os dados cobrem o mês. Com o Open Finance isso
  acontece em D+1 ou D+2, bem antes do dia 5.
- **Fechamento contábil da competência**: só depois de **D+7** (`contabil.fechamento_liberado`), porque o
  provedor ainda reprocessa transações removidas na origem. Antes disso, o TXT pode ser gerado, mas a tela avisa.

## 4. Contrato, LGPD e operação
- **Contrato de prestação de serviços**: cláusula autorizando o escritório a receber, pela TecnoSpeed/Pluggy,
  dados bancários compartilhados pelo cliente via Open Finance, com a finalidade (escrituração, conciliação,
  BPO), retenção e revogação (o cliente revoga no app do banco). Base legal LGPD: execução de contrato e
  cumprimento de obrigação legal da escrituração. O modelo de contrato do site (branch `ccr-ccc0afbf-rzorrt`,
  `contrato/condicoes-gerais.html`) deve receber essa cláusula.
- **Operador e controlador**: no contrato com a TecnoSpeed, exigir um DPA. Os dados de terceiros nas
  contrapartes (nome e CPF) também são dados pessoais tratados.
- **Acesso**: só analistas do contábil e do financeiro veem a tela de lançamentos, e cada exportação gera um `Evento` (auditoria).
- **Onboarding do cliente**: avisar que os dados aparecem em 6 a 24 h e que o consentimento expira ou pode ser revogado.

## 5. Fases

| Fase | Entrega | Pré-requisito |
|---|---|---|
| 0 | Contrato e credenciais de **homologação** TecnoSpeed (ou Pluggy) e cotação das duas | Comercial |
| 1 | Tabela, card da empresa, criação de conta e link, envio por WhatsApp/e-mail | Fase 0 |
| 2 | Worker com polling, gravação idempotente, baixa automática da DOC_EXTRATOS | Fase 1 |
| 3 | Tela de lançamentos, pendências e TXT para o Domínio (usa `mo_openfinance.contabil`) | Fase 2 + plano de contas por empresa |
| 4 | Produção: webhook com segredo, cobrança de renovação, cartão de crédito (CREDIT_CARD) | Contrato de produção |
| 5 | Opcional: MCP da TecnoSpeed para o assistente interno ("saldo e pendências da empresa X") | Fase 4 |

Depois de validado em homologação, o piloto deve começar com **3 a 5 empresas** que tenham bancos diferentes
(ex.: Itaú, Bradesco, Sicoob, Inter, Nubank PJ). Para cada uma, comparar o extrato Open Finance com o OFX do mesmo mês antes de desligar o OFX.
