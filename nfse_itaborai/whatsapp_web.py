"""Envio AUTOMÁTICO da cobrança pelo WhatsApp do escritório, via WhatsApp Web no próprio computador — sem API
oficial, sem intermediário e sem custo por mensagem.

Como funciona:
- Uma única vez, em Configurações › WhatsApp, o escritório clica em "Conectar" e lê o QR Code com o celular
  (WhatsApp › Aparelhos conectados), como faz no WhatsApp Web. A sessão fica guardada na pasta da empresa
  (dados/whatsapp_web), separada por empresa e fora dos backups.
- Depois disso o robô (de hora em hora), a régua e o botão "Cobrar" enviam sozinhos: o sistema abre o WhatsApp Web
  num navegador controlado por ele (Edge ou Chrome já instalados no Windows, fora da tela), abre a conversa do
  cliente com a mensagem pronta e aperta Enviar. Só vai para os clientes marcados em "Cobrar por WhatsApp".
- Mensagem que não sai (computador desligado, sessão desconectada) continua na fila e sai na próxima rodada.
  Número sem WhatsApp vira erro no histórico de cobrança (o e-mail segue normalmente).

Cuidados que o sistema toma para o número não ser tratado como spam: só clientes marcados (que já conversam com o
escritório), intervalo aleatório entre as mensagens e limite por rodada.

Requer o pacote Python "playwright" (o INICIAR.bat instala sozinho).
"""

from __future__ import annotations

import json
import os
import random
import shutil
import threading
import time
import urllib.parse
from datetime import datetime
from pathlib import Path

from . import config, db, emissor

URL_WEB = "https://web.whatsapp.com"

# seletores do WhatsApp Web (com alternativas, porque a página muda de tempos em tempos)
LOGADO = ('#pane-side, [data-testid="chat-list"], div[aria-label="Lista de conversas"], div[aria-label="Chat list"], '
          'div[aria-label="Lista de chats"]')
QR = 'canvas[aria-label], div[data-ref] canvas, [data-testid="qrcode"]'
CAIXA = ('footer div[contenteditable="true"], div[contenteditable="true"][data-tab="10"], '
         'div[contenteditable="true"][aria-label="Digite uma mensagem"], div[contenteditable="true"][aria-placeholder]')
DIALOGO = 'div[role="dialog"], [data-animate-modal-popup="true"]'
SAIDA = "div.message-out"
ANEXAR = ('button[title="Anexar"], [aria-label="Anexar"], button[title="Attach"], [aria-label="Attach"], '
          'span[data-icon="plus-rounded"], span[data-icon="attach-menu-plus"], span[data-icon="clip"]')
ENVIAR_ANEXO = 'span[data-icon="send"], span[data-icon="wds-ic-send-filled"], [aria-label="Enviar"], [aria-label="Send"]'
PENDENTE = 'span[data-icon="msg-time"]'

_trava = threading.Lock()
_situacao: dict = {"conectando": False, "enviando": False, "mensagem": ""}


class ErroWhatsAppWeb(RuntimeError):
    pass


class Desconectado(ErroWhatsAppWeb):
    pass


class NumeroInvalido(ErroWhatsAppWeb):
    pass


def _cfg(cfg: dict | None = None) -> dict:
    return (cfg or config.carregar())["cobranca"]


def pasta() -> Path:
    """Sessão do WhatsApp Web DESTA empresa (nunca compartilhada com outra empresa)."""
    return emissor.raiz() / "dados" / "whatsapp_web"


def _marca() -> Path:
    return emissor.raiz() / "dados" / "whatsapp_web.json"


def disponivel() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
        return True
    except ImportError:
        return False


def conectado() -> dict:
    try:
        return json.loads(_marca().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ativo(cfg: dict | None = None) -> bool:
    """Envio automático ligado e sessão conectada (QR Code já lido)."""
    return bool(_cfg(cfg).get("whatsapp_web")) and bool(conectado()) and disponivel()


def estado(cfg: dict | None = None) -> dict:
    c = conectado()
    return {"disponivel": disponivel(), "conectado": bool(c), "desde": c.get("desde", ""),
            "verificado": c.get("verificado", ""), "ligado": bool(_cfg(cfg).get("whatsapp_web")),
            "ativo": ativo(cfg), **_situacao}


# ---------------------------------------------------------------- navegador

def _abrir(p, cfg: dict | None, visivel: bool):
    c = _cfg(cfg)
    pasta().mkdir(parents=True, exist_ok=True)
    args = ["--disable-notifications", "--no-first-run", "--no-default-browser-check"]
    if not visivel:
        args += ["--window-position=-32000,-32000", "--window-size=1200,900"]
    kw = {"user_data_dir": str(pasta()), "headless": False, "args": args, "locale": "pt-BR", "no_viewport": True}
    tentativas = ([{"executable_path": c["whatsapp_web_navegador"]}] if c.get("whatsapp_web_navegador")
                  else [{"channel": "msedge"}, {"channel": "chrome"}, {}])
    erro = None
    for t in tentativas:
        try:
            return p.chromium.launch_persistent_context(**kw, **t)
        except Exception as ex:  # noqa: BLE001 — tenta o próximo navegador
            erro = ex
            if "user data directory is already in use" in str(ex).lower() or "processsingleton" in str(ex).lower():
                raise ErroWhatsAppWeb("WhatsApp Web já está aberto por outra rotina do sistema; tento de novo depois.") from ex
    raise ErroWhatsAppWeb(f"Não consegui abrir o navegador (Edge/Chrome) para o WhatsApp Web: {erro}")


def _url(cfg: dict | None) -> str:
    return (_cfg(cfg).get("whatsapp_web_url") or URL_WEB).rstrip("/")


def _gravar_marca(**k) -> None:
    m = conectado() | k
    _marca().write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")


def conectar(cfg: dict | None = None, espera: int = 180) -> dict:
    """Abre o WhatsApp Web numa janela VISÍVEL para ler o QR Code (uma vez). Fecha sozinho quando conectar."""
    from playwright.sync_api import sync_playwright
    if not disponivel():
        raise ErroWhatsAppWeb("Falta o componente do WhatsApp Web: feche e abra o sistema pelo INICIAR.bat (ele instala).")
    with _trava:
        _situacao.update(conectando=True, mensagem="Leia o QR Code na janela do WhatsApp Web que abriu.")
        try:
            with sync_playwright() as p:
                ctx = _abrir(p, cfg, visivel=True)
                try:
                    pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                    pg.goto(_url(cfg), wait_until="domcontentloaded")
                    try:
                        pg.wait_for_selector(LOGADO, timeout=espera * 1000)
                    except Exception as ex:  # noqa: BLE001
                        raise ErroWhatsAppWeb("O QR Code não foi lido a tempo. Clique em Conectar de novo.") from ex
                    time.sleep(3)                       # deixa o WhatsApp Web terminar de sincronizar a sessão
                finally:
                    ctx.close()
        finally:
            _situacao.update(conectando=False, mensagem="")
    agora = datetime.now().isoformat(timespec="seconds")
    _gravar_marca(desde=conectado().get("desde") or agora, verificado=agora)
    c = config.carregar()
    if not c["cobranca"].get("whatsapp_web"):
        c["cobranca"]["whatsapp_web"] = True
        config.salvar(c)
    db.registrar("whatsapp", "WhatsApp Web conectado (QR Code lido)")
    return {"ok": True, "mensagem": "WhatsApp conectado. A cobrança por WhatsApp agora sai sozinha."}


def desconectar() -> dict:
    with _trava:
        shutil.rmtree(pasta(), ignore_errors=True)
        _marca().unlink(missing_ok=True)
    db.registrar("whatsapp", "WhatsApp Web desconectado pelo sistema")
    return {"ok": True, "mensagem": "WhatsApp desconectado deste computador. Remova também em Aparelhos conectados no celular."}


def _confirmar(pg, antes: int, espera: int = 60) -> bool:
    fim = time.time() + espera
    while time.time() < fim:
        n = pg.locator(SAIDA).count()
        if n > antes and not pg.locator(SAIDA).nth(n - 1).locator(PENDENTE).count():
            return True
        time.sleep(0.5)
    return False


def _anexar_pdf(pg, caminho: str) -> None:
    """Anexa o boleto em PDF como documento na conversa aberta e envia."""
    antes = pg.locator(SAIDA).count()
    pg.locator(ANEXAR).first.click()
    entrada, fim = None, time.time() + 15
    while entrada is None and time.time() < fim:          # o campo de documento aceita qualquer arquivo (não só fotos)
        campos = pg.locator('input[type="file"]')
        for i in range(campos.count()):
            aceita = campos.nth(i).get_attribute("accept") or "*"
            if not aceita.startswith(("image", "video")):
                entrada = campos.nth(i)
                break
        time.sleep(0.3)
    if entrada is None:
        raise ErroWhatsAppWeb("não achei onde anexar documento no WhatsApp Web")
    entrada.set_input_files(caminho)
    pg.wait_for_selector(ENVIAR_ANEXO, timeout=30000)
    time.sleep(random.uniform(0.6, 1.2))
    pg.locator(ENVIAR_ANEXO).last.click()
    if not _confirmar(pg, antes, 90):
        raise ErroWhatsAppWeb("o WhatsApp não confirmou o envio do PDF")


def _enviar_na_pagina(pg, url: str, numero: str, texto: str, pdf: str = "") -> str:
    pg.goto(f"{url}/send?phone={numero}&text={urllib.parse.quote(texto)}", wait_until="domcontentloaded")
    pg.wait_for_selector(f"{CAIXA}, {DIALOGO}, {QR}", timeout=90000)
    if pg.locator(QR).count() and not pg.locator(LOGADO).count():
        raise Desconectado("WhatsApp desconectado: leia o QR Code de novo em Configurações › WhatsApp.")
    fim = time.time() + 30
    while not pg.locator(CAIXA).count():                 # diálogo "carregando" ou "número inválido"
        if pg.locator(DIALOGO).count():
            txt = pg.locator(DIALOGO).first.inner_text().lower()
            if "inválido" in txt or "invalid" in txt or "não está no whatsapp" in txt:
                raise NumeroInvalido(f"O número {numero} não tem WhatsApp.")
        if time.time() > fim:
            raise ErroWhatsAppWeb("A conversa não abriu no WhatsApp Web.")
        time.sleep(0.5)
    pg.wait_for_function("s => { const e = document.querySelector(s); return e && e.innerText.trim().length > 0 }",
                         arg=CAIXA, timeout=20000)
    antes = pg.locator(SAIDA).count()
    time.sleep(random.uniform(0.6, 1.5))
    pg.locator(CAIXA).first.press("Enter")
    res = "enviado" if _confirmar(pg, antes) else "enviado (sem confirmação de entrega)"
    if pdf and os.path.isfile(pdf):
        try:
            _anexar_pdf(pg, pdf)
            res += " com o boleto em PDF"
        except Exception as ex:  # noqa: BLE001 — a mensagem (linha digitável e PIX) já foi; o PDF segue no e-mail
            res += f" (sem o PDF: {str(ex)[:120]})"
    return res


def enviar(itens: list[dict], cfg: dict | None = None, so_horario_comercial: bool = True) -> list[dict]:
    """Envia [{numero, texto, ...}] numa só sessão do navegador. Devolve cada item com 'resultado' ou 'erro'.
    Para tudo se a sessão estiver desconectada (o restante continua na fila).
    Toda mensagem do sistema passa por aqui: fora do horário comercial nada sai (só a mensagem de teste da tela)."""
    from playwright.sync_api import sync_playwright

    from . import horario
    if so_horario_comercial and not horario.comercial(cfg=cfg):
        raise ErroWhatsAppWeb(horario.motivo(cfg=cfg))
    c = _cfg(cfg)
    if not disponivel():
        raise ErroWhatsAppWeb("Falta o componente do WhatsApp Web: abra o sistema pelo INICIAR.bat (ele instala).")
    if not conectado():
        raise Desconectado("WhatsApp não conectado: leia o QR Code em Configurações › WhatsApp.")
    intervalo = float(c.get("whatsapp_web_intervalo", 15) or 0)
    saida = []
    if not _trava.acquire(timeout=600):
        raise ErroWhatsAppWeb("WhatsApp Web ocupado com outro envio; tento de novo depois.")
    _situacao.update(enviando=True)
    try:
        with sync_playwright() as p:
            ctx = _abrir(p, cfg, visivel=bool(c.get("whatsapp_web_visivel")))
            try:
                pg = ctx.pages[0] if ctx.pages else ctx.new_page()
                for i, it in enumerate(itens):
                    if i and intervalo and it["numero"] != itens[i - 1]["numero"]:   # mesmo cliente: segue direto
                        time.sleep(random.uniform(intervalo * 0.6, intervalo * 1.4))
                    try:
                        saida.append(it | {"resultado": _enviar_na_pagina(pg, _url(cfg), it["numero"], it["texto"], it.get("pdf", ""))})
                    except Desconectado as ex:
                        _marca().unlink(missing_ok=True)
                        saida.append(it | {"erro": str(ex), "desconectado": True})
                        break
                    except NumeroInvalido as ex:
                        saida.append(it | {"erro": str(ex), "invalido": True})
                    except Exception as ex:  # noqa: BLE001 — um cliente com problema não trava os outros
                        saida.append(it | {"erro": str(ex)[:300]})
            finally:
                ctx.close()
    finally:
        _situacao.update(enviando=False)
        _trava.release()
    if any("resultado" in s for s in saida):
        _gravar_marca(verificado=datetime.now().isoformat(timespec="seconds"))
    return saida


def numero_de(telefone: str) -> str:
    from . import clientes
    d = clientes._digitos(telefone)
    if d.startswith("55") and len(d) in (12, 13):
        return d
    return "55" + d if len(d) in (10, 11) else ""


def _do_link(link: str) -> tuple[str, str]:
    u = urllib.parse.urlparse(link)
    return u.path.strip("/"), (urllib.parse.parse_qs(u.query).get("text") or [""])[0]


def enviar_fila(cfg: dict | None = None, limite: int | None = None) -> dict:
    """Envia sozinho as mensagens de WhatsApp que a régua deixou na fila (status 'pendente').
    Cobrança: UMA mensagem por cliente com TODOS os títulos em aberto dele (soma e valor atualizado), montada na hora
    do envio, e um PDF de boleto por título logo em seguida. Agradecimento e nota fiscal continuam por título."""
    from . import cobranca, financeiro, horario
    cfg = cfg or config.carregar()
    if not horario.comercial(cfg=cfg):
        return {"enviados": 0, "erros": 0, "pendentes": len(cobranca.fila_whatsapp()), "aviso": horario.motivo(cfg=cfg)}
    fila = cobranca.fila_whatsapp()
    res = {"enviados": 0, "erros": 0, "pendentes": 0}
    if not fila:
        return res
    maximo = limite or int(_cfg(cfg).get("whatsapp_web_limite", 40) or 40)
    grupos: dict[str, list[dict]] = {}
    itens = []
    for e in fila:                                             # cobranças: agrupa por cliente, na ordem da fila
        t = financeiro.obter_titulo(e["titulo_id"])
        e["_t"] = t
        if e["etapa"] < cobranca.ETAPA_PAGO:
            grupos.setdefault(t["cpf_cnpj"], []).append(e)
        else:
            numero, texto = _do_link(e["detalhe"])
            pdf = ""
            if e["etapa"] == cobranca.ETAPA_NFSE and _cfg(cfg).get("whatsapp_web_pdf", True):
                try:
                    pdf = cobranca.pdf_nfse(t)               # a nota em PDF vai como documento, logo após o texto
                except Exception:  # noqa: BLE001
                    pdf = ""
            itens.append({"eventos": [e["id"]], "numero": numero, "texto": texto, "cliente": e["cliente_nome"], "pdf": pdf})
    for cpf, evs in grupos.items():
        numero, texto_antigo = _do_link(evs[0]["detalhe"])
        devidos = cobranca.todos_do_cliente(cpf, [(e["_t"], e["etapa"]) for e in evs])
        if len(devidos) == 1:
            t, etapa = devidos[0]
            texto = cobranca.mensagem(t, etapa, cfg, canal="whatsapp")[1] if t["status"] == "aberto" else texto_antigo
        else:
            texto = cobranca.mensagem_grupo(devidos, cfg, canal="whatsapp")[1]
        pdfs = [(t, p) for t, _ in devidos for p in [_pdf_do_titulo(t["id"], cfg)] if p]
        itens.append({"eventos": [e["id"] for e in evs], "numero": numero, "texto": texto, "cliente": evs[0]["cliente_nome"],
                      "pdf": pdfs[0][1] if pdfs else ""})
        for t, p in pdfs[1:]:                                  # os demais boletos, um documento por título
            itens.append({"eventos": [], "numero": numero, "cliente": evs[0]["cliente_nome"], "pdf": p,
                          "texto": f"Boleto com vencimento em {t['vencimento'][8:]}/{t['vencimento'][5:7]}/{t['vencimento'][:4]}"})
    itens = itens[:maximo]
    try:
        saida = enviar(itens, cfg)
    except Desconectado as ex:
        db.registrar("whatsapp", f"Fila de WhatsApp não enviada: {ex}")
        return res | {"pendentes": len(fila), "aviso": str(ex)}
    feitos = set()
    with db.conexao() as con:
        for s in saida:
            ids = s.get("eventos") or []
            feitos.update(ids)
            if "resultado" in s:
                for i in ids:
                    con.execute("UPDATE eventos_cobranca SET status='enviado', detalhe=? WHERE id=?",
                                (f"WhatsApp Web {s['numero']}: {s['resultado']}", i))
                res["enviados"] += 1 if ids else 0
            elif s.get("desconectado"):
                res["pendentes"] += len(ids)
                res["aviso"] = s["erro"]
                feitos.difference_update(ids)
            elif s.get("invalido"):
                for i in ids:
                    con.execute("UPDATE eventos_cobranca SET status='erro', detalhe=? WHERE id=?", (s["erro"], i))
                res["erros"] += 1 if ids else 0
            else:
                res["erros"] += 1 if ids else 0            # erro passageiro: continua na fila para a próxima rodada
                feitos.difference_update(ids)
    res["pendentes"] = len([e for e in fila if e["id"] not in feitos])
    db.registrar("whatsapp", f"WhatsApp Web: {res}")
    return res


def _pdf_do_titulo(tid: int, cfg: dict) -> str:
    """Boleto em PDF do título para mandar junto (Configurações › WhatsApp: 'enviar também o boleto em PDF')."""
    if not _cfg(cfg).get("whatsapp_web_pdf", True):
        return ""
    from . import cobranca, financeiro
    try:
        return cobranca._pdf_boleto(financeiro.obter_titulo(tid), cfg) or ""
    except Exception:  # noqa: BLE001 — sem PDF a mensagem sai com a linha digitável e o PIX
        return ""


def enviar_um(telefone: str, texto: str, cfg: dict | None = None, so_horario_comercial: bool = True, pdf: str = "") -> str:
    """Envio imediato (botão "Cobrar" e mensagem de teste). Devolve o número usado."""
    from . import horario
    if so_horario_comercial and not horario.comercial(cfg=cfg):
        raise ErroWhatsAppWeb(horario.motivo(cfg=cfg))
    numero = numero_de(telefone)
    if not numero:
        raise ErroWhatsAppWeb("Telefone do cliente inválido para WhatsApp (DDD + número).")
    s = enviar([{"numero": numero, "texto": texto, "pdf": pdf}], cfg, so_horario_comercial=so_horario_comercial)[0]
    if "erro" in s:
        raise ErroWhatsAppWeb(s["erro"])
    db.registrar("whatsapp", f"WhatsApp Web: mensagem enviada para {numero}")
    return numero


def em_segundo_plano(funcao, *args) -> None:
    """Roda o envio numa thread, na pasta da empresa que pediu (a tela não fica travada)."""
    raiz = emissor.raiz()

    def _rodar():
        with emissor.usar_empresa(raiz):
            try:
                funcao(*args)
            except Exception as ex:  # noqa: BLE001 — registra no log da empresa
                _situacao["mensagem"] = str(ex)[:300]
                db.registrar("whatsapp", f"WhatsApp Web: {ex}")
    threading.Thread(target=_rodar, daemon=True).start()
