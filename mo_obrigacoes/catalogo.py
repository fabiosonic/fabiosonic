"""Catálogo padrão de obrigações e documentos monitorados.

Cada item define:
  * aplicabilidade   -> para quais empresas a obrigação é gerada na agenda
  * regra_vencimento -> como calcular o prazo (ver calendario.py)
  * reconhecimento   -> como identificar o comprovante no Google Drive
                        (nome do arquivo, texto do PDF/XML, extensão, pasta)

Prazos conforme a legislação federal vigente em 2026. Obrigações estaduais e
municipais (ICMS, EFD ICMS/IPI, ISS) têm prazo variável por UF/município: o
padrão abaixo pode ser ajustado por empresa no campo ``personalizacoes``
(ex.: {"ICMS": {"dia": 9}}).

Observação: a DIRF foi extinta a partir do ano-calendário 2025 (informações
migradas para eSocial e EFD-Reinf) e por isso não consta do catálogo. A DCTF
mensal foi substituída pela DCTFWeb (MIT) a partir da competência 01/2025.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import TIPO_ENTREGA, TIPO_RECEBIMENTO, Obrigacao

TODOS_EXCETO_MEI = ["SIMPLES", "PRESUMIDO", "REAL", "IMUNE_ISENTA"]
LUCRO = ["PRESUMIDO", "REAL"]
LUCRO_E_TERCEIRO_SETOR = ["PRESUMIDO", "REAL", "IMUNE_ISENTA"]

DARF = r"Documento de Arrecada[cç][aã]o de Receitas Federais|\bDARF\b"
RECIBO = r"Recibo de Entrega|Recibo de Transmiss[aã]o|N[uú]mero do Recibo|Recibo n"

CATALOGO: list[dict] = [
    # ------------------------------------------------------------------ FISCAL
    {
        "codigo": "PGDAS_D",
        "nome": "PGDAS-D (apuração do Simples Nacional)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "LC 123/2006, art. 18, §15-A; Res. CGSN 140/2018, art. 38",
        "multa_referencia": "2% ao mês sobre os tributos declarados, mín. R$ 50,00 (LC 123, art. 38-A)",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": ["SIMPLES"]},
        "reconhecimento": {
            "nome": [r"pgdas", r"extrato.{0,15}simples", r"declara[cç][aã]o.{0,5}simples", r"recibo.{0,15}simples"],
            "conteudo": [r"Programa Gerador do Documento de Arrecada[cç][aã]o do Simples Nacional",
                         r"PGDAS-?D", r"Recibo de Entrega da Apura[cç][aã]o", r"Extrato do Simples Nacional"],
            "exclui": [r"\bMEI\b", r"DEFIS"],
            "pastas": ["fiscal"],
        },
    },
    {
        "codigo": "DAS",
        "nome": "Guia DAS - Simples Nacional",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Res. CGSN 140/2018, art. 40",
        "multa_referencia": "Multa de mora 0,33%/dia (até 20%) + Selic",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": ["SIMPLES"]},
        "reconhecimento": {
            "nome": [r"(^|[^a-z])das([^a-z]|$)", r"guia.{0,5}simples"],
            "conteudo": [r"(?<!Gerador do )Documento de Arrecada[cç][aã]o\s+do Simples Nacional"],
            "exclui": [r"Programa Gerador", r"Recibo de Entrega", r"\bMEI\b", r"dasn", r"das.?mei", r"Extrato do Simples"],
            "pastas": ["fiscal", "guias"],
        },
    },
    {
        "codigo": "DAS_MEI",
        "nome": "Guia DAS-MEI",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "LC 123/2006, art. 18-A; Res. CGSN 140/2018, art. 101",
        "multa_referencia": "Multa de mora 0,33%/dia (até 20%) + Selic",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": ["MEI"]},
        "reconhecimento": {
            "nome": [r"das.?mei", r"pgmei"],
            "conteudo": [r"PGMEI", r"Microempreendedor Individual"],
            "conteudo_obrigatorio": [r"Documento de Arrecada[cç][aã]o do Simples Nacional",
                                     r"\bMEI\b|Microempreendedor|PGMEI"],
            "exclui": [r"DASN"],
        },
    },
    {
        "codigo": "DASN_SIMEI",
        "nome": "DASN-SIMEI (declaração anual do MEI)",
        "departamento": "FISCAL",
        "periodicidade": "anual",
        "base_legal": "Res. CGSN 140/2018, art. 109",
        "multa_referencia": "2% ao mês, mín. R$ 50,00",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 31, "mes": 5, "anos_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": ["MEI"]},
        "reconhecimento": {
            "nome": [r"dasn"],
            "conteudo": [r"DASN-?SIMEI", r"Declara[cç][aã]o Anual do Simples Nacional.{0,80}Microempreendedor"],
        },
    },
    {
        "codigo": "DEFIS",
        "nome": "DEFIS (declaração anual do Simples Nacional)",
        "departamento": "FISCAL",
        "periodicidade": "anual",
        "base_legal": "Res. CGSN 140/2018, art. 72",
        "multa_referencia": "2% ao mês sobre tributos, mín. R$ 200,00 (LC 123, art. 38-A)",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 31, "mes": 3, "anos_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": ["SIMPLES"]},
        "reconhecimento": {
            "nome": [r"defis"],
            "conteudo": [r"Declara[cç][aã]o de Informa[cç][oõ]es Socioecon[oô]micas e Fiscais", r"\bDEFIS\b"],
        },
    },
    {
        "codigo": "DESTDA",
        "nome": "DeSTDA (ICMS-ST, DIFAL e antecipação - Simples)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Ajuste SINIEF 12/2015",
        "multa_referencia": "Conforme legislação estadual",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 28, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": ["SIMPLES"], "exige": ["comercio"]},
        "reconhecimento": {
            "nome": [r"destda", r"sedif"],
            "conteudo": [r"DeSTDA", r"Declara[cç][aã]o de Substitui[cç][aã]o Tribut[aá]ria,? Diferencial de Al[ií]quota"],
        },
    },
    {
        "codigo": "DCTFWEB",
        "nome": "DCTFWeb (com MIT)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "IN RFB 2.005/2021, art. 19 (redação da IN RFB 2.237/2024)",
        "multa_referencia": "2% ao mês sobre os tributos, mín. R$ 200,00 (com movimento) / R$ 500,00",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "meses_apos": 1},
        "aplicabilidade": {"qualquer": [
            {"regimes": LUCRO_E_TERCEIRO_SETOR},
            {"regimes": ["SIMPLES"], "exige_algum": ["possui_funcionarios", "possui_prolabore"]},
        ]},
        "reconhecimento": {
            "nome": [r"dctf.?web", r"recibo.{0,10}dctf"],
            "conteudo": [r"DCTFWeb", r"Declara[cç][aã]o de D[eé]bitos e Cr[eé]ditos Tribut[aá]rios Federais Previdenci[aá]rios"],
            "exclui": [DARF],
            "pastas": ["fiscal", "pessoal"],
        },
    },
    {
        "codigo": "DARF_DCTFWEB",
        "nome": "DARF DCTFWeb (INSS / IRRF / tributos do MIT)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Lei 8.212/1991, art. 30, I, 'b'",
        "multa_referencia": "Multa de mora 0,33%/dia (até 20%) + Selic",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"qualquer": [
            {"regimes": LUCRO_E_TERCEIRO_SETOR, "exige_algum": ["possui_funcionarios", "possui_prolabore"]},
            {"regimes": ["SIMPLES"], "exige_algum": ["possui_funcionarios", "possui_prolabore"]},
        ]},
        "reconhecimento": {
            "nome": [r"darf.{0,10}(dctf|inss|previd)", r"guia.{0,5}inss"],
            "conteudo": [r"DCTFWeb", r"Contribui[cç][aã]o Previdenci[aá]ria", r"CP SEGURADOS", r"CP PATRONAL"],
            "conteudo_obrigatorio": [DARF, r"DCTFWeb|Previdenci[aá]ri|CP SEGURADOS|CP PATRONAL|\b(1082|1099|1138|1646)\b"],
            "pastas": ["fiscal", "pessoal", "guias"],
        },
    },
    {
        "codigo": "EFD_REINF",
        "nome": "EFD-Reinf",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "IN RFB 2.043/2021",
        "multa_referencia": "2% ao mês, mín. R$ 200,00 / R$ 500,00",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 15, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"exige": ["retem_tributos"], "regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"reinf"],
            "conteudo": [r"EFD-?Reinf", r"Escritura[cç][aã]o Fiscal Digital de Reten[cç][oõ]es"],
        },
    },
    {
        "codigo": "PIS_COFINS",
        "nome": "DARF PIS/COFINS",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Lei 9.715/1998, art. 2º; Lei 11.933/2009",
        "multa_referencia": "Multa de mora 0,33%/dia (até 20%) + Selic",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 25, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": LUCRO},
        "reconhecimento": {
            "nome": [r"pis", r"cofins"],
            "conteudo_obrigatorio": [DARF, r"\b(8109|2172|6912|5856|8301)\b"],
            "pastas": ["fiscal", "guias"],
        },
    },
    {
        "codigo": "IRPJ_CSLL",
        "nome": "DARF IRPJ/CSLL trimestral",
        "departamento": "FISCAL",
        "periodicidade": "trimestral",
        "base_legal": "Lei 9.430/1996, arts. 1º, 5º e 6º",
        "multa_referencia": "Multa de mora 0,33%/dia (até 20%) + Selic",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "meses_apos": 1},
        "aplicabilidade": {"regimes": LUCRO},
        "reconhecimento": {
            "nome": [r"irpj", r"csll"],
            "conteudo_obrigatorio": [DARF, r"\b(2089|2372|0220|2484|3373|6012)\b"],
            "pastas": ["fiscal", "guias"],
        },
    },
    {
        "codigo": "EFD_CONTRIBUICOES",
        "nome": "EFD-Contribuições",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "IN RFB 1.252/2012, art. 5º",
        "multa_referencia": "R$ 500,00 a R$ 1.500,00 por mês-calendário (Lei 12.766/2012)",
        "regra_vencimento": {"tipo": "dia_util", "n": 10, "meses_apos": 2},
        "aplicabilidade": {"regimes": LUCRO},
        "reconhecimento": {
            "nome": [r"efd.{0,3}contrib", r"sped.{0,3}contrib", r"pis.{0,3}cofins.{0,10}recibo"],
            "conteudo": [r"EFD[- ]?Contribui[cç][oõ]es", r"Escritura[cç][aã]o Fiscal Digital.{0,60}Contribui[cç][oõ]es"],
            "exclui": [DARF],
        },
    },
    {
        "codigo": "EFD_ICMS_IPI",
        "nome": "EFD ICMS/IPI (SPED Fiscal)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Ajuste SINIEF 02/2009 e legislação estadual (prazo varia por UF)",
        "multa_referencia": "Conforme legislação estadual",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": LUCRO, "exige_algum": ["comercio", "industria"]},
        "reconhecimento": {
            "nome": [r"efd.{0,3}icms", r"sped.{0,3}fiscal"],
            "conteudo": [r"EFD[- ]?ICMS", r"ICMS[/ ]IPI", r"SPED Fiscal"],
            "conteudo_obrigatorio": [r"Escritura[cç][aã]o Fiscal Digital|EFD|SPED"],
            "exclui": [r"Contribui[cç][oõ]es", DARF],
        },
    },
    {
        "codigo": "ICMS",
        "nome": "Guia de ICMS (GARE/DAE)",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "Legislação estadual (prazo varia por UF)",
        "multa_referencia": "Conforme legislação estadual",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": LUCRO, "exige_algum": ["comercio", "industria"]},
        "reconhecimento": {
            "nome": [r"icms", r"gare", r"(^|[^a-z])dae([^a-z]|$)"],
            "conteudo": [r"\bGARE\b", r"Documento de Arrecada[cç][aã]o Estadual", r"\bDAE\b"],
            "conteudo_obrigatorio": [r"ICMS"],
            "exclui": [r"Escritura[cç][aã]o Fiscal Digital", r"Recibo de Entrega", r"DeSTDA"],
            "pastas": ["fiscal", "guias"],
        },
    },
    {
        "codigo": "ISS",
        "nome": "Guia de ISS",
        "departamento": "FISCAL",
        "periodicidade": "mensal",
        "base_legal": "LC 116/2003 e legislação municipal (prazo varia por município)",
        "multa_referencia": "Conforme legislação municipal",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 10, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": LUCRO, "exige": ["servicos"]},
        "reconhecimento": {
            "nome": [r"(^|[^a-z])iss(qn)?([^a-z]|$)"],
            "conteudo": [r"Guia", r"\bDAM\b", r"Documento de Arrecada[cç][aã]o Municipal", r"Boleto"],
            "conteudo_obrigatorio": [r"\bISSQN\b|Imposto Sobre Servi[cç]os|\bISS\b"],
            "exclui": [r"Simples Nacional"],
            "pastas": ["fiscal", "guias"],
        },
    },
    {
        "codigo": "DMED",
        "nome": "DMED (serviços de saúde)",
        "departamento": "FISCAL",
        "periodicidade": "anual",
        "base_legal": "IN RFB 985/2009",
        "multa_referencia": "R$ 5.000,00 por mês-calendário (IN RFB 985/2009)",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "mes": 2, "anos_apos": 1},
        "aplicabilidade": {"exige": ["area_saude"], "regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {"nome": [r"dmed"], "conteudo": [r"\bDMED\b", r"Declara[cç][aã]o de Servi[cç]os M[eé]dicos"]},
    },
    {
        "codigo": "DIMOB",
        "nome": "DIMOB (atividades imobiliárias)",
        "departamento": "FISCAL",
        "periodicidade": "anual",
        "base_legal": "IN RFB 1.115/2010",
        "multa_referencia": "R$ 5.000,00 por mês-calendário",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "mes": 2, "anos_apos": 1},
        "aplicabilidade": {"exige": ["atividade_imobiliaria"], "regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {"nome": [r"dimob"], "conteudo": [r"\bDIMOB\b", r"Declara[cç][aã]o de Informa[cç][oõ]es sobre Atividades Imobili[aá]rias"]},
    },
    # ---------------------------------------------------------------- CONTÁBIL
    {
        "codigo": "BALANCETE",
        "nome": "Balancete mensal (prazo interno)",
        "departamento": "CONTABIL",
        "periodicidade": "mensal",
        "base_legal": "NBC TG Estrutura Conceitual / ITG 2000 (R1) - escrituração tempestiva",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 25, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"regimes": LUCRO_E_TERCEIRO_SETOR},
        "reconhecimento": {
            "nome": [r"balancete"],
            "conteudo": [r"Balancete( de Verifica[cç][aã]o)?"],
            "exclui": [r"Balan[cç]o Patrimonial"],
            "pastas": ["contabil"],
        },
    },
    {
        "codigo": "DEMONSTRACOES_ANUAIS",
        "nome": "Demonstrações contábeis anuais (BP, DRE, DMPL, DFC, Notas)",
        "departamento": "CONTABIL",
        "periodicidade": "anual",
        "base_legal": "Lei 6.404/1976, art. 176; NBC TG 26 (R5) / NBC TG 1000 (R1) / ITG 1000",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "mes": 4, "anos_apos": 1},
        "aplicabilidade": {"regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"balan[cç]o", r"demonstra[cç](oe|õe)s"],
            "conteudo": [r"Balan[cç]o Patrimonial", r"Demonstra[cç][aã]o do Resultado"],
            "conteudo_obrigatorio": [r"Balan[cç]o Patrimonial"],
            "pastas": ["contabil"],
        },
    },
    {
        "codigo": "ECD",
        "nome": "ECD - Escrituração Contábil Digital",
        "departamento": "CONTABIL",
        "periodicidade": "anual",
        "base_legal": "IN RFB 2.003/2021, art. 5º (red. IN RFB 2.142/2023)",
        "multa_referencia": "0,5% da receita bruta por mês (Lei 8.218/1991, art. 12)",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "mes": 6, "anos_apos": 1},
        "aplicabilidade": {"regimes": LUCRO_E_TERCEIRO_SETOR},
        "reconhecimento": {
            "nome": [r"(^|[^a-z])ecd([^a-z]|$)", r"sped.{0,3}cont[aá]bil"],
            "conteudo": [r"Escritura[cç][aã]o Cont[aá]bil Digital", r"SPED Cont[aá]bil"],
            "exclui": [r"Escritura[cç][aã]o Cont[aá]bil Fiscal"],
        },
    },
    {
        "codigo": "ECF",
        "nome": "ECF - Escrituração Contábil Fiscal",
        "departamento": "CONTABIL",
        "periodicidade": "anual",
        "base_legal": "IN RFB 2.004/2021, art. 3º",
        "multa_referencia": "0,25% do lucro líquido por mês, limitada a 10% (Lei 12.973/2014, art. 8º-A)",
        "regra_vencimento": {"tipo": "ultimo_dia_util", "mes": 7, "anos_apos": 1},
        "aplicabilidade": {"regimes": LUCRO_E_TERCEIRO_SETOR},
        "reconhecimento": {
            "nome": [r"(^|[^a-z])ecf([^a-z]|$)"],
            "conteudo": [r"Escritura[cç][aã]o Cont[aá]bil Fiscal", r"\bECF\b"],
            "exclui": [r"Escritura[cç][aã]o Cont[aá]bil Digital"],
        },
    },
    # ------------------------------------------------------- DEPARTAMENTO PESSOAL
    {
        "codigo": "FOLHA",
        "nome": "Folha de pagamento e holerites",
        "departamento": "PESSOAL",
        "periodicidade": "mensal",
        "base_legal": "CLT, art. 459, §1º (salário até o 5º dia útil) - prazo interno no 3º dia útil",
        "regra_vencimento": {"tipo": "dia_util", "n": 3, "meses_apos": 1},
        "aplicabilidade": {"exige": ["possui_funcionarios"]},
        "reconhecimento": {
            "nome": [r"folha", r"holerite", r"contra.?cheque"],
            "conteudo": [r"Folha de Pagamento", r"Recibo de Pagamento de Sal[aá]rio", r"Demonstrativo de Pagamento", r"Holerite"],
            "exclui": [r"Pr[oó][- ]?labore", r"FGTS Digital", DARF],
            "pastas": ["pessoal"],
        },
    },
    {
        "codigo": "PROLABORE",
        "nome": "Recibo de pró-labore",
        "departamento": "PESSOAL",
        "periodicidade": "mensal",
        "base_legal": "Lei 8.212/1991, art. 12, V, 'f' e art. 22, III",
        "regra_vencimento": {"tipo": "dia_util", "n": 5, "meses_apos": 1},
        "aplicabilidade": {"exige": ["possui_prolabore"], "regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"pr[oó].?labore"],
            "conteudo": [r"Pr[oó][- ]?labore"],
            "exclui": [DARF],
            "pastas": ["pessoal"],
        },
    },
    {
        "codigo": "ESOCIAL",
        "nome": "eSocial - fechamento dos eventos periódicos (S-1299)",
        "departamento": "PESSOAL",
        "periodicidade": "mensal",
        "base_legal": "Decreto 8.373/2014; Manual de Orientação do eSocial",
        "multa_referencia": "Conforme CLT e Lei 8.212/1991, por evento/trabalhador",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 15, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"exige_algum": ["possui_funcionarios", "possui_prolabore"], "regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"esocial", r"s.?1299"],
            "conteudo": [r"S-1299", r"Fechamento dos Eventos Peri[oó]dicos"],
            "conteudo_obrigatorio": [r"eSocial"],
            "pastas": ["pessoal"],
        },
    },
    {
        "codigo": "FGTS_DIGITAL",
        "nome": "Guia do FGTS Digital (GFD)",
        "departamento": "PESSOAL",
        "periodicidade": "mensal",
        "base_legal": "Lei 8.036/1990, art. 15 (red. Lei 14.438/2022); Portaria MTE 240/2024",
        "multa_referencia": "Multa e juros conforme Lei 8.036/1990, art. 22",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 20, "meses_apos": 1, "ajuste": "antecipa"},
        "aplicabilidade": {"exige": ["possui_funcionarios"]},
        "reconhecimento": {
            "nome": [r"fgts", r"(^|[^a-z])gfd([^a-z]|$)"],
            "conteudo": [r"FGTS Digital", r"Guia do FGTS", r"\bGFD\b"],
            "pastas": ["pessoal", "guias"],
        },
    },
    # ------------------------------------------- DOCUMENTOS DEPOSITADOS PELO CLIENTE
    {
        "codigo": "DOC_EXTRATOS",
        "nome": "Extratos bancários (cliente)",
        "departamento": "CLIENTE",
        "tipo": TIPO_RECEBIMENTO,
        "periodicidade": "mensal",
        "base_legal": "Prazo combinado em contrato de prestação de serviços (NBC PG 01 - Res. CFC 1.590/2020)",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 5, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"extrato", r"\.ofx$", r"concilia"],
            "conteudo": [r"Extrato", r"Saldo anterior", r"Saldo dispon[ií]vel", r"<OFX>", r"<STMTTRN>"],
            "exclui": [r"Simples Nacional", r"Programa Gerador"],
            "pastas": ["cliente", "extrato", "banco"],
        },
    },
    {
        "codigo": "DOC_NOTAS_FISCAIS",
        "nome": "XML/PDF das notas fiscais de entrada e saída (cliente)",
        "departamento": "CLIENTE",
        "tipo": TIPO_RECEBIMENTO,
        "periodicidade": "mensal",
        "base_legal": "Prazo combinado em contrato; guarda: CTN, art. 195, par. único",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 5, "meses_apos": 1, "ajuste": "posterga"},
        "aplicabilidade": {"regimes": TODOS_EXCETO_MEI},
        "reconhecimento": {
            "nome": [r"(^|[^a-z])nf-?s?e?([^a-z]|$)", r"nota.{0,3}fisca", r"notas", r"\.xml$", r"xmls?"],
            "conteudo": [r"<nfeProc", r"<infNFe", r"CompNfse", r"<Nfse", r"DANFE", r"Nota Fiscal de Servi[cç]o"],
            "pastas": ["cliente", "nota", "xml"],
        },
    },
    {
        "codigo": "DOC_VARIAVEIS_FOLHA",
        "nome": "Ponto e variáveis da folha (cliente)",
        "departamento": "CLIENTE",
        "tipo": TIPO_RECEBIMENTO,
        "periodicidade": "mensal",
        "base_legal": "CLT, art. 74, §2º (registro de ponto) - prazo combinado em contrato",
        "regra_vencimento": {"tipo": "dia_fixo", "dia": 25, "meses_apos": 0, "ajuste": "antecipa"},
        "aplicabilidade": {"exige": ["possui_funcionarios"]},
        "reconhecimento": {
            "nome": [r"ponto", r"vari[aá]veis", r"horas.?extras", r"faltas"],
            "conteudo": [r"Folha de Ponto", r"Cart[aã]o de Ponto", r"Espelho de Ponto", r"Horas Extras"],
            "pastas": ["cliente", "ponto", "pessoal"],
        },
    },
]


def sincronizar_catalogo(sessao: Session) -> int:
    """Insere/atualiza o catálogo padrão no banco. Retorna quantos itens foram gravados."""
    existentes = {o.codigo: o for o in sessao.scalars(select(Obrigacao))}
    for item in CATALOGO:
        dados = {
            "nome": item["nome"],
            "descricao": item.get("descricao", ""),
            "base_legal": item.get("base_legal", ""),
            "departamento": item["departamento"],
            "tipo": item.get("tipo", TIPO_ENTREGA),
            "periodicidade": item.get("periodicidade", "mensal"),
            "regra_vencimento": item["regra_vencimento"],
            "aplicabilidade": item.get("aplicabilidade", {}),
            "reconhecimento": item.get("reconhecimento", {}),
            "multa_referencia": item.get("multa_referencia", ""),
        }
        obj = existentes.get(item["codigo"])
        if obj is None:
            sessao.add(Obrigacao(codigo=item["codigo"], **dados))
        else:
            for k, v in dados.items():
                setattr(obj, k, v)
    sessao.flush()
    return len(CATALOGO)
