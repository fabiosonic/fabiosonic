# Guia de implantação

## 1. Organização das pastas no Google Drive

A pasta **"Clientes"** fica num Drive compartilhado (recomendado) ou no "Meu Drive" do escritório, com uma subpasta por empresa:

```
Clientes/
  0001 - PADARIA BOM PAO LTDA/
    2026/
      09 - Setembro/
        01 - Fiscal/                  <- recibos e guias gerados pelo escritório
        02 - Contabil/
        03 - Pessoal/
        04 - Documentos do Cliente/   <- extratos, XML, ponto (o cliente deposita aqui)
      Anual/                          <- DEFIS, ECD, ECF, DASN-SIMEI...
```

O sistema cria essa estrutura pelo botão **"Criar estrutura de pastas"** na tela da empresa. A estrutura **não é obrigatória**:
o robô identifica o documento pelo conteúdo. A pasta serve só como dica de competência e de departamento quando o PDF não tem texto.

Compartilhe com cada cliente **apenas a pasta dele** (permissão de editor na pasta "04 - Documentos do Cliente" ou na pasta da empresa).

## 2. Conta de serviço do Google

1. Acesse <https://console.cloud.google.com/>, crie um projeto (ex.: `mo-obrigacoes`) e ative a **Google Drive API**.
2. Vá em *IAM e administrador → Contas de serviço*, crie uma conta e gere uma **chave JSON**.
   Salve em `credenciais/service-account.json`. **Não versione esse arquivo**, ele já está no `.gitignore`.
3. No Drive, compartilhe a pasta **"Clientes"** com o e-mail da conta de serviço (`...@...iam.gserviceaccount.com`):
   - **Leitor**: o sistema só monitora;
   - **Editor**: o sistema também cria a estrutura de pastas.
4. Copie o ID da pasta "Clientes" (o trecho da URL depois de `/folders/`) para `MO_DRIVE_ROOT_FOLDER_ID`.

> Google Workspace: alternativamente, habilite a *delegação em todo o domínio* para a conta de serviço com o escopo
> `https://www.googleapis.com/auth/drive` e informe `MO_GOOGLE_IMPERSONATE=usuario@seudominio.com.br`.

## 3. Configuração (`.env`)

Copie `.env.example` para `.env` e preencha. Principais variáveis:

| Variável | Uso |
|---|---|
| `MO_ADMIN_USER` / `MO_ADMIN_PASSWORD` | Login do painel (HTTP Basic). **Obrigatório em produção.** Publique atrás de HTTPS (Caddy, Nginx ou Cloud Run). |
| `MO_DRIVE_BACKEND` | `google` em produção; `local` para monitorar uma pasta sincronizada pelo Google Drive para computador. |
| `MO_SYNC_INTERVAL_MINUTES` | Intervalo entre varreduras (padrão 15). |
| `MO_DIAS_ALERTA_VENCIMENTO` | Antecedência do alerta "a vencer" (padrão 3). |
| `MO_SMTP_*`, `MO_EMAIL_GESTOR` | Envio dos resumos diários. Com Gmail ou Workspace, use uma *senha de app*. |
| `MO_COBRANCA_AUTOMATICA_CLIENTE` | `true` para cobrar o cliente por e-mail dos documentos atrasados. |
| `MO_WEBHOOK_URL` | Recebe JSON (`cobranca_cliente`, `resumo_atrasos`) para disparar WhatsApp via Z-API, Twilio ou n8n. |
| `MO_DATABASE_URL` | SQLite por padrão. Para PostgreSQL: `postgresql+psycopg://usuario:senha@host/banco` (instale `psycopg`). |

## 4. Carga inicial

```bash
python -m mo_obrigacoes init
python -m mo_obrigacoes importar minha_carteira.csv   # modelo em scripts/empresas_modelo.csv
```

Depois, no painel:

1. Em **Equipe**, cadastre os responsáveis.
2. Em **Empresas**, revise o perfil de cada cliente e vincule os responsáveis.
3. Em **Exceções por obrigação**, ajuste os prazos estaduais e municipais: ICMS, ISS e EFD ICMS/IPI variam por UF e município.
4. Em **Painel**, clique em **Gerar agenda** para a competência.
5. Clique em **Verificar Google Drive agora** para a primeira varredura completa (`python -m mo_obrigacoes sync --completo`).

## 5. Rotina automática

O `worker` roda continuamente:

- a cada `MO_SYNC_INTERVAL_MINUTES`: gera a agenda da competência anterior e da atual (é idempotente) e varre o Drive de forma incremental;
- uma vez por dia, a partir das 7h: envia o resumo ao gestor, as pendências a cada responsável e as cobranças aos clientes.

```bash
docker compose up -d        # sobe "web" (porta 8000) e "worker"
```

Sem Docker: rode `python -m mo_obrigacoes serve` e `python -m mo_obrigacoes worker` como serviços (systemd ou NSSM no Windows).
Também dá para usar o cron com `sync` a cada 15 minutos e `alertas` às 7h.

## 6. Rotina da equipe

1. Salve o recibo ou a guia em PDF na pasta do cliente. A baixa acontece sozinha na próxima varredura.
2. Uma vez por dia, abra **Documentos → Para revisar**:
   - **Não identificado**: escolha a obrigação e a competência e clique em OK;
   - **CNPJ de outra empresa**: mova o arquivo para a pasta certa no Drive;
   - **Fora do perfil**: o cliente tem uma obrigação que o cadastro não prevê. Atualize o perfil da empresa.
3. Mês sem movimento: em **Agenda**, use **Dispensar** e escreva a justificativa. Ela fica registrada na auditoria.

## 7. Segurança e LGPD

- O banco guarda só metadados, nunca o conteúdo dos documentos. O texto é lido em memória para classificar e depois descartado.
- A conta de serviço pode ficar como **leitora**. Revogue o acesso dela retirando o compartilhamento da pasta.
- Faça backup diário de `dados/` (SQLite) ou use PostgreSQL gerenciado.
- A trilha de auditoria (`/eventos`) registra quem baixou, dispensou ou reabriu cada tarefa.
