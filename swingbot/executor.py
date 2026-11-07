"""Ciclo diário do robô nos modos simulado e real."""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from . import dados, motor, risco
from .carteira import Carteira
from .config import Config
from .estrategia import criar
from .modelos import brl, AJUSTAR_STOP, COMPRAR, VENDER, Ordem
from .simulador import executar_dia

FUSO = ZoneInfo("America/Sao_Paulo")


class Relatorio:
    def __init__(self, pasta_logs: str):
        self.arquivo = Path(pasta_logs) / dt.date.today().isoformat() / "relatorio.txt"
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)

    def __call__(self, msg: str) -> None:
        linha = f"[{dt.datetime.now(FUSO):%H:%M:%S}] {msg}"
        print(linha)
        with open(self.arquivo, "a", encoding="utf-8") as f:
            f.write(linha + "\n")


def _imprimir_ordens(log, ordens: list[Ordem], avisos: list[str]) -> None:
    for a in avisos:
        log(f"AVISO: {a}")
    if not ordens:
        log("Nenhuma ordem para o próximo pregão.")
    for o in ordens:
        extra = f" stop {o.preco_stop}" if o.preco_stop else ""
        extra += f" alvo {o.alvo}" if o.alvo else ""
        log(f"ORDEM {o.acao} {o.ticker} {o.quantidade} @ {o.preco_limite}{extra} ({o.motivo})")


# =============================================================================== SIMULADO
def rodar_simulado(cfg: Config) -> Carteira:
    log = Relatorio(cfg.pasta_logs)
    caminho = Path(cfg.pasta_estado) / "carteira_simulada.json"
    cart = Carteira.carregar_ou_criar(caminho, cfg.risco.capital_teste, cfg.risco.custo_percentual)
    agora = dt.datetime.now(FUSO)
    corte = agora.date() + dt.timedelta(days=1) if agora.hour >= 19 else agora.date()
    hist = dados.historicos(cfg.ativos, cfg.inicio_dados, ate=corte.isoformat())
    datas = sorted(set().union(*[set(df.index) for df in hist.values()]))
    if cart.ultima_data is None:
        datas = datas[-1:]  # primeira execução: começa a operar a partir de agora
    else:
        datas = [d for d in datas if d > pd.Timestamp(cart.ultima_data)]
    if not datas:
        log("Sem pregões novos desde a última execução.")
        return cart
    estrategia = criar(cfg.estrategia)
    for i, d in enumerate(datas):
        data = d.date().isoformat()
        barras = {t: df.loc[d] for t, df in hist.items() if d in df.index}
        for ev in executar_dia(cart, barras, data):
            log(ev)
        proxima = datas[i + 1].date().isoformat() if i + 1 < len(datas) else None
        ordens, avisos = motor.planejar(cfg, estrategia, cart, hist, data, proxima)
        cart.pendentes = ordens
    precos = {t: float(df["close"].iloc[-1]) for t, df in hist.items()}
    log(f"[SIMULADO] pregão {cart.ultima_data} | patrimônio R$ {brl(cart.patrimonio(precos))} "
        f"| caixa R$ {brl(cart.caixa)} | posições {list(cart.posicoes)}")
    _imprimir_ordens(log, cart.pendentes, avisos)
    cart.salvar(caminho)
    return cart


# =============================================================================== REAL
def _horario_permitido(cfg: Config) -> bool:
    agora = dt.datetime.now(FUSO)
    if agora.weekday() >= 5:
        return False
    ini = dt.time.fromisoformat(cfg.clear.horario_inicio)
    fim = dt.time.fromisoformat(cfg.clear.horario_fim)
    return ini <= agora.time() <= fim


def reconciliar(cart: Carteira, hb: dict[str, tuple[int, float]], hoje: str, ativos: list[str], log) -> set[str]:
    """Ajusta a carteira do robô ao que a Clear mostra. Retorna ativos bloqueados."""
    bloqueados: set[str] = set()
    restantes = []
    for o in cart.pendentes:
        q_hb = hb.get(o.ticker, (0, 0.0))[0]
        q_robo = cart.posicoes[o.ticker].quantidade if o.ticker in cart.posicoes else 0
        if o.acao == COMPRAR:
            if q_hb > q_robo:
                exec_qtd = min(q_hb - q_robo, o.quantidade)
                preco = round(hb[o.ticker][1], 2) if q_robo == 0 else o.preco_limite
                cart.comprar(o.data_envio or hoje, o.ticker, exec_qtd, preco, o.preco_stop, o.alvo, estimado=True)
                cart.posicoes[o.ticker].stop_enviado = False
                log(f"EXECUTADA compra {o.ticker} {exec_qtd} @ ~{preco}")
            elif o.data_envio == hoje:
                restantes.append(o)
        elif o.acao == VENDER:
            if q_hb < q_robo:
                qtd = q_robo - q_hb
                cart.vender(hoje, o.ticker, qtd, o.preco_limite, o.motivo, estimado=True)
                log(f"EXECUTADA venda {o.ticker} {qtd} @ ~{o.preco_limite} ({o.motivo})")
            elif o.data_envio == hoje:
                restantes.append(o)
                log(f"ATENÇÃO: venda de {o.ticker} ainda não executada e o stop foi cancelado — acompanhe!")
            elif o.ticker in cart.posicoes:
                cart.posicoes[o.ticker].stop_enviado = False  # venda expirou: recolocar stop
    cart.pendentes = restantes

    for ticker, pos in list(cart.posicoes.items()):
        q_hb = hb.get(ticker, (0, 0.0))[0]
        if q_hb < pos.quantidade:
            qtd = pos.quantidade - q_hb
            cart.vender(hoje, ticker, qtd, pos.stop, "stop", estimado=True)
            log(f"STOP executado em {ticker}: {qtd} @ ~{pos.stop} (data/preço estimados — confira a nota de corretagem)")
        elif q_hb > pos.quantidade:
            bloqueados.add(ticker)
            log(f"BLOQUEADO {ticker}: a conta tem {q_hb}, o robô controla {pos.quantidade}. Há posição manual?")
    for ticker in ativos:
        if ticker not in cart.posicoes and hb.get(ticker, (0, 0))[0] > 0 and \
                not any(o.ticker == ticker for o in cart.pendentes):
            bloqueados.add(ticker)
            log(f"BLOQUEADO {ticker}: posição na conta que não foi aberta pelo robô — não será operada.")
    return bloqueados


def proteger(cart: Carteira, corretora, cfg: Config, log) -> None:
    """Garante stop registrado na Clear para toda posição do robô."""
    vendendo = {o.ticker for o in cart.pendentes if o.acao == VENDER}
    for ticker, pos in cart.posicoes.items():
        if pos.stop_enviado or ticker in vendendo:
            continue
        corretora.cancelar_stops(ticker)
        limite = round(pos.stop * (1 - cfg.risco.folga_stop), 2)
        for tk, q in risco.dividir_lotes(ticker, pos.quantidade):
            corretora.stop_venda(tk, q, pos.stop, limite)
        pos.stop_enviado = True
        log(f"STOP registrado {ticker} {pos.quantidade} disparo {pos.stop} limite {limite}")


def executar_ordens(cart: Carteira, ordens: list[Ordem], corretora, hoje: str, log) -> None:
    from .corretoras.clear_homebroker import ErroHomeBroker
    for o in ordens:
        try:
            if o.acao == VENDER:
                corretora.cancelar_stops(o.ticker)
                cart.posicoes[o.ticker].stop_enviado = False
                for tk, q in risco.dividir_lotes(o.ticker, o.quantidade):
                    corretora.vender_limitada(tk, q, o.preco_limite)
                o.data_envio = hoje
                cart.pendentes.append(o)
            elif o.acao == AJUSTAR_STOP:
                pos = cart.posicoes[o.ticker]
                pos.stop_enviado = False
                pos.stop = o.preco_stop
                corretora.cancelar_stops(o.ticker)
                for tk, q in risco.dividir_lotes(o.ticker, pos.quantidade):
                    corretora.stop_venda(tk, q, o.preco_stop, o.preco_limite)
                pos.stop_enviado = True
            elif o.acao == COMPRAR:
                for tk, q in risco.dividir_lotes(o.ticker, o.quantidade):
                    corretora.comprar_limitada(tk, q, o.preco_limite)
                o.data_envio = hoje
                cart.pendentes.append(o)
            log(f"ENVIADA {o.acao} {o.ticker} {o.quantidade} @ {o.preco_limite} ({o.motivo})")
        except ErroHomeBroker as e:
            log(f"FALHA {o.acao} {o.ticker}: {e}")


def rodar_real(cfg: Config, confirmar: bool = True) -> None:
    from .corretoras.clear_homebroker import ClearHomeBroker, carregar_seletores, pendencias

    log = Relatorio(cfg.pasta_logs)
    if risco.parada_manual_ativa():
        log("Arquivo PARAR encontrado: robô travado. Apague-o para voltar a operar.")
        return
    if not _horario_permitido(cfg):
        log(f"Fora do horário permitido ({cfg.clear.horario_inicio}–{cfg.clear.horario_fim}, dias úteis).")
        return
    seletores = carregar_seletores(cfg.clear.arquivo_seletores)
    faltando = pendencias(seletores)
    if faltando:
        log("Seletores não calibrados: " + ", ".join(faltando) + ". Rode: python -m swingbot calibrar")
        return
    if confirmar:
        print(f"\n*** MODO REAL — capital de teste R$ {brl(cfg.risco.capital_teste)}, "
              f"risco {cfg.risco.risco_por_operacao:.1%} por operação ***")
        if input('Digite "OPERAR REAL" para continuar: ').strip() != "OPERAR REAL":
            log("Cancelado pelo usuário.")
            return

    trava = Path(cfg.pasta_estado) / "robo.lock"
    trava.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(trava, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        log(f"Outra execução em andamento (apague {trava} se tiver certeza de que não há).")
        return

    caminho = Path(cfg.pasta_estado) / "carteira_real.json"
    cart = Carteira.carregar_ou_criar(caminho, cfg.risco.capital_teste, cfg.risco.custo_percentual)
    hoje = dt.datetime.now(FUSO).date().isoformat()
    hb = ClearHomeBroker(seletores, cfg.clear.pasta_sessao, cfg.pasta_logs,
                         cfg.clear.timeout_login_seg, cfg.clear.headless)
    try:
        hist = dados.historicos(cfg.ativos, cfg.inicio_dados, ate=hoje)  # só pregões encerrados
        data_ref = max(df.index[-1] for df in hist.values()).date().isoformat()
        hb.abrir()
        hb.entrar()
        hb.pedir_assinatura()

        bloqueados = reconciliar(cart, hb.ler_posicoes(), hoje, cfg.ativos, log)
        proteger(cart, hb, cfg, log)

        if cart.ultima_execucao == hoje:
            log("Ordens de hoje já foram enviadas: execução apenas de conferência e proteção.")
        elif risco.parada_manual_ativa():
            log("PARAR detectado durante a execução: nenhuma ordem nova.")
        else:
            ordens, avisos = motor.planejar(cfg, criar(cfg.estrategia), cart, hist, data_ref, hoje, bloqueados)
            _imprimir_ordens(log, ordens, avisos)
            executar_ordens(cart, ordens, hb, hoje, log)
            cart.ultima_execucao = hoje
            cart.salvar(caminho)
            if ordens:
                hb.page.wait_for_timeout(20000)  # tempo para as ordens executarem
                reconciliar(cart, hb.ler_posicoes(), hoje, cfg.ativos, log)
                proteger(cart, hb, cfg, log)
        cart.ultima_data = data_ref
        precos = {t: float(df["close"].iloc[-1]) for t, df in hist.items()}
        log(f"[REAL] patrimônio do robô R$ {brl(cart.patrimonio(precos))} | caixa R$ {brl(cart.caixa)} "
            f"| posições {[(t, p.quantidade, p.stop) for t, p in cart.posicoes.items()]}")
    finally:
        cart.salvar(caminho)
        hb.fechar()
        trava.unlink(missing_ok=True)
