# Parecer do Gestor Contábil: revisão do catálogo de obrigações

**Sistema:** `mo_obrigacoes`, arquivo `mo_obrigacoes/catalogo.py` (28 itens)
**Data-base:** 13/10/2026
**Escopo:** prazo e regra para dia não útil, aplicabilidade por regime e perfil, base legal, multa de referência e padrões de reconhecimento dos recibos e guias. Este parecer **não altera código**: as mudanças estão listadas para implementação.

---

## 1. Resumo executivo

1. **O catálogo está bom no essencial.** Os prazos centrais estão corretos para 2026:
   - DCTFWeb no último dia útil do mês seguinte;
   - DAS e PGDAS-D no dia 20, com prorrogação;
   - DARF previdenciário e FGTS Digital no dia 20, com antecipação;
   - PIS/COFINS no dia 25, com antecipação;
   - EFD-Contribuições no 10º dia útil do 2º mês;
   - ECD no último dia útil de junho e ECF no último dia útil de julho;
   - DMED e DIMOB no último dia útil de fevereiro.
2. **Erros objetivos que devem ser corrigidos:**
   - **DCTFWeb, base legal:** a IN RFB 2.005/2021 foi **revogada**. A norma vigente é a **IN RFB 2.237/2024**, art. 6º, com a redação da IN RFB 2.248/2025.
   - **DCTFWeb, multa:** os mínimos estão **invertidos**. O correto é R$ 200 para declaração sem movimento e R$ 500 nos demais casos (art. 11).
   - **eSocial (S-1299) e EFD-Reinf:** quando o dia 15 não é útil, o prazo é **prorrogado** para o dia útil seguinte, e não antecipado. Para a Reinf, isso vale desde a IN RFB 2.163/2023; para o eSocial, está no MOS.
   - **DEFIS, multa:** o mínimo de R$ 200 está no **art. 38, §3º** da LC 123. O art. 38-A trata do PGDAS-D.
   - **DMED e DIMOB, multa:** não é "R$ 5.000 por mês". O valor é **R$ 500 ou R$ 1.500 por mês-calendário**, conforme o art. 57 da MP 2.158-35/2001.
   - **ECF, multa:** o fundamento é o **art. 8º-A do Decreto-Lei 1.598/1977**, incluído pela Lei 12.973/2014, e não a "Lei 12.973, art. 8º-A".
   - **PIS/COFINS, base legal:** o prazo do dia 25, com antecipação, está no **art. 18, II e parágrafo único, da MP 2.158-35/2001**, com a redação da Lei 11.933/2009.
3. **Lacunas de aplicabilidade:**
   - O **MEI com empregado** está obrigado à DCTFWeb (IN 2.237, art. 3º, IX), ao eSocial e ao DARF previdenciário. Hoje recebe só Folha e FGTS.
   - **DeSTDA:** deve valer para comércio **ou** indústria.
   - **DARF DCTFWeb:** deve ser gerado também para Presumido/Real que só retêm tributos, sem folha.
   - **DCTFWeb do Simples:** também é devida pelo optante que retém tributos, por exemplo em cessão de mão de obra (R-2010).
4. **Confirmado:** a **DIRF foi extinta** a partir do ano-calendário 2025 (IN RFB 2.181/2024). A última foi entregue até 28/02/2025. Continua obrigatório o **Informe/Comprovante de Rendimentos** ao beneficiário, até o último dia útil de fevereiro (IN RFB 2.060/2021). Esse item está **faltando** no catálogo.
5. **Reforma tributária:**
   - Em 2026 vale o destaque informativo de CBS 0,9% e IBS 0,1% em NF-e, NFC-e, CT-e e NFS-e. As penalidades pela falta dos campos ficaram dispensadas pelo Ato Conjunto RFB/CGIBS 1/2025 até 1º/08/2026. A RFB anunciou que não multará em 2026 e que dará prazo de 60 dias para regularizar (LC 214/2025, art. 348). Estados e municípios não se vincularam a essa promessa.
   - A LC 214/2025 (art. 542) revoga o art. 18 da MP 2.158-35 **a partir de 01/01/2027**, quando PIS/COFINS dão lugar à CBS. **Os itens PIS_COFINS e EFD_CONTRIBUICOES precisam de data de término**, com última competência em 12/2026; a EFD-Contribuições dessa competência ainda vence em fevereiro de 2027.
   - O Simples "híbrido" (IBS/CBS pelo regime regular) teve janela de opção de 01 a 30/09/2026 para o 1º semestre de 2027 (Res. CGSN 186/2026).
6. **Itens novos recomendados:**
   - Informe de Rendimentos;
   - 13º salário: 1ª parcela, 2ª parcela e DCTFWeb/eSocial/DARF anuais em 20/12, com antecipação;
   - parcelamentos (parcela no último dia útil do mês), opcional;
   - estimativa mensal de IRPJ/CSLL no Lucro Real anual, opcional;
   - conferência mensal de destaque de CBS/IBS, prazo interno, opcional.

---

## 2. Tabela item a item

Legenda: **OK** = mantém. **Corrigir** = alteração confirmada em fonte. **A confirmar** = ponto de atenção sem fonte primária suficiente; não alterar por ora.

| Código | Situação | O que mudar | Fundamento legal e fonte |
|---|---|---|---|
| PGDAS_D | OK, com ajuste de texto | Prazo dia 20, com prorrogação: OK. Multa: acrescentar "limitada a 20%". Desde 01/2026, a multa corre a partir do dia seguinte ao vencimento. | LC 123/2006, art. 18, §15-A e art. 38-A, §2º (mín. R$ 50/mês). [Fenacon](https://fenacon.org.br/reforma-tributaria/novas-regras-para-multas-por-atraso-na-entrega-das-declaracoes-do-simples-nacional/) |
| DAS | OK, com ajuste de regex | Prazo OK. Incluir `SIMEI` e `Parcelamento` em `exclui` (evita confundir com DAS-MEI e DAS de parcelamento). | Res. CGSN 140/2018, art. 40; LC 123, art. 21, III |
| DAS_MEI | OK, com ajuste de regex | Aceitar `SIMEI` como marcador de MEI. A composição do DAS-MEI traz "INSS - SIMEI", "ISS - SIMEI" e "ICMS - SIMEI", nem sempre "Microempreendedor". | LC 123, art. 18-A. Artigo da Res. CGSN 140 para o vencimento: a confirmar |
| DASN_SIMEI | OK | 31/05 do ano seguinte. | Res. CGSN 140/2018, art. 109 |
| DEFIS | Corrigir | Multa: "LC 123, art. 38-A" passa a ser "LC 123, art. 38, §3º". | [Fenacon](https://fenacon.org.br/reforma-tributaria/novas-regras-para-multas-por-atraso-na-entrega-das-declaracoes-do-simples-nacional/), [LegisWeb](https://www.legisweb.com.br/noticia/?id=31981) |
| DESTDA | Corrigir | Aplicabilidade: `exige: ["comercio"]` passa a `exige_algum: ["comercio", "industria"]`. Há UFs com dispensa: usar `personalizacoes`. | Ajuste SINIEF 12/2015 (dia 28 do mês seguinte) |
| DCTFWEB | Corrigir | Base legal: IN 2.237/2024, arts. 3º, 4º e 6º. Multa com os mínimos corretos. Aplicabilidade: incluir MEI com empregado e Simples com retenção. Prazo (último dia útil do mês seguinte): **OK**. | IN RFB 2.237/2024, art. 6º (red. IN 2.248/2025) e art. 11. [Normas Legais](https://www.normaslegais.com.br/legislacao/in-rfb-2237-2024.htm), [RFB](https://normas.receita.fazenda.gov.br/sijut2consulta/link.action?idAto=141910), [COAD](https://www.coad.com.br/home/noticias-detalhe/130294/rfb-prorroga-prazo-de-apresentacao-da-dctfweb) |
| DARF_DCTFWEB | Corrigir | Aplicabilidade: incluir MEI com empregado; para Presumido/Real/Imune, incluir `retem_tributos`. Reconhecimento: acrescentar o código 0561 (IRRF sobre salário). Base legal: acrescentar o IRRF. | Lei 8.212/1991, art. 30, I, "b"; Lei 11.196/2005, art. 70, I, "d" |
| EFD_REINF | Corrigir | `ajuste`: "antecipa" passa a "posterga". Base legal: incluir a IN 2.163/2023. Reconhecimento: acrescentar `R-2099` e `R-4099`. | IN RFB 2.043/2021 (red. IN RFB 2.163/2023). [NetCPA](https://netcpa.com.br/noticias/urgente-reinf-alteracoes-e-prorrogacao-do-prazo-para-o-proximo-dia-util/17096) |
| PIS_COFINS | Corrigir | Base legal. Término em 12/2026 (CBS a partir de 2027): ver alteração opcional em agenda.py. | MP 2.158-35/2001, art. 18, II e par. único (red. Lei 11.933/2009). [Lei 11.933](https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2009/lei/L11933.htm), [LegJur: revogação pela LC 214, art. 542](https://www.legjur.com/legislacao/art/mpv_0002158352001-18) |
| IRPJ_CSLL | OK | Prazo OK (último dia útil do mês seguinte ao trimestre, em quota única). O código 2484 (CSLL por estimativa mensal) pertence ao item novo IRPJ_CSLL_ESTIMATIVA. | Lei 9.430/1996, arts. 1º, 5º e 6º |
| EFD_CONTRIBUICOES | OK, com ajuste de texto | Multa: citar o art. 57 da MP 2.158-35 (red. Lei 12.766/2012). Término na competência 12/2026. Imunes e isentas: obrigadas quando PIS/COFINS/folha passa de R$ 10 mil por mês (usar personalização). | IN RFB 1.252/2012, art. 5º |
| EFD_ICMS_IPI | OK | Prazo varia por UF (personalização). | Ajuste SINIEF 02/2009 |
| ICMS | OK | Prazo varia por UF. | Legislação estadual |
| ISS | OK | Prazo varia por município. NFS-e Padrão Nacional obrigatória desde 01/2026. | LC 116/2003; LC 214/2025, art. 62. [Fenacon](https://fenacon.org.br/reforma-tributaria/nota-fiscal-de-servico-eletronica-nfs-e-sera-obrigatoria-a-partir-de-janeiro-de-2026/) |
| DMED | Corrigir | Multa: R$ 500/R$ 1.500 por mês-calendário. | MP 2.158-35, art. 57, I. [Econet](https://blog.econeteditora.com.br/como-apurar-e-recolher-a-multa-no-atraso-da-entrega-da-dirf-dmed-e-dimob-2/), [Contábeis](https://www.contabeis.com.br/noticias/74748/quem-deve-entregar-a-dmed-2026-e-qual-o-prazo-para-declarar/) |
| DIMOB | Corrigir | Multa: idem DMED. | IN RFB 1.115/2010; MP 2.158-35, art. 57. [Econet](https://blog.econeteditora.com.br/como-apurar-e-recolher-a-multa-no-atraso-da-entrega-da-dirf-dmed-e-dimob-2/) |
| BALANCETE | OK | Prazo interno. | ITG 2000 (R1) |
| DEMONSTRACOES_ANUAIS | OK, com ajuste de texto | Base legal: acrescentar CC, arts. 1.078 (aprovação em até 4 meses, o que sustenta o prazo de 30/04) e 1.179; ITG 2002 (R1) para o 3º setor. | Lei 6.404/1976, art. 176; CC/2002 |
| ECD | OK | Prazo confirmado. Ressalva: o Presumido com Livro Caixa e o imune/isento com receita até R$ 4,8 milhões podem ser dispensados (IN 2.003, art. 3º). Manter como padrão do escritório e tratar exceções com `ignorar`. | IN RFB 2.003/2021, art. 5º (red. IN RFB 2.142/2023). [Senior](https://documentacao.senior.com.br/exigenciaslegais/noticias/federal/2023/2023-06-07-in-rfb-n-2142-2023-receita-federal-ratifica-novo-prazo-para-entrega-da-ecd) |
| ECF | Corrigir | Multa: corrigir a citação. Prazo OK. | IN RFB 2.004/2021, art. 3º; DL 1.598/1977, art. 8º-A. [Econet](https://blog.econeteditora.com.br/ecf-2026-quem-deve-entregar-prazo-dispensas-e-multas/) |
| FOLHA | OK | Prazo interno (o legal é o 5º dia útil). | CLT, art. 459, §1º |
| PROLABORE | OK | | Lei 8.212/1991 |
| ESOCIAL | Corrigir | `ajuste`: "antecipa" passa a "posterga". Aplicabilidade: incluir MEI com empregado. Para MEI, o prazo é dia 7 com antecipação: configurar por personalização. | MOS eSocial. [CRCMS](https://crcms.org.br/?p=26911), [Senior](https://documentacao.senior.com.br/seniorxplatform/manual-do-usuario/hcm/folha-x/esocial/eventos-periodicos/s-1299) |
| FGTS_DIGITAL | OK | Dia 20 com antecipação, confirmado (Caixa/MTE). O artigo exato (15 ou 17 da Lei 8.036) fica a confirmar. | Lei 8.036/1990 (red. Lei 14.438/2022); Portaria MTE 240/2024. [Contábeis](https://www.contabeis.com.br/noticias/63928/fgts-digital-caixa-esclarece-como-ficara-vencimento-em-dia-nao-util/) |
| DOC_EXTRATOS | OK | Prazo contratual. | NBC PG 01 |
| DOC_NOTAS_FISCAIS | OK | | CTN, art. 195 |
| DOC_VARIAVEIS_FOLHA | OK | | CLT, art. 74 |

---

## 3. Verificações pedidas

| Ponto | Conclusão | Fonte |
|---|---|---|
| Prazo da DCTFWeb | Último dia útil do mês seguinte (IN 2.237, art. 6º, red. IN 2.248/2025). A redação original previa dia 25. Sem movimento: entrega só no 1º mês sem movimento (art. 6º, §2º). Anual (13º): até 20/12, antecipando (art. 7º, I). Assinatura via gov.br para MEI e ME/EPP com até 1 empregado. | [Normas Legais](https://www.normaslegais.com.br/legislacao/in-rfb-2237-2024.htm), [Senior](https://documentacao.senior.com.br/exigenciaslegais/noticias/federal/2024/2024-12-05-substituicao-da-dctf-pela-dctfweb-a-partir-de-janeiro-de-2025) |
| ECD | Último dia útil de junho (IN 2.142/2023 alterou a IN 2.003/2021, art. 5º) | [Senior](https://documentacao.senior.com.br/exigenciaslegais/noticias/federal/2023/2023-06-07-in-rfb-n-2142-2023-receita-federal-ratifica-novo-prazo-para-entrega-da-ecd) |
| ECF | Último dia útil de julho | [Econet](https://blog.econeteditora.com.br/ecf-2026-quem-deve-entregar-prazo-dispensas-e-multas/) |
| EFD-Reinf | Dia 15 do mês seguinte, **prorrogado** se não for útil (IN 2.163/2023) | [NetCPA](https://netcpa.com.br/noticias/urgente-reinf-alteracoes-e-prorrogacao-do-prazo-para-o-proximo-dia-util/17096) |
| FGTS Digital | Dia 20, **antecipa** | [Contábeis](https://www.contabeis.com.br/noticias/63928/fgts-digital-caixa-esclarece-como-ficara-vencimento-em-dia-nao-util/) |
| DAS/PGDAS-D | Dia 20, prorroga (DAS). O PGDAS-D acompanha o vencimento do DAS. | Res. CGSN 140/2018 |
| EFD-Contribuições | 10º dia útil do 2º mês, OK | IN RFB 1.252/2012 |
| DMED/DIMOB | Último dia útil de fevereiro, OK | [Contábeis](https://www.contabeis.com.br/noticias/74748/quem-deve-entregar-a-dmed-2026-e-qual-o-prazo-para-declarar/) |
| DEFIS / DASN-SIMEI | 31/03 e 31/05, OK | Res. CGSN 140/2018 |
| DeSTDA | Dia 28, OK. Algumas UFs dispensam. | Ajuste SINIEF 12/2015 |
| DIRF | **Extinta** a partir do ano-calendário 2025. Informe de rendimentos mantido. | [Senior](https://documentacao.senior.com.br/exigenciaslegais/noticias/federal/2024/2024-03-15-in-rfb-2181-2024-extincao-da-dirf-prorrogada-para-2025-veja-o-que-muda), [Contábeis](https://www.contabeis.com.br/noticias/73208/fim-da-dirf-o-que-muda-no-informe-de-rendimento/) |
| Reforma 2026 | Destaque CBS/IBS nos documentos fiscais; Simples "puro" fora em 2026; penalidades dispensadas até 01/08/2026; RFB sem multa em 2026, com 60 dias para regularizar; regulamento publicado em 30/04/2026 (Decreto 12.955/2026). | [Comsefaz](https://comsefaz.org.br/novo/reforma-tributaria-comeca-em-2026-com-periodo-de-adaptacao-destaque-informativo-dos-novos-tributos-e-dispensa-de-penalidades/), [Correio Braziliense](https://blogs.correiobraziliense.com.br/jusbraziliense/2026/07/01/reforma-tributaria-e-obrigacoes-acessorias-em-2026-o-limbo-entre-1o-de-agosto-e-a-promessa-da-receita-federal/), [Fenacon](https://fenacon.org.br/reforma-tributaria/multa-por-falta-de-cbs-e-ibs-em-notas-e-suspensa-no-inicio-de-2026/) |
| Simples 2027 / híbrido | Opção de 01 a 30/09/2026 (Res. CGSN 186/2026); cancelamento da opção até 30/11/2026 | [NetCPA](https://netcpa.com.br/colunas/cgsn-define-prazos-de-opcao-pelo-simples-nacional-e-pelo-regime-regular-do-ibs-e-da-cbs-para-2027/27640) |
| GIA-SP | GIA-ST dispensada desde 07/2025; GIA-ICMS em extinção gradual (dispensa por notificação no DEC). Não incluir item fixo; usar personalização. | [COAD](https://coad.com.br/home/noticias-detalhe/130193/sao-paulo-vai-deixar-de-exigir-a-gia-st-a-partir-de-julho-de-2025) |
| RAIS / CAGED | Substituídos pelo eSocial: **não incluir** | Portaria SEPRT 1.127/2019 |

---

## 4. Itens novos sugeridos

| Código | Por quê | Aplicação |
|---|---|---|
| INFORME_RENDIMENTOS | Obrigatório após o fim da DIRF; vence no último dia útil de fevereiro | Empresas com funcionários, pró-labore ou retenções |
| DECIMO_TERCEIRO_1A | 1ª parcela até 30/11 (Lei 4.749/1965, art. 2º) | Empresas com funcionários |
| DECIMO_TERCEIRO_2A | 2ª parcela até 20/12 (Lei 4.749/1965, art. 1º) | Empresas com funcionários |
| DCTFWEB_ANUAL | DCTFWeb do 13º até 20/12, antecipando (IN 2.237, art. 7º, I); eSocial anual e DARF do 13º no mesmo dia | Empresas com funcionários |
| PARCELAMENTO | Parcela vence no último dia útil do mês (Lei 10.522/2002, art. 13) | Opcional (`incluir` por empresa) |
| IRPJ_CSLL_ESTIMATIVA | Lucro Real anual: estimativa mensal (Lei 9.430/1996, art. 2º e art. 6º) | Opcional (`incluir`) |
| REFORMA_CBS_IBS | Conferência interna mensal do destaque CBS/IBS e do cClassTrib nas notas | Opcional; Presumido/Real |

Itens **não recomendados** como item fixo: DIRPF dos sócios (não é obrigação da PJ; se o escritório presta o serviço, usar um módulo próprio), SINTEGRA e declarações municipais de ISS (variam demais; usar `personalizacoes` com `incluir` e `regra`), férias (por evento, não periódica), RAIS e CAGED (extintos para quem está no eSocial).

---

## 5. Ressalvas

1. **Dias não úteis.** `calendario.py` trata Carnaval e Corpus Christi como não úteis, o que é aceitável para fins bancários. **31/12** não tem expediente bancário ao público (FEBRABAN), mas o calendário o considera útil. Isso afeta prazos que caem nesse dia. Feriados estaduais e municipais dependem de `FERIADOS_EXTRAS`.
2. **13º e itens anuais.** O motor só gera itens anuais na competência 12. Para que as tarefas de 13º (30/11 e 20/12) nasçam a tempo, a agenda da competência **AAAA-12** deve ser gerada **até 31/10**. Isso não causa efeito colateral: as demais tarefas da competência 12 apenas ficam a vencer.
3. **DARF único da DCTFWeb com MIT.** Desde 2025, o DARF emitido pela DCTFWeb pode reunir no mesmo documento CP (1082/1138), IRRF (0561), PIS/COFINS (8109/2172) e IRPJ/CSLL (2089/2372). O classificador escolhe uma única obrigação e pode haver empate, que manda o documento para a fila de revisão. A evolução recomendada é permitir que um documento baixe várias tarefas. Isso é uma melhoria de código, fora do catálogo.
4. **Fim de PIS/COFINS em 2027 (LC 214/2025).** Recomenda-se uma chave de vigência; ver a alteração opcional em `agenda.py`. Itens de CBS e IBS para 2027 (apuração, eventual declaração) ainda não têm leiaute definitivo. Monitorar.
5. Valores de multa no catálogo são **referência**. O cálculo efetivo depende do regime, das reduções (50% para ME/EPP e 90% para MEI na DCTFWeb) e da denúncia espontânea.
6. Várias fontes consultadas são secundárias (portais e entidades contábeis), porque o site de normas da RFB e o Planalto estavam inacessíveis ao robô. Marquei como "a confirmar" o que não teve confirmação convergente.

---

## 6. Patch sugerido

O arquivo `docs/revisao/catalogo-sugerido.patch` aplica em `mo_obrigacoes/catalogo.py` todas as correções marcadas como "Corrigir" e os 7 itens novos.

- **Aplicar:** `patch -p0 < docs/revisao/catalogo-sugerido.patch`
- **Validação:** o patch foi aplicado numa cópia do repositório e os **23 testes existentes passaram** sem alteração. Também foi feita uma checagem de classificação com documentos de exemplo: DAS-MEI com "SIMEI", DAS de parcelamento, DARF 0561 e 2362, informe de rendimentos, 13º (1ª e 2ª parcelas), DCTFWeb anual e Reinf R-4099.
- **Itens opcionais:** `PARCELAMENTO`, `IRPJ_CSLL_ESTIMATIVA` e `REFORMA_CBS_IBS` usam flags que não existem no modelo (`possui_parcelamento`, `estimativa_mensal`, `monitorar_reforma`). Por isso só entram na agenda quando a empresa tem `personalizacoes = {"<CODIGO>": {"incluir": true}}`.
