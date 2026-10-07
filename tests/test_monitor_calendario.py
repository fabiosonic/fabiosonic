from datetime import date

from mo_autonomo.clientes.perfil import Perfis
from mo_autonomo.normas.catalogo import Catalogo
from mo_autonomo.normas.monitor import carregar_alteradas, ficha_conferencia, monitorar, texto_normalizado
from mo_autonomo.obrigacoes.calendario import alertas, dia_util_anterior, gerar
from mo_autonomo.util.arquivos import sha256_bytes
from tests.conftest import CNPJ_A, CNPJ_B, CONFERIDA, carteira_teste

HTML = b"<html><body><h1>Lei X</h1><p>Art. 1&ordm; O imposto &eacute; devido.</p><script>x()</script></body></html>"


def cat_com_hash(h, status="CONFERIDO", **kw):
    item = {"id": "LEI_X", "titulo": "Lei X", "area": "fiscal", "hash_texto": h, "parametros": {"p": 1},
            "dispositivos": ["Art. 1º"], **kw}
    if status == "CONFERIDO":
        item.update({**CONFERIDA, "hash_texto": h})
    return Catalogo.de_lista([item])


def test_texto_normalizado():
    assert texto_normalizado(HTML) == "Lei X Art. 1º O imposto é devido."


def test_monitor_texto_igual_e_mudou(tmp_path):
    h = sha256_bytes(texto_normalizado(HTML).encode())
    r = monitorar(cat_com_hash(h), tmp_path, buscar=lambda u: HTML)
    assert r[0]["situacao"] == "IGUAL" and carregar_alteradas(tmp_path) == []
    r = monitorar(cat_com_hash(h), tmp_path, buscar=lambda u: HTML.replace(b"devido", b"isento"))
    assert r[0]["situacao"] == "MUDOU" and carregar_alteradas(tmp_path) == ["LEI_X"]
    cat = cat_com_hash(h)
    cat.marcar_alteradas(carregar_alteradas(tmp_path))
    assert cat.parametro("LEI_X", "p") is None and cat.status("LEI_X") == "ALTERADA_RECONFERIR"
    # texto voltou ao conferido: sai da lista
    monitorar(cat_com_hash(h), tmp_path, buscar=lambda u: HTML)
    assert carregar_alteradas(tmp_path) == []


def test_monitor_erro_de_rede_nao_derruba(tmp_path):
    def falha(u):
        raise OSError("sem rede")
    assert monitorar(cat_com_hash("x"), tmp_path, buscar=falha)[0]["situacao"] == "ERRO"


def test_ficha_conferencia_nao_marca_conferido(tmp_path):
    cat = cat_com_hash(None, status="PENDENTE", fonte_url_sugerida="https://www.planalto.gov.br/x")
    f = ficha_conferencia(cat, "LEI_X", tmp_path, buscar=lambda u: HTML)
    t = f.read_text(encoding="utf-8")
    assert "Status atual: **PENDENTE**" in t and "O imposto é devido" in t and "conferido_por: <seu nome>" in t
    assert cat.get("LEI_X").status == "PENDENTE"


def cat_obrigacoes(status="CONFERIDO"):
    item = {"id": "OBRIG_TESTE", "titulo": "t", "area": "fiscal",
            "parametros": {"obrigacoes": [
                {"codigo": "GUIA_S", "dia": 20, "meses_apos_competencia": 1, "regimes": ["SIMPLES"]},
                {"codigo": "GUIA_P", "dia": 31, "meses_apos_competencia": 1, "regimes": ["PRESUMIDO"]}]}}
    if status == "CONFERIDO":
        item.update(CONFERIDA)
    return Catalogo.de_lista([item])


def perfis(cat):
    p = Perfis(carteira_teste(), {}, cat)
    return {c: p.em(c, date(2026, 10, 1)) for c in (CNPJ_A, CNPJ_B)}


def test_calendario_antecipa_dia_util_e_alertas():
    cat = cat_obrigacoes()
    feriados = {date(2026, 11, 20)}
    v = gerar("2026-10", perfis(cat), cat, feriados)
    assert [(x.apelido, x.codigo) for x in v] == [("ALFA COMERCIO", "GUIA_S"), ("BETA SERVICOS", "GUIA_P")]
    # 20/11/2026 é sexta e feriado (config) -> 19/11
    assert v[0].vencimento_legal == date(2026, 11, 20) and v[0].vencimento == date(2026, 11, 19)
    # dia 31 em novembro -> 30/11 (segunda)
    assert v[1].vencimento == date(2026, 11, 30)
    assert dia_util_anterior(date(2026, 11, 22), set()) == date(2026, 11, 20)  # domingo -> sexta
    al = alertas(v, date(2026, 11, 16))
    assert len(al) == 1 and al[0]["quando"] == "em 3 dia(s)"
    assert alertas(v, date(2026, 11, 30))[0]["quando"] == "HOJE"


def test_calendario_sem_norma_conferida_fica_vazio():
    cat = cat_obrigacoes(status="PENDENTE")
    assert gerar("2026-10", perfis(cat), cat, set()) == []


def test_virada_de_ano():
    cat = cat_obrigacoes()
    v = gerar("2026-12", perfis(cat), cat, set())
    assert v[0].vencimento_legal == date(2027, 1, 20)
