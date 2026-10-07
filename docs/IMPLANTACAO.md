# Implantação no escritório — passo a passo

Ordem pensada para ligar a autonomia **aos poucos**, cada degrau com um critério objetivo.
Nada aqui mexe na caixa real, no `D:` ou no Domínio sem você decidir.

## Degrau 0 — Instalar (30 min)

1. Instale Python 3.12+ (python.org, marcar "Add to PATH") e Git.
2. Clone o repositório e rode:
   ```powershell
   cd "C:\Users\fabio moraes\mo_autonomo"
   powershell -ExecutionPolicy Bypass -File scripts\instalar_windows.ps1
   ```
   Critério: a instalação termina com `... passed` e cria `config\config.yaml` em **simulação**.

## Degrau 1 — Cadastro e perfis (1 dia)

1. Baixe do Drive a planilha **CONTROLE EMPRESAS POR REGIME** (xlsx) e rode
   `python -m mo_autonomo cadastro importar --planilha "CONTROLE EMPRESAS POR REGIME.xlsx"`
   → gera `config\empresas.csv` (o CÓD. da planilha vira código do Domínio — conferido para a LMG = 12).
   Depois rode `python -m mo_autonomo cadastro conferir-pastas --base "D:\XML NOTAS"` e ajuste a
   coluna `apelido` para bater com o nome das pastas `<Código-Apelido>` que já existem.
   O sistema recusa CNPJ inválido, regime fora da lista e apelido com `\ / : * ? " < > |`.
2. Baixe os zips dos **Dados Abertos do CNPJ** (Empresas, Estabelecimentos, Simples) para
   `dados\rfb\` e rode `python -m mo_autonomo perfil atualizar`.
3. Abra `dados\relatorios\perfis_AAAAMMDD.csv`. Cada `REGIME_DIVERGENTE` é um cliente com
   Domínio × Receita discordando: resolva no cadastro (ou confirme que a Receita está errada).

   Critério: zero `REGIME_DIVERGENTE`/`REGIME_DESCONHECIDO` nas empresas ativas.

## Degrau 2 — Conferir as normas que destravam a escrita fiscal (1 a 2 dias)

Para cada norma, na ordem: `python -m mo_autonomo normas conferir --id <ID>` gera
`dados\conferencia\<ID>.md` com o texto oficial e o bloco YAML a preencher. Você confere o
trecho literal e preenche `status: CONFERIDO`, `conferido_por`, `conferido_em`, `hash_texto`
e os `parametros` no arquivo `config\normas\*.yaml`.

1. `MOC_NFE` (sentido da NF-e, NFC-e, indTot, CRT, cancelamento, posições da chave)
2. `MOC_CTE` (tomador)
3. `DICIONARIO_DADOS_ABERTOS_CNPJ` (situação ativa, opção "S")
4. `TABELA_CFOP`
5. `LEIAUTE_NFSE_NACIONAL` e `LEIAUTE_NFSE_ABRASF` do município
6. `LEI_10833_ART30`, `TABELA_NCM_MONOFASICO`, `LC_123_2006`, `RES_CGSN_140_2018`
7. DP: `TABELA_INSS_SEGURADO`, `TABELA_IRRF_MENSAL`, `LEI_8036_FGTS`

Acompanhe com `python -m mo_autonomo normas cobertura`.
Critério: as regras fiscais aparecem `ATIVA` com natureza `APONTAMENTO`.

## Degrau 3 — Simulação com e-mail real (7 dias)

1. Rode `powershell -ExecutionPolicy Bypass -File scripts\configurar_email.ps1`. Ele procura
   servidor/porta nos arquivos de `D:\AUTOMAÇÕES FUNCIONANDO\email_backup` (sem mostrar
   linhas de senha), pede a confirmação, grava a senha no Cofre de Credenciais do Windows e
   ajusta o `config.yaml` (`email.tipo: imap`).
2. O próprio script roda `python -m mo_autonomo imap testar` — só lê (EXAMINE + BODY.PEEK).
3. Ative a tarefa **"MO Autonomo - Ciclo"** no Agendador (7h–20h).
4. Todo dia, abra `dados\painel.html` e os pareceres em `dados\pareceres\`.
5. No 7º dia: `python -m mo_autonomo amostra gerar --n 20`, marque CERTO/ERRADO no CSV e
   rode `python -m mo_autonomo amostra medir --arquivo <csv>`.

   Critério: 7 dias sem erro de execução no resumo e taxa de acerto ≥ a meta que você definir
   (sugestão: 99% em XML, 95% em PDF lido por IA).

## Degrau 4 — Aprovar à mão e conferir no Domínio (2 a 4 semanas)

1. Para cada lote: confira o parecer, rode
   `python -m mo_autonomo aprovar --lote dados\lotes\lote_X.json --usuario "Seu Nome"`,
   cole o hash e digite `APROVADO`.
2. Em **simulação** os XML vão para `dados\_STAGING\XML NOTAS`. Compare com o que você
   faria à mão.
3. Quando estiver confiante, peça a troca para `modo: producao` (grava em `D:\XML NOTAS`).
4. Exporte do Domínio o relatório de notas escrituradas e rode `auditar-dominio`
   (configure `dominio.relatorio_colunas`).

   Critério: um mês inteiro de um cliente piloto batendo com o fechamento manual.

## Degrau 5 — Aprovação por exceção (opcional)

No `config.yaml`:
```yaml
aprovacao_por_excecao:
  ativa: true
  valor_limite: "50000.00"          # você define
  acoes_auto_permitidas: [copiar_xml_rotina]
```
Só passa sozinho lote **sem pendência, sem achado bloqueante e só com CONTROLE**, dentro do
limite. Transmitir declaração, emitir/pagar guia, ato societário e alterar cadastro **sempre**
exigem APROVADO humano.

## Degrau 6 — Contábil e DP

**Plano de contas (cada empresa tem o seu):** no Domínio, para cada empresa, gere a mesma exportação
do plano que está no Drive como "PLANO DE CONTAS.csv" (*Impressão de campos da consulta*). Salve
todos numa pasta com o **código da empresa no início do nome** (ex.: `12 - LMG.csv`) e rode:
`python -m mo_autonomo contabil importar-planos --pasta "D:\PLANOS DOMINIO"`. O comando lista quem
ainda está sem plano. O código **reduzido** de cada conta é o que vai no TXT de importação.

- Contábil: coloque `plano_contas.csv` e `razao.csv` (exportados do Domínio) em
  `dados\dominio\<código>\` e cadastre as contas em `contas_bancarias.csv`. Os OFX que
  chegarem por e-mail viram lotes de lançamentos propostos. A gravação no Domínio só será
  feita quando você entregar o **leiaute oficial de importação**.
- DP: `python -m mo_autonomo dp conferir --folha folha.csv --cnpj <CNPJ>`.

## Degrau 7 — IA

1. Instale o Ollama no PC e um modelo local (o config de exemplo cita um; escolha conforme a
   memória do PC). Ligue `ia.ativa: true`.
2. As APIs gratuitas na nuvem vêm **desligadas**. Só ligue depois de avaliar os termos de uso
   de dados de cada provedor (alguns planos gratuitos usam o conteúdo para treinar modelos).
