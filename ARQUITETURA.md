# Arquitetura

## Visão geral

```
                    ┌───────────────────────────── Windows (escritório) ─────────────────────────────┐
  Navegador ───────▶│ FastAPI (127.0.0.1:8765)  ── painel React/TS (build estático em moxml/web)      │
                    │      │                                                                         │
                    │      ├── Agendador (APScheduler, America/Sao_Paulo, max_instances=1)           │
                    │      └── Orquestrador ── fila empresa × modelo (ThreadPool, isolamento)        │
                    │             │                                                                  │
                    │             ├── Conectores (interface comum) ──────────────┐                   │
                    │             │     sefaz_consulta   (NFeConsultaProtocolo)  │ mTLS com A1       │
                    │             │     svrs_portal_download (Portal DF-e SVRS)  │ do emitente       │
                    │             │     sefaz_sae_nfce   (SAE — só SP)           │                   │
                    │             │     pasta_emissor    (pastas do ERP/PDV)     │                   │
                    │             │     apisimples       (comercial, desligado)  │                   │
                    │             ├── Repositório: validação XML/XSD-lógica/assinatura, deduplicação │
                    │             ├── Armazenamento: 1-CLIENTES/CLIENTES ATIVOS/<EMPRESA>/XML/AAAA/MM │
                    │             ├── Auditoria de numeração (lacunas)                               │
                    │             └── Integrações: Google Drive (md5) · Domínio (pacote XML)         │
                    │  Cofre DPAPI (PFX/senhas) · PostgreSQL ou SQLite · logs rotativos               │
                    └────────────────────────────────────────────────────────────────────────────────┘
```

## Decisões e justificativas

| Decisão | Motivo |
|---|---|
| **Python 3.14 + FastAPI + SQLAlchemy 2 + Pydantic 2 + APScheduler 3** | Todas as dependências instalaram e passaram nos testes em **CPython 3.14.6** (ver TESTES.md). O instalador aceita 3.13/3.12 como contingência. |
| **Transporte SOAP próprio (httpx + lxml)** em vez de NFePHP/zeep | O SVRS exige apenas `nfeDadosMsg` em SOAP 1.2. Um transporte enxuto permite: mTLS com verificação obrigatória do servidor, retentativa só para falhas de rede, limitador por host, bloqueio de 1 h em cStat 656 e injeção de laboratório (`httpx.MockTransport`). O NFePHP não traz ganho para o RJ (o SAE é só de SP) e exigiria PHP no Windows. |
| **Conectores com interface comum** (`moxml/conectores/base.py`) | Métodos `verificar_disponibilidade`, `autenticar`, `listar_documentos`, `recuperar_xml`, `recuperar_eventos`, `consultar_situacao`, `sincronizar` e `consultar_limites`. O núcleo só conversa com a interface. UFs novas entram pelo catálogo (`catalogo_local.json`); provedores novos, por uma classe registrada em `criar_registro`. |
| **Catálogo de serviços em JSON**, com evidência | Impede "inventar endpoint": o que não está no catálogo é `INDISPONIVEL`, com o motivo documentado. |
| **Descoberta separada da recuperação** | A chave pode ser conhecida (J04/562, semente, cadastro manual, listagem SAE) sem que o XML esteja disponível. O sistema guarda `ChaveConhecida` e só conta "recuperado" quando o XML **integral validado** é gravado. |
| **Situação ≠ XML** | `Situacao` (consulta) atualiza status e eventos, mas nunca cria `Documento`. A classe `DocumentoXML.e_xml_integral` só é verdadeira para nfeProc autorizado/denegado, válido e com assinatura íntegra. |
| **XML imutável** | Os bytes recebidos são gravados como vieram. O único caso de composição é `montar_nfeproc` (NFe assinada do emissor + protNFe da SEFAZ, sem reformatação), o procedimento padrão de distribuição. |
| **Nunca sobrescrever** | Mesmo nome com conteúdo diferente gera `-v2`, `-v3`, tanto no disco quanto no Drive. Divergências ficam registradas como CONFLITO. |
| **Checkpoints e commit por chave** | Cada chave descoberta é persistida antes de avançar o checkpoint. Execuções interrompidas são marcadas `INTERROMPIDA` na subida e retomam sem perda (testado). |
| **Isolamento por empresa × modelo** | Cada tarefa tem sessão e `Execucao` próprias. Exceções não se propagam (testado). |
| **Janela sobreposta de eventos** | Documentos dos últimos 35 dias são re-consultados a cada 20 h (cobre CC-e de até 30 dias e cancelamentos extemporâneos). |
| **Modo SIMULADO vs REAL** | Em SIMULADO, todo transporte vai para o laboratório (`moxml/simulador`), registros ficam marcados `modo=SIMULADO` e o painel exibe uma faixa de alerta. Em REAL, sem certificado nada é consultado. |
| **Domínio** | Pacote de importação com os XMLs originais, em pasta plana por modelo, mais relatórios e manifesto SHA-256. A integração direta não foi validada, então não é simulada. |
| **Serviço Windows via Agendador de Tarefas** | Roda com o **mesmo usuário** que cifrou o cofre DPAPI, inicia com o Windows, reinicia em falha e funciona com o painel fechado. |

## Banco de dados (migrations em `backend/moxml/migrations`)

Tabelas:
- `empresas`, `certificados` (só referência ao cofre), `series`
- `documentos` (UNIQUE cnpj_emitente + ambiente + modelo + chave), `eventos` (UNIQUE chave + tipo + sequência + ambiente)
- `inutilizacoes`, `chaves_conhecidas`, `lacunas` (UNIQUE empresa + modelo + série + ambiente + número)
- `execucoes`, `logs_execucao`, `checkpoints`, `arquivos_drive`, `pastas_monitoradas`, `arquivos_importados`
- `conectores`, `registros_fonte` (auditoria de cStat), `configuracoes`

Índices extras: documento por (empresa, modelo, série, número) e por data de emissão.

## Fluxo diário (seção 8 do escopo)

1. Empresas ativas → 2. Certificado (validade + CNPJ) → 3. Séries ativas → 4. Pastas do emissor → 5. Descoberta (SAE onde existir; J04/562 na SVRS; comercial se ligado) → 6. Recuperação do XML integral (portal SVRS → SAE → comercial), completando o protocolo quando necessário → 7. Eventos → 8. Validação → 9. Deduplicação → 10. Banco → 11. Arquivos → 12. Google Drive (confirmação por md5) → 13. Relatório (Histórico/Logs) → 14. Pacote Domínio (sob demanda/mensal).
