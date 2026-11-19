"""Modelo de dados (SQLAlchemy 2). PostgreSQL em produção; SQLite para testes/local."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def agora() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    type_annotation_map = {datetime: DateTime(timezone=True), dict: JSON, list: JSON}


class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(primary_key=True)
    razao_social: Mapped[str] = mapped_column(String(160))
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)
    uf: Mapped[str] = mapped_column(String(2), default="RJ")
    regime: Mapped[str | None] = mapped_column(String(40))
    ie: Mapped[str | None] = mapped_column(String(20))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    nome_pasta: Mapped[str | None] = mapped_column(String(160))  # nome da pasta em CLIENTES ATIVOS
    captura_nfe: Mapped[bool] = mapped_column(Boolean, default=True)
    captura_nfce: Mapped[bool] = mapped_column(Boolean, default=True)
    observacoes: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    certificados: Mapped[list[Certificado]] = relationship(back_populates="empresa")


class Certificado(Base):
    __tablename__ = "certificados"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    escopo: Mapped[str] = mapped_column(String(12), default="EMPRESA")  # EMPRESA | ESCRITORIO
    referencia_armazenamento_seguro: Mapped[str] = mapped_column(String(120))
    referencia_senha: Mapped[str] = mapped_column(String(120))
    titular: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    valido_de: Mapped[datetime]
    validade: Mapped[datetime]
    serial: Mapped[str] = mapped_column(String(80))
    impressao_digital: Mapped[str] = mapped_column(String(64))
    emissor: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default="VALIDO")  # VALIDO|VENCENDO|VENCIDO|REVOGADO|SUBSTITUIDO
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    autorizado_por: Mapped[str] = mapped_column(String(120))
    autorizado_em: Mapped[datetime] = mapped_column(default=agora)
    termo_autorizacao: Mapped[str] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(default=agora)

    empresa: Mapped[Empresa | None] = relationship(back_populates="certificados")


class Serie(Base):
    __tablename__ = "series"
    __table_args__ = (UniqueConstraint("empresa_id", "modelo", "serie", "ambiente", name="uq_serie"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    modelo: Mapped[str] = mapped_column(String(2))
    serie: Mapped[int] = mapped_column(Integer)
    ambiente: Mapped[int] = mapped_column(Integer, default=1)
    ultimo_numero_identificado: Mapped[int | None] = mapped_column(BigInteger)
    ultimo_numero_recuperado: Mapped[int | None] = mapped_column(BigInteger)
    numero_inicial_controle: Mapped[int | None] = mapped_column(BigInteger)
    chave_semente: Mapped[str | None] = mapped_column(String(44))
    data_semente: Mapped[datetime | None]
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    atualizado_em: Mapped[datetime] = mapped_column(default=agora, onupdate=agora)


class Documento(Base):
    __tablename__ = "documentos"
    __table_args__ = (
        UniqueConstraint("cnpj_emitente", "ambiente", "modelo", "chave", name="uq_documento"),
        Index("ix_doc_empresa_modelo_serie_numero", "empresa_id", "modelo", "serie", "numero"),
        Index("ix_doc_emissao", "data_emissao"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    chave: Mapped[str] = mapped_column(String(44), index=True)
    cnpj_emitente: Mapped[str] = mapped_column(String(14))
    ambiente: Mapped[int] = mapped_column(Integer)
    modelo: Mapped[str] = mapped_column(String(2))
    serie: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(BigInteger)
    data_emissao: Mapped[datetime | None]
    valor: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    tp_nf: Mapped[int | None] = mapped_column(Integer)
    situacao: Mapped[str] = mapped_column(String(16))  # AUTORIZADA|CANCELADA|DENEGADA|SEM_PROTOCOLO|INVALIDA
    tipo_xml: Mapped[str] = mapped_column(String(24))
    protocolo: Mapped[str | None] = mapped_column(String(20))
    origem: Mapped[str] = mapped_column(String(40))
    caminho_xml: Mapped[str | None] = mapped_column(Text)
    hash_sha256: Mapped[str | None] = mapped_column(String(64))
    assinatura_ok: Mapped[bool | None] = mapped_column(Boolean)
    problemas: Mapped[list | None] = mapped_column(JSON)
    modo: Mapped[str] = mapped_column(String(10), default="REAL")
    situacao_verificada_em: Mapped[datetime | None]
    data_captura: Mapped[datetime] = mapped_column(default=agora)
    atualizado_em: Mapped[datetime] = mapped_column(default=agora, onupdate=agora)


class Evento(Base):
    __tablename__ = "eventos"
    __table_args__ = (UniqueConstraint("chave", "tipo_evento", "sequencia", "ambiente", name="uq_evento"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    chave: Mapped[str] = mapped_column(String(44), index=True)
    tipo_evento: Mapped[str] = mapped_column(String(6))
    descricao: Mapped[str | None] = mapped_column(String(120))
    sequencia: Mapped[int] = mapped_column(Integer, default=1)
    ambiente: Mapped[int] = mapped_column(Integer, default=1)
    protocolo: Mapped[str | None] = mapped_column(String(20))
    cstat: Mapped[str | None] = mapped_column(String(3))
    data_evento: Mapped[datetime | None]
    caminho_xml: Mapped[str | None] = mapped_column(Text)
    hash_sha256: Mapped[str | None] = mapped_column(String(64))
    origem: Mapped[str] = mapped_column(String(40))
    modo: Mapped[str] = mapped_column(String(10), default="REAL")
    data_captura: Mapped[datetime] = mapped_column(default=agora)


class Inutilizacao(Base):
    __tablename__ = "inutilizacoes"
    __table_args__ = (UniqueConstraint("empresa_id", "modelo", "serie", "ambiente", "numero_inicial", "numero_final",
                                       name="uq_inut"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    modelo: Mapped[str] = mapped_column(String(2))
    serie: Mapped[int] = mapped_column(Integer)
    ambiente: Mapped[int] = mapped_column(Integer, default=1)
    ano: Mapped[int] = mapped_column(Integer)
    numero_inicial: Mapped[int] = mapped_column(BigInteger)
    numero_final: Mapped[int] = mapped_column(BigInteger)
    protocolo: Mapped[str | None] = mapped_column(String(20))
    caminho_xml: Mapped[str | None] = mapped_column(Text)
    hash_sha256: Mapped[str | None] = mapped_column(String(64))
    origem: Mapped[str] = mapped_column(String(40))
    data_captura: Mapped[datetime] = mapped_column(default=agora)


class ChaveConhecida(Base):
    """Chave obtida de fonte legítima (listagem oficial, resumo DistDFe, XML semente, cadastro manual)
    cujo XML integral ainda pode estar pendente."""

    __tablename__ = "chaves_conhecidas"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    chave: Mapped[str] = mapped_column(String(44), unique=True)
    modelo: Mapped[str] = mapped_column(String(2))
    serie: Mapped[int] = mapped_column(Integer)
    numero: Mapped[int] = mapped_column(BigInteger)
    ambiente: Mapped[int] = mapped_column(Integer, default=1)
    origem: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="PENDENTE")
    situacao_sefaz: Mapped[str | None] = mapped_column(String(24))
    cstat_situacao: Mapped[str | None] = mapped_column(String(3))
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    ultima_tentativa: Mapped[datetime | None]
    mensagem: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(default=agora)


class Execucao(Base):
    __tablename__ = "execucoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    lote: Mapped[str | None] = mapped_column(String(36), index=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"), index=True)
    modelo: Mapped[str | None] = mapped_column(String(2))
    fonte: Mapped[str | None] = mapped_column(String(40))
    gatilho: Mapped[str] = mapped_column(String(12), default="MANUAL")  # AGENDADA|MANUAL|HISTORICA
    inicio: Mapped[datetime] = mapped_column(default=agora)
    fim: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(16), default="EM_ANDAMENTO")
    quantidade: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[int] = mapped_column(Integer, default=0)
    detalhes: Mapped[dict | None] = mapped_column(JSON)
    modo: Mapped[str] = mapped_column(String(10), default="REAL")


class LogExecucao(Base):
    __tablename__ = "logs_execucao"
    id: Mapped[int] = mapped_column(primary_key=True)
    execucao_id: Mapped[int | None] = mapped_column(ForeignKey("execucoes.id"), index=True)
    momento: Mapped[datetime] = mapped_column(default=agora, index=True)
    nivel: Mapped[str] = mapped_column(String(8))
    mensagem: Mapped[str] = mapped_column(Text)


class Lacuna(Base):
    __tablename__ = "lacunas"
    __table_args__ = (UniqueConstraint("empresa_id", "modelo", "serie", "ambiente", "numero", name="uq_lacuna"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int] = mapped_column(ForeignKey("empresas.id"), index=True)
    modelo: Mapped[str] = mapped_column(String(2))
    serie: Mapped[int] = mapped_column(Integer)
    ambiente: Mapped[int] = mapped_column(Integer, default=1)
    numero: Mapped[int] = mapped_column(BigInteger)
    ano: Mapped[int | None] = mapped_column(Integer)
    periodo: Mapped[str | None] = mapped_column(String(7))  # AAAA-MM estimado pelos vizinhos
    classificacao: Mapped[str] = mapped_column(String(32))
    observacao: Mapped[str | None] = mapped_column(Text)
    ultima_verificacao: Mapped[datetime] = mapped_column(default=agora)


class Checkpoint(Base):
    __tablename__ = "checkpoints"
    __table_args__ = (UniqueConstraint("fonte", "escopo", name="uq_checkpoint"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    fonte: Mapped[str] = mapped_column(String(40))
    escopo: Mapped[str] = mapped_column(String(80))
    valor: Mapped[str] = mapped_column(Text)
    atualizado_em: Mapped[datetime] = mapped_column(default=agora, onupdate=agora)


class ArquivoDrive(Base):
    __tablename__ = "arquivos_drive"
    id: Mapped[int] = mapped_column(primary_key=True)
    caminho_local: Mapped[str] = mapped_column(Text, unique=True)
    caminho_remoto: Mapped[str] = mapped_column(Text)
    hash_md5: Mapped[str] = mapped_column(String(32))
    drive_file_id: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="PENDENTE")  # PENDENTE|CONFIRMADO|ERRO|CONFLITO
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    erro: Mapped[str | None] = mapped_column(Text)
    confirmado_em: Mapped[datetime | None]


class PastaMonitorada(Base):
    __tablename__ = "pastas_monitoradas"
    id: Mapped[int] = mapped_column(primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(ForeignKey("empresas.id"))
    caminho: Mapped[str] = mapped_column(Text, unique=True)
    recursivo: Mapped[bool] = mapped_column(Boolean, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultima_varredura: Mapped[datetime | None]


class ArquivoImportado(Base):
    __tablename__ = "arquivos_importados"
    __table_args__ = (UniqueConstraint("caminho", "hash_sha256", name="uq_arquivo_importado"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    caminho: Mapped[str] = mapped_column(Text)
    tamanho: Mapped[int] = mapped_column(BigInteger)
    mtime: Mapped[float]
    hash_sha256: Mapped[str] = mapped_column(String(64))
    resultado: Mapped[str] = mapped_column(String(40))
    importado_em: Mapped[datetime] = mapped_column(default=agora)


class ConectorConfig(Base):
    __tablename__ = "conectores"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(40), unique=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    parametros: Mapped[dict | None] = mapped_column(JSON)


class RegistroFonte(Base):
    """Auditoria de chamadas às fontes (sem conteúdo sensível)."""

    __tablename__ = "registros_fonte"
    id: Mapped[int] = mapped_column(primary_key=True)
    momento: Mapped[datetime] = mapped_column(default=agora, index=True)
    fonte: Mapped[str] = mapped_column(String(40))
    servico: Mapped[str] = mapped_column(String(60))
    cnpj: Mapped[str | None] = mapped_column(String(14))
    cstat: Mapped[str | None] = mapped_column(String(3))
    xmotivo: Mapped[str | None] = mapped_column(Text)
    erro: Mapped[str | None] = mapped_column(Text)
    duracao_ms: Mapped[int | None] = mapped_column(Integer)
    modo: Mapped[str] = mapped_column(String(10), default="REAL")


class Configuracao(Base):
    __tablename__ = "configuracoes"
    chave: Mapped[str] = mapped_column(String(80), primary_key=True)
    valor: Mapped[str | None] = mapped_column(Text)



