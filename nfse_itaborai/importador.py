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

from . import clientes, config, db, emissor, empresas, leitura_fiscal, servicos
from .clientes import _achar, _digitos, _local, _texto

NOME_PASTA = "IMPORTAR XML"
CAMPOS_SERVICO = ("descricao", "item_lista_servico", "codigo_desdobro", "codigo_nbs", "cnae", "aliquota_iss",
                  "tipo_tributacao", "iss_retido", "indicador_operacao", "classificacao_tributaria",
                  "codigo_tributacao_municipio", "ibpt_percentual")


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


def empresa_de_xml(raiz) -> dict:
    """Dados da empresa emissora na nota: razão social, inscrição municipal, número da nota de origem (RPS/DPS),
    série e município de emissão — para completar o cadastro da empresa na importação."""
    if _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "PrestadorServico") is not None:
        p = _achar(raiz, "PrestadorServico")
        return {"canal": "municipal", "nome": _texto(p, "RazaoSocial"), "im": _digitos(_texto(p, "InscricaoMunicipal")),
                "numero": _digitos(_texto(raiz, "IdentificacaoRps/Numero")), "serie": "", "cmun": ""}
    dps = _achar(raiz, "infDPS")
    return {"canal": "nacional", "nome": _texto(raiz, "emit/xNome") or _texto(dps, "prest/xNome"),
            "im": _digitos(_texto(raiz, "emit/IM") or _texto(dps, "prest/IM")),
            "numero": _digitos(_texto(dps, "nDPS")), "serie": _texto(dps, "serie"),
            "cmun": _digitos(_texto(dps, "cLocEmi") or _texto(raiz, "emit/enderNac/cMun"))}


def _padrao_pelas_notas(criados: list[dict], escolheu: bool = False, codigos: set | None = None) -> str:
    """Se o padrão atual não aparece nas notas da empresa (ex.: o modelo 'Contabilidade' que vem no sistema numa
    empresa de psicologia), o serviço mais usado nas notas vira o padrão (ou o escolhido na tela); o modelo de
    fábrica nunca usado sai da lista."""
    fabrica = {}
    try:
        import json as _json
        fabrica = _json.loads(servicos.ARQ_FABRICA.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    eh_fabrica = lambda s: servicos.assinatura(s) == servicos.assinatura(fabrica) \
        and (s.get("descricao") or "") == (fabrica.get("descricao") or "")  # noqa: E731
    if escolheu:
        novo = servicos.padrao()
        sobra = [s for s in servicos.listar() if not s.get("padrao") and eh_fabrica(s)
                 and servicos.assinatura(s)[0] not in (codigos or set())]
        usados = {c.get("servico_id") for c in clientes.listar()}
        for s in sobra:
            if s["id"] not in usados:
                servicos.excluir(s["id"])
        return novo["nome"] if sobra else ""
    atual = servicos.padrao()
    if servicos.assinatura(atual)[0] in (codigos or set()) or any(servicos.assinatura(c) == servicos.assinatura(atual) for c in criados):
        return ""                                     # o padrão atual aparece nas notas: continua padrão
    novo = criados[0]                                  # a lista vem do mais frequente para o menos frequente
    servicos.salvar({**novo, "padrao": True})
    usado = any(c.get("servico_id") == atual["id"] for c in clientes.listar())
    if not usado and eh_fabrica(atual):
        servicos.excluir(atual["id"])
    db.registrar("importacao", f"Serviço padrão passou a ser '{novo['nome']}' (o mais usado nas notas da empresa)")
    return novo["nome"]


def completar_empresa(pasta: Path, cnpj: str) -> list[str]:
    """Completa o cadastro da empresa em uso com o que as notas emitidas por ela mostram. Só preenche o que está
    vazio (nome, assinatura, inscrição municipal, município do Emissor Nacional) e só AVANÇA a numeração
    (próximo RPS/DPS = maior número já usado + 1); nunca apaga nem volta nada."""
    from collections import Counter
    dados = []
    for arq in sorted(pasta.glob("*.xml")):
        raiz = _ler(arq)
        if raiz is not None and _prestador(raiz)[0] == cnpj:
            dados.append(empresa_de_xml(raiz))
    if not dados:
        return []
    freq = lambda campo: (Counter(d[campo] for d in dados if d.get(campo)).most_common(1) or [("", 0)])[0][0]  # noqa: E731
    feito: list[str] = []
    cfg = config.carregar()
    nome = freq("nome")
    if nome and not cfg["empresa"].get("nome"):
        config.salvar({"empresa": {"nome": nome, **({} if cfg["empresa"].get("assinatura") else {"assinatura": nome})}})
        feito.append(f"nome da empresa: {nome}")
    im = freq("im")
    if im and im != "0" and not _digitos(emissor.env("ITABORAI_IM") or ""):
        empresas.salvar_credenciais({"im": im})
        feito.append(f"inscrição municipal: {im}")
    canal = cfg["emissao"].get("canal", "municipal")
    cmun = freq("cmun")
    if canal == "nacional" and cmun and len(cmun) == 7 and not cfg["emissao"].get("municipio_emissor"):
        config.salvar({"emissao": {"municipio_emissor": cmun}})
        feito.append(f"município emissor (IBGE): {cmun}")
    nums = [int(d["numero"]) for d in dados if d.get("numero") and d["canal"] == canal]
    if nums:
        prox = max(nums) + 1
        if canal == "nacional":
            from . import nacional
            if prox > nacional._proximo_dps():
                config.salvar({"emissao": {"proximo_dps": prox}})
                feito.append(f"próximo número da DPS: {prox} (a última nota usou {max(nums)})")
        elif prox > int(emissor._ler_sequencia().get("proximo_rps", 1)):
            emissor._definir_proximo_rps(prox)
            empresas.salvar_credenciais({"proximo_rps": str(prox)})
            feito.append(f"próximo número de RPS: {prox} (a última nota usou {max(nums)})")
    if feito:
        db.registrar("importacao", "Cadastro da empresa completado pelos XML: " + "; ".join(feito))
    return feito


def servico_de_xml(raiz) -> dict:
    """Dados do serviço da nota (para sugerir o serviço padrão da empresa)."""
    if _local(raiz.tag) == "RetornoNfse" or _achar(raiz, "TomadorServico") is not None:
        return {"descricao": _texto(raiz, "DescritivoDoItem"), "item_lista_servico": _texto(raiz, "ItemListaServico"),
                "codigo_desdobro": _digitos(_texto(raiz, "CodigoLsnDesdobro")), "codigo_nbs": _digitos(_texto(raiz, "CodigoNbs")),
                "cnae": _digitos(_texto(raiz, "ClassificacaoCNAE")), "aliquota_iss": _texto(raiz, "Aliquota"),
                "tipo_tributacao": _texto(raiz, "TipoDeTributacao"), "iss_retido": _texto(raiz, "IssRetido"),
                "indicador_operacao": _digitos(_texto(raiz, "IndicadorOperacao")),
                "classificacao_tributaria": _digitos(_texto(raiz, "ClassificacaoTributaria")),
                "codigo_tributacao_municipio": _texto(raiz, "CodigoTributacaoMunicipio"), "ibpt_percentual": "",
                "_nome": ""}
    dps = _achar(raiz, "infDPS")
    ctrib = _digitos(_texto(dps, "cServ/cTribNac"))
    ret = _texto(dps, "tribMun/tpRetISSQN")
    sn = _texto(dps, "regTrib/opSimpNac")
    # carga tributária aproximada da nota (Lei 12.741/2012): % do Simples ou soma federal + estadual + municipal
    tot = _achar(dps, "totTrib")
    ibpt = _texto(tot, "pTotTribSN")
    if not ibpt and tot is not None:
        try:
            soma = sum(float(_texto(tot, k) or 0) for k in ("pTotTribFed", "pTotTribEst", "pTotTribMun"))
            ibpt = f"{soma:.2f}" if soma else ""
        except ValueError:
            ibpt = ""
    return {"descricao": _texto(dps, "cServ/xDescServ"),
            "item_lista_servico": f"{ctrib[:2]}.{ctrib[2:4]}" if len(ctrib) >= 4 else "",
            "codigo_desdobro": ctrib, "codigo_nbs": _digitos(_texto(dps, "cServ/cNBS")), "cnae": "",
            "aliquota_iss": _texto(dps, "tribMun/pAliq"),
            "tipo_tributacao": "4" if sn in ("2", "3") else "", "iss_retido": "1" if ret in ("2", "3") else ("2" if ret else ""),
            "indicador_operacao": _digitos(_texto(dps, "IBSCBS/cIndOp")),
            "classificacao_tributaria": _digitos(_texto(dps, "gIBSCBS/cClassTrib")),
            "codigo_tributacao_municipio": _digitos(_texto(dps, "cServ/cTribMun")), "ibpt_percentual": ibpt,
            # nome da atividade como o próprio Emissor Nacional descreve o código (ex.: "Psicologia.")
            "_nome": _texto(raiz, "xTribNac").rstrip(". ") or _texto(raiz, "xTribMun").rstrip(". ")}


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
        g.setdefault("fatos", []).append(leitura_fiscal.fatos(raiz))
    cadastradas = {e["cnpj"]: e for e in empresas.listar() if e.get("cnpj")}
    saida = []
    for g in grupos.values():
        emp = cadastradas.get(g["cnpj"])
        existentes, catalogo = set(), []
        if emp:
            with emissor.usar_empresa(empresas.pasta(emp)):
                existentes = {c["cpf_cnpj"] for c in clientes.listar()}
                catalogo = servicos.listar()
        saida.append({"cnpj": g["cnpj"], "nome": g["nome"], "notas": g["notas"],
                      "empresa_id": emp["id"] if emp else "", "empresa_nome": emp["nome"] if emp else "",
                      "clientes": len(g["clientes"]), "clientes_novos": len(g["clientes"] - existentes),
                      "padroes": padroes(g["servicos"]), "servicos": separar_servicos(g["servicos"], catalogo),
                      "fiscal": _resumo_fiscal([f for f in g.get("fatos", []) if f])})
    return {"pasta": str(caixa()), "zips_descompactados": zips, "invalidos": invalidos,
            "grupos": sorted(saida, key=lambda x: -x["notas"]),
            "empresas": [{"id": e["id"], "nome": e["nome"], "cnpj": e["cnpj"]} for e in cadastradas.values()]}


def _resumo_fiscal(notas: list[dict]) -> dict:
    """Prévia do que as notas mostram: regime e tomadores com particularidades (ISS retido, retenções...)."""
    from .fiscal import REGIMES
    g = leitura_fiscal.regra_geral(notas)
    especiais = {n["doc"] for n in notas if n.get("doc") and (
        n["tomador"].get("iss_retido") or any(n["tomador"].get(k) for k in
        ("ret_irrf_pct", "ret_pis_pct", "ret_cofins_pct", "ret_csll_pct", "ret_inss_pct", "exig_susp_tp", "n_bm",
         "tp_ente_gov", "dest_doc")) or n["tomador"].get("trib_issqn") not in ("1", "", None))}
    return {"regime": REGIMES.get(g.get("regime", ""), ""), "tomadores_especiais": len(especiais),
            "ibscbs": bool(g.get("tem_ibscbs"))}


def separar_servicos(lista: list[dict], catalogo: list[dict]) -> list[dict]:
    """Cada atividade distinta das notas (mesmo desdobro/item e NBS), com os padrões dela e o nome sugerido.
    Nota sem NBS (o Emissor Nacional deixa omitir) entra na atividade de mesmo código que tem o NBS."""
    grupos: dict[tuple, list] = {}
    for s in lista:
        grupos.setdefault(servicos.assinatura(s), []).append(s)
    for chave in [k for k in grupos if not k[1]]:
        par = max((k for k in grupos if k[0] == chave[0] and k[1]), key=lambda k: len(grupos[k]), default=None)
        if par:
            grupos[par] += grupos.pop(chave)
    out = []
    for chave, itens in sorted(grupos.items(), key=lambda x: -len(x[1])):
        p = padroes(itens)
        existente = next((c for c in catalogo if servicos.assinatura(c) == servicos.assinatura(p) and any(chave)), None)
        nomes = Counter(s.get("_nome") for s in itens if s.get("_nome"))
        sugerido = nomes.most_common(1)[0][0] if nomes else servicos._nome_de(p.get("descricao", ""))
        out.append({"notas": len(itens), "campos": p, "existente_id": existente["id"] if existente else "",
                    "nome": existente["nome"] if existente else sugerido[:60]})
    return out


def padroes(servicos: list[dict]) -> dict:
    """Valor mais frequente de cada campo do serviço nas notas da empresa."""
    out = {}
    for campo in CAMPOS_SERVICO:
        valores = Counter(s.get(campo, "") for s in servicos if s.get(campo, ""))
        out[campo] = valores.most_common(1)[0][0] if valores else ""
    return out


# ---------------------------------------------------------------- importação

def importar(empresa_id: str, cnpj_prestador: str, servico: dict | None = None,
             lista_servicos: list[dict] | None = None) -> dict:
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
        cadastrados, criados, escolheu = 0, [], False
        for item in lista_servicos or []:
            campos = {k: str(v).strip() for k, v in (item.get("campos") or {}).items() if k in CAMPOS_SERVICO}
            s = servicos.registrar_detectado(campos, str(item.get("nome") or "").strip())
            if item.get("padrao"):
                servicos.salvar({**s, "padrao": True})
                escolheu = True
            criados.append(s)
            cadastrados += 1
        codigos = {servicos.assinatura(servico_de_xml(x))[0] for a in (destino.glob("*.xml") if destino.exists() else [])
                   if (x := _ler(a)) is not None and _prestador(x)[0] == cnpj}
        padrao_trocado = _padrao_pelas_notas(criados, escolheu, codigos) if criados else ""
        ligados = _ligar_clientes_aos_servicos(destino, cnpj) if destino.exists() else 0
        notas = _fatos_fiscais(destino, cnpj) if destino.exists() else []
        regra_geral = leitura_fiscal.aplicar_geral(notas)
        empresa_completada = completar_empresa(destino, cnpj) if destino.exists() else []
        regras_tomadores = leitura_fiscal.aplicar_tomadores(notas)
        if not str(config.carregar()["pastas"].get("xml_nfse") or "").strip():
            config.salvar({"pastas": {"xml_nfse": str(destino)}})
        db.registrar("importacao", f"{movidos} XML importado(s) da pasta {NOME_PASTA}: {r['clientes_novos']} cliente(s) novo(s)")
    return {"empresa": emp["nome"], "xml": movidos, "clientes_novos": r["clientes_novos"],
            "clientes_total": r["clientes_total"], "padrao_salvo": bool(servico), "servicos": cadastrados,
            "clientes_com_servico": ligados, "regra_geral": regra_geral, "regras_tomadores": regras_tomadores,
            "empresa_completada": empresa_completada, "padrao_trocado": padrao_trocado}


def _fatos_fiscais(pasta: Path, cnpj: str) -> list[dict]:
    out = []
    for arq in pasta.rglob("*.xml"):
        raiz = _ler(arq)
        if raiz is not None and _prestador(raiz)[0] == cnpj:
            f = leitura_fiscal.fatos(raiz)
            if f:
                out.append(f)
    return out


def _ligar_clientes_aos_servicos(pasta: Path, cnpj: str) -> int:
    """Serviço habitual de cada cliente = serviço da nota mais recente dele (só para quem ainda não tem)."""
    catalogo = {servicos.assinatura(s): s["id"] for s in servicos.listar() if any(servicos.assinatura(s))}
    if not catalogo:
        return 0
    ultimo: dict[str, tuple] = {}
    for arq in pasta.rglob("*.xml"):
        raiz = _ler(arq)
        if raiz is None or _prestador(raiz)[0] != cnpj:
            continue
        cli = clientes.cliente_de_xml(ET.tostring(raiz), cnpj)
        if not cli:
            continue
        ass = servicos.assinatura(servico_de_xml(raiz))
        sid = catalogo.get(ass) or (next((v for k, v in catalogo.items() if k[0] == ass[0]), None) if not ass[1] else None)
        if sid and cli.get("ultima_data", "") >= ultimo.get(cli["cpf_cnpj"], ("",))[0]:
            ultimo[cli["cpf_cnpj"]] = (cli.get("ultima_data", ""), sid)
    n = 0
    for c in clientes.listar():
        if c["cpf_cnpj"] in ultimo and not c.get("servico_id"):
            clientes.salvar({**c, "servico_id": ultimo[c["cpf_cnpj"]][1]})
            n += 1
    return n


NOMES_FISCAIS = {"regime": "regime tributário", "op_simp_nac": "situação no Simples", "reg_ap_trib_sn": "apuração no Simples",
                 "reg_esp_trib": "regime especial", "pis_cofins_cst": "CST do PIS/COFINS", "p_pis": "alíquota do PIS",
                 "p_cofins": "alíquota da COFINS", "tot_trib_modo": "forma da carga tributária na nota",
                 "p_tot_fed": "carga federal", "p_tot_est": "carga estadual", "p_tot_mun": "carga municipal",
                 "aliquota_simples_pct": "alíquota efetiva do Simples", "ibscbs": "informar IBS/CBS",
                 "cst_reg": "CST IBS/CBS", "class_trib_reg": "classificação IBS/CBS", "p_dif_uf": "diferimento UF",
                 "p_dif_mun": "diferimento município", "p_dif_cbs": "diferimento CBS", "c_cred_pres": "crédito presumido"}


def importar_tudo(origem: Path | None = None) -> list[dict]:
    """IMPORTAR_CLIENTES.bat: importa de uma vez, para cada empresa cadastrada, tudo o que as notas mostram —
    clientes, serviços (o mais usado como padrão), dados da empresa, numeração e regras fiscais do regime.
    Notas de prestador ainda não cadastrado ficam na pasta, com o aviso."""
    if origem and Path(origem).resolve() != caixa().resolve():
        for arq in Path(origem).iterdir():
            if arq.is_file() and arq.suffix.lower() in (".xml", ".zip"):
                shutil.copy2(arq, caixa() / arq.name)
    a = analisar()
    saida = []
    for g in a["grupos"]:
        if not g["empresa_id"]:
            saida.append({"cnpj": g["cnpj"], "nome": g["nome"], "notas": g["notas"],
                          "erro": "empresa não cadastrada no sistema (cadastre-a e rode de novo)"})
            continue
        lista = [{"nome": s["nome"], "campos": s["campos"], "padrao": False} for s in g["servicos"] if not s["existente_id"]]
        r = importar(g["empresa_id"], g["cnpj"], lista_servicos=lista)
        saida.append({"cnpj": g["cnpj"], "nome": g["nome"], "notas": g["notas"]} | r)
    return saida


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
