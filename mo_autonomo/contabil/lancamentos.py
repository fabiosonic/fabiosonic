"""Proposta de lançamentos a partir de OFX, usando o razão do próprio cliente como de-para (regra 9).

Entradas (exportações do Domínio, CSV `;`):
- plano de contas: codigo;descricao;analitica(S/N)
- razão histórico: data;conta_debito;conta_credito;valor;historico
- contas bancárias: cnpj;banco;agencia;conta;conta_contabil
Nada de conta "chutada": sem histórico suficiente ou conta fora do plano = pendência.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..util.arquivos import ler_csv
from ..util.dinheiro import dinheiro
from ..util.documentos_id import so_digitos


def normalizar_historico(texto: str, palavras: int = 3) -> str:
    t = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode().upper()
    t = re.sub(r"[^A-Z ]+", " ", t)
    tokens = [w for w in t.split() if len(w) > 2]
    return " ".join(tokens[:palavras])


def _ler_csv(caminho: Path) -> list[dict]:
    return ler_csv(caminho)


@dataclass
class PlanoContas:
    contas: dict[str, dict]

    @classmethod
    def carregar(cls, caminho: Path) -> "PlanoContas":
        return cls({l["codigo"].strip(): {"descricao": l.get("descricao", "").strip(),
                                          "analitica": (l.get("analitica") or "S").strip().upper() == "S"}
                    for l in _ler_csv(caminho)})

    def valida(self, codigo: str | None) -> bool:
        return bool(codigo) and codigo in self.contas and self.contas[codigo]["analitica"]


@dataclass
class DePara:
    """Aprende contrapartidas por histórico normalizado, a partir do razão do cliente."""
    ocorrencias: dict[tuple[str, str, str], Counter] = field(default_factory=dict)

    @classmethod
    def do_razao(cls, linhas: list[dict], conta_banco: str) -> "DePara":
        dp = cls()
        for l in linhas:
            deb, cred = l["conta_debito"].strip(), l["conta_credito"].strip()
            chave = normalizar_historico(l["historico"])
            if not chave:
                continue
            if deb == conta_banco and cred:
                dp.ocorrencias.setdefault(("CREDITO", chave, conta_banco), Counter())[cred] += 1
            elif cred == conta_banco and deb:
                dp.ocorrencias.setdefault(("DEBITO", chave, conta_banco), Counter())[deb] += 1
        return dp

    def sugerir(self, sentido: str, memo: str, conta_banco: str, minimo: int, dominancia: float):
        c = self.ocorrencias.get((sentido, normalizar_historico(memo), conta_banco))
        if not c:
            return None, "sem histórico igual no razão do cliente"
        conta, n = c.most_common(1)[0]
        total = sum(c.values())
        if n < minimo:
            return None, f"histórico visto só {n} vez(es) (mínimo {minimo})"
        if n / total < dominancia:
            return None, f"contrapartida ambígua ({dict(c)})"
        return conta, f"{n}/{total} ocorrências no razão"


def contas_bancarias(caminho: Path) -> dict[tuple[str, str], dict]:
    out = {}
    for l in _ler_csv(caminho):
        out[(so_digitos(l["banco"]).lstrip("0"), so_digitos(l["conta"]).lstrip("0"))] = {
            "cnpj": so_digitos(l["cnpj"]), "conta_contabil": l["conta_contabil"].strip()}
    return out


def propor(ofx: dict, conta_banco: str, depara: DePara, plano: PlanoContas,
           minimo: int = 2, dominancia: float = 0.8) -> dict:
    if not plano.valida(conta_banco):
        return {"lancamentos": [], "pendencias": [{"codigo": "CONTA_BANCO_INVALIDA",
                "mensagem": f"Conta do banco {conta_banco} não existe/não é analítica no plano do Domínio."}]}
    lanc, pend = [], []
    for t in ofx["transacoes"]:
        if t["valor"] == 0:
            continue
        sentido = "CREDITO" if t["valor"] > 0 else "DEBITO"
        contra, motivo = depara.sugerir(sentido, t["memo"], conta_banco, minimo, dominancia)
        ref = {"fitid": t["fitid"], "data": t["data"], "valor": abs(t["valor"]), "memo": t["memo"]}
        if contra is None:
            pend.append({"codigo": "SEM_CONTRAPARTIDA", "mensagem": f"{t['memo']!r}: {motivo}", **ref})
            continue
        if not plano.valida(contra):
            pend.append({"codigo": "CONTA_FORA_DO_PLANO", "mensagem": f"conta {contra} não está no plano", **ref})
            continue
        deb, cred = (conta_banco, contra) if sentido == "CREDITO" else (contra, conta_banco)
        lanc.append({"data": t["data"], "debito": deb, "credito": cred, "valor": dinheiro(abs(t["valor"])),
                     "historico": t["memo"], "fitid": t["fitid"], "origem": motivo})
    return {"lancamentos": lanc, "pendencias": pend}


def conciliar_com_notas(lancamentos_ofx: list[dict], notas: list[dict], janela_dias: int = 5) -> list[dict]:
    """Casa créditos do extrato com notas emitidas (mesmo valor, data próxima). Informativo."""
    usados, pares = set(), []
    for t in lancamentos_ofx:
        if t["valor"] <= 0:
            continue
        for i, n in enumerate(notas):
            v = (n.get("totais") or {}).get("vNF") or (n.get("totais") or {}).get("vServ")
            if i in usados or v is None or n.get("emissao") is None:
                continue
            if v == t["valor"] and abs((t["data"] - n["emissao"]).days) <= janela_dias:
                usados.add(i)
                pares.append({"fitid": t["fitid"], "chave": n.get("chave"), "valor": v})
                break
    return pares


def ler_txt_dominio(caminho: Path) -> list[dict]:
    """Lançamentos já importados no Domínio (formato TXT do escritório) como histórico do de-para.

    `DD/MM/AAAA;débito;crédito;valor;histórico;1;;;;;;` — linhas fora do formato são ignoradas.
    """
    import re as _re
    bruto = Path(caminho).read_bytes()
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = bruto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    out = []
    for l in texto.splitlines():
        f = l.split(";")
        if len(f) >= 5 and _re.fullmatch(r"\d{2}/\d{2}/\d{4}", f[0].strip()) and f[1].strip().isdigit() and f[2].strip().isdigit():
            out.append({"data": f[0].strip(), "conta_debito": f[1].strip(), "conta_credito": f[2].strip(),
                        "valor": f[3].strip(), "historico": f[4].strip()})
    return out


def historico_empresa(pasta_empresa: Path) -> list[dict]:
    """Razão para o de-para: `razao.csv` (exportação) + todo TXT em `historico/` (lançamentos já
    importados no Domínio, inclusive os exportados por este sistema depois do APROVADO)."""
    linhas = []
    razao = Path(pasta_empresa) / "razao.csv"
    if razao.exists():
        linhas += _ler_csv(razao)
    pasta_hist = Path(pasta_empresa) / "historico"
    if pasta_hist.is_dir():
        for arq in sorted(pasta_hist.glob("*.txt")):
            linhas += ler_txt_dominio(arq)
    return linhas
