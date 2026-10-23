"""Banco de dados SQLite do Studio Contábil. Datas guardadas no horário local, sem fuso."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from pydantic import NaiveDatetime
from sqlmodel import Field, Session, SQLModel, create_engine, select

from avatar_contabil import config


def agora() -> datetime:
    return datetime.now().replace(microsecond=0)


class Usuario(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    email: str = Field(index=True, unique=True)
    crc: str = ""
    papel: str = "redator"  # admin | revisor | redator
    senha_hash: str


class Perfil(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    nome: str
    tipo: str = "cliente"  # escritorio | cliente
    site: str = ""
    instagram: str = ""
    whatsapp: str = ""  # número com DDI/DDD, só dígitos
    crc_responsavel: str = ""
    cor_primaria: str = "#0B3D5C"
    cor_secundaria: str = "#F4F6F8"
    cor_destaque: str = "#FFB703"
    logo: str = ""  # caminho em data/
    tom: str = "Profissional, próximo e didático."
    publico: str = "Donos de pequenas e médias empresas."
    servicos: str = ""
    nunca_dizer: str = ""  # um termo por linha
    postiz_canais: str = "{}"  # {"instagram": "<integration id>", ...}
    heygen_avatar_id: str = ""
    elevenlabs_voice_id: str = ""
    consentimento_arquivo: str = ""
    consentimento_em: Optional[NaiveDatetime] = None
    # Piloto automático
    auto_ativo: bool = False
    auto_dias: str = "0,2,4"  # dias da semana (0 = segunda ... 6 = domingo)
    auto_horario: str = "11:30"
    auto_formatos: str = "carrossel,post"
    auto_antecedencia: int = 7  # dias de antecedência com que os posts são criados
    # Instagram (API de publicação de conteúdo)
    ig_user_id: str = ""
    ig_token: str = ""

    @property
    def avatar_liberado(self) -> bool:
        return bool(self.consentimento_arquivo and self.consentimento_em)

    def termos_proibidos(self) -> list[str]:
        return [t.strip() for t in self.nunca_dizer.splitlines() if t.strip()]

    @property
    def instagram_conectado(self) -> bool:
        return bool(self.ig_user_id and self.ig_token)

    def dias_auto(self) -> list[int]:
        return sorted({int(d) for d in self.auto_dias.split(",") if d.strip().isdigit() and 0 <= int(d) <= 6})

    def formatos_auto(self) -> list[str]:
        return [f for f in (x.strip() for x in self.auto_formatos.split(",")) if f in ("post", "carrossel")] or ["carrossel"]

    def canais(self) -> dict[str, str]:
        return {k: v for k, v in json.loads(self.postiz_canais or "{}").items() if v}


class Pauta(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    origem: str  # noticia | fiscal | ideia
    titulo: str
    resumo: str = ""
    link: str = ""
    data_ref: Optional[str] = None  # data da notícia ou do vencimento (AAAA-MM-DD)
    chave: str = Field(default="", index=True)  # evita duplicar
    arquivada: bool = False
    criada_em: NaiveDatetime = Field(default_factory=agora)


class Conteudo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    perfil_id: int = Field(foreign_key="perfil.id")
    pauta_id: Optional[int] = Field(default=None, foreign_key="pauta.id")
    formato: str  # post | carrossel | video
    estilo: str = ""
    status: str = "rascunho"
    dados: str = "{}"  # JSON gerado pela IA (editável)
    nota: str = "{}"
    alertas: str = "[]"
    revisor: str = ""
    aprovado_cliente_em: Optional[NaiveDatetime] = None
    comentario_cliente: str = ""
    token_cliente: str = Field(default="", index=True)
    token_expira: Optional[NaiveDatetime] = None
    agendado_para: Optional[NaiveDatetime] = None
    arquivos: str = "[]"
    publicacao: str = "{}"
    midia_token: str = Field(default="", index=True)  # dá acesso público às imagens finais (o Instagram baixa por URL)
    automatico: bool = False
    erro: str = ""
    criado_em: NaiveDatetime = Field(default_factory=agora)
    atualizado_em: NaiveDatetime = Field(default_factory=agora)

    def j(self, campo: str):
        return json.loads(getattr(self, campo) or "null")

    def guardar(self, campo: str, valor) -> None:
        setattr(self, campo, json.dumps(valor, ensure_ascii=False))


class Evento(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    conteudo_id: Optional[int] = Field(default=None, foreign_key="conteudo.id", index=True)
    quando: NaiveDatetime = Field(default_factory=agora)
    usuario: str = ""
    acao: str
    detalhe: str = ""


_engine = None


def engine():
    global _engine
    if _engine is None:
        caminho = config.DADOS / "studio.db"
        caminho.parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{caminho}", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(_engine)
        _migrar(_engine)
    return _engine


def _migrar(eng) -> None:
    """Acrescenta colunas novas em bancos criados por versões anteriores."""
    from sqlalchemy import inspect, text

    insp = inspect(eng)
    with eng.begin() as con:
        for tabela in SQLModel.metadata.sorted_tables:
            existentes = {c["name"] for c in insp.get_columns(tabela.name)}
            for coluna in tabela.columns:
                if coluna.name in existentes:
                    continue
                tipo = coluna.type.compile(dialect=eng.dialect)
                padrao = coluna.default.arg if coluna.default is not None and not callable(coluna.default.arg) else None
                sql_padrao = "" if padrao is None else f" DEFAULT {padrao!r}" if isinstance(padrao, str) else f" DEFAULT {int(padrao)}"
                con.execute(text(f'ALTER TABLE "{tabela.name}" ADD COLUMN "{coluna.name}" {tipo}{sql_padrao}'))


def reiniciar_engine() -> None:
    """Usado nos testes, ao trocar a pasta de dados."""
    global _engine
    _engine = None


def sessao() -> Session:
    return Session(engine(), expire_on_commit=False)


def registrar(s: Session, conteudo_id: Optional[int], usuario: str, acao: str, detalhe: str = "") -> None:
    s.add(Evento(conteudo_id=conteudo_id, usuario=usuario, acao=acao, detalhe=detalhe))


__all__ = ["Usuario", "Perfil", "Pauta", "Conteudo", "Evento", "sessao", "select", "registrar", "agora"]
