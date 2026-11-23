"""Modelos de dados do motor de importação e auditoria."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from .util import ZERO

SEVERIDADES = ["CRITICO", "ALTO", "MEDIO", "BAIXO", "INFO"]
TIPO_ROTULO = {"NFE": "NF-e", "NFCE": "NFC-e", "NFSE": "NFS-e"}
PESO_SEVERIDADE = {"CRITICO": 15, "ALTO": 7, "MEDIO": 3, "BAIXO": 1, "INFO": 0}


@dataclass
class Participante:
    documento: str = ""
    nome: str = ""
    uf: str = ""
    municipio: str = ""
    crt: str = ""  # NF-e: 1=Simples, 2=Simples excesso sublimite, 3=Normal, 4=MEI
    optante_simples: bool | None = None


@dataclass
class Item:
    numero: int
    codigo: str = ""
    descricao: str = ""
    ncm: str = ""
    cfop: str = ""
    quantidade: Decimal = ZERO
    valor_unitario: Decimal = ZERO
    valor_produto: Decimal = ZERO
    desconto: Decimal = ZERO
    cst_icms: str = ""
    csosn: str = ""
    cst_pis: str = ""
    cst_cofins: str = ""
    valor_icms: Decimal = ZERO
    valor_icms_st: Decimal = ZERO
    valor_pis: Decimal = ZERO
    valor_cofins: Decimal = ZERO
    valor_ipi: Decimal = ZERO
    tem_ibscbs: bool = False

    @property
    def valor_liquido(self) -> Decimal:
        return self.valor_produto - self.desconto


@dataclass
class DocumentoFiscal:
    tipo: str  # NFE | NFCE | NFSE
    chave: str
    numero: str
    serie: str
    data_emissao: date | None
    emitente: Participante
    destinatario: Participante
    valor_total: Decimal
    arquivo: str
    tipo_operacao: str = "saida"  # visão do emitente (tpNF): saida | entrada
    situacao: str = "autorizada"  # autorizada | sem_protocolo | cancelada | denegada
    protocolo: str = ""
    itens: list[Item] = field(default_factory=list)
    totais: dict[str, Decimal] = field(default_factory=dict)
    tem_ibscbs: bool = False
    # Campos de NFS-e
    layout: str = ""  # nfe | nacional | abrasf
    valor_servico: Decimal = ZERO
    desconto_incondicionado: Decimal = ZERO
    valor_liquido: Decimal = ZERO
    base_iss: Decimal = ZERO
    aliquota_iss: Decimal | None = None  # em %
    valor_iss: Decimal = ZERO
    iss_retido: bool = False
    retencoes: dict[str, Decimal] = field(default_factory=dict)  # irrf, pis, cofins, csll, inss
    codigo_servico: str = ""
    descricao_servico: str = ""

    @property
    def autorizada(self) -> bool:
        return self.situacao == "autorizada"

    @property
    def total_retencoes_federais(self) -> Decimal:
        return sum(self.retencoes.values(), ZERO)

    @property
    def rotulo(self) -> str:
        return f"{TIPO_ROTULO.get(self.tipo, self.tipo)} nº {self.numero}" + (f" série {self.serie}" if self.serie else "")


@dataclass
class EventoFiscal:
    chave: str
    tipo: str  # cancelamento
    data: date | None
    arquivo: str
    homologado: bool = True


@dataclass
class LancamentoBancario:
    data: date | None
    valor: Decimal  # positivo = crédito
    tipo: str
    fitid: str
    memo: str
    conta: str
    arquivo: str


@dataclass
class FolhaCompetencia:
    competencia: str  # AAAA-MM
    salarios: Decimal = ZERO
    pro_labore: Decimal = ZERO
    encargos: Decimal = ZERO  # CPP + FGTS (compõem a folha do Fator R)
    arquivo: str = ""

    @property
    def total(self) -> Decimal:
        return self.salarios + self.pro_labore + self.encargos


@dataclass
class ErroImportacao:
    arquivo: str
    motivo: str


@dataclass
class Lote:
    documentos: list[DocumentoFiscal] = field(default_factory=list)
    eventos: list[EventoFiscal] = field(default_factory=list)
    lancamentos: list[LancamentoBancario] = field(default_factory=list)
    folha: list[FolhaCompetencia] = field(default_factory=list)
    erros: list[ErroImportacao] = field(default_factory=list)
    duplicados: list[str] = field(default_factory=list)
    arquivos_lidos: int = 0


@dataclass
class Empresa:
    cnpj: str
    regime: str = "desconhecido"  # simples | mei | normal | desconhecido
    nome: str = ""
    uf: str = ""
    regime_inferido: bool = False


@dataclass
class Achado:
    codigo: str
    severidade: str
    categoria: str
    titulo: str
    descricao: str
    recomendacao: str
    base_legal: str = ""
    referencia: str = ""
    valor: Decimal | None = None
    ocorrencias: int = 1
