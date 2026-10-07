# Plano da contabilidade autônoma — a partir do inventário do Drive do escritório

Fonte: inventário somente leitura do Google Drive de backup (`backup.mocont@gmail.com`) em
07/10/2026. Nenhum CNPJ, CPF ou senha foi copiado para este repositório.

## 1. Como o escritório está organizado hoje

- `MORAES & OLIVEIRA CONTABILIDADE/1-CLIENTES/CLIENTES ATIVOS/<regime>/<cliente>/<obrigação>/AAAA/MM-AAAA`
  - Regimes: 0-LUCRO REAL (1), 1-LUCRO PRESUMIDO (12), 1-1 IMUNE E ISENTA (2),
    2-SIMPLES NACIONAL (75), 3-MEI (7), além de PF (domésticas, IRPF, carnê-leão).
  - Por cliente, pastas por **obrigação** (DAS, DCTFWEB, EFD REINF, FGTS DIGITAL, E-SOCIAL, DEFIS,
    DARF PIS/COFINS/IRPJ/CSLL, EFD-CONTRIBUIÇÕES, ECD/ECF/LALUR no Real…) e dentro delas por mês.
- `XML/AAAA/MM` e `XML/NFSE/<empresa>/<ano>` (NFS-e pela chave de 50 dígitos).
- E-mail: o script atual (`motor_imap.py`) lê `mail.emailemnuvem.com.br:993` e separa as mensagens
  em subpastas `INBOX.<empresa>`. **Ele marca como lido e sinaliza mensagens** — o `mo_autonomo`
  não reaproveita esse comportamento (regra 7: só EXAMINE + BODY.PEEK).

## 2. O que já está ligado no sistema

| Fonte do escritório | Onde entra no `mo_autonomo` | Estado |
|---|---|---|
| Caixas fiscal@, moraes@, contabil@, dp@ (todas as pastas, inclusive `INBOX.<empresa>`) | `email.caixas` + `pasta: "*"` | pronto; falta senha no Cofre do Windows (`configurar_email.ps1`) |
| XML NF-e/NFC-e/CT-e/NFS-e e ZIPs de "Documentação Mensal" | captura → classificação → rota para `XML NOTAS` | pronto (regras legais aguardam normas conferidas) |
| Extratos OFX (`<ag>_<conta>_<data>.ofx`) | contábil: proposta de lançamentos pelo razão do cliente | pronto; falta `plano_contas.csv`/`razao.csv` por empresa |
| DAS em PDF (3 padrões de nome) | leitura por IA local → arquivamento por empresa/competência | pronto com IA ligada |
| Folha (exportação do SCI) | `dp conferir` | pronto; aguarda tabelas INSS/IRRF/FGTS conferidas |

## 3. O que o Drive tem e destrava os próximos passos

1. **Cadastro mestre de empresas** — planilha "CONTROLE EMPRESAS POR REGIME", aba *Cadastro de
   Clientes* (código, razão, CNPJ, cidade, regime, segmento, status). É a semente do
   `empresas.csv`. Atenção: o "CÓD." dela não é o código do Domínio (ex.: a mesma empresa tem
   códigos diferentes na carteira, no SCI e no Integra Contador) — o cruzamento é por CNPJ e o
   código do Domínio precisa vir da exportação do próprio Domínio.
2. **Importação no Domínio já usada pelo escritório** — arquivos `Dominio-<empresa>-<banco>-<conta>.txt`
   no formato `data;conta débito;conta crédito;valor;histórico;1;;;;;` (códigos reduzidos) e a
   importação real do leiaute 90 *Lançamentos Contábeis em Lote com Filial e Centro de Custos*
   (arquivo de conferência da LMG). Isso é o caminho para os lançamentos entrarem no Domínio —
   **falta só o escritório confirmar** que esse formato pode ser usado como leiaute oficial
   (regra do projeto: exportador só com leiaute fornecido pelo usuário).
3. **Plano de contas** — "PLANO DE CONTAS.csv" exportado do Domínio (3 versões; Latin-1, registro
   em várias linhas). Precisa de um leitor próprio e de saber de qual empresa é cada versão.
4. **De-para da folha** — "Planilha Rubricas Folha.xlsx" (evento → débito/crédito), hoje com o
   **nome** da conta; precisa ser convertido para o código reduzido do plano.
5. **Controle de sequência de NFS-e** — "PLANILHA IMPORTAÇÃO XML.xlsx" (numeração inicial/final por
   mês) — já coberto pela regra `COMP_SEQUENCIA`.
6. **Obrigações por município/regime** — "Obrigações Acessórias - FISCAL.xlsx" e "OBRIGAÇÕES DO
   SIMPLES NACIONAL - MUNICIPIO.xlsx" — base para o calendário, mas cada obrigação ainda precisa
   da norma conferida (`parametros.obrigacoes`).

## 4. Divergências encontradas (viram pendência no sistema, não chute)

- Contagem de clientes: planilha 101 × pastas ~97; Presumido 7 (dashboard) × 12 (aba/pastas).
- Regime: ao menos uma entidade aparece como Simples na planilha e como Imune/Isenta nas pastas.
- Meses faltando em DAS e em `XML/2026`; duplicidades de DAS por padrões de nome diferentes.
- Nomes de pasta inconsistentes (erros de digitação, com/sem LTDA, CPF em nome de pasta de MEI).
- CSVs do SCI e do Domínio em Latin-1 (o `mo_autonomo` já lê UTF-8 e ANSI).

## 5. Alerta de segurança (ação do escritório, fora do sistema)

No Drive há planilhas "SENHAS", arquivos `.env`, a pasta de **certificados A1** e uma imagem com
frase de segurança. Recomendação: tirar do Drive, guardar senhas no Cofre do Windows/gerenciador
de senhas e restringir o compartilhamento das pastas com contas externas.

## 6. Próximos passos, em ordem

1. Rodar `scripts\configurar_email.ps1` no PC (4 caixas, todas as pastas) e `imap testar`.
2. Exportar do Domínio a relação de empresas (código Domínio + CNPJ) e cruzar por CNPJ com a
   planilha "CONTROLE EMPRESAS POR REGIME" → `config\empresas.csv`. Divergência de regime = pendência.
3. Confirmar se o formato `Dominio-<empresa>-<banco>-<conta>.txt` / leiaute 90 pode ser usado
   como leiaute oficial → escrever o exportador e testar com a importação real da LMG como
   "teste de ouro".
4. Colocar o plano de contas e o razão exportados de um cliente piloto em `dados\dominio\<código>\`.
5. Conferir as normas na ordem do `docs/IMPLANTACAO.md` (começando pelo `MOC_NFE`).
