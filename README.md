# Portal M&O: integração com o Domínio

Módulo de integração entre o escritório **Moraes & Oliveira** e o **Domínio Sistemas** (Escrita Fiscal e Contabilidade).
Usa só a biblioteca padrão do Python 3.9 ou superior: não precisa de `pip install` e roda direto no Windows do escritório.

| Comando | Entrada | Saída | Para quê |
|---|---|---|---|
| `matriz` | XML de NF-e, NFC-e, CT-e e NFS-e (Nacional ou ABRASF), soltos ou em zip | Matriz de regras por empresa, empresa-modelo por regime e alertas tributários | Montar a **Configuração de Importação** e os **Acumuladores** a partir do que realmente aparece nos XML |
| `rotinas` | Pasta de XML em zip (`D:\XML NOTAS`) | Árvore `<BASE>\<Código-Apelido>\<MMAAAA>\*.xml` por tipo de documento | Alimentar a **Rotina Automática** do Domínio, que não lê zip |
| `ofx` | Extrato OFX e tabela de-para da empresa | TXT de lançamentos contábeis e lista de pendências | Importar o extrato no Domínio Contabilidade sem digitação |

## Carteira (`carteira.csv`)

```
codigo;apelido;cnpj;regime
86;RTX;11.111.111/0001-11;SIMPLES
```

- Extraia a carteira do Domínio em `Controle > Empresas` ou em `Relatórios > Cadastrais > Empresas`.
- O **apelido** tem de ser idêntico ao do Domínio, porque vira o nome da pasta que a rotina procura (Central de Soluções, cód. 4399 e 9143).
- `regime` aceita `SIMPLES`, `PRESUMIDO`, `MEI`, `IMUNE` ou `REAL`.
- As empresas `EXEMPLO*`, `MORAES` e `MORAES & OLIVEIRA CO` são ignoradas automaticamente.

## 1. Matriz de regras (configurar o Domínio)

```
python -m mo_dominio matriz --raiz "D:\XML ORIGINAIS" --carteira carteira.csv --saida "D:\XML NOTAS\_CONFIG\2026-10\matriz"
```

Gera estes arquivos:

- `matriz_<codigo>.md`: uma linha por combinação (CFOP, CST/CSOSN, CST PIS/COFINS, forma de pagamento, tribISSQN, ISS retido, município etc.), cada uma uma relação que precisa existir na Configuração de Importação. Inclui também os **alertas** que pedem decisão antes de configurar:
  - retenção federal em NFS-e prestada por optante do Simples ou MEI;
  - ISS retido pelo tomador, que precisa de acumulador próprio e sai da base do DAS;
  - entradas com CST de fornecedor do regime normal: no Simples, `Percentual B.C` do ICMS = 0;
  - CT-e tomado e CT-e em que a empresa é só participante;
  - devolução (finNFe=4): mesmo anexo da venda;
  - NFC-e sem CPF: cliente padrão;
  - cancelamentos.
- `modelos.json`: empresa-modelo sugerida por regime e o **delta** de cada réplica.
- `matriz_carteira.csv`, `terceiros.csv` (XML de quem não é cliente) e `nao_reconhecidos.csv`.

## 2. Rotinas automáticas (importação mensal sem intervenção)

```
python -m mo_dominio rotinas --origem "D:\XML NOTAS" --destino "D:\XML NOTAS\_ROTINAS" --carteira carteira.csv --competencia 092026 --dry-run
```

Confira o resumo do `--dry-run` e depois rode de novo sem essa opção. O resultado é uma pasta-base por tipo de documento:

```
_ROTINAS\NFE-ENTRADA\86-RTX\092026\<chave>.xml
_ROTINAS\NFE-SAIDA\...   NFCE\...   CTE\...
_ROTINAS\NFSE-NACIONAL-PRESTADA\...   NFSE-NACIONAL-TOMADA\...   NFSE-ABRASF-*\...
_ROTINAS\_log\preparacao_092026.csv, resumo_092026.json
```

Regras aplicadas:

- **Competência:** `dCompet` na NFS-e (fato gerador do ISS e do Simples) e data de emissão nos demais documentos.
- **Cancelamentos:** o evento vai para a mesma pasta da nota, porque o Domínio importa as canceladas da mesma pasta (cód. 12427).
- **Nota entre dois clientes do escritório:** é gravada nas duas empresas, como saída de uma e entrada da outra.
- **CT-e:** só entra quando a empresa é **tomadora** (ou emitente, se for transportadora). Quem é só remetente ou destinatário não escritura o frete.
- **Reexecução:** o processo é idempotente, e um XML que já existe no destino não é regravado.

No Domínio, cada rotina de `Arquivos > Rotinas Automáticas` aponta para **uma pasta-base**, com *Buscar os arquivos* = `Sempre da pasta da competência da execução da rotina`. O agendamento em `Movimentos > Rotinas Automáticas` usa `Competência anterior à execução`. Lembre que a rotina só importa a competência atual ou a anterior, e que o Escrita Fiscal precisa estar aberto no horário agendado (cód. 5516).

## 3. Extrato OFX → lançamentos contábeis

```
python -m mo_dominio ofx --ofx itau_092026.ofx --depara depara_86.csv --conta-banco 7 --conta-transitoria 999 --saida lanc_86_092026.txt
```

O `depara.csv` (exemplo em `exemplos/depara_banco.csv`) tem este formato:

```
padrao;sentido;conta;historico;complemento
tarifa;D;520;;Tarifa bancária {memo}
re:^(DAS|SIMPLES NACIONAL);D;245;;DAS Simples Nacional {memo}
```

- `padrao`: trecho do histórico do banco. A comparação ignora maiúsculas e acentos. Com o prefixo `re:`, o padrão é tratado como expressão regular.
- `sentido`: `C` para entrada no banco, `D` para saída, `*` para ambos.
- **A primeira regra que casar vence**, então coloque as mais específicas em cima.

Como os lançamentos são montados:

- Entrada no banco: D banco / C contrapartida. Saída do banco: D contrapartida / C banco.
- O que não casar com nenhuma regra **não é adivinhado**: vai para a conta transitória e para `<saida>_pendencias.csv`, para o analista classificar e, de preferência, transformar em regra.
- Transações duplicadas (mesmo FITID) e de valor zero são descartadas.
- O resumo mostra créditos, débitos e o movimento líquido, ao lado do saldo final do OFX, para a conciliação.

Formato do arquivo gerado:

- Texto `;` sem cabeçalho, codificação cp1252, quebra de linha CRLF.
- Campos `data;debito;credito;valor;historico;complemento`, com data `dd/mm/aaaa` e valor `1234,56`.
- A ordem pode ser mudada com `--colunas`. Os campos disponíveis são `data`, `debito`, `credito`, `valor`, `historico`, `complemento`, `documento`, `empresa` e `fitid`.

> **Antes da primeira importação**, cadastre no Domínio Contabilidade um leiaute de importação de lançamentos (arquivo texto delimitado) com separador `;` e os campos na **mesma ordem** de `--colunas`. Depois faça um teste com um extrato pequeno numa competência sem movimento e confira o razão da conta do banco contra o saldo do OFX.

## Testes

```
python -m unittest discover -s tests -v
```

Os XML de teste são sintéticos e cobrem:

- NF-e de saída Simples (CSOSN) e de entrada de fornecedor do regime normal;
- CT-e com tomador "4 - Outros" e CT-e em que a empresa é só participante;
- NFS-e Nacional com ISS retido;
- evento de cancelamento, zip e competência fora do mês;
- OFX SGML em cp1252 com transação duplicada.

## Origem

A lógica de leitura dos XML, da matriz e das rotinas vem da skill interna `configuracao-importacao-dominio` (carteira M&O), que foi refatorada como pacote testável. Correções feitas no caminho:

- CT-e com `toma4` agora identifica o tomador;
- CT-e de mero participante deixou de ir para a pasta da rotina;
- o CNPJ do emitente é extraído da chave da NFS-e Nacional nos eventos de cancelamento;
- `Element` não é mais usado como booleano, o que gerava aviso no Python 3.12 ou superior.
