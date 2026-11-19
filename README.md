# M&O XML Captador

Captura de XML de **saída** de **NF-e (modelo 55)** e **NFC-e (modelo 65)** de empresas do **Rio de Janeiro**, para a **MORAES E OLIVEIRA CONTABILIDADE LTDA**.

**Independente** do Fisco Fácil, do Hubstrom e do autXML. Prioriza fontes oficiais e usa o certificado A1 do próprio emitente, com autorização registrada.

> **Situação (19/11/2026):** software completo e testado em laboratório (65 testes em Python 3.14.6). **Nenhuma recuperação real de XML foi feita ainda**: falta o teste com um certificado A1 autorizado. Até esse teste (`moxml teste-real`, um por modelo), nenhuma UF/modelo é considerada operacional. Ver [LIMITACOES.md](LIMITACOES.md).

## Como funciona no RJ
1. **XML semente** por série: fornece CNPJ, modelo, série e numeração.
2. **Descoberta oficial** (NFeConsultaProtocolo/SVRS): uma consulta por número. O MOC (regra J04, cStat 562) prevê que a SEFAZ devolva ao emitente a chave existente. Sem força bruta. *Provável; confirmar no teste real.*
3. **Situação e eventos**: protocolo, cancelamentos e CC-e pela mesma consulta.
4. **XML integral**: Portal DF-e SVRS (`DownloadXMLDFe`) com o A1 do emitente. *Não comprovado; interrompe se houver CAPTCHA.* Fontes complementares: pasta do emissor do cliente e conector comercial opcional (desligado).
5. **Validação** (assinatura criptográfica, chave/DV, protocolo, XSD PL_010g), **deduplicação**, gravação sem sobrescrever, **auditoria de numeração**, **Google Drive** com confirmação por MD5 e **pacote para o Domínio**.

## Início rápido (Windows)
```bat
windows\instalar.bat          :: instala, migra o banco e registra o serviço
start http://127.0.0.1:8765   :: painel (começa em modo SIMULADO)
windows\testar.bat            :: testes automatizados
```
Demonstração com dados fictícios: `backend\.venv\Scripts\python -m moxml demo`.

## Estrutura
```
backend/moxml/      núcleo Python (FastAPI, SQLAlchemy, conectores, motor, simulador)
  conectores/       sefaz_consulta · svrs_portal · sefaz_sae · pastas · apisimples
  fiscal/           chave de acesso, leitura/validação de XML
  motor/            orquestrador, repositório, auditoria, agendador, armazenamento
  integracoes/      gdrive · dominio
  migrations/       Alembic
  sefaz/            catálogo de serviços oficiais + schemas (PL_010g, SAE)
backend/tests/      65 testes (laboratório, sem rede)
frontend/           painel React + TypeScript (build em backend/moxml/web)
windows/            instalar/iniciar/parar/atualizar/testar/backup/diagnostico/capturar
docs/               manuais e relatório de testes reais
```

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
MOXML_HOME=./dados MOXML_MODO=SIMULADO .venv/bin/python -m moxml servidor
cd frontend && npm install && npm run dev      # painel com proxy para a API
```
