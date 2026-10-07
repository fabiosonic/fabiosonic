"""Auditoria do que está no Domínio × o que foi capturado.

Entrada: relatório exportado do Domínio em CSV (separador `;`), com as colunas informadas no
config (`dominio.relatorio_colunas`), p.ex. {chave: "Chave", valor: "Valor Contábil",
cnpj: "CNPJ Empresa", competencia: "Competência"}. Para NFS-e ABRASF (sem chave nacional),
informe também `numero` e `cnpj_prestador`: o casamento é por prestador + número. Sem o mapeamento de colunas, nada é
inferido: a auditoria recusa o arquivo.
"""
from __future__ import annotations

import csv
from pathlib import Path

from ..especialista.modelo import CONTROLE, Achado
from ..util.dinheiro import ValorInvalido, dinheiro
from ..util.documentos_id import so_digitos

OBRIGATORIAS = ("chave", "valor", "cnpj")


class RelatorioInvalido(ValueError):
    pass


def _chave(bruta: str) -> str:
    """Chave de 44 (NF-e/CT-e) ou 50 dígitos (NFS-e Nacional), mesmo com pontuação; o resto fica como está."""
    d = so_digitos(bruta)
    return d if len(d) in (44, 50) else (bruta or "").strip()


def _chave_abrasf(prestador: str | None, numero: str | None) -> str | None:
    """NFS-e ABRASF não tem chave nacional: casa por (prestador, número sem zeros à esquerda)."""
    p, n = so_digitos(prestador), so_digitos(numero).lstrip("0")
    return f"ABRASF|{p}|{n}" if p and n else None


def ler_relatorio(caminho: Path, colunas: dict) -> list[dict]:
    faltam = [c for c in OBRIGATORIAS if not colunas.get(c)]
    if faltam:
        raise RelatorioInvalido(f"mapeamento de colunas sem {faltam} (config dominio.relatorio_colunas)")
    linhas = []
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with open(caminho, encoding=enc, newline="") as f:
                leitor = csv.DictReader(f, delimiter=";")
                cab = leitor.fieldnames or []
                ausentes = [colunas[c] for c in OBRIGATORIAS if colunas[c] not in cab]
                if ausentes:
                    raise RelatorioInvalido(f"colunas ausentes no relatório: {ausentes}")
                for n, l in enumerate(leitor, start=2):
                    try:
                        valor = dinheiro(l[colunas["valor"]])
                    except ValorInvalido as exc:
                        raise RelatorioInvalido(f"linha {n}: {exc}") from exc
                    ch = _chave(l[colunas["chave"]])
                    if colunas.get("numero") and colunas.get("cnpj_prestador") and len(ch) not in (44, 50):
                        ch = _chave_abrasf(l.get(colunas["cnpj_prestador"]), l.get(colunas["numero"])) or ch
                    linhas.append({"chave": ch,
                                   "valor": valor, "cnpj": so_digitos(l[colunas["cnpj"]]),
                                   "competencia": (l.get(colunas.get("competencia") or "", "") or "").strip() or None})
            return linhas
        except UnicodeDecodeError:
            linhas = []
            continue
    raise RelatorioInvalido("codificação do relatório não reconhecida")


def _valor_doc(doc: dict):
    t = doc.get("totais") or {}
    for k in ("vNF", "vServ", "vTPrest"):
        if t.get(k) is not None:
            return t[k]
    return None


def auditar(capturados: list[dict], relatorio: list[dict], cnpj: str, competencia: str) -> list[Achado]:
    """`capturados`: docs normalizados roteados para a empresa/competência (com chave)."""
    nossos = {}
    for d in capturados:
        if d.get("padrao") == "ABRASF":
            k = _chave_abrasf(d.get("prestador_cnpj"), d.get("numero"))
        else:
            k = d.get("chave")
        if k:
            nossos[k] = d
    dom = {l["chave"]: l for l in relatorio if l["cnpj"] == cnpj}
    achados = []

    def a(regra, titulo, msg, chave, correcao, valor=None):
        achados.append(Achado(regra, titulo, CONTROLE, msg, cnpj, competencia, chave, [], correcao, True, valor))

    for ch, d in sorted(nossos.items()):
        if ch not in dom:
            a("DOMINIO_NAO_IMPORTADO", "Documento capturado e não escriturado no Domínio",
              f"Chave {ch} recebida e não consta no relatório do Domínio.", ch,
              "Verificar o log da rotina automática e importar.")
        else:
            v = _valor_doc(d)
            if v is not None and v != dom[ch]["valor"]:
                a("DOMINIO_VALOR_DIVERGENTE", "Valor escriturado diferente do XML",
                  f"Chave {ch}: XML {v} × Domínio {dom[ch]['valor']}.", ch,
                  "Corrigir a escrituração conforme o documento fiscal.", dom[ch]["valor"] - v)
    for ch in sorted(set(dom) - set(nossos)):
        a("DOMINIO_SEM_DOCUMENTO", "Escriturado no Domínio sem XML capturado",
          f"Chave {ch} está no Domínio e não foi recebida pela caixa fiscal.", ch,
          "Obter o XML (cliente/portal) e arquivar; conferir se a nota é legítima.")
    return achados
