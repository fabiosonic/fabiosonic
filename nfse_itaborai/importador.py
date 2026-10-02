"""Importação de clientes e padrões da NFS-e a partir dos XML colocados na pasta do sistema (IMPORTAR XML).

Fluxo: o usuário coloca XML ou ZIP de notas emitidas na pasta IMPORTAR XML (dentro da pasta do sistema), de qualquer
empresa. A análise agrupa as notas pelo CNPJ do prestador, indica a empresa cadastrada correspondente, os clientes
(novos e já cadastrados) e os padrões de serviço mais usados (item, desdobro, NBS, alíquota, descrição, IBS/CBS).
Ao importar para uma empresa, só entram as notas em que ela é a prestadora; os arquivos vão para
IMPORTAR XML/importados/<CNPJ> (que passa a ser a pasta de XML daquela empresa para o robô).
"""

from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import clientes, config, db, emissor, empresas
from .clientes import _achar, _digitos, _local, _texto

NOME_PASTA = "IMPORTAR XML"
CAMPOS_SERVICO = ("descricao", "item_lista_servico", "codigo_desdobro", "codigo_nbs", "cnae", "aliquota_iss",
                  "tipo_tributacao", "iss_retido", "indicador_operacao", "classificacao_tributaria")


def caixa() -> Path:
    p = emissor.BASE / NOME_PASTA
    p.mkdir(parents=True, exist_ok=True)
    return p


def arquivo_da_empresa(cnpj: str) -> Path:
    return caixa() / "importados" / _digitos(cnpj)


# ---------------------------------------------------------------- leitura

def _prestador(raiz) -> tuple[str, str]:
    if _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "PrestadorServico") is not None:
        p = _achar(raiz, "PrestadorServico")
        return _digitos(_texto(p, "Cnpj") or _texto(raiz, "Cnpj")), _texto(p, "RazaoSocial")
    dps = _achar(raiz, "infDPS")
    cnpj = _texto(raiz, "emit/CNPJ") or _texto(dps, "prest/CNPJ")
    return _digitos(cnpj), _texto(raiz, "emit/xNome") or _texto(dps, "prest/xNome")


def servico_de_xml(raiz) -> dict:
    """Dados do serviço da nota (para sugerir o serviço padrão da empresa)."""
    if _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "TomadorServico") is not None:
        return {"descricao": _texto(raiz, "DescritivoDoItem"), "item_lista_servico": _texto(raiz, "ItemListaServico"),
                "codigo_desdobro": _digitos(_texto(raiz, "CodigoLsnDesdobro")), "codigo_nbs": _digitos(_texto(raiz, "CodigoNbs")),
                "cnae": _digitos(_texto(raiz, "ClassificacaoCNAE")), "aliquota_iss": _texto(raiz, "Aliquota"),
                "tipo_tributacao": _texto(raiz, "TipoDeTributacao"), "iss_retido": _texto(raiz, "IssRetido"),
                "indicador_operacao": _digitos(_texto(raiz, "IndicadorOperacao")),
                "classificacao_tributaria": _digitos(_texto(raiz, "ClassificacaoTributaria"))}
    dps = _achar(raiz, "infDPS")
    ctrib = _digitos(_texto(dps, "cServ/cTribNac"))
    ret = _texto(dps, "tribMun/tpRetISSQN")
    sn = _texto(dps, "regTrib/opSimpNac")
    return {"descricao": _texto(dps, "cServ/xDescServ"),
            "item_lista_servico": f"{ctrib[:2]}.{ctrib[2:4]}" if len(ctrib) >= 4 else "",
            "codigo_desdobro": ctrib, "codigo_nbs": _digitos(_texto(dps, "cServ/cNBS")), "cnae": "",
            "aliquota_iss": _texto(dps, "tribMun/pAliq"),
            "tipo_tributacao": "4" if sn in ("2", "3") else "", "iss_retido": "1" if ret in ("2", "3") else ("2" if ret else ""),
            "indicador_operacao": _digitos(_texto(dps, "IBSCBS/cIndOp")),
            "classificacao_tributaria": _digitos(_texto(dps, "gIBSCBS/cClassTrib"))}


def _expandir_zips() -> int:
    """Descompacta os ZIP da caixa em subpastas e guarda o ZIP original em importados/_zips."""
    n = 0
    for z in list(caixa().glob("*.zip")) + list(caixa().glob("*.ZIP")):
        destino = caixa() / z.stem
        with zipfile.ZipFile(z) as arq:
            for membro in arq.infolist():
                nome = Path(membro.filename)
                if membro.is_dir() or nome.suffix.lower() != ".xml" or ".." in nome.parts:
                    continue
                alvo = destino / nome.name
                alvo.parent.mkdir(parents=True, exist_ok=True)
                alvo.write_bytes(arq.read(membro))
        guardado = caixa() / "importados" / "_zips" / z.name
        guardado.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(z), guardado)
        n += 1
    return n


def _pendentes() -> list[Path]:
    importados = caixa() / "importados"
    return [a for a in sorted(caixa().rglob("*")) if a.suffix.lower() == ".xml" and importados not in a.parents]


def _ler(arq: Path):
    try:
        return ET.fromstring(arq.read_bytes())
    except ET.ParseError:
        return None


def analisar() -> dict:
    """Agrupa os XML da caixa por prestador, com empresa correspondente, clientes e padrões sugeridos."""
    zips = _expandir_zips()
    grupos: dict[str, dict] = {}
    invalidos = 0
    for arq in _pendentes():
        raiz = _ler(arq)
        cnpj, nome = _prestador(raiz) if raiz is not None else ("", "")
        cli = clientes.cliente_de_xml(ET.tostring(raiz), cnpj) if raiz is not None and cnpj else None
        if not cnpj:
            invalidos += 1
            continue
        g = grupos.setdefault(cnpj, {"cnpj": cnpj, "nome": nome, "notas": 0, "clientes": set(), "servicos": []})
        g["nome"] = g["nome"] or nome
        g["notas"] += 1
        if cli:
            g["clientes"].add(cli["cpf_cnpj"])
        g["servicos"].append(servico_de_xml(raiz))
    cadastradas = {e["cnpj"]: e for e in empresas.listar() if e.get("cnpj")}
    saida = []
    for g in grupos.values():
        emp = cadastradas.get(g["cnpj"])
        existentes = set()
        if emp:
            with emissor.usar_empresa(empresas.pasta(emp)):
                existentes = {c["cpf_cnpj"] for c in clientes.listar()}
        saida.append({"cnpj": g["cnpj"], "nome": g["nome"], "notas": g["notas"],
                      "empresa_id": emp["id"] if emp else "", "empresa_nome": emp["nome"] if emp else "",
                      "clientes": len(g["clientes"]), "clientes_novos": len(g["clientes"] - existentes),
                      "padroes": padroes(g["servicos"])})
    return {"pasta": str(caixa()), "zips_descompactados": zips, "invalidos": invalidos,
            "grupos": sorted(saida, key=lambda x: -x["notas"]),
            "empresas": [{"id": e["id"], "nome": e["nome"], "cnpj": e["cnpj"]} for e in cadastradas.values()]}


def padroes(servicos: list[dict]) -> dict:
    """Valor mais frequente de cada campo do serviço nas notas da empresa."""
    out = {}
    for campo in CAMPOS_SERVICO:
        valores = Counter(s.get(campo, "") for s in servicos if s.get(campo, ""))
        out[campo] = valores.most_common(1)[0][0] if valores else ""
    return out


# ---------------------------------------------------------------- importação

def importar(empresa_id: str, cnpj_prestador: str, servico: dict | None = None) -> dict:
    """Importa para a empresa escolhida os clientes das notas emitidas por ela (prestador = CNPJ da empresa)."""
    emp = next((e for e in empresas.listar() if e["id"] == empresa_id), None)
    if not emp:
        raise ValueError("Empresa não encontrada.")
    cnpj = _digitos(cnpj_prestador)
    if emp.get("cnpj") and cnpj != _digitos(emp["cnpj"]):
        raise ValueError(f"Estas notas foram emitidas pelo CNPJ {cnpj}, não por {emp['nome']}. Os clientes de uma "
                         "empresa não podem ser cadastrados em outra.")
    destino = arquivo_da_empresa(cnpj)
    movidos = 0
    for arq in _pendentes():
        raiz = _ler(arq)
        if raiz is None or _prestador(raiz)[0] != cnpj:
            continue
        alvo = destino / arq.name
        if alvo.exists() and alvo.read_bytes() != arq.read_bytes():
            alvo = destino / f"{arq.stem}_{datetime.now():%Y%m%d%H%M%S%f}{arq.suffix}"
        alvo.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(arq), alvo)
        movidos += 1
    _limpar_subpastas_vazias()
    with emissor.usar_empresa(empresas.pasta(emp)):
        r = clientes.importar_xmls(destino, cnpj) if destino.exists() else {"clientes_novos": 0, "clientes_total": 0}
        if servico:
            empresas.salvar_servico({k: str(v).strip() for k, v in servico.items() if k in CAMPOS_SERVICO and str(v).strip()})
        if not str(config.carregar()["pastas"].get("xml_nfse") or "").strip():
            config.salvar({"pastas": {"xml_nfse": str(destino)}})
        db.registrar("importacao", f"{movidos} XML importado(s) da pasta {NOME_PASTA}: {r['clientes_novos']} cliente(s) novo(s)")
    return {"empresa": emp["nome"], "xml": movidos, "clientes_novos": r["clientes_novos"],
            "clientes_total": r["clientes_total"], "padrao_salvo": bool(servico)}


def importar_automatico() -> dict:
    """Robô: importa os clientes das notas da caixa emitidas pela empresa em uso (sem mexer no serviço padrão)."""
    cnpj = _digitos(emissor.env("ITABORAI_CNPJ"))
    if not cnpj:
        return {"xml": 0}
    tem = any((r := _ler(a)) is not None and _prestador(r)[0] == cnpj for a in _pendentes())
    if not tem:
        return {"xml": 0}
    emp = next(e for e in empresas.listar() if empresas.pasta(e).resolve() == emissor.raiz().resolve())
    return importar(emp["id"], cnpj)


def _limpar_subpastas_vazias() -> None:
    for p in sorted(caixa().rglob("*"), key=lambda x: -len(x.parts)):
        if p.is_dir() and p.name not in ("importados", "_zips") and "importados" not in p.parts and not any(p.iterdir()):
            p.rmdir()
