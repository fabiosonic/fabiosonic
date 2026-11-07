"""Mapeador do Home Broker: encontra campos e não vaza valores da conta."""
import json

import pytest

pw = pytest.importorskip("playwright.sync_api")

# Valores FICTÍCIOS (nunca use dados reais de conta em testes)
HTML = """<html><body>
<div class="resumo"><span>Resumo da conta</span><span>Total investido + saldo</span><b>R$ 1.234,56</b></div>
<div class="boleta">
  <div class="MuiChip-root" role="button">Compra</div><div class="MuiChip-root" role="button">Venda</div>
  <div class="tipo"><span>Tipo de ordem</span><div role="combobox" aria-label="Tipo de ordem">A mercado</div></div>
  <fieldset><legend>Preço</legend><input name="price" value="2,68"></fieldset>
  <fieldset><legend>Quantidade</legend><input name="qty" value="100"></fieldset>
  <button class="btn-buy">Comprar 2,68</button>
</div>
<section><h3>Posição Swing Trade</h3>
<table><thead><tr><th>Ativo</th><th>Qtd.</th><th>Posição</th></tr></thead>
<tbody><tr><td>TEST3</td><td>300</td><td>9.876,54</td></tr><tr><td>TEST4</td><td>500</td><td>1.111,22</td></tr></tbody></table>
</section></body></html>"""


def _navegador(p):
    try:
        return p.chromium.launch()
    except Exception:
        import glob
        exes = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux*/chrome"))
        if not exes:
            pytest.skip("Chromium do Playwright indisponível")
        return p.chromium.launch(executable_path=exes[-1])


def test_coleta_estrutura_sem_valores():
    from swingbot.corretoras.mapeador import coletar, sem_dados_pessoais
    with pw.sync_playwright() as p:
        b = _navegador(p)
        pg = b.new_page()
        pg.set_content(HTML)
        dados = coletar(pg)
        b.close()
    q = dados["quadros"][0]
    rotulos = {i["rotulo"]: i for i in q["itens"] if i["tag"] == "input"}
    assert rotulos["Preço"]["name"] == "price" and rotulos["Quantidade"]["name"] == "qty"
    assert any(i["texto"] == "Comprar #,##" and i["tag"] == "button" for i in q["itens"])
    tab = q["tabelas"][0]
    assert tab["cabecalhos"] == ["Ativo", "Qtd.", "Posição"] and tab["linhas"] >= 2
    assert tab["linha_exemplo"]["celulas"][1]["texto"] == "###"
    texto = json.dumps(dados, ensure_ascii=False)
    for valor in ("1.234", "9.876", "1.111", "300"):
        assert valor not in texto
    assert sem_dados_pessoais(dados)


def test_rascunho_de_seletores_encontra_elementos_do_layout():
    import yaml
    sel = yaml.safe_load(open("config/seletores_clear.yaml", encoding="utf-8"))
    with pw.sync_playwright() as p:
        b = _navegador(p)
        pg = b.new_page()
        pg.set_content(HTML)
        for chave in ("navegacao.indicador_logado", "boleta.abrir_compra", "boleta.abrir_venda", "boleta.botao_enviar"):
            g, n = chave.split(".")
            assert pg.locator(sel[g][n]).count() >= 1, chave
        assert pg.locator(sel["boleta"]["botao_enviar"]).first.inner_text().startswith("Comprar")
        b.close()
    assert sel["validado"] is False   # modo real bloqueado até o ensaio ser confirmado


def test_coleta_dentro_de_shadow_dom():
    """O HB novo usa componentes com Shadow DOM: o coletor precisa enxergar dentro deles."""
    from swingbot.corretoras.mapeador import coletar
    html = """<html><body><boleta-clear></boleta-clear><script>
      const h = document.querySelector('boleta-clear'); const r = h.attachShadow({mode: 'open'});
      r.innerHTML = '<div role="tablist"><button>Compra</button><button>Venda</button></div>' +
        '<fieldset><legend>Quantidade</legend><input name="qty" value="100"></fieldset>' +
        '<div style="cursor:pointer">Limitada</div><button>Comprar 9,99</button>';
    </script></body></html>"""
    with pw.sync_playwright() as p:
        b = _navegador(p)
        pg = b.new_page()
        pg.set_content(html)
        q = coletar(pg)["quadros"][0]
        assert pg.locator("text='Compra'").count() == 1          # o Playwright também enxerga o shadow
        b.close()
    textos = [i["texto"] for i in q["itens"]]
    assert "Compra" in textos and "Venda" in textos and "Limitada" in textos and "Comprar #,##" in textos
    assert any(i["rotulo"] == "Quantidade" and i["name"] == "qty" for i in q["itens"])
    assert q["diagnostico"]["componentes_shadow"] == 1


BOLETA_HTML = """<html><body>
<div data-testid="SomaWindow">
  <div class="SomaWindow-header"><span id="tk">BEEF3</span> <span>2,61</span></div>
  <div class="MuiChip-root" role="button">Compra</div><div class="MuiChip-root" role="button">Venda</div>
  <ul><li class="MuiListItem-root" id="tipo"><p>Tipo de ordem</p><span id="tipoval">A mercado</span></li></ul>
  <div id="campos"><input name="price" value="A mercado"><input name="quantity" value="100"></div>
  <button id="enviar">Comprar 2,68</button>
</div>
<div id="menu"></div>
<script>
  window.ENVIADO = false;
  document.getElementById('enviar').onclick = () => { window.ENVIADO = true; };
  document.getElementById('tipo').onclick = () => {
    document.getElementById('menu').innerHTML = ['A mercado','Limitada','Stop','Stop duplo']
      .map(o => '<li role="option">' + o + '</li>').join('');
    document.querySelectorAll('#menu li').forEach(li => li.onclick = () => {
      document.getElementById('tipoval').innerText = li.innerText;
      const extra = li.innerText === 'Stop' ? '<input name="stopPrice">' :
                    li.innerText === 'Stop duplo' ? '<input name="gainTrigger"><input name="lossTrigger">' : '';
      document.getElementById('campos').innerHTML = '<input name="price"><input name="quantity">' + extra;
      document.getElementById('menu').innerHTML = '';
    });
  };
  document.addEventListener('keydown', e => { if (e.key === 'Escape') document.getElementById('menu').innerHTML = ''; });
  document.getElementById('tk').onclick = () => {
    document.getElementById('menu').innerHTML = '<div role="dialog"><input name="symbolSearch" placeholder="Buscar ativo"></div>';
    document.querySelector('[name=symbolSearch]').focus();
  };
</script></body></html>"""


def test_exploracao_automatica_descobre_campos_sem_enviar():
    from swingbot.corretoras.mapeador import explorar_boleta
    with pw.sync_playwright() as p:
        b = _navegador(p)
        pg = b.new_page()
        pg.set_content(BOLETA_HTML)
        r = explorar_boleta(pg, log=lambda *_: None)
        enviado = pg.evaluate("window.ENVIADO")
        b.close()
    assert enviado is False, "a exploração NUNCA pode clicar em Comprar"
    assert r["opcoes_tipo_ordem"] == ["A mercado", "Limitada", "Stop", "Stop duplo"]
    nomes = {op: [c["name"] for c in cs] for op, cs in r["seletores_descobertos"].items() if op != "busca_ativo"}
    assert "stopPrice" in nomes["Stop"] and "gainTrigger" in nomes["Stop duplo"]
    assert r["seletores_descobertos"]["busca_ativo"][0]["name"] == "symbolSearch"


def test_clique_seguro_bloqueia_envio():
    from swingbot.corretoras.mapeador import _clique_seguro
    with pw.sync_playwright() as p:
        b = _navegador(p)
        pg = b.new_page()
        pg.set_content(BOLETA_HTML)
        assert _clique_seguro(pg.locator("#enviar"), lambda *_: None) is False
        assert pg.evaluate("window.ENVIADO") is False
        b.close()


def test_url_sem_codigos_de_acesso():
    from swingbot.corretoras.mapeador import _url_limpa
    assert _url_limpa("https://authenticate.clear.com.br/login?state=hKFo2SBW") == "https://authenticate.clear.com.br/login"
    assert _url_limpa("https://trader.clear.com.br/home-broker/new/?code=abc#x") == "https://trader.clear.com.br/home-broker/new/"


def test_espera_o_home_broker_carregar():
    from swingbot.corretoras.mapeador import esperar_homebroker
    with pw.sync_playwright() as p:
        b = _navegador(p)
        ctx = b.new_context()
        pg = ctx.new_page()
        pg.set_content("<p>Tela de login</p>")
        assert esperar_homebroker(ctx, log=lambda *_: None, timeout_seg=3) is None   # ainda no login: não começa
        pg.route("https://trader.clear.com.br/**", lambda r: r.fulfill(body="<span>Resumo da conta</span>",
                                                                       content_type="text/html"))
        pg.goto("https://trader.clear.com.br/home-broker/new/")
        assert esperar_homebroker(ctx, log=lambda *_: None, timeout_seg=10) is pg
        b.close()
