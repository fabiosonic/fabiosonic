"""Tela local de emissão (somente 127.0.0.1), sem dependências externas."""

from __future__ import annotations

import json
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import emissor
from .validacao import ErroValidacao

PADRAO = Path(__file__).resolve().parent.parent / "exemplos" / "padrao_prestador.json"

PAGINA = """<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NFS-e Itaboraí</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#f4f6fb;color:#1c2333}
header{background:#1f3a8a;color:#fff;padding:14px 20px;font-weight:600}
main{max-width:980px;margin:0 auto;padding:16px}
fieldset{background:#fff;border:1px solid #d5dbe8;border-radius:8px;margin:0 0 14px;padding:12px 14px}
legend{font-weight:600;color:#1f3a8a}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px 12px}
label{display:flex;flex-direction:column;font-size:12px;color:#4a5570;gap:3px}
input,select,textarea{font:inherit;font-size:14px;padding:6px 8px;border:1px solid #c3cbdc;border-radius:6px}
.itens div{display:grid;grid-template-columns:3fr 1fr 1fr;gap:8px;margin-bottom:6px}
button{font:inherit;padding:9px 16px;border:0;border-radius:6px;cursor:pointer;margin-right:8px}
.b1{background:#e3e8f4}.b2{background:#1f3a8a;color:#fff}.b3{background:#b91c1c;color:#fff}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;white-space:pre-wrap;word-break:break-all;font-size:12px}
.ok{color:#047857;font-weight:600}.erro{color:#b91c1c;font-weight:600}
</style></head><body><header>Emissor NFS-e — Prefeitura de Itaboraí (webservice)</header><main>
<form id="f">
<fieldset><legend>Tomador</legend><div class="g">
<label>CPF/CNPJ<input name="t_doc" required></label>
<label style="grid-column:span 2">Razão social / nome<input name="t_nome" required></label>
<label>Inscrição municipal<input name="t_im"></label>
<label>E-mail<input name="t_email" type="email"></label><label>Telefone<input name="t_fone"></label>
<label>Tipo logradouro<input name="e_tipo" placeholder="RUA"></label>
<label style="grid-column:span 2">Logradouro<input name="e_logr"></label>
<label>Número<input name="e_num"></label><label>Complemento<input name="e_compl"></label>
<label>Bairro<input name="e_bairro"></label><label>Cód. IBGE município<input name="e_mun" value="3301900"></label>
<label>UF<input name="e_uf" value="RJ" maxlength="2"></label><label>CEP<input name="e_cep"></label>
</div></fieldset>
<fieldset><legend>Serviço (até 5 itens; descrição até 190 caracteres)</legend><div class="itens" id="itens"></div>
<div class="g">
<label>Item LC 116<input name="item" required></label><label>NBS (9 dígitos)<input name="nbs" required></label>
<label>Desdobro (6 dígitos)<input name="desdobro" required></label><label>CNAE<input name="cnae" required></label>
<label>Alíquota ISS % (Simples sem retenção: 0)<input name="aliq" required></label>
<label>Tributação<select name="trib"><option value="4">4 - Simples Nacional</option><option value="0">0 - Tributado no município</option><option value="1">1 - Tributado fora do município</option><option value="2">2 - Isento/imune</option><option value="3">3 - Exigibilidade suspensa</option><option value="5">5 - Retido no município</option></select></label>
<label>ISS retido<select name="ret"><option value="2">Não</option><option value="1">Sim</option></select></label>
<label>IBS/CBS - Indicador operação (cIndOp)<input name="indop" required></label>
<label>IBS/CBS - Classif. tributária (cClassTrib)<input name="ctrib" required></label>
<label>Competência<input name="comp" type="month"></label>
<label>Código da obra (14.14)<input name="obra"></label>
<label>Local prestação (IBGE)<input name="lp" value="3301900"></label><label>Local recolhimento (IBGE)<input name="lr" value="3301900"></label>
<label>Valor aprox. tributos (IBPT)<input name="ibpt" value="0"></label>
<label>Nº RPS (vazio = automático)<input name="rps"></label>
</div>
<label style="margin-top:8px">Observações (até 190)<textarea name="obs" rows="2" maxlength="190"></textarea></label>
</fieldset>
<button type="button" class="b1" onclick="enviar('conferir')">Conferir XML</button>
<button type="button" class="b2" onclick="enviar('homologacao')">Emitir em homologação</button>
<button type="button" class="b3" onclick="enviar('producao')">Emitir em PRODUÇÃO</button>
</form>
<fieldset style="margin-top:14px"><legend>Cancelar NFS-e</legend><div class="g">
<label>Número da NFS-e<input id="c_num"></label><label style="grid-column:span 2">Justificativa<input id="c_just"></label>
</div><p><button class="b1" onclick="cancelar(false)">Cancelar (homologação)</button><button class="b3" onclick="cancelar(true)">Cancelar (PRODUÇÃO)</button></p></fieldset>
<div id="out"></div></main>
<script>
const P=__PADRAO__;
const it=document.getElementById('itens');
for(let i=0;i<5;i++)it.insertAdjacentHTML('beforeend',`<div><input name="d${i}" maxlength="190" placeholder="Descrição item ${i+1}"><input name="q${i}" value="1"><input name="v${i}" placeholder="Valor unitário"></div>`);
const f=document.getElementById('f');
for(const[k,v]of Object.entries(P))if(f.elements[k])f.elements[k].value=v;
function dados(){const g=n=>f.elements[n].value.trim();const itens=[];
for(let i=0;i<5;i++)if(g('d'+i))itens.push({descricao:g('d'+i),quantidade:+g('q'+i)||1,valor_unitario:g('v'+i)});
return{numero:g('rps'),itens,item_lista_servico:g('item'),codigo_nbs:g('nbs'),codigo_desdobro:g('desdobro'),cnae:g('cnae'),
aliquota_iss:g('aliq'),tipo_tributacao:g('trib'),iss_retido:g('ret'),indicador_operacao:g('indop'),classificacao_tributaria:g('ctrib'),
competencia:g('comp'),codigo_obra:g('obra'),local_prestacao:g('lp'),local_recolhimento:g('lr'),
valor_total_tributos:g('ibpt'),observacoes:g('obs'),
tomador:{cpf_cnpj:g('t_doc'),razao_social:g('t_nome'),inscricao_municipal:g('t_im'),email:g('t_email'),telefone:g('t_fone'),
endereco:{tipo_logradouro:g('e_tipo'),logradouro:g('e_logr'),numero:g('e_num'),complemento:g('e_compl'),bairro:g('e_bairro'),
codigo_municipio:g('e_mun'),uf:g('e_uf'),cep:g('e_cep')}}}}
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function mostrar(r){let h=r.sucesso?'<p class="ok">'+esc(r.titulo)+'</p>':'<p class="erro">'+esc(r.titulo)+'</p>';
if(r.erros&&r.erros.length)h+='<ul>'+r.erros.map(e=>'<li class="erro">'+esc(e)+'</li>').join('')+'</ul>';
if(r.alertas&&r.alertas.length)h+='<ul>'+r.alertas.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul>';
(r.notas||[]).forEach(n=>{h+=`<p>NFS-e <b>${esc(n.numero_nfse)}</b> — verificação ${esc(n.codigo_verificacao)} ${n.link?'— <a target=_blank href="'+esc(n.link)+'">abrir</a>':''}</p>`});
if(r.pasta)h+='<p>Arquivos: '+esc(r.pasta)+'</p>';if(r.xml)h+='<pre>'+esc(r.xml)+'</pre>';
document.getElementById('out').innerHTML=h;window.scrollTo(0,document.body.scrollHeight)}
async function enviar(modo){if(modo==='producao'&&!confirm('Emitir em PRODUÇÃO? A nota terá validade fiscal.'))return;
const r=await fetch('/api/'+modo,{method:'POST',body:JSON.stringify(dados())});mostrar(await r.json())}
async function cancelar(prod){if(prod&&!confirm('Cancelar a NFS-e em PRODUÇÃO?'))return;
const r=await fetch('/api/cancelar',{method:'POST',body:JSON.stringify({numero:c_num.value,justificativa:c_just.value,producao:prod})});mostrar(await r.json())}
</script></body></html>"""


def _resultado(resp, titulo_ok: str, titulo_erro: str) -> dict:
    return {"sucesso": resp.sucesso, "titulo": titulo_ok if resp.sucesso else titulo_erro,
            "erros": resp.erros, "alertas": resp.alertas, "pasta": resp.pasta,
            "notas": [asdict(n) | {"xml": None} for n in resp.notas],
            "xml": "" if resp.sucesso else resp.xml_retorno}


def tratar(rota: str, corpo: dict) -> dict:
    try:
        if rota == "conferir":
            rps = emissor.rps_de_dict(corpo)
            xml, _lote, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
            return {"sucesso": True, "titulo": f"RPS {rps.numero} válido — serviços R$ {rps.valor_servicos}, "
                    f"ISS R$ {rps.valor_iss}, líquido R$ {rps.valor_liquido}", "alertas": alertas, "xml": xml}
        if rota in ("homologacao", "producao"):
            resp = emissor.emitir(emissor.rps_de_dict(corpo), producao=rota == "producao")
            return _resultado(resp, "NFS-e emitida", "RPS não convertido em NFS-e")
        if rota == "cancelar":
            resp = emissor.cancelar(str(corpo.get("numero", "")), str(corpo.get("justificativa", "")),
                                    producao=bool(corpo.get("producao")))
            return _resultado(resp, "Cancelamento processado", "Cancelamento não processado")
        return {"sucesso": False, "titulo": "Rota inválida"}
    except ErroValidacao as ex:
        return {"sucesso": False, "titulo": "RPS com pendências (nada foi enviado)", "erros": ex.erros}
    except (emissor.ErroConfiguracao, ValueError, KeyError) as ex:
        return {"sucesso": False, "titulo": "Erro", "erros": [str(ex)]}
    except OSError as ex:
        return {"sucesso": False, "titulo": "Falha de comunicação com o webservice", "erros": [str(ex)]}


class _Handler(BaseHTTPRequestHandler):
    def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):  # noqa: N802
        padrao = PADRAO.read_text(encoding="utf-8") if PADRAO.exists() else "{}"
        self._responder(200, PAGINA.replace("__PADRAO__", padrao).encode("utf-8"), "text/html; charset=utf-8")

    def do_POST(self):  # noqa: N802
        if not self.path.startswith("/api/"):
            return self._responder(404, b"{}", "application/json")
        tamanho = int(self.headers.get("Content-Length", 0))
        corpo = json.loads(self.rfile.read(tamanho) or b"{}")
        r = tratar(self.path[len("/api/"):], corpo)
        self._responder(200, json.dumps(r, ensure_ascii=False, default=str).encode("utf-8"),
                        "application/json; charset=utf-8")

    def log_message(self, *args):
        pass


def servir(porta: int = 8765, abrir: bool = True) -> None:
    srv = ThreadingHTTPServer(("127.0.0.1", porta), _Handler)
    url = f"http://127.0.0.1:{porta}"
    print(f"Tela de emissão em {url} (Ctrl+C para sair)")
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
