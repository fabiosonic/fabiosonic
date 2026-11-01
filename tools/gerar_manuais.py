#!/usr/bin/env python3
"""Gera um manual de emissao de notas fiscais por empresa (HTML pronto para PDF).

Uso: python3 tools/gerar_manuais.py
Entrada: dados/notas_analisadas.json + tools/empresas.py
Saida:   manuais/<slug>.html e manuais/index.html
"""
import html
import json
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "dados"))  # parecer por empresa: dados locais, fora do Git
from empresas import CCLASS, EMPRESAS, SEM_NOTAS_NOTA  # noqa: E402

E = html.escape
HOJE = date(2026, 10, 31)


def cnpj_fmt(c):
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


def brl(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return "–"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_nbs(n):
    if not n or not n.isdigit() or len(n) != 9:
        return n or "–"
    return f"{n[0]}.{n[1:5]}.{n[5:7]}.{n[7:9]}"


def fmt_ctrib(c):
    if not c or len(c) != 6:
        return c or "–"
    return f"{c[:2]}.{c[2:4]}.{c[4:]}"


CSS = """
:root{
  --navy-900:#040a1f; --navy-800:#08133a; --navy-700:#0c1d55; --navy-600:#13297a;
  --blue-500:#1f6fff; --blue-400:#3d8bff; --cyan-300:#5cc8ff; --cyan-100:#d9f1ff;
  --ink:#0b1533; --muted:#4a5a80; --line:#c9d7f2; --paper:#ffffff; --tint:#f2f7ff;
  --ok:#0f8a5f; --warn:#b86a00; --bad:#c0272d;
}
*{box-sizing:border-box}
html,body{margin:0;background:#dfe7f6;color:var(--ink);font-family:"Inter","Segoe UI",Roboto,Arial,sans-serif;font-size:10.5pt;line-height:1.5}
@page{size:A4;margin:0}
.page{width:210mm;height:297mm;margin:12px auto;background:var(--paper);position:relative;padding:20mm 18mm 22mm;box-shadow:0 4px 24px rgba(4,10,31,.18);overflow:hidden;page-break-after:always}
.page:last-child{page-break-after:auto}
@media print{html,body{background:#fff}.page{margin:0;box-shadow:none}}
/* capa */
.capa{background:radial-gradient(120% 80% at 70% 20%,#123a9c 0%,var(--navy-800) 45%,var(--navy-900) 100%);color:#fff;padding:0;display:flex;flex-direction:column}
.capa .foto{height:155mm;background:url(assets/capa.jpg) center 18%/cover no-repeat;position:relative}
.capa .foto:after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(4,10,31,0) 45%,var(--navy-900) 100%)}
.capa .grade{position:absolute;inset:0;background-image:linear-gradient(rgba(92,200,255,.07) 1px,transparent 1px),linear-gradient(90deg,rgba(92,200,255,.07) 1px,transparent 1px);background-size:9mm 9mm;pointer-events:none}
.capa .txt{padding:6mm 18mm 0;position:relative}
.capa .selo{display:inline-block;border:1px solid var(--cyan-300);color:var(--cyan-300);border-radius:20px;padding:2px 12px;font-size:8.5pt;letter-spacing:.12em;text-transform:uppercase}
.capa h1{font-size:25pt;line-height:1.15;margin:5mm 0 2mm;font-weight:800;letter-spacing:-.01em}
.capa h1 span{color:var(--cyan-300)}
.capa .emp{font-size:15pt;font-weight:700;margin-top:6mm;color:#fff}
.capa .meta{color:var(--cyan-100);font-size:10pt;margin-top:1.5mm}
.capa .rod{position:absolute;bottom:12mm;left:18mm;right:18mm;display:flex;justify-content:space-between;font-size:8.5pt;color:#9fb6e6;border-top:1px solid rgba(92,200,255,.35);padding-top:3mm}
/* cabecalho de paginas */
.topo{position:absolute;top:0;left:0;right:0;height:11mm;background:linear-gradient(90deg,var(--navy-900),var(--navy-700) 60%,var(--blue-500));color:#cfe6ff;font-size:8pt;display:flex;align-items:center;justify-content:space-between;padding:0 18mm;letter-spacing:.04em}
.topo b{color:#fff}
.pe{position:absolute;bottom:8mm;left:18mm;right:18mm;font-size:7.5pt;color:var(--muted);display:flex;justify-content:space-between;border-top:1px solid var(--line);padding-top:2mm}
h2{font-size:15pt;color:var(--navy-700);margin:6mm 0 3mm;padding-left:4mm;border-left:4px solid var(--blue-500)}
h2 small{display:block;font-size:8.5pt;color:var(--blue-500);font-weight:600;letter-spacing:.14em;text-transform:uppercase}
h3{font-size:11.5pt;color:var(--navy-600);margin:5mm 0 2mm}
p{margin:0 0 2.5mm}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:3mm;margin:3mm 0}
.card{background:var(--tint);border:1px solid var(--line);border-radius:6px;padding:3mm}
.card .k{font-size:7.5pt;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.card .v{font-size:11pt;font-weight:700;color:var(--navy-700)}
.card.dark{background:linear-gradient(135deg,var(--navy-800),var(--navy-600));border-color:var(--navy-600)}
.card.dark .k{color:var(--cyan-300)} .card.dark .v{color:#fff}
table{width:100%;border-collapse:collapse;margin:2mm 0 4mm;font-size:9pt}
th{background:var(--navy-700);color:#fff;text-align:left;padding:2mm 2.5mm;font-weight:600}
td{padding:1.8mm 2.5mm;border-bottom:1px solid var(--line);vertical-align:top}
tr:nth-child(even) td{background:#f7faff}
.code{font-family:"JetBrains Mono",Consolas,monospace;font-weight:700;color:var(--navy-700);white-space:nowrap}
.hl{background:linear-gradient(135deg,#e6f2ff,#d3eaff);border:1px solid var(--cyan-300);border-radius:8px;padding:4mm;margin:3mm 0}
.hl h3{margin-top:0}
.novo{display:grid;grid-template-columns:repeat(4,1fr);gap:2mm;margin:2mm 0}
.novo>div{background:#fff;border:1px solid var(--line);border-radius:6px;padding:2mm 2.5mm}
.novo .k{font-size:7pt;text-transform:uppercase;letter-spacing:.08em;color:var(--muted)}
.novo .v{font-family:Consolas,monospace;font-size:12pt;font-weight:800;color:var(--blue-500)}
.tag{display:inline-block;border-radius:10px;padding:0 8px;font-size:8pt;font-weight:700}
.tag.ok{background:#e1f6ee;color:var(--ok)} .tag.warn{background:#fff1dc;color:var(--warn)} .tag.bad{background:#fde5e6;color:var(--bad)}
ul{margin:1mm 0 3mm;padding-left:5mm} li{margin-bottom:1.3mm}
.achados li::marker{color:var(--warn)} .benef li::marker{color:var(--ok)}
.passos{counter-reset:p;list-style:none;padding:0}
.passos li{counter-increment:p;position:relative;padding-left:10mm;margin-bottom:2.2mm}
.passos li:before{content:counter(p);position:absolute;left:0;top:0;width:6.5mm;height:6.5mm;border-radius:50%;background:var(--blue-500);color:#fff;font-weight:700;font-size:8.5pt;display:flex;align-items:center;justify-content:center}
.linha{display:grid;grid-template-columns:22mm 1fr;gap:3mm;margin-bottom:2mm}
.linha .ano{background:var(--navy-700);color:#fff;font-weight:800;border-radius:6px;text-align:center;padding:1.5mm 0}
.linha .ano.atual{background:linear-gradient(135deg,var(--blue-500),var(--cyan-300))}
.nota{font-size:8pt;color:var(--muted)}
.aviso{border-left:4px solid var(--warn);background:#fff8ec;padding:3mm;border-radius:0 6px 6px 0;font-size:9pt;margin:3mm 0}
.sim td.num,.sim th.num{text-align:right;white-space:nowrap}
"""


def page(conteudo, emp_nome, n, extra_cls=""):
    return f"""<section class="page {extra_cls}">
<div class="topo"><span><b>MORAES &amp; OLIVEIRA</b> · Manual de Emissão de Notas Fiscais 2027</span><span>{E(emp_nome)}</span></div>
{conteudo}
<div class="pe"><span>MINUTA elaborada com apoio de IA · Pendente de revisão do contador responsável · Ref. {HOJE.strftime('%d/%m/%Y')}</span><span>Página {n}</span></div>
</section>"""


def capa(emp, cnpj):
    return f"""<section class="page capa">
<div class="foto"></div><div class="grade"></div>
<div class="txt">
<span class="selo">Reforma Tributária · Edição 2027</span>
<h1>Manual de Emissão de<br><span>Notas Fiscais</span> e Guia da<br>Reforma Tributária 2027</h1>
<div class="emp">{E(emp['nome'])}</div>
<div class="meta">CNPJ {cnpj_fmt(cnpj)} · {E(emp['municipio'])}</div>
<div class="meta">{E(emp['atividade'])}</div>
</div>
<div class="rod"><span>MINUTA · PRONTO PARA REVISÃO HUMANA · Sem validade até aprovação do contador responsável</span><span>Documento exclusivo do cliente · {HOJE.strftime('%B de %Y').replace('October','outubro')}</span></div>
</section>"""


def secao_perfil(emp, cnpj, dados):
    notas = dados["notas"]
    valores = [float(x.get("valor_servico") or x.get("valor_total") or 0) for x in notas]
    comp = sorted({(x.get("competencia") or x.get("emissao") or "")[:7] for x in notas if (x.get("competencia") or x.get("emissao"))})
    linhas = "".join(
        f"<tr><td>{E(x['tipo'])}</td><td>{E((x.get('competencia') or x.get('emissao') or '')[:10])}</td>"
        f"<td class='code'>{E(fmt_ctrib(x.get('cTribNac')) if x.get('cTribNac') else (x['itens'][0]['NCM'] if x.get('itens') else '–'))}</td>"
        f"<td class='code'>{E(fmt_nbs(x.get('cNBS')) if x.get('cNBS') else '–')}</td>"
        f"<td>{E(x.get('aliq_iss') or ('retido' if x.get('ret_issqn') == '2' else '–'))}</td>"
        f"<td>{E(x.get('cst_pis_cofins') or '–')}</td>"
        f"<td>{E(x.get('p_tot_trib_sn') or '–')}</td>"
        f"<td style='text-align:right;white-space:nowrap'>{brl(x.get('valor_servico') or x.get('valor_total'))}</td></tr>"
        for x in notas
    )
    return f"""
<h2><small>Seção 1</small>Perfil fiscal da empresa</h2>
<div class="cards">
<div class="card dark"><div class="k">Regime tributário</div><div class="v">{'Simples Nacional' if emp['regime_curto']=='SN' else 'Regime normal (Lucro Presumido)'}</div></div>
<div class="card"><div class="k">Município de emissão</div><div class="v">{E(emp['municipio'])}</div></div>
<div class="card"><div class="k">Perfil dos clientes</div><div class="v">{E(emp['perfil_cliente'])}</div></div>
</div>
<p><b>Enquadramento identificado nas notas:</b> {E(emp['regime'])}.</p>
<h2><small>Seção 2</small>Notas fiscais analisadas</h2>
<p>Foram localizadas <b>{dados['total_drive']}</b> NFS-e de emissão própria no padrão nacional no repositório do portal (mais DPS/RPS e notas municipais, quando houver). Foram auditadas <b>{len(notas)}</b> notas, distribuídas ao longo do período ({E(', '.join(comp))}), cobrindo todos os códigos de serviço utilizados. Valor das notas auditadas: <b>{brl(sum(valores))}</b>.</p>
<table><tr><th>Documento</th><th>Compet.</th><th>cTribNac / NCM</th><th>NBS</th><th>ISS %</th><th>CST PIS</th><th>% SN</th><th style='text-align:right'>Valor</th></tr>{linhas}</table>
<p class="nota">Dados de tomadores pessoa física foram omitidos (LGPD). % SN = percentual aproximado de tributos do Simples Nacional informado na nota.</p>
"""


def classif_atual(notas, ctrib):
    """CST/cClassTrib efetivamente informados nas notas do mesmo codigo de servico."""
    cod = ctrib.replace(".", "")
    vist = sorted({(x.get("ibscbs_cst"), x.get("ibscbs_cclasstrib")) for x in notas
                   if x.get("cTribNac") == cod and x.get("ibscbs_cclasstrib")})
    return ", ".join(f"{c} / {k}" for c, k in vist) if vist else "não informado nas notas analisadas"


def bloco_servico(s, i, emp, notas):
    a, n = s["atual"], s["novo"]
    cst, nome_cst, red, desc = CCLASS[n["cclass"]]
    sn = emp["regime_curto"] == "SN"
    if red:
        tag = f"<span class='tag ok'>Redução de {red}%{' – só no regime regular' if sn else ''}</span>"
    else:
        tag = "<span class='tag warn'>Tributação integral</span>"
    atual_cls = classif_atual(notas, a["cTribNac"])
    ok = n["cclass"] in atual_cls
    marca = "" if atual_cls.startswith("não") else (" <span class='tag ok'>correto</span>" if ok else " <span class='tag bad'>divergente</span>")
    red_txt = (f"<b>{red}% / {red}%</b>" + (" – aplica-se apenas se a empresa optar por apurar IBS/CBS no regime regular; no DAS não se aplica (art. 41, § 2º)" if sn else "")) if red else "–"
    return f"""
<div class="hl">
<h3>Serviço {i}: {E(a['desc_nac'])} {tag}</h3>
<table><tr><th style="width:34%">Campo</th><th>Hoje (2026)</th><th>A partir de jan/2027</th></tr>
<tr><td>Código de Tributação Nacional (cTribNac – LC 116)</td><td class="code">{E(a['cTribNac'])}</td><td class="code">{E(n['cTribNac'])}</td></tr>
<tr><td>Código de tributação municipal</td><td class="code">{E(a['cTribMun'])}</td><td class="code">{E(a['cTribMun'] if a['cTribMun'][0].isdigit() else 'preencher (cadastro municipal)')}</td></tr>
<tr><td>NBS</td><td class="code">{E(a['cNBS'])}</td><td class="code">{E(n['cNBS'])}</td></tr>
<tr><td>ISS</td><td colspan="2">{E(a['iss'])}. Mantido em 2027; transição para o IBS conforme EC 132/2023 [pendente de validação normativa].</td></tr>
<tr><td>PIS/Cofins (CST)</td><td class="code">{E(a['pis'])}</td><td>Extintos – substituídos pela CBS</td></tr>
<tr><td>CST / cClassTrib IBS-CBS</td><td class="code">{E(atual_cls)}{marca}</td><td class="code">{cst} / {n['cclass']}</td></tr>
<tr><td>Redução de alíquota IBS / CBS</td><td>–</td><td>{red_txt}</td></tr>
</table>
<div class="novo">
<div><div class="k">cTribNac</div><div class="v">{E(n['cTribNac'])}</div></div>
<div><div class="k">NBS</div><div class="v" style="font-size:10pt">{E(n['cNBS'])}</div></div>
<div><div class="k">CST IBS/CBS</div><div class="v">{cst}</div></div>
<div><div class="k">cClassTrib</div><div class="v">{n['cclass']}</div></div>
</div>
<p><b>Fundamento:</b> {E(desc)}<br><b>Orientação:</b> {E(n['obs'])}</p>
</div>"""


def bloco_mercadoria(m):
    a, n = m["atual"], m["novo"]
    return f"""
<div class="hl"><h3>Mercadorias (NF-e)</h3>
<table><tr><th>NCM</th><th>Produto</th><th>CFOP observado</th><th>ICMS (CRT/CSOSN)</th><th>CST IBS/CBS</th><th>cClassTrib</th></tr>
<tr><td class="code">{E(a['ncm'])}</td><td>{E(a['desc'])}</td><td>{E(a['cfop'])}</td><td>{E(a['csosn'])}</td><td class="code">{n['cst']}</td><td class="code">{n['cclass']}</td></tr></table>
<p><b>Orientação:</b> {E(n['obs'])}</p></div>"""


def secao_codigos(emp, notas):
    """Uma pagina por servico; mercadorias vao junto do ultimo servico."""
    intro = """<h2><small>Seção 3</small>Códigos que a empresa passa a usar</h2>
<p>Tabela “de → para” de cada serviço emitido pela empresa. Os códigos de CST e cClassTrib foram conferidos na <b>Tabela de Classificação Tributária do IBS e da CBS</b> publicada no Portal Nacional de DF-e e nos Anexos da LC 214/2025.</p>"""
    blocos = [bloco_servico(sv, i + 1, emp, notas) for i, sv in enumerate(emp["servicos"])]
    blocos[0] = intro + blocos[0]
    if emp.get("mercadorias"):
        blocos.append("".join(bloco_mercadoria(m) for m in emp["mercadorias"]))
    for i in range(1, len(blocos)):
        blocos[i] = "<h2><small>Seção 3 (continuação)</small>Códigos que a empresa passa a usar</h2>" + blocos[i]
    return blocos


def secao_achados(emp):
    a = "".join(f"<li>{E(x)}</li>" for x in emp["achados"])
    return f"""<h2><small>Seção 4</small>Inconsistências e pontos de atenção</h2><ul class="achados">{a}</ul>"""


def secao_passos(emp):
    sv = emp["servicos"][0]["novo"]
    sn = emp["regime_curto"] == "SN"
    return f"""<h2><small>Seção 5</small>Passo a passo de emissão (Emissor Nacional / portal)</h2>
<ol class="passos">
<li><b>Prestador:</b> confira CNPJ, inscrição municipal e o regime: {'“Optante do Simples Nacional – ME/EPP” (opSimpNac = 3) e a forma de apuração correta (regApTribSN)' if sn else '“Não optante” (opSimpNac = 1)'}.</li>
<li><b>Tomador:</b> CNPJ/CPF completo e endereço. Tomador PJ do regime regular usa a nota para crédito de IBS/CBS – dados errados impedem o crédito.</li>
<li><b>Serviço:</b> selecione o código nacional <span class="code">{E(sv['cTribNac'])}</span>, o código municipal cadastrado e a NBS <span class="code">{E(sv['cNBS'])}</span>. Local da prestação = município onde o serviço é executado (obras: município da obra).</li>
<li><b>Descrição:</b> o que foi feito, período/competência, contrato ou obra. Não inclua mensagens, dados de saúde ou CPF de terceiros.</li>
<li><b>Valores:</b> valor do serviço, descontos incondicionais (reduzem a base) e condicionais (não reduzem). Informe retenções (ISS, INSS, IR/CSRF) quando o tomador for obrigado a reter.</li>
<li><b>Grupo IBS/CBS (Reforma):</b> CST <span class="code">{CCLASS[sv['cclass']][0]}</span>, cClassTrib <span class="code">{sv['cclass']}</span>, indicador de operação conforme a tabela do emissor (local do consumo). {'No Simples, o preenchimento do grupo IBS/CBS segue o leiaute vigente da NFS-e [pendente de validação normativa].' if sn else 'A CBS e o IBS são destacados por fora e entram no total da nota.'}</li>
<li><b>Conferência final:</b> compare com a tabela da Seção 3. Nota com código errado deve ser corrigida conforme as regras de substituição/cancelamento do emissor e do município [pendente de validação normativa].</li>
</ol>"""


def secao_beneficios(emp):
    b = "".join(f"<li>{E(x)}</li>" for x in emp["beneficios"])
    return f"""<h2><small>Seção 6</small>Benefícios fiscais da atividade</h2><ul class="benef">{b}</ul>"""


def pct(v, casas=2):
    return f"{v:.{casas}f}".replace(".", ",") + "%"


def secao_simulacao(emp):
    """Cenario HIPOTETICO: a aliquota de referencia oficial da CBS (art. 349) nao foi confirmada nesta revisao."""
    ref_hip = 8.8                       # HIPOTESE para ilustracao - nao e aliquota oficial
    cbs = ref_hip - 0.1                 # art. 347 (reducao de 0,1 p.p. em 2027-2028)
    ibs = 0.1                           # art. 344 (0,05% UF + 0,05% municipio)
    base = 10000.0
    linhas = ""
    for sv in emp["servicos"]:
        red = CCLASS[sv["novo"]["cclass"]][2]
        cbs_ef = cbs * (1 - red / 100)  # art. 347, par. 1o, I (reducao proporcional)
        ibs_ef = ibs * (1 - red / 100)  # art. 344, par. unico, I
        linhas += (f"<tr><td>{E(sv['novo']['cTribNac'])} – CBS (ref. hipotética {pct(ref_hip,1)} – 0,1 p.p.)</td><td class='num'>{pct(cbs)}</td><td class='num'>{red}%</td><td class='num'>{pct(cbs_ef)}</td><td class='num'>{brl(base*cbs_ef/100)}</td></tr>"
                   f"<tr><td>{E(sv['novo']['cTribNac'])} – IBS 2027 (art. 344)</td><td class='num'>{pct(ibs)}</td><td class='num'>{red}%</td><td class='num'>{pct(ibs_ef,3)}</td><td class='num'>{brl(base*ibs_ef/100)}</td></tr>")
    if emp["regime_curto"] == "SN":
        txt = ("<p>Optante do Simples que <b>permanece no DAS</b> segue as regras do Simples (LC 214/2025, art. 41, § 2º): as reduções da LC 214 não entram no cálculo do DAS "
               "e a carga depende das tabelas da LC 123 vigentes em 2027 [pendente de validação normativa]. "
               "A tabela abaixo ilustra o cenário de <b>IBS/CBS pelo regime regular</b> (fora do DAS), útil para decidir a opção:</p>")
    else:
        txt = "<p>Empresa do regime normal: a CBS passa a ser devida em janeiro de 2027. Ilustração sobre R$ 10.000,00 de faturamento por serviço:</p>"
    return f"""<h3>Cenário hipotético (R$ 10.000,00 por serviço)</h3>{txt}
<p><b>Fórmula:</b> CBS = base × (alíquota de referência – 0,1 p.p.) × (1 – redução); IBS = base × 0,1% × (1 – redução). Arredondamento: 2 casas.</p>
<table class="sim"><tr><th>Serviço / tributo</th><th class="num">Alíquota</th><th class="num">Redução</th><th class="num">Efetiva</th><th class="num">Valor</th></tr>{linhas}</table>
<p class="nota"><b>Cenário hipotético, não é cálculo oficial:</b> a alíquota de referência da CBS para 2027 é fixada por Resolução do Senado Federal (LC 214/2025, art. 349) e não foi confirmada nesta revisão. Créditos sobre aquisições não foram considerados. Recalcular com a alíquota oficial antes de qualquer decisão.</p>"""


def secao_reforma(emp):
    sn = emp["regime_curto"] == "SN"
    reg = (
        """<h3>Regras para o Simples Nacional</h3><ul>
<li><b>Opção 1 – permanecer no DAS (LC 214/2025, art. 41, § 2º):</b> IBS e CBS são recolhidos dentro da guia única. O crédito do cliente PJ fica limitado ao montante recolhido no DAS [pendente de validação normativa do dispositivo].</li>
<li><b>Opção 2 – regime regular de IBS/CBS (LC 214/2025, art. 41, §§ 3º e 4º):</b> IBS e CBS apurados e pagos fora do DAS, pelas regras gerais (com reduções da LC 214 e créditos nas compras). O cliente PJ se credita do valor integral destacado.</li>
<li><b>Prazo:</b> a LC 214/2025 incluiu na LC 123/2006 (art. 13, §§ 10 e 11) a opção semestral, irretratável, exercida em setembro (para o 1º semestre) e abril (para o 2º semestre). Essa alteração produz efeitos a partir de 01/01/2027 (LC 214, art. 544, III); a regra de transição para o 1º semestre de 2027 e a regulamentação do CGSN estão <b>pendentes de validação normativa</b>. Confirmar no Portal do Simples Nacional se a opção já foi oferecida/exercida; pela regra legal, a próxima janela seria abril/2027.</li>
<li><b>Regra prática:</b> clientela pessoa física → DAS; clientela PJ do Lucro Real/Presumido com margem apertada → simular o híbrido.</li></ul>"""
        if sn else
        """<h3>Regras para o regime normal (Lucro Presumido)</h3><ul>
<li>Os dispositivos que instituem o PIS e a Cofins são revogados a partir de 01/01/2027 (LC 214/2025, art. 542). A CBS é não cumulativa: dá direito a crédito nas aquisições com documento fiscal, observadas as vedações da lei.</li>
<li>O IBS e a CBS não integram a própria base de cálculo (LC 214/2025, art. 12, § 2º, I) e devem ser destacados no documento fiscal.</li>
<li>Split payment (LC 214/2025, art. 31): os prestadores de serviços de pagamento deverão segregar e recolher o IBS e a CBS na liquidação financeira da transação. A implantação depende de regulamento – acompanhar.</li>
<li>IRPJ e CSLL não mudam com a Reforma do consumo.</li></ul>"""
    )
    return f"""<h2><small>Seção 7</small>Manual da Reforma Tributária – ano 2027</h2>
<div class="linha"><div class="ano">2026</div><div>Ano de teste: CBS 0,9% (art. 346) e IBS estadual 0,1% (art. 343), com o valor recolhido compensado com PIS/Cofins (art. 348).</div></div>
<div class="linha"><div class="ano atual">2027</div><div><b>Revogação do PIS e da Cofins</b> (art. 542) e cobrança da <b>CBS pela alíquota de referência</b> fixada por Resolução do Senado (art. 349), reduzida em 0,1 p.p. em 2027–2028 (art. 347). IBS de 0,05% estadual + 0,05% municipal (art. 344). <b>IPI</b>: redução a zero prevista na EC 132/2023 [pendente de validação normativa]; a LC 214 (art. 454) trata da redução a zero para produtos da Zona Franca de Manaus. Imposto Seletivo sobre bens prejudiciais à saúde/meio ambiente (instituído pela LC 214/2025; início da cobrança [pendente de validação normativa]).</div></div>
<div class="linha"><div class="ano">2028</div><div>Mesma estrutura de 2027.</div></div>
<div class="linha"><div class="ano">2029–32</div><div>Transição gradual do ICMS e do ISS para o IBS, conforme EC 132/2023 [percentuais pendentes de validação normativa].</div></div>
<div class="linha"><div class="ano">2033</div><div>Sistema pleno: CBS + IBS + Imposto Seletivo (EC 132/2023) [pendente de validação normativa].</div></div>
<h3>O que muda na nota fiscal em 2027</h3><ul>
<li>Grupo <b>IBS/CBS</b> na NFS-e e NF-e: CST, cClassTrib, base de cálculo, alíquotas, reduções e valores.</li>
<li><b>NBS</b> coerente com o código de serviço – as reduções da LC 214 são definidas por NBS (Anexos II e III).</li>
<li>Local da operação definido pelas regras de destino da LC 214/2025 [dispositivo pendente de citação].</li>
<li>O crédito do adquirente depende de documento fiscal idôneo – nota com classificação errada prejudica o cliente.</li>
<li>Cada cClassTrib só é aceito com o CST correspondente (os 3 primeiros dígitos do cClassTrib são o CST – Informe Técnico 2025.002); redução só para NBS listada nos Anexos.</li></ul>
<!--SPLIT-->{reg}
{secao_simulacao(emp)}
<div class="aviso"><b>Checklist até 31/12/2026:</b> (1) atualizar o cadastro de serviços no emissor com os códigos da Seção 3; (2) corrigir as inconsistências da Seção 4; (3) definir com o escritório a permanência no DAS ou o regime híbrido; (4) revisar contratos e preços considerando a CBS; (5) guardar todas as notas de compras para crédito.</div>"""


def secao_fontes():
    return """<h2><small>Referências</small>Base legal, fontes e estado da revisão</h2>
<table><tr><th>Fonte oficial</th><th>Dispositivos usados</th><th>Consulta</th></tr>
<tr><td>Lei Complementar nº 214/2025 – texto publicado no portal de legislação do Senado Federal (legis.senado.leg.br/norma/40180341)</td><td>arts. 12, § 2º; 31; 41; 127; 129; 130; 251; 252; 253; 261; 343; 344; 346; 347; 348; 349; 454; 542; 544, III; Anexos II e III; LC 123/2006, art. 13, §§ 10 e 11 (redação da LC 214)</td><td>31/10/2026</td></tr>
<tr><td>Tabela de Classificação Tributária do IBS e da CBS (CST e cClassTrib) – Portal Nacional de DF-e (dfe-portal.svrs.rs.gov.br/DFE/TabelaClassificacaoTributaria)</td><td>cClassTrib, CST, % de redução e documentos aceitos</td><td>31/10/2026</td></tr>
<tr><td>Informe Técnico 2025.002 v1.40 – Tabelas de Classificação do IBS e da CBS (Portal Nacional da NF-e / encarregados do leiaute)</td><td>relação CST × cClassTrib (3 primeiros dígitos)</td><td>31/10/2026</td></tr>
<tr><td>Notas fiscais (XML) da empresa no repositório do portal do escritório</td><td>códigos atuais, regime informado, ISS, NBS</td><td>31/10/2026</td></tr></table>
<p class="nota"><b>Limitações:</b> foi usado o texto da LC 214/2025 disponível no portal do Senado; alterações posteriores (inclusive a LC 227/2026, referida na tabela oficial) não foram conferidas dispositivo a dispositivo. Itens marcados “pendente de validação normativa” não devem ser aplicados sem conferência na fonte oficial. O texto oficial do Planalto não pôde ser acessado nesta revisão.</p>
<div class="aviso"><b>Estado: PRONTO PARA REVISÃO HUMANA.</b> Minuta elaborada com apoio de inteligência artificial. Não substitui a análise e a aprovação do contador responsável, que deve conferir os pontos pendentes antes do envio ao cliente. Nenhuma alteração foi feita em sistemas, cadastros ou declarações.</div>"""


def gerar(cnpj, emp, dados):
    nome = emp["nome"]
    paginas = [capa(emp, cnpj)]
    paginas.append(page(secao_perfil(emp, cnpj, dados), nome, 2))
    for cod in secao_codigos(emp, dados["notas"]):
        paginas.append(page(cod, nome, len(paginas) + 1))
    paginas.append(page(secao_achados(emp) + secao_passos(emp), nome, len(paginas) + 1))
    ref1, ref2 = secao_reforma(emp).split("<!--SPLIT-->")
    paginas.append(page(secao_beneficios(emp) + ref1, nome, len(paginas) + 1))
    paginas.append(page(ref2, nome, len(paginas) + 1))
    paginas.append(page(secao_fontes(), nome, len(paginas) + 1))
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Manual NF 2027 – {E(nome)}</title><style>{CSS}</style></head><body>{''.join(paginas)}</body></html>"""


def indice(clientes_sem_notas):
    linhas = "".join(
        f"<tr><td>{E(e['nome'])}</td><td class='code'>{cnpj_fmt(c)}</td><td>{E(e['municipio'])}</td><td>{E(e['atividade'])}</td>"
        f"<td class='code'>{' / '.join(s['novo']['cclass'] for s in e['servicos'])}</td>"
        f"<td><a href='{e['slug']}.pdf'>PDF</a> · <a href='{e['slug']}.html'>HTML</a></td></tr>"
        for c, e in sorted(EMPRESAS.items(), key=lambda kv: kv[1]["nome"])
    )
    pend = "".join(f"<li>{E(n)}</li>" for n in clientes_sem_notas)
    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Manuais NF 2027</title><style>{CSS}</style></head><body>
<section class="page" style="height:auto;min-height:297mm;padding-top:24mm"><div class="topo"><span><b>MORAES &amp; OLIVEIRA</b> · Manuais de Emissão de Notas Fiscais 2027</span><span>Índice</span></div>
<h2><small>Índice</small>Manuais por empresa</h2>
<table><tr><th>Empresa</th><th>CNPJ</th><th>Município</th><th>Atividade</th><th>cClassTrib 2027</th><th>Arquivo</th></tr>{linhas}</table>
<h3>Clientes sem notas de saída no portal</h3><p>{E(SEM_NOTAS_NOTA)}</p><ul style="columns:2;font-size:8.5pt">{pend}</ul>
</section></body></html>"""


def main():
    dados = json.loads((RAIZ / "dados" / "notas_analisadas.json").read_text(encoding="utf-8"))
    saida = RAIZ / "manuais"
    saida.mkdir(exist_ok=True)
    for cnpj, emp in EMPRESAS.items():
        (saida / f"{emp['slug']}.html").write_text(gerar(cnpj, emp, dados[cnpj]), encoding="utf-8")
    pend_path = RAIZ / "dados" / "clientes_sem_notas.txt"
    pend = pend_path.read_text(encoding="utf-8").splitlines() if pend_path.exists() else []
    (saida / "index.html").write_text(indice(pend), encoding="utf-8")
    print(f"{len(EMPRESAS)} manuais gerados em {saida}")


if __name__ == "__main__":
    main()
