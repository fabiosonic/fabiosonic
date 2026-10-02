"""Autonomia: checklist de implantação/saúde do sistema e fechamento mensal automático (relatório gerencial)."""

from __future__ import annotations

import html
import os
from datetime import date, datetime, timedelta
from pathlib import Path

from . import clientes, cobranca, config, contabil, db, emissor, financeiro, inter, nacional, relatorios


# ---------------------------------------------------------------- checklist

def checklist(em: date | None = None) -> dict:
    """Itens de implantação e saúde. Cada item: id, ok, nivel (erro|aviso), titulo, detalhe, pagina."""
    em = em or financeiro.hoje()
    cfg = config.carregar()
    emissor.carregar_env()
    itens = []

    def item(id_, ok, titulo, detalhe, pagina, nivel="erro"):
        itens.append({"id": id_, "ok": bool(ok), "titulo": titulo, "detalhe": "" if ok else detalhe,
                      "pagina": pagina, "nivel": nivel})

    nac = cfg["emissao"].get("canal") == "nacional"
    exigidas = ("ITABORAI_CNPJ",) if nac else ("ITABORAI_CNPJ", "ITABORAI_IM", "ITABORAI_CHAVE")
    nomes = {"ITABORAI_CNPJ": "CNPJ", "ITABORAI_IM": "inscrição municipal", "ITABORAI_CHAVE": "chave do webservice"}
    faltando = [nomes[k] for k in exigidas if not emissor.env(k)]
    item("prefeitura", not faltando, "Dados da empresa emissora" if nac else "Credenciais da prefeitura",
         "Falta informar: " + ", ".join(faltando), "config")
    item("servico", cfg["emissao"].get("servico_revisado", True), "Serviço padrão revisado",
         "Empresa nova: confira item da lista, desdobro, NBS, alíquota e IBS/CBS do serviço padrão.", "config")
    item("producao", emissor.em_producao(), "Emissão em produção",
         "O sistema está em homologação: as notas não têm validade e o robô não emite.", "painel", "aviso")
    if cfg["emissao"].get("canal") == "nacional":
        try:
            info = nacional.info_certificado(cfg)
            ok, det = not info["vencido"] and info["dias_restantes"] > 30, \
                f"Certificado A1 vence em {info['dias_restantes']} dia(s) ({info['validade']})."
        except emissor.ErroConfiguracao as ex:
            ok, det = False, str(ex)
        item("certificado", ok, "Certificado digital A1 (NFS-e Nacional)", det, "config")
    prov = cfg["cobranca"]["provedor"]
    if prov == "inter":
        item("inter", inter.configurado(cfg), "Boletos pelo Banco Inter",
             "Informe client_id, client_secret, certificado e chave da integração do Inter.", "config")
    if prov in ("pix", "inter"):
        item("pix", bool(cfg["empresa"].get("pix_chave")) or prov == "inter" and inter.configurado(cfg),
             "Chave PIX do escritório", "Sem chave PIX: as cobranças saem sem PIX copia e cola.", "config", "aviso")
    item("smtp", bool(cfg["smtp"].get("host")), "E-mail de envio (SMTP)",
         "Sem SMTP, a régua de cobrança e o resumo diário não são enviados.", "config")
    item("dono", bool(cfg["resumo"].get("email_dono")), "E-mail do dono para resumos",
         "Informe o e-mail que recebe o resumo diário e o fechamento mensal.", "config", "aviso")
    lst = clientes.listar()
    ativos = {t["cpf_cnpj"] for t in db.linhas("SELECT DISTINCT cpf_cnpj FROM titulos WHERE status='aberto' AND cobrar=1")}
    sem_contato = [c for c in lst if c["cpf_cnpj"] in ativos and not c.get("email") and not c.get("telefone")]
    item("contato", not sem_contato, "Clientes com contato para cobrança",
         f"{len(sem_contato)} cliente(s) com título em aberto sem e-mail nem telefone: "
         + _nomes(sem_contato), "clientes", "aviso")
    if prov == "inter":
        incompletos = [c for c in lst if c["cpf_cnpj"] in ativos and (not inter.cidade(c) or not c["endereco"].get("cep")
                                                                      or not c["endereco"].get("logradouro"))]
        item("cadastro", not incompletos, "Cadastro completo para boleto",
             f"{len(incompletos)} cliente(s) sem cidade, CEP ou endereço: "
             + _nomes(incompletos), "clientes")
    erros = db.linhas("SELECT COUNT(*) n FROM titulos WHERE status='aberto' AND nfse_status='erro'")[0]["n"]
    item("nfse_erro", erros == 0, "NFS-e sem erro", f"{erros} título(s) com NFS-e recusada para revisar.", "receber")
    ultima = (db.linhas("SELECT quando FROM log WHERE tipo='robo' ORDER BY id DESC LIMIT 1") or [{"quando": ""}])[0]["quando"]
    recente = bool(ultima) and datetime.strptime(ultima, "%Y-%m-%d %H:%M:%S").date() >= em - timedelta(days=1)
    item("robo", cfg["automacao"]["ativa"] and recente, "Robô trabalhando",
         "O robô está desligado." if not cfg["automacao"]["ativa"] else
         "O robô não roda há mais de 1 dia: abra o sistema ou rode INSTALAR.bat para agendar.", "config")
    ok = sum(i["ok"] for i in itens)
    return {"itens": itens, "ok": ok, "total": len(itens), "completo": ok == len(itens),
            "erros": sum(1 for i in itens if not i["ok"] and i["nivel"] == "erro")}


# ---------------------------------------------------------------- fechamento mensal

def _nomes(lst: list[dict], n: int = 3) -> str:
    nomes = ", ".join(c["razao_social"] for c in lst[:n])
    return nomes + (f" e mais {len(lst) - n}" if len(lst) > n else "")


def _b(c: int) -> str:
    sinal = "-" if c < 0 else ""
    return sinal + f"R$ {abs(c) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _contab(c: int) -> str:
    if not c:
        return "–"
    v = f"{abs(c) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"({v})" if c < 0 else v


def relatorio_mensal_html(competencia: str, em: date | None = None) -> str:
    """Relatório gerencial do mês (HTML autocontido, pronto para e-mail, impressão ou PDF)."""
    em = em or financeiro.hoje()
    ano, mes = int(competencia[:4]), int(competencia[5:])
    d = contabil.dre(ano, em)
    i = contabil.indicadores(em)
    ag = relatorios.aging(em)["faixas"]
    pc = relatorios.painel(em)
    cfg = config.carregar()
    e = html.escape
    col = mes - 1
    acum = lambda l: sum(l["valores"][:mes])  # noqa: E731
    linhas_dre = "".join(
        f'<tr style="{"font-weight:700;background:#f4f6f9" if l["tipo"] != "item" else "color:#475467"}">'
        f'<td style="padding:6px 10px;{"padding-left:26px" if l["tipo"] == "item" else ""}">{e(l["conta"])}</td>'
        f'<td style="padding:6px 10px;text-align:right">{_contab(l["valores"][col])}</td>'
        f'<td style="padding:6px 10px;text-align:right">{_contab(acum(l))}</td></tr>'
        for l in d["linhas"] if l["tipo"] != "item" or l["valores"][col] or acum(l))
    kpi = lambda rot, val, sub="": (f'<td style="padding:12px 14px;border:1px solid #e3e7ee;border-radius:8px;width:25%">'  # noqa: E731
                                    f'<div style="font-size:12px;color:#475467">{rot}</div><div style="font-size:19px;font-weight:700;'
                                    f'margin-top:4px">{val}</div><div style="font-size:11px;color:#667085">{sub}</div></td>')
    receita = d["linhas"][0]["valores"][col]
    resultado = d["linhas"][-1]["valores"][col]
    faixas = "".join(f'<td style="padding:8px;text-align:center"><div style="font-size:11px;color:#475467">{t}</div>'
                     f'<b>{_b(ag[k])}</b></td>' for k, t in (("a_vencer", "A vencer"), ("1_30", "1–30 dias"),
                                                              ("31_60", "31–60"), ("61_90", "61–90"), ("90_mais", "+90")))
    devedores = "".join(f'<tr><td style="padding:5px 10px">{e(x["cliente"])}</td><td style="padding:5px 10px;text-align:right">'
                        f'{_b(x["valor"])}</td></tr>' for x in pc["maiores_devedores"])
    return f"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><title>Fechamento {mes:02d}/{ano}</title></head>
<body style="margin:0;background:#f4f6f9;font-family:Segoe UI,Arial,sans-serif;color:#101828">
<div style="max-width:760px;margin:0 auto;background:#fff;padding:28px 32px">
<div style="border-bottom:2px solid #101828;padding-bottom:10px;margin-bottom:18px">
<div style="font-size:12px;color:#475467">{e(cfg["empresa"].get("nome", ""))}</div>
<div style="font-size:22px;font-weight:700">Fechamento de {mes:02d}/{ano}</div>
<div style="font-size:12px;color:#475467">Relatório gerencial automático · emitido em {em:%d/%m/%Y}</div></div>
<table style="width:100%;border-collapse:separate;border-spacing:8px 0"><tr>
{kpi("Receita do mês", _b(receita), "competência")}{kpi("Resultado do mês", _b(resultado), f"margem {round(resultado / receita * 100, 1) if receita else 0}%".replace(".", ","))}
{kpi("Em atraso", _b(pc["atrasado"]), f'{pc["atrasado_qtd"]} título(s)')}{kpi("Receita recorrente", _b(pc["mrr"]), f'{pc["contratos_ativos"]} contrato(s)')}
</tr></table>
<h3 style="font-size:15px;margin:24px 0 8px">Demonstração do resultado</h3>
<table style="width:100%;border-collapse:collapse;font-size:13px;border:1px solid #e3e7ee">
<tr style="background:#101828;color:#fff"><th style="padding:7px 10px;text-align:left">Conta</th><th style="padding:7px 10px;text-align:right">{mes:02d}/{ano}</th><th style="padding:7px 10px;text-align:right">Acumulado {ano}</th></tr>
{linhas_dre}</table>
<p style="font-size:11px;color:#667085">{e(d["nota"])}</p>
<h3 style="font-size:15px;margin:24px 0 8px">Indicadores <span style="font-weight:400;color:#667085;font-size:12px">(posição em {em:%d/%m/%Y})</span></h3>
<table style="width:100%;font-size:13px;border-collapse:collapse">
<tr><td style="padding:5px 0">Ponto de equilíbrio mensal</td><td style="text-align:right"><b>{_b(i["ponto_equilibrio"])}</b> (folga {str(i["folga_equilibrio_pct"]).replace(".", ",")}%)</td></tr>
<tr><td style="padding:5px 0">Inadimplência (90 dias)</td><td style="text-align:right"><b>{str(i["inadimplencia_90d"]).replace(".", ",")}%</b></td></tr>
<tr><td style="padding:5px 0">Atraso médio ponderado</td><td style="text-align:right"><b>{str(i["atraso_medio_ponderado"]).replace(".", ",")} dias</b></td></tr>
<tr><td style="padding:5px 0">Concentração nos 5 maiores clientes</td><td style="text-align:right"><b>{str(i["concentracao_top5"]).replace(".", ",")}%</b></td></tr>
<tr><td style="padding:5px 0">Clientes ativos / sem faturamento recente</td><td style="text-align:right"><b>{i["clientes_ativos"]} / {len(i["clientes_perdidos"])}</b></td></tr>
</table>
<h3 style="font-size:15px;margin:24px 0 8px">Contas a receber por faixa de atraso <span style="font-weight:400;color:#667085;font-size:12px">(posição em {em:%d/%m/%Y})</span></h3>
<table style="width:100%;border:1px solid #e3e7ee;font-size:13px"><tr>{faixas}</tr></table>
{f'<h3 style="font-size:15px;margin:24px 0 8px">Maiores devedores</h3><table style="width:100%;font-size:13px;border-collapse:collapse">{devedores}</table>' if devedores else ""}
<p style="font-size:11px;color:#667085;margin-top:28px;border-top:1px solid #e3e7ee;padding-top:10px">Gerado automaticamente pelo sistema financeiro. Valores gerenciais: o DAS é estimado pela alíquota efetiva do Anexo III.</p>
</div></body></html>"""


def pasta_relatorios(cfg: dict | None = None) -> Path:
    cfg = cfg or config.carregar()
    p = Path(os.path.expanduser(cfg["pastas"].get("relatorios") or "~/Downloads/Relatorios financeiros"))
    return p if p.is_absolute() else emissor.RAIZ / p


def fechamento_mensal(em: date | None = None, forcar: bool = False) -> str:
    """No dia configurado (padrão: dia 3), gera o fechamento do mês anterior, salva o HTML e envia ao dono."""
    em = em or financeiro.hoje()
    cfg = config.carregar()
    ref = (em.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    if not forcar:
        if em.day < int(cfg["resumo"].get("dia_fechamento", 3)):
            return "aguardando o dia do fechamento"
        if cfg["resumo"].get("ultimo_fechamento") == ref:
            return f"fechamento de {ref} já feito"
    doc = relatorio_mensal_html(ref, em)
    arq = pasta_relatorios(cfg) / f"Fechamento {ref}.html"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(doc, encoding="utf-8")
    enviado = ""
    para = cfg["resumo"].get("email_dono")
    if para and cfg["smtp"].get("host"):
        cobranca.enviar_email(para, f"Fechamento financeiro de {ref[5:]}/{ref[:4]}",
                              "Seu relatório de fechamento está em anexo e no corpo deste e-mail (versão HTML).",
                              cfg, html=doc)
        enviado = f" e enviado para {para}"
    config.salvar({"resumo": {"ultimo_fechamento": ref}})
    db.registrar("fechamento", f"Fechamento de {ref} salvo em {arq}{enviado}")
    return f"fechamento de {ref} salvo{enviado}"
