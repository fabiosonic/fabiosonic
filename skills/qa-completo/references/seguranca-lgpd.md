# Checklist de segurança e LGPD

Passe por todos os itens. Para cada falha: arquivo:linha, risco concreto, correção.

## Segredos e credenciais
- Senhas, tokens de API, senha do certificado A1 (.pfx), credenciais de e-CAC/prefeitura/SEFAZ escritas no código ou commitadas no git (procure também no histórico: `git log -p | grep -iE "senha|password|token|secret|pfx"`).
- `.env` e arquivos `.pfx`/`.p12` fora do `.gitignore`.
- Segredos impressos em log ou mensagem de erro.

## Entrada de dados
- SQL montado por concatenação de string → usar parâmetros.
- Comando de sistema montado com entrada do usuário (`os.system`, `subprocess(shell=True)`, `exec`).
- Caminho de arquivo vindo do usuário sem validação (path traversal: `../../`).
- XML de NF-e/NFS-e lido com parser que aceita entidades externas (XXE) — desative entidades externas.
- Upload sem limite de tamanho ou tipo.
- HTML montado com dado do usuário sem escape (XSS).

## Acesso
- Rotas/telas sem login, ou um cliente vendo dados de outro cliente (troque o ID na URL e veja se abre).
- Senhas guardadas em texto puro → hash forte (bcrypt/argon2).
- Sessão sem expiração; cookie sem `HttpOnly`/`Secure`.

## Dados pessoais (LGPD — Lei 13.709/2018)
- CPF, salário, dados bancários, dados de saúde (atestados na folha) em log, em planilha temporária esquecida, ou em pasta pública.
- Coleta de dado que o sistema não precisa (princípio da necessidade, art. 6º, III).
- Ausência de forma de excluir/exportar dados do titular quando aplicável.
- Dados enviados para serviço externo (API de terceiros, IA) sem necessidade ou sem avisar.
- Backup sem criptografia.

## Dependências
- Rode o auditor da stack (`npm audit`, `pip-audit`, `dotnet list package --vulnerable`) e reporte vulnerabilidades altas/críticas.

## Sigilo profissional
- Contador tem dever de sigilo (NBC PG 01 — Código de Ética Profissional do Contador). Dados de um cliente do escritório nunca devem aparecer para outro cliente nem em relatórios compartilhados.
