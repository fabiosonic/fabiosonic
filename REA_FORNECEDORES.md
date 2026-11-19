# Relatório de Engenharia Reversa Autorizada (REA): fornecedores que prometem XML de SAÍDA NF-e/NFC-e do RJ

**Data do levantamento:** 19/11/2026
**Método:** apenas análise estática de material público, permitida pelo escopo:
- páginas comerciais;
- documentação de API pública;
- bases de conhecimento públicas;
- código aberto (NFePHP);
- normas oficiais (MOC, NT).

**O que não foi feito:** criar conta, fazer login, chamar API sem credencial válida, interceptar tráfego, extrair segredo, contornar bloqueio ou CAPTCHA. Páginas que recusaram acesso automatizado (HTTP 403, como o fórum Projeto ACBr, ou "conta inválida", como a base da SIEG) **não foram contornadas**. Nesses casos, quando citadas, usou-se apenas o resumo do buscador, e isso está sinalizado.

**Classificação:** CONFIRMADO · PROVÁVEL · NÃO COMPROVADO · IMPOSSÍVEL PELO MÉTODO.

## 1. Resumo por fornecedor

| Fornecedor | NF-e 55 RJ | NFC-e 65 RJ | Requisitos declarados | Natureza da evidência |
|---|---|---|---|---|
| **API Simples** (apisimples.com) | ✓ declarado | ✓ declarado | A1 do emitente + **XML semente por série dos últimos 60 dias**; "SP, AM e GO não exigem XML semente" para NFC-e | Documentação de API pública + página de cobertura que integra os Termos de Uso (17/11/2026) |
| **DFe Digital** (dfedigital.com.br) | ✓ "em produção" | ✓ "em produção" (também CT-e) | A1 da empresa; "19 UFs com notas emitidas capturadas direto na SEFAZ"; "consulta por chave: 1 crédito" | Página comercial + blog técnico (cStat 641 do DistDFe) |
| **Fluvi** (usefluvi.com.br) | ✓ "Atendido" | ✓ "Atendido" (23 UFs) | "somente com o certificado A1 do cliente"; não exige autXML; captura em nuvem; integração com Domínio via Integrador + pasta | Marketing + tabela de cobertura |
| **NF-Stock / Alterdata** | ✓ | ✓ (via "Controle Sefaz") | "cadastre um XML de saída emitido nos últimos 30 dias… reconhece o padrão da série… descobre e baixa as próximas"; RJ: "a partir de 10 dias após a emissão… + 5 dias" | Base de conhecimento técnica (confiabilidade boa) |
| **SIEG** (HüB/Cofre) | ✓ (resumo de busca) | não encontrado | A1 + "um XML de cada série" de 30 a 60 dias; janela de 60 dias | **Página bloqueada**; só o resumo do buscador (NÃO COMPROVADO) |
| **Jettax** | "Brasil inteiro" | ✗ (NFC-e só PB, BA, GO, MG, SC, SP) | A1 | Marketing com listas contraditórias |
| **Fisco Fácil** | — | — | **Não é fornecedor**: sistema oficial da SEFAZ-RJ ("Extração de documentos fiscais", lote assíncrono, cerca de 10 dias de defasagem) | Manual NFC-e SEFAZ-RJ + fórum. **Excluído por decisão do escritório** |
| Espião NF-e | não encontrado | só SP declarado | A1 | Marketing |
| Qive/Arquivei, e-Auditoria, Focus NFe, PlugNotas, Nuvem Fiscal, Oobj, Systax, FiscalAPI, Sittax, Kolossus, Gestta, BaixaXML, Onvio/Domínio, Questor, Fortes, Tributos.io | sem promessa de saída RJ sem autXML | — | — | Saída apenas por importação, autXML, emissão própria ou DistDFe (entrada) |

## 2. O que os indícios públicos revelam sobre o mecanismo

### 2.1 Fase 1: descoberta da chave por consulta de situação (regra J04/562)

**PROVÁVEL** (a mais bem fundamentada).

1. **API Simples**, **NF-Stock** e **SIEG** exigem um XML **por série**, recente (30 a 60 dias), e validam modelo e CNPJ. É exatamente o que basta para montar a parte fixa da chave candidata (cUF, AAMM, CNPJ, mod, série) e caminhar pelo nNF.
2. O MOC (NFeConsultaProtocolo, J03/J04) prevê que a SEFAZ **devolva a chave existente** na rejeição 562 quando o certificado é do emitente (NT 2010.007). Conferido no MOC online em 19/11/2026.
3. A janela de 30 a 60 dias para a semente é coerente com a regra J02k (chave com mais de 6 meses → 526) e com a necessidade de começar perto do número atual.
4. A NF-Stock exclui exatamente UFs com autorizador próprio (AM, BA, GO, MA, MG, PR, SP). Isso é coerente com a concatenação ser "opcional" e não implementada por todos. A SVRS (que atende o RJ) aparece como coberta.
5. A API da API Simples lista a nota (chave, número, situação, `cancelada`) **antes** de o XML existir (`xml_disponivel=false`, 404 "O XML da nota ainda não foi capturado"). Isso indica **duas fases distintas**: descoberta e download.

Nenhum fornecedor afirma isso explicitamente: é inferência. **Implementado** no conector `sefaz_consulta` e **pendente de teste real**.

### 2.2 Fase 2: XML integral no Portal DF-e SVRS com certificado

**PROVÁVEL**.

- O manual NFC-e da SEFAZ-RJ (pergunta 1.43, lido em cópia pública) diz: "No Portal DF-e, há dois serviços de recuperação de arquivo XML: um utilizando **série/número (com certificado digital)** e outro utilizando a chave de acesso".
- Notícia da SVRS de 12/02/2019 sobre o botão "Download Arquivo da NFC-e" para "usuário apresentando certificado digital desde que esteja relacionado com a NFC-e".
- `/NFESSL/DownloadXMLDFe` e `/NFCESSL/DownloadXMLDFe` observados em 19/11/2026: exigem certificado ICP-Brasil.
- A DFe Digital descreve UFs com "lista das notas… XML por chave, como o portal da SVRS".
- O padrão de cobertura de NFC-e da API Simples e da Fluvi ("estados da SEFAZ Virtual + SP, GO, AM") bate com o alcance desse portal.

**Ponto crítico em aberto (NÃO COMPROVADO):** há relato público (PortalSPED, 2020) de CAPTCHA "Não sou um robô" no download, e notícia de 2025 sobre consultas da SVRS migrando para login gov.br. **Não se sabe como os fornecedores automatizam essa etapa.** Este projeto **não contorna CAPTCHA**: se houver desafio, o conector registra IMPOSSÍVEL PELO MÉTODO para operação desassistida.

**Implementado** no conector `svrs_portal_download`, que lê o formulário em tempo de execução (sem campos inventados), aceita chave ou série/número e para diante de CAPTCHA.

### 2.3 Hipóteses descartadas ou não adotadas

| Hipótese | Evidência | Decisão |
|---|---|---|
| Extração em lote pelo Fisco Fácil (SEFAZ-RJ) | manual oficial; NF-Stock: "10 dias + 5 dias" | **Não usada** por decisão do escritório |
| DistDFe com o CNPJ do escritório em autXML | NT 2014.002 | **Não usada**: o escritório vetou a dependência de autXML |
| Reconstruir o XML a partir da consulta pública/QR Code e "colar" o protocolo | fórum ACBr (assinatura divergente, "remontagem"); FiscalAPI admite "cópia sem assinatura" | **Rejeitada**: não é o XML original. O validador do sistema confere DigestValue/SignatureValue e detectaria |
| Provocar a rejeição 539 enviando NF-e duplicada para autorização | regra 539 (duplicidade com chave diferente) | **Rejeitada**: risco real de autorizar documento fiscal, uso indevido do serviço de autorização |
| Força bruta do cNF (8 dígitos) | — | **Proibida** pelo escopo e inviável |

## 3. Conclusões

1. **Nenhum fornecedor publica o mecanismo**. O que há são indícios convergentes para "consulta J04/562 + Portal DF-e SVRS com certificado".
2. Esse caminho usa **apenas serviços oficiais** e o **A1 do próprio emitente**. Foi implementado de forma independente, sem endpoints privados de fornecedores.
3. O risco principal para operação desassistida é o **CAPTCHA/gov.br no portal**. Só um teste com certificado real resolve a dúvida (`diagnostico.bat <id>` registra a estrutura do formulário, sem valores, e `moxml teste-real` registra a evidência).
4. Se o portal se mostrar IMPOSSÍVEL PELO MÉTODO, as alternativas para o XML integral são:
   - (a) a pasta do emissor do cliente, que sempre tem o XML;
   - (b) o conector comercial opcional (API Simples), mantido desligado;
   - (c) a descoberta J04/562, que continua dando **chave, situação, protocolo e eventos**. Com isso se audita a numeração e se cobra do cliente exatamente quais XMLs faltam.

## 4. Fontes consultadas

- https://apisimples.com/documentacao/emitentes e https://apisimples.com/cobertura
- https://dfedigital.com.br/solucoes/contabilidade e https://dfedigital.com.br/produto/captura
- https://usefluvi.com.br/captura-nfe/ e https://usefluvi.com.br/cobertura/
- ajuda.alterdata.com.br (NF-Stock: "Controle Sefaz", "Ativar baixa de NFe/NFCe emitida")
- jettax.com.br/federal/
- https://portal.fazenda.sp.gov.br/servicos/nfce/Paginas/sae-nfce.aspx (NT SAE-NFC-e v1.0.0 e XSD)
- https://dfe-portal.svrs.rs.gov.br/Nfce (notícias), `/NFESSL/DownloadXMLDFe`, `/NFCESSL/DownloadXMLDFe`
- https://moc.sped.fazenda.pr.gov.br/NFe_NFCe/NFeConsultaProtocolo.html (regras J01 a J06)
- https://github.com/nfephp-org/sped-nfe (commit 4596b89, 13/11/2026): `src/SAE.php`, `docs/SAE.md`, `storage/wsae_nfce.json` (somente SP), `storage/autorizadores.json`, `storage/cstat.json`
- portalspedbrasil.com.br (p=15076, p=20741); fórum Contábeis, tópico 386640; Projeto ACBr, tópicos 52918, 64193 e 88163 (**403 ao acesso automatizado**; conteúdo só pelo resumo do buscador)

## 5. Exame do NFePHP (sped-nfe, commit 4596b89 de 13/11/2026)

| Item | Achado | Status |
|---|---|---|
| Classe `src/SAE.php` | Implementa `listagemChaves($dataHoraInicial, $dataHoraFinal)` e `downloadXML($chNFCe)`. Envelope SOAP 1.2 com `nfeDadosMsg` no namespace `http://www.portalfiscal.inf.br/nfe/wsdl/<operation>`; action `"<ns>/<method>"`; autenticação por `SoapCurl` com o certificado (mTLS). Valida formato `AAAA-MM-DDThh:mm` e chave de 44 caracteres. Sem assinatura XML (o SAE não exige). | CONFIRMADO (leitura do código) |
| `storage/wsae_nfce.json` | Somente **SP** (`homologacao.nfce.fazenda.sp.gov.br` / `nfce.fazenda.sp.gov.br`). **RJ não está configurado**; o construtor lança `InvalidArgumentException("SAE-NFC-e não disponível para o estado [RJ]")`. | CONFIRMADO |
| Paginação | Documentada em `docs/SAE.md`: em cStat 101, usar `dhEmisUltNfce` truncado para minutos como novo início. | CONFIRMADO |
| Códigos de retorno | 100/101/107/104/110/656 (listagem); 200/203/204/205/207/656 (download). Conferem com a NT SP v1.00. | CONFIRMADO |
| Eventos | O download devolve `procEventoNFe` simplificados (dhInc, nProt, evento) e `nfeProc` **sem `protNFe`**. | CONFIRMADO (NT e XSD) |
| Testes | `tests/SAETest.php` usa `SoapFake`; não há teste contra ambiente real. | CONFIRMADO |
| Autorizadores | `storage/autorizadores.json`: RJ → SVRS para os modelos 55 e 65. | CONFIRMADO |
| Rejeição 562 | `storage/cstat.json`: "Código Numérico informado na Chave de Acesso difere do Código Numérico da NF-e [chNFe:…]". | CONFIRMADO |

**Decisão:** o NFePHP **não** é usado como serviço auxiliar. Não há vantagem técnica comprovada para o RJ, porque o SAE não existe lá. O transporte SOAP, o envelope e o tratamento de códigos foram implementados em Python com o mesmo padrão de envelope e cobertos por testes. Isso evita manter um runtime PHP no Windows do escritório.
