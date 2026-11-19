# M&O XML Captador

Captura de XML de **saída** de **NF-e (modelo 55)** e **NFC-e (modelo 65)** de empresas do **Rio de Janeiro**, para a **MORAES E OLIVEIRA CONTABILIDADE LTDA**.

**Independente** do Fisco Fácil, do Hubstrom e do autXML. Prioriza fontes oficiais e usa o certificado A1 do próprio emitente, com autorização registrada.

> **Situação (19/11/2026):** software completo e testado em laboratório (67 testes em Python 3.14.6). **Nenhuma recuperação real de XML foi feita ainda**: falta o teste com um certificado A1 autorizado. Até esse teste (`moxml teste-real`, um por modelo), nenhuma UF/modelo é considerada operacional. Ver [LIMITACOES.md](LIMITACOES.md).

## Como funciona no RJ
1. **XML semente** por série: fornece CNPJ, modelo, série e numeração.
2. **Descoberta oficial** (NFeConsultaProtocolo/SVRS): uma consulta por número. O MOC (regra J04, cStat 562) prevê que a SEFAZ devolva ao emitente a chave existente. Sem força bruta. *Provável; confirmar no teste real.*
3. **Situação e eventos**: protocolo, cancelamentos e CC-e pela mesma consulta.
4. **XML integral — NF-e 55**: **NFeDistribuicaoDFe por chave** (`consChNFe`, Ambiente Nacional, webservice, mTLS). O emitente consulta a própria nota pela chave e recebe o `nfeProc` completo com protocolo e eventos. **Sem CAPTCHA e sem autXML** (autXML é só para terceiros; o emitente tem direito ao próprio documento). *A confirmar no teste real.*
5. **XML integral — NFC-e 65**: a Distribuição DFe não cobre NFC-e. A via da SEFAZ é o Portal DF-e SVRS (`DownloadXMLDFe`); se exigir CAPTCHA, o sistema não o contorna.
6. **Validação** (assinatura criptográfica, chave/DV, protocolo, XSD PL_010g), **deduplicação**, gravação sem sobrescrever, **auditoria de numeração**, **Google Drive** com confirmação por MD5 e **pacote para o Domínio**.

## Início rápido (Windows)
```bat
windows\instalar.bat          :: instala, migra o banco e registra o serviço
start http://127.0.0.1:8765   :: painel (opera somente com notas reais)
windows\testar.bat            :: testes automatizados
```
O sistema **não possui modo de simulação** em operação: só traz notas reais das fontes oficiais, com o A1 de cada cliente. O laboratório existe apenas dentro dos testes automatizados (`backend/tests/laboratorio`) e não é instalado.

## Estrutura
```
backend/moxml/      núcleo Python (FastAPI, SQLAlchemy, conectores, motor)
  conectores/       sefaz_consulta · svrs_portal · sefaz_sae · pastas · apisimples
  fiscal/           chave de acesso, leitura/validação de XML
  motor/            orquestrador, repositório, auditoria, agendador, armazenamento
  integracoes/      gdrive · dominio
  migrations/       Alembic
  sefaz/            catálogo de serviços oficiais + schemas (PL_010g, SAE)
backend/tests/      67 testes (laboratório interno, sem rede)
frontend/           painel React + TypeScript (build em backend/moxml/web)
windows/            instalar/iniciar/parar/atualizar/testar/backup/diagnostico/capturar
agente/             agente coletor autônomo (lado do cliente) — só biblioteca padrão
docs/               manuais e relatório de testes reais
```

## Operação autônoma (sem CAPTCHA)
O sistema é feito para rodar sozinho. As fontes **100% automáticas** (sem CAPTCHA, sem humano) são:
- **Consulta oficial (webservice SVRS, mTLS)** — descobre todas as notas, situação, cancelamentos e numeração faltante.
- **Coleta na origem** — o XML já é do emitente. Pastas acessíveis pela rede entram em *Configurações → Pastas monitoradas*; nas demais, o **agente coletor** (`agente/`) é instalado no PC do cliente e envia os XMLs novos ao escritório por HTTPS, continuamente.

O download pelo Portal DF-e SVRS é opcional e **não é necessário** para a operação autônoma: se o portal exigir CAPTCHA, o sistema não o contorna — segue pelas fontes acima. Referência de modelos a partir dos XSDs oficiais: [akretion/nfelib](https://github.com/akretion/nfelib) (a validação já usa os XSDs oficiais PL_010g + assinatura criptográfica).

## Documentos
| Documento | Conteúdo |
|---|---|
| [FONTES_FISCAIS.md](FONTES_FISCAIS.md) | matriz de fontes oficiais e matriz de cobertura UF × modelo |
| [REA_FORNECEDORES.md](REA_FORNECEDORES.md) | relatório de engenharia reversa autorizada (fornecedores + NFePHP) |
| [ARQUITETURA.md](ARQUITETURA.md) | arquitetura e decisões |
| [SEGURANCA.md](SEGURANCA.md) | certificados, DPAPI, TLS, conduta com as fontes |
| [TESTES.md](TESTES.md) | testes automatizados e teste de aceitação real |
| [LIMITACOES.md](LIMITACOES.md) | pendências e riscos |
| [PLANO_IMPLANTACAO.md](PLANO_IMPLANTACAO.md) | implantação, backup e restauração |
| [docs/MANUAL_INSTALACAO.md](docs/MANUAL_INSTALACAO.md) | instalação |
| [docs/MANUAL_OPERACAO.md](docs/MANUAL_OPERACAO.md) | operação diária e mensal |
| [docs/RELATORIO_TESTES_REAIS.md](docs/RELATORIO_TESTES_REAIS.md) | evidências reais (pendente) |

## Desenvolvimento
```bash
cd backend && python3.14 -m venv .venv && .venv/bin/pip install -r requirements.txt -e .
MOXML_HOME=./dados .venv/bin/python -m moxml servidor
cd frontend && npm install && npm run dev      # painel com proxy para a API
```
