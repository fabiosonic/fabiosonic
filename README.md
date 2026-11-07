# Moraes & Oliveira Contabilidade — Escritório com agentes de IA

Projeto de automação do escritório **Moraes & Oliveira Contabilidade** sobre o
[Paperclip](https://github.com/paperclipai/paperclip), uma plataforma de código aberto (licença MIT)
que organiza agentes de IA como uma empresa: organograma, metas, tickets, rotinas agendadas,
orçamento por agente e aprovações.

> **Premissa:** os agentes **preparam, conferem e sinalizam**. O contador responsável (CRC)
> **aprova, assina, transmite e comunica**. Nada com efeito fiscal, jurídico ou financeiro sai sem um humano.

## O que tem aqui

```
paperclip/moraes-oliveira-contabilidade/   ← pacote importável no Paperclip (formato agentcompanies/v1)
├── COMPANY.md                              metas e princípios do escritório
├── .paperclip.yaml                         modelos de IA, orçamentos, cargos e 17 rotinas (cron)
├── agents/        12 agentes (AGENTS.md = descrição do cargo e limites)
├── skills/        9 procedimentos técnicos compartilhados
└── projects/      6 projetos, 17 tarefas recorrentes e 6 tarefas de implantação
scripts/validar_pacote.py                   validador do pacote (rodar antes de importar)
docs/plano-implantacao.md                   implantação em 90 dias, custos e indicadores
docs/governanca-lgpd.md                     matriz de autonomia, LGPD, sigilo e riscos
```

## Organograma

```
Conselho (sócios e contadores responsáveis — humanos)
└── Diretor-Geral (CEO) ................................ Opus
    ├── Gerente de Operações Contábeis ................. Sonnet
    │   ├── Analista Fiscal (Simples, Presumido, Real, CBS/IBS)
    │   ├── Analista Contábil (conciliação, fechamento, ECD/ECF)
    │   ├── Analista de DP (folha, eSocial, Reinf, DCTFWeb, FGTS)
    │   └── Analista Societário e Legalização
    ├── Consultor Tributário (legislação, Reforma, planejamento) ... Opus
    ├── Controller de Prazos e Qualidade (revisão quatro olhos) ..... Opus
    ├── Atendimento ao Cliente (triagem, cobrança de documentos) .... Haiku
    ├── Marketing e Comercial (conteúdo com compliance CFC)
    ├── Financeiro Interno (honorários, inadimplência)
    └── Engenheiro de Automação (scripts de XML, OFX e importação)
```

## Ciclo mensal automatizado

| Quando | Rotina | Agente |
|---|---|---|
| Dias úteis 07:40 | Monitor de legislação | Consultor Tributário |
| Dias úteis 08:10 e 13:40 | Triagem de solicitações | Atendimento |
| Segunda | Painel de prazos, briefing dos sócios, pauta de conteúdo | Controller, CEO, Marketing |
| Sexta | Revisão de qualidade (amostragem) | Controller |
| Dia 1 | Atualizar calendário + cobrança de documentos | Consultor + Atendimento |
| Dia 3 | Fechamento de DP (folha, eSocial, Reinf, DCTFWeb) | Analista de DP |
| Dia 5 | Conciliação bancária | Analista Contábil |
| Dia 6 / 8 | Apuração do Simples / Presumido e Real | Analista Fiscal |
| Dia 12 | Honorários e inadimplência | Financeiro Interno |
| Dia 15 | Fechamento contábil e balancete | Analista Contábil |
| Dia 27 | Relatório gerencial | CEO |
| 2/dez · 2/jan · 2/abr | Planejamento tributário · DEFIS/DASN/IRPF · ECD/ECF | Consultor / Controller |

## Instalação rápida

Requisitos: **Node.js 24.11+**, Claude Code instalado e autenticado na máquina, e Python 3 (para o validador e o login por assinatura).

```bash
# 1. Validar o pacote
pip install pyyaml
python3 scripts/validar_pacote.py

# 2. Instalar e iniciar o Paperclip (interface em http://localhost:3100)
npx paperclipai@latest onboard --yes

# 3. Simular a importação e depois importar
npx paperclipai company import ./paperclip/moraes-oliveira-contabilidade --target new --dry-run
npx paperclipai company import ./paperclip/moraes-oliveira-contabilidade --target new
```

Agentes e rotinas importados **começam pausados**. Ative por fases, conforme `docs/plano-implantacao.md`.
Depois de importar, configure no painel a **pasta de trabalho** (workspace) de cada projeto, apontando para
o diretório de documentos dos clientes. Caminhos de máquina não vão no pacote, por segurança.

## Ajustes recomendados antes de ativar

1. Revisar os **orçamentos** em `.paperclip.yaml` (hoje um teto de US$ 345/mês somando todos os agentes).
2. Fazer a 1ª revisão do **calendário de obrigações** (tarefa de implantação 05), incluindo regras da UF e do município.
3. Documentar os **layouts de importação** do sistema contábil (tarefa 03).
4. Aprovar a **matriz de autonomia e LGPD** (tarefa 06).
