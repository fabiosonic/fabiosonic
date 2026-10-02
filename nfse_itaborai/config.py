"""Configurações do sistema (dados/config.json, fora do Git — contém senhas e chaves)."""

from __future__ import annotations

import copy
import json

from . import emissor

PADRAO = {
    "empresa": {
        "nome": "MORAES & OLIVEIRA CONTABILIDADE",
        "pix_chave": "",            # chave PIX que recebe (CNPJ, e-mail, telefone ou aleatória)
        "pix_cidade": "ITABORAI",
        "whatsapp": "",             # número do escritório, aparece nas mensagens
        "assinatura": "Moraes & Oliveira Contabilidade",
    },
    "smtp": {"host": "", "porta": 587, "usuario": "", "senha": "", "remetente": "", "ssl": False,
             "copia_para": ""},
    "cobranca": {
        "provedor": "pix",          # pix (PIX copia-e-cola próprio, sem tarifa) | asaas (boleto+PIX com baixa automática) | nenhum
        "asaas_api_key": "",
        "asaas_sandbox": True,
        "multa_pct": 2.0,
        "juros_mes_pct": 1.0,
        "regua_dias": [-3, 0, 1, 5, 15, 30],
        "regua_email": True,
        "regua_whatsapp": True,
        "bloquear_apos_dias": 60,   # alerta de cliente para suspensão/negociação
    },
    "financeiro": {
        "dia_vencimento_padrao": 10,
        "prazo_avulso_dias": 5,     # vencimento de nota avulsa = emissão + N dias
        "dia_geracao": 1,           # dia do mês em que a recorrência gera os títulos
        "aliquota_simples_pct": 3.99,  # usada só sem histórico; com histórico calcula pelo RBT12 (Anexo III)
        "iss_fixo": True,           # escritório contábil: ISS fixo fora do DAS (LC 123, art. 18, § 22-A)
        "categorias_despesa": ["Aluguel", "Folha", "Pró-labore", "Impostos", "Sistemas", "Energia/Internet",
                               "Contador/Assessoria", "Marketing", "Bancárias", "Outras"],
    },
    "automacao": {
        "ativa": False,             # liga o robô (geração, NFS-e, cobrança, régua, baixa)
        "gerar_titulos": True,
        "emitir_nfse": True,
        "criar_cobranca": True,
        "regua": True,
        "sincronizar_asaas": True,
        "despesas_recorrentes": True,
        "backup": True,
    },
}


def _arquivo():
    return emissor.RAIZ / "dados" / "config.json"


def _mesclar(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v
    return base


def carregar() -> dict:
    cfg = copy.deepcopy(PADRAO)
    arq = _arquivo()
    if arq.exists():
        _mesclar(cfg, json.loads(arq.read_text(encoding="utf-8")))
    return cfg


def salvar(novo: dict) -> dict:
    cfg = _mesclar(carregar(), novo)
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def publico(cfg: dict | None = None) -> dict:
    """Cópia para a tela, sem expor senhas (mostra só se estão preenchidas)."""
    c = copy.deepcopy(cfg or carregar())
    for sec, campo in (("smtp", "senha"), ("cobranca", "asaas_api_key")):
        c[sec][campo] = "••••••" if c[sec].get(campo) else ""
    return c


def salvar_da_tela(novo: dict) -> dict:
    """Salva o que veio da tela, mantendo senhas quando o campo vier mascarado."""
    for sec, campo in (("smtp", "senha"), ("cobranca", "asaas_api_key")):
        if novo.get(sec, {}).get(campo) == "••••••":
            novo[sec].pop(campo)
    return publico(salvar(novo))
