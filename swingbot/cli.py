"""Linha de comando: python -m swingbot <comando>"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as config_mod
from .modelos import brl


def cmd_backtest(cfg, args):
    from . import backtest, dados, fiscal
    hist = dados.historicos(cfg.ativos, cfg.inicio_dados)
    res = backtest.rodar(cfg, hist, inicio=args.inicio)
    for k, v in backtest.metricas(res, cfg.risco.capital_teste).items():
        print(f"{k:>22}: {v}")
    meses = fiscal.apurar(res.operacoes, cfg.fiscal.limite_isencao_mensal, cfg.fiscal.tipos_ativo)
    print(f"{'DARFs (6015) no período':>22}: R$ {brl(sum(m.darf_6015 for m in meses))}")
    if args.trades:
        for t in res.trades:
            print(t)


def cmd_rodar(cfg, args):
    from . import executor
    if cfg.modo == "real" and args.real:
        executor.rodar_real(cfg, confirmar=not args.sem_confirmacao)
    else:
        if args.real:
            print("Para operar real: defina modo: real no config.yaml E use --real.")
        executor.rodar_simulado(cfg)


def cmd_apuracao(cfg, args):
    from .carteira import Carteira
    from .fiscal import apurar
    caminho = Path(cfg.pasta_estado) / f"carteira_{args.carteira}.json"
    if not caminho.exists():
        sys.exit(f"Sem estado em {caminho}")
    cart = Carteira.from_dict(json.loads(caminho.read_text(encoding="utf-8")))
    estimadas = sum(1 for o in cart.operacoes if o.estimado)
    for m in apurar(cart.operacoes, cfg.fiscal.limite_isencao_mensal, cfg.fiscal.tipos_ativo):
        print(f"\n== {m.mes} ==  vendas de ações R$ {brl(m.vendas_acoes)} ({'ISENTO' if m.isento else 'tributável'})")
        print(f"   resultado comum ações {m.resultado_comum_acoes:+,.2f} | outros {m.resultado_comum_outros:+,.2f} "
              f"| day trade {m.resultado_day_trade:+,.2f} | FII {m.resultado_fii:+,.2f}")
        print(f"   prejuízo a compensar: comum {brl(m.prejuizo_comum_acumulado)} | DT {brl(m.prejuizo_dt_acumulado)}")
        print(f"   IR {brl(m.imposto_bruto)} - IRRF {brl(m.irrf_utilizado)} => DARF 6015: R$ {brl(m.darf_6015)}"
              + (f" (acumula R$ {brl(m.valor_acumulado_proximo_mes)})" if m.valor_acumulado_proximo_mes else ""))
        for a in m.avisos:
            print(f"   * {a}")
    if estimadas:
        print(f"\n{estimadas} operação(ões) com preço/data ESTIMADOS: confira com as notas de corretagem.")


def cmd_calibrar(cfg, args):
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores, pendencias
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    try:
        hb.page.goto((sel.get("urls") or {}).get("site") or "https://www.clear.com.br")
        print("Faça login, abra o Home Broker e use 'Pick locator' no Playwright Inspector.")
        print("Seletores pendentes:", ", ".join(pendencias(sel)) or "nenhum")
        hb.page.pause()
    finally:
        hb.fechar()


ETAPAS_MAPA = [
    ("tela_principal", "Deixe o Home Broker aberto na tela principal (com Posição e Ordens Swing Trade visíveis)."),
    ("boleta_compra_lista", "Na boleta, clique em 'Compra' e ABRA a lista 'Tipo de ordem' (deixe a lista aberta)."),
    ("boleta_limitada", "Escolha 'Limitada' na lista (os campos de preço e quantidade devem aparecer)."),
    ("boleta_stop", "Abra 'Tipo de ordem' de novo e escolha a ordem STOP (stop loss / stop de venda)."),
    ("boleta_oco", "Se existir 'Stop duplo' / 'OCO' na lista, escolha-o. Se não existir, apenas tecle ENTER."),
    ("boleta_venda", "Clique na aba 'Venda' da boleta (não envie nada)."),
]


def cmd_mapear(cfg, args):
    """Abre a Clear, você faz login e navega; coleta a estrutura da página (sem dados da conta)."""
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores
    from .corretoras.mapeador import coletar, sem_dados_pessoais
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    resultado = {}
    try:
        hb.page.goto((sel.get("urls") or {}).get("homebroker") or "https://trader.clear.com.br/home-broker/new/")
        input("\n>>> Faça o LOGIN na janela do navegador. Quando o Home Broker estiver aberto, tecle ENTER aqui...")
        hb.page = hb._ctx.pages[-1]
        for i, (nome, instrucao) in enumerate(ETAPAS_MAPA, 1):
            input(f"\n[{i}/{len(ETAPAS_MAPA)}] {instrucao}\n    Tecle ENTER quando estiver pronto (NÃO envie ordens)...")
            resultado[nome] = coletar(hb.page)
            n = sum(len(q.get("itens", [])) for q in resultado[nome]["quadros"])
            print(f"    coletados {n} elementos")
    finally:
        hb.fechar()
    if not sem_dados_pessoais(resultado):
        sys.exit("Aviso: restaram números nos textos coletados; arquivo NÃO salvo por segurança.")
    destino = Path(cfg.pasta_logs) / "mapa_clear.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nMapa salvo em {destino} ({destino.stat().st_size // 1024} KB).")
    print("Ele contém só a estrutura da página (botões, campos, tabelas) — números da conta foram trocados por '#'.")
    print("Envie esse arquivo na conversa para eu finalizar os seletores.")


def cmd_ensaio(cfg, args):
    """Testa os seletores: login, custódia e boleta preenchida SEM enviar."""
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    try:
        hb.entrar()
        print("Posições lidas:", hb.ler_posicoes())
        hb.comprar_limitada(args.ticker, 1, args.preco, enviar=False)
        hb.stop_venda(args.ticker, 1, args.preco, round(args.preco * 0.99, 2), enviar=False)
        print(f"Capturas de tela em {hb.pasta_logs}")
        ok = input("A boleta foi preenchida CORRETAMENTE (ativo, quantidade, preço e tipo)? [s/N] ").strip().lower()
        if ok == "s":
            arq = Path(cfg.clear.arquivo_seletores)
            texto = arq.read_text(encoding="utf-8")
            import re as _re
            texto = _re.sub(r"(?m)^validado:\s*\S+", "validado: true", texto, count=1)
            arq.write_text(texto, encoding="utf-8")
            print("Mapeamento VALIDADO: o modo real fica liberado (ainda exige 'OPERAR REAL' a cada uso).")
        else:
            print("Não validado. Ajuste os seletores (ou rode 'mapear' e envie o arquivo) e repita o ensaio.")
    finally:
        hb.fechar()


def cmd_painel(cfg, args):
    """Abre o painel web local (http://127.0.0.1:8050)."""
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from painel.servidor import iniciar
    print(f"Painel em http://127.0.0.1:{args.porta}  (Ctrl+C para encerrar)")
    iniciar(args.porta, abrir=not args.sem_navegador)


def cmd_sincronizar(cfg, args):
    """Abre a Clear, aguarda o login e salva a custódia para o painel."""
    import datetime as _dt
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores, pendencias
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    faltando = [p for p in pendencias(sel) if p.startswith(("navegacao", "custodia", "urls"))]
    if faltando:
        sys.exit("Calibre antes os seletores: " + ", ".join(faltando) + " (python -m swingbot calibrar)")
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    try:
        hb.entrar()
        posicoes = hb.ler_posicoes()
    finally:
        hb.fechar()
    destino = Path(cfg.pasta_estado) / "custodia_clear.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({
        "atualizado_em": _dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
        "posicoes": {t: {"quantidade": q, "preco_medio": round(pm, 4)} for t, (q, pm) in posicoes.items()},
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Custódia salva: {len(posicoes)} ativo(s) em {destino}")


def _registrar_protecao_da_fila(cfg, o):
    """Grava stop/alvo/trailing da ordem; o monitor registra o stop na Clear quando a compra executar."""
    from .protecoes import Protecao, Repositorio
    pr = o["protecao"]
    Repositorio(Path(cfg.pasta_estado) / "protecoes.json").upsert(Protecao(
        ticker=o["ticker"], quantidade=o["quantidade"], preco_entrada=o["preco"], stop=pr["stop"],
        take_profit=pr.get("take_profit"), trailing=pr.get("trailing"), breakeven_pct=pr.get("breakeven_pct"),
        usa_oco=bool(pr.get("usa_oco")), na_reversao=pr.get("na_reversao") or "avisar",
        origem=o.get("origem", "painel")))
    print(f"  {o['ticker']}: proteção registrada (stop {pr['stop']})")


PREFERIDOS_OLLAMA = ["qwen3", "qwen2.5", "llama3.3", "llama3.2", "llama3.1", "gemma3", "gemma2", "mistral", "phi4", "phi3"]


def escolher_modelo(instalados: list[str]) -> str | None:
    """Melhor modelo instalado para o painel (bom em português e em JSON)."""
    for pref in PREFERIDOS_OLLAMA:
        for m in instalados:
            if m.startswith(pref) and "embed" not in m:
                return m
    return next((m for m in instalados if "embed" not in m), None)


def cmd_ia_testar(cfg, args):
    """Verifica o Ollama local, escolhe o modelo e (com --configurar) ativa no config.yaml."""
    import urllib.request
    url = cfg.ia.ollama_url.rstrip("/")
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            modelos = [m["name"] for m in json.loads(r.read().decode()).get("models", [])]
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Ollama não respondeu em {url} ({e}).\n"
                 "  - Abra o aplicativo Ollama (ou rode: ollama serve) e tente de novo.\n"
                 "  - Confirme a instalação com: ollama --version")
    print(f"Ollama encontrado em {url}. Modelos instalados: {', '.join(modelos) or 'nenhum'}")
    modelo = escolher_modelo(modelos)
    if not modelo:
        sys.exit("Nenhum modelo de conversa instalado. Rode: ollama pull qwen2.5:7b  (≈ 4,7 GB)")
    print(f"Modelo escolhido: {modelo}. Testando…")
    corpo = json.dumps({"model": modelo, "stream": False, "messages": [
        {"role": "user", "content": "Responda só com JSON: {\"ok\": true, \"idioma\": \"pt\"}"}],
        "format": "json"}).encode()
    req = urllib.request.Request(url + "/api/chat", data=corpo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read().decode())["message"]["content"]
        print(f"Resposta do modelo: {resp.strip()[:120]}")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"O modelo não respondeu ({e}). Tente outro: ollama pull qwen2.5:7b")
    if args.configurar:
        arq = Path(args.config)
        texto = arq.read_text(encoding="utf-8")
        import re
        texto = re.sub(r"(?m)^(\s*provedor:\s*)\S+", r"\1ollama", texto, count=1)
        texto = re.sub(r"(?m)^(\s*ollama_modelo:\s*)\S+", rf"\g<1>{modelo}", texto, count=1)
        arq.write_text(texto, encoding="utf-8")
        print(f"\nPronto: config.yaml agora usa provedor ollama com {modelo}. Reinicie o painel.")
    else:
        print("\nTudo certo. Para ativar: python -m swingbot ia-testar --configurar")


def cmd_monitorar(cfg, args):
    from .monitor import Monitor
    from .protecoes import Repositorio
    repo = Repositorio(Path(cfg.pasta_estado) / "protecoes.json")
    ativas = [p for p in repo.carregar().values() if p.ativa]
    if not ativas:
        sys.exit("Nenhuma proteção ativa (crie pelo painel ou pela fila de ordens).")
    for p in ativas:
        tr = f" trailing {p.trailing.tipo} {p.trailing.valor}" if p.trailing else ""
        print(f"  {p.ticker:7} {p.quantidade:>6} entrada {p.preco_entrada:.2f} stop {p.stop:.2f} "
              f"alvo {p.take_profit or '-'}{tr}{' breakeven ' + str(p.breakeven_pct) if p.breakeven_pct else ''}")
    if not args.real:
        print("\nSIMULAÇÃO (nada é enviado). Use --real para operar na Clear.")
        Monitor(repo).rodar(args.intervalo, (cfg.clear.horario_inicio, cfg.clear.horario_fim), args.ciclos)
        return
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores, pendencias
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    if pendencias(sel):
        sys.exit("Seletores não calibrados: python -m swingbot calibrar")
    if input('\nDigite "OPERAR REAL" para o monitor gerenciar stops e alvos na Clear: ').strip() != "OPERAR REAL":
        sys.exit("Cancelado.")
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    try:
        hb.entrar()
        hb.pedir_assinatura()
        Monitor(repo, hb, folga_stop=cfg.risco.folga_stop).rodar(
            args.intervalo, (cfg.clear.horario_inicio, cfg.clear.horario_fim), args.ciclos)
    finally:
        hb.fechar()


def cmd_executar_fila(cfg, args):
    """Executa no Home Broker as ordens que o painel colocou na fila."""
    from . import risco as _risco
    from .corretoras.clear_homebroker import ClearHomeBroker, ErroHomeBroker, carregar_seletores, pendencias
    arq = Path(cfg.pasta_estado) / "fila_ordens.json"
    fila = json.loads(arq.read_text(encoding="utf-8")) if arq.exists() else []
    pendentes = [o for o in fila if o["status"] == "aguardando robô"]
    if not pendentes:
        sys.exit("Fila vazia.")
    print(f"\n{len(pendentes)} ordem(ns) na fila:")
    for o in pendentes:
        extra = f" disparo {o['disparo']}" if o.get("disparo") else ""
        print(f"  {'COMPRA' if o['lado'] == 'C' else 'VENDA '} {o['tipo']:9} {o['ticker']:7} {o['quantidade']:>6} @ {o['preco']:.2f}{extra}  ({o.get('motivo', '')})")
    if not args.real:
        sys.exit("\nSimulação: nada enviado. Para executar de verdade use --real.")
    if _risco.parada_manual_ativa():
        sys.exit("Arquivo PARAR presente: execução bloqueada.")
    sel = carregar_seletores(cfg.clear.arquivo_seletores)
    if pendencias(sel):
        sys.exit("Seletores não calibrados: python -m swingbot calibrar")
    if input('\nDigite "OPERAR REAL" para enviar estas ordens à Clear: ').strip() != "OPERAR REAL":
        sys.exit("Cancelado.")
    hb = ClearHomeBroker(sel, cfg.clear.pasta_sessao, cfg.pasta_logs, cfg.clear.timeout_login_seg, False)
    hb.abrir()
    try:
        hb.entrar()
        hb.pedir_assinatura()
        for o in pendentes:
            try:
                for tk, q in _risco.dividir_lotes(o["ticker"], o["quantidade"]):
                    if o["tipo"] == "stop":
                        hb.stop_venda(tk, q, o["disparo"] or o["preco"], o["preco"])
                    elif o["lado"] == "C":
                        hb.comprar_limitada(tk, q, o["preco"])
                    else:
                        hb.vender_limitada(tk, q, o["preco"])
                o["status"] = "executada (enviada)"
                if o["lado"] == "C" and o.get("protecao"):
                    _registrar_protecao_da_fila(cfg, o)
            except ErroHomeBroker as e:
                o["status"] = f"falha: {e}"[:160]
            print(f"  {o['ticker']}: {o['status']}")
            arq.write_text(json.dumps(fila, indent=2, ensure_ascii=False), encoding="utf-8")
    finally:
        hb.fechar()


def _console_utf8() -> None:
    """Evita UnicodeEncodeError em terminais do Windows (cp1252) ao imprimir acentos e símbolos."""
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main(argv=None):
    _console_utf8()
    p = argparse.ArgumentParser(prog="swingbot", description="Robô de swing trade — Home Broker Clear")
    p.add_argument("--config", default="config/config.yaml")
    sub = p.add_subparsers(dest="comando", required=True)

    b = sub.add_parser("backtest", help="testa a estratégia no histórico")
    b.add_argument("--inicio", help="AAAA-MM-DD")
    b.add_argument("--trades", action="store_true", help="lista os trades")

    r = sub.add_parser("rodar", help="ciclo diário (simulado por padrão)")
    r.add_argument("--real", action="store_true", help="opera de verdade (exige modo: real no config)")
    r.add_argument("--sem-confirmacao", action="store_true", help="para agendamento: pula o prompt OPERAR REAL")

    a = sub.add_parser("apuracao", help="apuração mensal do IR")
    a.add_argument("--carteira", choices=["simulada", "real"], default="simulada")

    sub.add_parser("calibrar", help="abre a Clear com o Playwright Inspector para mapear seletores")
    sub.add_parser("mapear", help="coleta a estrutura do Home Broker (sem dados da conta) para configurar o robô")

    pn = sub.add_parser("painel", help="abre o painel web com IA")
    pn.add_argument("--porta", type=int, default=8050)
    pn.add_argument("--sem-navegador", action="store_true")

    sub.add_parser("sincronizar", help="lê a custódia da Clear para o painel")

    it = sub.add_parser("ia-testar", help="verifica o Ollama local e ativa a IA gratuita")
    it.add_argument("--configurar", action="store_true", help="grava provedor ollama e o modelo no config.yaml")

    mo = sub.add_parser("monitorar", help="stop loss, take profit e trailing durante o pregão")
    mo.add_argument("--real", action="store_true")
    mo.add_argument("--intervalo", type=int, default=60, help="segundos entre leituras")
    mo.add_argument("--ciclos", type=int, default=None, help="encerra após N ciclos (teste)")

    ef = sub.add_parser("executar-fila", help="executa no Home Broker as ordens da fila do painel")
    ef.add_argument("--real", action="store_true")

    e = sub.add_parser("ensaio", help="preenche a boleta sem enviar (teste de seletores)")
    e.add_argument("ticker")
    e.add_argument("--preco", type=float, required=True)

    args = p.parse_args(argv)
    cfg = config_mod.carregar(args.config)
    {"backtest": cmd_backtest, "rodar": cmd_rodar, "apuracao": cmd_apuracao,
     "calibrar": cmd_calibrar, "ensaio": cmd_ensaio, "painel": cmd_painel,
     "sincronizar": cmd_sincronizar, "executar-fila": cmd_executar_fila, "monitorar": cmd_monitorar,
     "ia-testar": cmd_ia_testar, "mapear": cmd_mapear}[args.comando](cfg, args)


if __name__ == "__main__":
    main()
