"""Painel HTML estático do ciclo (abre no navegador do escritório, sem servidor)."""
from __future__ import annotations

import html
from collections import Counter

from ..util.documentos_id import formatar_cnpj

CSS = """
:root{--bg:#f7f7f5;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e3e2dc;--ok:#1f7a4d;--warn:#a15c00;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#1f1f1d;--line:#33332f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px}h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:28px 0 8px}
.sub{color:var(--muted)}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:16px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}.kpi b{display:block;font-size:24px}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:13px;color:var(--muted)}
.tag{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;border:1px solid currentColor}
.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.wrap{overflow-x:auto}code{font-size:12px}
"""


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def gerar(estado: dict, ctx, cobertura: list[dict]) -> str:
    lotes = estado.get("lotes", [])
    gerais = estado.get("pendencias_gerais", [])
    aprovados = sum(1 for l in lotes if l.get("aprovado"))
    ativas = sum(1 for c in cobertura if c["ativa"])
    resumo_normas = ctx.catalogo.resumo()
    linhas_lotes = []
    for l in lotes:
        emp = ctx.carteira.get(l["cnpj"])
        nome = emp.apelido if emp else l["cnpj"]
        if l.get("aprovado"):
            sit = '<span class="tag ok">aprovado</span>'
        else:
            sit = '<span class="tag warn">aguarda APROVADO</span>'
        motivos = "<br>".join(_e(m) for m in (l.get("aguardando") or []))
        linhas_lotes.append(f"<tr><td>{_e(nome)}<br><span class='sub'>{_e(formatar_cnpj(l['cnpj']))}</span></td>"
                            f"<td>{_e(l['area'])}</td><td>{_e(l.get('competencia'))}</td><td>{sit}</td>"
                            f"<td>{motivos}</td><td><code>{_e(l['hash'][:16])}…</code></td></tr>")
    falhas_exec = [(x["lote"], r) for x in estado.get("execucoes", []) for r in x["resultado"]
                   if r.get("status") not in ("GRAVADO", "JA_EXISTIA")]
    linhas_falhas = [f"<tr><td><code>{_e(l)}</code></td><td>{_e(r.get('acao'))}</td><td class='bad'>{_e(r['status'])}</td></tr>"
                     for l, r in falhas_exec]
    por_codigo = Counter(p["codigo"] for p in gerais)
    linhas_gerais = [f"<tr><td>{_e(p['codigo'])}</td><td>{_e(p['mensagem'])}</td></tr>" for p in gerais[:200]]
    linhas_regras = [f"<tr><td>{_e(c['regra'])}</td><td>{_e(c['titulo'])}</td>"
                     f"<td><span class='tag {'ok' if c['ativa'] else 'bad'}'>{'ativa' if c['ativa'] else 'inativa'}</span></td>"
                     f"<td>{_e(c['natureza'])}</td><td>{_e(c['motivo'])}</td></tr>" for c in cobertura]
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Painel do ciclo</title><style>{CSS}</style></head>
<body><main><h1>Painel do ciclo {_e(estado['_run_id'][:8])}</h1>
<div class="sub">{ctx.hoje:%d/%m/%Y} · modo <b>{_e(ctx.config['modo'])}</b> · {len(ctx.carteira)} empresas na carteira</div>
<div class="kpis">
<div class="kpi"><b>{estado.get('emails_lidos', 0)}</b>e-mails novos</div>
<div class="kpi"><b>{len(estado.get('anexos', []))}</b>anexos processados</div>
<div class="kpi"><b>{len(lotes)}</b>lotes ({aprovados} aprovados)</div>
<div class="kpi"><b>{len(gerais)}</b>pendências sem empresa</div>
<div class="kpi"><b>{ativas}/{len(cobertura)}</b>regras ativas</div>
<div class="kpi"><b>{resumo_normas.get('CONFERIDO', 0)}/{len(ctx.catalogo.normas)}</b>normas conferidas</div>
</div>
<h2>Lotes</h2><div class="wrap"><table><tr><th>Empresa</th><th>Área</th><th>Competência</th><th>Situação</th><th>Por que aguarda</th><th>Hash</th></tr>
{''.join(linhas_lotes) or '<tr><td colspan=6>Nenhum lote neste ciclo.</td></tr>'}</table></div>
{('<h2>Execuções com falha (refeitas no próximo ciclo)</h2><div class="wrap"><table><tr><th>Lote</th><th>Ação</th><th>Erro</th></tr>' + ''.join(linhas_falhas) + '</table></div>') if linhas_falhas else ''}
<h2>Pendências sem empresa identificada</h2>
<div class="sub">{_e(', '.join(f'{k}: {v}' for k, v in por_codigo.items()) or 'nenhuma')}</div>
<div class="wrap"><table><tr><th>Código</th><th>Mensagem</th></tr>{''.join(linhas_gerais)}</table></div>
<h2>Cobertura das regras</h2>
<div class="wrap"><table><tr><th>Regra</th><th>O que verifica</th><th>Estado</th><th>Natureza</th><th>Motivo</th></tr>
{''.join(linhas_regras)}</table></div>
</main></body></html>"""
