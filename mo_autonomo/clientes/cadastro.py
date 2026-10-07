"""Cadastro de empresas da carteira (gerado da exportação do cadastro do Domínio).

Formato `empresas.csv` (separador `;`, UTF-8):
codigo_dominio;apelido;cnpj;regime;codigo_apuracao;uf;municipio_ibge;ie;ativa
Regime aceito: SIMPLES | MEI | PRESUMIDO | REAL | IMUNE | ISENTA | (vazio = desconhecido -> pendência)
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from ..util.documentos_id import cnpj_valido, so_digitos

REGIMES = ("SIMPLES", "MEI", "PRESUMIDO", "REAL", "IMUNE", "ISENTA")


class CadastroInvalido(ValueError):
    pass


@dataclass
class Empresa:
    codigo_dominio: str
    apelido: str
    cnpj: str
    regime_dominio: str | None
    codigo_apuracao: str | None = None
    uf: str | None = None
    municipio_ibge: str | None = None
    ie: str | None = None
    ativa: bool = True

    @property
    def pasta(self) -> str:
        """Nome da pasta no padrão <Código-Apelido> das rotinas automáticas."""
        return f"{self.codigo_dominio}-{self.apelido}"


class Carteira:
    def __init__(self, empresas: list[Empresa]):
        self.por_cnpj: dict[str, Empresa] = {}
        for e in empresas:
            if e.cnpj in self.por_cnpj:
                raise CadastroInvalido(f"CNPJ duplicado no cadastro: {e.cnpj}")
            self.por_cnpj[e.cnpj] = e

    def __len__(self):
        return len(self.por_cnpj)

    def __iter__(self):
        return iter(self.por_cnpj.values())

    def get(self, cnpj: str | None) -> Empresa | None:
        return self.por_cnpj.get(so_digitos(cnpj))

    @classmethod
    def carregar(cls, caminho: Path | str) -> "Carteira":
        empresas, erros = [], []
        with open(caminho, encoding="utf-8-sig", newline="") as f:
            for n, linha in enumerate(csv.DictReader(f, delimiter=";"), start=2):
                cnpj = so_digitos(linha.get("cnpj"))
                if not cnpj_valido(cnpj):
                    erros.append(f"linha {n}: CNPJ inválido {linha.get('cnpj')!r}")
                    continue
                regime = (linha.get("regime") or "").strip().upper() or None
                if regime and regime not in REGIMES:
                    erros.append(f"linha {n}: regime desconhecido {regime!r}")
                    continue
                codigo = (linha.get("codigo_dominio") or "").strip()
                apelido = (linha.get("apelido") or "").strip()
                if not codigo or not apelido:
                    erros.append(f"linha {n}: código/apelido do Domínio vazio")
                    continue
                empresas.append(Empresa(
                    codigo_dominio=codigo, apelido=apelido, cnpj=cnpj, regime_dominio=regime,
                    codigo_apuracao=(linha.get("codigo_apuracao") or "").strip() or None,
                    uf=(linha.get("uf") or "").strip().upper() or None,
                    municipio_ibge=so_digitos(linha.get("municipio_ibge")) or None,
                    ie=(linha.get("ie") or "").strip() or None,
                    ativa=(linha.get("ativa") or "S").strip().upper() not in ("N", "NAO", "NÃO", "0"),
                ))
        if erros:
            raise CadastroInvalido("cadastro com erros:\n" + "\n".join(erros))
        return cls(empresas)
