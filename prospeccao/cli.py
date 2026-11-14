"""Linha de comando: python -m prospeccao <etapa>"""
from __future__ import annotations

import argparse

from . import base as B
from . import etapas, fila


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="prospeccao", description="Prospecção ativa para escritório de contabilidade.")
    p.add_argument("--config", default="config.json")
    p.add_argument("--dados", default="dados")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("nichos", help="1. lê o site do escritório e define os nichos")
    b = sub.add_parser("buscar", help="2. busca empresas dos nichos na região (Google Places API)")
    b.add_argument("--setor"); b.add_argument("--max", type=int, default=40)
    i = sub.add_parser("importar", help="2b. importa um CSV de leads (ex.: gosom/google-maps-scraper)")
    i.add_argument("csv"); i.add_argument("--setor", default=""); i.add_argument("--municipio", default="")
    q = sub.add_parser("qualificar", help="3-4. qualifica, coleta contato publicado e identifica o decisor")
    q.add_argument("--limite", type=int, default=25)
    m = sub.add_parser("material", help="5. prepara dores e o texto único por empresa")
    m.add_argument("--limite", type=int, default=25)
    sub.add_parser("revisar", help="reaplica o checklist nos textos editados à mão")
    sub.add_parser("fila", help="6. gera a fila de WhatsApp de hoje (envio manual)")
    e = sub.add_parser("enviado", help="registra que a mensagem saiu"); e.add_argument("id")
    r = sub.add_parser("resultado", help="registra a resposta do lead")
    r.add_argument("id"); r.add_argument("resultado", choices=fila.RESULTADOS); r.add_argument("--notas", default="")
    sub.add_parser("relatorio", help="taxas por gancho e por setor")
    sub.add_parser("servidor", help="modo automático: motor de envio, funil, webhook e painel")
    sub.add_parser("diagnostico", help="confere configuração, chaves, site e conexão antes de ligar")
    sub.add_parser("webhook", help="aponta o webhook da Evolution API para este servidor")
    a = p.parse_args(argv)

    base = B.Base(a.dados)
    if a.cmd == "relatorio":
        return print(fila.relatorio(base))
    if a.cmd == "enviado":
        return print(f"Registrado: {fila.marcar_enviado(base, a.id)['empresa']}")
    if a.cmd == "resultado":
        return print(f"Registrado: {fila.registrar_resultado(base, a.id, a.resultado, a.notas)['empresa']} = {a.resultado}")
    if a.cmd == "importar":
        return print(etapas.importar(base, a.csv, a.setor, a.municipio))
    if a.cmd == "revisar":
        ok = 0
        for l in base.leads:
            if l["status"] == B.QUALIFICADO and l["o_que_vimos"]:
                outros = [o["o_que_vimos"] for o in base.leads if o is not l and o["o_que_vimos"]]
                l["alertas"] = "; ".join(etapas.revisar(l, outros))
                if not l["alertas"]:
                    l["status"] = B.PRONTO
                    ok += 1
        base.salvar()
        return print(f"{ok} texto(s) liberado(s) para a fila.")

    cfg = B.carregar_config(a.config)
    if a.cmd == "diagnostico":
        from . import diagnostico
        raise SystemExit(0 if diagnostico.rodar(cfg, a.dados) else 1)
    if a.cmd == "webhook":
        from . import whatsapp
        p_ = cfg.get("painel", {})
        url = f"{p_.get('url_webhook', 'http://127.0.0.1:' + str(p_.get('porta', 8787))).rstrip('/')}/webhook/{p_.get('token', '')}"
        codigo = whatsapp.Evolution(cfg).configurar_webhook(url)
        return print("Webhook configurado." if codigo < 300 else f"A Evolution API recusou (HTTP {codigo}). Configure o webhook pelo painel dela.")
    if a.cmd == "servidor":
        from . import servidor
        return servidor.rodar(cfg, a.dados)
    if a.cmd == "nichos":
        out = etapas.nichos(cfg, a.dados)
        print(out["resumo_escritorio"])
        for n in out["nichos"]:
            print(f"- {n['setor']} / {n['subsetor']}: {n['por_que']}")
    elif a.cmd == "buscar":
        print(etapas.buscar(cfg, base, a.setor, a.max))
    elif a.cmd == "qualificar":
        print(etapas.qualificar(cfg, base, a.limite))
    elif a.cmd == "material":
        print(etapas.material(cfg, base, a.limite))
    elif a.cmd == "fila":
        out = fila.gerar(cfg, base)
        if out["fila"]:
            print(f"{len(out['fila'])} empresa(s) na fila. Abra {out['arquivo']} no navegador com o WhatsApp Web logado.")
        else:
            print(f"Fila vazia — {out['motivo']}.")
