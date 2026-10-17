"""
Carteira de empresas do escritório, extraída do Domínio (Controle > Empresas ou
Relatórios > Cadastrais > Empresas) para um CSV ';' com cabeçalho codigo;apelido;cnpj;regime.

O apelido precisa ser o do Domínio, letra por letra: é o nome da pasta "<Código>-<Apelido>"
que a Rotina Automática procura (Central de Soluções cód. 4399/9143).
"""
import csv
import os
import re

from .xmlfiscal import digits

# Empresas do próprio escritório / de exemplo que nunca entram na integração
EXCLUIR = ("EXEMPLO", "MORAES & OLIVEIRA CO")
EXCLUIR_EXATO = ("MORAES",)


def excluida(apelido):
    a = (apelido or "").strip().upper()
    return a in EXCLUIR_EXATO or any(a.startswith(p) for p in EXCLUIR)


def ler_carteira(path, incluir_excluidas=False):
    emp = []
    if not path:
        return emp
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            if not row.get("cnpj"):
                continue
            if not incluir_excluidas and excluida(row.get("apelido")):
                continue
            emp.append({"codigo": row.get("codigo", ""), "apelido": row.get("apelido", ""), "cnpj": digits(row["cnpj"]),
                        "regime": (row.get("regime") or "?").upper()})
    return emp


def nome_pasta(e):
    """Exatamente Código-Apelido; caracteres inválidos em nome de pasta Windows são trocados."""
    return re.sub(r'[<>:"/\\|?*]', "_", f'{e["codigo"]}-{e["apelido"]}').strip()


def rotulo(e):
    return f'{e["codigo"]}-{e["apelido"]}'


def empresa_da_pasta(caminho, raiz, carteira):
    """Empresa dona da pasta de 1º nível sob `raiz`, pelo prefixo '<codigo>-' (padrão do Domínio)."""
    rel = os.path.relpath(caminho.split("!")[0], raiz)
    m = re.match(r"\s*(\d+)\s*-", rel.split(os.sep)[0])
    if m:
        for e in carteira:
            if e["codigo"] == m.group(1):
                return e
    return None
