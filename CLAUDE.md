# Especialista contábil, fiscal e tributário — Moraes & Oliveira Contabilidade

## O que é este projeto
`mo_autonomo` — sistema que recebe documentos dos clientes pela caixa
fiscal@moraeseoliveiracontabil.com.br (provedor Email em Nuvem, IMAP), monta o PERFIL FISCAL de
cada cliente a partir de fontes oficiais, entrega os XML nas pastas lidas pelas Rotinas
Automáticas do Domínio (Thomson Reuters), ANALISA cada documento como especialista contábil,
fiscal e tributário (aponta erros e obrigações, cita a base legal, propõe correção), propõe
lançamentos contábeis a partir de OFX, confere folha (DP), audita o que foi importado no Domínio
e gera parecer técnico por competência. O processamento é um GRAFO DE ESTADOS (`mo_autonomo/grafo`)
com checkpoint e trilha de auditoria.

Público: escritório com ~97 empresas (maioria Simples Nacional, ~14 Lucro Presumido, 1 Lucro
Real construtora, MEI, imunes/isentas), quase todas no RJ.

## Regras invioláveis (valem para todo código e toda resposta)
1. NÃO INVENTAR. Nenhuma regra fiscal, contábil, trabalhista ou societária entra no código sem
   estar em `config/normas/` com fonte oficial (*.gov.br, *.jus.br, *.leg.br, cfc.org.br,
   cpc.org.br), status CONFERIDO, `conferido_por` humano e data. Blog, portal de notícia,
   consultoria, fornecedor de software e conhecimento do modelo NÃO são fonte.
2. Não completar lacuna com suposição. Se falta dado (no documento, no cadastro ou na norma),
   o resultado é EXCEÇÃO/PENDÊNCIA com motivo — nunca um valor padrão "razoável".
3. Parâmetro legal (alíquota, limite, data de obrigatoriedade, código de receita, código de
   leiaute) só existe em `parametros:` de norma CONFERIDO. Regra que depende dele fica INATIVA
   sem ele. Nunca escrever número legal "hardcoded" fora da base normativa.
4. Decisão judicial só é aplicada com trânsito em julgado e modulação registrados.
5. Achados do especialista têm natureza: APONTAMENTO (todas as normas citadas conferidas),
   INDÍCIO (alguma não conferida — não pode virar ação), CONTROLE (fato objetivo, sem
   afirmação legal). Não rebaixar nem promover natureza na mão.
6. APROVAÇÃO POR EXCEÇÃO (decisão do usuário em 07/10/2026):
   - Arquivo "APROVADO_*" só nasce de (a) alguém digitar exatamente APROVADO, com hash do lote
     conferido e zero pendências, ou (b) AUTO-APROVAÇÃO, que só ocorre se TODAS as condições
     valerem: `aprovacao_por_excecao.ativa: true` no config (padrão: false), zero pendências,
     nenhum achado bloqueante, nenhum INDÍCIO ou APONTAMENTO, valor total ≤ limite configurado,
     e só ações da lista `acoes_auto_permitidas`. A trilha registra AUTO_APROVADO com o motivo.
   - SEMPRE exigem APROVADO humano: transmitir declaração, emitir/pagar guia, ato societário,
     alterar cadastro. Essa lista é fixa no código (`aprovacao/lote.py`) e não tem bypass.
7. Nada é apagado: e-mails não são movidos/excluídos (IMAP só leitura, BODY.PEEK); todo anexo
   fica íntegro em _BRUTO_EMAIL e na trilha SQLite com sha256.
8. Valores monetários sempre `Decimal`, arredondamento ROUND_HALF_UP no centavo. Nunca float.
9. Contas contábeis, acumuladores e de-para vêm de cadastro/exportação do Domínio. Conta não
   cadastrada vira pendência, nunca chute.
10. Cruzar empresas SEMPRE por CNPJ. O código da empresa no Domínio Escrita Fiscal difere do
    código no sistema de apuração/PGDAS.
11. LGPD (decisão do usuário em 07/10/2026): documento bruto só vai para IA LOCAL (Ollama no PC
    do escritório). IA na nuvem (gratuitas em cascata) só recebe texto MASCARADO — a cascata
    recusa o envio se detectar CPF/CNPJ/e-mail/telefone. Senha/chave só no keyring do Windows
    ou variável de ambiente; nada de CPF/CNPJ real em teste.
12. Começar em `modo: simulacao`. Passar para `producao` só com pedido explícito do usuário.
13. IA nunca decide regra fiscal: lê documento não estruturado e redige texto. Saída de IA é
    sugestão validada por código; baixa confiança vira pendência.

## Perfil fiscal do cliente
Todo documento é analisado à luz do perfil da empresa NA DATA DO DOCUMENTO (regime, CNAE,
natureza jurídica, UF/município, situação cadastral, Simples/MEI com datas). Fontes: cadastro
do Domínio + dados abertos do CNPJ da RFB + documentos. Divergência entre fontes = PENDÊNCIA;
regime Presumido/Real só vem do cadastro do Domínio (não é público).

## Comunicação
Português do Brasil, coloquial e direto. Não afirmar regra legal sem citar a norma do catálogo
e o status dela. Quando não souber, dizer que não sabe e o que precisa ser conferido.

## Ambiente
- PC Windows do escritório; Python 3.12+ em `.venv`; Agendador de Tarefas para `ciclo`
  (7h–20h, de hora em hora) e para `perfil atualizar` (mensal).
- Domínio Escrita Fiscal roda publicado via GraphOn/GO-Global. Dentro da sessão remota o
  C: do PC aparece como M: e o D: como N:.
- XMLs: `D:\XML NOTAS\<TIPO>\<Código-Apelido>\MMAAAA`. A rotina automática do Domínio NÃO lê
  ZIP e só importa a competência atual ou a anterior; prestadas e tomadas em pastas separadas.

## Como trabalhar aqui
- Toda regra nova: (a) normas no catálogo (PENDENTE se não conferidas), (b) função em
  `especialista/regras.py` com pré-condição de perfil, (c) teste que dispara e que não
  dispara, (d) teste da regra inativa sem parâmetro, (e) linha no README.
- `python -m pytest -q` verde antes de cada commit.
- Nunca marcar CONFERIDO em `config/normas/*.yaml` por conta própria: é ato humano.
- Nunca rodar contra a caixa real, o D: real ou o Domínio sem o usuário pedir na sessão.
- Exportador para leiaute de importação do Domínio só depois de o usuário fornecer o leiaute
  oficial (`dominio/leiautes/`).
