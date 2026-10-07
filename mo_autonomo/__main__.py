"""Linha de comando: python -m mo_autonomo <comando> --config config/config.yaml"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .util.arquivos import dumps, escrever_atomico


def _ctx(args, **kw):
    from .fluxos.contexto import carregar_config, montar_contexto
    return montar_contexto(carregar_config(args.config), **kw)


def cmd_ciclo(args):
    from .fluxos.ciclo import rodar_ciclo
    ctx = _ctx(args)
    e = rodar_ciclo(ctx)
    print(f"ciclo {e['_run_id'][:8]} ({ctx.config['modo']}): {e.get('emails_lidos', 0)} e-mail(s), "
          f"{len(e.get('anexos', []))} anexo(s), {len(e.get('lotes', []))} lote(s). Resumo: {e.get('resumo')}")


def cmd_retomar(args):
    from .fluxos.ciclo import grafo_ciclo
    ctx = _ctx(args)
    e = grafo_ciclo().retomar(args.run, ctx.trilha, ctx)
    print(f"retomado; resumo: {e.get('resumo')}")


def cmd_aprovar(args):
    from .aprovacao.lote import AprovacaoRecusada, aprovar_humano, carregar
    ctx = _ctx(args, fonte=object())
    lote = carregar(Path(args.lote))
    print(f"Lote {lote['id']}: {len(lote['acoes'])} ação(ões), {len(lote['achados'])} achado(s), "
          f"{len(lote['pendencias'])} pendência(s).")
    hash_inf = input("Cole o hash do lote conferido: ").strip()
    texto = input("Digite APROVADO para aprovar: ")
    try:
        destino = aprovar_humano(Path(args.lote), texto, hash_inf, args.usuario, ctx.trilha)
    except AprovacaoRecusada as exc:
        print(f"RECUSADO: {exc}")
        sys.exit(2)
    print(f"aprovado: {destino}")


def cmd_executar(args):
    from .fluxos.ciclo import executar_lote
    ctx = _ctx(args, fonte=object())
    for r in executar_lote(Path(args.aprovado), ctx):
        print(r)


def cmd_normas(args):
    from .especialista.motor import cobertura
    from .normas.catalogo import Catalogo
    cat = Catalogo.carregar(args.pasta)
    print("normas:", cat.resumo())
    if args.acao == "cobertura":
        for c in cobertura(cat):
            print(f"{'ATIVA  ' if c['ativa'] else 'INATIVA'} {c['natureza']:<11} {c['regra']:<26} {c['motivo']}")


def cmd_perfil(args):
    from .clientes.perfil import montar_perfil
    from .clientes.receita import extrair_carteira
    ctx = _ctx(args, fonte=object())
    cache = ctx.dados / "rfb_carteira.json"
    if args.acao == "atualizar":
        pasta = Path((ctx.config.get("receita") or {}).get("pasta_dados_abertos") or "dados/rfb")
        pasta = pasta if pasta.is_absolute() else Path(ctx.config["_base"]) / pasta
        dados = extrair_carteira(pasta, {e.cnpj for e in ctx.carteira},
                                 (ctx.config.get("receita") or {}).get("colunas"))
        escrever_atomico(cache, dumps(dados).encode())
        print(f"{len(dados)}/{len(ctx.carteira)} empresas encontradas nos dados abertos.")
        from .util.arquivos import loads
        receita = loads(cache.read_text(encoding="utf-8"))
    else:
        from .util.arquivos import loads
        receita = loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    linhas = ["codigo;apelido;cnpj;regime;fonte_regime;cnaes;natureza;uf;situacao_ativa;pendencias"]
    for emp in ctx.carteira:
        p = montar_perfil(emp, receita.get(emp.cnpj), ctx.catalogo, date.today())
        linhas.append(";".join([emp.codigo_dominio, emp.apelido, emp.cnpj, p.regime or "", p.regime_fonte,
                                ",".join(p.cnaes), p.natureza_juridica or "", p.uf or "", str(p.situacao_ativa),
                                " | ".join(f"{x.codigo}: {x.mensagem}" for x in p.pendencias)]))
    saida = ctx.dados / "relatorios" / f"perfis_{date.today():%Y%m%d}.csv"
    escrever_atomico(saida, "\n".join(linhas).encode("utf-8-sig"))
    print(f"relatório de perfis: {saida}")


def cmd_imap(args):
    from .fluxos.contexto import carregar_config, montar_fonte
    cfg = carregar_config(args.config)
    fonte = montar_fonte(cfg, lambda p: Path(p), date.today())
    print(fonte.testar() if hasattr(fonte, "testar") else "fonte não é IMAP")


def cmd_auditar(args):
    from .dominio.auditoria import auditar, ler_relatorio
    ctx = _ctx(args, fonte=object())
    cols = (ctx.config.get("dominio") or {}).get("relatorio_colunas") or {}
    rel = ler_relatorio(Path(args.relatorio), cols)
    docs = []
    from .documentos.classificador import classificar
    for d in ctx.trilha.documentos(args.competencia):
        if args.cnpj in d["cnpjs"]:
            row = ctx.trilha.con.execute("SELECT caminho_bruto FROM anexos WHERE sha256=?", (d["sha256"],)).fetchone()
            if row:
                r = classificar(Path(row[0]).read_bytes())
                if r["doc"]:
                    docs.append(r["doc"])
    achados = auditar(docs, rel, args.cnpj, args.competencia)
    for a in achados:
        print(f"[{a.regra}] {a.mensagem}")
    print(f"{len(achados)} divergência(s).")


def cmd_dp(args):
    from .dp.folha import conferir, ler_folha
    ctx = _ctx(args, fonte=object())
    r = conferir(ler_folha(Path(args.folha)), args.cnpj, ctx.catalogo)
    for i in r["inativas"]:
        print("INATIVA:", i)
    for a in r["achados"]:
        print(f"[{a.natureza}] {a.mensagem}")


def cmd_grafo(args):
    from .fluxos.ciclo import grafo_ciclo
    from .fluxos.documento import grafo_documento
    print("```mermaid\n" + grafo_ciclo().mermaid() + "\n```\n\n```mermaid\n" + grafo_documento().mermaid() + "\n```")


def main(argv=None):
    p = argparse.ArgumentParser(prog="mo_autonomo")
    sub = p.add_subparsers(dest="cmd", required=True)

    def com_config(nome, f, **kw):
        s = sub.add_parser(nome, **kw)
        s.add_argument("--config", default="config/config.yaml")
        s.set_defaults(f=f)
        return s

    com_config("ciclo", cmd_ciclo, help="captura + análise + lotes + pareceres")
    com_config("retomar", cmd_retomar).add_argument("--run", required=True)
    s = com_config("aprovar", cmd_aprovar)
    s.add_argument("--lote", required=True)
    s.add_argument("--usuario", required=True)
    com_config("executar", cmd_executar).add_argument("--aprovado", required=True)
    s = sub.add_parser("normas")
    s.add_argument("acao", choices=["validar", "cobertura"])
    s.add_argument("--pasta", default="config/normas")
    s.set_defaults(f=cmd_normas)
    com_config("perfil", cmd_perfil).add_argument("acao", choices=["atualizar", "relatorio"])
    com_config("imap", cmd_imap).add_argument("acao", choices=["testar"])
    s = com_config("auditar-dominio", cmd_auditar)
    s.add_argument("--relatorio", required=True)
    s.add_argument("--cnpj", required=True)
    s.add_argument("--competencia", required=True, help="AAAA-MM")
    s = com_config("dp", cmd_dp)
    s.add_argument("acao", choices=["conferir"])
    s.add_argument("--folha", required=True)
    s.add_argument("--cnpj", required=True)
    s = sub.add_parser("grafo")
    s.add_argument("acao", choices=["desenhar"])
    s.set_defaults(f=cmd_grafo)
    args = p.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    main()
