# Plano de implantação — 90 dias

## Fase 0 — Preparação (semana 1–2)

- [ ] Separar a máquina ou o servidor do Paperclip: computador dedicado no escritório ou servidor em nuvem no Brasil,
      com disco criptografado, backup diário e acesso restrito aos sócios e ao responsável de TI.
- [ ] Instalar Node.js 24.11+, Claude Code (autenticado) e Paperclip; importar o pacote (ver README).
- [ ] Criar a estrutura de pastas de documentos por cliente e competência: `CLIENTES/<COD>/<AAAA-MM>/{xml,extratos,folha,outros}`.
- [ ] Rodar as tarefas de implantação 01 (cadastro da carteira), 05 (calendário) e 06 (política LGPD).
- [ ] Desligar a telemetria se a política do escritório exigir: `PAPERCLIP_TELEMETRY_DISABLED=1`.

## Fase 1 — Piloto (semana 3–6): 5 clientes, modo sombra

Ative apenas: **CEO, Gerente de Operações, Analista Fiscal, Analista Contábil, Controller e Consultor Tributário**.

- Rotinas ligadas: monitor de legislação, apuração do Simples, conciliação bancária, painel de prazos e revisão semanal.
- **Modo sombra:** a equipe humana faz o trabalho normalmente; os agentes fazem em paralelo e os resultados são comparados.
- Critério para avançar: divergência zero nos tributos em 2 competências seguidas e retrabalho abaixo de 10%.

## Fase 2 — Expansão (semana 7–10): 30% da carteira

- Ativar: **Analista de DP, Atendimento (só rascunhos), Engenheiro de Automação e Financeiro Interno**.
- Entregar as automações 1 a 3 do engenheiro (leitor de XML, conciliador OFX, gerador de importação). Elas reduzem o custo de tokens.
- Os agentes passam a ser a **primeira versão** do trabalho; o humano revisa e aprova.

## Fase 3 — Escala (semana 11–13): carteira inteira

- Ativar **Marketing e Comercial**, Societário e as rotinas anuais.
- O Conselho decide quais categorias de mensagem podem ter envio automático (ex.: confirmação de recebimento).
- Revisar os orçamentos com base no gasto real das fases 1 e 2.

## Custos

| Item | Estimativa |
|---|---|
| Paperclip | Gratuito (código aberto, auto-hospedado) |
| Tokens de IA (teto configurado) | até **US$ 345/mês** somando os 12 agentes |
| Alternativa | Assinatura Claude (Max/Team) com o adaptador `claude_local` pela sessão autenticada; aí o custo é fixo por assento |
| Servidor | Máquina já existente ou servidor em nuvem com 4 vCPU e 8 GB |

Os tetos de orçamento são **limites**, não previsão: o agente pausa automaticamente ao atingir 100%.
O consumo cai à medida que o trabalho repetitivo vira script (Fase 2).

## Indicadores (relatório gerencial mensal)

| Indicador | Meta em 6 meses |
|---|---|
| Obrigações entregues no prazo | 100% |
| Multas por atraso | R$ 0 |
| Fechamento contábil até o dia 25 | 100% dos clientes |
| Retrabalho apontado na revisão | < 5% |
| 1ª resposta ao cliente | < 4 horas úteis |
| Horas humanas em tarefa repetitiva | −60% |
| Custo de IA por cliente/mês | acompanhar e reduzir mês a mês |
