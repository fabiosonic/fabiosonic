# Portal M&O: Painel de Pendências e Vencimentos (substitui o box "Alertas")

## Objetivo
Trocar o box "Alertas", que hoje só lista DPS rejeitadas, por dois boxes fixos no topo da tela inicial:

1. **Pendências em aberto**: tudo o que já venceu ou está irregular, de todos os clientes.
2. **Vencendo em breve**: o que vence nos próximos N dias (padrão 15; opções 7/15/30), para agir antes do prazo.

Cada item tem um **botão de ação** que resolve a pendência: emitir a 2ª via, a guia ou o documento necessário.

## Box 1: Pendências em aberto (vermelho)

| Categoria | Exemplos | Botão principal | Fonte |
|---|---|---|---|
| Tributos vencidos | DAS, DARF (IRPJ/CSLL/PIS/COFINS/IRRF), DARF DCTFWeb, FGTS Digital, ISS, ICMS, parcela de parcelamento | **Emitir 2ª via atualizada** | Integra Contador (SERPRO) / PGDAS-D / Sicalc / FGTS Digital / prefeitura / SEFAZ |
| Férias vencidas | Período concessivo expirado (pagamento em dobro, art. 137 CLT) | **Gerar aviso/recibo de férias** | Domínio Folha |
| Obrigações acessórias em atraso | DCTFWeb, EFD-Reinf, eSocial, PGDAS-D, DEFIS, SPED, DASN-SIMEI | **Transmitir / gerar declaração** | Integra Contador / Domínio |
| Certidões irregulares | CND federal, CRF FGTS, CNDT, estadual e municipal vencidas ou positivas | **Emitir certidão** (e, se positiva, **Ver débitos**) | Integra Contador / Caixa / TST / SEFAZ / prefeitura |
| NFS-e/DPS rejeitada | O que hoje aparece em "Alertas" | **Corrigir e reenviar DPS** | NFS-e Nacional |
| Fiscalização / malha | Caixa postal e-CAC não lida, intimação, termo de exclusão do Simples, DTE | **Abrir mensagem** | Integra Contador / DTE |
| Acessos | Certificado digital vencido, procuração e-CAC vencida | **Renovar / solicitar procuração** | Cadastro do portal |
| Documentos do cliente | Extrato, notas, folha de ponto não enviados | **Cobrar cliente (WhatsApp/e-mail)** | Portal |

## Box 2: Vencendo em breve (amarelo)

| Categoria | Regra de alerta | Botão principal |
|---|---|---|
| Guias do mês | Vencimento ≤ N dias (DAS, DARF DCTFWeb, FGTS Digital, IRRF, PIS/COFINS, ISS, ICMS, parcelamentos) | **Emitir guia** + **Enviar ao cliente** |
| Férias a vencer | Limite do período concessivo ≤ 60 dias (o aviso exige 30 dias de antecedência, art. 135 CLT) | **Programar férias** |
| Contrato de experiência | Fim do 1º período (até 45 dias) ou do 2º (total até 90 dias) ≤ 10 dias | **Prorrogar / efetivar / rescindir** |
| Certidões | Validade ≤ 15 dias | **Renovar certidão** |
| Certificado digital | Validade ≤ 30 dias | **Agendar renovação** |
| Procuração e-CAC | Validade ≤ 30 dias | **Renovar procuração** |
| Obrigações acessórias | Prazo de entrega ≤ N dias | **Gerar / transmitir** |

> Os vencimentos ficam numa tabela de configuração `agenda_obrigacoes`, editável no portal, e **não fixos no código**. A legislação muda (DCTFWeb, FGTS Digital e Reforma Tributária: CBS/IBS a partir de 2026). Cada regra é ajustada por regime (Simples, Presumido, Real, MEI) e por município/UF.

## Cada item mostra
- Cliente (razão social e CNPJ), categoria e competência
- Vencimento e **dias em atraso** ou **dias restantes**
- Valor original e **valor atualizado**. Estimativa para tributo federal: multa de mora de 0,33% ao dia, limitada a 20% (art. 61 da Lei 9.430/96), mais Selic acumulada desde o mês seguinte ao vencimento, mais 1% no mês do pagamento. O valor oficial é o da guia emitida.
- Responsável (setor Fiscal / DP / Contábil / Societário)
- Botões: **[ação principal]** · **Enviar ao cliente** · **Marcar resolvida** · **Ignorar (com justificativa)**

## Comportamento
- Os dois boxes ficam **sempre visíveis** no topo, com contadores no cabeçalho (ex.: "Pendências 23 · Vencendo 41"). O sino (badge 8) passa a mostrar a soma.
- Ordenação: criticidade primeiro (impede CND ou gera multa diária), depois dias de atraso e valor.
- Filtros: setor, cliente, categoria e "só meus".
- Mobile: cards como na tela atual, com a cor do selo indicando o status ("VENCIDO há 12 dias", "VENCE em 3 dias") e o botão de ação dentro do card.
- Lista paginada com "ver todas", que abre a tela completa de pendências.
- A pendência sai sozinha quando a fonte confirma: pagamento conciliado, declaração transmitida, férias lançadas no Domínio.

## Modelo de dados
```sql
CREATE TABLE pendencias (
  id               BIGSERIAL PRIMARY KEY,
  cliente_id       BIGINT NOT NULL REFERENCES clientes(id),
  categoria        TEXT NOT NULL,      -- tributo | ferias | obrigacao | certidao | nfse | fiscalizacao | acesso | documento | experiencia
  subtipo          TEXT NOT NULL,      -- DAS, DARF_DCTFWEB, FGTS, ISS, FERIAS_VENCIDA, CND_FEDERAL ...
  referencia       TEXT,               -- competência, matrícula do empregado, nº DPS...
  vencimento       DATE NOT NULL,
  valor_original   NUMERIC(14,2),
  valor_atualizado NUMERIC(14,2),
  status           TEXT NOT NULL DEFAULT 'aberta',  -- aberta | resolvida | ignorada
  setor            TEXT NOT NULL,
  responsavel_id   BIGINT,
  acao_tipo        TEXT NOT NULL,      -- emitir_das | emitir_darf | emitir_fgts | gerar_ferias | emitir_cnd | reenviar_dps ...
  acao_payload     JSONB,
  origem           TEXT NOT NULL,      -- dominio | integra_contador | nfse_nacional | portal
  justificativa    TEXT,
  detectado_em     TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolvido_em     TIMESTAMPTZ,
  UNIQUE (cliente_id, subtipo, referencia)
);
```
- **Vencidas**: `status='aberta' AND vencimento < current_date`, mais os itens sem data e irregulares por natureza (certidão positiva, DPS rejeitada).
- **Vencendo**: `status='aberta' AND vencimento BETWEEN current_date AND current_date + :dias`.

## API
- `GET  /api/pendencias?escopo=vencidas|a_vencer&dias=15&setor=&cliente_id=`
- `POST /api/pendencias/{id}/acao`: executa `acao_tipo` e devolve o PDF da guia/documento ou o link para emissão
- `POST /api/pendencias/{id}/enviar-cliente`: WhatsApp/e-mail com o documento
- `POST /api/pendencias/{id}/resolver` e `/ignorar` (justificativa obrigatória)

## Coleta (job agendado, de hora em hora / diário)
1. **Integra Contador (SERPRO)**: situação fiscal, DAS em aberto, débitos DCTFWeb, caixa postal, procurações.
2. **Domínio (via integração existente)**: férias (períodos aquisitivo e concessivo), contratos de experiência, guias de folha (FGTS, DARF previdenciário, IRRF).
3. **NFS-e Nacional**: DPS rejeitadas (migra o box "Alertas" atual).
4. **Cadastro do portal**: validade de certificados, certidões e procurações; documentos esperados do cliente.

## Ordem de implementação sugerida
1. Tabela + API + os dois boxes na tela, migrando as DPS rejeitadas para a categoria `nfse`.
2. Férias vencidas/a vencer e experiência (dados do Domínio).
3. Tributos: DAS (Integra Contador) com o botão "Emitir 2ª via", depois DARF DCTFWeb e FGTS Digital.
4. Certidões, certificados, procurações e caixa postal.
5. "Enviar ao cliente" via WhatsApp/e-mail.
