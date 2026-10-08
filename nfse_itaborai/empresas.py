"""Multiempresa: cadastro das empresas atendidas e troca da empresa em uso.

Cada empresa tem uma pasta própria com o .env (credenciais), dados/ (banco, clientes, configurações, numeração),
saida/ (XML enviados e notas) e servico_padrao.json. A empresa original continua na pasta do sistema
(sem mover nenhum arquivo); as novas ficam em empresas/<CNPJ>/. O registro fica em empresas.json, na pasta base.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from . import emissor
from .xml_rps import so_digitos

# modelo de fábrica, vazio e dentro do programa: o servico_padrao.json da pasta do sistema é o da 1ª empresa
# e nunca é copiado para outra (cada empresa começa sem serviço e cadastra o seu)
ARQ_PADRAO_SERVICO = Path(__file__).resolve().parent / "servico_fabrica.json"
SEGREDO = "••••••"
CAMPOS_ENV = {  # campo da tela -> variável do .env
    "cnpj": "ITABORAI_CNPJ", "im": "ITABORAI_IM", "chave": "ITABORAI_CHAVE", "ie": "ITABORAI_IE",
    "simples": "ITABORAI_SIMPLES", "proximo_rps": "ITABORAI_PROXIMO_RPS",
}


def _registro() -> Path:
    return emissor.BASE / "empresas.json"


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False
    for n in (12, 13):
        pesos = list(range(n - 7, 1, -1)) + list(range(9, 1, -1))
        dv = sum(int(a) * b for a, b in zip(d[:n], pesos)) % 11
        if int(d[n]) != (0 if dv < 2 else 11 - dv):
            return False
    return True


def _ler() -> dict:
    arq = _registro()
    reg = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else {"empresas": [], "ativa": ""}
    if not any(e["pasta"] == "." for e in reg["empresas"]):
        # a instalação original vira a primeira empresa, na própria pasta do sistema
        with emissor.usar_empresa(emissor.BASE):
            cnpj = so_digitos(emissor.env("ITABORAI_CNPJ"))
        reg["empresas"].insert(0, {"id": cnpj or "principal", "nome": _nome_config(emissor.BASE) or "Empresa principal",
                                   "cnpj": cnpj, "pasta": "."})
        reg["ativa"] = reg.get("ativa") or reg["empresas"][0]["id"]
    return reg


def _gravar(reg: dict) -> None:
    _registro().write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")


def _nome_config(pasta: Path) -> str:
    arq = pasta / "dados" / "config.json"
    try:
        return json.loads(arq.read_text(encoding="utf-8")).get("empresa", {}).get("nome", "")
    except (OSError, ValueError):
        return ""


def pasta(e: dict) -> Path:
    return emissor.BASE if e["pasta"] == "." else emissor.BASE / e["pasta"]


def listar() -> list[dict]:
    reg = _ler()
    out = []
    for e in reg["empresas"]:
        with emissor.usar_empresa(pasta(e)):
            prod = emissor.em_producao()
            cnpj = so_digitos(emissor.env("ITABORAI_CNPJ")) or e.get("cnpj", "")
        out.append(e | {"nome": _nome_config(pasta(e)) or e["nome"], "ativa": e["id"] == reg["ativa"], "producao": prod,
                        "cnpj": cnpj})
    return out


def ativa() -> dict:
    reg = _ler()
    return next((e for e in reg["empresas"] if e["id"] == reg["ativa"]), reg["empresas"][0])


def aplicar_ativa() -> dict:
    """Aponta a tela para a empresa ativa (chamado ao iniciar e ao trocar)."""
    e = ativa()
    emissor.definir_ativa(pasta(e))
    return e


def ativar(id_: str) -> dict:
    reg = _ler()
    if not any(e["id"] == id_ for e in reg["empresas"]):
        raise ValueError("Empresa não encontrada.")
    reg["ativa"] = id_
    _gravar(reg)
    return aplicar_ativa()


def criar(d: dict) -> dict:
    """Nova empresa: valida o CNPJ, cria a pasta com .env, configurações e serviço padrão, e a ativa."""
    cnpj = so_digitos(d.get("cnpj"))
    nome = str(d.get("nome", "")).strip()
    if not nome:
        raise ValueError("Informe o nome da empresa.")
    if not cnpj_valido(cnpj):
        raise ValueError("CNPJ inválido.")
    reg = _ler()
    if any(e["cnpj"] == cnpj for e in reg["empresas"]) or any(e["cnpj"] == cnpj for e in listar()):
        raise ValueError("Esta empresa já está cadastrada.")
    rel = f"empresas/{cnpj}"
    destino = emissor.BASE / rel
    (destino / "dados").mkdir(parents=True, exist_ok=True)
    salvar_credenciais({k: d.get(k, "") for k in CAMPOS_ENV} | {"cnpj": cnpj, "simples": d.get("simples") or "S"}, destino)
    with open(destino / ".env", "a", encoding="utf-8") as f:
        f.write("ITABORAI_AMBIENTE=homologacao\nITABORAI_CIENTE_IRREVERSIVEL=NAO\n")
    if not (destino / "servico_padrao.json").exists():
        shutil.copy(ARQ_PADRAO_SERVICO, destino / "servico_padrao.json")
    canal = "nacional" if d.get("canal") == "nacional" else "municipal"
    cfg = {"empresa": {"nome": nome, "assinatura": nome, "pix_chave": "", "whatsapp": ""},
           "emissao": {"canal": canal, "municipio_emissor": so_digitos(d.get("municipio")) or "3301900",
                       "servico_revisado": False},
           "pastas": {"xml_nfse": "", "extratos": f"~/Downloads/Extratos/{nome}", "boletos": f"~/Downloads/Boletos/{nome}",
                      "relatorios": f"~/Downloads/Relatorios financeiros/{nome}"},
           "cobranca": {"migrado_inter": True}}
    (destino / "dados" / "config.json").write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    reg["empresas"].append({"id": cnpj, "nome": nome, "cnpj": cnpj, "pasta": rel})
    reg["ativa"] = cnpj
    _gravar(reg)
    return aplicar_ativa()


def credenciais(destino: Path | None = None) -> dict:
    """Credenciais da empresa em uso para a tela (chave mascarada)."""
    v = emissor.ler_env((destino or emissor.raiz()) / ".env")
    out = {k: v.get(var, "") for k, var in CAMPOS_ENV.items()}
    out["chave"] = SEGREDO if out["chave"] else ""
    return out


def historico(destino: Path | None = None) -> dict:
    """O que a empresa já fez (e não pode ser bagunçado por uma edição de cadastro): títulos, notas emitidas e o
    maior RPS/DPS já aceito em produção."""
    import sqlite3
    destino = Path(destino or emissor.raiz())
    tit = notas = 0
    banco = destino / "dados" / "sistema.db"
    if banco.exists():
        try:
            with sqlite3.connect(f"file:{banco}?mode=ro", uri=True) as con:
                tit = con.execute("SELECT COUNT(*) FROM titulos").fetchone()[0]
                notas = con.execute("SELECT COUNT(*) FROM titulos WHERE nfse_status='emitida'").fetchone()[0]
        except sqlite3.Error:
            pass
    maior = {"RPS": 0, "DPS": 0}
    saida = destino / "saida"
    for resumo in saida.glob("*/*/resumo.json") if saida.is_dir() else []:
        tipo, _, n = resumo.parent.name.partition("_")
        if tipo not in maior or not n.isdigit():
            continue
        try:
            r = json.loads(resumo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if r.get("sucesso") and r.get("ambiente") == "producao":
            maior[tipo] = max(maior[tipo], int(n))
            notas = max(notas, 1)
    return {"titulos": tit, "notas": notas, "maior_rps": maior["RPS"], "maior_dps": maior["DPS"]}


def _conferir_edicao(novos: dict, destino: Path) -> None:
    """Travas de segurança: o cadastro pode ser editado, mas nunca de um jeito que misture empresas ou repita nota."""
    atual = emissor.ler_env(destino / ".env")
    cnpj_novo, cnpj_atual = novos.get("ITABORAI_CNPJ"), so_digitos(atual.get("ITABORAI_CNPJ", ""))
    if cnpj_novo and cnpj_novo != cnpj_atual:
        for e, p in [(e, pasta(e)) for e in _ler()["empresas"] if pasta(e).resolve() != destino.resolve()]:
            if so_digitos(emissor.ler_env(p / ".env").get("ITABORAI_CNPJ", "")) == cnpj_novo:
                raise ValueError(f"O CNPJ {cnpj_novo} já é da empresa {e['nome']} cadastrada aqui. Os dados de uma "
                                 "empresa nunca vão para outra.")
        h = historico(destino)
        if cnpj_atual and (h["titulos"] or h["notas"]):
            raise ValueError(f"Esta empresa já tem {h['titulos']} título(s) e notas emitidas no CNPJ {cnpj_atual}. "
                             "Trocar o CNPJ misturaria esse histórico com outra empresa. Para outra empresa use "
                             "Empresas › Nova empresa.")
    rps = novos.get("ITABORAI_PROXIMO_RPS")
    if rps and rps != so_digitos(atual.get("ITABORAI_PROXIMO_RPS", "")):
        maior = historico(destino)["maior_rps"]
        if maior and int(rps) <= maior:
            raise ValueError(f"O RPS {maior} já foi usado em nota emitida em produção: o próximo RPS não pode ser "
                             f"menor que {maior + 1} (a prefeitura recusaria ou duplicaria a numeração).")


def salvar_credenciais(d: dict, destino: Path | None = None) -> dict:
    """Atualiza as credenciais no .env da empresa (mantém a chave quando vier mascarada)."""
    destino = Path(destino or emissor.raiz())
    arq = destino / ".env"
    linhas = arq.read_text(encoding="utf-8").splitlines() if arq.exists() else []
    novos = {}
    for campo, var in CAMPOS_ENV.items():
        if campo not in d or d[campo] is None or d[campo] == SEGREDO:
            continue
        valor = str(d[campo]).strip()
        if campo in ("cnpj", "im", "proximo_rps"):
            valor = so_digitos(valor)
        if campo == "cnpj" and valor and not cnpj_valido(valor):
            raise ValueError("CNPJ inválido.")
        if re.search(r"[\r\n]", valor):
            raise ValueError("Valor inválido.")
        if campo == "chave":                      # chave do webservice guardada protegida no .env
            from . import segredos
            valor = segredos.proteger(valor)
        novos[var] = valor
    _conferir_edicao(novos, destino)
    feitos = set()
    for i, linha in enumerate(linhas):
        k = linha.split("=", 1)[0].strip()
        if k in novos:
            linhas[i] = f"{k}={novos[k]}"
            feitos.add(k)
    linhas += [f"{k}={v}" for k, v in novos.items() if k not in feitos and v != ""]
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return credenciais(destino)


def proteger_senhas() -> int:
    """Protege as senhas ainda gravadas em texto (versões anteriores) em todas as empresas deste computador."""
    from . import config, segredos
    n = 0
    for e in listar():
        p = pasta(e)
        with emissor.usar_empresa(p):
            arq = p / "dados" / "config.json"
            if arq.exists():
                bruto = json.loads(arq.read_text(encoding="utf-8"))
                if any(bruto.get(sec, {}).get(campo) and not segredos.protegido(bruto[sec][campo])
                       for sec, campo in config.SEGREDOS):
                    config.salvar({})
                    n += 1
            chave = emissor.ler_env(p / ".env").get("ITABORAI_CHAVE", "")
            if chave and not segredos.protegido(chave):
                salvar_credenciais({"chave": chave}, p)
                n += 1
    return n


def salvar_servico(d: dict) -> dict:
    """Serviço da empresa em uso: com id/nome altera ou cria um serviço do catálogo; sem, altera o padrão."""
    from . import servicos
    if d.get("id") or d.get("nome"):
        return servicos.salvar(d)
    return servicos.salvar({**servicos.padrao(), **{k: v for k, v in d.items() if k in servicos.CAMPOS}})


# ---------------------------------------------------------------- isolamento de credenciais

EXCLUSIVOS = {  # (seção, campo) da configuração que nunca pode ser igual ao de outra empresa
    ("cobranca", "inter_client_id"): "credencial da API do Banco Inter",
    ("empresa", "pix_chave"): "chave PIX",
    ("smtp", "usuario"): "conta de e-mail de envio",
}
PASTA_CERT = Path("dados") / "certificados"


def _outras() -> list[tuple[dict, Path]]:
    propria = emissor.raiz().resolve()
    return [(e, pasta(e)) for e in _ler()["empresas"] if pasta(e).resolve() != propria]


def _cfg_de(p: Path) -> dict:
    try:
        return json.loads((p / "dados" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _digest(arq: Path) -> str:
    import hashlib
    return hashlib.sha256(arq.read_bytes()).hexdigest() if arq.is_file() else ""


def verificar_exclusividade(novo: dict | None = None, arquivo: bytes | None = None) -> None:
    """Recusa credenciais (API, PIX, e-mail, certificados) já usadas por outra empresa cadastrada."""
    import hashlib
    dig = hashlib.sha256(arquivo).hexdigest() if arquivo else ""
    for e, p in _outras():
        cfg = _cfg_de(p)
        for (sec, campo), rotulo in EXCLUSIVOS.items():
            v = str((novo or {}).get(sec, {}).get(campo, "") or "").strip().lower()
            if v and v != SEGREDO and v == str(cfg.get(sec, {}).get(campo, "") or "").strip().lower():
                raise ValueError(f"Esta {rotulo} já pertence à empresa {e['nome']}. Os dados de uma empresa "
                                 "não podem ser usados por outra.")
        if dig and any(_digest(a) == dig for a in (p / PASTA_CERT).glob("*")):
            raise ValueError(f"Este arquivo já está cadastrado na empresa {e['nome']}. Certificados e chaves "
                             "não podem ser compartilhados entre empresas.")


def _guardar(nome: str, conteudo: bytes) -> str:
    destino = emissor.raiz() / PASTA_CERT
    destino.mkdir(parents=True, exist_ok=True)
    (destino / nome).write_bytes(conteudo)
    return str(PASTA_CERT / nome).replace("\\", "/")


def enviar_certificado(arquivo_b64: str, senha: str) -> dict:
    """Recebe o .pfx pela tela, confere a senha e o CNPJ e guarda só na pasta desta empresa."""
    import base64
    from cryptography.hazmat.primitives.serialization import pkcs12
    from . import config, nacional
    dados = base64.b64decode(arquivo_b64.split(",")[-1] or b"")
    try:
        _, cert, _ = pkcs12.load_key_and_certificates(dados, senha.encode() or None)
    except ValueError as ex:
        raise ValueError("Senha incorreta ou arquivo que não é um certificado A1 (.pfx).") from ex
    from cryptography.x509.oid import NameOID
    cn = (cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME) or [None])[0]
    m = re.search(r":(\d{14})\b", cn.value if cn else "")
    cnpj = so_digitos(emissor.env("ITABORAI_CNPJ"))
    if m and cnpj and m.group(1)[:8] != cnpj[:8]:
        raise ValueError(f"Este certificado é do CNPJ {m.group(1)}, mas a empresa em uso é {cnpj}.")
    verificar_exclusividade(arquivo=dados)
    rel = _guardar("certificado-a1.pfx", dados)
    config.salvar({"emissao": {"certificado_pfx": rel, "certificado_senha": senha}})
    return nacional.info_certificado()


def enviar_arquivo_inter(tipo: str, arquivo_b64: str) -> dict:
    """Recebe o .crt ou o .key da integração do Inter e guarda só na pasta desta empresa."""
    import base64
    from . import config
    if tipo not in ("crt", "key"):
        raise ValueError("Tipo de arquivo inválido.")
    dados = base64.b64decode(arquivo_b64.split(",")[-1] or b"")
    marca = b"PRIVATE KEY" if tipo == "key" else b"CERTIFICATE"
    if marca not in dados:
        raise ValueError("Arquivo inválido: selecione o " + (".key (chave privada)" if tipo == "key" else ".crt (certificado)")
                         + " gerado na integração do Inter.")
    verificar_exclusividade(arquivo=dados)
    rel = _guardar(f"inter.{tipo}", dados)
    config.salvar({"cobranca": {"inter_certificado" if tipo == "crt" else "inter_chave": rel}})
    return {"ok": True, "arquivo": rel}
