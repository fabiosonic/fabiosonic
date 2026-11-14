"""Fila diária de WhatsApp — o envio é sempre feito por uma pessoa.

O sistema prepara o texto, respeita a janela comercial e o teto diário, e gera
uma página com um botão por empresa. Quem clica, confere o contato na tela e
envia é alguém do escritório. O WhatsApp proíbe disparo automatizado a frio; a
punição é o banimento do número, então nada aqui envia sozinho.
"""
from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from . import base as B

FUSO = ZoneInfo("America/Sao_Paulo")
FERIADOS_FIXOS = {(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (11, 20), (12, 25)}


def _pascoa(ano: int) -> date:
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes, dia = divmod(h + l - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriado(d: date, extras: list[str] = ()) -> bool:
    p = _pascoa(d.year)
    moveis = {p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2), p + timedelta(days=60)}
    return (d.month, d.day) in FERIADOS_FIXOS or d in moveis or d.isoformat() in extras


def janela_aberta(cfg: dict, agora: datetime | None = None) -> tuple[bool, str]:
    """Só de segunda a sexta, no horário comercial de Brasília, fora de feriado."""
    agora = agora or datetime.now(FUSO)
    w = cfg["whatsapp"]
    if agora.weekday() >= 5:
        return False, "fim de semana"
    if feriado(agora.date(), w.get("feriados_extras", [])):
        return False, "feriado"
    if not w["hora_inicio"] <= agora.hour < w["hora_fim"]:
        return False, f"fora do horário comercial ({w['hora_inicio']}h–{w['hora_fim']}h)"
    return True, ""


def montar_texto(cfg: dict, lead: dict, agora: datetime | None = None) -> str:
    """Quatro blocos: quem somos, o que vimos, a conta, o convite (com CRC e saída)."""
    agora = agora or datetime.now(FUSO)
    e = cfg["escritorio"]
    saudacao = "Bom dia" if agora.hour < 12 else "Boa tarde"
    nome = lead["decisor_nome"].split()[0] if lead["decisor_nivel"] == "A" and lead["decisor_nome"] else ""
    abre = f"{saudacao}, {nome}." if nome else f"{saudacao}."
    return "\n\n".join([
        f"{abre} Aqui é da {e['nome']}, de {e['cidade']}.",
        lead["o_que_vimos"],
        lead["a_conta"],
        f"Se fizer sentido avaliar uma proposta, é só responder.\n{e['assinatura']} — {e['crc']}.\n"
        "Se não fizer sentido, é só avisar que não enviaremos mais mensagens.",
    ])


def enviados_hoje(base: B.Base, hoje: date) -> int:
    return sum(1 for l in base.leads if l["status"] == B.ENVIADO and l["canal_usado"] == "whatsapp"
               and l["data_1"] == hoje.isoformat())


def gerar(cfg: dict, base: B.Base, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(FUSO)
    aberta, motivo = janela_aberta(cfg, agora)
    if not aberta:
        return {"fila": [], "motivo": f"aguardando janela comercial: {motivo}"}
    vagas = cfg["whatsapp"]["teto_dia"] - enviados_hoje(base, agora.date())
    # quem já estava na fila e não foi enviado volta a concorrer
    for l in base.leads:
        if l["status"] == B.NA_FILA:
            l["status"] = B.PRONTO
    aptos = [l for l in base.leads if l["status"] == B.PRONTO and not l["alertas"]
             and B.eh_celular(l["whatsapp"]) and l["fonte_whatsapp"] and not base.esta_removido(l)]
    aptos.sort(key=lambda l: (l["prioridade"] or "C", l["decisor_nivel"] or "Z"))
    fila = aptos[: max(vagas, 0)]
    for l in fila:
        l["status"] = B.NA_FILA
        l["texto_enviado"] = montar_texto(cfg, l, agora)
    base.salvar()
    arq = base.pasta / f"fila-{agora.date().isoformat()}.html"
    arq.write_text(_pagina(cfg, fila, agora, vagas), encoding="utf-8")
    return {"fila": fila, "arquivo": str(arq), "vagas": vagas,
            "motivo": "" if fila else ("teto diário atingido" if vagas <= 0 else "nenhum lead pronto")}


def _pagina(cfg: dict, fila: list[dict], agora: datetime, vagas: int) -> str:
    cartoes = []
    for l in fila:
        e = html.escape
        link = f"https://web.whatsapp.com/send?phone=55{l['whatsapp']}&text={quote(l['texto_enviado'])}"
        evid = "".join(f"<li>{e(x['fato'])} — <a href='{e(x['url'])}'>{e(x['url'])}</a></li>"
                       for x in json.loads(l["evidencias"] or "[]"))
        dores = "".join(f"<li><b>{e(d['dor'])}</b> — {e(d['por_que_nesta_empresa'])}</li>"
                        for d in json.loads(l["dor"] or "[]"))
        decisor = (f"{e(l['decisor_nome'])} — {e(l['decisor_cargo'])} (nível {l['decisor_nivel']})"
                   if l["decisor_nome"] else "não identificado no site")
        lk = f" · <a href='{e(l['decisor_linkedin'])}'>buscar sócio/diretor no LinkedIn</a>" if l["decisor_linkedin"] else ""
        cartoes.append(f"""<section>
<h2>{e(l['id'])} · {e(l['empresa'])} <small>{e(l['subsetor'])} · {e(l['municipio'])} · prioridade {e(l['prioridade'])}</small></h2>
<p><b>Decisor:</b> {decisor}{lk}</p>
<p><b>Número:</b> {e(l['whatsapp'])} — publicado em <a href="{e(l['fonte_whatsapp'])}">{e(l['fonte_whatsapp'])}</a></p>
<details><summary>Material: dores e evidências</summary><ul>{dores}</ul><p>Gancho: {e(l['gancho'])}</p><ul>{evid}</ul></details>
<pre>{e(l['texto_enviado'])}</pre>
<a class="btn" target="_blank" rel="noopener" href="{html.escape(link)}">Abrir no WhatsApp Web</a>
<p class="obs">Confira na tela se o contato aberto é a empresa certa, envie, e registre:
<code>python -m prospeccao enviado {e(l['id'])}</code></p>
</section>""")
    corpo = "\n".join(cartoes) or "<p>Nenhuma empresa na fila.</p>"
    return f"""<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Fila de WhatsApp</title>
<style>body{{font:16px/1.5 system-ui;max-width:820px;margin:2rem auto;padding:0 1rem;color:#1c2430;background:#f6f7f9}}
section{{background:#fff;border:1px solid #d9dee5;border-radius:10px;padding:1rem 1.25rem;margin:1rem 0}}
h2{{font-size:1.1rem;margin:.2rem 0}}small{{font-weight:400;color:#5a6675}}
pre{{white-space:pre-wrap;background:#f0f3f6;padding:.8rem;border-radius:8px;font:15px/1.5 system-ui}}
.btn{{display:inline-block;background:#1f7a4d;color:#fff;padding:.55rem 1rem;border-radius:8px;text-decoration:none}}
.obs{{color:#5a6675;font-size:.9rem}}</style>
<h1>Fila de WhatsApp — {agora:%d/%m/%Y}</h1>
<p>{len(fila)} empresa(s) hoje · teto diário {cfg['whatsapp']['teto_dia']} · uma mensagem por empresa, sem sequência,
sem áudio e sem anexo. Envie com intervalo natural entre uma e outra. Se respostas sumirem ou houver bloqueio, pare.</p>
{corpo}</html>"""


def marcar_enviado(base: B.Base, id_: str, agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(FUSO)
    lead = base.por_id(id_)
    if lead["status"] != B.NA_FILA:
        raise SystemExit(f"{id_} não está na fila de hoje (status: {lead['status']}).")
    lead.update(status=B.ENVIADO, data_1=agora.date().isoformat(), canal_usado="whatsapp", gancho_usado=lead["gancho"])
    base.salvar()
    return lead


RESULTADOS = ("respondeu", "automatica", "sem_resposta", "negativa", "positiva", "reuniao", "optout")


def registrar_resultado(base: B.Base, id_: str, resultado: str, notas: str = "") -> dict:
    if resultado not in RESULTADOS:
        raise SystemExit("Resultado deve ser um de: " + ", ".join(RESULTADOS))
    lead = base.por_id(id_)
    lead.update(resultado=resultado, data_resultado=date.today().isoformat(), notas_resultado=notas or lead["notas_resultado"])
    if resultado == "optout":      # sai da base em todos os canais, para sempre
        base.registrar_remocao(lead, notas or "pediu remoção")
        lead["status"] = B.REMOVIDO
    base.salvar()
    return lead


def relatorio(base: B.Base) -> str:
    linhas = ["Status: " + ", ".join(f"{s}={sum(1 for l in base.leads if l['status'] == s)}"
                                     for s in sorted({l['status'] for l in base.leads}))]
    for campo, titulo in (("gancho_usado", "Por gancho"), ("setor", "Por setor")):
        linhas.append(f"\n{titulo} (enviados / com resultado / positivas+reunião):")
        for chave in sorted({l[campo] for l in base.leads if l["data_1"]}):
            grupo = [l for l in base.leads if l["data_1"] and l[campo] == chave]
            com = [l for l in grupo if l["resultado"]]
            bons = [l for l in com if l["resultado"] in ("positiva", "reuniao")]
            linhas.append(f"  {chave or '(sem gancho)'}: {len(grupo)} / {len(com)} / {len(bons)}")
    return "\n".join(linhas)
