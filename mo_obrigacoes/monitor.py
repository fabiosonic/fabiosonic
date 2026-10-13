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
import re
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .agenda import obrigacao_aplicavel, ocorre_na_competencia, regra_efetiva
from .calendario import calcular_vencimento
from .classificador import Regra, classificar
from .drive.base import ArquivoDrive, DriveClient, ErroLeitura
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
RE_COMPETENCIA = re.compile(r"\d{4}-(0[1-9]|1[0-2])")
SITUACOES_COM_TAREFA = ("classificado", "manual")


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


def reabrir_baixa_automatica(sessao: Session, tarefa: Tarefa | None, motivo: str) -> bool:
    """Desfaz a baixa automática (origem 'drive') quando o comprovante deixou de valer
    (arquivo apagado, movido para outra empresa ou reclassificado). Baixa manual e dispensa não são tocadas."""
    if tarefa is None or tarefa.origem_baixa != "drive" or tarefa.status not in (STATUS_ENTREGUE, STATUS_ENTREGUE_ATRASO):
        return False
    sessao.flush()
    outros = sessao.scalar(select(func.count(Documento.id)).where(
        Documento.tarefa_id == tarefa.id, Documento.situacao.in_(SITUACOES_COM_TAREFA)))
    if outros:
        return False
    tarefa.status, tarefa.data_entrega, tarefa.origem_baixa = STATUS_PENDENTE, None, ""
    sessao.add(Evento(tipo="reabertura_automatica", empresa_id=tarefa.empresa_id, tarefa_id=tarefa.id,
                      mensagem=f"{tarefa.obrigacao.codigo} {tarefa.competencia}: {motivo}"))
    return True


def tarefa_da_competencia(sessao: Session, emp: Empresa, ob: Obrigacao, competencia: str,
                          mesmo_fora_do_perfil: bool = False) -> Tarefa | None:
    """Localiza a tarefa; se não existir, cria SÓ ela (nunca a agenda inteira da competência)."""
    stmt = select(Tarefa).where(Tarefa.empresa_id == emp.id, Tarefa.obrigacao_id == ob.id,
                                Tarefa.competencia == competencia)
    tarefa = sessao.scalar(stmt)
    if tarefa is not None:
        return tarefa
    if not mesmo_fora_do_perfil and not (obrigacao_aplicavel(emp, ob) and ocorre_na_competencia(ob, competencia)):
        return None
    tarefa = Tarefa(empresa_id=emp.id, obrigacao_id=ob.id, competencia=competencia,
                    vencimento=calcular_vencimento(regra_efetiva(emp, ob), competencia, ob.periodicidade))
    sessao.add(tarefa)
    sessao.flush()
    return tarefa


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
        self.sessao.commit()  # grava o que o chamador já tinha pendente: o rollback de uma empresa não pode apagá-lo
        if empresas is None:
            empresas = list(self.sessao.scalars(
                select(Empresa).where(Empresa.ativa.is_(True), Empresa.drive_folder_id != "")))
        for emp in empresas:
            resumo.empresas += 1
            try:
                self.sincronizar_empresa(emp, resumo, completo)
                self.sessao.commit()  # grava empresa a empresa: libera o banco e não perde o que já foi feito
            except Exception as exc:  # noqa: BLE001 - uma empresa com erro não interrompe as demais
                log.exception("Erro ao sincronizar %s", emp.codigo)
                self.sessao.rollback()
                resumo.erros.append(f"{emp.codigo}: {exc}")
                self._estado(emp).ultimo_erro = str(exc)[:2000]
                self.sessao.commit()
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
        """Lista a pasta inteira (sem filtro por data: arquivos movidos ou com data antiga também contam),
        processa o que é novo ou mudou e trata os arquivos que sumiram da pasta."""
        est = self._estado(emp)
        conhecidos = {d.drive_file_id: d for d in self.sessao.scalars(
            select(Documento).where(Documento.empresa_id == emp.id))}
        vistos: set[str] = set()
        maior = est.ultimo_modificado
        lidos = 0
        for arq in self.drive.listar_arquivos(emp.drive_folder_id, None):
            vistos.add(arq.id)
            if arq.modificado_em and (maior is None or arq.modificado_em > maior):
                maior = arq.modificado_em
            doc = conhecidos.get(arq.id)
            if not completo and doc is not None and self._inalterado(doc, arq):
                continue
            lidos += 1
            self.processar_arquivo(emp, arq, resumo, forcar=completo)
        resumo.arquivos_lidos += lidos
        sumidos = [d for i, d in conhecidos.items() if i not in vistos and d.situacao != "removido"]
        if not vistos and len(sumidos) > 3:
            # pasta vazia de repente (permissão retirada?): não desfaz baixas em massa
            est.ultimo_erro = f"Pasta sem nenhum arquivo, mas {len(sumidos)} documento(s) registrados: verifique o compartilhamento"
        else:
            for doc in sumidos:
                self._marcar_removido(doc)
            est.ultimo_erro = ""
        est.ultima_varredura = datetime.utcnow()
        est.ultimo_modificado = maior
        est.arquivos_vistos = len(vistos)

    @staticmethod
    def _inalterado(doc: Documento, arq: ArquivoDrive) -> bool:
        return (doc.situacao != "removido" and doc.md5 == arq.md5 and doc.modificado_drive_em == arq.modificado_em
                and doc.caminho == arq.caminho)

    def _marcar_removido(self, doc: Documento) -> None:
        tarefa = doc.tarefa
        doc.situacao, doc.tarefa = "removido", None
        self.sessao.add(Evento(tipo="documento_removido", empresa_id=doc.empresa_id,
                               mensagem=f"'{doc.nome}' não está mais na pasta do Drive"))
        reabrir_baixa_automatica(self.sessao, tarefa, f"comprovante '{doc.nome}' removido do Drive")

    # ------------------------------------------------------------------
    def processar_arquivo(self, emp: Empresa, arq: ArquivoDrive, resumo: ResumoSync | None = None,
                          forcar: bool = False) -> Documento | None:
        resumo = resumo or ResumoSync()
        doc = self.sessao.scalar(select(Documento).where(Documento.drive_file_id == arq.id))
        if not forcar and doc is not None and self._inalterado(doc, arq) and doc.empresa_id == emp.id:
            return doc  # nada mudou
        manual = doc is not None and doc.situacao == "manual"
        texto = ""
        if not manual:
            try:
                texto = self.drive.ler_texto(arq)  # lê ANTES de alterar o registro: em falha, tenta de novo depois
            except ErroLeitura as exc:
                resumo.erros.append(f"{emp.codigo}: {exc}")
                return doc
        tarefa_anterior = doc.tarefa if doc is not None else None
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

        if manual:  # classificação feita por pessoa prevalece
            return doc

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
                self._desvincular(doc, tarefa_anterior, None)
                doc.detalhes["empresa_sugerida"] = f"{outro.codigo} - {outro.razao_social}"
                resumo.divergentes += 1
                self.sessao.add(Evento(tipo="documento_divergente", empresa_id=emp.id, mensagem=(
                    f"'{arq.nome}' está na pasta de {emp.codigo} mas pertence a {outro.codigo}")))
                return doc

        # competência deduzida só pela data do arquivo é palpite: vai para revisão, sem baixa automática
        if not res.identificado or not res.competencia or res.origem_competencia == "data_arquivo":
            doc.situacao = "nao_identificado"
            self._desvincular(doc, tarefa_anterior, None)
            resumo.nao_identificados += 1
            return doc

        tarefa = tarefa_da_competencia(self.sessao, emp, self.por_codigo[res.codigo], res.competencia)
        if tarefa is None:
            doc.situacao = "sem_tarefa"
            self._desvincular(doc, tarefa_anterior, None)
            return doc

        doc.situacao = "classificado"
        self._desvincular(doc, tarefa_anterior, tarefa)
        if dar_baixa(self.sessao, tarefa, arq.criado_em or arq.modificado_em or datetime.now(), "drive"):
            resumo.baixas += 1
        return doc

    def _desvincular(self, doc: Documento, anterior: Tarefa | None, nova: Tarefa | None) -> None:
        """Liga o documento à nova tarefa e, se ele comprovava outra, desfaz aquela baixa automática."""
        doc.tarefa = nova
        if anterior is not None and anterior is not nova:
            reabrir_baixa_automatica(self.sessao, anterior, f"comprovante '{doc.nome}' foi reclassificado ou movido")


def classificar_manual(sessao: Session, doc: Documento, codigo: str, competencia: str, usuario: str) -> Tarefa | None:
    """Classificação feita pela equipe na tela 'Documentos não identificados'."""
    if not RE_COMPETENCIA.fullmatch(competencia or ""):
        raise ValueError("competência inválida (use AAAA-MM)")
    ob = sessao.scalar(select(Obrigacao).where(Obrigacao.codigo == codigo))
    if ob is None or doc.empresa is None:
        raise ValueError("obrigação ou empresa inválida")
    anterior = doc.tarefa
    doc.obrigacao_codigo, doc.competencia, doc.situacao, doc.confianca = codigo, competencia, "manual", 100
    # obrigação fora do perfil: cria mesmo assim, pois a pessoa confirmou
    tarefa = tarefa_da_competencia(sessao, doc.empresa, ob, competencia, mesmo_fora_do_perfil=True)
    doc.tarefa = tarefa
    if anterior is not None and anterior is not tarefa:
        reabrir_baixa_automatica(sessao, anterior, f"'{doc.nome}' reclassificado manualmente")
    dar_baixa(sessao, tarefa, doc.criado_drive_em or datetime.now(), "manual", usuario)
    sessao.add(Evento(tipo="classificacao_manual", usuario=usuario, empresa_id=doc.empresa_id,
                      tarefa_id=tarefa.id, mensagem=f"'{doc.nome}' classificado como {codigo} {competencia}"))
    return tarefa
