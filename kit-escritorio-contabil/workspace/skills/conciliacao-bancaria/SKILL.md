---
name: conciliacao-bancaria
description: Concilia extrato bancário (OFX, CSV, XLSX, PDF convertido) com o razão contábil, aponta divergências e propõe lançamentos de ajuste. Use no fechamento mensal.
---

# Conciliação bancária

1. Leia o extrato (prefira OFX; use `ofxparse` ou `pandas`) e o razão da conta banco exportado do sistema contábil.
2. Normalize: data, valor com sinal, histórico, documento.
3. Faça o casamento nesta ordem: (a) valor e data iguais; (b) valor igual com data até ±3 dias; (c) soma de vários lançamentos igual a um movimento (agrupamentos).
4. Gere uma planilha `trabalho/conciliacao_<banco>_<AAAA-MM>.xlsx` com as abas: Conciliados, Só no extrato, Só no razão, Resumo (saldo extrato × saldo contábil × diferença explicada).
5. Para os itens "só no extrato", sugira conta e histórico: tarifas → despesas bancárias; rendimentos → receita financeira com IRRF a compensar; IOF; PIX de clientes → baixa de duplicatas.
6. Não lance nada sem aprovação. Entregue a lista de ajustes em formato de importação do sistema do escritório, se ele for informado.

**LGPD:** extrato é dado sensível. Recomende o modo sigiloso (`-Sigiloso`) ou processar localmente via script.
