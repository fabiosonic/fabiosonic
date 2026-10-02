"""Catálogo de serviços (atividades) da empresa: contabilidade, consultoria, treinamento...

Cada serviço tem os próprios códigos da NFS-e (item da LC 116, desdobro, NBS, CNAE, alíquota, tributação, IBS/CBS)
e a descrição. Um deles é o padrão. Guardado em servicos.json na pasta da empresa; na primeira leitura, o antigo
servico_padrao.json vira o primeiro serviço do catálogo (nada se perde).
"""

from __future__ import annotations

import json
import re
import secrets
from pathlib import Path

from . import emissor

ARQ_FABRICA = Path(__file__).resolve().parent.parent / "servico_padrao.json"
CAMPOS = ("descricao", "item_lista_servico", "codigo_desdobro", "codigo_nbs", "cnae", "aliquota_iss",
          "tipo_tributacao", "iss_retido", "indicador_operacao", "classificacao_tributaria", "ibpt_percentual",
          "observacoes")


def _arquivo() -> Path:
    return emissor.raiz() / "servicos.json"


def _nome_de(descricao: str) -> str:
    d = (descricao or "").upper()
    for chave, nome in (("CONTAB", "Contabilidade"), ("CONSULT", "Consultoria"), ("TREINAM", "Treinamento"),
                        ("CURSO", "Treinamento"), ("ASSESSOR", "Assessoria"), ("AUDITOR", "Auditoria"),
                        ("PERICIA", "Perícia"), ("PERÍCIA", "Perícia")):
        if chave in d:
            return nome
    return (descricao or "Serviço").strip().title()[:40] or "Serviço"


def _legado() -> dict:
    """servico_padrao.json da empresa (ou o de fábrica), da versão anterior ao catálogo."""
    local = emissor.raiz() / "servico_padrao.json"
    arq = local if local.exists() else ARQ_FABRICA
    return json.loads(arq.read_text(encoding="utf-8"))


def listar() -> list[dict]:
    arq = _arquivo()
    if arq.exists():
        lst = json.loads(arq.read_text(encoding="utf-8"))
        if lst:
            return lst
    base = _legado()
    lst = [{"id": "padrao", "nome": _nome_de(base.get("descricao", "")), "padrao": True,
            **{k: str(base.get(k, "")) for k in CAMPOS}}]
    _gravar(lst)
    return lst


def _gravar(lst: list[dict]) -> None:
    if lst and not any(s.get("padrao") for s in lst):
        lst[0]["padrao"] = True
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(lst, indent=2, ensure_ascii=False), encoding="utf-8")
    # mantém servico_padrao.json igual ao padrão (compatibilidade com versões e rotinas antigas)
    padrao = next(s for s in lst if s.get("padrao"))
    (emissor.raiz() / "servico_padrao.json").write_text(
        json.dumps({k: padrao.get(k, "") for k in CAMPOS}, indent=2, ensure_ascii=False), encoding="utf-8")


def padrao() -> dict:
    lst = listar()
    return next((s for s in lst if s.get("padrao")), lst[0])


def obter(servico_id: str | None) -> dict:
    """Serviço pelo id; sem id (ou id que não existe mais) usa o padrão."""
    if servico_id:
        for s in listar():
            if s["id"] == servico_id:
                return s
    return padrao()


def _validar(s: dict) -> dict:
    s = {**s, **{k: str(s.get(k, "") or "").strip() for k in CAMPOS}}
    s["nome"] = str(s.get("nome") or _nome_de(s["descricao"])).strip()[:60]
    s["codigo_desdobro"] = re.sub(r"\D", "", s["codigo_desdobro"])
    s["codigo_nbs"] = re.sub(r"\D", "", s["codigo_nbs"])
    if s["codigo_desdobro"] and len(s["codigo_desdobro"]) != 6:
        raise ValueError(f"{s['nome']}: o desdobro deve ter 6 dígitos (ex.: 171901).")
    if s["codigo_nbs"] and len(s["codigo_nbs"]) != 9:
        raise ValueError(f"{s['nome']}: a NBS deve ter 9 dígitos.")
    if not s["descricao"]:
        raise ValueError(f"{s['nome']}: informe a descrição que vai na nota.")
    return s


def salvar(d: dict) -> dict:
    """Cria ou altera um serviço. Com padrao=True, ele vira o padrão da empresa."""
    lst = listar()
    s = _validar(d)
    if not s["ibpt_percentual"] and lst:   # carga aproximada (Lei 12.741/2012): herda a do padrão se não informada
        s["ibpt_percentual"] = next((x for x in lst if x.get("padrao")), lst[0]).get("ibpt_percentual", "")
    if not s.get("id"):
        s["id"] = secrets.token_hex(4)
        lst.append(s)
    else:
        i = next((i for i, x in enumerate(lst) if x["id"] == s["id"]), None)
        if i is None:
            raise ValueError("Serviço não encontrado.")
        lst[i] = {**lst[i], **s}
    if s.get("padrao"):
        for x in lst:
            x["padrao"] = x["id"] == s["id"]
    if len({x["nome"].lower() for x in lst}) != len(lst):
        raise ValueError(f"Já existe um serviço chamado {s['nome']}.")
    _gravar(lst)
    from . import config
    if not config.carregar()["emissao"].get("servico_revisado", True):
        config.salvar({"emissao": {"servico_revisado": True}})
    return next(x for x in lst if x["id"] == s["id"])


def excluir(servico_id: str) -> None:
    lst = listar()
    if len(lst) == 1:
        raise ValueError("A empresa precisa ter pelo menos um serviço.")
    _gravar([s for s in lst if s["id"] != servico_id])


def assinatura(s: dict) -> tuple:
    """Identifica o mesmo serviço vindo de notas diferentes."""
    return (re.sub(r"\D", "", s.get("codigo_desdobro", "")) or s.get("item_lista_servico", ""),
            re.sub(r"\D", "", s.get("codigo_nbs", "")))


def _nome_livre(nome: str, ignorar_id: str = "") -> str:
    usados = {s["nome"].lower() for s in listar() if s["id"] != ignorar_id}
    base, n = nome, 2
    while nome.lower() in usados:
        nome, n = f"{base} {n}", n + 1
    return nome


def registrar_detectado(dados: dict, nome: str = "") -> dict:
    """Importação: cria o serviço se ainda não existir um com os mesmos códigos; senão completa o que falta."""
    lst = listar()
    alvo = next((s for s in lst if assinatura(s) == assinatura(dados) and any(assinatura(dados))), None)
    if alvo:
        novos = {k: v for k, v in dados.items() if k in CAMPOS and str(v).strip() and not str(alvo.get(k, "")).strip()}
        renomear = {"nome": _nome_livre(nome, alvo["id"])} if nome and nome != alvo["nome"] else {}
        return salvar({**alvo, **novos, **renomear}) if novos or renomear else alvo
    return salvar({**{k: dados.get(k, "") for k in CAMPOS}, "nome": _nome_livre(nome or _nome_de(dados.get("descricao", ""))),
                   "ibpt_percentual": dados.get("ibpt_percentual") or padrao().get("ibpt_percentual", "")})
