"""Base de leads em CSV, lista de remoção (opt-out) e utilitários de contato.

Todo contato carrega a URL de onde saiu (`fonte_*`). Sem fonte, o contato não
entra — é esse registro que sustenta o legítimo interesse (LGPD, art. 7º, IX).
"""
from __future__ import annotations

import csv
import json
import os
import re
import threading
import unicodedata
from datetime import date
from pathlib import Path

COLUNAS = [
    "id", "empresa", "cnpj", "municipio", "setor", "subsetor", "porte", "ticket",
    "prioridade", "email", "fonte_email", "whatsapp", "fonte_whatsapp",
    "instagram", "linkedin", "site", "fonte_lead",
    "decisor_nome", "decisor_cargo", "decisor_nivel", "decisor_linkedin", "decisor_fonte",
    "sinais", "dor", "gancho", "o_que_vimos", "a_conta", "evidencias", "alertas",
    "observacao", "status", "data_1",
    "resultado", "data_resultado", "gancho_usado", "canal_usado", "texto_versao",
    "texto_enviado", "notas_resultado",
]

# status possíveis, em ordem de fluxo
NOVO, QUALIFICADO, PRONTO, NA_FILA, ENVIADO, DESCARTADO, REMOVIDO = (
    "novo", "qualificado", "pronto", "na fila", "enviado", "descartado", "removido",
)
EM_CONVERSA, BARRADO = "em conversa", "barrado"   # respondeu (humano assume) / texto reprovado 2 vezes


def carregar_config(caminho: str = "config.json") -> dict:
    p = Path(caminho)
    if not p.exists():
        raise SystemExit(
            f"Falta o {caminho}. Copie config.exemplo.json para {caminho} e preencha os dados do escritório."
        )
    return json.loads(p.read_text(encoding="utf-8"))


def normaliza_nome(nome: str) -> str:
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(ltda|me|epp|eireli|s/?a|sa)\b", " ", s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def so_digitos(numero: str) -> str:
    n = re.sub(r"\D", "", numero or "")
    if n.startswith("55") and len(n) > 11:
        n = n[2:]
    return n.lstrip("0")


def eh_celular(numero: str) -> bool:
    """DDD + 9 dígitos começando em 9. Fixo (10 dígitos) não recebe WhatsApp comum."""
    n = so_digitos(numero)
    return len(n) == 11 and n[2] == "9"


def chave_fone(numero: str) -> str:
    return so_digitos(numero)[-9:]


_TRAVA_ARQUIVO = threading.Lock()


def _ler_csv(arq: Path) -> list[dict]:
    if not arq.exists():
        return []
    with arq.open(encoding="utf-8", newline="") as f:
        return [{c: r.get(c, "") or "" for c in COLUNAS} for r in csv.DictReader(f)]


class Base:
    def __init__(self, pasta: str = "dados"):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arq = self.pasta / "base.csv"
        self.arq_remocao = self.pasta / "remocao.csv"
        self.leads: list[dict] = _ler_csv(self.arq)
        self._lido = {l["id"]: dict(l) for l in self.leads}

    # ---------- persistência
    def salvar(self) -> None:
        """Grava mesclando com o que está em disco: o motor de envio, o webhook e o
        abastecimento trabalham ao mesmo tempo, cada um com a sua cópia. Linha que
        esta cópia alterou prevalece; linha que ela não tocou fica como está no disco."""
        with _TRAVA_ARQUIVO:
            disco = {l["id"]: l for l in _ler_csv(self.arq)}
            for lead in self.leads:
                no_disco = disco.get(lead["id"])
                if no_disco is not None and lead == self._lido.get(lead["id"]):
                    lead.update(no_disco)            # não mexi: vale o disco
            meus = {l["id"] for l in self.leads}
            self.leads += [l for i, l in disco.items() if i not in meus]   # criados por outro processo
            tmp = self.arq.with_suffix(".tmp")
            with tmp.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLUNAS)
                w.writeheader()
                w.writerows(self.leads)
            os.replace(tmp, self.arq)
            self._lido = {l["id"]: dict(l) for l in self.leads}

    def por_id(self, id_: str) -> dict:
        for lead in self.leads:
            if lead["id"].lower() == id_.lower():
                return lead
        raise SystemExit(f"Lead {id_} não está na base.")

    def proximo_id(self) -> str:
        n = max((int(l["id"][1:]) for l in self.leads if l["id"][1:].isdigit()), default=0)
        return f"P{n + 1:04d}"

    # ---------- remoção (opt-out) — permanente, todos os canais
    def removidos(self) -> list[dict]:
        if not self.arq_remocao.exists():
            return []
        with self.arq_remocao.open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    def registrar_remocao(self, lead: dict, motivo: str) -> None:
        novo = not self.arq_remocao.exists()
        with self.arq_remocao.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["empresa", "fone", "email", "data", "motivo"])
            if novo:
                w.writeheader()
            w.writerow({
                "empresa": normaliza_nome(lead["empresa"]), "fone": chave_fone(lead["whatsapp"]),
                "email": lead["email"].lower(), "data": date.today().isoformat(), "motivo": motivo,
            })

    def esta_removido(self, lead: dict) -> bool:
        nome, fone, email = normaliza_nome(lead["empresa"]), chave_fone(lead.get("whatsapp", "")), (lead.get("email") or "").lower()
        for r in self.removidos():
            if (r["empresa"] and r["empresa"] == nome) or (fone and r["fone"] == fone) or (email and r["email"] == email):
                return True
        return False

    # ---------- dedupe
    def duplicado(self, lead: dict) -> dict | None:
        nome, fone, email = normaliza_nome(lead["empresa"]), chave_fone(lead.get("whatsapp", "")), (lead.get("email") or "").lower()
        for l in self.leads:
            if l is lead:
                continue
            mesmo_nome = nome and normaliza_nome(l["empresa"]) == nome and (
                not lead.get("municipio") or not l["municipio"] or normaliza_nome(l["municipio"]) == normaliza_nome(lead["municipio"])
            )
            if mesmo_nome or (fone and chave_fone(l["whatsapp"]) == fone) or (email and l["email"].lower() == email):
                return l
        return None

    def adicionar(self, dados: dict) -> tuple[dict | None, str]:
        """Devolve (lead, motivo). lead=None quando não entrou."""
        lead = {c: str(dados.get(c, "") or "").strip() for c in COLUNAS}
        if not lead["empresa"]:
            return None, "sem nome"
        if self.esta_removido(lead):
            return None, "pediu remoção"
        if self.duplicado(lead):
            return None, "já está na base"
        with _TRAVA_ARQUIVO:   # id único mesmo com outra cópia inserindo
            usados = {l["id"] for l in _ler_csv(self.arq)} | {l["id"] for l in self.leads}
        n = max((int(i[1:]) for i in usados if i[1:].isdigit()), default=0)
        lead["id"] = f"P{n + 1:04d}"
        lead["status"] = lead["status"] or NOVO
        self.leads.append(lead)
        return lead, "ok"
