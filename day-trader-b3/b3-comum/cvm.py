"""Acesso ao Portal de Dados Abertos da CVM (dados.cvm.gov.br) para as skills
b3-noticias, b3-analista e b3-insiders. Só biblioteca padrão.

Conjuntos usados (companhias abertas, um ZIP por ano, CSV em latin-1 com ";"):
  FCA   formulário cadastral: valor_mobiliario liga o código de negociação
        (PETR4) ao CNPJ da companhia
  IPE   documentos eventuais: fatos relevantes, comunicados, avisos (D-1)
  ITR   informações trimestrais; DFP demonstrações anuais
  VLMO  valores mobiliários negociados e detidos por administradores,
        conselheiros e controladores (Resolução CVM 44, art. 11), mensal

Os ZIPs ficam em trader-b3/cache/cvm e são baixados de novo depois de
`horas` (padrão 12): a CVM atualiza os arquivos uma vez por dia.
"""

import csv
import io
import os
import time
import zipfile

import b3lib

BASE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/%s/DADOS/%s"
csv.field_size_limit(10 ** 7)


def _cache(nome):
    return b3lib.caminho("cache", "cvm", nome)


def zip_ano(conjunto, ano, horas=12, offline=None):
    """Caminho local do ZIP de `conjunto` (IPE, FCA, ITR, DFP, VLMO) do ano."""
    nome = "%s_cia_aberta_%d.zip" % (conjunto.lower(), ano)
    if offline:
        p = os.path.join(offline, nome)
        if not os.path.exists(p):
            raise b3lib.B3Erro("não há %s em %s" % (nome, offline))
        return p
    p = _cache(nome)
    if os.path.exists(p) and time.time() - os.path.getmtime(p) < horas * 3600:
        return p
    try:
        dados = b3lib.http_get(BASE % (conjunto.upper(), nome), timeout=120)
    except Exception as e:  # rede, 404 de ano ainda sem arquivo
        if os.path.exists(p):
            return p
        raise b3lib.B3Erro("não consegui baixar %s da CVM (%s)" % (nome, e))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "wb") as f:
        f.write(dados)
    os.replace(p + ".tmp", p)
    return p


def linhas(path_zip, membro_contem, filtro=None):
    """Lê o CSV do ZIP cujo nome contém `membro_contem`; devolve dicts.
    `filtro(linha_dict)` descarta cedo o que não interessa."""
    with zipfile.ZipFile(path_zip) as z:
        nomes = [n for n in z.namelist() if n.endswith(".csv") and membro_contem in n]
        if not nomes:
            raise b3lib.B3Erro("o arquivo %s não tem %s" % (os.path.basename(path_zip), membro_contem))
        nome = min(nomes, key=len)
        with z.open(nome) as f:
            leitor = csv.DictReader(io.TextIOWrapper(f, encoding="latin-1", newline=""), delimiter=";")
            for r in leitor:
                if filtro is None or filtro(r):
                    yield r


def mapa_tickers(ano, offline=None):
    """{TICKER: {"cnpj", "nome"}} a partir do FCA do ano (e do anterior, se faltar)."""
    out = {}
    for a in (ano - 1, ano):
        try:
            z = zip_ano("FCA", a, horas=24, offline=offline)
        except b3lib.B3Erro:
            continue
        for r in linhas(z, "valor_mobiliario"):
            cod = b3lib.normalizar(r.get("Codigo_Negociacao"))
            if cod and r.get("Mercado", "").startswith("Bolsa"):
                out[cod] = {"cnpj": r["CNPJ_Companhia"], "nome": r.get("Nome_Empresarial", "").strip()}
    if not out:
        raise b3lib.B3Erro("não consegui ler o cadastro (FCA) da CVM")
    return out


def cnpj_de(syms, ano, offline=None):
    """{TICKER: cnpj} e a lista dos que não acharam."""
    m = mapa_tickers(ano, offline)
    achou, faltou = {}, []
    for s in syms:
        base = b3lib.sem_fracionario(s)
        if base in m:
            achou[base] = m[base]
        else:
            faltou.append(base)
    return achou, faltou
