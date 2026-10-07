"""Lote de ações e aprovação (regra 6 — aprovação por exceção).

O lote é um JSON canônico com hash sha256. Só depois de aprovado nasce o arquivo
APROVADO_<lote>.json, que é o que os executores aceitam.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from ..especialista.modelo import CONTROLE
from ..util.arquivos import dumps, escrever_atomico, loads, sha256_bytes

PALAVRA = "APROVADO"

# Ações que SEMPRE exigem APROVADO digitado por pessoa. Fixo, sem bypass.
SEMPRE_HUMANO = frozenset({
    "transmitir_declaracao", "emitir_guia", "pagar_guia", "ato_societario", "alterar_cadastro",
    "transmitir_reinf", "transmitir_esocial", "transmitir_dctfweb", "transmitir_pgdas",
})


class AprovacaoRecusada(PermissionError):
    pass


def hash_lote(lote: dict) -> str:
    corpo = {k: v for k, v in lote.items() if k != "hash"}
    return sha256_bytes(dumps(corpo).encode())


def montar_lote(id_lote: str, acoes: list[dict], achados: list[dict], pendencias: list[dict]) -> dict:
    lote = {"id": id_lote, "acoes": acoes, "achados": achados, "pendencias": pendencias}
    lote["hash"] = hash_lote(lote)
    return lote


def salvar(lote: dict, pasta: Path) -> Path:
    caminho = Path(pasta) / f"lote_{lote['id']}.json"
    escrever_atomico(caminho, dumps(lote).encode())
    return caminho


def carregar(caminho: Path) -> dict:
    lote = loads(Path(caminho).read_text(encoding="utf-8"))
    if hash_lote(lote) != lote.get("hash"):
        raise AprovacaoRecusada("lote adulterado: hash não confere")
    return lote


@dataclass
class Avaliacao:
    pode_auto: bool
    motivos: list[str]


def avaliar_auto(lote: dict, politica: dict) -> Avaliacao:
    motivos = []
    if politica.get("ativa") is not True:
        motivos.append("aprovação por exceção desligada no config")
    if lote["pendencias"]:
        motivos.append(f"{len(lote['pendencias'])} pendência(s)")
    bloqueantes = [a for a in lote["achados"] if a.get("bloqueia")]
    if bloqueantes:
        motivos.append(f"{len(bloqueantes)} achado(s) bloqueante(s)")
    nao_controle = [a for a in lote["achados"] if a.get("natureza") != CONTROLE]
    if nao_controle:
        motivos.append(f"{len(nao_controle)} achado(s) INDÍCIO/APONTAMENTO")
    permitidas = set(politica.get("acoes_auto_permitidas") or [])
    for a in lote["acoes"]:
        if a["tipo"] in SEMPRE_HUMANO:
            motivos.append(f"ação {a['tipo']} sempre exige APROVADO humano")
        elif a["tipo"] not in permitidas:
            motivos.append(f"ação {a['tipo']} fora de acoes_auto_permitidas")
    limite = politica.get("valor_limite")
    if limite is None:
        motivos.append("valor_limite não configurado")
    else:
        total = sum((Decimal(str(a.get("valor") or 0)) for a in lote["acoes"]), Decimal("0"))
        if total > Decimal(str(limite)):
            motivos.append(f"valor total {total} acima do limite {limite}")
    return Avaliacao(not motivos, sorted(set(motivos)))


def _gravar_aprovado(lote: dict, pasta: Path, modo: str, motivo: str) -> Path:
    destino = Path(pasta) / f"APROVADO_{lote['id']}.json"
    escrever_atomico(destino, dumps({**lote, "aprovacao": {"modo": modo, "motivo": motivo}}).encode())
    return destino


def aprovar_humano(caminho_lote: Path, texto_digitado: str, hash_informado: str, usuario: str,
                   trilha=None) -> Path:
    lote = carregar(caminho_lote)
    if texto_digitado != PALAVRA:
        raise AprovacaoRecusada("é preciso digitar exatamente APROVADO")
    if hash_informado != lote["hash"]:
        raise AprovacaoRecusada("hash informado não confere com o lote")
    if lote["pendencias"]:
        raise AprovacaoRecusada(f"lote com {len(lote['pendencias'])} pendência(s): resolva antes de aprovar")
    if not usuario or not usuario.strip():
        raise AprovacaoRecusada("informe quem está aprovando")
    destino = _gravar_aprovado(lote, Path(caminho_lote).parent, "HUMANO", f"aprovado por {usuario}")
    if trilha:
        trilha.registrar_aprovacao(lote["id"], lote["hash"], "HUMANO", "APROVADO digitado", usuario)
    return destino


def aprovar_auto(caminho_lote: Path, politica: dict, trilha=None) -> Path | None:
    lote = carregar(caminho_lote)
    av = avaliar_auto(lote, politica)
    if not av.pode_auto:
        if trilha:
            trilha.evento("AUTO_APROVACAO_NEGADA", lote["id"], av.motivos)
        return None
    motivo = "zero pendências; só CONTROLE não bloqueante; ações permitidas; dentro do limite"
    destino = _gravar_aprovado(lote, Path(caminho_lote).parent, "AUTO_APROVADO", motivo)
    if trilha:
        trilha.registrar_aprovacao(lote["id"], lote["hash"], "AUTO_APROVADO", motivo, "sistema")
    return destino


def exigir_aprovado(caminho_aprovado: Path, trilha) -> dict:
    """Executores chamam isto: só aceitam APROVADO_* íntegro E registrado na trilha.

    O registro em `aprovacoes` (feito por aprovar_humano/aprovar_auto) impede que um arquivo
    APROVADO_* montado à mão em dados/lotes seja executado.
    """
    if trilha is None:
        raise AprovacaoRecusada("executor precisa da trilha para conferir a aprovação")
    p = Path(caminho_aprovado)
    if not p.name.startswith("APROVADO_"):
        raise AprovacaoRecusada("executor só aceita arquivo APROVADO_*")
    dados = loads(p.read_text(encoding="utf-8"))
    aprov = dados.pop("aprovacao", None)
    if not aprov or hash_lote(dados) != dados.get("hash"):
        raise AprovacaoRecusada("arquivo APROVADO_* inválido ou adulterado")
    for a in dados["acoes"]:
        if a["tipo"] in SEMPRE_HUMANO and aprov["modo"] != "HUMANO":
            raise AprovacaoRecusada(f"ação {a['tipo']} exige aprovação humana")
    if not trilha.aprovacao_registrada(dados["id"], dados["hash"], aprov["modo"]):
        raise AprovacaoRecusada("aprovação não consta na trilha: arquivo APROVADO_* não reconhecido")
    return dados
