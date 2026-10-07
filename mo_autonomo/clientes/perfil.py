"""Perfil fiscal do cliente NA DATA do documento.

Fontes: cadastro do Domínio (regime atual, UF, município IBGE, IE) + Dados Abertos do CNPJ
(CNAE, natureza jurídica, situação, Simples/MEI com datas) + documentos (CRT, prestador).
Divergência entre fontes = pendência (regra 2). Presumido/Real só pelo Domínio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from ..normas.catalogo import Catalogo
from .cadastro import Empresa

NORMA_DICIONARIO = "DICIONARIO_DADOS_ABERTOS_CNPJ"


@dataclass
class Pendencia:
    codigo: str
    mensagem: str
    cnpj: str | None = None
    referencia: str | None = None
    bloqueia: bool = True

    def como_dict(self):
        return {"codigo": self.codigo, "mensagem": self.mensagem, "cnpj": self.cnpj,
                "referencia": self.referencia, "bloqueia": self.bloqueia}


@dataclass
class PerfilFiscal:
    cnpj: str
    codigo_dominio: str
    apelido: str
    regime: str | None
    regime_fonte: str
    data_ref: date
    cnaes: list[str] = field(default_factory=list)
    natureza_juridica: str | None = None
    uf: str | None = None
    municipio: str | None = None
    situacao_ativa: bool | None = None
    pendencias: list[Pendencia] = field(default_factory=list)
    fontes: dict = field(default_factory=dict)

    def como_dict(self):
        return {
            "cnpj": self.cnpj, "codigo_dominio": self.codigo_dominio, "apelido": self.apelido,
            "regime": self.regime, "regime_fonte": self.regime_fonte, "data_ref": self.data_ref,
            "cnaes": self.cnaes, "natureza_juridica": self.natureza_juridica, "uf": self.uf,
            "municipio": self.municipio, "situacao_ativa": self.situacao_ativa,
            "pendencias": [p.como_dict() for p in self.pendencias], "fontes": self.fontes,
        }


def _dentro(d: date, inicio: date | None, fim: date | None) -> bool:
    if inicio is None:
        return False
    if d < inicio:
        return False
    return fim is None or d <= fim


def _optante(simples: dict | None, d: date, sim: str | None, prefixo: str) -> bool | None:
    """True/False se a RFB permite afirmar; None se não dá (sem dado ou dicionário não conferido)."""
    if simples is None or sim is None:
        return None
    ini, fim = simples.get(f"data_opcao_{prefixo}"), simples.get(f"data_exclusao_{prefixo}")
    if ini is not None:
        return _dentro(d, ini, fim)
    # sem data de opção: só a flag atual, válida apenas para afirmar "não optante"
    flag = simples.get(f"opcao_{prefixo}")
    if flag and flag != sim:
        return False
    return None


def montar_perfil(empresa: Empresa, receita: dict | None, catalogo: Catalogo, data_ref: date) -> PerfilFiscal:
    pend: list[Pendencia] = []
    fontes: dict = {"dominio": True, "receita": receita is not None}
    est = (receita or {}).get("estabelecimento") or {}
    emp = (receita or {}).get("empresa") or {}
    simp = (receita or {}).get("simples")

    sim = catalogo.parametro(NORMA_DICIONARIO, "valor_opcao_sim", data_ref)
    cod_ativa = catalogo.parametro(NORMA_DICIONARIO, "codigo_situacao_ativa", data_ref)
    if receita is not None and (sim is None or cod_ativa is None):
        pend.append(Pendencia("DICIONARIO_RFB_NAO_CONFERIDO",
                              f"Norma {NORMA_DICIONARIO} não conferida: códigos de situação/Simples da RFB não usados.",
                              empresa.cnpj, bloqueia=False))
    if receita is None:
        pend.append(Pendencia("SEM_DADOS_RFB", "CNPJ não encontrado nos dados abertos carregados.",
                              empresa.cnpj, bloqueia=False))

    opt_simples = _optante(simp, data_ref, sim, "simples")
    opt_mei = _optante(simp, data_ref, sim, "mei")
    dom = empresa.regime_dominio

    regime, fonte = None, "INDEFINIDO"
    if opt_mei:
        regime, fonte = "MEI", "RFB"
    elif opt_simples:
        regime, fonte = "SIMPLES", "RFB"
    if regime and dom and dom != regime:
        pend.append(Pendencia("REGIME_DIVERGENTE",
                              f"RFB indica {regime} em {data_ref:%d/%m/%Y}; cadastro do Domínio diz {dom}.",
                              empresa.cnpj))
        regime, fonte = None, "DIVERGENTE"
    elif regime is None:
        if opt_simples is False and dom in ("SIMPLES", "MEI") and opt_mei is not True:
            pend.append(Pendencia("REGIME_DIVERGENTE",
                                  f"RFB indica NÃO optante em {data_ref:%d/%m/%Y}; cadastro do Domínio diz {dom}.",
                                  empresa.cnpj))
            fonte = "DIVERGENTE"
        elif dom:
            regime, fonte = dom, "DOMINIO"
        else:
            pend.append(Pendencia("REGIME_DESCONHECIDO",
                                  "Regime não informado no cadastro do Domínio e não determinável pela RFB.",
                                  empresa.cnpj))
    elif regime and not dom:
        fonte = "RFB"

    situacao = None
    if est.get("data_inicio") and data_ref < est["data_inicio"]:
        pend.append(Pendencia("ANTERIOR_A_ABERTURA",
                              f"Data {data_ref:%d/%m/%Y} anterior ao início de atividade na RFB "
                              f"({est['data_inicio']:%d/%m/%Y}).", empresa.cnpj))
    elif est.get("data_situacao") and data_ref < est["data_situacao"]:
        # a RFB só informa a situação ATUAL (desde data_situacao): antes disso ela é desconhecida
        pend.append(Pendencia("SITUACAO_NA_DATA_DESCONHECIDA",
                              f"Situação cadastral atual vale desde {est['data_situacao']:%d/%m/%Y}; "
                              f"em {data_ref:%d/%m/%Y} não é conhecida pelos dados abertos.", empresa.cnpj, bloqueia=False))
    elif cod_ativa is not None and est.get("situacao_cadastral"):
        situacao = est["situacao_cadastral"] == str(cod_ativa)
        if not situacao:
            pend.append(Pendencia("SITUACAO_CADASTRAL",
                                  f"Situação cadastral na RFB diferente de ativa (código {est['situacao_cadastral']}).",
                                  empresa.cnpj))

    uf = empresa.uf
    if est.get("uf") and empresa.uf and est["uf"] != empresa.uf:
        pend.append(Pendencia("UF_DIVERGENTE", f"UF na RFB {est['uf']} × Domínio {empresa.uf}.", empresa.cnpj))
    uf = uf or est.get("uf") or None
    cnaes = [c for c in [est.get("cnae_principal")] + list(est.get("cnaes_secundarias") or []) if c]
    if not cnaes:
        pend.append(Pendencia("SEM_CNAE", "CNAE não disponível (carregue os dados abertos da RFB).",
                              empresa.cnpj, bloqueia=False))

    return PerfilFiscal(
        cnpj=empresa.cnpj, codigo_dominio=empresa.codigo_dominio, apelido=empresa.apelido,
        regime=regime, regime_fonte=fonte, data_ref=data_ref, cnaes=cnaes,
        natureza_juridica=emp.get("natureza_juridica") or None, uf=uf,
        municipio=empresa.municipio_ibge, situacao_ativa=situacao, pendencias=pend, fontes=fontes,
    )


class Perfis:
    """Cache de perfis por (cnpj, data)."""

    def __init__(self, carteira, receita: dict[str, dict], catalogo: Catalogo):
        self.carteira, self.receita, self.catalogo = carteira, receita or {}, catalogo
        self._cache: dict = {}

    def em(self, cnpj: str, d: date) -> PerfilFiscal | None:
        emp = self.carteira.get(cnpj)
        if emp is None:
            return None
        k = (emp.cnpj, d)
        if k not in self._cache:
            self._cache[k] = montar_perfil(emp, self.receita.get(emp.cnpj), self.catalogo, d)
        return self._cache[k]
