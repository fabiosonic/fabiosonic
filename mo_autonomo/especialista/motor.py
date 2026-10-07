"""Motor do especialista: aplica as regras ativas a cada documento, à luz do perfil da empresa."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .modelo import Achado, natureza_por_normas
from .regras import DESTINATARIO, EMITENTE, QUALQUER, REGRAS, Contexto, Regra


@dataclass
class EstadoRegra:
    regra: Regra
    ativa: bool
    motivo: str
    params: dict


def estado_regra(regra: Regra, catalogo, em: date | None = None) -> EstadoRegra:
    params, faltas = {}, []
    for norma, nome in regra.parametros:
        v = catalogo.parametro(norma, nome, em)
        if v is None:
            faltas.append(f"{norma}.{nome} ({catalogo.status(norma)})")
        else:
            params[nome] = v
    if faltas:
        return EstadoRegra(regra, False, "sem parâmetro conferido: " + ", ".join(faltas), params)
    return EstadoRegra(regra, True, "ativa", params)


def _normas_citadas(regra: Regra, catalogo) -> list[dict]:
    out = []
    for n in regra.normas:
        norma = catalogo.get(n)
        out.append({"id": n, "status": catalogo.status(n),
                    "titulo": norma.titulo if norma else None,
                    "dispositivos": list(norma.dispositivos) if norma else []})
    return out


def _papel(doc: dict, cnpj: str) -> str | None:
    if doc.get("emitente_cnpj") == cnpj:
        return EMITENTE
    if cnpj in (doc.get("participantes") or []):
        return DESTINATARIO
    return None


def _achados(regra, resultados, catalogo, cnpj, competencia, documento):
    natureza = natureza_por_normas(regra.normas, catalogo)
    citadas = _normas_citadas(regra, catalogo)
    return [Achado(regra=regra.id, titulo=regra.titulo, natureza=natureza, mensagem=r.mensagem, cnpj=cnpj,
                   competencia=competencia, documento=r.documento or documento, normas=citadas,
                   correcao=r.correcao, bloqueia=r.bloqueia, valor=r.valor) for r in resultados]


def avaliar_documento(doc: dict, perfil, catalogo, data_processamento: date, regras=None) -> list[Achado]:
    out: list[Achado] = []
    papel = _papel(doc, perfil.cnpj)
    for regra in regras or REGRAS:
        if regra.escopo != "documento" or (regra.tipos and doc["tipo"] not in regra.tipos):
            continue
        if regra.papel != QUALQUER and regra.papel != papel:
            continue
        if regra.precondicao and not regra.precondicao(perfil):
            continue
        est = estado_regra(regra, catalogo, doc.get("emissao"))
        if not est.ativa:
            continue
        ctx = Contexto(perfil, papel, est.params, catalogo, data_processamento)
        out.extend(_achados(regra, regra.funcao(doc, ctx), catalogo, perfil.cnpj, doc.get("competencia"),
                            doc.get("chave") or doc.get("_sha256")))
    return out


def avaliar_competencia(docs: list[dict], perfil, competencia: str, catalogo, data_processamento: date,
                        trilha=None, regras=None) -> list[Achado]:
    out: list[Achado] = []
    for regra in regras or REGRAS:
        if regra.escopo != "competencia":
            continue
        if regra.precondicao and not regra.precondicao(perfil):
            continue
        est = estado_regra(regra, catalogo)
        if not est.ativa:
            continue
        ctx = Contexto(perfil, None, est.params, catalogo, data_processamento, docs, trilha)
        out.extend(_achados(regra, regra.funcao(docs, ctx), catalogo, perfil.cnpj, competencia, None))
    return out


def cobertura(catalogo, regras=None) -> list[dict]:
    """Relatório: cada regra, se está ativa e qual natureza produziria."""
    linhas = []
    for regra in regras or REGRAS:
        est = estado_regra(regra, catalogo)
        linhas.append({"regra": regra.id, "titulo": regra.titulo, "ativa": est.ativa, "motivo": est.motivo,
                       "natureza": natureza_por_normas(regra.normas, catalogo), "normas": list(regra.normas)})
    return linhas
