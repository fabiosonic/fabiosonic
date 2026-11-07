---
kind: task
slug: conciliacao-bancaria-mensal
name: Conciliação bancária mensal
assignee: analista-contabil
project: operacao-mensal
recurring: true
---

Para cada cliente com extratos recebidos: aplique a skill conciliacao-bancaria, gere o relatório de
conciliação e o lote de lançamentos (skill importacao-dominio). Itens sem documento vão para transitória,
e é aberta uma pendência para o atendimento cobrar o cliente.
