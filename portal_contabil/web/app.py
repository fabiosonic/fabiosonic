"""Portal web: o cliente envia os arquivos e recebe a auditoria na hora.

Execução:  python -m portal_contabil web   (ou: uvicorn portal_contabil.web.app:app)

Segurança/LGPD:
- Defina PORTAL_USUARIO e PORTAL_SENHA para exigir login (HTTP Basic). Em produção,
  publique atrás de HTTPS e de um provedor de identidade.
- Os arquivos não são gravados em disco: são processados em memória. Só os relatórios
  ficam em PORTAL_DADOS (padrão: pasta temporária) e são apagados após PORTAL_RETENCAO_HORAS.
"""
from __future__ import annotations

import os
import re
import secrets
import shutil
import tempfile
import time
import uuid
from html import escape
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..auditoria import auditar
from ..importadores import Importador
from ..relatorio import salvar

PASTA = Path(os.environ.get("PORTAL_DADOS", Path(tempfile.gettempdir()) / "portal_contabil"))
RETENCAO_S = float(os.environ.get("PORTAL_RETENCAO_HORAS", "24")) * 3600
LIMITE_UPLOAD = int(os.environ.get("PORTAL_LIMITE_MB", "300")) * 1024 * 1024
ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")

app = FastAPI(title="Portal Contábil - Auditoria", docs_url=None, redoc_url=None)
_basic = HTTPBasic(auto_error=False)


def autenticar(cred: HTTPBasicCredentials | None = Depends(_basic)) -> None:
    usuario, senha = os.environ.get("PORTAL_USUARIO"), os.environ.get("PORTAL_SENHA")
    if not usuario or not senha:
        return
    ok = cred is not None and secrets.compare_digest(cred.username.encode(), usuario.encode()) \
        and secrets.compare_digest(cred.password.encode(), senha.encode())
    if not ok:
        raise HTTPException(401, "Autenticação necessária", headers={"WWW-Authenticate": "Basic"})


def _limpar_antigos() -> None:
    if not PASTA.exists():
        return
    agora = time.time()
    for p in PASTA.iterdir():
        if p.is_dir() and agora - p.stat().st_mtime > RETENCAO_S:
            shutil.rmtree(p, ignore_errors=True)


FORM = """<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Auditoria Fiscal</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--fg:#1c2330;--muted:#5b6575;--line:#d9dde3;--accent:#1f5eff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#0f1218;--card:#171b23;--fg:#e6e9ef;--muted:#9aa3b2;--line:#2a303b;--accent:#6f9bff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:720px;margin:0 auto;padding:32px 16px}h1{font-size:24px;margin:0 0 6px}p{color:var(--muted)}
form{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:20px;display:grid;gap:16px}
label{font-weight:600;font-size:14px;display:grid;gap:6px}
input,select{font:inherit;padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
.drop{border:2px dashed var(--line);border-radius:10px;padding:28px;text-align:center;color:var(--muted);cursor:pointer}
.drop.on{border-color:var(--accent);color:var(--accent)}
button{font:inherit;font-weight:600;background:var(--accent);color:#fff;border:0;border-radius:8px;padding:11px;cursor:pointer}
ul{margin:0;padding-left:18px;color:var(--muted);font-size:14px}.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
@media(max-width:520px){.row{grid-template-columns:1fr}}
</style></head><body><main>
<h1>Envie seus documentos para auditoria</h1>
<p>Arraste a pasta compactada (.zip) ou os arquivos soltos. O portal importa tudo, separa as notas emitidas e
recebidas, cruza com o extrato e aponta riscos e oportunidades de recuperação de tributos.</p>
<form method="post" action="auditar" enctype="multipart/form-data" id="f">
<div class="drop" id="drop">Clique ou arraste aqui: XML de NF-e/NFC-e/NFS-e, eventos de cancelamento, extratos OFX,
CSV da folha ou ZIP com tudo<input type="file" name="arquivos" id="arq" multiple hidden
accept=".xml,.zip,.ofx,.csv,.txt"><div id="lista"></div></div>
<div class="row"><label>CNPJ da empresa (opcional)<input name="cnpj" placeholder="Detectado automaticamente"
inputmode="text" maxlength="18"></label>
<label>Regime tributário<select name="regime"><option value="auto">Detectar pelas notas</option>
<option value="simples">Simples Nacional</option><option value="mei">MEI</option>
<option value="normal">Lucro Presumido / Real</option></select></label></div>
<button type="submit">Importar e auditar</button>
<ul><li>CSV da folha: <code>competencia;salarios;pro_labore;encargos</code> (para o Fator R).</li>
<li>Os arquivos são processados em memória e os relatórios são apagados automaticamente.</li></ul>
</form></main>
<script>
const d=document.getElementById('drop'),i=document.getElementById('arq'),l=document.getElementById('lista');
const mostrar=()=>{l.textContent=i.files.length?i.files.length+' arquivo(s) selecionado(s)':''};
d.onclick=()=>i.click();i.onchange=mostrar;
['dragenter','dragover'].forEach(e=>d.addEventListener(e,ev=>{ev.preventDefault();d.classList.add('on')}));
['dragleave','drop'].forEach(e=>d.addEventListener(e,ev=>{ev.preventDefault();d.classList.remove('on')}));
d.addEventListener('drop',ev=>{i.files=ev.dataTransfer.files;mostrar()});
</script></body></html>"""


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(autenticar)])
def inicio() -> str:
    return FORM


@app.post("/auditar", dependencies=[Depends(autenticar)])
async def enviar(arquivos: list[UploadFile] = File(...), cnpj: str = Form(""), regime: str = Form("auto")):
    if regime not in {"auto", "simples", "mei", "normal"}:
        raise HTTPException(400, "regime inválido")
    _limpar_antigos()
    imp = Importador()
    total = 0
    for arq in arquivos:
        conteudo = await arq.read(LIMITE_UPLOAD - total + 1)
        total += len(conteudo)
        if total > LIMITE_UPLOAD:
            raise HTTPException(413, "Envio maior que o limite permitido")
        nome = Path(arq.filename or "arquivo").name
        imp.importar_bytes(nome, conteudo)
    lote = imp.finalizar()
    res = auditar(lote, cnpj=cnpj.strip() or None, regime=regime)
    job = uuid.uuid4().hex
    salvar(res, PASTA / job)
    return RedirectResponse(f"relatorio/{job}", status_code=303)


def _pasta_job(job: str) -> Path:
    if not ID_VALIDO.match(job):
        raise HTTPException(404)
    p = PASTA / job
    if not p.is_dir():
        raise HTTPException(404, "Relatório expirado ou inexistente")
    return p


@app.get("/relatorio/{job}", response_class=HTMLResponse, dependencies=[Depends(autenticar)])
def relatorio(job: str) -> str:
    html = (_pasta_job(job) / "auditoria.html").read_text(encoding="utf-8")
    barra = (f'<div style="max-width:1180px;margin:0 auto;padding:16px 16px 0;display:flex;gap:12px;flex-wrap:wrap">'
             f'<a href="../">← Nova auditoria</a><a href="{escape(job)}/xlsx">Baixar Excel</a>'
             f'<a href="{escape(job)}/json">Baixar JSON</a></div>')
    return html.replace("<main>", barra + "<main>", 1)


@app.get("/relatorio/{job}/{formato}", dependencies=[Depends(autenticar)])
def baixar(job: str, formato: str):
    if formato not in {"xlsx", "json", "html"}:
        raise HTTPException(404)
    arq = _pasta_job(job) / f"auditoria.{formato}"
    if not arq.exists():
        raise HTTPException(404, "Formato indisponível")
    return FileResponse(arq, filename=f"auditoria_{job[:8]}.{formato}")
