# Manual de instalação (Windows)

## 1. Pré-requisitos
- Windows 10/11 ou Windows Server 2019+, ligado continuamente (ou nos horários de captura).
- **Python 3.14** de https://www.python.org/downloads/windows/. Marque "Add python.exe to PATH" e mantenha o "py launcher".
- Usuário Windows dedicado ao serviço, com senha. É ele que guarda os certificados (DPAPI).
- Internet comum (os portais da SEFAZ-RJ bloqueiam alguns IPs de datacenter).
- Opcional: PostgreSQL 16+ (recomendado para a carteira inteira).

## 2. Instalação
1. Copie a pasta do projeto para `C:\MO-XML-Captador`.
2. Entre com o **usuário do serviço** e execute `C:\MO-XML-Captador\windows\instalar.bat`. O script:
   - localiza o Python (3.14; aceita 3.13/3.12 se necessário);
   - cria `backend\.venv` e instala as dependências fixadas;
   - cria `%PROGRAMDATA%\MO-XML-Captador` (dados, XMLs, cofre, logs, backups) com permissão restrita;
   - copia `moxml.env.modelo` para `%PROGRAMDATA%\MO-XML-Captador\moxml.env`;
   - aplica as migrations do banco;
   - registra a tarefa agendada **"MO XML Captador"** (início com o Windows, reinício automático em falha). A senha do Windows é pedida para que a tarefa rode mesmo sem ninguém logado.
3. Abra http://127.0.0.1:8765. A faixa verde confirma a operação em **produção, somente com notas reais**.

## 3. PostgreSQL (recomendado)
```sql
CREATE USER moxml WITH PASSWORD '<senha forte>';
CREATE DATABASE moxml OWNER moxml;
```
No `moxml.env`: `MOXML_DATABASE_URL=postgresql+psycopg://moxml:<senha>@localhost:5432/moxml`. Em seguida, execute `windows\atualizar.bat` para aplicar as migrations.

## 4. Google Drive
- **Opção A (recomendada): conta de serviço.**
  1. No Google Cloud, crie um projeto, ative a Drive API e crie uma conta de serviço.
  2. Baixe o JSON para `%PROGRAMDATA%\MO-XML-Captador\gdrive-sa.json`.
  3. Compartilhe a pasta "MORAES & OLIVEIRA CONTABILIDADE" (ou o Drive compartilhado) com o e-mail da conta de serviço, como Editor.
- **Opção B: OAuth de um usuário.**
  ```
  backend\.venv\Scripts\python -m moxml drive-autorizar --client-secret client_secret.json --saida %PROGRAMDATA%\MO-XML-Captador\gdrive-token.json
  ```
- Configure no `moxml.env`:
  ```
  MOXML_GDRIVE_ATIVO=true
  MOXML_GDRIVE_CREDENCIAIS=C:\ProgramData\MO-XML-Captador\gdrive-sa.json
  MOXML_GDRIVE_PASTA_RAIZ_ID=<id da pasta, visto na URL do Drive>
  ```
  O sistema reaproveita as pastas existentes (`1-CLIENTES`, `CLIENTES ATIVOS`, `<EMPRESA>`…), ignorando acentos e maiúsculas, e cria só o que falta.

## 5. Cadeia de certificados (se o diagnóstico acusar falha de TLS)
Baixe as cadeias ICP-Brasil do repositório do ITI e a cadeia pública usada pelo SVRS. Concatene em um PEM e defina `MOXML_CA_BUNDLE`. Nunca desabilite a verificação TLS.

## 6. Scripts
| Script | Função |
|---|---|
| `instalar.bat` | instalação completa e serviço |
| `iniciar.bat` / `parar.bat` | inicia ou para o serviço (e abre o painel) |
| `atualizar.bat` | backup, atualização do código e das dependências, migrations, reinício |
| `testar.bat` | testes automatizados (laboratório) |
| `backup.bat [destino]` | backup de banco SQLite, XMLs e cofre |
| `diagnostico.bat [id_empresa]` | serviço, banco, TLS, matriz RJ; com id, inspeciona o portal SVRS usando o A1 |
| `capturar.bat [--empresa N] [--modelo 55]` | captura imediata pela linha de comando |

## 7. Desinstalar
`powershell -ExecutionPolicy Bypass -File windows\servico.ps1 -Acao remover` remove a tarefa e preserva os dados.
