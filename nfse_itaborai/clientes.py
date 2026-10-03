"""Cadastro de clientes (tomadores): dados/clientes.json, fora do Git.

- CRUD simples por CPF/CNPJ;
- importação a partir de XMLs de NFS-e já emitidas (padrão nacional e retorno do webservice).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from . import emissor
from .modelos import Endereco, Tomador

TIPOS_LOGRADOURO = ("AVENIDA", "AV", "RUA", "R", "TRAVESSA", "TV", "RODOVIA", "ROD", "ESTRADA", "EST",
                    "PRACA", "PCA", "ALAMEDA", "AL", "LARGO", "LGO", "VIA", "BECO", "VILA", "VL")
UF_POR_IBGE = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO", "21": "MA",
               "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL", "28": "SE", "29": "BA",
               "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
               "51": "MT", "52": "GO", "53": "DF"}


def _digitos(v) -> str:
    return re.sub(r"\D", "", str(v or ""))


def arquivo() -> Path:
    return emissor.RAIZ / "dados" / "clientes.json"


def listar() -> list[dict]:
    arq = arquivo()
    if not arq.exists():
        return []
    return json.loads(arq.read_text(encoding="utf-8"))


def _gravar(lista: list[dict]) -> None:
    arq = arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    lista.sort(key=lambda c: c.get("razao_social", "").upper())
    arq.write_text(json.dumps(lista, indent=2, ensure_ascii=False), encoding="utf-8")


def obter(cpf_cnpj: str) -> dict | None:
    doc = _digitos(cpf_cnpj)
    return next((c for c in listar() if _digitos(c.get("cpf_cnpj")) == doc), None)


def normalizar(c: dict) -> dict:
    e = c.get("endereco") or {}
    cod = _digitos(e.get("codigo_municipio"))
    tipo, logr = separar_tipo(str(e.get("tipo_logradouro", "")), str(e.get("logradouro", "")))
    return {
        "cpf_cnpj": _digitos(c.get("cpf_cnpj")),
        "razao_social": str(c.get("razao_social", "")).strip(),
        "inscricao_municipal": _digitos(c.get("inscricao_municipal")),
        "email": str(c.get("email", "")).strip(),
        "telefone": _digitos(c.get("telefone"))[-11:],
        "endereco": {
            "tipo_logradouro": tipo, "logradouro": logr,
            "numero": str(e.get("numero", "")).strip(), "complemento": str(e.get("complemento", "")).strip(),
            "bairro": str(e.get("bairro", "")).strip(), "codigo_municipio": cod,
            "uf": (str(e.get("uf", "")).strip() or UF_POR_IBGE.get(cod[:2], "")).upper(),
            "cep": _digitos(e.get("cep")), "cidade": str(e.get("cidade", "")).strip(),
        },
        **{k: c[k] for k in ("ultima_nfse", "ultima_data", "ultimo_valor", "notas_vistas", "observacao", "servico_id") if k in c},
        **({"fiscal": _fiscal(c["fiscal"])} if "fiscal" in c else {}),
    }


def _fiscal(d: dict) -> dict:
    from .fiscal import normalizar_tomador
    return normalizar_tomador(d)


def separar_tipo(tipo: str, logradouro: str) -> tuple[str, str]:
    """'AV AVENIDA CHURCHILL' -> ('AV', 'AVENIDA CHURCHILL'); mantém o tipo informado se houver."""
    tipo, logradouro = tipo.strip(), logradouro.strip()
    if tipo:
        return tipo, logradouro
    partes = logradouro.split(" ", 1)
    if len(partes) == 2 and partes[0].upper().rstrip(".") in TIPOS_LOGRADOURO:
        return partes[0].rstrip("."), partes[1]
    return "", logradouro


def salvar(c: dict) -> dict:
    c = normalizar(c)
    if len(c["cpf_cnpj"]) not in (11, 14):
        raise ValueError("CPF/CNPJ inválido.")
    if not c["razao_social"]:
        raise ValueError("Razão social obrigatória.")
    lista = [x for x in listar() if _digitos(x.get("cpf_cnpj")) != c["cpf_cnpj"]]
    antigo = obter(c["cpf_cnpj"]) or {}
    # regra fiscal e serviço habitual do tomador só mudam quando vierem no cadastro (importações não apagam)
    lista.append({**{k: antigo[k] for k in ("ultima_nfse", "ultima_data", "ultimo_valor", "notas_vistas", "fiscal",
                                            "servico_id") if k in antigo}, **c})
    _gravar(lista)
    return c


def excluir(cpf_cnpj: str) -> bool:
    doc = _digitos(cpf_cnpj)
    lista = listar()
    nova = [c for c in lista if _digitos(c.get("cpf_cnpj")) != doc]
    _gravar(nova)
    return len(nova) != len(lista)


def para_tomador(c: dict) -> Tomador:
    e = c.get("endereco", {})
    return Tomador(
        cpf_cnpj=c["cpf_cnpj"], razao_social=c["razao_social"],
        inscricao_municipal=c.get("inscricao_municipal", ""), email=c.get("email", ""),
        telefone=c.get("telefone", ""),
        endereco=Endereco(logradouro=e.get("logradouro", ""), numero=e.get("numero", ""),
                          bairro=e.get("bairro", ""), codigo_municipio=e.get("codigo_municipio", ""),
                          uf=e.get("uf", ""), cep=e.get("cep", ""), tipo_logradouro=e.get("tipo_logradouro", ""),
                          complemento=e.get("complemento", "")))


def para_dict_tomador(c: dict) -> dict:
    """Formato de 'tomador' usado nos JSON de RPS."""
    return {k: c.get(k, "") for k in ("cpf_cnpj", "razao_social", "inscricao_municipal", "email", "telefone")} \
        | {"endereco": dict(c.get("endereco", {}))}


# ---------------------------------------------------------------- XML de NFS-e

def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _achar(no: ET.Element | None, caminho: str) -> ET.Element | None:
    """Busca por nomes locais separados por '/', ignorando namespace."""
    if no is None:
        return None
    atual = [no]
    for nome in caminho.split("/"):
        prox = [f for n in atual for f in n.iter() if _local(f.tag) == nome and f is not n]
        if not prox:
            return None
        atual = prox[:1]
    return atual[0]


def _texto(no, caminho: str) -> str:
    alvo = _achar(no, caminho)
    return (alvo.text or "").strip() if alvo is not None else ""


def cliente_de_xml(xml: str, cnpj_prestador: str | None = None) -> dict | None:
    """Extrai o tomador de uma NFS-e (padrão nacional ou RetornoNfse do webservice de Itaboraí)."""
    raiz = ET.fromstring(xml.encode("utf-8") if isinstance(xml, str) else xml)
    if _local(raiz.tag) in ("NFSe", "CompNFSe") or _achar(raiz, "infDPS") is not None:
        dps = _achar(raiz, "infDPS")
        prest = _texto(dps, "prest/CNPJ") or _texto(raiz, "emit/CNPJ")
        toma = _achar(dps, "toma")
        if toma is None:
            return None
        c = {
            "cpf_cnpj": _texto(toma, "CNPJ") or _texto(toma, "CPF"),
            "razao_social": _texto(toma, "xNome"), "inscricao_municipal": _texto(toma, "IM"),
            "email": _texto(toma, "email"), "telefone": _texto(toma, "fone"),
            "endereco": {"logradouro": _texto(toma, "end/xLgr"), "numero": _texto(toma, "end/nro"),
                         "complemento": _texto(toma, "end/xCpl"), "bairro": _texto(toma, "end/xBairro"),
                         "codigo_municipio": _texto(toma, "endNac/cMun"), "cep": _texto(toma, "endNac/CEP")},
            "ultima_nfse": _texto(raiz, "nNFSe"), "ultima_data": _texto(dps, "dhEmi")[:10],
            "ultimo_valor": _texto(dps, "vServ"),
        }
    elif _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "TomadorServico") is not None:
        prest = _texto(raiz, "PrestadorServico/Cnpj") or _texto(raiz, "Cnpj")
        t = _achar(raiz, "TomadorServico")
        if t is None:
            return None
        im = _digitos(_texto(t, "InscricaoMunicipal"))
        c = {
            "cpf_cnpj": _texto(t, "CpfCnpj"), "razao_social": _texto(t, "RazaoSocial"),
            "inscricao_municipal": "" if im.strip("0") == "" else im,
            "email": _texto(t, "Email"), "telefone": _texto(t, "Telefone"),
            "endereco": {"tipo_logradouro": _texto(t, "TipoLogradouro"), "logradouro": _texto(t, "Logradouro"),
                         "numero": _texto(t, "NumeroTomadorServico").lstrip("0") or _texto(t, "Numero"),
                         "complemento": _texto(t, "Complemento"), "bairro": _texto(t, "Bairro"),
                         "codigo_municipio": _texto(t, "CodigoMunicipio"), "uf": _texto(t, "Uf"),
                         "cep": _texto(t, "Cep")},
            "ultima_nfse": _texto(raiz, "NumeroNFSe"), "ultima_data": _texto(raiz, "DataEmissaoNFSe")[:10],
            "ultimo_valor": _texto(raiz, "ValorTotalDosServicos"),
        }
    else:
        return None
    if cnpj_prestador and _digitos(prest) and _digitos(prest) != _digitos(cnpj_prestador):
        return None
    if len(_digitos(c["cpf_cnpj"])) not in (11, 14):
        return None
    return normalizar(c)


def importar_xmls(pasta: Path, cnpj_prestador: str | None = None) -> dict:
    """Varre a pasta (e subpastas) e atualiza o cadastro com o tomador mais recente de cada CNPJ."""
    encontrados: dict[str, dict] = {}
    lidos = ignorados = 0
    for arq in sorted(Path(pasta).rglob("*.xml")):
        try:
            c = cliente_de_xml(arq.read_text(encoding="utf-8", errors="replace"), cnpj_prestador)
        except ET.ParseError:
            c = None
        if not c:
            ignorados += 1
            continue
        lidos += 1
        doc = c["cpf_cnpj"]
        anterior = encontrados.get(doc)
        c["notas_vistas"] = (anterior or {}).get("notas_vistas", 0) + 1
        if anterior is None or c.get("ultima_data", "") >= anterior.get("ultima_data", ""):
            encontrados[doc] = c
        else:
            anterior["notas_vistas"] = c["notas_vistas"]
    atuais = {_digitos(c["cpf_cnpj"]): c for c in listar()}
    novos = 0
    for doc, c in encontrados.items():
        if doc not in atuais:
            novos += 1
            atuais[doc] = c
            continue
        # Cliente já cadastrado: o cadastro (que pode ter sido corrigido à mão) prevalece;
        # do XML vêm só os dados da última nota e os campos que estiverem vazios.
        atual = atuais[doc]
        if c.get("ultima_data", "") >= atual.get("ultima_data", ""):
            for k in ("ultima_nfse", "ultima_data", "ultimo_valor"):
                atual[k] = c.get(k, "")
        atual["notas_vistas"] = max(int(atual.get("notas_vistas", 0) or 0), c.get("notas_vistas", 0))
        for k in ("razao_social", "email", "telefone", "inscricao_municipal"):
            atual[k] = atual.get(k) or c.get(k, "")
        end = atual.setdefault("endereco", {})
        for k, v in c["endereco"].items():
            end[k] = end.get(k) or v
    _gravar(list(atuais.values()))
    return {"xml_lidos": lidos, "xml_ignorados": ignorados, "clientes_novos": novos,
            "clientes_total": len(atuais)}
