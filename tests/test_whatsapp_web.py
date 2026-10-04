"""WhatsApp automático pelo WhatsApp Web (sem API oficial), testado num navegador de verdade contra um
WhatsApp Web simulado (QR Code, conversa, número inválido e confirmação de envio)."""

import json
import os
import shutil
import threading
import time
import urllib.parse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from nfse_itaborai import backup, clientes, cobranca, config, db, emissor, financeiro, whatsapp_web
from test_emissor import ambiente  # noqa: F401  (fixture)
from test_financeiro import CLI_A, base  # noqa: F401  (fixture)


def _navegador() -> str:
    for p in (os.environ.get("NFSE_TESTE_NAVEGADOR", ""), "/opt/pw-browsers/chromium", shutil.which("chromium") or "",
              shutil.which("google-chrome") or ""):
        if p and Path(p).exists():
            return p
    return ""


pytestmark = pytest.mark.skipif(not whatsapp_web.disponivel() or not _navegador()
                                or (os.name != "nt" and not os.environ.get("DISPLAY") and not shutil.which("Xvfb")),
                                reason="playwright, navegador ou tela (Xvfb) indisponível")


@pytest.fixture(scope="module", autouse=True)
def _tela_virtual():
    """O envio usa o navegador com janela (fora da tela), como no Windows; no Linux sem tela, um Xvfb."""
    if os.name == "nt" or os.environ.get("DISPLAY"):
        yield
        return
    import subprocess
    x = subprocess.Popen(["Xvfb", ":97", "-screen", "0", "1280x1024x24"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.environ["DISPLAY"] = ":97"
    time.sleep(1)
    try:
        yield
    finally:
        os.environ.pop("DISPLAY", None)
        x.terminate()

_TOPO = '<!doctype html><meta charset="utf-8"><title>WhatsApp</title>'
_QR = _TOPO + """<div data-ref="x"><canvas aria-label="Scan this QR code to link a device!" width="200" height="200"></canvas></div>
<script>setInterval(async () => { const r = await fetch('/_estado'); if ((await r.json()).logado) location.reload(); }, 300);</script>"""
_LISTA = _TOPO + '<div id="pane-side">conversas</div>'
_CONVERSA = _TOPO + """<div id="pane-side">conversas</div><div id="main"><div id="msgs"></div></div>
<script>
const q = new URLSearchParams(location.search), fone = q.get('phone'), texto = q.get('text') || '';
setTimeout(() => {
  if (%(invalido)s) { const d = document.createElement('div'); d.setAttribute('role', 'dialog');
    d.textContent = 'O número de telefone compartilhado através de url é inválido.'; document.body.append(d); return; }
  const f = document.createElement('footer'), c = document.createElement('div');
  c.setAttribute('contenteditable', 'true'); c.dataset.tab = '10'; c.style.whiteSpace = 'pre-wrap'; c.textContent = texto;
  f.append(c); document.body.append(f);
  c.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !c.textContent.trim()) return;
    e.preventDefault();
    const m = document.createElement('div'); m.className = 'message-out';
    m.innerHTML = '<span data-icon="msg-time"></span>'; m.append(c.textContent);
    document.getElementById('msgs').append(m);
    await fetch('/_enviado', { method: 'POST', body: JSON.stringify({ fone, texto: c.textContent }) });
    c.textContent = '';
    setTimeout(() => { m.querySelector('span').dataset.icon = 'msg-check'; }, 300);
  });
  // anexar documento: botão "Anexar" abre o menu com os campos de foto e de documento; a prévia tem "Enviar"
  const anexar = document.createElement('button'); anexar.setAttribute('aria-label', 'Anexar'); anexar.textContent = '+';
  f.prepend(anexar);
  anexar.onclick = () => {
    if (document.querySelector('input[type=file]')) return;
    const foto = document.createElement('input'); foto.type = 'file'; foto.accept = 'image/*,video/mp4'; foto.hidden = true;
    const doc = document.createElement('input'); doc.type = 'file'; doc.accept = '*'; doc.hidden = true;
    document.body.append(foto, doc);
    doc.onchange = () => {
      const nome = doc.files[0].name, prev = document.createElement('div');
      prev.innerHTML = '<span>' + nome + '</span><div role="button" aria-label="Enviar"><span data-icon="send">➤</span></div>';
      document.body.append(prev);
      prev.querySelector('[aria-label=Enviar]').onclick = async () => {
        const m = document.createElement('div'); m.className = 'message-out';
        m.innerHTML = '<span data-icon="msg-time"></span>'; m.append(nome);
        document.getElementById('msgs').append(m); prev.remove(); foto.remove(); doc.remove();
        await fetch('/_enviado', { method: 'POST', body: JSON.stringify({ fone, arquivo: nome, tamanho: doc.files[0].size }) });
        setTimeout(() => { m.querySelector('span').dataset.icon = 'msg-check'; }, 300);
      };
    };
  };
}, 400);
</script>"""


class FakeWhatsAppWeb(BaseHTTPRequestHandler):
    logado = False
    invalidos: set = set()
    enviados: list = []

    def log_message(self, *a):
        pass

    def _html(self, corpo: str):
        b = corpo.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _json(self, d):
        b = json.dumps(d).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):  # noqa: N802
        u = urllib.parse.urlparse(self.path)
        if u.path == "/_estado":
            return self._json({"logado": FakeWhatsAppWeb.logado})
        if u.path == "/_enviados":
            return self._json(FakeWhatsAppWeb.enviados)
        if not FakeWhatsAppWeb.logado:
            return self._html(_QR)
        if u.path == "/send":
            fone = (urllib.parse.parse_qs(u.query).get("phone") or [""])[0]
            return self._html(_CONVERSA % {"invalido": "true" if fone in FakeWhatsAppWeb.invalidos else "false"})
        return self._html(_LISTA)

    def do_POST(self):  # noqa: N802
        corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path == "/_enviado":
            FakeWhatsAppWeb.enviados.append(json.loads(corpo))
        elif self.path == "/_logar":
            FakeWhatsAppWeb.logado = True
        return self._json({"ok": True})


def servir_whatsapp_web() -> int:
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeWhatsAppWeb)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv.server_address[1]


@pytest.fixture
def wa(base):  # noqa: F811
    FakeWhatsAppWeb.logado, FakeWhatsAppWeb.invalidos, FakeWhatsAppWeb.enviados = False, set(), []
    porta = servir_whatsapp_web()
    c = config.carregar()
    c["cobranca"] |= {"whatsapp_web_url": f"http://127.0.0.1:{porta}", "whatsapp_web_navegador": _navegador(),
                      "whatsapp_web_intervalo": 0}
    config.salvar(c)
    return f"http://127.0.0.1:{porta}"


def _logar(url):
    import urllib.request
    urllib.request.urlopen(urllib.request.Request(url + "/_logar", data=b"{}", method="POST"))


def _conectar(url):
    th = threading.Thread(target=lambda: whatsapp_web.conectar(espera=30))
    th.start()
    time.sleep(2)              # QR Code na tela
    assert whatsapp_web.estado()["conectando"]
    _logar(url)                # "celular leu o QR Code"
    th.join(40)


def test_conectar_le_qr_code_e_liga_o_envio_automatico(wa):
    assert not whatsapp_web.ativo() and not whatsapp_web.estado()["conectado"]
    _conectar(wa)
    e = whatsapp_web.estado()
    assert e["conectado"] and e["ligado"] and e["ativo"] and not e["conectando"]
    assert config.carregar()["cobranca"]["whatsapp_web"] is True
    assert whatsapp_web.pasta().is_dir() and whatsapp_web.pasta().is_relative_to(emissor.raiz())


def test_regua_e_robo_enviam_sozinhos_so_para_clientes_marcados(wa, monkeypatch):
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    _conectar(wa)
    outro = CLI_A | {"cpf_cnpj": "11222333000181", "razao_social": "NAO MARCADO LTDA", "whatsapp_cobranca": False}
    clientes.salvar(outro)
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    financeiro.criar_titulo(outro["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    cobranca.rodar_regua(date(2026, 9, 30))
    assert len(cobranca.fila_whatsapp()) == 1
    r = whatsapp_web.enviar_fila()
    assert r == {"enviados": 1, "erros": 0, "pendentes": 0}
    assert cobranca.fila_whatsapp() == []
    env = FakeWhatsAppWeb.enviados
    assert len(env) == 1 and env[0]["fone"] == "5521988887777"
    assert "Olá, RPS Consultoria" in env[0]["texto"] and "anexo" not in env[0]["texto"] and "\n" in env[0]["texto"]
    ev = db.linhas("SELECT * FROM eventos_cobranca WHERE canal='whatsapp'")
    assert ev[0]["status"] == "enviado" and "WhatsApp Web 5521988887777: enviado" == ev[0]["detalhe"]


def test_numero_sem_whatsapp_vira_erro_e_nao_trava_os_outros(wa):
    _conectar(wa)
    FakeWhatsAppWeb.invalidos = {"5521977776666"}
    s = whatsapp_web.enviar([{"numero": "5521977776666", "texto": "a"}, {"numero": "5521988887777", "texto": "b"}])
    assert s[0]["invalido"] and "não tem WhatsApp" in s[0]["erro"]
    assert s[1]["resultado"] == "enviado" and [e["texto"] for e in FakeWhatsAppWeb.enviados] == ["b"]


def test_desconectado_mantem_a_fila_para_a_proxima_rodada(wa, monkeypatch):
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    _conectar(wa)
    FakeWhatsAppWeb.logado = False                       # celular removeu o aparelho conectado
    financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    cobranca.rodar_regua(date(2026, 9, 30))
    r = whatsapp_web.enviar_fila()
    assert r["enviados"] == 0 and r["pendentes"] == 1 and "QR Code" in r["aviso"]
    assert len(cobranca.fila_whatsapp()) == 1 and not whatsapp_web.estado()["conectado"]


def test_cobrar_envia_na_hora_e_mensagem_de_teste(wa, monkeypatch):
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    _conectar(wa)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-10-20", emitir_nfse=False)
    r = cobranca.cobrar_agora(tid)
    assert r["whatsapp_enviado"] == "5521988887777" and not r["whatsapp_erro"]
    from nfse_itaborai import tela
    r = tela.ROTAS["whatsapp_web/teste"]({"telefone": "21 97186-7366"})
    assert "5521971867366" in r["mensagem"]
    t = FakeWhatsAppWeb.enviados[-1]
    assert t["fone"] == "5521971867366" and t["texto"].startswith("*[TESTE") and "Cliente Exemplo LTDA" in t["texto"]


def test_sessao_fica_fora_do_backup_e_desconectar_apaga(wa):
    _conectar(wa)
    (whatsapp_web.pasta() / "Default").mkdir(exist_ok=True)
    (whatsapp_web.pasta() / "Default" / "Cookies").write_text("sessao")
    nomes = list(backup._arquivos(emissor.raiz()))
    assert nomes and not any("whatsapp_web/" in n for n in nomes)
    assert not backup._caminho_permitido("dados/whatsapp_web/Default/Cookies")
    whatsapp_web.desconectar()
    assert not whatsapp_web.pasta().exists() and not whatsapp_web.estado()["conectado"]


def test_boleto_em_pdf_vai_junto_da_mensagem(wa, tmp_path, monkeypatch):
    _conectar(wa)
    pdf = tmp_path / "Boleto RPS 10-2026.pdf"
    pdf.write_bytes(b"%PDF-1.4 boleto de teste")
    s = whatsapp_web.enviar([{"numero": "5521988887777", "texto": "Olá! Segue a cobrança.", "pdf": str(pdf)}])[0]
    assert s["resultado"] == "enviado com o boleto em PDF"
    env = FakeWhatsAppWeb.enviados
    assert env[0]["texto"] == "Olá! Segue a cobrança." and env[1]["arquivo"] == "Boleto RPS 10-2026.pdf" and env[1]["tamanho"] == 24
    # régua: o PDF do boleto do título vai junto; sem o PDF a mensagem sai normalmente
    monkeypatch.setattr(cobranca, "enviar_email", lambda *a, **k: None)
    tid = financeiro.criar_titulo(CLI_A["cpf_cnpj"], "300", vencimento="2026-09-25", emitir_nfse=False)
    monkeypatch.setattr(cobranca, "_pdf_boleto", lambda t, cfg: str(pdf) if t["id"] == tid else "")
    cobranca.rodar_regua(date(2026, 9, 30))
    assert whatsapp_web.enviar_fila()["enviados"] == 1
    assert [e.get("arquivo") for e in FakeWhatsAppWeb.enviados[2:]] == [None, "Boleto RPS 10-2026.pdf"]
    ev = db.linhas("SELECT detalhe FROM eventos_cobranca WHERE canal='whatsapp'")[0]["detalhe"]
    assert ev.endswith("enviado com o boleto em PDF")
    c = config.carregar(); c["cobranca"]["whatsapp_web_pdf"] = False; config.salvar(c)
    assert whatsapp_web._pdf_do_titulo(tid, config.carregar()) == ""
