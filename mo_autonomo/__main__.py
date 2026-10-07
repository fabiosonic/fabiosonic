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
    from .normas.monitor import carregar_alteradas, ficha_conferencia, monitorar
    if args.config:  # usa as pastas do config (pastas.normas / pastas.dados)
        from .fluxos.contexto import carregar_config
        cfg = carregar_config(args.config)
        base = Path(cfg["_base"])
        pastas = cfg.get("pastas") or {}
        args.pasta = str(base / (pastas.get("normas") or "config/normas"))
        args.dados = str(base / (pastas.get("dados") or "dados"))
    cat = Catalogo.carregar(args.pasta)
    textos = Path(args.dados) / "normas_textos"
    cat.marcar_alteradas(carregar_alteradas(textos))
    print("normas:", cat.resumo())
    if args.acao == "monitorar":
        for r in monitorar(cat, textos):
            print(f"{r['situacao']:<20} {r['id']}" + (f"  {r.get('erro')}" if r.get("erro") else ""))
    elif args.acao == "conferir":
        if not args.id:
            sys.exit("informe --id")
        print("ficha:", ficha_conferencia(cat, args.id, Path(args.dados) / "conferencia"))
    elif args.acao == "cobertura":
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
    r = fonte.testar() if hasattr(fonte, "testar") else "fonte não é IMAP"
    for linha in (r if isinstance(r, list) else [r]):
        print(linha)


def cmd_auditar(args):
    from .documentos.classificador import classificar
    from .dominio.auditoria import auditar, ler_relatorio
    from .util.documentos_id import so_digitos
    ctx = _ctx(args, fonte=object())
    cnpj = so_digitos(args.cnpj)
    cols = (ctx.config.get("dominio") or {}).get("relatorio_colunas") or {}
    if not cols.get("competencia"):
        sys.exit("config dominio.relatorio_colunas sem 'competencia': sem ela notas de outros meses "
                 "virariam divergência. Mapeie a coluna de competência/data do relatório.")
    rel, ilegiveis = [], []
    for n, l in enumerate(ler_relatorio(Path(args.relatorio), cols), start=1):
        mesma = _mesma_competencia(l.get("competencia") or "", args.competencia)
        if mesma is None:
            ilegiveis.append(f"linha {n}: competência {l.get('competencia')!r} não reconhecida (chave {l.get('chave')})")
        elif mesma:
            rel.append(l)
    for i in ilegiveis:
        print("PENDÊNCIA:", i)
    caminhos = dict(ctx.trilha.con.execute("SELECT sha256, caminho_bruto FROM anexos").fetchall())
    docs = []
    for d in ctx.trilha.documentos(args.competencia):
        res = d.get("resumo") or {}
        if cnpj in (d["cnpjs"] or []) or cnpj in (res.get("emitente"), res.get("prestador")):
            if d["sha256"] in caminhos and Path(caminhos[d["sha256"]]).exists():
                r = classificar(Path(caminhos[d["sha256"]]).read_bytes(), ctx.catalogo)
                if r["doc"] and cnpj in (r["doc"].get("participantes") or []):
                    docs.append(r["doc"])
    achados = auditar(docs, rel, cnpj, args.competencia)
    for a in achados:
        print(f"[{a.regra}] {a.mensagem}")
    print(f"{len(achados)} divergência(s) ({len(docs)} documento(s) capturado(s), {len(rel)} linha(s) do Domínio).")


def _mesma_competencia(valor: str, comp: str) -> bool | None:
    """Aceita 'AAAA-MM', 'MM/AAAA' ou 'DD/MM/AAAA' do relatório. None = formato não reconhecido."""
    import re
    v = valor.strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})(?:-\d{2})?", v) or None
    if m:
        return f"{m.group(1)}-{m.group(2)}" == comp
    m = re.fullmatch(r"(?:\d{2}/)?(\d{2})/(\d{4})", v)
    if not m:
        return None
    return f"{m.group(2)}-{m.group(1)}" == comp


def cmd_dp(args):
    from .dp.folha import conferir, ler_folha
    ctx = _ctx(args, fonte=object())
    r = conferir(ler_folha(Path(args.folha)), args.cnpj, ctx.catalogo)
    for i in r["inativas"]:
        print("INATIVA:", i)
    for a in r["achados"]:
        print(f"[{a.natureza}] {a.mensagem}")


def cmd_calendario(args):
    from .obrigacoes.calendario import alertas, gerar
    ctx = _ctx(args, fonte=object())
    venc = gerar_calendario(ctx, args.competencia)
    linhas = ["vencimento;vencimento_legal;codigo;descricao;apelido;cnpj;norma"]
    for v in venc:
        linhas.append(f"{v.vencimento:%d/%m/%Y};{v.vencimento_legal:%d/%m/%Y};{v.codigo};{v.descricao};"
                      f"{v.apelido};{v.cnpj};{v.norma}")
    saida = ctx.dados / "relatorios" / f"calendario_{args.competencia}.csv"
    escrever_atomico(saida, "\n".join(linhas).encode("utf-8-sig"))
    print(f"{len(venc)} vencimento(s) -> {saida}")
    for a in alertas(venc, date.today(), tuple((ctx.config.get("calendario") or {}).get("dias_alerta", [3, 0]))):
        v = a["vencimento"]
        print(f"ALERTA {a['quando']}: {v.codigo} {v.apelido} vence {v.vencimento:%d/%m/%Y}")


def gerar_calendario(ctx, competencia):
    from .obrigacoes.calendario import gerar
    from .clientes.perfil import data_da_competencia
    cal = ctx.config.get("calendario") or {}
    feriados = {date.fromisoformat(str(f)) for f in cal.get("feriados") or []}
    perfis = {e.cnpj: ctx.perfis.em(e.cnpj, data_da_competencia(competencia)) for e in ctx.carteira if e.ativa}
    return gerar(competencia, perfis, ctx.catalogo, feriados)


def cmd_amostra(args):
    from .qualidade.amostra import gerar, medir
    ctx = _ctx(args, fonte=object())
    if args.acao == "gerar":
        destino = ctx.dados / "relatorios" / f"amostra_{date.today():%Y%m%d}.csv"
        r = gerar(ctx.trilha, destino, args.n)
        print(f"amostra de {r['amostra']} de {r['universo']} documentos -> {destino}")
        print("Preencha a coluna 'conferencia' com CERTO ou ERRADO e rode: amostra medir --arquivo <csv>")
    else:
        if not args.arquivo:
            sys.exit("informe --arquivo")
        r = medir(Path(args.arquivo))
        for k, v in r["por_classe"].items():
            print(f"{k:<20} certo {v['certo']:>3}  errado {v['errado']:>3}  taxa {v['taxa']}")
        print(f"GERAL: {r['taxa_geral']} ({r['conferidos']} conferidos, {r['sem_conferencia']} sem conferência)")


def cmd_cadastro(args):
    from .clientes.importar_planilha import conferir_pastas, converter, escrever, ler_planilha
    if args.acao == "importar":
        empresas, pend = converter(ler_planilha(Path(args.planilha)))
        saida = Path(args.saida)
        if saida.exists() and not args.sobrescrever:
            sys.exit(f"{saida} já existe: use --sobrescrever ou outra --saida")
        escrever(empresas, saida)
        print(f"{len(empresas)} empresa(s) -> {saida}")
        print("ATENÇÃO: confira o código do Domínio (coluna CÓD.) e o apelido das pastas "
              "(python -m mo_autonomo cadastro conferir-pastas).")
        for p in pend:
            print("PENDENTE:", p)
    else:
        ctx = _ctx(args, fonte=object())
        base = Path(args.base) if args.base else ctx.base_xml
        faltam = conferir_pastas(ctx.carteira, base, ctx.config["dominio"]["tipos_pasta"])
        for f in faltam:
            print("SEM PASTA:", f)
        print(f"{len(ctx.carteira) - len(faltam)}/{len(ctx.carteira)} empresa(s) com pasta encontrada em {base}")


def cmd_contabil(args):
    from .contabil.plano_dominio import escrever_plano, importar_pasta, ler
    ctx = _ctx(args, fonte=object())
    if args.acao == "importar-planos":
        r = importar_pasta(Path(args.pasta), ctx.carteira, ctx.dados / "dominio", args.sobrescrever)
        for linha in r["importados"]:
            print("OK:", linha)
        for linha in r["erros"]:
            print("ERRO:", linha)
        print(f"{len(r['importados'])} plano(s) importado(s); {len(r['sem_plano'])} empresa(s) ainda sem plano:")
        for e in r["sem_plano"]:
            print("  SEM PLANO:", e)
        return
    if not args.arquivo or not args.empresa:
        sys.exit("informe --arquivo e --empresa")
    emp = next((e for e in ctx.carteira if e.codigo_dominio == str(args.empresa)), None)
    if emp is None:
        sys.exit(f"empresa de código {args.empresa} não está no cadastro")
    contas = ler(Path(args.arquivo))
    destino = ctx.dados / "dominio" / emp.codigo_dominio / "plano_contas.csv"
    try:
        escrever_plano(contas, destino, args.sobrescrever)
    except FileExistsError as exc:
        sys.exit(str(exc))
    analiticas = sum(1 for c in contas if c["analitica"])
    print(f"{len(contas)} conta(s) ({analiticas} analíticas) -> {destino}")


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
    s.add_argument("acao", choices=["validar", "cobertura", "monitorar", "conferir"])
    raiz = Path(__file__).resolve().parent.parent  # Agendador roda com diretório atual em System32
    s.add_argument("--pasta", default=str(raiz / "config" / "normas"))
    s.add_argument("--dados", default=str(raiz / "dados"))
    s.add_argument("--config", help="usa pastas.normas/pastas.dados deste config")
    s.add_argument("--id")
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
    com_config("calendario", cmd_calendario).add_argument("--competencia", required=True, help="AAAA-MM")
    s = com_config("amostra", cmd_amostra)
    s.add_argument("acao", choices=["gerar", "medir"])
    s.add_argument("--n", type=int, default=20, help="documentos por classe")
    s.add_argument("--arquivo")
    s = com_config("cadastro", cmd_cadastro, help="gera empresas.csv da planilha do escritório / confere pastas")
    s.add_argument("acao", choices=["importar", "conferir-pastas"])
    s.add_argument("--planilha", help="xlsx 'CONTROLE EMPRESAS POR REGIME' baixado do Drive")
    s.add_argument("--saida", default="config/empresas.csv")
    s.add_argument("--sobrescrever", action="store_true")
    s.add_argument("--base", help="pasta XML NOTAS a conferir (padrão: a do config)")
    s = com_config("contabil", cmd_contabil, help="importa o plano de contas exportado do Domínio")
    s.add_argument("acao", choices=["importar-plano", "importar-planos"])
    s.add_argument("--arquivo", help="PLANO DE CONTAS.csv (Impressão de campos da consulta)")
    s.add_argument("--empresa", help="código da empresa no Domínio")
    s.add_argument("--pasta", help="pasta com um CSV por empresa, nome começando pelo código (ex.: '12 - LMG.csv')")
    s.add_argument("--sobrescrever", action="store_true", help="troca o plano já importado (o anterior vira .bak)")
    s = sub.add_parser("grafo")
    s.add_argument("acao", choices=["desenhar"])
    s.set_defaults(f=cmd_grafo)
    args = p.parse_args(argv)
    args.f(args)


if __name__ == "__main__":
    main()
