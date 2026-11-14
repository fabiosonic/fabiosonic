# Prospecção ativa para escritório de contabilidade

Ciclo completo, da leitura do site do escritório até a fila diária de WhatsApp:

| Etapa | Comando | O que faz |
|---|---|---|
| 1 | `nichos` | Lê o site do escritório e define os nichos que ele atende, com termos de busca |
| 2 | `buscar` / `importar` | Acha empresas dos nichos na região (Google Places API oficial) ou importa um CSV |
| 3–4 | `qualificar` | Lê o site de cada empresa, comprova sinais de honorário, coleta o WhatsApp **publicado por ela** e identifica o decisor (sócio, diretor, financeiro) |
| 5 | `material` | Prepara as dores do decisor e o texto único da empresa, com a norma conferida |
| 6 | `fila` | Gera a página do dia com um botão por empresa — **uma pessoa confere e envia** |
| 7 | `enviado`, `resultado`, `relatorio` | Registra envio e resposta; compara taxa por gancho e por setor |

## Instalação

```bash
pip install -r requirements.txt
cp config.exemplo.json config.json      # preencha site, cidade, CRC e região
export ANTHROPIC_API_KEY=...            # etapas 1, 3–4 e 5
export GOOGLE_MAPS_API_KEY=...          # etapa 2 (Places API); dispensável se usar 'importar'
```

## Uso diário

```bash
python -m prospeccao nichos
python -m prospeccao buscar --setor laboratório --max 40
python -m prospeccao qualificar --limite 25
python -m prospeccao material --limite 25
python -m prospeccao fila               # abre dados/fila-AAAA-MM-DD.html no navegador
python -m prospeccao enviado P0001      # depois de enviar cada mensagem
python -m prospeccao resultado P0001 positiva --notas "pediu proposta"
python -m prospeccao relatorio
```

Sem a chave do Google, gere o CSV com o [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)
e rode `python -m prospeccao importar resultado.csv --setor Saúde --municipio "Itaboraí"`.

A base fica em `dados/base.csv` (abre no Excel). Texto com alerta não entra na fila: corrija
`o_que_vimos` / `a_conta` na planilha e rode `python -m prospeccao revisar`.

## Por que o envio é manual

O WhatsApp proíbe disparo automatizado para quem não pediu contato, e a punição é o banimento do
número. Ferramenta que imita digitação para esconder a automação não muda a regra — só adia o
bloqueio. Aqui a mensagem não parece automação porque não é: o sistema pesquisa e escreve, e
alguém do escritório abre o contato, confere e envia. As travas ficam no código:

- só número de **celular publicado pela própria empresa** (site ou Perfil do Google), com a URL de origem gravada;
- **segunda a sexta, 9h–18h** de Brasília, fora de feriado nacional (`feriados_extras` para os locais);
- **teto diário** (`whatsapp.teto_dia`: 8 para número novo; 15 com respostas chegando; 20–30 aquecido);
- uma mensagem por empresa, sem sequência, sem áudio, sem anexo, sem link;
- **opt-out** em toda mensagem; `resultado <id> optout` tira a empresa da base para sempre.

Para volume maior, o caminho é a Cloud API oficial do WhatsApp Business, com template aprovado.

## O que o texto nunca contém

O checklist (`prospeccao/etapas.py`, `PROIBIDOS`) barra antes da fila:

- trabalho gratuito, diagnóstico, "sem compromisso";
- recuperação, restituição ou ressarcimento de valores;
- preço, honorário ou promessa de economia;
- menção ao contador atual (NBC PG 01, itens 11 a 15);
- norma que não esteja em `prospeccao/conhecimento/dores-por-setor.md` — a base de normas já
  conferidas na fonte. Para usar uma norma nova, confira no Planalto/órgão emissor e acrescente lá;
- norma revogada (CPC 17 — o vigente para contrato de obra é o CPC 47 / NBC TG 47).

A assinatura com CRC e a frase de saída são acrescentadas pelo sistema, não pela IA.

## LGPD

Base legal: legítimo interesse (Lei 13.709/2018, art. 7º, IX), para contato B2B com dado que a
empresa publicou como canal comercial. A planilha guarda, por lead, o contato usado, a URL de
origem, a data, o texto enviado e a resposta. Não entram: telefone ou e-mail do cadastro da
Receita, dado pessoal fora do contexto empresarial, base comprada.

## Testes

```bash
python -m unittest discover -s tests
```
