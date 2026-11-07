"""Carrega e valida config/config.yaml."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ConfigEstrategia:
    nome: str = "tendencia_mm"
    mm_rapida: int = 9
    mm_lenta: int = 21
    mm_filtro: int = 200
    atr_periodo: int = 14
    stop_atr: float = 3.0
    alvo_r: float = 3.0
    tempo_max_dias: int = 30
    trailing_atr: bool = True


@dataclass
class ConfigRisco:
    capital_teste: float = 5000.0
    risco_por_operacao: float = 0.01      # 1% do capital por trade
    max_posicoes: int = 3
    max_peso_posicao: float = 0.40        # no máx. 40% do capital num ativo
    max_ordens_dia: int = 6
    perda_maxima_total: float = 0.10      # kill switch: -10% do capital
    folga_preco: float = 0.005            # tolerância do preço limite (0,5%)
    folga_stop: float = 0.01              # limite do stop 1% abaixo do disparo
    custo_percentual: float = 0.0003      # emolumentos + liquidação B3 (aprox.)


@dataclass
class ConfigFiscal:
    limite_isencao_mensal: float = 20000.0
    bloquear_venda_acima_isencao: bool = False
    tipos_ativo: dict = field(default_factory=dict)   # ex.: {"TAEE11": "acao"}


@dataclass
class ConfigClear:
    arquivo_seletores: str = "config/seletores_clear.yaml"
    pasta_sessao: str = ".sessao_clear"
    timeout_login_seg: int = 300
    horario_inicio: str = "10:15"
    horario_fim: str = "16:45"
    headless: bool = False


@dataclass
class ConfigIA:
    # regras (grátis, sem IA) | ollama (grátis, IA local) | compativel (Groq/OpenRouter/Gemini, plano grátis)
    # | anthropic (pago)
    provedor: str = "regras"
    ollama_url: str = "http://localhost:11434"
    ollama_modelo: str = "qwen2.5:7b"
    compat_url: str = "https://api.groq.com/openai/v1"
    compat_modelo: str = "llama-3.3-70b-versatile"
    compat_variavel_chave: str = "IA_API_KEY"
    modelo_analise: str = "claude-opus-5-5"     # só para provedor anthropic
    modelo_chat: str = "claude-opus-5-5"
    orcamento_mensal_usd: float = 0.0           # gasto máximo com provedor pago (0 = bloqueia qualquer gasto)


@dataclass
class Config:
    modo: str = "simulado"                # simulado | real
    ativos: list = field(default_factory=list)
    inicio_dados: str = "2018-01-01"
    pasta_estado: str = "estado"
    pasta_logs: str = "logs"
    estrategia: ConfigEstrategia = field(default_factory=ConfigEstrategia)
    risco: ConfigRisco = field(default_factory=ConfigRisco)
    fiscal: ConfigFiscal = field(default_factory=ConfigFiscal)
    clear: ConfigClear = field(default_factory=ConfigClear)
    ia: ConfigIA = field(default_factory=ConfigIA)


def _montar(cls, dados: dict | None):
    dados = dados or {}
    validos = cls.__dataclass_fields__.keys()
    desconhecidos = set(dados) - set(validos)
    if desconhecidos:
        raise ValueError(f"Chaves desconhecidas em {cls.__name__}: {sorted(desconhecidos)}")
    return cls(**dados)


def carregar(caminho: str | Path = "config/config.yaml") -> Config:
    with open(caminho, encoding="utf-8") as f:
        bruto = yaml.safe_load(f) or {}
    cfg = Config(
        modo=bruto.get("modo", "simulado"),
        ativos=[a.upper() for a in bruto.get("ativos", [])],
        inicio_dados=str(bruto.get("inicio_dados", "2018-01-01")),
        pasta_estado=bruto.get("pasta_estado", "estado"),
        pasta_logs=bruto.get("pasta_logs", "logs"),
        estrategia=_montar(ConfigEstrategia, bruto.get("estrategia")),
        risco=_montar(ConfigRisco, bruto.get("risco")),
        fiscal=_montar(ConfigFiscal, bruto.get("fiscal")),
        clear=_montar(ConfigClear, bruto.get("clear")),
        ia=_montar(ConfigIA, bruto.get("ia")),
    )
    validar(cfg)
    return cfg


def validar(cfg: Config) -> None:
    if cfg.modo not in ("simulado", "real"):
        raise ValueError("modo deve ser 'simulado' ou 'real'")
    if not cfg.ativos:
        raise ValueError("Informe ao menos um ativo em 'ativos'")
    r = cfg.risco
    if not 0 < r.risco_por_operacao <= 0.03:
        raise ValueError("risco_por_operacao deve ficar entre 0 e 3% (recomendado: 0,5% a 1%)")
    if r.capital_teste <= 0:
        raise ValueError("capital_teste deve ser positivo")
    if not 0 < r.perda_maxima_total <= 0.5:
        raise ValueError("perda_maxima_total deve ficar entre 0 e 50%")
    if cfg.ia.provedor not in ("regras", "ollama", "compativel", "anthropic"):
        raise ValueError("ia.provedor deve ser regras, ollama, compativel ou anthropic")
    e = cfg.estrategia
    if not e.mm_rapida < e.mm_lenta < e.mm_filtro:
        raise ValueError("Exige-se mm_rapida < mm_lenta < mm_filtro")
