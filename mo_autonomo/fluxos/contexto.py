"""Contexto de execução compartilhado pelos nós dos grafos."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import yaml

from ..clientes.cadastro import Carteira
from ..clientes.perfil import Perfis
from ..dominio.pastas import TIPOS_PADRAO
from ..normas.catalogo import Catalogo
from ..trilha.auditoria import Trilha
from ..util.arquivos import loads


class ConfigInvalida(ValueError):
    pass


def carregar_config(caminho: Path | str) -> dict:
    cfg = yaml.safe_load(Path(caminho).read_text(encoding="utf-8")) or {}
    cfg["_base"] = str(Path(caminho).resolve().parent.parent)
    if cfg.get("modo", "simulacao") not in ("simulacao", "producao"):
        raise ConfigInvalida("modo deve ser 'simulacao' ou 'producao'")
    cfg.setdefault("modo", "simulacao")
    tipos = {**TIPOS_PADRAO, **(cfg.get("dominio", {}).get("tipos_pasta") or {})}
    cfg.setdefault("dominio", {})["tipos_pasta"] = tipos
    return cfg


@dataclass
class Contexto:
    config: dict
    trilha: Trilha
    catalogo: Catalogo
    carteira: Carteira
    perfis: Perfis
    hoje: date
    cascata: object = None
    fonte: object = None
    extras: dict = field(default_factory=dict)

    @property
    def versao_base(self) -> str:
        """Muda quando normas (status/parâmetros/alteradas) ou o cadastro mudam: dispara reprocesso de pendências."""
        if "_versao_base" not in self.extras:
            from ..util.arquivos import dumps, sha256_bytes
            normas = {n.id: [n.status, n.alterada, n.parametros] for n in self.catalogo.normas.values()}
            cad = sorted((e.cnpj, e.codigo_dominio, e.apelido, e.regime_dominio, e.uf, e.ativa) for e in self.carteira)
            contas = sorted(map(str, (self.extras.get("contas_bancarias") or {}).items()))
            relevantes = {k: self.config.get(k) for k in ("ia", "contabil", "dominio", "cruzamentos")}
            arquivos = []
            for pasta in (self.dados / "dominio", self.dados / "apuracao"):
                if pasta.exists():
                    arquivos += sorted((str(p.relative_to(self.dados)), p.stat().st_size, int(p.stat().st_mtime))
                                       for p in pasta.rglob("*.csv"))
            receita = sha256_bytes(dumps(self.perfis.receita).encode())
            self.extras["_versao_base"] = sha256_bytes(
                dumps([normas, cad, contas, relevantes, arquivos, receita]).encode())[:16]
        return self.extras["_versao_base"]

    def caminho(self, chave: str, padrao: str) -> Path:
        p = Path((self.config.get("pastas") or {}).get(chave) or padrao)
        return p if p.is_absolute() else Path(self.config["_base"]) / p

    @property
    def dados(self) -> Path:
        return self.caminho("dados", "dados")

    @property
    def base_xml(self) -> Path:
        if self.config["modo"] == "producao":
            p = (self.config.get("pastas") or {}).get("xml_notas_producao")
            if not p:
                raise ConfigInvalida("modo produção sem pastas.xml_notas_producao")
            return Path(p)
        return self.dados / "_STAGING" / "XML NOTAS"


def montar_contexto(config: dict, hoje: date | None = None, fonte=None, cascata=None) -> Contexto:
    base = Path(config["_base"])

    def rel(p):
        p = Path(p)
        return p if p.is_absolute() else base / p

    pastas = config.get("pastas") or {}
    dados = rel(pastas.get("dados") or "dados")
    trilha = Trilha(dados / "trilha.sqlite")
    catalogo = Catalogo.carregar(rel(pastas.get("normas") or "config/normas"))
    from ..normas.monitor import carregar_alteradas
    catalogo.marcar_alteradas(carregar_alteradas(dados / "normas_textos"))
    carteira = Carteira.carregar(rel((config.get("cadastro") or {}).get("empresas") or "config/empresas.csv"))
    receita = {}
    cache = dados / "rfb_carteira.json"
    if cache.exists():
        receita = loads(cache.read_text(encoding="utf-8"))
    perfis = Perfis(carteira, receita, catalogo)
    razoes = [((v or {}).get("empresa") or {}).get("razao_social") for v in receita.values()]
    if cascata is None and (config.get("ia") or {}).get("ativa"):
        from ..ia.cascata import montar_cascata
        cascata = montar_cascata(config["ia"], str(dados / "ia_esperas.json"))
    if fonte is None:
        fonte = montar_fonte(config, rel, hoje or date.today())
    extras = {"razoes_sociais": [r for r in razoes if r]}
    contas_csv = (config.get("cadastro") or {}).get("contas_bancarias")
    if contas_csv and rel(contas_csv).exists():
        from ..contabil.lancamentos import contas_bancarias
        extras["contas_bancarias"] = contas_bancarias(rel(contas_csv))
    return Contexto(config, trilha, catalogo, carteira, perfis, hoje or date.today(), cascata, fonte, extras)


def montar_fonte(config: dict, rel, hoje: date):
    from ..entrada.fontes import FonteImap, FontePastaEml, obter_senha
    e = config.get("email") or {}
    tipo = e.get("tipo", "pasta")
    if tipo == "pasta":
        return FontePastaEml(rel(e.get("pasta_eml") or "dados/entrada_eml"))
    if tipo == "imap":
        for k in ("host", "porta", "usuario"):
            if not e.get(k):
                raise ConfigInvalida(f"email.{k} não configurado")
        senha = obter_senha(e.get("keyring_servico", "mo_autonomo_imap"), e["usuario"], e.get("senha_env"))
        desde = hoje - timedelta(days=int(e.get("desde_dias", 30)))
        return FonteImap(e["host"], int(e["porta"]), e["usuario"], senha, e.get("pasta", "INBOX"), desde,
                         ssl=bool(e.get("ssl", True)))
    raise ConfigInvalida(f"email.tipo desconhecido: {tipo}")
