"""Pagamento com cartão de crédito pela InfinitePay (Checkout Integrado), com a taxa repassada a quem escolher o cartão.

API (pública, sem mensalidade; identifica a conta pela InfiniteTag, sem senha):
- POST https://api.checkout.infinitepay.io/links  {handle, order_nsu, items:[{quantity, price (centavos), description}],
  customer?}  →  {"url": link de pagamento (cartão ou Pix)}
- POST https://api.checkout.infinitepay.io/payment_check {handle, order_nsu, transaction_nsu, slug} → {paid, paid_amount...}

A confirmação automática da InfinitePay exige o código da transação (transaction_nsu), que ela só manda por webhook a
um endereço na internet. Este sistema roda no computador do escritório (sem endereço público), então:
- o link é criado sozinho e vai na mensagem de cobrança (ao lado do boleto/PIX do Inter);
- quando o pagamento aparece no app da InfinitePay, o escritório clica em "Pago no cartão" no título; se colar o
  link do comprovante (com slug e transaction_nsu), o sistema confere na InfinitePay (payment_check) antes da baixa.

Na baixa: o título é pago pelo valor cobrado no cartão, a taxa vira despesa paga ("Bancárias"), o boleto do Inter é
cancelado e, se a NFS-e ainda não foi emitida, ela sai pelo valor total (o acréscimo faz parte do preço — Lei
13.455/2017 permite preço diferente conforme o meio de pagamento).
"""

from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request

from . import clientes, config, db, financeiro

URL_API = "https://api.checkout.infinitepay.io"


class ErroCartao(RuntimeError):
    pass


def _cfg(cfg: dict | None = None) -> dict:
    return (cfg or config.carregar())["cobranca"]


def _tag(c: dict) -> str:
    return re.sub(r"[^A-Za-z0-9_\-]", "", str(c.get("cartao_infinitepay_tag") or ""))


def configurado(cfg: dict | None = None) -> bool:
    c = _cfg(cfg)
    return c.get("cartao_provedor") == "infinitepay" and bool(_tag(c))


# ---------------------------------------------------------------- taxa repassada

def taxa_pct(parcelas: int, cfg: dict | None = None) -> float:
    c = _cfg(cfg)
    if parcelas <= 1:
        return float(c.get("cartao_taxa_1x") or 0)
    if parcelas <= 6:
        return float(c.get("cartao_taxa_2a6") or 0)
    return float(c.get("cartao_taxa_7a12") or 0)


def valor_no_cartao(valor_cent: int, parcelas: int = 1, cfg: dict | None = None) -> dict:
    """Valor a cobrar no cartão para que, descontada a taxa (percentual + fixa), sobre o honorário cheio."""
    c = _cfg(cfg)
    parcelas = max(1, min(int(parcelas or 1), int(c.get("cartao_parcelas_max") or 12)))
    pct, fixa = taxa_pct(parcelas, cfg), round(float(c.get("cartao_taxa_fixa") or 0) * 100)
    total = math.ceil((valor_cent + fixa) / (1 - pct / 100)) if c.get("cartao_repassar", True) else valor_cent
    return {"valor_cent": valor_cent, "parcelas": parcelas, "taxa_pct": pct, "taxa_fixa_cent": fixa,
            "total_cent": total, "acrescimo_cent": total - valor_cent, "parcela_cent": math.ceil(total / parcelas),
            "taxa_cent": round(total * pct / 100) + fixa}


# ---------------------------------------------------------------- API da InfinitePay

def _post(caminho: str, corpo: dict, cfg: dict | None = None) -> dict:
    c = _cfg(cfg)
    req = urllib.request.Request((c.get("cartao_infinitepay_url") or URL_API) + caminho, method="POST",
                                 data=json.dumps(corpo).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "nfse-itaborai"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        bruto = e.read().decode("utf-8", "replace")
        try:
            js = json.loads(bruto)
            msg = js.get("message") or js.get("error") or bruto[:300]
            if js.get("errors"):
                msg += f" ({json.dumps(js['errors'], ensure_ascii=False)[:200]})"
        except ValueError:
            msg = bruto[:300] or f"HTTP {e.code}"
        raise ErroCartao(f"InfinitePay: {msg}") from e


def _telefone(tel: str) -> str:
    d = clientes._digitos(tel)
    if len(d) in (10, 11):
        d = "55" + d
    return "+" + d if len(d) >= 12 else ""


def _criar_link(order_nsu: str, total_cent: int, descricao: str, cli: dict | None, cfg: dict | None) -> str:
    corpo = {"handle": _tag(_cfg(cfg)), "order_nsu": order_nsu,
             "items": [{"quantity": 1, "price": int(total_cent), "description": descricao[:120]}]}
    if cli:
        tel = _telefone(cli.get("telefone", ""))
        if tel:                                   # telefone inválido faz a InfinitePay recusar o link
            corpo["customer"] = {"name": cli["razao_social"][:100],
                                 "email": (cli.get("email") or "").split(";")[0].strip(), "phone_number": tel}
    r = _post("/links", corpo, cfg)
    if not r.get("url"):
        raise ErroCartao("InfinitePay não devolveu o link de pagamento.")
    return r["url"]


def testar(cfg: dict | None = None) -> dict:
    """Cria um link de R$ 1,00 só para conferir a InfiniteTag (o link não é enviado a ninguém)."""
    if not configurado(cfg):
        raise ErroCartao("Cartão de crédito: escolha InfinitePay e informe a sua InfiniteTag em Configurações.")
    url = _criar_link("TESTE-CONEXAO", 100, "Teste de conexão do sistema", None, cfg)
    return {"ok": True, "mensagem": "Conexão com a InfinitePay OK (InfiniteTag aceita).", "link": url}


# ---------------------------------------------------------------- link do título

def gerar_link(tid: int, parcelas: int = 0, cfg: dict | None = None) -> dict:
    """Cria (ou reaproveita) o link de pagamento com cartão do título e devolve o link e os valores."""
    cfg = cfg or config.carregar()
    if not configurado(cfg):
        raise ErroCartao("Cartão de crédito não configurado (Configurações › Cartão de crédito).")
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        raise ErroCartao("Só títulos em aberto podem ser pagos com cartão.")
    parcelas = parcelas or int(_cfg(cfg).get("cartao_parcelas_max") or 1)
    v = valor_no_cartao(t["valor_cent"], parcelas, cfg)
    if t.get("cartao_link") and t.get("cartao_total_cent") == v["total_cent"] and t.get("cartao_parcelas") == v["parcelas"] \
            and t.get("cartao_status") == "aberto":
        return v | {"link": t["cartao_link"], "id": t["cartao_id"], "reaproveitado": True}
    n = int(str(t["cartao_id"]).rsplit("-", 1)[-1]) + 1 if re.fullmatch(r"T\d+-\d+", t.get("cartao_id") or "") else 1
    order = f"T{tid}-{n}"                          # número novo a cada link (valor ou parcelas mudaram)
    desc = f"{t['descricao']} - comp. {t['competencia'][5:]}/{t['competencia'][:4]}"
    url = _criar_link(order, v["total_cent"], desc, clientes.obter(t["cpf_cnpj"]), cfg)
    financeiro.atualizar_titulo(tid, cartao_id=order, cartao_link=url, cartao_total_cent=v["total_cent"],
                                cartao_parcelas=v["parcelas"], cartao_status="aberto")
    db.registrar("cartao", f"Título {tid} ({t['cliente_nome']}): link de cartão {_brl(v['total_cent'])} "
                           f"(acréscimo {_brl(v['acrescimo_cent'])})")
    return v | {"link": url, "id": order}


def _comprovante(texto: str) -> dict:
    """Lê slug, transaction_nsu e order_nsu de um link de retorno/comprovante da InfinitePay (quando vierem)."""
    q = urllib.parse.parse_qs(urllib.parse.urlparse(str(texto or "").strip()).query)
    return {k: (q.get(k) or [""])[0] for k in ("slug", "transaction_nsu", "order_nsu")}


def confirmar_pagamento(tid: int, valor=None, data: str = "", comprovante: str = "", cfg: dict | None = None) -> dict:
    """Botão "Pago no cartão": baixa pelo valor cobrado no cartão (conferido na InfinitePay quando há comprovante),
    taxa em despesas, cancela o boleto e emite a NFS-e pendente pelo valor total."""
    from . import cobranca
    cfg = cfg or config.carregar()
    t = financeiro.obter_titulo(tid)
    if t["status"] != "aberto":
        raise ErroCartao("Este título não está em aberto.")
    total = financeiro.cent(valor) if valor not in (None, "") else (t.get("cartao_total_cent") or t["valor_cent"])
    conferido = False
    c = _comprovante(comprovante)
    if c["transaction_nsu"] and c["slug"]:
        r = _post("/payment_check", {"handle": _tag(_cfg(cfg)), "order_nsu": c["order_nsu"] or t.get("cartao_id") or f"T{tid}",
                                     "transaction_nsu": c["transaction_nsu"], "slug": c["slug"]}, cfg)
        if not r.get("paid"):
            raise ErroCartao("A InfinitePay não confirmou este pagamento. Confira o comprovante.")
        total, conferido = int(r.get("paid_amount") or r.get("amount") or total), True
    elif comprovante.strip():
        raise ErroCartao("Não achei o código da transação no comprovante. Deixe o campo vazio para baixar sem conferir.")
    if total <= 0:
        raise ErroCartao("Informe o valor pago no cartão.")
    v = valor_no_cartao(t["valor_cent"], t.get("cartao_parcelas") or 1, cfg)
    taxa = round(total * v["taxa_pct"] / 100) + v["taxa_fixa_cent"]
    data = data or financeiro.hoje().isoformat()
    if t["nfse_status"] != "emitida" and total != t["valor_cent"]:
        # NFS-e ainda não emitida: o preço do serviço pago no cartão inclui o acréscimo
        financeiro.atualizar_titulo(tid, valor_cent=total,
                                    descricao=(t["descricao"] + " (pagamento com cartão de crédito)")[:190])
    financeiro.atualizar_titulo(tid, cartao_status="pago")
    financeiro.baixar(tid, data, financeiro.reais(total), "cartao")
    if taxa > 0:
        did = financeiro.salvar_despesa({"descricao": f"Taxa do cartão (InfinitePay) - título {tid} - {t['cliente_nome']}"[:120],
                                         "fornecedor": "InfinitePay", "categoria": "Bancárias",
                                         "valor": financeiro.reais(taxa), "vencimento": data})
        financeiro.pagar_despesa(did, data)
    cobranca.cancelar_boleto(financeiro.obter_titulo(tid), "Pago com cartão de crédito", cfg)
    db.registrar("cartao", f"Título {tid} ({t['cliente_nome']}) pago no cartão: {_brl(total)}, taxa "
                           f"{_brl(taxa)}{' (conferido na InfinitePay)' if conferido else ''}")
    return {"ok": True, "titulo": financeiro.obter_titulo(tid), "taxa_cent": taxa, "conferido": conferido}


def encerrar_links(cfg: dict | None = None) -> int:
    """Robô: título pago por boleto/PIX ou cancelado deixa de mostrar o link do cartão nas mensagens.
    (A InfinitePay não cancela link pela API: se o cliente pagar duas vezes, estorne pelo app.)"""
    n = 0
    for t in db.linhas("SELECT id FROM titulos WHERE cartao_status='aberto' AND status!='aberto'"):
        financeiro.atualizar_titulo(t["id"], cartao_status="encerrado")
        n += 1
    return n


def _brl(c: int) -> str:
    return f"R$ {c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
