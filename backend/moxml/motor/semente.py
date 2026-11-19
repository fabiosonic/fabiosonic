"""Conector C — XML semente por modelo/série.

Extrai CNPJ, UF, modelo, série, número, chave, emissão, ambiente, protocolo e autorizador
(verAplic) e inicializa o controle de sequência. O XML semente NÃO prova que as notas
seguintes poderão ser recuperadas: ele apenas fornece os campos fixos da chave candidata usada
na descoberta J04/562 e o ponto de partida da numeração.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from ..db.modelos import Empresa, Serie
from ..fiscal import xmlfiscal as xf
from .repositorio import Repositorio


@dataclass
class InfoSemente:
    cnpj: str
    uf: str
    modelo: str
    serie: int
    numero: int
    chave: str
    data_emissao: datetime | None
    ambiente: int
    protocolo: str | None
    autorizador: str | None
    tipo: str
    registro: str


class SementeInvalida(ValueError):
    pass


def importar_semente(repo: Repositorio, empresa: Empresa, conteudo: bytes) -> InfoSemente:
    d = xf.ler(conteudo)
    if d.tipo not in (xf.TipoXML.NFE_AUTORIZADA, xf.TipoXML.NFE_DENEGADA, xf.TipoXML.NFE_SEM_PROTOCOLO):
        raise SementeInvalida(f"XML semente deve ser NF-e/NFC-e (recebido {d.tipo})")
    if (d.cnpj_emitente or "").zfill(14) != empresa.cnpj:
        raise SementeInvalida(f"CNPJ do XML ({d.cnpj_emitente}) difere da empresa ({empresa.cnpj})")
    if d.uf != empresa.uf:
        raise SementeInvalida(f"UF do XML ({d.uf}) difere da UF da empresa ({empresa.uf})")
    graves = [p.mensagem for p in d.problemas if p.grave]
    if graves:
        raise SementeInvalida("; ".join(graves))
    reg = repo.registrar_xml(conteudo, "xml_semente", empresa)
    sr = repo.s.scalar(select(Serie).where(Serie.empresa_id == empresa.id, Serie.modelo == d.modelo,
                                           Serie.serie == d.serie, Serie.ambiente == (d.ambiente or 1)))
    assert sr is not None
    if sr.data_semente is None or (d.data_emissao and sr.data_semente and d.data_emissao > sr.data_semente):
        sr.chave_semente, sr.data_semente = d.chave, d.data_emissao
    sr.ativo = True
    repo.s.flush()
    return InfoSemente(cnpj=empresa.cnpj, uf=d.uf or "", modelo=d.modelo or "", serie=d.serie or 0, numero=d.numero or 0,
                       chave=d.chave or "", data_emissao=d.data_emissao, ambiente=d.ambiente or 1,
                       protocolo=d.protocolo, autorizador=d.ver_aplic, tipo=d.tipo.value, registro=reg.resultado)
