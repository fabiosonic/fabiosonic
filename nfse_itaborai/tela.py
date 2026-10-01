"""Tela local de emissão (somente 127.0.0.1), sem dependências externas.

Três abas, pensadas para o mínimo de cliques:
  Emitir   — escolhe o cliente, digita o valor, clica em Emitir;
  Lote     — marca os clientes (valor da última nota já preenchido) e emite todos;
  Clientes — cadastro, com busca automática do CNPJ na Receita (BrasilAPI).
"""

from __future__ import annotations

import json
import webbrowser
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import clientes, emissor, lote
from .validacao import ErroValidacao

PAGINA = r"""<!doctype html><html lang="pt-br"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NFS-e Itaboraí</title>
<style>
:root{--azul:#1f3a8a;--borda:#d5dbe8;--fundo:#f4f6fb;--verde:#047857;--verm:#b91c1c}
*{box-sizing:border-box}body{font-family:system-ui,Segoe UI,sans-serif;margin:0;background:var(--fundo);color:#1c2333}
header{background:var(--azul);color:#fff;padding:12px 20px;display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
header b{font-size:18px}.amb{padding:6px 12px;border-radius:20px;font-weight:600;font-size:13px;cursor:pointer;border:0}
.amb.hom{background:#fde68a;color:#78350f}.amb.prod{background:#22c55e;color:#052e16}
nav{display:flex;gap:4px;padding:0 20px;background:#fff;border-bottom:1px solid var(--borda)}
nav button{background:none;border:0;padding:14px 18px;font-size:15px;cursor:pointer;border-bottom:3px solid transparent}
nav button.on{border-color:var(--azul);color:var(--azul);font-weight:600}
main{max-width:1000px;margin:0 auto;padding:18px 16px}section{display:none}section.on{display:block}
.card{background:#fff;border:1px solid var(--borda);border-radius:10px;padding:18px;margin-bottom:14px}
label{display:flex;flex-direction:column;font-size:13px;color:#4a5570;gap:4px}
input,select{font:inherit;font-size:15px;padding:9px 10px;border:1px solid #c3cbdc;border-radius:7px;width:100%}
.g{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.big{font-size:20px}
button.b{font:inherit;font-size:15px;padding:11px 20px;border:0;border-radius:8px;cursor:pointer;background:var(--azul);color:#fff}
button.s{background:#e3e8f4;color:#1c2333}button.r{background:var(--verm)}button:disabled{opacity:.5;cursor:wait}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{padding:8px 6px;border-bottom:1px solid #eef1f7;text-align:left;vertical-align:middle}
th{font-size:12px;color:#4a5570;text-transform:uppercase}td input{padding:6px 8px;font-size:14px}
.ok{color:var(--verde);font-weight:600}.erro{color:var(--verm)}.muted{color:#6b7280;font-size:13px}
.res{margin-top:14px}.res div{padding:8px 10px;border-radius:7px;margin-bottom:6px;background:#fff;border:1px solid var(--borda)}
.linha{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.linha>*{flex:1}
details summary{cursor:pointer;color:var(--azul);font-size:14px;margin-top:10px}
</style></head><body>
<header><b>Emissor NFS-e · Itaboraí</b><button id="amb" class="amb hom" onclick="trocarAmbiente()">…</button></header>
<nav><button class="on" onclick="aba('emitir',this)">Emitir nota</button><button onclick="aba('lote',this)">Emitir em lote</button><button onclick="aba('clientes',this)">Clientes</button></nav>
<main>
<section id="emitir" class="on"><div class="card">
 <div class="g">
  <label style="grid-column:1/-1">Cliente<input id="e_cli" list="lista_cli" placeholder="Digite o nome ou CNPJ e escolha" class="big"></label>
  <label>Valor (R$)<input id="e_valor" inputmode="decimal" placeholder="0,00" class="big"></label>
  <label style="grid-column:span 2">Descrição<input id="e_desc" maxlength="190"></label>
 </div>
 <datalist id="lista_cli"></datalist>
 <p style="margin:16px 0 0"><button class="b" id="e_btn" onclick="emitirUma()">Emitir nota</button></p>
 <div id="e_res" class="res"></div>
</div></section>

<section id="lote"><div class="card">
 <div class="linha"><label>Filtrar<input id="l_filtro" placeholder="nome ou CNPJ" oninput="desenharLote()"></label>
  <label>Descrição para todas<input id="l_desc" maxlength="190"></label></div>
 <p class="muted">Marque os clientes. O valor já vem com o da última nota — ajuste se precisar.</p>
 <table><thead><tr><th><input type="checkbox" onclick="marcarTodos(this.checked)"></th><th>Cliente</th><th style="width:140px">Valor (R$)</th><th>Última</th></tr></thead><tbody id="l_tab"></tbody></table>
 <p style="margin:16px 0 0"><button class="b" id="l_btn" onclick="emitirLote()">Emitir selecionadas</button> <span id="l_tot" class="muted"></span></p>
 <div id="l_res" class="res"></div>
</div></section>

<section id="clientes"><div class="card">
 <div class="linha"><label>CNPJ / CPF<input id="c_doc" placeholder="só números"></label>
  <div style="flex:0"><button class="b s" onclick="buscarCnpj()">Buscar na Receita</button></div></div>
 <div class="g" style="margin-top:12px">
  <label style="grid-column:1/-1">Razão social / nome<input id="c_nome"></label>
  <label>Tipo logradouro<input id="c_tipo" placeholder="RUA"></label><label style="grid-column:span 2">Logradouro<input id="c_logr"></label>
  <label>Número<input id="c_num"></label><label>Complemento<input id="c_compl"></label><label>Bairro<input id="c_bairro"></label>
  <label>CEP<input id="c_cep"></label><label>Cód. IBGE município<input id="c_mun"></label><label>UF<input id="c_uf" maxlength="2"></label>
  <label>Inscrição municipal<input id="c_im"></label><label>E-mail<input id="c_email"></label><label>Telefone<input id="c_fone"></label>
 </div>
 <p style="margin:16px 0 0"><button class="b" onclick="salvarCliente()">Salvar cliente</button> <button class="b s" onclick="limparCliente()">Novo</button></p>
 <div id="c_res" class="res"></div>
</div>
<div class="card"><div class="linha"><label>Procurar<input id="c_filtro" oninput="desenharClientes()" placeholder="nome ou CNPJ"></label></div>
 <table><thead><tr><th>Cliente</th><th>CNPJ/CPF</th><th>Cidade</th><th></th></tr></thead><tbody id="c_tab"></tbody></table>
 <p class="muted" id="c_total"></p></div>
</section>
</main>
<script>
let CLIS=[],PADRAO={},PROD=false;
const $=id=>document.getElementById(id);
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmtDoc=d=>d.length==14?d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/,'$1.$2.$3/$4-$5'):d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/,'$1.$2.$3-$4');
const brl=v=>{const n=typeof v=='number'?v:valorNum(v);return n?n.toLocaleString('pt-BR',{minimumFractionDigits:2,maximumFractionDigits:2}):''};
async function api(rota,corpo){const r=await fetch('/api/'+rota,{method:'POST',body:JSON.stringify(corpo||{})});return r.json()}
function aba(id,b){document.querySelectorAll('section').forEach(s=>s.classList.toggle('on',s.id==id));document.querySelectorAll('nav button').forEach(x=>x.classList.toggle('on',x==b))}
async function carregar(){const d=await api('estado');CLIS=d.clientes;PADRAO=d.padrao;PROD=d.producao;
 $('amb').textContent=PROD?'PRODUÇÃO (notas válidas)':'HOMOLOGAÇÃO (teste) — clique para ativar produção';$('amb').className='amb '+(PROD?'prod':'hom');
 $('e_desc').value=$('e_desc').value||PADRAO.descricao;$('l_desc').value=$('l_desc').value||PADRAO.descricao;
 $('lista_cli').innerHTML=CLIS.map(c=>`<option value="${esc(c.razao_social)} — ${fmtDoc(c.cpf_cnpj)}">`).join('');
 desenharLote();desenharClientes()}
async function trocarAmbiente(){const p=!PROD;
 if(p&&!confirm('Ativar PRODUÇÃO? As notas emitidas terão validade fiscal.'))return;
 if(!p&&!confirm('Voltar para HOMOLOGAÇÃO (teste, sem validade)?'))return;await api('ambiente',{producao:p});carregar()}
function docDe(txt){const m=String(txt).match(/(\d[\d./-]{10,})\s*$/);return m?m[1].replace(/\D/g,''):String(txt).replace(/\D/g,'')}
function linhaRes(r){return r.sucesso?`<div><span class="ok">✔ ${esc(r.cliente)} — R$ ${esc(brl(r.valor))}</span> · NFS-e <b>${esc(r.nfse)}</b> · RPS ${esc(r.rps)} ${r.link&&r.link.startsWith('http')?`· <a href="${esc(r.link)}" target="_blank">abrir nota</a>`:''}${(r.alertas||[]).map(a=>`<div class="muted">${esc(a)}</div>`).join('')}</div>`
 :`<div><span class="erro">✖ ${esc(r.cliente)} — R$ ${esc(brl(r.valor))}</span>${(r.erros||[]).map(e=>`<div class="erro">${esc(e)}</div>`).join('')}</div>`}
async function emitirUma(){const doc=docDe($('e_cli').value);const cli=CLIS.find(c=>c.cpf_cnpj==doc);
 if(!cli)return alert('Escolha um cliente da lista (ou cadastre na aba Clientes).');
 const v=$('e_valor').value.trim();if(!v)return alert('Informe o valor.');
 if(!confirm(`${PROD?'EMITIR NOTA VÁLIDA':'Teste em homologação'}\n\n${cli.razao_social}\nR$ ${v}\n${$('e_desc').value}`))return;
 $('e_btn').disabled=true;$('e_res').innerHTML='<div>Enviando…</div>';
 const r=await api('emitir',{cpf_cnpj:doc,valor:v,descricao:$('e_desc').value});$('e_btn').disabled=false;
 $('e_res').innerHTML=linhaRes(r);if(r.sucesso){$('e_valor').value='';carregar()}}
function desenharLote(){const f=$('l_filtro').value.toLowerCase().replace(/[./-]/g,'');
 $('l_tab').innerHTML=CLIS.filter(c=>!f||c.razao_social.toLowerCase().includes(f)||c.cpf_cnpj.includes(f)).map(c=>`<tr>
 <td><input type="checkbox" class="lc" data-doc="${c.cpf_cnpj}" onchange="somar()"></td><td>${esc(c.razao_social)}<div class="muted">${fmtDoc(c.cpf_cnpj)}</div></td>
 <td><input class="lv" data-doc="${c.cpf_cnpj}" value="${c.ultimo_valor?brl(c.ultimo_valor):''}" oninput="somar()"></td><td class="muted">${esc(c.ultima_data||'')}</td></tr>`).join('');somar()}
function marcarTodos(v){document.querySelectorAll('.lc').forEach(x=>x.checked=v);somar()}
function valorNum(s){s=String(s).trim();if(s.includes(','))s=s.replace(/\./g,'').replace(',','.');return Number(s)||0}
function selecionados(){return [...document.querySelectorAll('.lc:checked')].map(x=>({cpf_cnpj:x.dataset.doc,valor:document.querySelector(`.lv[data-doc="${x.dataset.doc}"]`).value}))}
function somar(){const s=selecionados();$('l_tot').textContent=s.length?`${s.length} nota(s) · total R$ ${brl(s.reduce((a,b)=>a+valorNum(b.valor),0))}`:''}
async function emitirLote(){const itens=selecionados().map(i=>({...i,descricao:$('l_desc').value}));
 if(!itens.length)return alert('Marque ao menos um cliente.');const sem=itens.filter(i=>!valorNum(i.valor));if(sem.length)return alert('Há cliente marcado sem valor.');
 if(!confirm(`${PROD?'EMITIR '+itens.length+' NOTAS VÁLIDAS':'Teste em homologação de '+itens.length+' notas'}\nTotal R$ ${brl(itens.reduce((a,b)=>a+valorNum(b.valor),0))}`))return;
 $('l_btn').disabled=true;$('l_res').innerHTML='<div>Enviando, aguarde…</div>';
 const r=await api('lote',{itens});$('l_btn').disabled=false;const ok=r.filter(x=>x.sucesso).length;
 $('l_res').innerHTML=`<div><b>${ok} de ${r.length} emitida(s).</b></div>`+r.map(linhaRes).join('');carregar()}
const CAMPOS={c_tipo:'tipo_logradouro',c_logr:'logradouro',c_num:'numero',c_compl:'complemento',c_bairro:'bairro',c_cep:'cep',c_mun:'codigo_municipio',c_uf:'uf'};
function preencher(c){$('c_doc').value=c.cpf_cnpj||'';$('c_nome').value=c.razao_social||'';$('c_im').value=c.inscricao_municipal||'';$('c_email').value=c.email||'';$('c_fone').value=c.telefone||'';
 for(const[k,v]of Object.entries(CAMPOS))$(k).value=(c.endereco||{})[v]||''}
function limparCliente(){preencher({});$('c_res').innerHTML=''}
async function buscarCnpj(){$('c_res').innerHTML='<div>Consultando a Receita…</div>';const r=await api('cnpj',{cnpj:$('c_doc').value});
 if(r.erro){$('c_res').innerHTML=`<div class="erro">${esc(r.erro)}</div>`;return}preencher(r);$('c_res').innerHTML='<div class="ok">Dados da Receita preenchidos. Confira e clique em Salvar.</div>'}
async function salvarCliente(){const e={};for(const[k,v]of Object.entries(CAMPOS))e[v]=$(k).value;
 const r=await api('cliente/salvar',{cpf_cnpj:$('c_doc').value,razao_social:$('c_nome').value,inscricao_municipal:$('c_im').value,email:$('c_email').value,telefone:$('c_fone').value,endereco:e});
 $('c_res').innerHTML=r.erro?`<div class="erro">${esc(r.erro)}</div>`:'<div class="ok">Cliente salvo.</div>';if(!r.erro)carregar()}
async function excluirCliente(doc){const c=CLIS.find(x=>x.cpf_cnpj==doc);if(!confirm('Excluir '+c.razao_social+' do cadastro?'))return;await api('cliente/excluir',{cpf_cnpj:doc});carregar()}
function editar(doc){preencher(CLIS.find(c=>c.cpf_cnpj==doc));window.scrollTo(0,0)}
function usar(doc){const c=CLIS.find(x=>x.cpf_cnpj==doc);$('e_cli').value=`${c.razao_social} — ${fmtDoc(c.cpf_cnpj)}`;$('e_valor').value=c.ultimo_valor?brl(c.ultimo_valor):'';aba('emitir',document.querySelector('nav button'))}
function desenharClientes(){const f=$('c_filtro').value.toLowerCase().replace(/[./-]/g,'');const l=CLIS.filter(c=>!f||c.razao_social.toLowerCase().includes(f)||c.cpf_cnpj.includes(f));
 $('c_tab').innerHTML=l.map(c=>`<tr><td>${esc(c.razao_social)}</td><td>${fmtDoc(c.cpf_cnpj)}</td><td>${esc((c.endereco||{}).bairro||'')} ${esc((c.endereco||{}).uf||'')}</td>
 <td style="white-space:nowrap"><button class="b" onclick="usar('${c.cpf_cnpj}')">Emitir</button> <button class="b s" onclick="editar('${c.cpf_cnpj}')">Editar</button> <button class="b s" onclick="excluirCliente('${c.cpf_cnpj}')">✕</button></td></tr>`).join('');
 $('c_total').textContent=`${CLIS.length} cliente(s) cadastrado(s).`}
carregar();
</script></body></html>"""


def _resultado(resp, titulo_ok: str, titulo_erro: str) -> dict:
    return {"sucesso": resp.sucesso, "titulo": titulo_ok if resp.sucesso else titulo_erro,
            "erros": resp.erros, "alertas": resp.alertas, "pasta": resp.pasta,
            "notas": [asdict(n) | {"xml": None} for n in resp.notas],
            "xml": "" if resp.sucesso else resp.xml_retorno}


def tratar(rota: str, corpo: dict):
    try:
        if rota == "estado":
            return {"clientes": clientes.listar(), "padrao": lote.servico_padrao(), "producao": emissor.em_producao()}
        if rota == "ambiente":
            emissor.definir_ambiente(bool(corpo.get("producao")))
            return {"producao": emissor.em_producao()}
        if rota == "emitir":
            return lote.emitir_um(str(corpo.get("cpf_cnpj", "")), corpo.get("valor", 0),
                                  str(corpo.get("descricao", "")), producao=emissor.em_producao())
        if rota == "lote":
            return lote.emitir_lote(list(corpo.get("itens", [])), producao=emissor.em_producao())
        if rota == "cnpj":
            return clientes.consultar_cnpj(str(corpo.get("cnpj", "")))
        if rota == "cliente/salvar":
            return clientes.salvar(corpo)
        if rota == "cliente/excluir":
            return {"excluido": clientes.excluir(str(corpo.get("cpf_cnpj", "")))}
        if rota == "conferir":
            rps = emissor.rps_de_dict(corpo)
            xml, _lote, alertas = emissor.preparar(rps, emissor.prestador_do_ambiente(), producao=False)
            return {"sucesso": True, "titulo": f"RPS {rps.numero} válido — serviços R$ {rps.valor_servicos}, "
                    f"ISS R$ {rps.valor_iss}, líquido R$ {rps.valor_liquido}", "alertas": alertas, "xml": xml}
        if rota == "cancelar":
            resp = emissor.cancelar(str(corpo.get("numero", "")), str(corpo.get("justificativa", "")),
                                    producao=emissor.em_producao())
            return _resultado(resp, "Cancelamento processado", "Cancelamento não processado")
        return {"erro": "Rota inválida"}
    except ErroValidacao as ex:
        return {"sucesso": False, "titulo": "Pendências (nada foi enviado)", "erros": ex.erros, "erro": "; ".join(ex.erros)}
    except (emissor.ErroConfiguracao, ValueError, KeyError) as ex:
        return {"sucesso": False, "titulo": "Erro", "erros": [str(ex)], "erro": str(ex)}
    except OSError as ex:
        return {"sucesso": False, "titulo": "Falha de comunicação", "erros": [str(ex)],
                "erro": f"Falha de comunicação: {ex}"}


class _Handler(BaseHTTPRequestHandler):
    def _responder(self, codigo: int, corpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):  # noqa: N802
        self._responder(200, PAGINA.encode("utf-8"), "text/html; charset=utf-8")

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
    print(f"Tela de emissão em {url} (deixe esta janela aberta; Ctrl+C para sair)")
    if abrir:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
