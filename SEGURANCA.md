# Segurança

## Certificados A1 e senhas

| Controle | Implementação |
|---|---|
| Autorização do titular | O cadastro exige "autorizado por" + referência do termo/contrato + confirmação expressa (API, painel e CLI). Tudo fica registrado em `certificados.autorizado_por/termo_autorizacao/autorizado_em`. |
| Validação | Senha (erro específico para senha incorreta), validade, CNPJ do titular (OID ICP-Brasil 2.16.76.1.3.3, com fallback para o CN), correspondência com a empresa. Mesma raiz de CNPJ gera AVISO; CNPJ diferente bloqueia. Aceita CNPJ alfanumérico (IN RFB 2.229/2024). |
| Armazenamento | `moxml/seguranca/cofre.py`. **Windows: DPAPI** (`CryptProtectData`) no escopo do usuário, com entropia adicional gerada na instalação. O banco guarda só a referência ao segredo. Fora do Windows (desenvolvimento/testes): AES-256-GCM com chave local 0600. |
| Uso em memória | A chave privada é gravada em PEM temporário 0600 apenas durante `load_cert_chain` e removida em seguida (exigência do `ssl` do Python). |
| Senhas em logs | Não são registradas; o log central mascara padrões de senha/token/Bearer (`motor/logs.py`). |
| Versionamento | `.gitignore` bloqueia `*.pfx`, `*.p12`, `*.env`, tokens e credenciais do Drive. `moxml.env` fica em `%PROGRAMDATA%\MO-XML-Captador`, fora do repositório. |
| Controle de acesso ao arquivo | O instalador restringe `%PROGRAMDATA%\MO-XML-Captador` ao usuário do serviço, Administradores e SYSTEM (`icacls`). |
| Vencimento | Status VALIDO/VENCENDO (≤ 30 dias)/VENCIDO recalculado diariamente às 06:50, com alerta no painel. Certificado vencido bloqueia a captura daquela empresa. |
| Substituição | Novo certificado desativa o anterior (status SUBSTITUIDO), sem apagar o histórico. |

**Importante (DPAPI):** o cofre só abre para o **mesmo usuário Windows na mesma máquina**. A tarefa agendada roda com esse usuário. Para trocar de servidor, recadastre os certificados. O backup do cofre só é útil na mesma máquina e no mesmo usuário.

## TLS

- `ClienteSoap` **recusa** contexto com `CERT_NONE` ou sem verificação de hostname (há teste específico).
- TLS 1.2 ou superior.
- Os servidores SEFAZ/SVRS podem usar cadeias ICP-Brasil que não estão no repositório do Windows. Nesse caso, baixe as ACs no repositório oficial do ITI, gere um PEM e aponte `MOXML_CA_BUNDLE`. **Nunca desabilite a verificação.**
- `diagnostico.bat` testa o TLS com cada host (sem certificado de cliente) e mostra o emissor do certificado do servidor.

## Painel / API

- Escuta em `127.0.0.1` por padrão: só a própria máquina acessa.
- Para acesso em rede, defina `MOXML_API_TOKEN` (comparação em tempo constante). Use rede interna ou VPN e, se possível, um proxy HTTPS na frente.
- O download de XML confere se o caminho está dentro da pasta de XMLs (evita *path traversal*).

## XML de terceiros (pastas, portais, fornecedores)

- Parser `lxml` com `resolve_entities=False` e `no_network=True` (bloqueia XXE; há teste com entidade externa).
- Limite de 50 MB por arquivo e proteção contra zip-bomb (tamanho declarado por entrada).
- Verificação criptográfica da assinatura (DigestValue e SignatureValue). XML adulterado é rejeitado (há teste).

## Conduta com as fontes (conformidade)

- Só serviços publicados oficialmente (catálogo com evidência) e só o certificado do próprio emitente, com autorização registrada.
- Limitador local por host (SVRS: 30/min nos webservices, 12/min no portal). cStat 656 bloqueia aquele CNPJ por 1 h. HTTP 429 bloqueia o host por 60 s.
- Sem força bruta de cNF, sem tentativa de autorizar NF-e para descobrir chave (539) e sem contornar CAPTCHA ou login.
- Sigilo fiscal / LGPD: XMLs contêm dados de clientes dos clientes. Mantenha a pasta de dados e o Drive com acesso restrito. O conector comercial (API Simples) envia PFX e senha a terceiros e só deve ser ligado após análise contratual e de LGPD.
