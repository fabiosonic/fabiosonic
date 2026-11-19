"""Exportação para o Domínio (Thomson Reuters) — módulo Escrita Fiscal.

O escritório usa o Domínio. A integração direta (API/automação da importação) NÃO foi validada,
por isso este módulo NÃO importa nada no Domínio e não marca documentos como importados. Ele prepara
um PACOTE DE IMPORTAÇÃO com os XMLs ORIGINAIS (cópia byte a byte), organizado para a rotina de
importação de XML de NF-e/NFC-e do Escrita Fiscal, que lê os arquivos de uma pasta e identifica a
empresa pelo CNPJ do emitente contido no XML.

Pacote por empresa e competência (AAAA-MM):
  <CNPJ>_<AAAA-MM>/
    IMPORTAR_DOMINIO/NFE_55/*.xml        (autorizadas, canceladas e denegadas — XML integral)
    IMPORTAR_DOMINIO/NFCE_65/*.xml
    IMPORTAR_DOMINIO/EVENTOS/*.xml       (cancelamentos, CC-e)
    IMPORTAR_DOMINIO/INUTILIZACOES/*.xml
    relatorio_documentos.csv  relatorio_cancelamentos.csv  conferencia_valores.csv  pendencias.csv
    manifesto.json  (SHA-256 de cada arquivo: comprova que o XML não foi alterado)
Cada subpasta é plana (sem níveis adicionais) para seleção direta na tela de importação.
A conferência de valores deve ser comparada com o relatório de notas do Domínio após a importação.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import extract, select

from ..db.modelos import Documento, Empresa, Evento, Inutilizacao

SUBPASTA = {"55": "NFE_55", "65": "NFCE_65"}


def _csv(caminho: Path, cab: list[str], linhas: list[list]) -> None:
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cab)
        for linha in linhas:
            w.writerow(["" if v is None else (f"{v:.2f}".replace(".", ",") if isinstance(v, Decimal) else v) for v in linha])


def exportar(app, empresa_id: int, ano: int, mes: int, destino: Path, modelos: tuple[str, ...] = ("55", "65"),  # noqa: ANN001
             zipar: bool = True) -> dict:
    raiz_xml = Path(app.cfg.pasta_xml)
    with app.sessoes() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            raise ValueError("empresa não encontrada")
        docs = s.scalars(select(Documento).where(
            Documento.empresa_id == empresa_id, Documento.modelo.in_(modelos),
            extract("year", Documento.data_emissao) == ano, extract("month", Documento.data_emissao) == mes)
            .order_by(Documento.modelo, Documento.serie, Documento.numero)).all()
        chaves = [d.chave for d in docs]
        eventos = s.scalars(select(Evento).where(Evento.chave.in_(chaves))).all() if chaves else []
        inuts = s.scalars(select(Inutilizacao).where(Inutilizacao.empresa_id == empresa_id,
                                                     Inutilizacao.ano == ano)).all()
    pasta = Path(destino) / f"{emp.cnpj}_{ano:04d}-{mes:02d}"
    if pasta.exists():
        shutil.rmtree(pasta)
    imp = pasta / "IMPORTAR_DOMINIO"
    imp.mkdir(parents=True)
    manifesto: list[dict] = []
    pendencias: list[list] = []

    def copiar(rel: str | None, sub: str, ref: str) -> bool:
        if not rel or not (raiz_xml / rel).exists():
            pendencias.append([ref, "arquivo XML ausente no armazenamento"])
            return False
        origem = raiz_xml / rel
        alvo = imp / sub / origem.name
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, alvo)  # cópia byte a byte: XML fiscal inalterado
        manifesto.append({"arquivo": alvo.relative_to(pasta).as_posix(),
                          "sha256": hashlib.sha256(alvo.read_bytes()).hexdigest()})
        return True

    linhas_docs, linhas_canc = [], []
    totais: dict[tuple[str, str], list] = {}
    for d in docs:
        if d.tipo_xml not in ("NFE_AUTORIZADA", "NFE_DENEGADA"):
            pendencias.append([d.chave, f"sem XML integral autorizado ({d.tipo_xml})"])
            continue
        if not copiar(d.caminho_xml, SUBPASTA[d.modelo], d.chave):
            continue
        linhas_docs.append([d.modelo, d.serie, d.numero, d.chave,
                            d.data_emissao.strftime("%d/%m/%Y %H:%M") if d.data_emissao else "",
                            d.valor, d.situacao, d.protocolo, d.origem, d.hash_sha256])
        t = totais.setdefault((d.modelo, d.situacao), [0, Decimal("0")])
        t[0] += 1
        t[1] += d.valor or Decimal("0")
    for e in eventos:
        copiar(e.caminho_xml, "EVENTOS", f"{e.chave}/{e.tipo_evento}")
        if e.tipo_evento in ("110111", "110112"):
            linhas_canc.append([e.chave, e.tipo_evento, e.descricao, e.sequencia, e.protocolo,
                                e.data_evento.strftime("%d/%m/%Y %H:%M") if e.data_evento else ""])
    for i in inuts:
        copiar(i.caminho_xml, "INUTILIZACOES", f"inut {i.serie}/{i.numero_inicial}-{i.numero_final}")
    _csv(pasta / "relatorio_documentos.csv",
         ["modelo", "serie", "numero", "chave", "emissao", "valor", "situacao", "protocolo", "origem", "sha256"], linhas_docs)
    _csv(pasta / "relatorio_cancelamentos.csv", ["chave", "tp_evento", "descricao", "sequencia", "protocolo", "data"],
         linhas_canc)
    _csv(pasta / "conferencia_valores.csv", ["modelo", "situacao", "quantidade", "valor_total"],
         [[m, sit, q, v] for (m, sit), (q, v) in sorted(totais.items())])
    _csv(pasta / "pendencias.csv", ["referencia", "motivo"], pendencias)
    info = {"sistema_destino": "Domínio — Escrita Fiscal (importação de XML)", "empresa": emp.razao_social,
            "cnpj": emp.cnpj, "competencia": f"{ano:04d}-{mes:02d}", "gerado_em": datetime.now(UTC).isoformat(),
            "modo": app.modo, "documentos": len(linhas_docs), "cancelamentos": len(linhas_canc),
            "arquivos": manifesto, "pendencias": len(pendencias),
            "observacao": "Pacote para importação pelo operador no Domínio. Importação direta não validada; "
                          "nenhum documento é considerado importado por este sistema."}
    (pasta / "manifesto.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    resultado = {"pasta": str(pasta), "documentos": len(linhas_docs), "cancelamentos": len(linhas_canc),
                 "pendencias": len(pendencias)}
    if zipar:
        zp = pasta.with_suffix(".zip")
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(pasta.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(pasta.parent).as_posix())
        resultado["zip"] = str(zp)
    return resultado


def exportar_lote(app, ano: int, mes: int, destino: Path, empresas: list[int] | None = None) -> list[dict]:  # noqa: ANN001
    with app.sessoes() as s:
        q = select(Empresa.id).where(Empresa.ativo.is_(True))
        if empresas:
            q = q.where(Empresa.id.in_(empresas))
        ids = list(s.scalars(q))
    return [{"empresa_id": i, **exportar(app, i, ano, mes, destino)} for i in ids]
