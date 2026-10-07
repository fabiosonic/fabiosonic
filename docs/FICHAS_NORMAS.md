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

## MOC_NFE — Manual de Orientação do Contribuinte NF-e/NFC-e (proposta parcial)

| Parâmetro | Valor proposto | O que é | Fonte secundária |
|---|---|---|---|
| `crt_por_regime` | 1→Simples, 2→Simples (excesso de sublimite), 3→Presumido/Real/Imune/Isenta, 4→MEI | campo CRT (NT 2024.001) | tecnospeed, contmatic, inventti |
| `tp_nf_saida` | 1 | tpNF: 0 entrada, 1 saída | nfe.io, tecnospeed |
| `fin_nfe_devolucao` | 4 | finNFe = devolução | tecnospeed, oobj |
| `tp_evento_cancelamento` | 110111 | evento de cancelamento | projetoacbr, nfe.io |
| `cstat_evento_homologado` | 135 | "Evento registrado e vinculado a NF-e" | projetoacbr |
| `cstat_autorizado` | 100 | "Autorizado o uso da NF-e" | projetoacbr |
| `chave_pos_cnpj_emitente` | posições 7–20 da chave | CNPJ do emitente | senior, dootax |
| `chave_pos_modelo` | posições 21–22 da chave | modelo (55/65) | senior, dootax |

A conferir com atenção: se há outros cStat que também valem como autorizado (ex.: 150, fora de prazo)
ou como evento homologado (ex.: 155). O mapeamento CRT 3 → Imune/Isenta é proposta do sistema.
**Sem proposta:** `modelo_nfce` e `ind_tot_compoe` — a busca não trouxe o texto com confiança.

## MOC_CTE — tomador do serviço

`tomador_por_codigo`: toma3 0 = Remetente, 1 = Expedidor, 2 = Recebedor, 3 = Destinatário
(toma4 = 4 Outros, com os dados no próprio grupo). Fontes secundárias: oobj, webmania.

## TABELA_CFOP — primeiro dígito

- Por tipo da nota: entrada (tpNF 0) → 1, 2, 3; saída (tpNF 1) → 5, 6, 7.
- Por destino (idDest): 1 interna → 1/5; 2 interestadual → 2/6; 3 exterior → 3/7 (rejeições 732/733).

Fontes secundárias: aegro, oobj, alterdata.

## Ainda sem proposta

LEIAUTE_NFSE_NACIONAL/ABRASF (códigos de retenção), LEI_10833_ART30 (serviços sujeitos), TABELA_NCM_
MONOFASICO, DICIONARIO_DADOS_ABERTOS_CNPJ (códigos de situação/opção), LC 123, Res. CGSN 140, RICMS-RJ,
ISS-RJ, EFD-Reinf, reforma tributária e normas contábeis: a busca não trouxe os valores com confiança
suficiente — ficam para a conferência no site oficial.
