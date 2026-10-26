---
name: b3-noticias
description: >-
  Monitor de notícias para ações da B3: busca na CVM os fatos relevantes,
  comunicados ao mercado e avisos aos acionistas das empresas da carteira ou
  da watchlist (com link do PDF no RAD), mostra a variação do último pregão e,
  opcionalmente, manchetes do Google Notícias em português. Mostra só o que é
  novo desde a última consulta. Use quando o usuário disser "tem notícia de
  PETR4?", "saiu fato relevante?", "o que mexeu com VALE3", "monitora minhas
  ações" ou depois do /b3-scanner.
argument-hint: "[--symbols PETR4,VALE3] [--dias 3] [--manchetes]"
---

# b3-noticias

```bash
python3 "${CLAUDE_SKILL_DIR}/news.py"                         # carteira + watchlist, 3 dias
python3 "${CLAUDE_SKILL_DIR}/news.py" --symbols PETR4,VALE3 --dias 10
python3 "${CLAUDE_SKILL_DIR}/news.py" --manchetes --todos
python3 "${CLAUDE_SKILL_DIR}/news.py" --json
```

Fontes: Portal de Dados Abertos da CVM (documentos IPE, atualizado uma vez
por dia; para o que saiu hoje, oriente o usuário a consultar o RAD da CVM),
ticker ligado ao CNPJ pelo Formulário Cadastral (FCA), Yahoo para a variação
e Google Notícias (RSS de uso pessoal) com `--manchetes`. BDRs, ETFs e FIIs
não aparecem no cadastro de companhias abertas.

Fatos relevantes aparecem com `!!`. Resuma o assunto de cada documento,
inclua o link e lembre que notícia não é sinal de compra ou venda.
