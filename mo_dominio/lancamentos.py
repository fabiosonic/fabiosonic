"""
Extrato bancário (OFX) → arquivo TXT de lançamentos contábeis para importar no Domínio Contabilidade.

Por que existe: o lançamento de extrato digitado à mão é o maior consumo de horas do mês e o que mais erra
conta. Aqui o escritório mantém, por empresa, uma tabela de-para (texto do histórico do banco → conta
contábil do Domínio) e o script gera um arquivo pronto para a importação de lançamentos por leiaute
(arquivo texto delimitado). O que não casar com nenhuma regra NÃO é adivinhado: vai para a conta
transitória informada e para `pendencias.csv`, para o analista classificar e, de preferência, virar regra.

Uso:
  python -m mo_dominio ofx --ofx extrato.ofx --depara depara_86.csv --conta-banco 7 --conta-transitoria 999 \
        --saida lancamentos_86_082026.txt [--codigo-empresa 86] [--colunas data;debito;credito;valor;historico;complemento]

depara.csv (';', cabeçalho obrigatório):
  padrao;sentido;conta;historico;complemento
  - padrao     : trecho do MEMO do banco (sem diferenciar maiúsculas/acentos) ou expressão regular com prefixo "re:"
  - sentido    : C (entrada no banco), D (saída do banco) ou * (ambos)
  - conta      : código reduzido da contrapartida no plano de contas da empresa no Domínio
  - historico  : código do histórico padrão do Domínio (opcional)
  - complemento: texto do complemento; {memo} e {documento} são substituídos (vazio = memo do banco)
  A primeira regra que casar vence — coloque as mais específicas em cima.

Partidas: valor > 0 (crédito em conta) → D banco / C contrapartida; valor < 0 → D contrapartida / C banco.
Arquivo de saída: sem cabeçalho, ';', data dd/mm/aaaa, valor com vírgula decimal e sem milhar, cp1252 (Windows),
na ordem de `--colunas`. Cadastre no Domínio um leiaute de importação de lançamentos com o mesmo separador e a
mesma ordem de campos antes da primeira importação.
"""
import argparse
import csv
import json
import os
import re
import unicodedata
from decimal import Decimal

from .ofx import ler_ofx

COLUNAS_PADRAO = "data;debito;credito;valor;historico;complemento"
CAMPOS = {"data", "debito", "credito", "valor", "historico", "complemento", "documento", "empresa", "fitid"}


def normalizar(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().upper()


def ler_depara(path):
    regras = []
    with open(path, encoding="utf-8-sig") as fh:
        for i, row in enumerate(csv.DictReader(fh, delimiter=";"), start=2):
            row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            padrao, conta = row.get("padrao", ""), row.get("conta", "")
            if not padrao or not conta:
                continue
            sentido = (row.get("sentido") or "*").upper()[:1]
            if sentido not in "CD*":
                raise ValueError(f"{path}:{i}: sentido deve ser C, D ou * (veio {row.get('sentido')!r})")
            if padrao.lower().startswith("re:"):
                casa = re.compile(padrao[3:], re.I).search
                alvo = "bruto"
            else:
                p = normalizar(padrao)
                casa = lambda memo, p=p: p in memo  # noqa: E731
                alvo = "norm"
            regras.append({"linha": i, "padrao": padrao, "sentido": sentido, "conta": conta, "casa": casa, "alvo": alvo,
                           "historico": row.get("historico", ""), "complemento": row.get("complemento", "")})
    return regras


def classificar(t, regras):
    sentido = "C" if t["valor"] > 0 else "D"
    norm = normalizar(t["memo"])
    for r in regras:
        if r["sentido"] not in ("*", sentido):
            continue
        if r["casa"](t["memo"] if r["alvo"] == "bruto" else norm):
            return r
    return None


def fmt_valor(v):
    return f"{abs(v):.2f}".replace(".", ",")


def fmt_data(iso):
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if len(iso) == 10 else ""


def limpar_campo(s, sep):
    return re.sub(r"\s+", " ", (s or "").replace(sep, " ")).strip()[:200]


def gerar(extrato, regras, conta_banco, conta_transitoria, colunas=COLUNAS_PADRAO, codigo_empresa="",
          sep=";", historico_padrao=""):
    cols = [c.strip().lower() for c in colunas.split(";") if c.strip()]
    invalidas = [c for c in cols if c not in CAMPOS]
    if invalidas:
        raise ValueError(f"colunas desconhecidas: {invalidas}; válidas: {sorted(CAMPOS)}")
    linhas, pendencias, vistos = [], [], set()
    tot = {"creditos": Decimal("0"), "debitos": Decimal("0"), "classificados": 0, "pendentes": 0, "duplicados": 0, "zerados": 0}
    for t in extrato["transacoes"]:
        chave = t["fitid"] or (t["data"], t["valor"], t["memo"], t["documento"])
        if chave in vistos:
            tot["duplicados"] += 1
            continue
        vistos.add(chave)
        if t["valor"] == 0:
            tot["zerados"] += 1
            continue
        r = classificar(t, regras)
        contra = r["conta"] if r else conta_transitoria
        if r:
            tot["classificados"] += 1
            comp = (r["complemento"] or "{memo}").replace("{memo}", t["memo"]).replace("{documento}", t["documento"])
            hist = r["historico"] or historico_padrao
        else:
            tot["pendentes"] += 1
            comp, hist = t["memo"], historico_padrao
            pendencias.append(t)
        if t["valor"] > 0:
            deb, cred = conta_banco, contra
            tot["creditos"] += t["valor"]
        else:
            deb, cred = contra, conta_banco
            tot["debitos"] += -t["valor"]
        reg = {"data": fmt_data(t["data"]), "debito": deb, "credito": cred, "valor": fmt_valor(t["valor"]),
               "historico": hist, "complemento": limpar_campo(comp, sep), "documento": limpar_campo(t["documento"], sep),
               "empresa": codigo_empresa, "fitid": t["fitid"]}
        linhas.append(sep.join(reg[c] for c in cols))
    return linhas, pendencias, tot


def main(argv=None):
    ap = argparse.ArgumentParser(prog="mo_dominio ofx", description="Extrato OFX → TXT de lançamentos contábeis Domínio")
    ap.add_argument("--ofx", required=True)
    ap.add_argument("--depara", required=True, help="CSV padrao;sentido;conta;historico;complemento")
    ap.add_argument("--conta-banco", required=True, help="código reduzido da conta do banco no plano da empresa")
    ap.add_argument("--conta-transitoria", required=True, help="conta para o que não casar com o de-para (a classificar)")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--codigo-empresa", default="")
    ap.add_argument("--historico-padrao", default="", help="código de histórico quando a regra não traz um")
    ap.add_argument("--colunas", default=COLUNAS_PADRAO)
    ap.add_argument("--encoding", default="cp1252")
    a = ap.parse_args(argv)

    with open(a.ofx, "rb") as fh:
        extrato = ler_ofx(fh.read())
    regras = ler_depara(a.depara)
    linhas, pend, tot = gerar(extrato, regras, a.conta_banco, a.conta_transitoria, a.colunas, a.codigo_empresa,
                              historico_padrao=a.historico_padrao)
    os.makedirs(os.path.dirname(os.path.abspath(a.saida)), exist_ok=True)
    with open(a.saida, "w", encoding=a.encoding, errors="replace", newline="\r\n") as fh:
        fh.write("\n".join(linhas) + ("\n" if linhas else ""))
    pend_path = os.path.splitext(a.saida)[0] + "_pendencias.csv"
    with open(pend_path, "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["data", "valor", "tipo", "memo", "documento", "fitid"])
        for t in pend:
            w.writerow([fmt_data(t["data"]), f'{t["valor"]:.2f}'.replace(".", ","), t["tipo"], t["memo"], t["documento"], t["fitid"]])
    resumo = {"banco": extrato["banco"], "agencia": extrato["agencia"], "conta": extrato["conta"],
              "periodo": [extrato["inicio"], extrato["fim"]], "lancamentos": len(linhas),
              "classificados": tot["classificados"], "pendentes_conta_transitoria": tot["pendentes"],
              "duplicados_ignorados": tot["duplicados"], "zerados_ignorados": tot["zerados"],
              "total_creditos": f'{tot["creditos"]:.2f}', "total_debitos": f'{tot["debitos"]:.2f}',
              "movimento_liquido": f'{tot["creditos"] - tot["debitos"]:.2f}',
              "saldo_final_ofx": f'{extrato["saldo_final"]:.2f}', "data_saldo_ofx": extrato["data_saldo"],
              "saida": os.path.abspath(a.saida), "pendencias": os.path.abspath(pend_path)}
    print(json.dumps(resumo, ensure_ascii=False, indent=2))
    return resumo
