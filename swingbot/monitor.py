"""Monitor intradiário de proteções (stop loss, take profit, trailing, breakeven).

    python -m swingbot monitorar            # simulação: mostra o que faria, não envia nada
    python -m swingbot monitorar --real     # opera na Clear (login e confirmação manuais)

A cada ciclo: lê posições/preços -> avalia cada proteção -> ajusta ordens na Clear.
O stop loss fica sempre registrado na corretora; o monitor só o melhora (trailing,
breakeven) ou executa o take profit. Se o monitor cair, o último stop continua valendo.
"""
from __future__ import annotations

import datetime as dt
import time
from typing import Optional
from zoneinfo import ZoneInfo

from . import risco
from .protecoes import Protecao, Repositorio, avaliar

FUSO = ZoneInfo("America/Sao_Paulo")
FOLGA_VENDA = 0.003      # take profit vende com limite 0,3% abaixo (execução imediata)


def precos_yahoo(tickers: list[str]) -> dict[str, tuple[float, float]]:
    """(último preço, máxima do dia) com atraso de ~15 min. Fallback quando a Clear não fornece."""
    import yfinance as yf
    saida = {}
    for t in tickers:
        try:
            d = yf.download(f"{t}.SA", period="1d", interval="1m", progress=False, threads=False, auto_adjust=False)
            if d is None or d.empty:
                continue
            if hasattr(d.columns, "levels"):
                d.columns = d.columns.get_level_values(0)
            saida[t] = (float(d["Close"].dropna().iloc[-1]), float(d["High"].max()))
        except Exception:
            continue
    return saida


def historico_diario(ticker: str):
    """Candles diários (não ajustados, com cache) para avaliar a reversão."""
    from .dados import baixar
    inicio = (dt.date.today() - dt.timedelta(days=600)).isoformat()
    return baixar(ticker, inicio)


class Monitor:
    def __init__(self, repo: Repositorio, corretora=None, log=print, folga_stop: float = 0.01,
                 fonte_diaria=historico_diario, intervalo_reversao_seg: int = 900):
        self.repo = repo
        self.hb = corretora            # None = simulação (não envia ordens nem grava estado)
        self.log = log
        self.folga_stop = folga_stop
        self.fonte_diaria = fonte_diaria
        self.intervalo_reversao = intervalo_reversao_seg
        self._ultima_reversao = 0.0

    @property
    def simulado(self) -> bool:
        return self.hb is None

    # -------------------------------------------------------------- ordens na Clear
    def _registrar_protecao(self, p: Protecao) -> None:
        limite = round(p.stop * (1 - self.folga_stop), 2)
        usar_oco = p.usa_oco and p.take_profit and self.hb.suporta_oco()
        self.hb.cancelar_stops(p.ticker)
        for tk, q in risco.dividir_lotes(p.ticker, p.quantidade):
            if usar_oco:
                self.hb.oco_venda(tk, q, p.take_profit, round(p.take_profit * (1 - FOLGA_VENDA), 2), p.stop, limite)
            else:
                self.hb.stop_venda(tk, q, p.stop, limite)
        p.stop_enviado = True
        self.log(f"{p.ticker}: {'OCO' if usar_oco else 'stop'} registrado na Clear — stop {p.stop:.2f}"
                 + (f" / alvo {p.take_profit:.2f}" if usar_oco else ""))

    def checar_reversao(self, p: Protecao, preco: float) -> Optional[str]:
        """Avalia reversão de tendência; registra alerta e, se configurado, sai da posição."""
        from .reversao import SAIR, avaliar as avaliar_rev, com_preco_atual
        try:
            df = com_preco_atual(self.fonte_diaria(p.ticker), preco)
        except Exception as e:  # noqa: BLE001 - falha de dados não pode derrubar o monitor
            self.log(f"{p.ticker}: sem dados para avaliar reversão ({e})")
            return None
        diag = avaliar_rev(df, p.maior_preco)
        anterior = (p.ultimo_alerta or {}).get("nivel")
        p.ultimo_alerta = {**diag.to_dict(), "quando": agora()}
        if diag.nivel == "OK" or diag.nivel == anterior:
            return None
        msg = f"{p.ticker} @ {preco:.2f}: REVERSÃO {diag.nivel} ({diag.pontos} pts) — " + "; ".join(diag.sinais)
        if diag.nivel == SAIR:
            msg += " → " + ("SAINDO DA POSIÇÃO" if p.na_reversao == "vender" else "AVISO: considere sair")
        self.log(("[SIMULAÇÃO] " if self.simulado else "") + msg)
        p.historico.append([agora(), msg])
        if diag.nivel == SAIR and p.na_reversao == "vender" and not self.simulado:
            self._executar_take_profit(p, preco)
        return msg

    def _executar_take_profit(self, p: Protecao, preco: float) -> None:
        self.hb.cancelar_stops(p.ticker)
        limite = round(preco * (1 - FOLGA_VENDA), 2)
        for tk, q in risco.dividir_lotes(p.ticker, p.quantidade):
            self.hb.vender_limitada(tk, q, limite)
        p.ativa = False
        p.stop_enviado = False

    # -------------------------------------------------------------- ciclo
    def sincronizar_quantidades(self, itens: dict[str, Protecao], posicoes: dict[str, tuple[int, float]]) -> None:
        for p in itens.values():
            if not p.ativa:
                continue
            q = posicoes.get(p.ticker, (0, 0.0))[0]
            if q == 0:
                p.ativa = False
                p.historico.append([agora(), "posição encerrada na Clear (stop/alvo executado ou venda manual)"])
                self.log(f"{p.ticker}: posição zerada na Clear — proteção encerrada")
            elif q != p.quantidade:
                self.log(f"{p.ticker}: quantidade mudou {p.quantidade} -> {q}; stop será reenviado")
                p.quantidade, p.stop_enviado = q, False

    def ciclo(self, precos: dict[str, tuple[float, float]], posicoes: dict | None = None) -> list[str]:
        itens = self.repo.carregar()
        eventos = []
        checar_rev = time.time() - self._ultima_reversao >= self.intervalo_reversao
        if checar_rev:
            self._ultima_reversao = time.time()
        if posicoes is not None:
            self.sincronizar_quantidades(itens, posicoes)
        for p in itens.values():
            if not p.ativa:
                continue
            if not self.simulado and not p.stop_enviado:
                self._registrar_protecao(p)
            if p.ticker not in precos:
                continue
            preco, maxima = precos[p.ticker]
            d = avaliar(p, preco, maxima)
            if d.acao == "MANTER":
                if checar_rev:
                    msg = self.checar_reversao(p, preco)
                    if msg:
                        eventos.append(msg)
                continue
            msg = f"{p.ticker} @ {preco:.2f}: {d.acao} — {d.motivo}"
            eventos.append(msg)
            self.log(("[SIMULAÇÃO] " if self.simulado else "") + msg)
            if self.simulado:
                continue
            p.historico.append([agora(), msg])
            if d.acao == "TAKE_PROFIT":
                self._executar_take_profit(p, preco)
            elif d.acao == "NOVO_STOP":
                p.stop = d.novo_stop
                p.stop_enviado = False
                self._registrar_protecao(p)
        if not self.simulado:
            self.repo.salvar(itens)
        return eventos

    def rodar(self, intervalo_seg: int = 60, horario=("10:05", "16:50"), max_ciclos: int | None = None) -> None:
        n = 0
        while max_ciclos is None or n < max_ciclos:
            n += 1
            if risco.parada_manual_ativa():
                self.log("Arquivo PARAR encontrado: monitor encerrado (stops já registrados continuam na Clear).")
                return
            hora = dt.datetime.now(FUSO).time()
            if not (dt.time.fromisoformat(horario[0]) <= hora <= dt.time.fromisoformat(horario[1])):
                self.log("Fora do pregão: monitor encerrado.")
                return
            ativos = [p.ticker for p in self.repo.carregar().values() if p.ativa]
            if not ativos:
                self.log("Nenhuma proteção ativa.")
                return
            posicoes = None
            precos = {}
            if self.hb:
                posicoes = self.hb.ler_posicoes()
                precos = {t: (v, v) for t, v in self.hb.ler_precos().items()}
            faltando = [t for t in ativos if t not in precos]
            if faltando:
                precos.update(precos_yahoo(faltando))
            self.ciclo(precos, posicoes)
            time.sleep(intervalo_seg)


def agora() -> str:
    return dt.datetime.now(FUSO).strftime("%Y-%m-%d %H:%M:%S")
