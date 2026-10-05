"""Traz configurações e dados de uma instalação anterior do sistema (outra pasta no mesmo computador).

Procura pastas com o sistema (nfse_itaborai) nas pastas do usuário, mostra o que cada uma tem e copia para a versão
atual SOMENTE o que estiver vazio aqui: credenciais do .env, configurações (e-mail, Banco Inter, PIX...), clientes,
banco financeiro (se o atual estiver vazio), numeração, certificados e empresas. A pasta antiga só é lida, nunca
alterada ou apagada.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
from pathlib import Path

from . import clientes, config, db, emissor

PULAR = {"appdata", "node_modules", ".git", "__pycache__", "windows", "program files", "program files (x86)",
         "$recycle.bin", "onedrive - personal", ".cache", "site-packages", "importados", "saida"}
SEGREDOS_ENV = {"ITABORAI_CHAVE"}


def _raizes() -> list[Path]:
    casa = Path.home()
    out = [emissor.BASE.parent]
    for nome in ("Downloads", "Desktop", "Área de Trabalho", "Documents", "Documentos", "OneDrive"):
        p = casa / nome
        if p.is_dir():
            out.append(p)
    out.append(casa)
    return out


def localizar(profundidade: int = 4) -> list[Path]:
    """Pastas de outras instalações do sistema (com nfse_itaborai/ e .env ou dados/)."""
    atual = emissor.BASE.resolve()
    achadas: dict[str, Path] = {}
    for raiz in _raizes():
        base_niveis = len(raiz.parts)
        for pasta, subdirs, _ in os.walk(raiz):
            p = Path(pasta)
            if len(p.parts) - base_niveis >= profundidade:
                subdirs[:] = []
            subdirs[:] = [d for d in subdirs if d.lower() not in PULAR and not d.startswith(".")]
            if (p / "nfse_itaborai").is_dir() and ((p / ".env").exists() or (p / "dados").is_dir()):
                if p.resolve() != atual:
                    achadas[str(p.resolve())] = p.resolve()
                subdirs[:] = []
    return sorted(achadas.values(), key=lambda x: -(_mtime(x)))


def _cnpj(pasta: Path) -> str:
    return clientes._digitos(emissor.ler_env(Path(pasta) / ".env").get("ITABORAI_CNPJ", ""))


def mesma_empresa(pasta: Path) -> bool:
    """Só é 'versão anterior' a instalação do MESMO CNPJ desta. Outra empresa no mesmo computador (ex.: a instalação
    de um cliente do escritório) nunca é misturada com esta — nem nome, nem credenciais, nem clientes."""
    aqui = _cnpj(emissor.BASE)
    return bool(aqui) and _cnpj(pasta) == aqui


def _mtime(p: Path) -> float:
    try:
        return max(f.stat().st_mtime for f in [p / ".env", p / "dados"] if f.exists())
    except ValueError:
        return 0


def _cfg(p: Path) -> dict:
    try:
        return json.loads((p / "dados" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _qtd_titulos(arq: Path) -> int:
    if not arq.exists():
        return 0
    try:
        with sqlite3.connect(f"file:{arq}?mode=ro", uri=True) as con:
            return con.execute("SELECT COUNT(*) FROM titulos").fetchone()[0]
    except sqlite3.Error:
        return 0


def resumo(pasta: Path) -> dict:
    """O que a instalação antiga tem e que ainda FALTA nesta versão (só isso é oferecido)."""
    env = emissor.ler_env(pasta / ".env")
    c = _cfg(pasta)
    with emissor.usar_empresa(emissor.BASE):
        atual_env, atual = emissor.ler_env(emissor.raiz() / ".env"), config.carregar()
        atuais_cli = {x["cpf_cnpj"] for x in clientes.listar()}
        titulos_aqui = _qtd_titulos(db.caminho())
    falta = lambda sec, campo: bool(str(c.get(sec, {}).get(campo, "") or "").strip()) \
        and not str(atual.get(sec, {}).get(campo, "") or "").strip()  # noqa: E731
    try:
        antigos = json.loads((pasta / "dados" / "clientes.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        antigos = []
    novos_cli = len({clientes._digitos(x.get("cpf_cnpj")) for x in antigos} - atuais_cli - {""})
    tit = _qtd_titulos(pasta / "dados" / "sistema.db")
    reg_a = pasta / "empresas.json"
    outras = len([e for e in json.loads(reg_a.read_text(encoding="utf-8")).get("empresas", []) if e["pasta"] != "."]) \
        if reg_a.exists() else 0
    itens = {
        "Credenciais da prefeitura": bool(env.get("ITABORAI_CHAVE")) and not atual_env.get("ITABORAI_CHAVE"),
        "E-mail de envio (SMTP)": falta("smtp", "host"),
        "Banco Inter": falta("cobranca", "inter_client_id"),
        "Chave PIX": falta("empresa", "pix_chave"),
        "E-mail do dono": falta("resumo", "email_dono"),
        "Certificado digital": falta("emissao", "certificado_pfx"),
        f"{novos_cli} cliente(s) que não estão aqui": novos_cli > 0,
        f"Financeiro ({tit} títulos)": tit > 0 and not titulos_aqui,
        f"{outras} outra(s) empresa(s)": outras > 0,
    }
    return {"pasta": str(pasta), "itens": {k: v for k, v in itens.items() if v},
            "ambiente_producao": env.get("ITABORAI_AMBIENTE", "").lower() == "producao"}


def procurar() -> list[dict]:
    return [r for r in (resumo(p) for p in localizar() if mesma_empresa(p)) if r["itens"]]


def _vazio(v) -> bool:
    return v in (None, "", [], {}) or v == "••••••"


# Campos que podem vir da versão antiga (lista fechada: nada que tenha sido mudado de propósito na versão nova,
# como o meio de cobrança, a pasta de XML em Downloads ou integrações de terceiros removidas).
CAMPOS = {
    "empresa": ("nome", "pix_chave", "pix_cidade", "whatsapp", "assinatura"),
    "smtp": ("host", "porta", "usuario", "senha", "remetente", "ssl", "copia_para"),
    "resumo": ("email_dono", "dia_fechamento"),
    "emissao": ("canal", "certificado_pfx", "certificado_senha", "serie_dps", "municipio_emissor", "op_simp_nac",
                "reg_ap_trib_sn", "reg_esp_trib"),
    "cobranca": ("inter_client_id", "inter_client_secret", "inter_certificado", "inter_chave", "inter_conta",
                 "inter_sandbox", "multa_pct", "juros_mes_pct", "regua_dias", "bloquear_apos_dias"),
    "financeiro": ("dia_vencimento_padrao", "prazo_avulso_dias", "dia_geracao", "aliquota_simples_pct", "iss_fixo",
                   "iss_fixo_mensal", "contas_bancarias", "inicio_financeiro"),
}


def _completar(atual: dict, antigo: dict, padrao: dict) -> dict:
    """Valores do antigo, dentro da lista CAMPOS, só onde o atual está vazio ou ainda no padrão de fábrica."""
    novo: dict = {}
    for sec, campos in CAMPOS.items():
        for k in campos:
            v = antigo.get(sec, {}).get(k)
            if _vazio(v):
                continue
            a, p = atual.get(sec, {}).get(k), padrao.get(sec, {}).get(k)
            if _vazio(a) or (a == p and v != p):
                novo.setdefault(sec, {})[k] = v
    return novo


def _trazer_arquivo(origem: Path, caminho: str, destino: Path) -> str:
    """Copia um arquivo sensível (certificado, chave do banco) para dados/certificados desta empresa."""
    p = Path(os.path.expanduser(str(caminho)))
    p = p if p.is_absolute() else origem / p
    if not p.is_file():
        return ""
    alvo = destino / "dados" / "certificados" / p.name
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if not alvo.exists():
        shutil.copy2(p, alvo)
    return f"dados/certificados/{p.name}"


def importar(pasta: str) -> dict:
    """Copia da instalação antiga o que falta na atual (empresa original)."""
    origem = Path(pasta).resolve()
    if origem not in localizar() and not (origem / "nfse_itaborai").is_dir():
        raise ValueError("Pasta não reconhecida como uma instalação do sistema.")
    if not mesma_empresa(origem):
        raise ValueError(f"A instalação em {origem} é de outra empresa (CNPJ {_cnpj(origem) or 'não informado'}): "
                         "os dados de uma empresa nunca são copiados para outra.")
    feitos = []
    with emissor.usar_empresa(emissor.BASE):
        try:                                   # ponto de volta: o reparo (e você) sempre têm o "antes" exato
            from . import backup
            backup.criar("antes_da_versao_anterior", emissor.BASE)
        except Exception:  # noqa: BLE001 - backup não impede a importação
            pass
        destino = emissor.raiz()
        # .env: chaves ausentes; numeração do RPS pelo maior valor
        antigo_env, atual_env = emissor.ler_env(origem / ".env"), emissor.ler_env(destino / ".env")
        linhas = (destino / ".env").read_text(encoding="utf-8").splitlines() if (destino / ".env").exists() else []
        for k, v in antigo_env.items():
            if k in ("ITABORAI_AMBIENTE", "ITABORAI_CIENTE_IRREVERSIVEL"):
                continue  # produção é decisão do usuário (irreversível na prefeitura): nunca ligada por cópia
            if k == "ITABORAI_PROXIMO_RPS" and atual_env.get(k, "").isdigit() and v.isdigit():
                v = str(max(int(v), int(atual_env[k])))
                linhas = [l for l in linhas if not l.startswith(k + "=")]
            elif atual_env.get(k):
                continue
            linhas.append(f"{k}={v}")
            feitos.append(f".env: {k}")
        (destino / ".env").write_text("\n".join(linhas) + "\n", encoding="utf-8")
        # configurações (e-mail, Inter, PIX, régua, pastas...)
        antigo_cfg = _cfg(origem)
        novo = _completar(config.carregar(), antigo_cfg, config.PADRAO)
        for sec, campo in (("emissao", "certificado_pfx"), ("cobranca", "inter_certificado"), ("cobranca", "inter_chave")):
            if campo in novo.get(sec, {}):
                rel = _trazer_arquivo(origem, novo[sec][campo], destino)
                if rel:
                    novo[sec][campo] = rel
                else:
                    novo[sec].pop(campo)
        if novo:
            config.salvar(novo)
            feitos += [f"configuração: {sec}" for sec in novo]
        # certificados e arquivos do banco guardados na pasta da empresa
        for arq in (origem / "dados" / "certificados").glob("*") if (origem / "dados" / "certificados").is_dir() else []:
            alvo = destino / "dados" / "certificados" / arq.name
            if not alvo.exists():
                alvo.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(arq, alvo)
                feitos.append(f"arquivo: {arq.name}")
        # clientes que faltam
        try:
            antigos = json.loads((origem / "dados" / "clientes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            antigos = []
        atuais = {c["cpf_cnpj"] for c in clientes.listar()}
        novos = [c for c in antigos if clientes._digitos(c.get("cpf_cnpj")) not in atuais]
        for c in novos:
            clientes.salvar(c)
        if novos:
            feitos.append(f"{len(novos)} cliente(s)")
        # banco financeiro: só se o atual ainda não tem títulos
        db_antigo, db_atual = origem / "dados" / "sistema.db", db.caminho()
        if _qtd_titulos(db_antigo) and not _qtd_titulos(db_atual):
            if db_atual.exists():
                shutil.copy2(db_atual, db_atual.with_name("sistema_antes_da_migracao.db"))
            with sqlite3.connect(f"file:{db_antigo}?mode=ro", uri=True) as src, sqlite3.connect(db_atual) as dst:
                src.backup(dst)
            feitos.append(f"financeiro: {_qtd_titulos(db_atual)} título(s)")
        # numeração local (RPS/lote/DPS): maior valor
        seq_a, seq_n = origem / "dados" / "sequencia.json", destino / "dados" / "sequencia.json"
        if seq_a.exists():
            a = json.loads(seq_a.read_text(encoding="utf-8"))
            n = json.loads(seq_n.read_text(encoding="utf-8")) if seq_n.exists() else {}
            junto = {k: max(int(a.get(k, 0) or 0), int(n.get(k, 0) or 0)) for k in set(a) | set(n)}
            if junto != n:
                seq_n.parent.mkdir(parents=True, exist_ok=True)
                seq_n.write_text(json.dumps(junto, indent=2), encoding="utf-8")
                feitos.append("numeração")
    # outras empresas cadastradas na versão antiga
    reg_a = origem / "empresas.json"
    if reg_a.exists():
        from . import empresas
        reg = empresas._ler()
        for e in json.loads(reg_a.read_text(encoding="utf-8")).get("empresas", []):
            if e["pasta"] == "." or any(x["cnpj"] == e["cnpj"] for x in reg["empresas"]):
                continue
            if (origem / e["pasta"]).is_dir() and not (emissor.BASE / e["pasta"]).exists():
                shutil.copytree(origem / e["pasta"], emissor.BASE / e["pasta"])
                reg["empresas"].append(e)
                feitos.append(f"empresa: {e['nome']}")
        empresas._gravar(reg)
    db.registrar("migracao", f"Importado de {origem}: {', '.join(feitos) or 'nada novo'}")
    return {"pasta": str(origem), "importado": feitos}


# ---------------------------------------------------------------- reparo: dados de outra empresa trazidos por engano
# Até a versão 3.8.3, "Versão anterior encontrada" não conferia o CNPJ: a instalação de OUTRA empresa no mesmo
# computador podia ser trazida, e o nome de fábrica (que era o de um escritório) era tratado como "padrão" e trocado.

def _importacoes() -> list[dict]:
    out = []
    for r in db.linhas("SELECT quando, mensagem FROM log WHERE tipo='migracao' AND mensagem LIKE 'Importado de %' ORDER BY id"):
        pasta = r["mensagem"][len("Importado de "):].split(": ", 1)[0]
        out.append({"quando": r["quando"], "pasta": pasta, "detalhe": r["mensagem"]})
    return out


def misturas() -> list[dict]:
    """Importações feitas de uma instalação de OUTRO CNPJ e ainda não reparadas."""
    aqui = _cnpj(emissor.BASE)
    reparadas = {r["mensagem"].split("|", 1)[1] for r in db.linhas(
        "SELECT mensagem FROM log WHERE tipo='migracao_reparo' AND mensagem LIKE 'reparado|%'")}
    out = []
    for i in _importacoes():
        p = Path(i["pasta"])
        cnpj = _cnpj(p) if p.is_dir() else ""
        if p.is_dir() and aqui and cnpj != aqui and f"{i['pasta']}|{i['quando']}" not in reparadas:
            out.append(i | {"cnpj": cnpj, "nome": _cfg(p).get("empresa", {}).get("nome", "")})
    return out


def _backups() -> list[tuple[str, dict, list, dict, set]]:
    """(criado_em, config, clientes, .env, certificados) de cada backup .zip desta instalação, do mais novo ao mais velho."""
    import io
    import zipfile
    from . import backup, segredos
    out = []
    senha = None
    for arq in sorted(backup._backups(emissor.BASE), key=lambda a: a.name, reverse=True):
        try:
            if arq.suffix == backup.EXT_PROTEGIDO:          # backup com senha: abre com a senha de backup desta empresa
                senha = backup._senha_backup(emissor.BASE) if senha is None else senha
                if not senha:
                    continue
                fonte = io.BytesIO(segredos.decifrar_com_senha(arq.read_bytes(), senha))
            else:
                fonte = arq
            with zipfile.ZipFile(fonte) as z:
                nomes = z.namelist()
                m = json.loads(z.read(backup.MANIFESTO))
                cfg = json.loads(z.read("dados/config.json")) if "dados/config.json" in nomes else {}
                cli = json.loads(z.read("dados/clientes.json")) if "dados/clientes.json" in nomes else []
                env = {}
                if ".env" in nomes:
                    for linha in z.read(".env").decode("utf-8").splitlines():
                        if "=" in linha and not linha.lstrip().startswith("#"):
                            k, v = linha.split("=", 1)
                            env[k.strip()] = v.strip()
                certs = {n.rsplit("/", 1)[-1] for n in nomes if n.startswith("dados/certificados/")}
                out.append((m.get("criado_em") or "", cfg, cli, env, certs))
        except Exception:  # noqa: BLE001 - backup ilegível (senha trocada, arquivo corrompido): só não serve de fonte
            continue
    return out


def _backup_antes(quando: str) -> tuple[dict, list, dict, set] | None:
    """config, clientes, .env e certificados do backup .zip mais recente feito ANTES da importação."""
    for criado, cfg, cli, env, certs in _backups():
        if criado and criado < quando:
            return cfg, cli, env, certs
    return None


def _pelas_notas(cnpj: str) -> dict:
    """Canal, município e razão social desta empresa segundo as notas AUTORIZADAS (prefeitura/Sefin) para o CNPJ dela."""
    from collections import Counter
    from . import importador
    pastas = [emissor.BASE / "saida", emissor.BASE / importador.NOME_PASTA / "importados" / cnpj]
    dados = []
    for pasta in pastas:
        for arq in (pasta.rglob("NFSe_*.xml") if pasta.name == "saida" else pasta.glob("*.xml")) if pasta.is_dir() else []:
            raiz = importador._ler(arq)
            if raiz is not None and importador._prestador(raiz)[0] == cnpj:
                dados.append(importador.empresa_de_xml(raiz))
    if not dados:
        return {}
    freq = lambda campo: (Counter(d[campo] for d in dados if d.get(campo)).most_common(1) or [("", 0)])[0][0]  # noqa: E731
    canal = freq("canal")
    cmun = freq("cmun") if canal == "nacional" else "3301900"      # canal municipal = webservice de Itaboraí
    return {k: v for k, v in {"empresa": {"nome": freq("nome")}, "emissao": {"canal": canal, "municipio_emissor": cmun}}.items()}


def _pelo_certificado(cnpj: str, cfgs: list[dict]) -> str:
    """Razão social do certificado A1 (CN = 'RAZAO SOCIAL:CNPJ') desta empresa, se algum dos .pfx conhecidos for dela."""
    try:
        from . import nacional
    except ImportError:  # pragma: no cover
        return ""
    for c in cfgs:
        if not c.get("emissao", {}).get("certificado_pfx"):
            continue
        try:
            cert = nacional.carregar_certificado(c)
        except Exception:  # noqa: BLE001 - qualquer falha: só não serve de fonte
            continue
        if cert.cnpj == cnpj:
            return cert.titular.rsplit(":", 1)[0].strip()
    return ""


def fontes_proprias(quando: str = "") -> list[tuple[bool, dict]]:
    """Configurações desta empresa vindas de fontes que NÃO passaram pela mistura, da mais confiável à menos:
    backup anterior à importação, os demais backups, outras instalações do MESMO CNPJ, as notas autorizadas e o
    certificado A1 deste CNPJ. Cada item: (anterior_a_importacao, config). Só o backup anterior à importação é
    prova de que um valor igual ao da outra empresa também era desta; nas demais fontes ele é ignorado."""
    aqui = _cnpj(emissor.BASE)
    bks = _backups()
    antes = [b for b in bks if quando and b[0] and b[0] < quando]
    depois = [b for b in bks if b not in antes]
    desta = lambda b: clientes._digitos(b[3].get("ITABORAI_CNPJ", "")) in ("", aqui)  # noqa: E731
    fontes = [(True, _aberto(b[1])) for b in antes if desta(b)] + [(False, _aberto(b[1])) for b in depois if desta(b)]
    fontes += [(False, _aberto(_cfg(p))) for p in localizar() if mesma_empresa(p)]
    fontes.append((False, _pelas_notas(aqui)))
    nome = _pelo_certificado(aqui, [c for _, c in fontes if c] + [config.carregar()])
    if nome:
        fontes.append((False, {"empresa": {"nome": nome}}))
    return [(a, f) for a, f in fontes if f]


GENERICAS = {"LTDA", "EIRELI", "UNIPESSOAL", "EPP", "SOCIEDADE", "SERVICOS", "CONTABILIDADE", "CONTABIL", "ASSESSORIA",
             "CONSULTORIA", "COMERCIO", "CLINICA", "PSICOLOGIA", "ADVOCACIA", "ADVOGADOS", "ASSOCIADOS", "DOS", "DAS", "DES"}


def _palavras(nome: str) -> set[str]:
    import re
    import unicodedata
    s = unicodedata.normalize("NFKD", nome or "").encode("ascii", "ignore").decode().upper().replace("&", " E ")
    return {w for w in re.findall(r"[A-Z0-9]+", s) if len(w) > 2 and w not in GENERICAS}


def identidade() -> dict | None:
    """Confere o nome da empresa com a razão social OFICIAL deste CNPJ (certificado A1 dele ou notas do Emissor
    Nacional). Nome sem nenhuma palavra em comum com o oficial = nome de outra empresa: o Painel avisa."""
    aqui = _cnpj(emissor.BASE)
    if not aqui:
        return None
    with emissor.usar_empresa(emissor.BASE):
        cfg = config.carregar()
        oficial, fonte = _pelo_certificado(aqui, [cfg]), "certificado digital"
        if not oficial:
            oficial, fonte = _pelas_notas(aqui).get("empresa", {}).get("nome", ""), "notas autorizadas"
    nome = cfg["empresa"].get("nome", "")
    if not oficial or not nome or _palavras(nome) & _palavras(oficial) or not _palavras(oficial):
        return None
    return {"nome": nome, "oficial": oficial, "fonte": fonte, "cnpj": aqui}


def usar_nome_oficial() -> dict:
    """Troca o nome (e a assinatura, se era o mesmo nome) pela razão social oficial deste CNPJ."""
    i = identidade()
    if not i:
        raise ValueError("O nome da empresa já confere com a razão social oficial.")
    with emissor.usar_empresa(emissor.BASE):
        emp = config.carregar()["empresa"]
        novo = {"nome": i["oficial"]} | ({"assinatura": i["oficial"]} if emp.get("assinatura") in ("", i["nome"]) else {})
        config.salvar({"empresa": novo})
        db.registrar("migracao", f"Nome da empresa corrigido de '{i['nome']}' para '{i['oficial']}' ({i['fonte']})")
    return {"nome": i["oficial"]}


# Dados que identificam a outra empresa: se não houver fonte com o valor desta, ficam VAZIOS (para você preencher),
# nunca com o da outra.
IDENTIFICAM = {("empresa", "nome"), ("empresa", "pix_chave"), ("empresa", "pix_cidade"), ("empresa", "whatsapp"),
               ("empresa", "assinatura"), ("smtp", "usuario"), ("smtp", "senha"), ("smtp", "remetente"),
               ("smtp", "copia_para"), ("resumo", "email_dono"), ("emissao", "certificado_pfx"),
               ("emissao", "certificado_senha"), ("cobranca", "inter_client_id"), ("cobranca", "inter_client_secret"),
               ("cobranca", "inter_certificado"), ("cobranca", "inter_chave"), ("cobranca", "inter_conta"),
               ("financeiro", "contas_bancarias")}


def _aberto(cfg: dict) -> dict:
    from . import segredos
    c = json.loads(json.dumps(cfg))
    for sec, campo in config.SEGREDOS:
        if campo in c.get(sec, {}):
            c[sec][campo] = segredos.revelar(c[sec][campo])
    return c


def reparar() -> dict:
    """Desfaz o que veio da outra empresa e TRAZ DE VOLTA os dados desta. Só mexe no que ainda está IGUAL ao da outra
    instalação (o que você mudou depois fica como está). O valor certo vem de fontes_proprias(): backups, outras
    instalações do mesmo CNPJ, notas autorizadas e certificado A1 deste CNPJ. Dado que identifica a outra empresa
    (nome, PIX, e-mail, banco, certificado) sem fonte desta fica vazio, nunca com o da outra. Clientes da outra
    empresa saem do cadastro, desde que não tenham títulos nem notas aqui."""
    feito: list[str] = []
    pendente: list[str] = []
    for m in misturas():
        origem = Path(m["pasta"])
        outra_cfg, outra_env = _aberto(_cfg(origem)), emissor.ler_env(origem / ".env")
        try:
            outra_cli = json.loads((origem / "dados" / "clientes.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            outra_cli = []
        bk = _backup_antes(m["quando"])
        with emissor.usar_empresa(emissor.BASE):
            atual = config.carregar()
            fontes = fontes_proprias(m["quando"])
            volta: dict = {}
            for sec, campos in CAMPOS.items():
                for k in campos:
                    a, o = atual.get(sec, {}).get(k), outra_cfg.get(sec, {}).get(k)
                    if _vazio(o) or a != o:
                        continue                                  # não veio da outra (ou já foi corrigido)
                    certo = next((v for antes_da, f in fontes if not _vazio(v := f.get(sec, {}).get(k))
                                  and (antes_da or v != o)), None)
                    if sec == "empresa" and k == "assinatura" and certo is None:
                        certo = volta.get("empresa", {}).get("nome") or certo
                    if certo is not None and certo == a:
                        continue                                  # esta empresa usa o mesmo valor (ex.: smtp.gmail.com)
                    if certo is not None:
                        volta.setdefault(sec, {})[k] = certo
                        feito.append(f"{sec}.{k}: {o!s:.40} → {certo!s:.40}")
                    elif (sec, k) in IDENTIFICAM:
                        volta.setdefault(sec, {})[k] = [] if isinstance(o, list) else ""
                        pendente.append(f"{sec}.{k}: o valor da outra empresa foi apagado — preencha com o desta")
                    else:
                        pendente.append(f"{sec}.{k} = {o!s:.40} (veio da outra empresa; confira)")
            if volta:
                config.salvar(volta)
            # .env: chaves acrescentadas pela importação
            arq = emissor.BASE / ".env"
            linhas = arq.read_text(encoding="utf-8").splitlines() if arq.exists() else []
            env_atual = emissor.ler_env(arq)
            env_antes = bk[2] if bk else None
            novas = []
            for linha in linhas:
                k = linha.split("=", 1)[0].strip()
                v = env_atual.get(k)
                if k in outra_env and v == outra_env[k] and k not in ("ITABORAI_PROXIMO_RPS", "ITABORAI_PROXIMO_LOTE") \
                        and env_antes is not None and k not in env_antes and "=" in linha:
                    feito.append(f".env: {k} removido (era da outra empresa)")
                    continue
                novas.append(linha)
            if novas != linhas:
                arq.write_text("\n".join(novas) + "\n", encoding="utf-8")
            # clientes da outra empresa
            antes_cli = {clientes._digitos(c.get("cpf_cnpj")) for c in (bk[1] if bk else [])}
            com_titulo = {r["cpf_cnpj"] for r in db.linhas("SELECT DISTINCT cpf_cnpj FROM titulos")}
            tirados = 0
            for c in outra_cli:
                doc = clientes._digitos(c.get("cpf_cnpj"))
                aqui_c = clientes.obter(doc) if doc else None
                ident = lambda x: ((x.get("razao_social") or "").strip().upper(), (x.get("email") or "").strip().lower())  # noqa: E731
                copia = bool(aqui_c) and (bool(bk) or ident(aqui_c) == ident(c))   # sem backup: só a cópia idêntica
                if doc and doc not in antes_cli and doc not in com_titulo and copia:
                    clientes.excluir(doc)
                    tirados += 1
            if tirados:
                feito.append(f"{tirados} cliente(s) da outra empresa retirados do cadastro")
            # certificados copiados da outra instalação
            for arq_c in (origem / "dados" / "certificados").glob("*") if (origem / "dados" / "certificados").is_dir() else []:
                aqui = emissor.BASE / "dados" / "certificados" / arq_c.name
                if aqui.exists() and (not bk or arq_c.name not in bk[3]) and aqui.read_bytes() == arq_c.read_bytes():
                    aqui.unlink()
                    feito.append(f"arquivo {arq_c.name} da outra empresa apagado")
        db.registrar("migracao_reparo", f"reparado|{m['pasta']}|{m['quando']}")
        db.registrar("migracao", f"Reparo dos dados trazidos de {m['pasta']} (CNPJ {m['cnpj']}): "
                     + ("; ".join(feito) or "nada a desfazer") + (f" — sem backup anterior: {'; '.join(pendente)}" if pendente else ""))
    return {"desfeito": feito, "conferir": pendente}


# ---------------------------------------------------------------- dados cadastrais: trazer de uma versão anterior
# Só os DADOS DA EMPRESA (identificação, canal, município, PIX, e-mail, banco, regras de cobrança). Nunca mexe no
# que já foi feito: notas emitidas, títulos, faturamento, clientes, contratos, numeração de RPS/DPS.

ROTULOS = {
    "empresa.nome": "Razão social", "empresa.assinatura": "Assinatura das mensagens", "empresa.pix_chave": "Chave PIX",
    "empresa.pix_cidade": "Cidade (PIX)", "empresa.whatsapp": "WhatsApp", "smtp.host": "E-mail: servidor",
    "smtp.porta": "E-mail: porta", "smtp.usuario": "E-mail: usuário", "smtp.senha": "E-mail: senha",
    "smtp.remetente": "E-mail: remetente", "smtp.ssl": "E-mail: SSL", "smtp.copia_para": "E-mail: cópia para",
    "resumo.email_dono": "E-mail do dono", "resumo.dia_fechamento": "Dia do fechamento",
    "emissao.canal": "Canal de emissão", "emissao.certificado_pfx": "Certificado A1",
    "emissao.certificado_senha": "Senha do certificado", "emissao.serie_dps": "Série da DPS",
    "emissao.municipio_emissor": "Município (IBGE)", "emissao.op_simp_nac": "Situação no Simples",
    "emissao.reg_ap_trib_sn": "Apuração no Simples", "emissao.reg_esp_trib": "Regime especial",
    "cobranca.inter_client_id": "Inter: client id", "cobranca.inter_client_secret": "Inter: client secret",
    "cobranca.inter_certificado": "Inter: certificado", "cobranca.inter_chave": "Inter: chave",
    "cobranca.inter_conta": "Inter: conta", "cobranca.inter_sandbox": "Inter: sandbox", "cobranca.multa_pct": "Multa (%)",
    "cobranca.juros_mes_pct": "Juros ao mês (%)", "cobranca.regua_dias": "Régua de cobrança (dias)",
    "cobranca.bloquear_apos_dias": "Atraso crítico (dias)", "financeiro.dia_vencimento_padrao": "Dia de vencimento",
    "financeiro.prazo_avulso_dias": "Prazo do avulso (dias)", "financeiro.dia_geracao": "Dia de geração",
    "financeiro.aliquota_simples_pct": "Alíquota do Simples (%)", "financeiro.iss_fixo": "ISS fixo",
    "financeiro.iss_fixo_mensal": "ISS fixo mensal", "financeiro.contas_bancarias": "Contas bancárias",
    "financeiro.inicio_financeiro": "Início do financeiro",
    "env.ITABORAI_IM": "Inscrição municipal", "env.ITABORAI_IE": "Inscrição estadual",
    "env.ITABORAI_SIMPLES": "Optante do Simples", "env.ITABORAI_CHAVE": "Chave do webservice",
}
ENV_DADOS = ("ITABORAI_IM", "ITABORAI_IE", "ITABORAI_SIMPLES", "ITABORAI_CHAVE")
OCULTOS = {f"{s}.{c}" for s, c in config.SEGREDOS} | {"env.ITABORAI_CHAVE"}


def _versao_de(pasta: Path) -> str:
    import re
    try:
        m = re.search(r'__version__\s*=\s*"([^"]+)"', (pasta / "nfse_itaborai" / "__init__.py").read_text(encoding="utf-8"))
        return m.group(1) if m else ""
    except OSError:
        return ""


def _valores(cfg: dict, env: dict) -> dict:
    out = {f"{s}.{k}": cfg.get(s, {}).get(k) for s, ks in CAMPOS.items() for k in ks}
    out |= {f"env.{k}": env.get(k, "") for k in ENV_DADOS}
    from . import segredos
    if out.get("env.ITABORAI_CHAVE"):
        out["env.ITABORAI_CHAVE"] = segredos.revelar(out["env.ITABORAI_CHAVE"])
    return out


def _fontes_cadastro() -> list[dict]:
    """Versões anteriores que trabalharam com os dados DESTA empresa (mesmo CNPJ), da mais recente à mais antiga:
    outras instalações no computador e os backups desta instalação."""
    from datetime import datetime
    aqui = _cnpj(emissor.BASE)
    nomes_outras = {(_cfg(p).get("empresa", {}).get("nome") or "").strip().upper()
                    for p in localizar() if _cnpj(p) and _cnpj(p) != aqui} - {""}
    fontes = []
    for p in localizar():
        if mesma_empresa(p):
            fontes.append({"id": f"inst:{p}", "tipo": "Instalação", "origem": str(p), "versao": _versao_de(p),
                           "quando": datetime.fromtimestamp(_mtime(p)).strftime("%Y-%m-%d %H:%M:%S"),
                           "valores": _valores(_aberto(_cfg(p)), emissor.ler_env(p / ".env"))})
    for criado, cfg, _cli, env, _certs in _backups():
        if clientes._digitos(env.get("ITABORAI_CNPJ", "")) in ("", aqui) and cfg:
            fontes.append({"id": f"bk:{criado}", "tipo": "Backup", "origem": f"backup de {criado}", "versao": "",
                           "quando": criado, "valores": _valores(_aberto(cfg), env)})
    for f in fontes:
        nome = (f["valores"].get("empresa.nome") or "").strip().upper()
        f["suspeita"] = bool(nome) and nome in nomes_outras            # já estava com o nome de outra empresa
    return sorted(fontes, key=lambda f: f["quando"], reverse=True)


def _mostrar(chave: str, v):
    if chave in OCULTOS:
        return "•••••• (preenchida)" if v not in (None, "") else ""
    return v


def dados_anteriores() -> dict:
    """Para a tela: cada versão anterior desta empresa com o que nela está DIFERENTE do atual; a sugerida é a mais
    recente que não estava com o nome de outra empresa."""
    with emissor.usar_empresa(emissor.BASE):
        atual = _valores(_aberto(config.carregar()), emissor.ler_env(emissor.BASE / ".env"))
    out = []
    for f in _fontes_cadastro():
        dif = [{"campo": k, "rotulo": ROTULOS.get(k, k), "atual": _mostrar(k, atual.get(k)), "valor": _mostrar(k, v)}
               for k, v in f["valores"].items() if not _vazio(v) and v != atual.get(k)]
        out.append({k: f[k] for k in ("id", "tipo", "origem", "versao", "quando", "suspeita")} | {"diferencas": dif})
    sugerida = next((f["id"] for f in out if not f["suspeita"] and f["diferencas"]), "")
    return {"cnpj": _cnpj(emissor.BASE), "fontes": out, "sugerida": sugerida}


def trazer_dados(fonte: str, campos: list[str]) -> dict:
    """Aplica os campos escolhidos da versão anterior. Faz backup antes. Notas, títulos, clientes e numeração não
    são tocados."""
    f = next((x for x in _fontes_cadastro() if x["id"] == fonte), None)
    if not f:
        raise ValueError("Versão anterior não encontrada (ou é de outro CNPJ).")
    validos = [c for c in campos if c in f["valores"] and not _vazio(f["valores"][c])]
    if not validos:
        raise ValueError("Escolha ao menos um dado para trazer.")
    from . import backup, empresas
    with emissor.usar_empresa(emissor.BASE):
        backup.criar("antes_de_trazer_dados", emissor.BASE)
        novo: dict = {}
        cred: dict = {}
        env_campo = {v: k for k, v in empresas.CAMPOS_ENV.items()}
        for c in validos:
            sec, k = c.split(".", 1)
            if sec == "env":
                cred[env_campo[k]] = f["valores"][c]
            else:
                novo.setdefault(sec, {})[k] = f["valores"][c]
        if novo:
            config.salvar(novo)
        if cred:
            empresas.salvar_credenciais(cred, emissor.BASE)
        db.registrar("migracao", f"Dados da empresa trazidos de {f['origem']}: " + ", ".join(ROTULOS.get(c, c) for c in validos))
    return {"trazidos": [ROTULOS.get(c, c) for c in validos]}
