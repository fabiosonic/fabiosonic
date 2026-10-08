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


_EMAIL = re.compile(r"[^@\s;,]+@[^@\s;,]+\.[^@\s;,]+")


def _partes(v) -> list[str]:
    itens = v if isinstance(v, (list, tuple)) else re.split(r"[;,\s\n]+", str(v or ""))
    return [str(x).strip() for x in itens if str(x).strip()]


def _lista_emails(v) -> list[str]:
    ruins = [x for x in _partes(v) if not _EMAIL.fullmatch(x)]
    if ruins:
        raise ValueError("E-mail adicional inválido: " + ", ".join(ruins))
    return list(dict.fromkeys(x.lower() for x in _partes(v)))


def _lista_fones(v) -> list[str]:
    nums = [_digitos(x) for x in (v if isinstance(v, (list, tuple)) else re.split(r"[;,/\n]+", str(v or "")))]
    ruins = [n for n in nums if n and not 10 <= len(n) <= 13]
    if ruins:
        raise ValueError("WhatsApp adicional inválido (DDD + número): " + ", ".join(ruins))
    return list(dict.fromkeys(n[-11:] for n in nums if n))


def emails(c: dict | None) -> list[str]:
    """Todos os e-mails que recebem as mensagens do cliente: o principal (pode ter vários separados por ;) e os adicionais."""
    c = c or {}
    todos = [x for x in _partes(c.get("email")) if _EMAIL.fullmatch(x)] + list(c.get("emails_extras") or [])
    return list(dict.fromkeys(x.lower() for x in todos))


def whatsapps(c: dict | None) -> list[str]:
    """Todos os números de WhatsApp do cliente: o telefone principal e os adicionais (sem repetir)."""
    c = c or {}
    todos = [_digitos(c.get("telefone"))[-11:]] + list(c.get("whatsapps_extras") or [])
    return list(dict.fromkeys(n for n in todos if len(n) >= 10))


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
        # código do cliente no sistema anterior (Nitrus): importações seguintes o reconhecem por ele
        **({"codigo_externo": str(c["codigo_externo"]).strip()} if str(c.get("codigo_externo") or "").strip() else {}),
        # outros e-mails e WhatsApp do mesmo cliente que também recebem as mensagens (o principal fica acima)
        **({"emails_extras": _lista_emails(c["emails_extras"])} if "emails_extras" in c else {}),
        **({"whatsapps_extras": _lista_fones(c["whatsapps_extras"])} if "whatsapps_extras" in c else {}),
        # cobrança por WhatsApp só para quem o escritório escolher (clientes que já conversam pelo WhatsApp)
        **({"whatsapp_cobranca": bool(c["whatsapp_cobranca"])} if "whatsapp_cobranca" in c else {}),
        **({"fiscal": _fiscal(c["fiscal"])} if "fiscal" in c else {}),
        **({"padroes_nota": _padroes(c["padroes_nota"])} if isinstance(c.get("padroes_nota"), dict) else {}),
        **({"estrangeiro": _estrangeiro(c["estrangeiro"])} if c.get("estrangeiro") else {}),
    }


PREFIXO_EXTERIOR = "99"      # chave interna (9 dígitos) do cliente do exterior, que não tem CPF/CNPJ


def eh_exterior(c: dict | None) -> bool:
    return bool((c or {}).get("estrangeiro"))


def _estrangeiro(d: dict) -> dict:
    """Cliente do exterior: NIF (ou motivo de não ter), país, cidade, estado/província e código postal."""
    from . import paises
    d = d if isinstance(d, dict) else {}
    iso = str(d.get("pais_iso") or "").strip().upper()[:2]
    out = {"pessoa": "2" if str(d.get("pessoa")) == "2" else "1", "nif": str(d.get("nif") or "").strip()[:40],
           "sem_nif": str(d.get("sem_nif") or "").strip()[:1], "pais_iso": iso,
           "pais_bacen": _digitos(d.get("pais_bacen"))[:4] or paises.bacen(iso),
           "cidade": " ".join(str(d.get("cidade") or "").split())[:55],
           "estado": " ".join(str(d.get("estado") or "").split())[:60],
           "cod_postal": str(d.get("cod_postal") or "").strip()[:11]}
    if len(iso) != 2 or not iso.isalpha():
        raise ValueError("Cliente do exterior: informe o país (sigla ISO de 2 letras, ex.: US).")
    if not out["pais_bacen"]:
        raise ValueError("Cliente do exterior: informe o código BACEN do país (4 dígitos) — exigido pela prefeitura.")
    if not out["cidade"]:
        raise ValueError("Cliente do exterior: informe a cidade.")
    if not out["nif"] and out["sem_nif"] not in ("1", "2"):
        raise ValueError("Cliente do exterior: informe o NIF (identificação fiscal no país dele) ou o motivo de não ter.")
    return out


def chave_exterior(nif: str, nome: str = "", pais: str = "") -> str:
    """Identidade do cliente do exterior nos XML (não tem CPF/CNPJ): o NIF, ou nome + país."""
    nif = "".join(str(nif or "").split()).upper()
    return f"EXT:{nif}" if nif else f"EXT:{' '.join(str(nome or '').upper().split())}|{str(pais or '').upper()}"


def chave_cliente(c: dict) -> str:
    """CPF/CNPJ, ou a chave_exterior do cliente do exterior (para casar com as notas importadas)."""
    x = c.get("estrangeiro")
    if x:
        return chave_exterior(x.get("nif"), c.get("razao_social"), x.get("pais_iso"))
    return _digitos(c.get("cpf_cnpj"))


def _nova_chave_exterior(lista: list[dict]) -> str:
    usados = {_digitos(c.get("cpf_cnpj")) for c in lista}
    n = 1
    while f"{PREFIXO_EXTERIOR}{n:07d}" in usados:
        n += 1
    return f"{PREFIXO_EXTERIOR}{n:07d}"


def _padroes(d: dict) -> dict:
    from .fiscal import padroes_nota
    return padroes_nota(d)


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
    if eh_exterior(c):
        if not (len(c["cpf_cnpj"]) == 9 and c["cpf_cnpj"].startswith(PREFIXO_EXTERIOR)):
            c["cpf_cnpj"] = _nova_chave_exterior(listar())
    elif len(c["cpf_cnpj"]) not in (11, 14):
        raise ValueError("CPF/CNPJ inválido.")
    if not c["razao_social"]:
        raise ValueError("Razão social obrigatória.")
    lista = [x for x in listar() if _digitos(x.get("cpf_cnpj")) != c["cpf_cnpj"]]
    antigo = obter(c["cpf_cnpj"]) or {}
    fora = excluidos()
    if c["cpf_cnpj"] in fora:                     # cadastrado de novo pela tela: volta a valer para o XML
        _gravar_excluidos(fora - {c["cpf_cnpj"]})
    # regra fiscal e serviço habitual do tomador só mudam quando vierem no cadastro (importações não apagam)
    lista.append({**{k: antigo[k] for k in ("ultima_nfse", "ultima_data", "ultimo_valor", "notas_vistas", "fiscal",
                                            "servico_id", "estrangeiro", "whatsapp_cobranca", "codigo_externo", "padroes_nota",
                                            "emails_extras", "whatsapps_extras")
                    if k in antigo}, **c})
    _gravar(lista)
    return c


def registrar_ultima_nota(cpf_cnpj: str, valor, data: str, numero: str) -> None:
    """Guarda no cadastro a última NFS-e emitida para o cliente (não volta para uma nota mais antiga)."""
    doc = _digitos(cpf_cnpj)
    lista = listar()
    for c in lista:
        if _digitos(c.get("cpf_cnpj")) == doc and str(c.get("ultima_data") or "") <= data:
            c.update(ultimo_valor=str(valor), ultima_data=data, ultima_nfse=str(numero))
            _gravar(lista)
            return


def _arq_excluidos() -> Path:
    return emissor.RAIZ / "dados" / "clientes_excluidos.json"


def excluidos() -> set[str]:
    """Clientes excluídos pela tela: a leitura dos XML não os cadastra de novo (só o cadastro manual traz de volta)."""
    try:
        return set(json.loads(_arq_excluidos().read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return set()


def _gravar_excluidos(docs: set[str]) -> None:
    arq = _arq_excluidos()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(sorted(docs), indent=2), encoding="utf-8")


def excluir(cpf_cnpj: str) -> bool:
    doc = _digitos(cpf_cnpj)
    lista = listar()
    nova = [c for c in lista if _digitos(c.get("cpf_cnpj")) != doc]
    _gravar(nova)
    if doc:
        _gravar_excluidos(excluidos() | {doc})
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
                          complemento=e.get("complemento", "")),
        estrangeiro=dict(c.get("estrangeiro") or {}))


def para_dict_tomador(c: dict) -> dict:
    """Formato de 'tomador' usado nos JSON de RPS."""
    return {k: c.get(k, "") for k in ("cpf_cnpj", "razao_social", "inscricao_municipal", "email", "telefone")} \
        | {"endereco": dict(c.get("endereco", {}))} | ({"estrangeiro": dict(c["estrangeiro"])} if c.get("estrangeiro") else {})


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
        ext = None
        if not (_texto(toma, "CNPJ") or _texto(toma, "CPF")) and (_achar(toma, "NIF") is not None
                                                                 or _achar(toma, "cNaoNIF") is not None):
            # tomador do exterior: NIF (ou motivo de não ter), país, cidade, estado/província e código postal
            from . import paises
            iso = _texto(toma, "endExt/cPais").upper()
            ext = {"nif": _texto(toma, "NIF"), "sem_nif": "2" if _texto(toma, "cNaoNIF") == "2" else "1",
                   "pais_iso": iso, "pais_bacen": paises.bacen(iso), "cidade": _texto(toma, "endExt/xCidade"),
                   "estado": _texto(toma, "endExt/xEstProvReg"), "cod_postal": _texto(toma, "endExt/cEndPost"),
                   "pessoa": "1"}
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
        if ext:
            c["estrangeiro"] = ext
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
    if cnpj_prestador and _digitos(prest) != _digitos(cnpj_prestador):
        return None                    # nota de outra empresa (ou sem o CNPJ do emissor): nunca entra nesta
    if c.get("estrangeiro"):
        try:
            c = normalizar(c)
        except ValueError:
            return None                              # exterior sem país/cidade na nota: não dá para cadastrar
        c["chave_ext"] = chave_exterior(c["estrangeiro"].get("nif"), c["razao_social"], c["estrangeiro"].get("pais_iso"))
        return c
    if len(_digitos(c["cpf_cnpj"])) not in (11, 14):
        return None
    return normalizar(c)


def importar_xmls(pasta: Path, cnpj_prestador: str | None = None) -> dict:
    """Varre a pasta (e subpastas) e atualiza o cadastro com o tomador mais recente de cada CNPJ."""
    if len(_digitos(cnpj_prestador)) != 14:
        raise ValueError("CNPJ da empresa não configurado: sem ele não dá para saber quais notas são desta empresa, "
                         "e nenhum cliente é importado.")
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
        doc = c.get("chave_ext") or c["cpf_cnpj"]
        anterior = encontrados.get(doc)
        c["notas_vistas"] = (anterior or {}).get("notas_vistas", 0) + 1
        if anterior is None or c.get("ultima_data", "") >= anterior.get("ultima_data", ""):
            encontrados[doc] = c
        else:
            anterior["notas_vistas"] = c["notas_vistas"]
    atuais = {chave_cliente(c): c for c in listar()}
    fora = excluidos()
    novos = 0
    for doc, c in encontrados.items():
        if doc not in atuais and doc in fora:
            continue                               # excluído pela tela: o XML não traz de volta
        if doc not in atuais:
            novos += 1
            if c.get("estrangeiro"):                 # cliente do exterior: ganha a chave interna 99xxxxxxx
                c["cpf_cnpj"] = _nova_chave_exterior(list(atuais.values()))
            c.pop("chave_ext", None)
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
