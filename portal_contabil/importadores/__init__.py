"""Importação unificada: pastas, ZIPs (inclusive aninhados), XML, OFX e CSV.

Tudo é lido em memória (sem extrair para disco, o que evita zip-slip), com
limites de quantidade e de tamanho descompactado contra zip-bomb.
"""
from __future__ import annotations

import io
import os
import zipfile
from pathlib import Path

from ..modelos import ErroImportacao, Lote
from ..util import ET, remover_namespaces
from . import folha, nfe, nfse, ofx

LIMITE_ARQUIVOS = 50_000
LIMITE_BYTES_TOTAL = 1024 * 1024 * 1024  # 1 GiB descompactado
LIMITE_BYTES_ARQUIVO = 50 * 1024 * 1024
PROFUNDIDADE_ZIP = 3
IGNORAR = ("__MACOSX/", ".DS_Store", "Thumbs.db")


class Importador:
    def __init__(self) -> None:
        self.lote = Lote()
        self._bytes = 0
        self._chaves: set[str] = set()
        self._fitids: set[tuple[str, str]] = set()

    # ------------------------------------------------------------ entrada
    def importar_caminho(self, caminho: str | os.PathLike) -> Lote:
        p = Path(caminho)
        if p.is_dir():
            for arq in sorted(p.rglob("*")):
                if arq.is_file():
                    self._ler_disco(arq, base=p)
        elif p.is_file():
            self._ler_disco(p, base=p.parent)
        else:
            self._erro(str(p), "caminho não encontrado")
        return self.lote

    def _ler_disco(self, arq: Path, base: Path) -> None:
        nome = str(arq.relative_to(base))
        if arq.stat().st_size > LIMITE_BYTES_ARQUIVO and arq.suffix.lower() != ".zip":
            self._erro(nome, "arquivo maior que o limite de 50 MB")
            return
        self.importar_bytes(nome, arq.read_bytes())

    def importar_bytes(self, nome: str, conteudo: bytes, profundidade: int = 0) -> None:
        if any(x in nome for x in IGNORAR) or Path(nome).name.startswith("."):
            return
        self.lote.arquivos_lidos += 1
        if self.lote.arquivos_lidos > LIMITE_ARQUIVOS:
            if self.lote.arquivos_lidos == LIMITE_ARQUIVOS + 1:
                self._erro(nome, f"limite de {LIMITE_ARQUIVOS} arquivos atingido; restante ignorado")
            return
        self._bytes += len(conteudo)
        if self._bytes > LIMITE_BYTES_TOTAL:
            self._erro(nome, "volume total descompactado excede 1 GiB; restante ignorado")
            return

        ext = Path(nome).suffix.lower()
        try:
            if ext == ".zip" or conteudo[:4] == b"PK\x03\x04":
                self._zip(nome, conteudo, profundidade)
            elif ext == ".ofx" or b"<OFX>" in conteudo[:4096].upper():
                self._ofx(nome, conteudo)
            elif ext == ".xml" or conteudo.lstrip()[:1] == b"<":
                self._xml(nome, conteudo)
            elif ext in (".csv", ".txt"):
                self._csv(nome, conteudo)
            else:
                self._erro(nome, f"formato '{ext or 'sem extensão'}' não suportado")
        except Exception as exc:  # noqa: BLE001 - um arquivo ruim não derruba o lote
            self._erro(nome, f"falha na leitura: {exc}")

    # ------------------------------------------------------------ formatos
    def _zip(self, nome: str, conteudo: bytes, profundidade: int) -> None:
        if profundidade >= PROFUNDIDADE_ZIP:
            self._erro(nome, "ZIP aninhado demais; ignorado")
            return
        self.lote.arquivos_lidos -= 1  # o contêiner não conta como documento
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                interno = f"{nome}/{info.filename}"
                if info.file_size > LIMITE_BYTES_ARQUIVO:
                    self._erro(interno, "arquivo maior que o limite de 50 MB")
                    continue
                if self._bytes + info.file_size > LIMITE_BYTES_TOTAL:
                    self._erro(interno, "volume total descompactado excede 1 GiB; restante ignorado")
                    return
                self.importar_bytes(interno, zf.read(info), profundidade + 1)

    def _xml(self, nome: str, conteudo: bytes) -> None:
        raiz = remover_namespaces(ET.fromstring(conteudo))
        if raiz.find(".//infNFe") is not None or raiz.tag == "infNFe":
            self._doc(nfe.ler_nfe(raiz, nome))
        elif raiz.find(".//infEvento/tpEvento") is not None:
            ev = nfe.ler_evento(raiz, nome)
            if ev:
                self.lote.eventos.append(ev)
            else:
                self._erro(nome, "evento de NF-e que não é cancelamento (ignorado)")
        elif raiz.find(".//infNFSe") is not None:
            self._doc(nfse.ler_nfse_nacional(raiz, nome))
        elif raiz.find(".//infPedReg") is not None:
            ev = nfse.ler_evento_nfse_nacional(raiz, nome)
            if ev:
                self.lote.eventos.append(ev)
            else:
                self._erro(nome, "evento de NFS-e que não é cancelamento (ignorado)")
        elif raiz.tag == "InfNfse" or raiz.find(".//InfNfse") is not None:
            for d in nfse.ler_nfse_abrasf(raiz, nome):
                self._doc(d)
        elif raiz.find(".//infCte") is not None:
            self._erro(nome, "CT-e reconhecido, mas ainda não auditado nesta versão")
        else:
            self._erro(nome, f"XML não reconhecido (raiz <{raiz.tag}>)")

    def _ofx(self, nome: str, conteudo: bytes) -> None:
        novos = 0
        for lanc in ofx.ler_ofx(conteudo, nome):
            chave = (lanc.conta, lanc.fitid or f"{lanc.data}-{lanc.valor}-{lanc.memo}")
            if chave in self._fitids:
                continue  # extratos sobrepostos repetem lançamentos
            self._fitids.add(chave)
            self.lote.lancamentos.append(lanc)
            novos += 1
        if not novos:
            self._erro(nome, "OFX sem lançamentos novos")

    def _csv(self, nome: str, conteudo: bytes) -> None:
        txt = ofx.decodificar(conteudo).lstrip("﻿")
        if not folha.eh_csv_folha(txt):
            self._erro(nome, "CSV não reconhecido (esperado: competencia;salarios;pro_labore;encargos)")
            return
        self.lote.folha.extend(folha.ler_folha(txt, nome))

    # ------------------------------------------------------------ apoio
    def _doc(self, doc) -> None:
        if doc.chave in self._chaves:
            self.lote.duplicados.append(f"{doc.rotulo} ({doc.arquivo})")
            return
        self._chaves.add(doc.chave)
        self.lote.documentos.append(doc)

    def _erro(self, arquivo: str, motivo: str) -> None:
        self.lote.erros.append(ErroImportacao(arquivo, motivo))

    def finalizar(self) -> Lote:
        """Aplica eventos de cancelamento aos documentos importados."""
        canceladas = {e.chave for e in self.lote.eventos if e.tipo == "cancelamento" and e.homologado}
        for d in self.lote.documentos:
            if d.chave in canceladas:
                d.situacao = "cancelada"
        self.lote.folha.sort(key=lambda f: f.competencia)
        self.lote.lancamentos.sort(key=lambda l: (l.data.toordinal() if l.data else 0, l.fitid))
        return self.lote


def importar(*caminhos) -> Lote:
    imp = Importador()
    for c in caminhos:
        imp.importar_caminho(c)
    return imp.finalizar()
