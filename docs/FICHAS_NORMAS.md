# Fichas de conferência das normas — propostas para o conferente

Situação em 07/10/2026: os sites oficiais (*.gov.br) estão bloqueados nesta sessão na nuvem. Os valores
abaixo foram levantados em **fontes secundárias** (busca na web) e entraram no YAML só como **proposta**:
a norma continua **PENDENTE** e o sistema **não usa** nenhum desses números até uma pessoa conferir no
texto oficial (regras 1 e 3 do `CLAUDE.md`).

Para conferir (no PC do escritório, com acesso ao site oficial):
1. `python -m mo_autonomo normas conferir --id <ID>` → gera `dados\conferencia\<ID>.md` com o texto
   oficial e o `hash_texto`.
2. Compare cada valor da tabela abaixo com o trecho oficial.
3. Se bater, no `config\normas\dp.yaml`: `status: CONFERIDO`, `fonte_url: <url oficial>`,
   `conferido_por: <seu nome>`, `conferido_em: <data>`, `hash_texto: <o da ficha>`.
4. `python -m mo_autonomo normas validar` e `normas cobertura` — as regras de DP passam a `ATIVA`.

## TABELA_INSS_SEGURADO — Portaria Interministerial MPS/MF nº 13, de 09/01/2026 (DOU)

| Faixa de salário de contribuição | Alíquota (progressiva) |
|---|---|
| até R$ 1.621,00 | 7,5% |
| R$ 1.621,01 a R$ 2.902,84 | 9% |
| R$ 2.902,85 a R$ 4.354,27 | 12% |
| R$ 4.354,28 a R$ 8.475,55 (teto) | 14% |

Conferência cruzada: desconto máximo calculado pelo sistema com esses valores = **R$ 988,09**
(é o valor divulgado). Vigência proposta: 01/01/2026 a 31/12/2026.
Fontes secundárias: debit.com.br, pontotel.com.br, caltrab.com.

## TABELA_IRRF_MENSAL — tabela progressiva mensal + redução da Lei 15.270/2025

| Base de cálculo mensal | Alíquota | Parcela a deduzir |
|---|---|---|
| até R$ 2.428,80 | — | — |
| R$ 2.428,81 a R$ 2.826,65 | 7,5% | R$ 182,16 |
| R$ 2.826,66 a R$ 3.751,05 | 15% | R$ 394,16 |
| R$ 3.751,06 a R$ 4.664,68 | 22,5% | R$ 675,49 |
| acima de R$ 4.664,68 | 27,5% | R$ 908,73 |

- Dedução por dependente: **R$ 189,59**.
- Redução (Lei 15.270/2025, a partir de 01/2026): rendimentos tributáveis até **R$ 5.000,00** → imposto
  zerado (redução de até R$ 312,89); de R$ 5.000,01 a **R$ 7.350,00** → redução = **R$ 978,62 −
  0,133145 × rendimentos tributáveis**; acima disso, sem redução.
- **Ponto a confirmar no texto da lei:** o redutor é medido sobre os *rendimentos tributáveis* (antes das
  deduções) — no YAML está `redutor.base: rendimento`. Se a lei disser outra coisa, troque para
  `base_calculo`.
- Exemplos com os valores propostos: base 4.800 → R$ 0,00; 6.000 → R$ 561,52; 8.000 → R$ 1.291,27.
- Limitação conhecida: o cálculo **não** trata o desconto simplificado mensal.

Fontes secundárias: valorfinal.com.br, portaltributario.com.br, caltrab.com.

## LEI_8036_FGTS — Lei 8.036/1990, art. 15

- `aliquota_deposito: 0.08` — "8% (oito por cento) da remuneração paga ou devida, no mês anterior".
- Atenção: § 7º reduz para **2% no contrato de aprendizagem**. O cálculo atual não diferencia aprendiz:
  folha de aprendiz vai aparecer como divergente até essa regra ser tratada.

Fonte secundária: juruadocs.com (transcrição do art. 15), guiatrabalhista.com.br.

## Normas fiscais (MOC NF-e, MOC CT-e, CFOP, NFS-e, dicionário CNPJ…)

Sem proposta: a busca não trouxe o texto dos manuais com confiança suficiente. Ficam vazias até o
acesso aos sites oficiais (Portal NF-e, CONFAZ, Receita) ou ao PC do escritório.
