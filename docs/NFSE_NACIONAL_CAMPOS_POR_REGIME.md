# NFS-e Nacional (DPS v1.01): campos por regime tributário e IBS/CBS

Estudo feito em 03/10/2026 a partir de:
- **Leiaute oficial** da DPS v1.01 (XSD em `schemas/nacional/`, já com o grupo IBS/CBS e as mudanças da
  NT SE/CGNFS-e 007/2026). Obrigatoriedade [mín-máx] tirada do próprio XSD.
- **Regras de validação** (Anexo I – Sefin/ADN) conhecidas pelas mensagens de rejeição (E0160, E0166, E0617,
  E0625, E0635, E1302, E1307).
- **Comunicados do CGNFS-e / CGIBS** sobre prazos do IBS e da CBS.

O que está marcado como **(a confirmar)** não pôde ser lido direto no portal oficial (acesso bloqueado neste
ambiente) e precisa ser conferido no Anexo I vigente antes de virar regra no sistema.

---

## 1. Campos comuns a todos os regimes

| Grupo / campo | Obrig. | O que é |
|---|---|---|
| `tpAmb` | 1 | 1 = produção, 2 = homologação (produção restrita) |
| `dhEmi` | 1 | Data/hora de emissão (não pode ser futura) |
| `verAplic`, `serie`, `nDPS` | 1 | Aplicativo, série e número da DPS |
| `dCompet` | 1 | Competência (data de início da prestação; não pode ser posterior à emissão) |
| `tpEmit` | 1 | 1 = prestador, 2 = tomador, 3 = intermediário |
| `cLocEmi` | 1 | Município emissor (IBGE) |
| `prest/CNPJ` ou `CPF` | 1 | Prestador |
| `prest/IM` | 0-1 | Só quando o município tem cadastro no Sistema Nacional |
| `prest/regTrib/opSimpNac` | 1 | **1 não optante · 2 MEI · 3 ME/EPP** — tem de bater com o cadastro do Simples na competência (E0160) |
| `prest/regTrib/regEspTrib` | 1 | 0 nenhum · 1 cooperativa · 2 estimativa · 3 ME municipal · 4 notário · 5 autônomo · 6 sociedade de profissionais · 9 outros |
| `toma` (CNPJ/CPF/NIF, `xNome`, `end`, `fone`, `email`) | 0-1 | Tomador (obrigatório na prática para B2B e para retenções) |
| `serv/locPrest/cLocPrestacao` | 1 | Município (IBGE) onde o serviço foi prestado |
| `serv/cServ/cTribNac` | 1 | Código de tributação nacional: item + subitem LC 116 + desdobro (6 dígitos) |
| `serv/cServ/cTribMun` | 0-1 | Código municipal, se o município exigir |
| `serv/cServ/xDescServ` | 1 | Descrição do serviço |
| `serv/cServ/cNBS` | 0-1 | NBS (9 dígitos) — **na prática obrigatória com a Reforma** (base da classificação IBS/CBS) |
| `valores/vServPrest/vServ` | 1 | Valor do serviço |
| `valores/vDescCondIncond`, `vDedRed` | 0-1 | Descontos e deduções da base (materiais, subempreitada etc.) |
| `valores/trib/tribMun/tribISSQN` | 1 | 1 tributável · 2 imunidade · 3 exportação · 4 não incidência |
| `valores/trib/tribMun/tpRetISSQN` | 1 | 1 não retido · 2 retido pelo tomador · 3 retido pelo intermediário |
| `valores/trib/totTrib` | 1 | Carga tributária aproximada (Lei 12.741/2012) — **uma** das formas abaixo, conforme o regime |

Grupos de uso específico (qualquer regime): `subst` (substituição de nota), `comExt` (exportação/importação),
`obra` (CNO/CIB), `atvEvento` (eventos), `infoCompl` (pedido, ART/RRT, informações complementares),
`exigSusp` (ISS com exigibilidade suspensa), `BM` (benefício municipal).

---

## 2. O que muda por regime

### 2.1 Lucro Real e Lucro Presumido (`opSimpNac = 1`)

| Campo | Regra |
|---|---|
| `regApTribSN` | **Não informar** (só para ME/EPP) |
| `pAliq` (ISS) | **Proibido** quando o município de incidência é conveniado/ativo no Sistema Nacional (E0617): a alíquota vem parametrizada pelo município. Só informar em município não conveniado |
| `tribFed/piscofins` | Apuração própria de PIS/COFINS: `CST` (01 alíquota básica etc.), `vBCPisCofins`, `pAliqPis`, `pAliqCofins`, `vPis`, `vCofins`. **Lucro Real** (não cumulativo): 1,65% e 7,6%. **Lucro Presumido** (cumulativo): 0,65% e 3% |
| `tpRetPisCofins` | Retenção na fonte (NT 007/2026): 0 nenhum retido · 1 PIS/COFINS retidos · 3 PIS/COFINS/CSLL retidos · 4 a 9 combinações |
| `vRetCSLL` | Pela NT 007/2026 passa a receber a **soma PIS + COFINS + CSLL retidos** (4,65% nos serviços do art. 30 da Lei 10.833/2003) |
| `vRetIRRF` | IRRF retido (1,5% serviços profissionais; 1% limpeza/conservação/segurança) |
| `vRetCP` | Retenção previdenciária (11% cessão de mão de obra/empreitada) |
| `totTrib` | `vTotTrib` (valores federal/estadual/municipal) **ou** `pTotTrib` (percentuais) **ou** `indTotTrib = 0`. **Nunca** `pTotTribSN` |
| `vTotTribFed` | Não é aceito sem o detalhamento das retenções em `vRetCP`/`vRetIRRF`/`vRetCSLL` quando houver |

### 2.2 Simples Nacional ME/EPP (`opSimpNac = 3`)

| Campo | Regra |
|---|---|
| `regApTribSN` | **Obrigatório** (E0166): 1 = federais e ISS no DAS · 2 = federais no DAS e ISS fora (sublimite excedido / ISS fixo) · 3 = federais e ISS fora do DAS |
| `pAliq` (ISS) | **Proibido sem retenção** (`tpRetISSQN = 1`) (E0625). Com retenção pelo tomador, informar a alíquota efetiva do Simples para o ISS (LC 123, art. 21, §4º) |
| `tribFed/piscofins` | Não se aplica (PIS/COFINS no DAS) |
| Retenções federais | Em regra não há (IN RFB 1.234/2012 dispensa o optante); IRRF/CSLL só em casos específicos |
| `totTrib` | Usar `pTotTribSN` = percentual do Simples (alíquota efetiva). Só um dos grupos de `totTrib` pode ser informado |
| `regEspTrib` | Escritório contábil com ISS fixo costuma usar 6 (sociedade de profissionais) — conferir com o cadastro municipal. Com regime especial, o ISS fica fora do cálculo da nota (E0635/E1307) |

### 2.3 MEI (`opSimpNac = 2`)

| Campo | Regra |
|---|---|
| `regApTribSN` | Não informar |
| Campos de ISS | **Proibido informar** base, alíquota e valor de ISS (E1302): o ISS do MEI é fixo no DAS-MEI. Manter só `tribISSQN` e `tpRetISSQN = 1` |
| `pAliq` | Não informar |
| `tribFed` | Não informar (tributos federais fixos no DAS-MEI) |
| `totTrib` | `indTotTrib = 0` ou valores zerados — **(a confirmar)** qual forma o Anexo I aceita para MEI |
| `regEspTrib` | 0 (nenhum) |

---

## 3. IBS e CBS (grupo `IBSCBS`, LC 214/2025)

### 3.1 Quem preenche e quando

| Regime | Contribuinte | Situação em 2026 | A partir de 2027 |
|---|---|---|---|
| Lucro Real / Presumido | Contribuinte do IBS/CBS (regime regular) | Preenchimento esperado desde 03/08/2026 (marco do CGIBS para os DF-e). Na NFS-e, o CGNFS-e (NT 004 v2.0) informou que a **ausência do grupo não gera rejeição até 31/12/2026** — fontes privadas citam 01/10 (grupo 1) e 01/12/2026 (grupo 2) **(a confirmar)** | Obrigatório, com rejeição |
| Simples ME/EPP | Recolhe IBS/CBS dentro do DAS (ou opta pelo regime regular — "híbrido") | Opcional; em 2026 basta a NBS | Obrigatório desde 01/01/2027 (Res. CGSN 190 e 191/2026) |
| MEI | Recolhe dentro do DAS-MEI | Opcional | Obrigatório desde 01/01/2027 |
| Imunes / isentos / não contribuintes | — | Informar com CST de imunidade/isenção/não incidência quando o grupo for usado | Idem |

**Regra técnica importante:** se o grupo `IBSCBS` for enviado, todas as validações dele passam a valer
mesmo no período em que ele é opcional. Ou seja: mandar incompleto é pior do que não mandar.

Alíquotas de teste em 2026: **CBS 0,9% e IBS 0,1%**. Não alteram o valor da nota e são compensáveis com
PIS/COFINS devidos.

### 3.2 Campos do grupo

| Campo | Obrig. | Preenchimento |
|---|---|---|
| `finNFSe` | 1 | 0 = NFS-e regular |
| `indFinal` | 0-1 | 1 = uso ou consumo pessoal (art. 57 da LC 214); 0 = demais |
| `cIndOp` | 1 | Código indicador da operação (6 dígitos — tabela "código indicador de operação"; define o local da operação/destino do IBS) |
| `tpOper` | 0-1 | Operação com ente governamental ou serviço sobre bem imóvel (1 a 5) |
| `tpEnteGov` | 0-1 | Tipo de ente governamental (1 a 4) |
| `gRefNFSe` | 0-1 | Chaves de NFS-e referenciadas |
| `indDest` | 1 | 0 = o destinatário é o próprio tomador; 1 = destinatário diferente (aí o grupo `dest` é obrigatório) |
| `dest` | 0-1 | Destinatário (CNPJ/CPF/NIF, nome, endereço) |
| `imovel` | 0-1 | Serviços sobre bens imóveis (exceto obra): CIB ou endereço |
| `valores/gReeRepRes` | 0-1 | Reembolso, repasse e ressarcimento de valores de terceiros já tributados (saem da base do ISS/IBS/CBS) |
| `trib/gIBSCBS/CST` | 1 | Código de situação tributária do IBS/CBS (3 dígitos = início do cClassTrib) — ex.: 000 tributação integral, 200 alíquota reduzida, 410 imunidade/não incidência |
| `trib/gIBSCBS/cClassTrib` | 1 | Classificação tributária (6 dígitos, tabela oficial). Ex.: 000001 tributação integral; 200052 redução de 30% para profissões intelectuais regulamentadas (inclui contabilidade) |
| `cCredPres` | 0-1 | Crédito presumido, quando houver |
| `gTribRegular` | 0-1 | `CSTReg` + `cClassTribReg`: tributação regular de referência (usado por optante do Simples que recolhe pelo regime regular / situações especiais) |
| `gDif` | 0-1 | Diferimento: percentuais para IBS UF, IBS Município e CBS |

**Escritório contábil (item 17.19, NBS 1.1302.21.00):** cClassTrib **200052** (redução de 30% — profissões
intelectuais, LC 214, art. 127). O optante do Simples só passa a informar a partir de 2027; se optar pelo
regime regular, usa a redução e destaca IBS/CBS normalmente.

---

## 4. Como o sistema aplica (implementado em `nfse_itaborai/fiscal.py`)

- **Regra geral** (Configurações › Regras fiscais): regime (MEI, Simples, Presumido, Real), apuração no Simples,
  regime especial, ISS retido e alíquota, retenções federais em % (IRRF, PIS, COFINS, CSLL, INSS), quando
  informar IBS/CBS (automático: regime regular já; Simples/MEI a partir de 2027) e consumo pessoal.
- **Regra do tomador**: no cadastro do cliente e na tela Emitir nota, "Usar regra geral" ou "Regra específica
  deste tomador". A específica fica guardada no tomador e vale primeiro, só para ele.
- **Montagem da DPS por regime**: Real/Presumido com `piscofins` (CST 01; 1,65/7,6 ou 0,65/3),
  `tpRetPisCofins` e `vRetCSLL` = PIS+COFINS+CSLL retidos (NT 007); Simples com `pTotTribSN` e `pAliq` só com
  retenção; MEI sem `pAliq`, sem `tribFed`, `regEspTrib = 0` e `indTotTrib = 0`; não optante sem `pAliq`.
- **Dispensas legais automáticas**: IRRF ≤ R$ 10 (Lei 9.430/96, art. 67) e PIS/COFINS/CSLL ≤ R$ 10
  (Lei 10.833/03, art. 31, §3º). Simples com retenção de PIS/COFINS é recusado (Lei 10.833/03, art. 32, II).
- **Canal municipal (Itaboraí)**: o regime define "Optante do Simples" e o tipo de tributação; as retenções
  calculadas vão em `ValoresRetencoes`.
