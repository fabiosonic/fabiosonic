"""Estruturas de dados do RPS no layout do webservice de Itaboraí/RJ (provedor CTA 2.00)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

CODIGO_IBGE_ITABORAI = "3301900"
CODIGO_PAIS_BRASIL = 1058

# TipoDeTributacao aceito pelo webservice
TRIBUTACAO = {
    "0": "Tributado no município",
    "1": "Tributado fora do município",
    "2": "Isento / imune",
    "3": "Exigibilidade suspensa",
    "4": "Simples Nacional",
    "5": "Retido no município",
}

# IssRetido
ISS_RETIDO_SIM = "1"
ISS_RETIDO_NAO = "2"

# ResponsavelRecolhimento: XSD aceita 0-2. NFS-e 3385 (08/2026, sem retenção) foi aceita com "2",
# logo 1 = tomador (ISS retido) e 2 = prestador.
RESPONSAVEL_TOMADOR = "1"
RESPONSAVEL_PRESTADOR = "2"
RESPONSAVEL = {"0": "Não se aplica", RESPONSAVEL_TOMADOR: "Tomador", RESPONSAVEL_PRESTADOR: "Prestador"}

# Tipo do tomador ("" = pessoa física não identificada)
TOMADOR_PJ = "1"
TOMADOR_PF = "2"

DUAS_CASAS = Decimal("0.01")


def dinheiro(valor) -> Decimal:
    return Decimal(str(valor or 0)).quantize(DUAS_CASAS, rounding=ROUND_HALF_UP)


@dataclass
class ItemServico:
    descricao: str
    valor_unitario: Decimal
    quantidade: int = 1

    @property
    def valor_total(self) -> Decimal:
        return dinheiro(self.valor_unitario * self.quantidade)


@dataclass
class Endereco:
    logradouro: str = ""
    numero: str = ""
    bairro: str = ""
    codigo_municipio: str = ""
    uf: str = ""
    cep: str = ""
    tipo_logradouro: str = ""
    complemento: str = ""
    codigo_pais: int = CODIGO_PAIS_BRASIL


@dataclass
class Tomador:
    cpf_cnpj: str
    razao_social: str
    endereco: Endereco = field(default_factory=Endereco)
    inscricao_municipal: str = ""
    inscricao_estadual: str = ""
    telefone: str = ""
    email: str = ""
    estrangeiro: dict = field(default_factory=dict)   # cliente do exterior: nif, sem_nif, pais_iso, pais_bacen, cidade...

    @property
    def tipo(self) -> str:
        if self.estrangeiro:
            return self.estrangeiro.get("pessoa") or TOMADOR_PJ
        digitos = "".join(c for c in self.cpf_cnpj if c.isdigit())
        if not digitos:
            return ""
        return TOMADOR_PJ if len(digitos) == 14 else TOMADOR_PF


@dataclass
class Retencoes:
    aliquota_pis: Decimal = Decimal(0)
    valor_pis: Decimal = Decimal(0)
    aliquota_cofins: Decimal = Decimal(0)
    valor_cofins: Decimal = Decimal(0)
    aliquota_csll: Decimal = Decimal(0)
    valor_csll: Decimal = Decimal(0)
    aliquota_inss: Decimal = Decimal(0)
    valor_inss: Decimal = Decimal(0)
    aliquota_ir: Decimal = Decimal(0)
    valor_ir: Decimal = Decimal(0)

    @property
    def total_federal(self) -> Decimal:
        return dinheiro(self.valor_pis + self.valor_cofins + self.valor_csll
                        + self.valor_inss + self.valor_ir)


@dataclass
class Rps:
    numero: str
    itens: list[ItemServico]
    tomador: Tomador
    item_lista_servico: str          # item da LC 116, ex.: "17.19"
    codigo_nbs: str                  # NBS, 9 dígitos
    codigo_desdobro: str             # desdobro da lista nacional, ex.: "171901"
    cnae: str                        # ex.: "6920601"
    aliquota_iss: Decimal            # em percentual, ex.: 2.00
    tipo_tributacao: str = "4"
    iss_retido: str = ISS_RETIDO_NAO
    responsavel_recolhimento: str = ""          # vazio = automático pelo IssRetido
    indicador_operacao: str = ""                # IBS/CBS - cIndOp (Tabela IBS x CBS), ex.: 100301
    classificacao_tributaria: str = ""          # IBS/CBS - cClassTrib, ex.: 200052 (17.19)
    competencia: Optional[date] = None
    data_emissao: Optional[datetime] = None
    local_prestacao: str = CODIGO_IBGE_ITABORAI
    local_recolhimento: str = CODIGO_IBGE_ITABORAI
    codigo_obra: str = ""
    codigo_tributacao_municipio: str = ""
    valor_deducoes: Decimal = Decimal(0)
    desconto_incondicionado: Decimal = Decimal(0)
    desconto_condicionado: Decimal = Decimal(0)
    retencoes: Retencoes = field(default_factory=Retencoes)
    valor_total_tributos: Decimal = Decimal(0)   # Lei 12.741/2012 (IBPT)
    observacoes: str = ""
    ind_final: str = ""                          # IBS/CBS: 1 = consumo pessoal (art. 57 LC 214); vazio = 0
    extras: dict = field(default_factory=dict)   # demais grupos da DPS nacional (regra fiscal + campos da nota)

    @property
    def responsavel(self) -> str:
        if self.responsavel_recolhimento:
            return self.responsavel_recolhimento
        return RESPONSAVEL_TOMADOR if self.iss_retido == ISS_RETIDO_SIM else RESPONSAVEL_PRESTADOR

    @property
    def valor_servicos(self) -> Decimal:
        return dinheiro(sum((i.valor_total for i in self.itens), Decimal(0)))

    @property
    def base_calculo(self) -> Decimal:
        return dinheiro(self.valor_servicos - self.valor_deducoes - self.desconto_incondicionado)

    @property
    def valor_iss(self) -> Decimal:
        return dinheiro(self.base_calculo * self.aliquota_iss / 100)

    @property
    def valor_liquido(self) -> Decimal:
        """Fórmula ABRASF: serviços - retenções federais - ISS retido - descontos."""
        iss_retido = self.valor_iss if self.iss_retido == ISS_RETIDO_SIM else Decimal(0)
        return dinheiro(self.valor_servicos - self.retencoes.total_federal - iss_retido
                        - self.desconto_incondicionado - self.desconto_condicionado)


@dataclass
class Prestador:
    cnpj: str
    inscricao_municipal: str
    chave_webservice: str
    inscricao_estadual: str = ""
    optante_simples: bool = True
    incentivo_fiscal: bool | str = False        # "1" incentivo, "2" não, "3" imunidade/isenção
