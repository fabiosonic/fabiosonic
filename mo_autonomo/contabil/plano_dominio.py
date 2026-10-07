"""Leitor do plano de contas exportado do Domínio ("Impressão de campos da consulta", CSV `;`).

Cada conta ocupa um bloco de linhas:
    ;<reduzido>;;;<classificação>;...;<tipo>;        <- linha-chave (tipo do Domínio, informativo)
    <nome da conta>;;;...
    ;;;;;;;;;;;<grupo>;...;<relatório>;...
O arquivo vem em ANSI/Latin-1. Saída: `plano_contas.csv` do mo_autonomo com o código REDUZIDO
(o mesmo usado no TXT de importação de lançamentos).
"""
from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

from ..util.arquivos import escrever_atomico

_CLASSIF = re.compile(r"^\d+(\.\d+)*$")


def _texto(bruto: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return bruto.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("codificação não reconhecida")


def ler(caminho: Path) -> list[dict]:
    linhas = _texto(Path(caminho).read_bytes()).splitlines()
    contas, i = [], 0
    while i < len(linhas):
        f = linhas[i].split(";")
        if len(f) > 15 and f[0].strip() == "" and f[1].strip().isdigit() and _CLASSIF.match(f[4].strip()):
            tipo = f[15].strip()
            nome, grupo = "", ""
            if i + 1 < len(linhas):
                nome = linhas[i + 1].split(";")[0].strip()
            if i + 2 < len(linhas):
                g = linhas[i + 2].split(";")
                grupo = g[11].strip() if len(g) > 11 else ""
            contas.append({"codigo": f[1].strip(), "classificacao": f[4].strip(), "tipo": tipo,
                           "descricao": nome, "grupo": grupo})
            i += 2
        i += 1
    if not contas:
        raise ValueError("nenhuma conta reconhecida: confira se é a 'Impressão de campos da consulta' do plano")
    # analítica = sem conta filha na classificação E sem tipo "T" (que marca contas de grupo no
    # Domínio). Se as duas pistas divergem, a conta NÃO é aceita para lançamento: vira pendência
    # (conta inválida) até alguém conferir — nunca lançar em conta de grupo por suposição.
    classes = [c["classificacao"] for c in contas]
    for c in contas:
        pref = c["classificacao"] + "."
        sem_filha = not any(x.startswith(pref) for x in classes)
        c["analitica"] = sem_filha and c["tipo"].upper() != "T"
        c["divergente"] = sem_filha and c["tipo"].upper() == "T"
    repetidos = {c["codigo"] for c in contas if sum(1 for x in contas if x["codigo"] == c["codigo"]) > 1}
    if repetidos:
        raise ValueError(f"código reduzido repetido no plano: {sorted(repetidos)[:5]}")
    return contas


def escrever_plano(contas: list[dict], destino: Path, sobrescrever: bool = False) -> None:
    """Grava de forma atômica. Plano já existente só é trocado com `sobrescrever`, e o anterior
    fica guardado como plano_contas.AAAAMMDDHHMMSS.bak (nada é apagado)."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    w.writerow(["codigo", "descricao", "analitica", "classificacao", "grupo"])
    for c in contas:
        w.writerow([c["codigo"], c["descricao"], "S" if c["analitica"] else "N", c["classificacao"], c["grupo"]])
    novo = buf.getvalue().encode("utf-8")
    if destino.exists():
        atual = destino.read_bytes()
        if atual == novo:
            return  # mesmo plano: nada a trocar, nada a guardar
        if not sobrescrever:
            raise FileExistsError(f"{destino} já existe e é diferente (use --sobrescrever; o anterior vira .bak)")
        carimbo = f"{datetime.now():%Y%m%d%H%M%S}"
        for n in range(1000):  # nome único: um .bak nunca sobrescreve outro
            bak = destino.with_name(f"{destino.stem}.{carimbo}{'' if n == 0 else f'-{n}'}.bak")
            try:
                with open(bak, "xb") as f:
                    f.write(atual)
                break
            except FileExistsError:
                continue
        else:
            raise FileExistsError(f"não foi possível criar .bak único para {destino}")
    escrever_atomico(destino, novo)


def importar_pasta(pasta: Path, carteira, destino_dados: Path, sobrescrever: bool = False) -> dict:
    """Importa vários planos: cada arquivo começa com o código da empresa no Domínio (ex.: '12 - LMG.csv').
    Dois arquivos para o mesmo código: nenhum é importado (não escolhe lado)."""
    codigos = {e.codigo_dominio: e for e in carteira}
    importados, erros, feitos = [], [], set()
    arquivos = []
    for arq in sorted(Path(pasta).glob("*.csv")):
        m = re.match(r"^\s*(\d+)", arq.name)
        if not m:
            erros.append(f"{arq.name}: nome não começa com o código da empresa")
            continue
        arquivos.append((arq, str(int(m.group(1)))))
    repetidos = {c for c, n in Counter(c for _, c in arquivos).items() if n > 1}
    for arq, cod in arquivos:
        if cod in repetidos:
            erros.append(f"{arq.name}: mais de um arquivo para a empresa {cod} — nenhum foi importado")
            continue
        if cod not in codigos:
            erros.append(f"{arq.name}: código {cod} não está no cadastro de empresas")
            continue
        try:
            contas = ler(arq)
        except Exception as exc:  # noqa: BLE001
            erros.append(f"{arq.name}: {exc}")
            continue
        destino = Path(destino_dados) / cod / "plano_contas.csv"
        try:
            escrever_plano(contas, destino, sobrescrever)
        except FileExistsError as exc:
            erros.append(f"{arq.name}: {exc}")
            continue
        feitos.add(cod)
        div = [c["codigo"] for c in contas if c.get("divergente")]
        importados.append(f"{codigos[cod].pasta}: {len(contas)} contas ({sum(c['analitica'] for c in contas)} analíticas)"
                          + (f"; {len(div)} sem filha mas com tipo T, bloqueadas para lançamento até conferir: {div[:10]}" if div else ""))
    sem_plano = sorted(e.pasta for c, e in codigos.items() if c not in feitos
                       and not (Path(destino_dados) / c / "plano_contas.csv").exists())
    return {"importados": importados, "erros": erros, "sem_plano": sem_plano}
