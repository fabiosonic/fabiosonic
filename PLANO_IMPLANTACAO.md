# Plano de implantação

## Fase 0: preparação (1 dia)
- Servidor ou estação Windows sempre ligado, com usuário dedicado (ex.: `MO\captador`) e senha que não expira.
- Python 3.14 (python.org, com "py launcher"). Opcional: PostgreSQL 16+ local.
- Termo de autorização de uso do certificado A1 assinado por cada cliente (modelo no MANUAL_OPERACAO.md).

## Fase 1: instalação (meio dia)
1. Copiar ou clonar o projeto para `C:\MO-XML-Captador`.
2. Executar `windows\instalar.bat` com o usuário dedicado.
3. `windows\testar.bat`: os 67 testes automatizados devem passar (laboratório interno, sem tocar na SEFAZ).

## Fase 2: piloto com 1 CNPJ autorizado (1 a 2 dias)
1. Cadastrar a empresa piloto, o certificado A1 (com o termo) e **um XML semente por modelo/série**.
2. `windows\diagnostico.bat <id>`: verifica TLS, banco e a estrutura do Portal SVRS (registra se há CAPTCHA).
3. `moxml teste-real` para **NF-e 55** e, separadamente, para **NFC-e 65**.
4. Analisar as evidências em `evidencias\`. Decisão por modelo:
   - todos os critérios OK → operacional;
   - critério 4 = IMPOSSÍVEL → descoberta indisponível; operar só com pasta do emissor e chaves;
   - critério 5 com CAPTCHA → XML integral só pela pasta do emissor ou pelo conector comercial.
5. Atualizar FONTES_FISCAIS.md e o RELATORIO_TESTES_REAIS.md com o resultado.

## Fase 3: ondas de entrada (2 a 4 semanas)
- Onda 1: 10 empresas de NF-e. Onda 2: 10 empresas de NFC-e de alto volume (calibrar limites). Ondas seguintes: 30 empresas por semana até as cerca de 110.
- Para cada empresa: certificado + termo, XML semente por série (inclusive séries de contingência e de cada PDV) e, se houver, pasta do emissor.
- Acompanhar diariamente: Visão geral → pendentes, lacunas, erros por fonte.

## Fase 4: integrações
- Google Drive: conta de serviço com acesso à pasta raiz, `MOXML_GDRIVE_ATIVO=true` e validação na página Integrações.
- Domínio: gerar o pacote do mês anterior, importar no Escrita Fiscal e conferir com `conferencia_valores.csv`. Ajustar o layout se a rotina do Domínio exigir.

## Banco de dados e backup
- **PostgreSQL (produção):** `MOXML_DATABASE_URL=postgresql+psycopg://moxml:<senha>@localhost:5432/moxml`. Migrations rodam em `moxml init` e `atualizar.bat`. Backup diário com `pg_dump -Fc moxml > moxml_AAAAMMDD.dump`, agendado no Windows.
- **XMLs + cofre (+ SQLite):** `windows\backup.bat [destino]` diário (mantém os 30 mais recentes). Recomenda-se destino em outro disco/NAS. O Google Drive é a cópia externa dos XMLs.
- **Restauração:** parar o serviço, restaurar o banco (`pg_restore` ou `banco/moxml.db`), restaurar `xml\` e `cofre\` na **mesma máquina e no mesmo usuário** (DPAPI) e iniciar.
- `atualizar.bat` sempre faz backup antes de atualizar.

## Critério de saída
Para cada modelo (55 e 65), os 10 critérios da seção 17 em OK com evidência arquivada. Até lá, o modelo segue **não operacional** pela fonte SEFAZ.
