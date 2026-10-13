# Arquitetura e decisões de projeto

## 1. Da engenharia reversa ao projeto

A [pesquisa](pesquisa-sistemas-obrigacoes.md) analisou Acessórias, Domínio/Onvio Processos (ex-Gestta), Nibo Obrigações,
Omie.G-Click, Questor Zen/Quiu, Alterdata eContador e Jettax 360. Todos seguem o mesmo modelo central:

```
Empresa → perfil/regime → Obrigação (regra de prazo) → Tarefa por competência → Documento comprobatório
```

Em nenhum deles a baixa vem de uma consulta ao e-CAC. A entrega é dada como feita quando aparece um **documento** que
o sistema consegue casar com a tarefa pendente pelo trio **(CNPJ + tipo de obrigação + competência)**.

| O que os líderes fazem | Como fizemos aqui |
|---|---|
| Templates de PDF por âncora textual ou código de receita (Nibo, G-Click ValidaPDF, Domínio Express, e-Contínuo) | `reconhecimento` em cada obrigação do catálogo: regex de conteúdo, conteúdo obrigatório, exclusões, nome e pasta. DARFs são diferenciados pelo **código de receita** (8109/2172 → PIS/COFINS; 2089/2372 → IRPJ/CSLL; 1082… → DCTFWeb). |
| Fila de conferência para casos ambíguos (cartões verde/amarelo/"não encontrado" do Domínio Express) | Pontuação de 0 a 100. Abaixo de 50 ou em empate técnico, o documento vai para **Documentos → Para revisar**, que mostra os candidatos. |
| Agente desktop vigiando pasta, só Windows (Nibo Assistente, G-Click InNubem) | Leitura **direta da API do Google Drive** com conta de serviço, sem nada instalado nas máquinas. Uma pasta local sincronizada também é suportada (`MO_DRIVE_BACKEND=local`). |
| Padrão rígido de nome de arquivo (G-Click) | O nome é só um dos sinais. O principal é o conteúdo. O nome sozinho vale apenas para PDF sem texto (digitalizado). |
| Regras de perfil E/OU/Exceto (G-Click) | `aplicabilidade` com `regimes`, `exige` (E), `exige_algum` (OU), `nao_exige` (exceto) e `qualquer` (alternativas), além de exceções por empresa (incluir, ignorar, dia próprio). |
| Prazo: dia fixo ou n-ésimo dia útil, deslocamento de mês, antecipa/posterga | `calendario.calcular_vencimento`: `dia_fixo`, `dia_util`, `ultimo_dia_util`, `meses_apos`, `mes`/`anos_apos` para os anuais, `ajuste`. |
| Feriados estaduais e municipais ficam a cargo do escritório (lacuna em todos) | Feriados nacionais calculados (Páscoa, Carnaval, Corpus Christi, 20/11 pela Lei 14.759/2023), mais `FERIADOS_EXTRAS` e prazo próprio por empresa. |
| Indicadores de multa (Acessórias, Domínio) | Cada obrigação traz `base_legal` e `multa_referencia`. Os indicadores mostram pontualidade e risco por responsável, departamento e empresa. |
| Documentos do cliente com lembretes (Acessórias, G-Click) | Obrigações de tipo `recebimento` (extratos, XML, ponto) com **cobrança automática** por e-mail e webhook, limitada a uma a cada 3 dias. |
| **Ninguém** confere o CNPJ do documento contra a pasta | **Diferencial**: um documento com CNPJ de outro cliente é marcado como *divergente* e aponta a empresa correta. |

## 2. Componentes

```
mo_obrigacoes/
├── catalogo.py      Obrigações: aplicabilidade, prazo, base legal, multa, reconhecimento
├── calendario.py    Feriados, dias úteis, vencimentos, competências
├── agenda.py        Gera tarefas (empresa × obrigação × competência), de forma idempotente
├── classificador.py Pontua o arquivo contra as regras; extrai competência e CNPJ (com DV)
├── drive/
│   ├── google.py    API v3: navegação recursiva, Drives compartilhados, exportação de Google Docs
│   └── local.py     Pasta local (testes e Drive para computador)
├── monitor.py       Varredura incremental → classificação → conferência de CNPJ → baixa
├── alertas.py       Resumo diário (gestor e responsáveis), cobrança ao cliente, webhook
├── relatorios.py    KPIs e exportação CSV
├── pastas.py        Estrutura padrão de pastas no Drive
├── web/             Painel FastAPI + Jinja2 (HTTP Basic)
└── cli.py           init | importar | agenda | sync | alertas | worker | serve | demo
```

### Fluxo de um arquivo

1. A equipe ou o cliente salva o PDF em `Clientes/0002 - CLINICA.../2026/09 - Setembro/01 - Fiscal/`.
2. O `worker` lista os arquivos com `modifiedTime` maior que a última varredura e baixa o conteúdo.
3. O `classificador` encontra "Documento de Arrecadação de Receitas Federais" e o código 8109, chega a **PIS_COFINS** com
   100% de confiança e extrai do texto "Período de Apuração 30/09/2026", ou seja, a competência **2026-09**.
4. O CNPJ do PDF tem a mesma raiz do CNPJ da empresa da pasta, então o documento é aceito.
5. A tarefa PIS/COFINS 2026-09 (vencimento 23/10/2026, porque o dia 25 cai num domingo e o prazo é antecipado) recebe baixa:
   **entregue no prazo**. A data considerada é a de criação do arquivo no Drive.
6. O documento fica ligado à tarefa (link no painel e na matriz) e o evento é registrado na auditoria.

Para extrair a competência, a ordem de prioridade é: texto do documento, nome do arquivo, pasta `AAAA/MM` e, por último, o mês anterior à data do arquivo.

## 3. Pontos de atenção legais e técnicos

- **Prazos estaduais e municipais** (ICMS, EFD ICMS/IPI, ISS) vêm com padrões genéricos. Configure por empresa.
- **DIRF**: extinta a partir do ano-calendário 2025, por isso não está no catálogo.
- **DCTF mensal**: substituída pela DCTFWeb com o MIT desde a competência 01/2025.
- **Data da entrega**: o sistema usa a data em que o comprovante foi salvo no Drive. Se o recibo for salvo dias depois da
  transmissão, a tarefa pode aparecer "com atraso" sem ter havido atraso real. A recomendação é salvar o recibo no mesmo
  dia. A evolução prevista (item 4.1) usa a data do recibo oficial.
- **Feriados municipais** afetam o ISS: inclua-os em `FERIADOS_EXTRAS` ou ajuste o dia do vencimento.

## 4. Próximas evoluções sugeridas

1. **Integra Contador (SERPRO)**: consultar os recibos do PGDAS-D e da DCTFWeb e a situação fiscal direto na Receita, dando baixa
   pelo número do recibo e pela data oficial. Nenhum concorrente faz isso como mecanismo de baixa.
2. **OCR** (Tesseract ou Google Document AI) para PDFs digitalizados, hoje identificados só pelo nome e pela pasta.
3. **Divisão de PDFs com várias guias** (uma página por empresa), como no Multipages do e-Contínuo.
4. **Protocolo de ciência do cliente**: link rastreável com data, hora e IP de abertura, como faz a Acessórias, ou a Drive Activity API
   para saber quando o cliente abriu o arquivo.
5. **Meta interna** (ex.: entregar 2 dias úteis antes do prazo legal) e indicador de multa evitada ou incorrida.
6. **Editor de regras de reconhecimento pelo painel**, para a equipe ajustar layouts sem programar.
7. **Push via `changes.watch`** do Drive, no lugar do polling, para baixas em segundos.
