"""Modelo de dados.

Visão geral:
    Empresa ──< Tarefa >── Obrigacao        (agenda: empresa × obrigação × competência)
    Empresa ──< Documento >── Tarefa        (arquivo do Google Drive que comprova a tarefa)
    Responsavel ──< Empresa (por departamento)
    Evento                                   (trilha de auditoria)
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# ----------------------------------------------------------------------------
# Domínios
# ----------------------------------------------------------------------------
REGIMES = {
    "MEI": "MEI - Microempreendedor Individual",
    "SIMPLES": "Simples Nacional",
    "PRESUMIDO": "Lucro Presumido",
    "REAL": "Lucro Real",
    "IMUNE_ISENTA": "Imune / Isenta (3º setor)",
}

DEPARTAMENTOS = {
    "FISCAL": "Fiscal / Tributário",
    "CONTABIL": "Contábil",
    "PESSOAL": "Departamento Pessoal",
    "SOCIETARIO": "Societário / Legalização",
    "CLIENTE": "Documentos do Cliente",
}

# Situação de uma tarefa da agenda
STATUS_PENDENTE = "pendente"
STATUS_ENTREGUE = "entregue"            # comprovante encontrado dentro do prazo
STATUS_ENTREGUE_ATRASO = "entregue_atraso"
STATUS_DISPENSADA = "dispensada"        # sem movimento / não se aplica no mês
STATUS_LABELS = {
    STATUS_PENDENTE: "Pendente",
    STATUS_ENTREGUE: "Entregue no prazo",
    STATUS_ENTREGUE_ATRASO: "Entregue com atraso",
    STATUS_DISPENSADA: "Dispensada",
}
STATUS_CONCLUIDOS = {STATUS_ENTREGUE, STATUS_ENTREGUE_ATRASO, STATUS_DISPENSADA}

# Sentido do documento
TIPO_ENTREGA = "entrega"          # escritório produz/entrega (declaração, guia, folha)
TIPO_RECEBIMENTO = "recebimento"  # cliente deposita (extrato, XML, ponto)


class Responsavel(Base):
    __tablename__ = "responsaveis"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200), default="")
    departamento: Mapped[str] = mapped_column(String(20), default="FISCAL")
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Responsavel {self.nome}>"


class Empresa(Base):
    __tablename__ = "empresas"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    razao_social: Mapped[str] = mapped_column(String(200))
    nome_fantasia: Mapped[str] = mapped_column(String(200), default="")
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)  # somente dígitos
    regime: Mapped[str] = mapped_column(String(20), default="SIMPLES")
    uf: Mapped[str] = mapped_column(String(2), default="")
    municipio: Mapped[str] = mapped_column(String(120), default="")

    # Perfil usado pelas regras de aplicabilidade das obrigações
    comercio: Mapped[bool] = mapped_column(Boolean, default=False)   # contribuinte ICMS
    industria: Mapped[bool] = mapped_column(Boolean, default=False)  # contribuinte IPI
    servicos: Mapped[bool] = mapped_column(Boolean, default=True)    # contribuinte ISS
    possui_funcionarios: Mapped[bool] = mapped_column(Boolean, default=False)
    possui_prolabore: Mapped[bool] = mapped_column(Boolean, default=True)
    retem_tributos: Mapped[bool] = mapped_column(Boolean, default=False)  # EFD-Reinf
    area_saude: Mapped[bool] = mapped_column(Boolean, default=False)      # DMED
    atividade_imobiliaria: Mapped[bool] = mapped_column(Boolean, default=False)  # DIMOB

    email_cliente: Mapped[str] = mapped_column(String(200), default="")
    whatsapp_cliente: Mapped[str] = mapped_column(String(30), default="")

    drive_folder_id: Mapped[str] = mapped_column(String(200), default="")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)

    # Exceções da carteira: {"EFD_ICMS_IPI": {"dia": 25}, "DEFIS": {"ignorar": true}}
    personalizacoes: Mapped[dict] = mapped_column(JSON, default=dict)

    resp_fiscal_id: Mapped[int | None] = mapped_column(ForeignKey("responsaveis.id"), nullable=True)
    resp_contabil_id: Mapped[int | None] = mapped_column(ForeignKey("responsaveis.id"), nullable=True)
    resp_pessoal_id: Mapped[int | None] = mapped_column(ForeignKey("responsaveis.id"), nullable=True)

    resp_fiscal: Mapped[Responsavel | None] = relationship(foreign_keys=[resp_fiscal_id])
    resp_contabil: Mapped[Responsavel | None] = relationship(foreign_keys=[resp_contabil_id])
    resp_pessoal: Mapped[Responsavel | None] = relationship(foreign_keys=[resp_pessoal_id])

    tarefas: Mapped[list["Tarefa"]] = relationship(back_populates="empresa", cascade="all, delete-orphan")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="empresa")

    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    @property
    def cnpj_formatado(self) -> str:
        c = self.cnpj
        if len(c) == 14:
            return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
        if len(c) == 11:
            return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}"
        return c

    @property
    def nome_exibicao(self) -> str:
        return self.nome_fantasia or self.razao_social

    def responsavel_do(self, departamento: str) -> Responsavel | None:
        return {
            "FISCAL": self.resp_fiscal,
            "CONTABIL": self.resp_contabil,
            "PESSOAL": self.resp_pessoal,
            "CLIENTE": self.resp_contabil or self.resp_fiscal,
        }.get(departamento)


class Obrigacao(Base):
    """Catálogo de obrigações/documentos monitorados (ver catalogo.py)."""

    __tablename__ = "obrigacoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(40), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    descricao: Mapped[str] = mapped_column(Text, default="")
    base_legal: Mapped[str] = mapped_column(String(300), default="")
    departamento: Mapped[str] = mapped_column(String(20))
    tipo: Mapped[str] = mapped_column(String(20), default=TIPO_ENTREGA)
    periodicidade: Mapped[str] = mapped_column(String(20), default="mensal")  # mensal|trimestral|anual
    # Regra de vencimento (ver calendario.calcular_vencimento)
    regra_vencimento: Mapped[dict] = mapped_column(JSON, default=dict)
    # Regras de aplicabilidade: {"regimes": [...], "exige": ["possui_funcionarios"], ...}
    aplicabilidade: Mapped[dict] = mapped_column(JSON, default=dict)
    # Regras de reconhecimento de arquivo: {"nome": [regex], "conteudo": [regex], "extensoes": [...]}
    reconhecimento: Mapped[dict] = mapped_column(JSON, default=dict)
    multa_referencia: Mapped[str] = mapped_column(String(300), default="")
    # Vigência (AAAA-MM, inclusive). Vazio = sem limite. Ex.: PIS/COFINS termina em 2026-12 (LC 214/2025)
    vigente_desde: Mapped[str] = mapped_column(String(7), default="")
    vigente_ate: Mapped[str] = mapped_column(String(7), default="")
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)


class Tarefa(Base):
    """Uma ocorrência da obrigação para uma empresa em uma competência."""

    __tablename__ = "tarefas"
    __table_args__ = (UniqueConstraint("empresa_id", "obrigacao_id", "competencia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"))
    obrigacao_id: Mapped[int] = mapped_column(ForeignKey("obrigacoes.id"))
    competencia: Mapped[str] = mapped_column(String(7))  # AAAA-MM (anual => AAAA-12, trimestral => último mês)
    vencimento: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_PENDENTE)
    data_entrega: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    origem_baixa: Mapped[str] = mapped_column(String(20), default="")  # drive|manual
    observacao: Mapped[str] = mapped_column(Text, default="")
    alertas_enviados: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_alerta_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    atualizado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    empresa: Mapped[Empresa] = relationship(back_populates="tarefas")
    obrigacao: Mapped[Obrigacao] = relationship()
    documentos: Mapped[list["Documento"]] = relationship(back_populates="tarefa")

    @property
    def concluida(self) -> bool:
        return self.status in STATUS_CONCLUIDOS

    def situacao(self, hoje: date | None = None, dias_alerta: int = 3) -> str:
        """Situação visual: entregue, atrasada, vence_hoje, a_vencer, no_prazo, dispensada..."""
        hoje = hoje or date.today()
        if self.concluida:
            return self.status
        if self.vencimento < hoje:
            return "atrasada"
        if self.vencimento == hoje:
            return "vence_hoje"
        if (self.vencimento - hoje).days <= dias_alerta:
            return "a_vencer"
        return "no_prazo"


class Documento(Base):
    """Arquivo encontrado nas pastas do Google Drive de uma empresa."""

    __tablename__ = "documentos"

    id: Mapped[int] = mapped_column(primary_key=True)
    drive_file_id: Mapped[str] = mapped_column(String(200), unique=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), nullable=True)
    tarefa_id: Mapped[int | None] = mapped_column(ForeignKey("tarefas.id"), nullable=True)
    nome: Mapped[str] = mapped_column(String(400))
    caminho: Mapped[str] = mapped_column(String(800), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="")
    tamanho: Mapped[int] = mapped_column(Integer, default=0)
    md5: Mapped[str] = mapped_column(String(64), default="")
    link: Mapped[str] = mapped_column(String(500), default="")
    criado_drive_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    modificado_drive_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    enviado_por: Mapped[str] = mapped_column(String(200), default="")

    # Resultado da classificação automática
    obrigacao_codigo: Mapped[str] = mapped_column(String(40), default="")
    competencia: Mapped[str] = mapped_column(String(7), default="")
    confianca: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    cnpjs_encontrados: Mapped[list] = mapped_column(JSON, default=list)
    detalhes: Mapped[dict] = mapped_column(JSON, default=dict)
    # classificado | nao_identificado | divergente (CNPJ de outra empresa) | sem_tarefa | manual
    situacao: Mapped[str] = mapped_column(String(30), default="nao_identificado")

    processado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    empresa: Mapped[Empresa | None] = relationship(back_populates="documentos")
    tarefa: Mapped[Tarefa | None] = relationship(back_populates="documentos")


class Evento(Base):
    """Trilha de auditoria (quem fez o quê, quando)."""

    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    momento: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    tipo: Mapped[str] = mapped_column(String(40))
    usuario: Mapped[str] = mapped_column(String(120), default="sistema")
    empresa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tarefa_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mensagem: Mapped[str] = mapped_column(Text, default="")


class EstadoSync(Base):
    """Guarda o ponto de parada da última varredura por empresa."""

    __tablename__ = "estado_sync"

    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(Integer, unique=True)
    ultima_varredura: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ultimo_modificado: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    arquivos_vistos: Mapped[int] = mapped_column(Integer, default=0)
    ultimo_erro: Mapped[str] = mapped_column(Text, default="")
