"""
Matriz de regras de importação a partir dos XML reais (D:\\XML ORIGINAIS ou qualquer pasta), por empresa.

A configuração de importação do Domínio é, no fundo, uma tabela "combinação do XML → acumulador/CFOP de
entrada". Este script lê todos os XML (soltos ou dentro de .zip) e lista exatamente quais combinações
existem para cada empresa — é a lista de linhas que precisam existir nas guias Acumuladores / CFOPs /
CST-CSOSN de cada tipo de importação. Sem isso, a configuração é feita "no chute" e a importação devolve
"Não foi encontrada relação de acumulador para o CFOP ...".

Uso:
  python -m mo_dominio matriz --raiz "D:\\XML ORIGINAIS" --carteira carteira.csv --saida ./matriz
  python -m mo_dominio matriz --raiz "D:\\XML ORIGINAIS\\86-RTX" --cnpj 12345678000199 --regime SIMPLES --saida ./matriz

  --carteira  CSV ';' com cabeçalho codigo;apelido;cnpj;regime (regime livre: SIMPLES, PRESUMIDO, MEI, IMUNE, REAL).
              A pasta de cada empresa é reconhecida pelo prefixo "<codigo>-" no nome (padrão do Domínio); se a
              pasta não casar, a empresa é identificada pelo CNPJ que mais aparece como emitente/destinatário.
  --raiz      pasta com subpastas por empresa (ou a pasta de uma empresa só, com --cnpj).

Saídas em --saida:
  matriz_carteira.csv   uma linha por (empresa, tipo, direcao, regra) com quantidade de docs/itens e valor
  matriz_<codigo>.md    leitura humana por empresa: tipos presentes, regras, alertas, o que conferir no Domínio
  modelos.json          por regime: empresa sugerida como modelo (a que cobre mais regras do regime), regras
                        cobertas pelo modelo, e o "delta" de cada empresa (regras que o modelo não tem)
  terceiros.csv         XML em que nenhum CNPJ da carteira é emitente/destinatário (pasta errada / não cliente)
  nao_reconhecidos.csv  arquivos inválidos ou de leiaute desconhecido

O que é "regra" por tipo (é o que se configura no Domínio):
  NF-e saída      : CFOP | CST/CSOSN+orig | CST PIS/COFINS | destinatário (CNPJ/CPF/exterior) | formas de pagamento
  NF-e entrada    : CFOP do fornecedor | CST/CSOSN do fornecedor | UF do fornecedor (1º dígito do CFOP de entrada) | CRT do fornecedor
  NFC-e           : CFOP | CST/CSOSN | com/sem CPF | forma de pagamento
  CT-e            : CFOP | CST ICMS | papel da empresa (tomador/remetente/destinatário) | UF do emitente
  NFS-e Nacional  : prestado/tomado | tribISSQN | tpRetISSQN | cTribNac | município (mesmo/outro/outra UF) | retenções federais
  NFS-e ABRASF    : prestado/tomado | natureza/exigibilidade | item da lista | IssRetido | retenções federais
"""
import argparse
import csv
import json
import os
import re
from collections import defaultdict

from .carteira import empresa_da_pasta, ler_carteira
from .xmlfiscal import D0, digits, direcao_para, iter_xml, parse_bytes


def uf_de_ibge(cod):
    return cod[:2] if cod else ""


def classe_municipio(mun_emissor, mun_ref):
    if not mun_emissor or not mun_ref:
        return "mun_desconhecido"
    if mun_emissor == mun_ref:
        return "mesmo_municipio"
    if uf_de_ibge(mun_emissor) == uf_de_ibge(mun_ref):
        return "outro_municipio"
    return "outra_uf"


def regras_do_doc(doc, direcao):
    """Devolve lista de (regra_str, valor) — uma por item para NF-e/NFC-e/CT-e, uma por nota para NFS-e."""
    t = doc["tipo"]
    out = []
    if t in ("NF-e", "NFC-e"):
        pag = "+".join(doc.get("formas_pagamento") or []) or "sem_pag"
        for it in doc["itens"]:
            cst = f'{it["tipo_cst"]}{it["cst"]}' if it["cst"] else "sem_cst"
            if direcao == "saida":
                r = f'CFOP={it["cfop"]}|{cst}|orig={it["orig"]}|PIS={it["cst_pis"]}|COFINS={it["cst_cofins"]}|dest={doc["dest_tipo"]}|pag={pag}|fin={doc["finalidade"]}'
            else:
                r = f'CFOPforn={it["cfop"]}|{cst}|orig={it["orig"]}|PIS={it["cst_pis"]}|COFINS={it["cst_cofins"]}|UFforn={doc["emitente_uf"]}|CRTforn={doc["emitente_crt"]}|fin={doc["finalidade"]}'
            if it["icms_st"]:
                r += "|ST"
            if it["ipi"]:
                r += "|IPI"
            out.append((r, it["valor"]))
    elif t == "CT-e":
        it = doc["itens"][0]
        papel = "emitente" if direcao == "saida" else ("tomador" if digits(doc.get("destinatario")) == doc.get("_cnpj") else "participante")
        r = f'CFOP={it["cfop"]}|CST{it["cst"]}|papel={papel}|UFemit={doc["emitente_uf"]}|modal={doc["modal"]}|tomaCod={doc["tomador_codigo"]}'
        out.append((r, it["valor"]))
    elif t == "NFS-e Nacional":
        ref = doc["mun_tomador"] if direcao == "prestado" else doc["mun_emissor"]
        base = doc["mun_emissor"] if direcao == "prestado" else doc["mun_tomador"]
        ret = []
        if doc["ret_irrf"] > 0: ret.append("IRRF")
        if doc["tp_ret_pis_cofins"] not in ("", "0"): ret.append(f'PISCOFINS{doc["tp_ret_pis_cofins"]}')
        if doc["ret_csll"] > 0: ret.append("CSLL")
        r = (f'{direcao}|tribISSQN={doc["trib_issqn"]}|tpRetISSQN={doc["tp_ret_issqn"]}|cTribNac={doc["c_trib_nac"]}'
             f'|{classe_municipio(base, ref)}|incid={classe_municipio(doc["mun_emissor"], doc["mun_incidencia"])}'
             f'|opSN={doc["op_simp_nac"]}|regEsp={doc["reg_esp_trib"]}|ret={"+".join(ret) or "nenhuma"}')
        out.append((r, doc["valor_total"]))
    elif t == "NFS-e ABRASF":
        ret = []
        if doc["ret_irrf"] > 0: ret.append("IRRF")
        if doc["ret_pis"] > 0 or doc["ret_cofins"] > 0: ret.append("PISCOFINS")
        if doc["ret_csll"] > 0: ret.append("CSLL")
        r = (f'{direcao}|natOp={doc["natureza_operacao"]}|item={doc["item_lista"]}|IssRetido={doc["iss_retido_flag"]}'
             f'|mun={doc["mun_prestacao"]}|opSN={doc["op_simp_nac"]}|regEsp={doc["reg_esp_trib"]}|ret={"+".join(ret) or "nenhuma"}')
        out.append((r, doc["valor_total"]))
    return out


def alertas_da_empresa(emp, regras, tipos):
    """Sinais que mudam a configuração e que o operador precisa decidir antes de importar."""
    a = []
    reg = emp["regime"]
    chaves = list(regras.keys())
    if reg.startswith("SIMPLES") or reg == "MEI":
        if any("prestado" in k and ("IRRF" in k or "PISCOFINS" in k or "CSLL" in k) for k in chaves):
            a.append("Retenção federal (IRRF/CSRF) sobre NFS-e PRESTADA por optante do Simples/MEI: em regra indevida — conferir nota a nota antes de habilitar impostos 16/22/23/24/25 no acumulador")
        if any(k.startswith("NF-e/entrada") and "CST" in k and "CSOSN" not in k for k in chaves):
            a.append("Entradas com CST de fornecedor do regime normal: Simples não toma crédito — acumulador de entrada com Percentual B.C do ICMS = 0")
    if reg.startswith("PRESUMIDO") or reg == "REAL":
        if any("tomado" in k for k in chaves):
            a.append("Serviços tomados: verificar retenção de ISS (tpRetISSQN 2/3 ou IssRetido=1) e CSRF/IRRF a reter como tomador — impostos 16/18/22/23/24/25 nos parâmetros e no acumulador de tomados")
    if "NFC-e" in tipos and any("dest=SEM_DEST" in k for k in chaves):
        a.append("NFC-e sem CPF/CNPJ: Configuração NFC-e > Cliente padrão = 'Quando no arquivo não possuir' (cód. 9261)")
    if any("CT-e" in k and "papel=tomador" in k for k in chaves):
        a.append("CT-e tomado (frete sobre compras): acumulador de frete em Entradas > CFOPs e Acumuladores; crédito de ICMS só se regime normal de ICMS")
    if any("CT-e" in k and "papel=participante" in k for k in chaves):
        a.append("CT-e em que a empresa é remetente/destinatária mas não tomadora: normalmente NÃO se escritura — confirmar antes de importar")
    if any("fin=4" in k for k in chaves):
        a.append("Há NF-e de devolução (finNFe=4): acumulador com [x] Devolução (Simples: mesmo anexo da venda — cód. 2171)")
    if any("tpRetISSQN=2" in k or "tpRetISSQN=3" in k for k in chaves if "prestado" in k):
        a.append("NFS-e prestada com ISS retido pelo tomador: acumulador próprio com Tipo de ISS = retido (cód. 10573); no Simples, excluir da base do ISS no DAS")
    if any("outra_uf" in k or "outro_municipio" in k for k in chaves if "prestado" in k):
        a.append("Serviços prestados para outro município/UF: [x] Definir CFPS (9101/9102/9103) na configuração Padrão Nacional (cód. 10162)")
    if any("EVENTO_CANCELAMENTO" in t for t in tipos):
        a.append("Há eventos de cancelamento: guia Cancelamento configurada e importar 'canceladas' depois das autorizadas (cód. 12427)")
    return a


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mo_dominio matriz")
    ap.add_argument("--raiz", required=True)
    ap.add_argument("--carteira", help="CSV codigo;apelido;cnpj;regime")
    ap.add_argument("--cnpj", help="CNPJ quando --raiz é a pasta de uma empresa só")
    ap.add_argument("--regime", default="?")
    ap.add_argument("--codigo", default="")
    ap.add_argument("--apelido", default="")
    ap.add_argument("--saida", default="./matriz")
    ap.add_argument("--competencia", default="", help="MMAAAA — se informado, só documentos dessa competência entram na matriz")
    a = ap.parse_args(argv)

    carteira = ler_carteira(a.carteira)
    if a.cnpj:
        carteira = [{"codigo": a.codigo or "0", "apelido": a.apelido or os.path.basename(os.path.normpath(a.raiz)),
                     "cnpj": digits(a.cnpj), "regime": a.regime.upper()}]
    if not carteira:
        ap.error("informe --carteira ou --cnpj")
    por_cnpj = {e["cnpj"]: e for e in carteira}
    os.makedirs(a.saida, exist_ok=True)

    # empresa -> tipo/direcao/regra -> {docs:set, itens:int, valor:Decimal}
    matriz = defaultdict(lambda: defaultdict(lambda: {"docs": set(), "itens": 0, "valor": D0}))
    tipos_emp = defaultdict(set)
    terceiros, nao_rec = [], []
    contagem_pasta = defaultdict(lambda: defaultdict(int))  # pasta topo -> cnpj -> ocorrências (para inferir dono da pasta)
    n = 0
    for origem, data in iter_xml(a.raiz, ignorar=[a.saida]):
        n += 1
        doc = parse_bytes(data, origem)
        if doc["tipo"] == "NAO_RECONHECIDO":
            nao_rec.append((origem, doc.get("erro", "")))
            continue
        if a.competencia and doc.get("competencia") and doc["competencia"] != a.competencia:
            continue
        if doc.get("situacao") not in (None, "autorizada") and not doc["tipo"].startswith("EVENTO"):
            pass  # canceladas também entram: a regra precisa existir para a nota e para o cancelamento
        donos = []
        for cnpj, e in por_cnpj.items():
            d = direcao_para(doc, cnpj)
            if d in ("saida", "entrada", "prestado", "tomado"):
                donos.append((e, d))
        e_pasta = empresa_da_pasta(origem, a.raiz, carteira) if not a.cnpj else carteira[0]
        if doc["tipo"].startswith("EVENTO"):
            if e_pasta is not None:
                tipos_emp[e_pasta["cnpj"]].add(f'{doc["tipo"]}(mod {doc.get("modelo")})')
            continue
        if not donos:
            terceiros.append((origem, doc["tipo"], doc.get("emitente"), doc.get("destinatario"), doc.get("numero"), str(doc.get("valor_total"))))
            continue
        for e, d in donos:
            doc["_cnpj"] = e["cnpj"]
            tipos_emp[e["cnpj"]].add(f'{doc["tipo"]}/{d}')
            for regra, valor in regras_do_doc(doc, d):
                k = f'{doc["tipo"]}/{d}|{regra}'
                cel = matriz[e["cnpj"]][k]
                cel["docs"].add(doc.get("chave") or doc.get("numero") or origem)
                cel["itens"] += 1
                cel["valor"] += valor
            if e_pasta is not None and e_pasta["cnpj"] != e["cnpj"]:
                # XML na pasta de uma empresa mas pertencente a outra da carteira — vale registrar
                tipos_emp[e["cnpj"]].add(f'(xml achado na pasta de {e_pasta["codigo"]}-{e_pasta["apelido"]})')

    # ---- matriz_carteira.csv ------------------------------------------------------------------
    with open(os.path.join(a.saida, "matriz_carteira.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["codigo", "apelido", "cnpj", "regime", "tipo", "direcao", "regra", "qtd_docs", "qtd_itens", "valor"])
        for e in sorted(carteira, key=lambda x: (x["regime"], int(x["codigo"] or 0))):
            for k, cel in sorted(matriz[e["cnpj"]].items()):
                tipo_dir, regra = k.split("|", 1)
                tipo, direcao = tipo_dir.split("/", 1)
                w.writerow([e["codigo"], e["apelido"], e["cnpj"], e["regime"], tipo, direcao, regra, len(cel["docs"]), cel["itens"], f'{cel["valor"]:.2f}'.replace(".", ",")])

    # ---- modelos.json --------------------------------------------------------------------------
    modelos = {}
    por_regime = defaultdict(list)
    for e in carteira:
        por_regime[e["regime"]].append(e)
    for regime, emps in por_regime.items():
        cobertura = {e["cnpj"]: set(matriz[e["cnpj"]].keys()) for e in emps}
        uniao = set().union(*cobertura.values()) if cobertura else set()
        # regra "genérica" = sem os campos que variam por parceiro (UF, pagamento, município) para medir cobertura funcional
        def generica(k):
            return re.sub(r"\|(UFforn|UFemit|pag|dest|mun|CRTforn|tomaCod)=[^|]*", "", k)
        cob_gen = {c: {generica(k) for k in ks} for c, ks in cobertura.items()}
        uniao_gen = set().union(*cob_gen.values()) if cob_gen else set()
        modelo = max(emps, key=lambda e: (len(cob_gen[e["cnpj"]]), len(cobertura[e["cnpj"]]))) if emps else None
        deltas = {}
        for e in emps:
            if modelo and e["cnpj"] != modelo["cnpj"]:
                falta = sorted(cob_gen[e["cnpj"]] - cob_gen[modelo["cnpj"]])
                deltas[f'{e["codigo"]}-{e["apelido"]}'] = falta
        modelos[regime] = {
            "empresas": len(emps),
            "modelo_sugerido": f'{modelo["codigo"]}-{modelo["apelido"]}' if modelo else None,
            "regras_distintas_no_regime": len(uniao_gen),
            "regras_cobertas_pelo_modelo": len(cob_gen[modelo["cnpj"]]) if modelo else 0,
            "regras_do_modelo": sorted(cob_gen[modelo["cnpj"]]) if modelo else [],
            "delta_por_empresa": deltas,
            "empresas_sem_xml": [f'{e["codigo"]}-{e["apelido"]}' for e in emps if not matriz[e["cnpj"]]],
        }
    with open(os.path.join(a.saida, "modelos.json"), "w", encoding="utf-8") as fh:
        json.dump(modelos, fh, ensure_ascii=False, indent=2)

    # ---- matriz_<codigo>.md ---------------------------------------------------------------------
    for e in carteira:
        regras = matriz[e["cnpj"]]
        linhas = [f'# {e["codigo"]}-{e["apelido"]} — CNPJ {e["cnpj"]} — regime {e["regime"]}', ""]
        if not regras:
            linhas.append("Nenhum XML desta empresa encontrado na raiz informada.")
        else:
            linhas.append("## Tipos/direções presentes")
            linhas += [f"- {t}" for t in sorted(tipos_emp[e["cnpj"]])]
            linhas += ["", "## Regras (uma linha = uma relação que precisa existir na Configuração de Importação)", "",
                       "| tipo/direção | regra | docs | itens | valor |", "|---|---|---:|---:|---:|"]
            for k, cel in sorted(regras.items()):
                tipo_dir, regra = k.split("|", 1)
                linhas.append(f'| {tipo_dir} | {regra} | {len(cel["docs"])} | {cel["itens"]} | {cel["valor"]:.2f} |')
            al = alertas_da_empresa(e, regras, tipos_emp[e["cnpj"]])
            if al:
                linhas += ["", "## Alertas (decidir antes de configurar)"] + [f"- {x}" for x in al]
        with open(os.path.join(a.saida, f'matriz_{e["codigo"] or e["cnpj"]}.md'), "w", encoding="utf-8") as fh:
            fh.write("\n".join(linhas) + "\n")

    with open(os.path.join(a.saida, "terceiros.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["origem", "tipo", "emitente", "destinatario", "numero", "valor"])
        w.writerows(terceiros)
    with open(os.path.join(a.saida, "nao_reconhecidos.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["origem", "erro"])
        w.writerows(nao_rec)

    resumo = {"arquivos_xml_lidos": n, "empresas_com_xml": sum(1 for e in carteira if matriz[e["cnpj"]]),
              "empresas_sem_xml": sum(1 for e in carteira if not matriz[e["cnpj"]]), "terceiros": len(terceiros),
              "nao_reconhecidos": len(nao_rec), "modelos": {r: m["modelo_sugerido"] for r, m in modelos.items()}, "saida": os.path.abspath(a.saida)}
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return resumo
