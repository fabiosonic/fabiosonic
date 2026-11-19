# Fontes fiscais — matriz oficial e matriz de cobertura (RJ prioritário)

Levantamento feito em **19/11/2026**. Classificação de evidência:

- **CONFIRMADO**: documento oficial lido ou comportamento observado diretamente.
- **PROVÁVEL**: hipótese com fundamento técnico.
- **NÃO COMPROVADO**: falta evidência suficiente.
- **IMPOSSÍVEL PELO MÉTODO**: limitação demonstrada.

Nenhum serviço foi chamado com certificado real: este ambiente não tem certificado A1 autorizado. Por isso a coluna "Teste autorizado" está **pendente** em todos os serviços.

## 1. Fatos estruturais do RJ

| Fato | Evidência | Status |
|---|---|---|
| A NF-e 55 do RJ é autorizada pela SVRS (SEFAZ Virtual do RS) | `storage/autorizadores.json` do NFePHP: `"RJ": "SVRS"` para os modelos 55 e 65; manual NFC-e da SEFAZ-RJ (pergunta 1.43, lido em cópia pública): "O Rio de Janeiro utiliza os webservices da SEFAZ Virtual do Rio Grande do Sul" | CONFIRMADO (documental) |
| A NFC-e 65 do RJ é autorizada pela SVRS | mesmas fontes | CONFIRMADO (documental) |
| O portal da SEFAZ-RJ bloqueia IPs de datacenter | `portal.fazenda.rj.gov.br/dfe/` respondeu, a partir deste ambiente de nuvem, com página de bloqueio por reputação de IP | CONFIRMADO (observado). No escritório, use internet comum |
| Não existe webservice público de **listagem** de NF-e/NFC-e emitidas para o próprio emitente no RJ/SVRS | não há NT SVRS/RJ equivalente ao SAE-SP; `wsae_nfce.json` do NFePHP só configura SP | CONFIRMADO (ausência documental até 19/11/2026) |
| O DistDFe (Ambiente Nacional) não entrega ao emitente as notas que ele próprio emitiu | NT 2014.002; fóruns e fornecedores (DFe Digital, cStat 641) | CONFIRMADO. **Fora da arquitetura**: depende de autXML, vetado pelo escritório |
| O DistDFe não distribui NFC-e | NT 2014.002 (somente NF-e) | CONFIRMADO |

## 2. Matriz de serviços oficiais

| # | URL oficial | Operação | Modelo | UF | Ambiente | Autenticação | Layout | Limites | Evidência de disponibilidade | Teste autorizado |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `https://nfe.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx` | NFeConsultaProtocolo 4.00 (`consSitNFe`) | 55 | RJ (SVRS) | produção | mTLS com e-CNPJ ICP-Brasil | MOC 7.0; XSD `consSitNFe_v4.00` | 656 (consumo indevido); J02k: chave com mais de 6 meses → 526 (facultativo) | URL no NFePHP e no Portal NF-e; MOC online (moc.sped.fazenda.pr.gov.br) | **pendente** |
| 2 | `https://nfe-homologacao.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx` | idem | 55 | RJ | homologação | idem | idem | idem | idem | pendente |
| 3 | `https://nfce.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx` | idem | 65 | RJ | produção | idem | idem | idem | idem | **pendente** |
| 4 | `https://nfce-homologacao.svrs.rs.gov.br/ws/NfeConsulta/NfeConsulta4.asmx` | idem | 65 | RJ | homologação | idem | idem | idem | idem | pendente |
| 5 | `https://dfe-portal.svrs.rs.gov.br/NFESSL/DownloadXMLDFe` | Portal DF-e: download do XML por chave (e, segundo o manual RJ, por série/número) | 55 | RJ (SVRS) | produção | certificado ICP-Brasil "relacionado ao documento" (TLS cliente) | página web (formulário) | não publicados; possível CAPTCHA | notícia SVRS 12/02/2019; resposta observada em 19/11/2026: "Esta consulta exige Certificado Digital emitido por AC credenciada junto ao ICP-Brasil" | **pendente** |
| 6 | `https://dfe-portal.svrs.rs.gov.br/NFCESSL/DownloadXMLDFe` | idem | 65 | RJ | produção | idem | idem | idem | idem | **pendente** |
| 7 | `https://nfce.fazenda.sp.gov.br/ws/NFCeListagemChaves.asmx` | SAE-NFC-e: listagem de chaves | 65 | SP | produção (há homologação) | mTLS e-CNPJ | NT "Serviços de Apoio à Escrituração da NFC-e" v1.00 + XSD (arquivados em `backend/moxml/sefaz/schemas/sae/`) | 2000 chaves por chamada (101 → paginar por `dhEmisUltNfce`); 100 dias; limite por IP (656) | NT oficial SEFAZ-SP | pendente (fora do RJ) |
| 7b | `https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx` | NFeDistribuicaoDFe `consChNFe` (XML completo por chave) | 55 | AN | produção (há homologação) | mTLS e-CNPJ do emitente | NT 2014.002; `docZip` gzip+base64 | ~3 meses; 656 | código verificado (PyTrustNFe/nfelib); fixture com `procNFe` completo | **pendente** |
| 8 | `https://nfce.fazenda.sp.gov.br/ws/NFCeDownloadXML.asmx` | SAE-NFC-e: download por chave | 65 | SP | produção | mTLS | idem; o `nfeProc` retornado é **simplificado** (sem `protNFe`) | 100 dias; 656 | idem | pendente |
| 9 | `https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx` | DistDFe | 55 | AN | produção | mTLS | NT 2014.002 | 3 meses, NSU | oficial | **não usado** (exige autXML ou papel de destinatário) |
| 10 | Fisco Fácil (SEFAZ-RJ): "Extração de documentos fiscais" | extração em lote (web, pedido assíncrono) | 55/65 | RJ | produção | e-CNPJ ou procuração | web | segundo relatos, ~10 dias de defasagem e 3 pedidos simultâneos | manual NFC-e RJ 1.43 (cópia pública) + fórum Contábeis | **excluído por decisão do escritório** |

Diferença entre serviço ao contribuinte e serviço interno: os itens 1 a 9 são publicados para contribuintes (MOC/NT/portal público). Este projeto não usa nenhum serviço interno entre administrações tributárias, nem endpoint não publicado.

## 3. Mecanismo oficial adotado para o RJ (sem autXML, sem Fisco Fácil)

**Etapa A: descoberta da chave (NFeConsultaProtocolo, regras do MOC)**

O MOC (Web Service NFeConsultaProtocolo, seção "Validação das regras de negócio") prevê, conferido no MOC online em 19/11/2026:

- **J03**: acesso ao BD pela chave natural *CNPJ/CPF emitente + modelo + série + número*. Inexistente → **217**.
- **J04**: "Verificar se campo Código Numérico informado na Chave de Acesso é diferente do existente no BD" → **562**. Observação do MOC: *"Opcionalmente, concatenar na mensagem de erro a Chave de Acesso da NF-e existente no BD nas situações de: CNPJ base do certificado digital de transmissão igual ao CNPJ base do emitente…"* (NT 2010.007).
- **J05**: mês divergente → **561**. **J06**: outra divergência → **613**. **J02k**: AAMM com mais de 6 meses → **526** (facultativo).

Com o A1 do emitente e os campos fixos tirados do XML semente (UF, CNPJ, modelo, série), o sistema faz **uma consulta por número**. A SEFAZ devolve a chave existente na própria mensagem 562. Não há força bruta do cNF: o código numérico candidato é sempre `00000000`.

Status: **PROVÁVEL** para a SVRS. A concatenação é "opcional" no MOC e precisa ser confirmada com certificado real (`moxml teste-real`). O laboratório reproduz a regra; se a SVRS não concatenar, o conector levanta `DescobertaImpossivel` e a fonte fica marcada como **IMPOSSÍVEL PELO MÉTODO**.

**Etapa B: situação e eventos (NFeConsultaProtocolo com a chave real)**

Retorna `protNFe` e `procEventoNFe` (cancelamento, CC-e). Status: **CONFIRMADO** documentalmente (MOC). Nunca é tratado como XML integral.

**Etapa C: XML integral — a verdade confirmada (55 e 65)**

> Correção (19/11/2026): a hipótese de obter o `procNFe` do emitente pela `NFeDistribuicaoDFe consChNFe` foi **refutada**. O fixture do `nfelib` é dado sintético de teste, não prova de comportamento do AN. O MOC da `NFeDistribuicaoDFe` define **cStat 641 "NF-e indisponível para o emitente"**: a Distribuição DFe NÃO entrega ao emitente o XML da própria nota. E não distribui NFC-e. A SEFAZ-SP confirmou por escrito que não há webservice de captura de NFC-e por CNPJ sem a chave.

Portanto, **não existe webservice da SEFAZ** que devolva o XML completo das notas de saída ao emitente. Pela SEFAZ, o XML completo (55 e 65) só sai pelo **Portal DF-e SVRS (DownloadXMLDFe) com A1**.

> **CAPTCHA CONFIRMADO (19/11/2026):** teste `moxml svrs` com certificado A1 real (CNPJ 09.295.435/0001-85) provou que o Portal DF-e SVRS **exige CAPTCHA** para 55 e 65 (`portal_captcha: true`, download interrompido com `CaptchaExigido`). Conclusão: **a captura 100% automática do XML diretamente da SVRS é IMPOSSÍVEL PELO MÉTODO** para o RJ. O XML completo das notas novas, de forma automática, só pela origem (sistema emissor do cliente) ou por fornecedor comercial.

Status: **NÃO COMPROVADO**. O formulário só aparece com certificado ICP-Brasil. Há relato público (PortalSPED, 2020) de CAPTCHA "Não sou um robô". Se houver CAPTCHA, o conector **para** e registra **IMPOSSÍVEL PELO MÉTODO**: o sistema não contorna desafios humanos.

**Fonte complementar sempre disponível: pasta do emissor**

O emitente é obrigado a guardar o XML. Quando o ERP/PDV do cliente grava os arquivos em pasta, o conector `pasta_emissor` importa, valida e completa o protocolo pela Etapa B quando o XML veio sem protocolo.

## 4. Matriz de cobertura UF × modelo × fonte (estado em 19/11/2026)

| UF | Modelo | Descoberta | XML integral | Eventos | Status operacional |
|---|---|---|---|---|---|
| RJ | 55 | Consulta J04/562 (PROVÁVEL) | **DistDFe por chave — webservice, sem CAPTCHA (NÃO COMPROVADO)** · Portal SVRS · pasta do emissor · API Simples (opcional) | DistDFe/consulta de situação | **Não operacional até o teste real** (critérios 1 a 10, seção 17) |
| RJ | 65 | Consulta J04/562 (PROVÁVEL) | Portal SVRS (NÃO COMPROVADO) · pasta do emissor · API Simples (opcional) | Consulta de situação | **Não operacional até o teste real**, avaliado separadamente do modelo 55 |
| SP | 65 | SAE ListagemChaves (documentado) | SAE DownloadXML + protocolo pela consulta | SAE | Fora do escopo inicial; conector pronto, NÃO COMPROVADO |
| SP | 55 | sem fonte oficial | pasta do emissor | — | IMPOSSÍVEL PELO MÉTODO oficial (a própria DFe Digital afirma: "a SEFAZ-SP não oferece as NF-e emitidas") |

A matriz é gerada em tempo real em **Integrações** no painel (`GET /api/integracoes`).

## 5. Como incluir outra UF sem alterar o núcleo

1. Confirmar o serviço em documento oficial e registrá-lo neste arquivo.
2. Incluir as URLs em `catalogo_local.json`, em `MOXML_HOME` (mesma estrutura de `backend/moxml/sefaz/catalogo.json`).
3. Rodar `moxml teste-real` com um CNPJ autorizado daquela UF.
