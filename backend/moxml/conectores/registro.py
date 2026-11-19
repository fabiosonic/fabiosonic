"""Registro de conectores e matriz de cobertura UF × modelo."""

from __future__ import annotations

from dataclasses import dataclass

from .base import Capacidade, Conector

# Ordem de preferência: oficiais primeiro; comercial por último.
PRIORIDADE_DESCOBERTA = ["sefaz_sae_nfce", "sefaz_consulta", "apisimples"]
PRIORIDADE_RECUPERACAO = ["dist_dfe_chave", "sefaz_sae_nfce", "svrs_portal_download", "apisimples"]


@dataclass
class Registro:
    conectores: dict[str, Conector]

    def get(self, nome: str) -> Conector | None:
        return self.conectores.get(nome)

    def com_capacidade(self, cap: Capacidade, ordem: list[str]) -> list[Conector]:
        lista = [self.conectores[n] for n in ordem if n in self.conectores and cap in self.conectores[n].capacidades]
        lista += [c for n, c in self.conectores.items() if n not in ordem and cap in c.capacidades]
        return lista

    def matriz(self, ufs: list[str], modelos: tuple[str, ...] = ("55", "65")) -> list[dict]:
        linhas = []
        for uf in ufs:
            for mod in modelos:
                for c in self.conectores.values():
                    d = c.suporta(uf, mod)
                    linhas.append({"uf": uf, "modelo": mod, "conector": c.nome, "oficial": c.oficial,
                                   "comercial": c.comercial, "capacidades": sorted(x.value for x in c.capacidades),
                                   "status": d.status.value, "motivo": d.motivo, "evidencia": d.evidencia})
        return linhas
