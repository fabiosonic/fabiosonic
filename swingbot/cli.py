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
        input("Confira a tela e tecle ENTER para fechar...")
    finally:
        hb.fechar()


def main(argv=None):
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

    e = sub.add_parser("ensaio", help="preenche a boleta sem enviar (teste de seletores)")
    e.add_argument("ticker")
    e.add_argument("--preco", type=float, required=True)

    args = p.parse_args(argv)
    cfg = config_mod.carregar(args.config)
    {"backtest": cmd_backtest, "rodar": cmd_rodar, "apuracao": cmd_apuracao,
     "calibrar": cmd_calibrar, "ensaio": cmd_ensaio}[args.comando](cfg, args)


if __name__ == "__main__":
    main()
