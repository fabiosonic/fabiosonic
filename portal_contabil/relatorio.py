"""Geração de relatórios da auditoria: HTML, Excel (XLSX) e JSON."""
from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from html import escape
from pathlib import Path

from .auditoria import Resultado
from .auditoria.conciliacao import valor_esperado
from .modelos import SEVERIDADES
from .util import fmt_doc, moeda, pct

ROTULO_SEV = {"CRITICO": "Crítico", "ALTO": "Alto", "MEDIO": "Médio", "BAIXO": "Baixo", "INFO": "Informativo"}
ROTULO_REGIME = {"simples": "Simples Nacional", "mei": "MEI", "normal": "Regime normal (Presumido/Real)",
                 "desconhecido": "Não identificado"}
SITUACAO = {"autorizada": "Autorizada", "cancelada": "Cancelada", "sem_protocolo": "Sem protocolo",
            "denegada": "Denegada"}


def valor_recuperavel(res: Resultado) -> Decimal:
    """Dinheiro recuperável já quantificado: retenções indevidas sofridas e ISS retido pago em dobro.

    As bases de monofásico/ST não entram aqui: são receitas a segregar, não o tributo em si.
    """
    total = Decimal(0)
    for a in res.achados_detalhados:
        if a.valor and ((a.codigo == "NFS001" and a.severidade == "ALTO") or a.codigo == "SN012"):
            total += a.valor
    return total


def _data(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "-"


# =================================================================== JSON

def _json_default(o):
    if isinstance(o, Decimal):
        return str(o)
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    if is_dataclass(o):
        return asdict(o)
    raise TypeError(type(o))


def gerar_json(res: Resultado) -> str:
    dados = {
        "empresa": asdict(res.empresa),
        "indice_conformidade": res.indice_conformidade,
        "severidades": res.por_severidade(),
        "indicadores": res.indicadores,
        "achados": [asdict(a) for a in res.achados],
        "achados_detalhados": [asdict(a) for a in res.achados_detalhados],
        "apuracao_mensal": [asdict(l) for l in res.apuracao],
        "conciliacao": {
            "conciliados": len(res.conciliacao.conciliados),
            "creditos_sem_nota": [asdict(l) for l in res.conciliacao.creditos_sem_nota],
            "notas_sem_recebimento": [d.chave for d in res.conciliacao.notas_sem_recebimento],
        },
        "erros_importacao": [asdict(e) for e in res.contexto.lote.erros],
    }
    return json.dumps(dados, default=_json_default, ensure_ascii=False, indent=2)


# =================================================================== HTML

CSS = """
:root{--bg:#f6f7f9;--card:#fff;--fg:#1c2330;--muted:#5b6575;--line:#e3e6eb;--accent:#1f5eff;
--crit:#b42318;--alto:#c4320a;--medio:#b54708;--baixo:#475467;--info:#155eef;
--crit-bg:#fef3f2;--alto-bg:#fff4ed;--medio-bg:#fffaeb;--baixo-bg:#f2f4f7;--info-bg:#eff4ff;--ok:#067647}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1218;--card:#171b23;--fg:#e6e9ef;
--muted:#9aa3b2;--line:#2a303b;--accent:#6f9bff;--crit:#ff8a80;--alto:#ffab70;--medio:#fdd36b;--baixo:#c2c8d2;
--info:#8fb0ff;--crit-bg:#3a1714;--alto-bg:#3a2114;--medio-bg:#3a3014;--baixo-bg:#232833;--info-bg:#17233d;--ok:#6ce9a6}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:36px 0 12px}
.sub{color:var(--muted);margin:0}
.grid{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));margin-top:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.card b{display:block;font-size:22px;font-variant-numeric:tabular-nums}.card span{color:var(--muted);font-size:13px}
.score b{color:var(--ok)}.score.mid b{color:var(--medio)}.score.low b{color:var(--crit)}
.tag{display:inline-block;font-size:12px;font-weight:600;padding:2px 8px;border-radius:99px;white-space:nowrap}
.tag.CRITICO{color:var(--crit);background:var(--crit-bg)}.tag.ALTO{color:var(--alto);background:var(--alto-bg)}
.tag.MEDIO{color:var(--medio);background:var(--medio-bg)}.tag.BAIXO{color:var(--baixo);background:var(--baixo-bg)}
.tag.INFO{color:var(--info);background:var(--info-bg)}
.achado{background:var(--card);border:1px solid var(--line);border-left-width:4px;border-radius:8px;
padding:12px 16px;margin-bottom:10px}
.achado.CRITICO{border-left-color:var(--crit)}.achado.ALTO{border-left-color:var(--alto)}
.achado.MEDIO{border-left-color:var(--medio)}.achado.BAIXO{border-left-color:var(--baixo)}
.achado.INFO{border-left-color:var(--info)}
.achado h3{font-size:15px;margin:6px 0}
.achado p{margin:4px 0}.meta{color:var(--muted);font-size:13px}.rec{font-weight:500}
.wrap{overflow-x:auto;background:var(--card);border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600;background:var(--bg)}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tr:last-child td{border-bottom:0}
.filtros{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:12px}
.filtros button{border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:99px;
padding:4px 12px;cursor:pointer;font:inherit;font-size:13px}.filtros button.on{border-color:var(--accent);color:var(--accent)}
footer{margin-top:40px;color:var(--muted);font-size:12.5px}
"""

JS = """
document.querySelectorAll('.filtros button').forEach(b=>b.addEventListener('click',()=>{
document.querySelectorAll('.filtros button').forEach(x=>x.classList.remove('on'));b.classList.add('on');
const s=b.dataset.s;document.querySelectorAll('.achado').forEach(a=>{
a.style.display=(s==='todos'||a.classList.contains(s))?'':'none'})}))
"""


def _tabela(cabecalho: list[str], linhas: list[list], numericas: set[int] = frozenset(), limite=1000) -> str:
    th = "".join(f'<th class="{"n" if i in numericas else ""}">{escape(c)}</th>' for i, c in enumerate(cabecalho))
    corpo = []
    for linha in linhas[:limite]:
        corpo.append("<tr>" + "".join(
            f'<td class="{"n" if i in numericas else ""}">{escape(str(v))}</td>' for i, v in enumerate(linha)) + "</tr>")
    extra = (f'<p class="meta">Exibindo {limite} de {len(linhas)} linhas. A lista completa está no Excel.</p>'
             if len(linhas) > limite else "")
    if not linhas:
        return '<p class="meta">Nenhum registro.</p>'
    return f'<div class="wrap"><table><thead><tr>{th}</tr></thead><tbody>{"".join(corpo)}</tbody></table></div>{extra}'


def gerar_html(res: Resultado) -> str:
    emp, ind, ctx = res.empresa, res.indicadores, res.contexto
    score = res.indice_conformidade
    classe_score = "" if score >= 80 else ("mid" if score >= 50 else "low")
    sev = res.por_severidade()
    impacto = valor_recuperavel(res)

    cards = [
        f'<div class="card score {classe_score}"><b>{score}/100</b><span>Índice de conformidade</span></div>',
        f'<div class="card"><b>{ind["documentos"]}</b><span>Documentos fiscais ({ind["emitidas"]} emitidos · '
        f'{ind["recebidas"]} recebidos)</span></div>',
        f'<div class="card"><b>{moeda(Decimal(ind["receita_total"]))}</b><span>Receita bruta apurada</span></div>',
        f'<div class="card"><b>{sev["CRITICO"] + sev["ALTO"]}</b><span>Achados críticos/altos</span></div>',
        f'<div class="card"><b>{moeda(impacto)}</b><span>Tributos retidos indevidamente ou em duplicidade '
        f'(recuperáveis)</span></div>',
        f'<div class="card"><b>{ind["lancamentos"]}</b><span>Lançamentos bancários ({ind["conciliados"]} conciliados)</span></div>',
    ]

    filtros = ['<button class="on" data-s="todos">Todos</button>'] + [
        f'<button data-s="{s}">{ROTULO_SEV[s]} ({sev[s]})</button>' for s in SEVERIDADES if sev[s]]

    achados_html = []
    for a in res.achados:
        valor = f' · <b>{moeda(a.valor)}</b>' if a.valor else ""
        base = f'<p class="meta">Base legal: {escape(a.base_legal)}</p>' if a.base_legal else ""
        ref = (f'<p class="meta">Referência: {escape(a.referencia[:120])}</p>'
               if a.referencia and len(a.referencia) > 8 else "")
        achados_html.append(
            f'<article class="achado {a.severidade}"><span class="tag {a.severidade}">{ROTULO_SEV[a.severidade]}</span> '
            f'<span class="meta">{escape(a.codigo)} · {escape(a.categoria)}{valor}</span>'
            f'<h3>{escape(a.titulo)}</h3><p>{escape(a.descricao)}</p>'
            f'<p class="rec">O que fazer: {escape(a.recomendacao)}</p>{base}{ref}</article>')

    apur = [[l.competencia, moeda(l.receita), moeda(l.rbt12) + (" *" if l.parcial else ""),
             moeda(l.folha12) if l.folha12 is not None else "-", pct(l.fator_r)] for l in res.apuracao]

    conc = res.conciliacao
    sem_nota = [[_data(l.data), moeda(l.valor), l.memo[:60], l.conta] for l in conc.creditos_sem_nota]
    sem_receb = [[d.rotulo, _data(d.data_emissao), d.destinatario.nome[:40] or fmt_doc(d.destinatario.documento),
                  moeda(valor_esperado(d))] for d in conc.notas_sem_recebimento]

    docs = sorted(ctx.lote.documentos, key=lambda d: (d.data_emissao or date.min, d.numero))
    docs_linhas = [[d.tipo, d.numero, _data(d.data_emissao),
                    ctx.papel(d),
                    (d.destinatario if ctx.eh_emitida(d) else d.emitente).nome[:40],
                    moeda(d.valor_total), SITUACAO.get(d.situacao, d.situacao)] for d in docs]
    erros = [[e.arquivo, e.motivo] for e in ctx.lote.erros]

    periodo = (f'{_data(ind["periodo_inicio"])} a {_data(ind["periodo_fim"])}'
               if ind["periodo_inicio"] else "sem documentos datados")
    regime = ROTULO_REGIME.get(emp.regime, emp.regime) + (" (inferido)" if emp.regime_inferido else "")

    conc_html = ""
    if conc.executada:
        conc_html = f"""<h2>Conciliação bancária</h2>
<p class="sub">{len(conc.conciliados)} recebimento(s) vinculado(s) a notas · {len(conc.creditos_sem_nota)} crédito(s) sem nota ·
{len(conc.notas_sem_recebimento)} nota(s) sem recebimento.</p>
<h3>Créditos sem documento fiscal</h3>{_tabela(["Data", "Valor", "Histórico", "Conta"], sem_nota, {1})}
<h3>Notas emitidas sem recebimento identificado</h3>{_tabela(["Documento", "Emissão", "Cliente", "Valor esperado"], sem_receb, {3})}"""

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Auditoria Fiscal</title><style>{CSS}</style></head>
<body><main>
<h1>Auditoria fiscal · {escape(emp.nome or "Empresa")}</h1>
<p class="sub">CNPJ {escape(fmt_doc(emp.cnpj))} · {escape(regime)} · Período {escape(periodo)} · {ind["arquivos_lidos"]} arquivo(s) lido(s)</p>
<div class="grid">{"".join(cards)}</div>
<h2>Achados da auditoria ({len(res.achados)})</h2>
<div class="filtros">{"".join(filtros)}</div>
{"".join(achados_html) or '<p class="meta">Nenhum achado. Documentação consistente.</p>'}
<h2>Receita bruta, RBT12 e Fator R</h2>
{_tabela(["Competência", "Receita do mês", "RBT12", "Folha 12 meses", "Fator R"], apur, {1, 2, 3, 4})}
<p class="meta">* RBT12 calculado com menos de 12 meses de histórico no lote.</p>
{conc_html}
<h2>Documentos importados</h2>
{_tabela(["Tipo", "Número", "Emissão", "Papel", "Contraparte", "Valor", "Situação"], docs_linhas, {5}, limite=500)}
<h2>Erros de importação</h2>{_tabela(["Arquivo", "Motivo"], erros)}
<footer>Relatório gerado automaticamente em {datetime.now().strftime("%d/%m/%Y %H:%M")}. Os achados são indícios
apontados por regras automáticas e devem ser validados pelo contador responsável antes de qualquer retificação,
conforme a NBC PG 01 e a NBC TG 1000.</footer>
</main><script>{JS}</script></body></html>"""


# =================================================================== XLSX

def gerar_xlsx(res: Resultado, caminho: Path) -> bool:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        return False
    wb = Workbook()
    negrito = Font(bold=True, color="FFFFFF")
    fundo = PatternFill("solid", fgColor="1F3A68")
    cores = {"CRITICO": "F8D7DA", "ALTO": "FDE2CF", "MEDIO": "FFF3CD", "BAIXO": "E9ECEF", "INFO": "DCE8FF"}

    def aba(titulo, cabecalho, linhas, larguras=None, primeira=False):
        ws = wb.active if primeira else wb.create_sheet()
        ws.title = titulo[:31]
        ws.append(cabecalho)
        for c in ws[1]:
            c.font, c.fill = negrito, fundo
        for linha in linhas:
            ws.append([float(v) if isinstance(v, Decimal) else v for v in linha])
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, w in enumerate(larguras or [], start=1):
            ws.column_dimensions[ws.cell(1, i).column_letter].width = w
        return ws

    emp, ind = res.empresa, res.indicadores
    aba("Resumo", ["Indicador", "Valor"], [
        ["Empresa", emp.nome], ["CNPJ", fmt_doc(emp.cnpj)], ["Regime", ROTULO_REGIME.get(emp.regime, emp.regime)],
        ["Índice de conformidade", res.indice_conformidade],
        *[[k.replace("_", " ").capitalize(), str(v) if isinstance(v, date) else v] for k, v in ind.items()],
        *[[f"Achados {ROTULO_SEV[s]}", n] for s, n in res.por_severidade().items()],
    ], [34, 40], primeira=True)

    ws = aba("Achados", ["Severidade", "Código", "Categoria", "Título", "Descrição", "Recomendação",
                         "Base legal", "Referência", "Valor (R$)"],
             [[ROTULO_SEV[a.severidade], a.codigo, a.categoria, a.titulo, a.descricao, a.recomendacao,
               a.base_legal, a.referencia, a.valor] for a in res.achados],
             [12, 9, 22, 45, 70, 70, 40, 30, 14])
    for row, a in zip(ws.iter_rows(min_row=2), res.achados):
        row[0].fill = PatternFill("solid", fgColor=cores[a.severidade])
        for c in row[3:7]:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    aba("Achados detalhados", ["Severidade", "Código", "Título", "Descrição", "Base legal", "Chave/Referência",
                               "Valor (R$)"],
        [[ROTULO_SEV[a.severidade], a.codigo, a.titulo, a.descricao, a.base_legal, a.referencia, a.valor]
         for a in res.achados_detalhados], [12, 9, 50, 80, 40, 46, 14])

    ctx = res.contexto
    aba("Documentos", ["Tipo", "Chave", "Número", "Série", "Emissão", "Papel", "Emitente CNPJ", "Emitente",
                       "Destinatário CNPJ", "Destinatário", "Valor total", "Receita apurada", "Situação",
                       "ISS retido", "Retenções federais", "Arquivo"],
        [[d.tipo, d.chave, d.numero, d.serie, d.data_emissao,
          ctx.papel(d),
          fmt_doc(d.emitente.documento), d.emitente.nome, fmt_doc(d.destinatario.documento), d.destinatario.nome,
          d.valor_total, ctx.receita_por_doc.get(d.chave), SITUACAO.get(d.situacao, d.situacao),
          "Sim" if d.iss_retido else "", d.total_retencoes_federais or None, d.arquivo]
         for d in ctx.lote.documentos], [7, 46, 10, 6, 12, 10, 20, 32, 20, 32, 14, 14, 13, 9, 14, 40])

    aba("Itens NF-e", ["Chave", "Número", "Item", "Código", "Descrição", "NCM", "CFOP", "CST ICMS", "CSOSN",
                       "CST PIS", "Qtd", "Valor", "Desconto", "ICMS", "ICMS-ST", "PIS", "COFINS", "IPI", "IBS/CBS"],
        [[d.chave, d.numero, i.numero, i.codigo, i.descricao, i.ncm, i.cfop, i.cst_icms, i.csosn, i.cst_pis,
          i.quantidade, i.valor_produto, i.desconto, i.valor_icms, i.valor_icms_st, i.valor_pis, i.valor_cofins,
          i.valor_ipi, "Sim" if i.tem_ibscbs else ""]
         for d in ctx.lote.documentos for i in d.itens])

    aba("Apuração mensal", ["Competência", "Receita", "RBT12", "Meses na base", "Folha 12m", "Fator R"],
        [[l.competencia, l.receita, l.rbt12, l.meses_base, l.folha12,
          float(l.fator_r) if l.fator_r is not None else None] for l in res.apuracao], [12, 16, 16, 12, 16, 10])

    conc = res.conciliacao
    if conc.executada:
        aba("Créditos sem nota", ["Data", "Valor", "Histórico", "Conta", "FITID", "Arquivo"],
            [[l.data, l.valor, l.memo, l.conta, l.fitid, l.arquivo] for l in conc.creditos_sem_nota], [12, 14, 50, 20, 20, 30])
        aba("Notas sem recebimento", ["Documento", "Chave", "Emissão", "Cliente", "Valor esperado"],
            [[d.rotulo, d.chave, d.data_emissao, d.destinatario.nome, valor_esperado(d)]
             for d in conc.notas_sem_recebimento], [22, 46, 12, 36, 14])
        aba("Conciliados", ["Documento", "Emissão", "Valor esperado", "Data crédito", "Valor creditado", "Diferença",
                            "Histórico"],
            [[p.documento.rotulo, p.documento.data_emissao, valor_esperado(p.documento), p.lancamento.data,
              p.lancamento.valor, p.diferenca, p.lancamento.memo] for p in conc.conciliados])
        aba("Créditos não operacionais", ["Data", "Valor", "Histórico", "Tipo"],
            [[l.data, l.valor, l.memo, "Não operacional"] for l in conc.creditos_nao_operacionais]
            + [[l.data, l.valor, l.memo, "Adquirente"] for l in conc.creditos_adquirente])

    aba("Erros de importação", ["Arquivo", "Motivo"], [[e.arquivo, e.motivo] for e in ctx.lote.erros], [60, 80])

    for ws in wb.worksheets:
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, float) and ws.cell(1, c.column).value not in ("Fator R", "Qtd"):
                    c.number_format = '#,##0.00'
                elif isinstance(c.value, date):
                    c.number_format = "DD/MM/YYYY"
                elif ws.cell(1, c.column).value == "Fator R" and c.value is not None:
                    c.number_format = "0.00%"
    wb.save(caminho)
    return True


def salvar(res: Resultado, pasta: str | Path) -> dict[str, Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = {"html": pasta / "auditoria.html", "json": pasta / "auditoria.json"}
    saidas["html"].write_text(gerar_html(res), encoding="utf-8")
    saidas["json"].write_text(gerar_json(res), encoding="utf-8")
    xlsx = pasta / "auditoria.xlsx"
    if gerar_xlsx(res, xlsx):
        saidas["xlsx"] = xlsx
    return saidas
