"""Auditoria de numeração por empresa × modelo × série × ambiente.

Uma lacuna NÃO é XML perdido nem prova de omissão: é um número sem documento conhecido.
Classificações (da mais à menos específica):
  INUTILIZADA                     faixa homologada de inutilização cobre o número
  CHAVE_CONHECIDA_XML_PENDENTE    chave conhecida (fonte oficial/semente) e XML integral ainda não obtido
  NAO_CONSTA_NA_SEFAZ             consulta oficial respondeu 217 para o número (possível rejeição,
                                  número pulado pelo emissor ou ainda não inutilizado — investigar)
  LACUNA_NAO_INVESTIGADA          sem consulta à fonte até o momento
O período (AAAA-MM) é estimado pelos documentos vizinhos; a numeração da NF-e não reinicia por ano.
"""

from __future__ import annotations

import bisect
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..db.modelos import ChaveConhecida, Documento, Inutilizacao, Lacuna, Serie

ESPECIFICIDADE = {"INUTILIZADA": 4, "CHAVE_CONHECIDA_XML_PENDENTE": 3, "NAO_CONSTA_NA_SEFAZ": 2,
                  "LACUNA_NAO_INVESTIGADA": 1}
LIMITE_LACUNAS_POR_SERIE = 20000


def marcar_nao_consta(s: Session, empresa_id: int, modelo: str, serie: int, ambiente: int, numero: int, msg: str) -> None:
    lac = s.scalar(select(Lacuna).where(Lacuna.empresa_id == empresa_id, Lacuna.modelo == modelo, Lacuna.serie == serie,
                                        Lacuna.ambiente == ambiente, Lacuna.numero == numero))
    if lac is None:
        s.add(Lacuna(empresa_id=empresa_id, modelo=modelo, serie=serie, ambiente=ambiente, numero=numero,
                     classificacao="NAO_CONSTA_NA_SEFAZ", observacao=msg[:500]))
    elif ESPECIFICIDADE.get(lac.classificacao, 0) <= ESPECIFICIDADE["NAO_CONSTA_NA_SEFAZ"]:
        lac.classificacao, lac.observacao, lac.ultima_verificacao = "NAO_CONSTA_NA_SEFAZ", msg[:500], datetime.now(UTC)


def auditar(s: Session, empresa_id: int) -> dict:
    resumo = {"series": 0, "lacunas": 0, "por_classificacao": {}}
    for sr in s.scalars(select(Serie).where(Serie.empresa_id == empresa_id)).all():
        resumo["series"] += 1
        docs = {n: dt for n, dt in s.execute(select(Documento.numero, Documento.data_emissao).where(
            Documento.empresa_id == empresa_id, Documento.modelo == sr.modelo, Documento.serie == sr.serie,
            Documento.ambiente == sr.ambiente, Documento.tipo_xml.in_(["NFE_AUTORIZADA", "NFE_DENEGADA"])))}
        pendentes = set(s.scalars(select(ChaveConhecida.numero).where(
            ChaveConhecida.empresa_id == empresa_id, ChaveConhecida.modelo == sr.modelo,
            ChaveConhecida.serie == sr.serie, ChaveConhecida.ambiente == sr.ambiente,
            ChaveConhecida.status != "RECUPERADA")))
        inuts = s.execute(select(Inutilizacao.numero_inicial, Inutilizacao.numero_final).where(
            Inutilizacao.empresa_id == empresa_id, Inutilizacao.modelo == sr.modelo,
            Inutilizacao.serie == sr.serie, Inutilizacao.ambiente == sr.ambiente)).all()
        conhecidos = set(docs) | pendentes
        if not conhecidos:
            continue
        ini = min(sr.numero_inicial_controle or min(conhecidos), min(conhecidos))
        fim = max(conhecidos)
        existentes = {lac.numero: lac for lac in s.scalars(select(Lacuna).where(
            Lacuna.empresa_id == empresa_id, Lacuna.modelo == sr.modelo, Lacuna.serie == sr.serie,
            Lacuna.ambiente == sr.ambiente)).all()}
        # Remove lacunas resolvidas (documento integral obtido)
        resolvidas = [n for n in existentes if n in docs]
        if resolvidas:
            s.execute(delete(Lacuna).where(Lacuna.empresa_id == empresa_id, Lacuna.modelo == sr.modelo,
                                           Lacuna.serie == sr.serie, Lacuna.ambiente == sr.ambiente,
                                           Lacuna.numero.in_(resolvidas)))
        ordenados = sorted((num, dt) for num, dt in docs.items() if dt)
        nums = [num for num, _ in ordenados]
        contagem = 0
        for n in range(ini, fim + 1):
            if n in docs:
                continue
            contagem += 1
            if contagem > LIMITE_LACUNAS_POR_SERIE:
                break
            if any(a <= n <= b for a, b in inuts):
                cls = "INUTILIZADA"
            elif n in pendentes:
                cls = "CHAVE_CONHECIDA_XML_PENDENTE"
            else:
                cls = "LACUNA_NAO_INVESTIGADA"
            i = bisect.bisect_left(nums, n)
            anterior = ordenados[i - 1][1] if i > 0 else (ordenados[0][1] if ordenados else None)
            periodo = f"{anterior:%Y-%m}" if anterior else None
            lac = existentes.get(n)
            if lac is None:
                s.add(Lacuna(empresa_id=empresa_id, modelo=sr.modelo, serie=sr.serie, ambiente=sr.ambiente, numero=n,
                             ano=anterior.year if anterior else None, periodo=periodo, classificacao=cls))
            else:
                if ESPECIFICIDADE[cls] >= ESPECIFICIDADE.get(lac.classificacao, 0) or cls == "INUTILIZADA":
                    lac.classificacao = cls
                lac.periodo, lac.ano = periodo, anterior.year if anterior else None
                lac.ultima_verificacao = datetime.now(UTC)
                cls = lac.classificacao
            resumo["lacunas"] += 1
            resumo["por_classificacao"][cls] = resumo["por_classificacao"].get(cls, 0) + 1
    s.flush()
    return resumo
