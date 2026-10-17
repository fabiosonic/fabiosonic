"""
Prepara os XML zipados de D:\\XML NOTAS no leiaute que a Rotina Automática do Domínio consegue ler.

Por que existe: a rotina automática NÃO abre .zip (Central de Soluções cód. 5516, item 34) e só procura
arquivos em  <Caminho da rotina>\\<Código-Apelido>\\<MMAAAA>  (cód. 4399/9143) — sem subpasta por tipo.
Como as rotinas são separadas por tipo (uma para NF-e entrada, outra para saída, NFC-e, CT-e, NFS-e
prestada/tomada — cód. 5516 itens 24/31), a solução é uma pasta-base por tipo, cada uma com a árvore
Código-Apelido\\MMAAAA dentro, e apontar cada rotina para a sua base.

Uso:
  python -m mo_dominio rotinas --origem "D:\\XML NOTAS" --destino "D:\\XML NOTAS\\_ROTINAS" \
         --carteira carteira.csv --competencia 082026 [--dry-run] [--todas-competencias]

  carteira.csv: codigo;apelido;cnpj;regime  (o nome da pasta de destino é exatamente "<codigo>-<apelido>",
                que precisa bater com Controle > Empresas do Domínio — sem espaço antes/depois do traço)

Resultado:
  <destino>\\NFE-ENTRADA\\<Código-Apelido>\\<MMAAAA>\\<chave>.xml     (NF-e mod. 55 em que a empresa é destinatária)
  <destino>\\NFE-SAIDA\\...                                          (NF-e mod. 55 emitida pela empresa)
  <destino>\\NFCE\\...                                               (NFC-e mod. 65 emitida pela empresa)
  <destino>\\CTE\\...                                                (CT-e em que a empresa é tomadora — ou emitente, se transportadora)
  <destino>\\NFSE-NACIONAL-PRESTADA\\... / NFSE-NACIONAL-TOMADA\\...
  <destino>\\NFSE-ABRASF-PRESTADA\\... / NFSE-ABRASF-TOMADA\\...
  eventos de cancelamento vão para a mesma base da nota (o importador lê "canceladas" da mesma pasta).
  <destino>\\_log\\preparacao_<MMAAAA>.csv  (um registro por XML: origem, tipo, empresa, destino ou motivo)
  <destino>\\_log\\resumo_<MMAAAA>.json      (contagens por empresa × tipo, terceiros, inválidos)

Idempotente: um XML já existente no destino não é regravado. A competência é a do documento (dCompet para
NFS-e, emissão para os demais), no formato MMAAAA — igual ao que a rotina espera. Um XML pode ser copiado para
duas empresas da carteira (cliente que vende para cliente): é o comportamento certo, cada uma escritura o seu lado.
"""
import argparse
import csv
import json
import os
import re
from collections import defaultdict

from .carteira import empresa_da_pasta, ler_carteira, nome_pasta
from .xmlfiscal import digits, direcao_para, iter_xml, parse_bytes

BASES = {
    ("NF-e", "entrada"): "NFE-ENTRADA", ("NF-e", "saida"): "NFE-SAIDA",
    ("NFC-e", "saida"): "NFCE", ("NFC-e", "entrada"): "NFE-ENTRADA",  # NFC-e recebida como compra é raríssimo; vai para entrada
    ("CT-e", "entrada"): "CTE", ("CT-e", "saida"): "CTE",
    ("NFS-e Nacional", "prestado"): "NFSE-NACIONAL-PRESTADA", ("NFS-e Nacional", "tomado"): "NFSE-NACIONAL-TOMADA",
    ("NFS-e ABRASF", "prestado"): "NFSE-ABRASF-PRESTADA", ("NFS-e ABRASF", "tomado"): "NFSE-ABRASF-TOMADA",
}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mo_dominio rotinas")
    ap.add_argument("--origem", required=True)
    ap.add_argument("--destino", required=True)
    ap.add_argument("--carteira", required=True)
    ap.add_argument("--competencia", default="", help="MMAAAA; obrigatório salvo com --todas-competencias")
    ap.add_argument("--todas-competencias", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if not a.competencia and not a.todas_competencias:
        ap.error("informe --competencia MMAAAA ou --todas-competencias")

    carteira = ler_carteira(a.carteira)
    por_cnpj = {e["cnpj"]: e for e in carteira}
    log_dir = os.path.join(a.destino, "_log")
    if not a.dry_run:
        os.makedirs(log_dir, exist_ok=True)
    registros = []
    contagem = defaultdict(lambda: defaultdict(int))
    terceiros = inval = copiados = existentes = fora = 0
    chaves_evento_pendentes = []

    for origem, data in iter_xml(a.origem, ignorar=[a.destino]):
        doc = parse_bytes(data, origem)
        if doc["tipo"] == "NAO_RECONHECIDO":
            inval += 1
            registros.append([origem, "NAO_RECONHECIDO", "", "", "", doc.get("erro", "")])
            continue
        comp = doc.get("competencia", "")
        if not a.todas_competencias and comp != a.competencia:
            fora += 1
            registros.append([origem, doc["tipo"], "", "", "", f"fora da competência ({comp})"])
            continue
        destinos = []
        if doc["tipo"].startswith("EVENTO"):
            if doc["tipo"] != "EVENTO_CANCELAMENTO":
                registros.append([origem, doc["tipo"], "", "", "", "evento que não é cancelamento — ignorado"])
                continue
            # dono do evento: emitente pela chave (saída) ou a empresa da pasta de origem (entrada)
            emit = digits(doc.get("emitente"))
            modelo = doc.get("modelo")
            e = por_cnpj.get(emit)
            if e is not None:
                base = "NFCE" if modelo == "65" else ("CTE" if modelo in ("57", "67") else ("NFSE-NACIONAL-PRESTADA" if modelo == "NFSe" else "NFE-SAIDA"))
                destinos.append((e, base))
            else:
                e = empresa_da_pasta(origem, a.origem, carteira)
                if e is not None:
                    base = "CTE" if modelo in ("57", "67") else ("NFSE-NACIONAL-TOMADA" if modelo == "NFSe" else "NFE-ENTRADA")
                    destinos.append((e, base))
        else:
            for cnpj, e in por_cnpj.items():
                d = direcao_para(doc, cnpj)
                if doc["tipo"] == "CT-e" and d == "entrada" and digits(doc.get("destinatario")) != cnpj:
                    continue  # só remetente/destinatário, não tomador: não escritura o frete
                base = BASES.get((doc["tipo"], d))
                if base:
                    destinos.append((e, base))
        if not destinos:
            terceiros += 1
            registros.append([origem, doc["tipo"], "", "", "", f'nenhuma empresa da carteira é parte (emit {doc.get("emitente")} / dest {doc.get("destinatario")})'])
            continue
        nome = (digits(doc.get("chave")) or re.sub(r"\W", "_", doc.get("chave") or doc.get("numero") or "doc"))
        if doc["tipo"].startswith("EVENTO"):
            nome += "_canc"
        for e, base in destinos:
            pasta = os.path.join(a.destino, base, nome_pasta(e), comp)
            alvo = os.path.join(pasta, nome + ".xml")
            if os.path.exists(alvo):
                existentes += 1
                registros.append([origem, doc["tipo"], f'{e["codigo"]}-{e["apelido"]}', base, alvo, "já existia"])
            else:
                if not a.dry_run:
                    os.makedirs(pasta, exist_ok=True)
                    with open(alvo, "wb") as fh:
                        fh.write(data)
                copiados += 1
                registros.append([origem, doc["tipo"], f'{e["codigo"]}-{e["apelido"]}', base, alvo, "dry-run" if a.dry_run else "copiado"])
            contagem[f'{e["codigo"]}-{e["apelido"]}'][base] += 1

    comp_tag = a.competencia or "todas"
    resumo = {"origem": a.origem, "destino": a.destino, "competencia": comp_tag, "copiados": copiados, "ja_existiam": existentes,
              "terceiros_sem_empresa": terceiros, "nao_reconhecidos": inval, "fora_da_competencia": fora,
              "por_empresa": {k: dict(v) for k, v in sorted(contagem.items())},
              "empresas_da_carteira_sem_xml": [f'{e["codigo"]}-{e["apelido"]}' for e in carteira if f'{e["codigo"]}-{e["apelido"]}' not in contagem],
              "bases_criadas": sorted({b for v in contagem.values() for b in v})}
    if not a.dry_run:
        with open(os.path.join(log_dir, f"preparacao_{comp_tag}.csv"), "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh, delimiter=";")
            w.writerow(["origem", "tipo", "empresa", "base", "destino", "resultado"])
            w.writerows(registros)
        with open(os.path.join(log_dir, f"resumo_{comp_tag}.json"), "w", encoding="utf-8") as fh:
            json.dump(resumo, fh, ensure_ascii=False, indent=2)
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return resumo
