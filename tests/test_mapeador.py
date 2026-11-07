"""Mapeador do Home Broker: encontra campos e não vaza valores da conta."""
import json

import pytest

pw = pytest.importorskip("playwright.sync_api")

HTML = """<html><body>
<div class="resumo"><span>Resumo da conta</span><span>Total investido + saldo</span><b>R$ 42.970,95</b></div>
<div class="boleta">
  <button role="tab">Compra</button><button role="tab">Venda</button><button role="tab">Rápida</button>
  <div class="tipo"><span>Tipo de ordem</span><div role="combobox" aria-label="Tipo de ordem">A mercado</div></div>
  <fieldset><legend>Preço</legend><input name="price" value="2,68"></fieldset>
  <fieldset><legend>Quantidade</legend><input name="qty" value="100"></fieldset>
  <button class="btn-buy">Comprar 2,68</button>
</div>
<section><h3>Posição Swing Trade</h3>
<table><thead><tr><th>Ativo</th><th>Qtd.</th><th>Posição</th></tr></thead>
<tbody><tr><td>BBAS3</td><td>700</td><td>12.019,00</td></tr><tr><td>CSAN3</td><td>1000</td><td>2.770,00</td></tr></tbody></table>
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
    for valor in ("42.970", "12.019", "2.770", "700"):
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
