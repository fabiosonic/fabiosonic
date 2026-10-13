"""Monitoramento das pastas do Google Drive de cada empresa.

Para cada arquivo novo ou alterado:
  1. lê o texto (PDF/XML/TXT, Google Docs exportado);
  2. classifica (qual obrigação? qual competência? quais CNPJs?);
  3. confere se o CNPJ do documento é o da empresa dona da pasta;
  4. localiza a tarefa da agenda e dá baixa automática (no prazo / com atraso);
  5. registra o documento e um evento de auditoria.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agenda import gerar_agenda, obrigacao_aplicavel
from .classificador import Regra, classificar
from .drive.base import ArquivoDrive, DriveClient
from .models import (
    STATUS_ENTREGUE,
    STATUS_ENTREGUE_ATRASO,
    STATUS_PENDENTE,
    Documento,
    Empresa,
    EstadoSync,
    Evento,
    Obrigacao,
    Tarefa,
)

log = logging.getLogger(__name__)


@dataclass
class ResumoSync:
    empresas: int = 0
    arquivos_lidos: int = 0
    novos: int = 0
    baixas: int = 0
    nao_identificados: int = 0
    divergentes: int = 0
    erros: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _regras(obrigacoes: list[Obrigacao]) -> list[Regra]:
    return [Regra(o.codigo, o.periodicidade, o.departamento, o.reconhecimento or {}) for o in obrigacoes]


def dar_baixa(sessao: Session, tarefa: Tarefa, quando: datetime, origem: str, usuario: str = "sistema",
              observacao: str = "") -> bool:
    """Marca a tarefa como entregue. Retorna False se já estava concluída."""
    if tarefa.status != STATUS_PENDENTE:
        return False
    tarefa.status = STATUS_ENTREGUE if quando.date() <= tarefa.vencimento else STATUS_ENTREGUE_ATRASO
    tarefa.data_entrega = quando
    tarefa.origem_baixa = origem
    if observacao:
        tarefa.observacao = observacao
    sessao.add(Evento(
        tipo="baixa_" + origem, usuario=usuario, empresa_id=tarefa.empresa_id, tarefa_id=tarefa.id,
        mensagem=f"{tarefa.obrigacao.codigo} {tarefa.competencia}: {tarefa.status}",
    ))
    return True


class Monitor:
    def __init__(self, sessao: Session, drive: DriveClient):
        self.sessao = sessao
        self.drive = drive
        self.obrigacoes = list(sessao.scalars(select(Obrigacao).where(Obrigacao.ativa.is_(True))))
        self.por_codigo = {o.codigo: o for o in self.obrigacoes}
        self.regras = _regras(self.obrigacoes)
        self.empresas_por_raiz: dict[str, Empresa] = {}
        for e in sessao.scalars(select(Empresa)):
            self.empresas_por_raiz.setdefault(e.cnpj[:8], e)

    # ------------------------------------------------------------------
    def sincronizar(self, empresas: list[Empresa] | None = None, completo: bool = False) -> ResumoSync:
        resumo = ResumoSync()
        if empresas is None:
            empresas = list(self.sessao.scalars(
                select(Empresa).where(Empresa.ativa.is_(True), Empresa.drive_folder_id != "")))
        for emp in empresas:
            resumo.empresas += 1
            try:
                self.sincronizar_empresa(emp, resumo, completo)
            except Exception as exc:  # noqa: BLE001 - uma empresa com erro não interrompe as demais
                log.exception("Erro ao sincronizar %s", emp.codigo)
                resumo.erros.append(f"{emp.codigo}: {exc}")
                self._estado(emp).ultimo_erro = str(exc)[:2000]
        self.sessao.add(Evento(tipo="sync", mensagem=(
            f"{resumo.empresas} empresa(s), {resumo.arquivos_lidos} arquivo(s) lido(s), "
            f"{resumo.baixas} baixa(s), {resumo.nao_identificados} não identificado(s), "
            f"{resumo.divergentes} divergente(s)")))
        self.sessao.flush()
        return resumo

    def _estado(self, emp: Empresa) -> EstadoSync:
        est = self.sessao.scalar(select(EstadoSync).where(EstadoSync.empresa_id == emp.id))
        if est is None:
            est = EstadoSync(empresa_id=emp.id)
            self.sessao.add(est)
        return est

    def sincronizar_empresa(self, emp: Empresa, resumo: ResumoSync, completo: bool = False) -> None:
        est = self._estado(emp)
        desde = None if completo else est.ultimo_modificado
        maior = est.ultimo_modificado
        for arq in self.drive.listar_arquivos(emp.drive_folder_id, desde):
            resumo.arquivos_lidos += 1
            self.processar_arquivo(emp, arq, resumo, forcar=completo)
            if arq.modificado_em and (maior is None or arq.modificado_em > maior):
                maior = arq.modificado_em
        est.ultima_varredura = datetime.utcnow()
        est.ultimo_modificado = maior
        est.arquivos_vistos = (est.arquivos_vistos or 0) + resumo.arquivos_lidos
        est.ultimo_erro = ""

    # ------------------------------------------------------------------
    def processar_arquivo(self, emp: Empresa, arq: ArquivoDrive, resumo: ResumoSync | None = None,
                          forcar: bool = False) -> Documento:
        resumo = resumo or ResumoSync()
        doc = self.sessao.scalar(select(Documento).where(Documento.drive_file_id == arq.id))
        if not forcar and doc is not None and doc.md5 == arq.md5 and doc.modificado_drive_em == arq.modificado_em \
                and doc.empresa_id == emp.id:
            return doc  # nada mudou
        novo = doc is None
        if novo:
            doc = Documento(drive_file_id=arq.id, nome=arq.nome)
            self.sessao.add(doc)
            resumo.novos += 1
        doc.empresa_id = emp.id
        doc.nome, doc.caminho, doc.mime_type = arq.nome, arq.caminho, arq.mime_type
        doc.tamanho, doc.md5, doc.link = arq.tamanho, arq.md5, arq.link
        doc.criado_drive_em, doc.modificado_drive_em = arq.criado_em, arq.modificado_em
        doc.enviado_por = arq.enviado_por
        doc.processado_em = datetime.utcnow()

        if doc.situacao == "manual":  # classificação feita por pessoa prevalece
            return doc

        texto = self.drive.ler_texto(arq)
        res = classificar(self.regras, arq.nome, texto, arq.caminho, arq.criado_em or arq.modificado_em)
        doc.obrigacao_codigo = res.codigo or ""
        doc.competencia = res.competencia or ""
        doc.confianca = res.confianca
        doc.cnpjs_encontrados = res.cnpjs
        doc.detalhes = {
            "motivos": res.motivos,
            "candidatos": res.candidatos,
            "origem_competencia": res.origem_competencia,
            "texto_extraido": bool(texto.strip()),
        }

        # Conferência de CNPJ: documento de outro cliente salvo na pasta errada?
        if res.cnpjs and not any(c[:8] == emp.cnpj[:8] for c in res.cnpjs):
            outro = next((self.empresas_por_raiz[c[:8]] for c in res.cnpjs if c[:8] in self.empresas_por_raiz), None)
            if outro is not None:
                doc.situacao = "divergente"
                doc.tarefa_id = None
                doc.detalhes["empresa_sugerida"] = f"{outro.codigo} - {outro.razao_social}"
                resumo.divergentes += 1
                self.sessao.add(Evento(tipo="documento_divergente", empresa_id=emp.id, mensagem=(
                    f"'{arq.nome}' está na pasta de {emp.codigo} mas pertence a {outro.codigo}")))
                return doc

        if not res.identificado or not res.competencia:
            doc.situacao = "nao_identificado"
            doc.tarefa_id = None
            resumo.nao_identificados += 1
            return doc

        tarefa = self._tarefa_para(emp, self.por_codigo[res.codigo], res.competencia)
        if tarefa is None:
            doc.situacao = "sem_tarefa"
            doc.tarefa_id = None
            return doc

        doc.situacao = "classificado"
        doc.tarefa = tarefa
        if dar_baixa(self.sessao, tarefa, arq.criado_em or arq.modificado_em or datetime.utcnow(), "drive"):
            resumo.baixas += 1
        return doc

    def _tarefa_para(self, emp: Empresa, ob: Obrigacao, competencia: str) -> Tarefa | None:
        stmt = select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
                                    Tarefa.competencia == competencia)
        tarefa = self.sessao.scalar(stmt)
        if tarefa is None and obrigacao_aplicavel(emp, ob):
            gerar_agenda(self.sessao, competencia, [emp])
            tarefa = self.sessao.scalar(stmt)
        return tarefa


def classificar_manual(sessao: Session, doc: Documento, codigo: str, competencia: str, usuario: str) -> Tarefa | None:
    """Classificação feita pela equipe na tela 'Documentos não identificados'."""
    ob = sessao.scalar(select(Obrigacao).where(Obrigacao.codigo == codigo))
    if ob is None or doc.empresa is None:
        raise ValueError("obrigação ou empresa inválida")
    doc.obrigacao_codigo, doc.competencia, doc.situacao, doc.confianca = codigo, competencia, "manual", 100
    stmt = select(Tarefa).where(Tarefa.empresa_id == doc.empresa_id, Tarefa.obrigacao_id == ob.id,
                                Tarefa.competencia == competencia)
    tarefa = sessao.scalar(stmt)
    if tarefa is None:
        gerar_agenda(sessao, competencia, [doc.empresa], usuario)
        tarefa = sessao.scalar(stmt)
    if tarefa is None:  # obrigação fora do perfil: cria mesmo assim, pois a pessoa confirmou
        from .agenda import regra_efetiva
        from .calendario import calcular_vencimento

        tarefa = Tarefa(empresa_id=doc.empresa_id, obrigacao_id=ob.id, competencia=competencia,
                        vencimento=calcular_vencimento(regra_efetiva(doc.empresa, ob), competencia, ob.periodicidade))
        sessao.add(tarefa)
        sessao.flush()
    doc.tarefa = tarefa
    dar_baixa(sessao, tarefa, doc.criado_drive_em or datetime.utcnow(), "manual", usuario)
    sessao.add(Evento(tipo="classificacao_manual", usuario=usuario, empresa_id=doc.empresa_id,
                      tarefa_id=tarefa.id, mensagem=f"'{doc.nome}' classificado como {codigo} {competencia}"))
    return tarefa
