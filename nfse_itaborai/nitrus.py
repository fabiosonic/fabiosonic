"""Importação do relatório de Inadimplência do Nitrus (PDF) para o contas a receber.

O PDF é lido com o pypdf pela posição de cada texto na página: as colunas (cliente/código, contato, vencimento,
valor original, juros e multa, dias de atraso, valor total) são achadas pelo cabeçalho da tabela, e cada título é a
linha da data de vencimento — o nome e o contato quebrados em várias linhas pertencem ao vencimento mais próximo.
A leitura é conferida com os totais impressos no relatório antes de qualquer lançamento.

Lançamento: um título por linha, com o vencimento original (o sistema calcula multa e juros pelo atraso), sem
emitir NFS-e (a nota é do sistema anterior), com boleto/PIX e régua de cobrança. Título igual (cliente, vencimento
e valor) já existente não é lançado de novo. O código do cliente no Nitrus fica guardado no cadastro.
"""

from __future__ import annotations

import base64
import io
import re
import unicodedata
from collections import defaultdict

from . import clientes, cobranca, config, db, financeiro

DESCRICAO = "HONORÁRIOS CONTABEIS MENSAIS."


class ErroNitrus(ValueError):
    pass


# ---------------------------------------------------------------- leitura do PDF

def _pedacos(dados: bytes) -> list[list[tuple[float, float, str]]]:
    try:
        import pypdf
    except ImportError as ex:
        raise ErroNitrus("Falta o componente de leitura de PDF: feche o sistema e abra pelo INICIAR.bat (ele instala).") from ex
    try:
        leitor = pypdf.PdfReader(io.BytesIO(dados))
    except Exception as ex:  # noqa: BLE001
        raise ErroNitrus("Não consegui abrir o PDF. Exporte o relatório de novo no Nitrus.") from ex
    paginas = []
    for pg in leitor.pages:
        itens: list[tuple[float, float, str]] = []

        def visita(texto, cm, tm, _fd, _fs, itens=itens):
            if texto and texto.strip():
                x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
                y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
                itens.append((x, y, texto.replace("\n", " ").strip()))
        pg.extract_text(visitor_text=visita)
        paginas.append(itens)
    return paginas


def _cent(txt: str) -> int:
    m = re.search(r"-?[\d.]+,\d{2}", txt or "")
    return round(float(m.group(0).replace(".", "").replace(",", ".")) * 100) if m else 0


def ler_inadimplencia(dados: bytes) -> dict:
    """Linhas do relatório de inadimplência e os totais impressos nele (para conferência)."""
    paginas = _pedacos(dados)
    texto = " ".join(t for p in paginas for _, _, t in p)
    if "Inadimpl" not in texto:
        raise ErroNitrus("Este PDF não é o relatório de Inadimplência do Nitrus.")
    tot = re.search(r"Total Original:\s*R\$\s*([\d.,]+).*?Juros e Multa:\s*R\$\s*([\d.,]+).*?Total a Receber:\s*R\$\s*([\d.,]+)", texto)
    linhas = []
    ultimo = {}
    for itens in paginas:
        cab = {t.strip(): (x, y) for x, y, t in itens if t.strip() in ("Cliente/Código", "Contato", "Vencimento", "Valor Original",
                                                                         "Juros e Multa", "D. Atraso", "Valor Total")}
        if "Vencimento" not in cab or "Contato" not in cab:
            continue
        y_cab = cab["Vencimento"][1]
        x_cont, x_venc = cab["Contato"][0], cab["Vencimento"][0]
        corpo = [(x, y, t) for x, y, t in itens if 30 < y < y_cab - 2 and not t.startswith("Total de Registros")]
        datas = sorted(((y, t) for x, y, t in corpo if re.fullmatch(r"\d\d/\d\d/\d{4}", t) and x >= x_venc - 15), reverse=True)
        if not datas:
            continue
        regs = [{"y": y, "venc": d, "nome": [], "cont": [], "vals": []} for y, d in datas]
        for x, y, t in corpo:
            # o nome começa um pouco acima da data do título e continua abaixo dela: o texto pertence ao título
            # mais baixo que já começou acima dele
            dentro = [k for k in range(len(regs)) if regs[k]["y"] + 8 >= y]
            if not dentro:
                continue
            r = regs[dentro[-1]]
            if x < x_cont - 2:
                r["nome"].append((-y, x, t))
            elif x < x_venc - 15:
                r["cont"].append((-y, x, t))
            elif not re.fullmatch(r"\d\d/\d\d/\d{4}", t):
                r["vals"].append((x, t))
        for r in regs:
            nome = re.sub(r"\s+", " ", " ".join(t for *_, t in sorted(r["nome"]))).strip()
            cod = re.search(r"\((\d+)\)\s*$", nome)
            nome = re.sub(r"\s*\(\d+\)\s*$", "", nome).strip()
            cont = [t for *_, t in sorted(r["cont"])]
            tel = next((c for c in cont if re.match(r"^\(\d\d\)", c)), "")
            email = "".join(c for c in cont if c != tel).replace(" ", "")
            vals = [t for _, t in sorted(r["vals"])]
            dinheiro = [_cent(t) for t in vals if "R$" in t or re.search(r",\d{2}$", t)]
            dias = next((int(t) for t in vals if re.fullmatch(r"\d+", t.strip())), 0)
            if not nome and ultimo:                     # linha sem nome na quebra de página: mesmo cliente de antes
                nome, cod = ultimo["nome"], None
            linha = {"codigo": cod.group(1) if cod else (ultimo.get("codigo", "") if nome == ultimo.get("nome") else ""),
                     "nome": nome, "email": email if "@" in email else "", "telefone": tel,
                     "vencimento": f"{r['venc'][6:]}-{r['venc'][3:5]}-{r['venc'][:2]}",
                     "valor_cent": dinheiro[0] if dinheiro else 0, "juros_cent": dinheiro[1] if len(dinheiro) > 2 else 0,
                     "dias": dias, "total_cent": dinheiro[-1] if dinheiro else 0}
            linhas.append(linha)
            ultimo = linha
    if not linhas:
        raise ErroNitrus("Não achei títulos no relatório.")
    lidos = {"original": sum(l["valor_cent"] for l in linhas), "juros": sum(l["juros_cent"] for l in linhas),
             "total": sum(l["total_cent"] for l in linhas)}
    impressos = {k: _cent(v) for k, v in zip(("original", "juros", "total"), tot.groups())} if tot else {}
    return {"linhas": linhas, "lidos": lidos, "impressos": impressos, "conferido": bool(impressos) and lidos == impressos}


# ---------------------------------------------------------------- vínculo com os clientes

def _sem(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s or "")) if unicodedata.category(c) != "Mn").upper()


def _norm(s: str) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", _sem(s))
    s = re.sub(r"\b\d{8,14}\b", " ", s)
    s = re.sub(r"^\s*\d{2} \d{3} \d{3}\s+", " ", s)
    s = re.sub(r"\b(LTDA|EIRELI|ME|EPP|SA|S A|SLU|SS)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def achar_cliente(nome: str, codigo: str = "", cads: list[dict] | None = None) -> tuple[dict | None, str]:
    """Cliente do cadastro: pelo código do Nitrus guardado, CPF no nome, raiz do CNPJ (MEI) ou nome."""
    cads = cads if cads is not None else clientes.listar()
    c = [x for x in cads if codigo and str(x.get("codigo_externo") or "") == str(codigo)]
    cpf = re.search(r"\b\d{11}\b", nome or "")
    raiz = re.match(r"^(\d{2})\.(\d{3})\.(\d{3})\s", nome or "")
    if not c and cpf:
        c = [x for x in cads if x["cpf_cnpj"] == cpf.group(0)]
    if not c and raiz:
        c = [x for x in cads if x["cpf_cnpj"].startswith("".join(raiz.groups()))]
    n = _norm(nome)
    if not c:
        c = [x for x in cads if _norm(x["razao_social"]) == n]
    if not c and len(n) >= 25:
        c = [x for x in cads if _norm(x["razao_social"]).startswith(n)]
    docs = {x["cpf_cnpj"] for x in c}
    if len(docs) == 1:
        return c[0], ""
    return None, (f"{len(docs)} clientes com nome parecido" if docs else "não encontrado no cadastro")


def _ja_existe(doc: str, venc: str, valor: int) -> dict | None:
    r = db.linhas("SELECT id, status FROM titulos WHERE cpf_cnpj=? AND vencimento=? AND valor_cent=? AND status!='cancelado'",
                  (doc, venc, valor))
    return r[0] if r else None


def analisar(pdf_b64: str) -> dict:
    """Conferência antes de lançar: um grupo por cliente do relatório, com o cliente achado e o que já existe."""
    rel = ler_inadimplencia(base64.b64decode(pdf_b64.split(",")[-1]))
    cads = clientes.listar()
    grupos: dict[str, dict] = {}
    for l in rel["linhas"]:
        chave = l["codigo"] or _norm(l["nome"])
        if chave not in grupos:
            cli, erro = achar_cliente(l["nome"], l["codigo"], cads)
            grupos[chave] = {"chave": chave, "codigo": l["codigo"], "nome": l["nome"], "email": l["email"],
                             "telefone": l["telefone"], "cpf_cnpj": cli["cpf_cnpj"] if cli else "",
                             "cliente_nome": cli["razao_social"] if cli else "", "motivo": erro, "titulos": []}
        g = grupos[chave]
        ja = _ja_existe(g["cpf_cnpj"], l["vencimento"], l["valor_cent"]) if g["cpf_cnpj"] else None
        g["titulos"].append({k: l[k] for k in ("vencimento", "valor_cent", "juros_cent", "total_cent", "dias")}
                            | {"existe": ja["status"] if ja else ""})
    lista = sorted(grupos.values(), key=lambda g: (bool(g["cpf_cnpj"]), -sum(t["valor_cent"] for t in g["titulos"])))
    return {"grupos": lista, "lidos": rel["lidos"], "impressos": rel["impressos"], "conferido": rel["conferido"],
            "titulos": len(rel["linhas"])}


def lancar(grupos: list[dict], cobrar: bool = True, gerar_agora: bool = True) -> dict:
    """Lança os títulos dos grupos vinculados. Grupo com 'cnpj_novo' cadastra o cliente com esse CNPJ.
    Os títulos seguem na régua de cobrança sem boleto (já vinham sendo cobrados); 'gerar_agora' fica só por
    compatibilidade — boleto, só pelo botão "Gerar boleto" do título."""
    from .empresas import cnpj_valido
    cfg = config.carregar()
    res = {"lancados": 0, "com_cobranca": 0, "ja_existiam": 0, "clientes_novos": 0, "pulados": 0, "avisos": []}
    for g in grupos:
        doc = clientes._digitos(g.get("cpf_cnpj"))
        novo = clientes._digitos(g.get("cnpj_novo"))
        if not doc and novo:
            if not (len(novo) == 11 or (len(novo) == 14 and cnpj_valido(novo))):
                res["avisos"].append(f"{g['nome']}: CPF/CNPJ {g.get('cnpj_novo')} inválido — não lançado")
                res["pulados"] += len(g["titulos"])
                continue
            doc = novo
        if not doc:
            res["pulados"] += len(g["titulos"])
            continue
        antigo = clientes.obter(doc)
        if antigo:                                   # só completa o que estiver vazio; nunca apaga o cadastro
            extra = {k: v for k, v in (("email", g.get("email")), ("telefone", g.get("telefone"))) if v and not antigo.get(k)}
            if g.get("codigo") and not antigo.get("codigo_externo"):
                extra["codigo_externo"] = g["codigo"]
            if extra:
                clientes.salvar({**antigo, **extra})
        else:
            clientes.salvar({"cpf_cnpj": doc, "razao_social": _sem(g["nome"]).strip(), "email": g.get("email", ""),
                             "telefone": g.get("telefone", ""), "endereco": {}, "codigo_externo": g.get("codigo", "")})
            res["clientes_novos"] += 1
            res["avisos"].append(f"{g['nome']}: cadastrado — complete o endereço em Clientes para o banco registrar o boleto")
        for t in g["titulos"]:
            if _ja_existe(doc, t["vencimento"], int(t["valor_cent"])):
                res["ja_existiam"] += 1
                continue
            tid = financeiro.criar_titulo(doc, financeiro.reais(int(t["valor_cent"])), DESCRICAO, vencimento=t["vencimento"],
                                          competencia=t["vencimento"][:7], emitir_nfse=True, apos_pagamento=True,
                                          cobrar=cobrar)          # a NFS-e sai só quando o cliente pagar
            res["lancados"] += 1
            if cobrar:
                # já vinha sendo cobrado no Nitrus: segue na régua sem gerar boleto (paga pelo PIX do escritório);
                # se quiser boleto para algum, o botão "Gerar boleto" do título registra um
                financeiro.atualizar_titulo(tid, boleto_situacao="dispensado")
                res["com_cobranca"] += 1
    db.registrar("importacao", f"Inadimplência do Nitrus: {res['lancados']} título(s) lançado(s), "
                               f"{res['clientes_novos']} cliente(s) novo(s), {res['ja_existiam']} já existiam")
    return res


def resumo_por_cliente(grupos: list[dict]) -> list[dict]:
    out = defaultdict(lambda: {"titulos": 0, "valor_cent": 0})
    for g in grupos:
        out[g["nome"]]["titulos"] += len(g["titulos"])
        out[g["nome"]]["valor_cent"] += sum(t["valor_cent"] for t in g["titulos"])
    return [{"nome": k, **v} for k, v in out.items()]
