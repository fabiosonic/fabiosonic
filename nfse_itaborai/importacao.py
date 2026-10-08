"""Entradas automáticas do robô: XML de NFS-e, extratos OFX e resumo diário.

- XML (pasta configurada): atualiza clientes; notas emitidas FORA do sistema (Nitrus, portal) a partir do
  início do financeiro viram contas a receber; padrões mensais viram contratos sugeridos (confirmação única).
- Extratos: todo .ofx novo na pasta de extratos é importado e conciliado.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from . import clientes, cobranca, conciliacao, config, db, emissor, financeiro, relatorios


def _pasta(caminho: str) -> Path:
    return Path(caminho).expanduser()


def numero_curto(n: str) -> str:
    """'202600099003740' e '99003740' -> '99003740' (o número municipal são os 8 dígitos finais)."""
    d = clientes._digitos(n)
    return d[-8:] if d else ""


# ---------------------------------------------------------------- leitura das notas

def nota_de_xml(xml: str, cnpj_prestador: str) -> dict | None:
    cli = clientes.cliente_de_xml(xml, cnpj_prestador)
    if not cli:
        return None
    raiz = ET.fromstring(xml.encode("utf-8"))
    t = clientes._texto
    if clientes._achar(raiz, "infDPS") is not None:
        dps = clientes._achar(raiz, "infDPS")
        numero, emissao = t(raiz, "nNFSe"), t(dps, "dhEmi")[:10]
        comp = t(dps, "dCompet")[:7] or emissao[:7]
        valor, desc = t(dps, "vServ"), t(dps, "xDescServ")
    else:
        numero, emissao = t(raiz, "NumeroNFSe"), t(raiz, "DataEmissaoNFSe")[:10]
        c = t(raiz, "Competencia")                      # MM-AAAA
        comp = f"{c[3:7]}-{c[0:2]}" if len(c) == 7 else emissao[:7]
        valor, desc = t(raiz, "ValorTotalDosServicos"), t(raiz, "DescritivoDoItem")
    if not (numero and emissao and valor):
        return None
    return {"numero": numero_curto(numero), "emissao": emissao, "competencia": comp,
            "valor_cent": financeiro.cent(valor), "descricao": " ".join(desc.split())[:190], "cliente": cli}


def ler_notas(pasta: Path, cnpj_prestador: str) -> list[dict]:
    notas, vistos = [], set()
    for arq in sorted(pasta.rglob("*.xml")):
        try:
            n = nota_de_xml(arq.read_text(encoding="utf-8", errors="replace"), cnpj_prestador)
        except ET.ParseError:
            n = None
        if n and n["numero"] not in vistos:          # a mesma nota costuma estar em vários arquivos
            vistos.add(n["numero"])
            notas.append(n)
    return notas


# ---------------------------------------------------------------- contratos detectados

def _meses_anteriores(em: date, n: int) -> list[str]:
    a, m, out = em.year, em.month, []
    for _ in range(n):
        a, m = (a, m - 1) if m > 1 else (a - 1, 12)
        out.append(f"{a}-{m:02d}")
    return out


def _proximo(comp: str) -> str:
    a, m = int(comp[:4]), int(comp[5:])
    return f"{a + (m == 12)}-{1 if m == 12 else m + 1:02d}"


def detectar_contratos(notas: list[dict], em: date | None = None) -> int:
    """Cliente com nota de mesmo valor em pelo menos 3 dos últimos 4 meses = honorário recorrente.

    O contrato nasce 'aguardando confirmação' (não gera cobrança até você confirmar) e começa no mês
    seguinte à última nota, para nunca cobrar em dobro um mês já faturado em outro sistema.
    """
    em = em or financeiro.hoje()
    janela = set(_meses_anteriores(em, 4)) | {financeiro.competencia_de(em)}
    com_contrato = {c["cpf_cnpj"] for c in db.linhas("SELECT cpf_cnpj FROM contratos WHERE ativo=1")}
    por_cliente: dict[str, list] = defaultdict(list)
    for n in notas:
        if n["competencia"] in janela:
            por_cliente[n["cliente"]["cpf_cnpj"]].append(n)
    criados = 0
    for doc, ns in por_cliente.items():
        if doc in com_contrato or len({n["competencia"] for n in ns}) < 3 or not clientes.obter(doc):
            continue
        valor, vezes = Counter(n["valor_cent"] for n in ns).most_common(1)[0]
        if vezes < 3:
            continue
        ultima = max(n["competencia"] for n in ns)
        k = financeiro.salvar_contrato({"cpf_cnpj": doc, "valor_cent": valor, "inicio": _proximo(ultima),
                                        "descricao": Counter(n["descricao"] for n in ns).most_common(1)[0][0] or None,
                                        "observacao": f"Detectado automaticamente: {vezes} notas de "
                                                      f"{financeiro.reais(valor)} nos últimos meses"})
        with db.conexao() as con:
            con.execute("UPDATE contratos SET confirmado=0, origem='detectado' WHERE id=?", (k["id"],))
        criados += 1
    if criados:
        db.registrar("contratos", f"{criados} contrato(s) recorrente(s) detectado(s) — aguardando confirmação")
    return criados


def confirmar_contratos(ids: list[int] | None = None) -> int:
    with db.conexao() as con:
        if ids:
            cur = con.execute(f"UPDATE contratos SET confirmado=1 WHERE id IN ({','.join('?' * len(ids))})", ids)
        else:
            cur = con.execute("UPDATE contratos SET confirmado=1 WHERE confirmado=0")
        return cur.rowcount


# ---------------------------------------------------------------- notas externas -> contas a receber

def inicio_financeiro() -> str:
    cfg = config.carregar()
    ini = cfg["financeiro"].get("inicio_financeiro")
    if not ini:
        ini = financeiro.hoje().isoformat()
        config.salvar({"financeiro": {"inicio_financeiro": ini}})
    return ini


def importar_titulos_externos(notas: list[dict]) -> int:
    ini = inicio_financeiro()
    existentes = {numero_curto(t["nfse_numero"]) for t in db.linhas("SELECT nfse_numero FROM titulos WHERE nfse_numero!=''")}
    prazo = int(config.carregar()["financeiro"]["prazo_avulso_dias"])
    novos = 0
    for n in notas:
        if n["emissao"] < ini or n["numero"] in existentes or not clientes.obter(n["cliente"]["cpf_cnpj"]):
            continue
        venc = (date.fromisoformat(n["emissao"]) + timedelta(days=prazo)).isoformat()
        tid = financeiro.criar_titulo(n["cliente"]["cpf_cnpj"], financeiro.reais(n["valor_cent"]), n["descricao"],
                                      venc, n["competencia"], emitir_nfse=False, cobrar=False)
        financeiro.atualizar_titulo(tid, nfse_status="emitida", nfse_numero=n["numero"], origem="importado",
                                    nfse_data=n["emissao"][:10])
        existentes.add(n["numero"])
        novos += 1
    if novos:
        db.registrar("importacao", f"{novos} nota(s) emitida(s) fora do sistema viraram contas a receber")
    return novos


def importar_xml(em: date | None = None) -> dict:
    cfg = config.carregar()
    from . import importador
    cnpj = emissor.so_digitos(emissor.env("ITABORAI_CNPJ"))
    if str(cfg["pastas"].get("xml_nfse") or "").strip():
        pasta = _pasta(cfg["pastas"]["xml_nfse"])
    elif cnpj:
        pasta = importador.arquivo_da_empresa(cnpj)
    else:
        return {"pasta": "não configurada"}
    if not pasta.exists():
        return {"pasta": "não encontrada"}
    cnpj = emissor.so_digitos(emissor.prestador_do_ambiente().cnpj)
    if len(cnpj) != 14:
        return {"pasta": "CNPJ da empresa não configurado"}
    r = clientes.importar_xmls(pasta, cnpj)
    notas = ler_notas(pasta, cnpj)
    return {"clientes_novos": r["clientes_novos"], "notas_lidas": len(notas),
            "contas_criadas": importar_titulos_externos(notas), "contratos_detectados": detectar_contratos(notas, em)}


# ---------------------------------------------------------------- extratos

def conta_da_empresa(texto: str) -> bool:
    """O extrato é da conta desta empresa? A primeira conta importada fica vinculada à empresa."""
    from . import empresas
    conta = conciliacao.conta_ofx(texto)
    contas = config.carregar()["financeiro"].get("contas_bancarias") or []
    if conta in contas and conta:
        return True
    if not conta:
        # extrato sem número da conta: com mais de uma empresa não dá para saber de quem é — só pela tela
        return len(empresas.listar()) == 1
    if any(conta in (empresas._cfg_de(p).get("financeiro", {}).get("contas_bancarias") or []) for _e, p in empresas._outras()):
        return False                   # conta de outra empresa
    if not contas:
        config.salvar({"financeiro": {"contas_bancarias": [conta]}})
        return True
    return False


def importar_manual(texto: str) -> dict:
    """Pela tela: o usuário escolheu a empresa. Extrato sem número da conta é aceito; conta de outra empresa, nunca."""
    if not conciliacao.conta_ofx(texto):
        return conciliacao.importar(texto)
    if not conta_da_empresa(texto):
        raise ValueError(f"Este extrato é da conta {conciliacao.conta_ofx(texto)}, que não é a desta empresa "
                         f"({', '.join(config.carregar()['financeiro']['contas_bancarias'])}). Troque de empresa "
                         "ou inclua a conta em Configurações.")
    return conciliacao.importar(texto)


def importar_extratos() -> dict:
    cfg = config.carregar()
    if not str(cfg["pastas"].get("extratos") or "").strip():
        return {"pasta": "não configurada"}
    pasta = _pasta(cfg["pastas"]["extratos"])
    if not pasta.exists():
        return {"pasta": "não encontrada"}
    feitos = {r["caminho"]: r["mtime"] for r in db.linhas("SELECT * FROM arquivos_processados")}
    total = {"arquivos": 0, "titulos": 0, "despesas": 0}
    ignorados = 0
    for arq in sorted(list(pasta.glob("*.ofx")) + list(pasta.glob("*.OFX"))):
        mtime = arq.stat().st_mtime
        if feitos.get(str(arq)) == mtime:
            continue
        conteudo = arq.read_bytes()
        try:
            texto = conteudo.decode("utf-8")
        except UnicodeDecodeError:
            texto = conteudo.decode("cp1252", errors="replace")
        if not conta_da_empresa(texto):
            ignorados += 1      # extrato de outra conta (outra empresa ou conta não vinculada): não concilia aqui
            continue
        r = conciliacao.importar(texto)
        total["arquivos"] += 1
        total["titulos"] += r["titulos"]
        total["despesas"] += r["despesas"]
        with db.conexao() as con:
            con.execute("INSERT OR REPLACE INTO arquivos_processados (caminho, mtime, quando) VALUES (?,?,?)",
                        (str(arq), mtime, db.agora()))
    if ignorados:
        total["outras_contas"] = ignorados
    return total


def importar_extrato_inter(dias: int | None = None, em: date | None = None) -> dict:
    """Baixa o extrato da conta do Inter pela API e concilia (sem arquivo OFX).
    Sem `dias`, continua de onde parou (com 3 dias de folga para lançamentos que entram atrasados)."""
    from datetime import timedelta
    from . import inter
    cfg = config.carregar()
    if not inter.configurado(cfg):
        return {"inter": "não configurado"}
    hoje = em or inter._hoje()
    ultimo = cfg["financeiro"].get("extrato_inter_ate") or ""
    if dias:
        inicio = hoje - timedelta(days=int(dias) - 1)
    elif ultimo:
        inicio = date.fromisoformat(ultimo) - timedelta(days=3)
    else:
        inicio = hoje - timedelta(days=29)
    if not dias and cfg["financeiro"].get("extrato_inter_sem_permissao") == hoje.isoformat():
        return {"inter": "sem permissão de extrato (aviso já registrado hoje)"}
    try:
        movs = inter.extrato(inicio, hoje, cfg)
    except inter.ErroInter as ex:
        if "extrato e saldo" in str(ex):        # o robô avisa uma vez por dia, não a cada hora
            config.salvar({"financeiro": {"extrato_inter_sem_permissao": hoje.isoformat()}})
        raise
    r = conciliacao.importar("", movs, origem="Extrato Inter (API)")
    config.salvar({"financeiro": {"extrato_inter_ate": hoje.isoformat()}})
    return r | {"periodo": f"{inicio.isoformat()} a {hoje.isoformat()}"}


# ---------------------------------------------------------------- resumo diário

def resumo_diario(resultado_robo: dict, em: date | None = None, forcar: bool = False) -> str:
    em = em or financeiro.hoje()
    cfg = config.carregar()
    para = cfg["resumo"].get("email_dono")
    if not para or not cfg["smtp"].get("host"):
        return "sem e-mail do dono ou SMTP"
    if cfg["resumo"].get("ultimo_envio") == em.isoformat() and not forcar:
        return "já enviado hoje"
    from . import horario
    if not forcar and not horario.comercial(cfg=cfg):
        return "fora do horário comercial (envia no próximo horário comercial)"
    p = relatorios.painel(em)
    recebidos = [t for t in db.linhas("SELECT * FROM titulos WHERE status='pago' AND data_pagamento=?",
                                      ((em - timedelta(days=1)).isoformat(),))]
    erros = db.linhas("SELECT cliente_nome, nfse_erro FROM titulos WHERE nfse_status='erro' AND status='aberto'")
    pendentes = db.linhas("SELECT COUNT(*) n FROM contratos WHERE confirmado=0 AND ativo=1")[0]["n"]
    b = lambda c: f"R$ {c / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")  # noqa: E731
    pct = f"{p['inadimplencia_pct']:.1f}".replace(".", ",") + "%"
    robo = {k: v for k, v in resultado_robo.items() if k not in ("executado", "data")}
    numeros = [("Recebido ontem", f"{b(sum(t['valor_pago_cent'] for t in recebidos))} ({len(recebidos)} pagamento(s))"),
               ("Recebido no mês", b(p["recebido_mes"])), ("A receber", b(p["a_receber"])),
               ("Em atraso", f"{b(p['atrasado'])} — {p['atrasado_qtd']} título(s), inadimplência {pct}"),
               ("A pagar", b(p["a_pagar"])), ("Receita recorrente (MRR)", b(p["mrr"]))]
    avisos = []
    if erros:
        avisos += ["NFS-e com erro (precisam de revisão):"] + [f"  - {e['cliente_nome']}: {e['nfse_erro'][:150]}" for e in erros]
    if pendentes:
        avisos.append(f"{pendentes} contrato(s) detectado(s) aguardando sua confirmação (menu Recorrência).")
    if p["criticos"]:
        avisos.append("Atraso crítico: " + ", ".join(p["criticos"][:15]))
    linhas = [f"Resumo financeiro de {em:%d/%m/%Y}", ""] + [f"{r}: {v}" for r, v in numeros]
    if robo:
        linhas += ["", "Robô de hoje:"] + [f"  - {k}: {v}" for k, v in robo.items()]
    if avisos:
        linhas += [""] + avisos
    from html import escape as e
    html = ('<!doctype html><html lang="pt-br"><head><meta charset="utf-8"></head><body style="margin:0;background:#f4f6f9">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px"><tr><td align="center">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;'
            'border:1px solid #e3e7ee;border-radius:12px;font-family:Segoe UI,Arial,sans-serif">'
            f'<tr><td style="padding:18px 24px;border-bottom:4px solid #1f4fbf"><b style="font-size:17px;color:#101828">'
            f'{e(cfg["empresa"]["nome"])}</b><br><span style="color:#667085;font-size:13px">Resumo financeiro de {em:%d/%m/%Y}</span></td></tr>'
            '<tr><td style="padding:18px 24px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0">'
            + "".join(f'<tr><td style="padding:7px 0;color:#667085;font-size:14px;border-bottom:1px solid #eef0f4">{e(r)}</td>'
                      f'<td style="padding:7px 0;text-align:right;font-weight:700;font-size:14px;color:#101828;border-bottom:1px solid #eef0f4">{e(v)}</td></tr>'
                      for r, v in numeros) + "</table>"
            + ('<div style="margin-top:16px;padding:12px 14px;background:#fdf1dc;border-radius:8px;color:#7a4500;font-size:14px;line-height:1.5">'
               + "<br>".join(e(a) for a in avisos) + "</div>" if avisos else "")
            + ('<p style="margin:16px 0 4px;font-size:13px;color:#667085;font-weight:700">ROBÔ DE HOJE</p><p style="margin:0;font-size:13px;color:#344054;line-height:1.6">'
               + "<br>".join(f"{e(k)}: {e(str(v))}" for k, v in robo.items()) + "</p>" if robo else "")
            + '</td></tr></table></td></tr></table></body></html>')
    cobranca.enviar_email(para, f"Resumo financeiro {em:%d/%m} — a receber {b(p['a_receber'])}", "\n".join(linhas), cfg,
                          html=html, teste=forcar, ref={"tipo": "Resumo financeiro"})
    config.salvar({"resumo": {"ultimo_envio": em.isoformat()}})
    return f"enviado para {para}"
