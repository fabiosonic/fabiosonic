"""Automação do Home Broker da Clear via navegador (Playwright).

Fluxo: abre o site da Clear -> entra no Home Broker -> aguarda VOCÊ fazer o
login (senha, 2FA e captcha nunca passam pelo robô) -> lê custódia -> envia e
cancela ordens preenchendo a boleta, com captura de tela de cada passo.

A sessão fica salva em `pasta_sessao` (perfil do navegador), então o login
costuma ser pedido só quando a Clear expira a sessão.

Todos os seletores vêm de config/seletores_clear.yaml (veja `calibrar`).
"""
from __future__ import annotations

import datetime as dt
import getpass
import os
import re
import time
from pathlib import Path

import yaml

from ..fiscal import ticker_base

PENDENTE = "PREENCHER"

OBRIGATORIOS = [
    "navegacao.indicador_logado", "navegacao.menu_custodia", "navegacao.menu_ordens",
    "custodia.linha", "custodia.ativo", "custodia.quantidade", "custodia.preco_medio",
    "boleta.abrir_compra", "boleta.abrir_venda", "boleta.aba_stop", "boleta.campo_ativo",
    "boleta.campo_quantidade", "boleta.campo_preco", "boleta.campo_disparo",
    "boleta.botao_enviar", "boleta.confirmacao",
    "ordens.linha", "ordens.ativo", "ordens.tipo", "ordens.lado", "ordens.status", "ordens.botao_cancelar",
]


class ErroHomeBroker(RuntimeError):
    pass


def carregar_seletores(caminho: str | Path) -> dict:
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f)


def pendencias(sel: dict) -> list[str]:
    """Lista os seletores obrigatórios ainda não calibrados."""
    faltando = []
    for chave in OBRIGATORIOS:
        grupo, nome = chave.split(".")
        valor = (sel.get(grupo) or {}).get(nome)
        if not valor or valor == PENDENTE:
            faltando.append(chave)
    nav = sel.get("navegacao") or {}
    if not (sel.get("urls") or {}).get("homebroker") and nav.get("link_homebroker") in (None, "", PENDENTE):
        faltando.append("urls.homebroker ou navegacao.link_homebroker")
    return faltando


def numero_br(texto: str) -> float:
    """'R$ 1.234,56' -> 1234.56 ; '300' -> 300.0"""
    limpo = re.sub(r"[^\d,.\-]", "", texto or "")
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    if not limpo or limpo in "-.":
        raise ValueError(f"Número inválido: {texto!r}")
    return float(limpo)


def formatar_br(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


class ClearHomeBroker:
    def __init__(self, seletores: dict, pasta_sessao: str, pasta_logs: str,
                 timeout_login_seg: int = 300, headless: bool = False):
        self.sel = seletores
        self.pasta_sessao = pasta_sessao
        self.pasta_logs = Path(pasta_logs) / dt.date.today().isoformat()
        self.timeout_login = timeout_login_seg
        self.headless = headless
        self._pw = self._ctx = self.page = None
        self._assinatura: str | None = None

    # ----------------------------------------------------------------- utilidades
    def s(self, chave: str) -> str:
        grupo, nome = chave.split(".")
        valor = (self.sel.get(grupo) or {}).get(nome, "")
        return "" if valor == PENDENTE else (valor or "")

    def foto(self, nome: str) -> None:
        if self.page is None:
            return
        self.pasta_logs.mkdir(parents=True, exist_ok=True)
        arquivo = self.pasta_logs / f"{dt.datetime.now():%H%M%S}_{nome}.png"
        try:
            self.page.screenshot(path=str(arquivo), full_page=False)
        except Exception:
            pass

    def _clicar(self, chave: str, timeout: int = 15000) -> None:
        seletor = self.s(chave)
        if not seletor:
            raise ErroHomeBroker(f"Seletor {chave} não configurado")
        self.page.locator(seletor).first.click(timeout=timeout)

    def _preencher(self, chave: str, valor: str) -> None:
        campo = self.page.locator(self.s(chave)).first
        campo.click(timeout=10000)
        campo.fill("")
        campo.fill(valor)
        # alguns campos com máscara só aceitam digitação real
        if campo.input_value().replace(".", "").replace(",", "") != valor.replace(".", "").replace(",", ""):
            campo.fill("")
            campo.type(valor, delay=40)

    # ----------------------------------------------------------------- sessão
    def abrir(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as e:  # pragma: no cover
            raise SystemExit("Instale o Playwright: pip install playwright && playwright install chromium") from e
        self._pw = sync_playwright().start()
        self._ctx = self._pw.chromium.launch_persistent_context(
            self.pasta_sessao, headless=self.headless, viewport={"width": 1600, "height": 950},
            locale="pt-BR", timezone_id="America/Sao_Paulo",
        )
        self.page = self._ctx.pages[0] if self._ctx.pages else self._ctx.new_page()
        self.page.set_default_timeout(20000)

    def fechar(self) -> None:
        try:
            if self._ctx:
                self._ctx.close()
        finally:
            if self._pw:
                self._pw.stop()

    def _pagina_logada(self):
        indicador = self.s("navegacao.indicador_logado")
        for pg in self._ctx.pages:
            try:
                if indicador and pg.locator(indicador).first.is_visible(timeout=500):
                    return pg
            except Exception:
                continue
        return None

    def entrar(self) -> None:
        """Abre o site da Clear, vai ao Home Broker e espera o login manual."""
        urls = self.sel.get("urls") or {}
        self.page.goto(urls.get("site") or "https://www.clear.com.br", wait_until="domcontentloaded")
        self.foto("site_clear")
        if urls.get("homebroker"):
            self.page.goto(urls["homebroker"], wait_until="domcontentloaded")
        elif self.s("navegacao.link_homebroker"):
            try:
                with self._ctx.expect_page(timeout=8000) as nova:
                    self._clicar("navegacao.link_homebroker")
                self.page = nova.value          # Home Broker abriu em nova aba
            except Exception:
                pass                            # abriu na mesma aba
        pg = self._pagina_logada()
        if pg is None:
            if self.s("navegacao.link_login"):
                try:
                    self._clicar("navegacao.link_login", timeout=5000)
                except Exception:
                    pass
            print(f"\n>>> Faça o login na Clear na janela do navegador (aguardando até {self.timeout_login}s)...")
            limite = time.time() + self.timeout_login
            while pg is None and time.time() < limite:
                time.sleep(2)
                pg = self._pagina_logada()
            if pg is None:
                self.foto("login_timeout")
                raise ErroHomeBroker("Login não detectado no tempo limite (confira navegacao.indicador_logado)")
        self.page = pg
        self.page.bring_to_front()
        self.foto("homebroker_logado")
        print(">>> Home Broker logado.")

    def pedir_assinatura(self) -> None:
        if self.s("boleta.campo_assinatura") and self._assinatura is None:
            self._assinatura = os.environ.get("CLEAR_ASSINATURA") or getpass.getpass(
                "Assinatura eletrônica da Clear (fica só na memória): ")

    # ----------------------------------------------------------------- leitura
    def ler_posicoes(self) -> dict[str, tuple[int, float]]:
        """{TICKER_BASE: (quantidade, preço médio)} somando padrão + fracionário."""
        self._clicar("navegacao.menu_custodia")
        self.page.wait_for_timeout(2500)
        self.foto("custodia")
        posicoes: dict[str, tuple[int, float]] = {}
        for linha in self.page.locator(self.s("custodia.linha")).all():
            try:
                ativo = linha.locator(self.s("custodia.ativo")).first.inner_text().strip().upper()
                qtd = int(numero_br(linha.locator(self.s("custodia.quantidade")).first.inner_text()))
                pm = numero_br(linha.locator(self.s("custodia.preco_medio")).first.inner_text())
            except Exception:
                continue
            if not ativo or qtd <= 0:
                continue
            base = ticker_base(ativo)
            q0, pm0 = posicoes.get(base, (0, 0.0))
            total = q0 + qtd
            posicoes[base] = (total, (q0 * pm0 + qtd * pm) / total)
        return posicoes

    # ----------------------------------------------------------------- ordens
    def _boleta(self, lado: str, tipo: str, ticker: str, qtd: int, preco: float,
                disparo: float | None = None, enviar: bool = True) -> None:
        rotulo = f"{lado}_{tipo}_{ticker}_{qtd}"
        self._clicar("boleta.abrir_compra" if lado == "compra" else "boleta.abrir_venda")
        self.page.wait_for_timeout(800)
        aba = "boleta.aba_stop" if tipo == "stop" else "boleta.aba_limitada"
        if self.s(aba):
            self._clicar(aba)
            self.page.wait_for_timeout(500)
        self._preencher("boleta.campo_ativo", ticker)
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1200)  # aguarda cotação do ativo carregar
        self._preencher("boleta.campo_quantidade", str(qtd))
        if tipo == "stop":
            self._preencher("boleta.campo_disparo", formatar_br(disparo))
        self._preencher("boleta.campo_preco", formatar_br(preco))
        if self.s("boleta.campo_assinatura") and self._assinatura:
            self._preencher("boleta.campo_assinatura", self._assinatura)
        self.foto(f"boleta_{rotulo}")
        if not enviar:
            print(f"[ENSAIO] Boleta preenchida e NÃO enviada: {rotulo}")
            if self.s("boleta.fechar"):
                self._clicar("boleta.fechar")
            return
        self._clicar("boleta.botao_enviar")
        self._aguardar_confirmacao(rotulo)

    def _aguardar_confirmacao(self, rotulo: str) -> None:
        ok, erro = self.s("boleta.confirmacao"), self.s("boleta.erro")
        limite = time.time() + 15
        while time.time() < limite:
            if erro and self.page.locator(erro).first.is_visible():
                msg = self.page.locator(erro).first.inner_text()
                self.foto(f"ERRO_{rotulo}")
                raise ErroHomeBroker(f"Ordem rejeitada ({rotulo}): {msg}")
            if self.page.locator(ok).first.is_visible():
                self.foto(f"ok_{rotulo}")
                if self.s("boleta.fechar"):
                    try:
                        self._clicar("boleta.fechar", timeout=3000)
                    except Exception:
                        pass
                return
            self.page.wait_for_timeout(300)
        self.foto(f"SEM_CONFIRMACAO_{rotulo}")
        raise ErroHomeBroker(f"Sem confirmação da ordem {rotulo} — confira no Home Broker antes de continuar")

    def comprar_limitada(self, ticker: str, qtd: int, preco: float, enviar: bool = True) -> None:
        self._boleta("compra", "limitada", ticker, qtd, preco, enviar=enviar)

    def vender_limitada(self, ticker: str, qtd: int, preco: float, enviar: bool = True) -> None:
        self._boleta("venda", "limitada", ticker, qtd, preco, enviar=enviar)

    def stop_venda(self, ticker: str, qtd: int, disparo: float, limite: float, enviar: bool = True) -> None:
        self._boleta("venda", "stop", ticker, qtd, limite, disparo=disparo, enviar=enviar)

    # ----------------------------------------------------------------- OCO e preços
    def suporta_oco(self) -> bool:
        return all(self.s(f"boleta.{k}") for k in ("aba_oco", "campo_gain_disparo", "campo_gain_preco",
                                                   "campo_loss_disparo", "campo_loss_preco"))

    def oco_venda(self, ticker: str, qtd: int, gain_disparo: float, gain_preco: float,
                  loss_disparo: float, loss_preco: float, enviar: bool = True) -> None:
        """Stop duplo (OCO): take profit e stop loss na mesma ordem; a execução de um cancela o outro."""
        if not self.suporta_oco():
            raise ErroHomeBroker("OCO não calibrado (boleta.aba_oco e campos de gain/loss)")
        rotulo = f"venda_oco_{ticker}_{qtd}"
        self._clicar("boleta.abrir_venda")
        self.page.wait_for_timeout(800)
        self._clicar("boleta.aba_oco")
        self.page.wait_for_timeout(500)
        self._preencher("boleta.campo_ativo", ticker)
        self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1200)
        self._preencher("boleta.campo_quantidade", str(qtd))
        self._preencher("boleta.campo_gain_disparo", formatar_br(gain_disparo))
        self._preencher("boleta.campo_gain_preco", formatar_br(gain_preco))
        self._preencher("boleta.campo_loss_disparo", formatar_br(loss_disparo))
        self._preencher("boleta.campo_loss_preco", formatar_br(loss_preco))
        if self.s("boleta.campo_assinatura") and self._assinatura:
            self._preencher("boleta.campo_assinatura", self._assinatura)
        self.foto(f"boleta_{rotulo}")
        if not enviar:
            print(f"[ENSAIO] OCO preenchida e NÃO enviada: {rotulo}")
            return
        self._clicar("boleta.botao_enviar")
        self._aguardar_confirmacao(rotulo)

    def ler_precos(self) -> dict[str, float]:
        """Último preço de cada ativo na tabela de custódia (coluna custodia.preco_atual)."""
        if not self.s("custodia.preco_atual"):
            return {}
        self._clicar("navegacao.menu_custodia")
        self.page.wait_for_timeout(1500)
        precos = {}
        for linha in self.page.locator(self.s("custodia.linha")).all():
            try:
                ativo = ticker_base(linha.locator(self.s("custodia.ativo")).first.inner_text().strip().upper())
                precos[ativo] = numero_br(linha.locator(self.s("custodia.preco_atual")).first.inner_text())
            except Exception:
                continue
        return precos

    def cancelar_stops(self, ticker: str) -> int:
        """Cancela os stops de venda abertos do ativo (padrão e fracionário)."""
        o = self.sel["ordens"]
        self._clicar("navegacao.menu_ordens")
        self.page.wait_for_timeout(2000)
        canceladas = 0
        for _ in range(10):  # a tabela é redesenhada a cada cancelamento
            alvo = None
            for linha in self.page.locator(self.s("ordens.linha")).all():
                try:
                    ativo = ticker_base(linha.locator(self.s("ordens.ativo")).first.inner_text().strip().upper())
                    tipo = linha.locator(self.s("ordens.tipo")).first.inner_text()
                    lado = linha.locator(self.s("ordens.lado")).first.inner_text().strip()
                    status = linha.locator(self.s("ordens.status")).first.inner_text()
                except Exception:
                    continue
                if (ativo == ticker
                        and any(t.lower() in tipo.lower() for t in o.get("textos_stop", ["Stop"]))
                        and any(lado.lower().startswith(t.lower()) for t in o.get("textos_venda", ["Venda"]))
                        and any(t.lower() in status.lower() for t in o.get("textos_aberta", ["Aberta"]))):
                    alvo = linha
                    break
            if alvo is None:
                break
            alvo.locator(self.s("ordens.botao_cancelar")).first.click()
            if self.s("ordens.confirmar_cancelamento"):
                if self.s("boleta.campo_assinatura") and self._assinatura:
                    try:
                        self._preencher("boleta.campo_assinatura", self._assinatura)
                    except Exception:
                        pass
                self._clicar("ordens.confirmar_cancelamento")
            self.page.wait_for_timeout(2000)
            canceladas += 1
            self.foto(f"cancelado_stop_{ticker}_{canceladas}")
        return canceladas
