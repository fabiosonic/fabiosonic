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
    return [r for r in (resumo(p) for p in localizar()) if r["itens"]]


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
    feitos = []
    with emissor.usar_empresa(emissor.BASE):
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
