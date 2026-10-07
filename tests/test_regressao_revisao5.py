"""Regressões da 5ª revisão."""
import re
import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from mo_autonomo.entrada.anexos import ZipSuspeito, anexos_do_email, expandir
from mo_autonomo.entrada.fontes import FonteImap
from mo_autonomo.util.dinheiro import ValorInvalido, dinheiro, dinheiro_br
from tests.conftest import eml_bytes, nfe_xml, zip_bytes

RAIZ = Path(__file__).resolve().parent.parent


def test_script_de_email_nao_imprime_linhas_nem_interpola_valores():
    bruto = (RAIZ / "scripts" / "configurar_email.ps1").read_bytes()
    texto = bruto.decode("utf-8-sig")
    assert "Select-String" not in texto and ".Line" not in texto  # nunca exibe linha de arquivo
    assert "'$imapHost'" not in texto and "'$porta'" not in texto and "'$Usuario'" not in texto
    assert "os.environ['MO_IMAP_HOST']" in texto


def test_regex_do_script_so_extrai_host_e_porta():
    # mesmo padrão do .ps1: em backup.py típico, só o host e a porta saem
    backup = 'imap = IMAP4_SSL("imap.provedor.com.br", 993)\nimap.login("fiscal@x.com.br", "Xy7#qWe2026")\n{"pw": "abc123"}'
    hosts = [m.group(0) for m in re.finditer(r"(?i)\b[a-z0-9-]*imap[a-z0-9-]*(\.[a-z0-9-]+)+\.[a-z]{2,}\b", backup)]
    portas = re.findall(r"\b(993|143)\b", backup)
    saida = " ".join(hosts + portas)
    assert hosts == ["imap.provedor.com.br"] and portas == ["993"]
    assert "Xy7" not in saida and "abc123" not in saida


@pytest.mark.parametrize("nome", ["configurar_email.ps1", "instalar_windows.ps1"])
def test_ps1_em_utf8_com_bom(nome):
    # Windows PowerShell 5.1 lê .ps1 sem BOM como ANSI e estraga "AUTOMAÇÕES"
    assert (RAIZ / "scripts" / nome).read_bytes().startswith(b"\xef\xbb\xbf")


def test_xlsx_nao_e_desmontado():
    xlsx = zip_bytes({"[Content_Types].xml": b"<Types/>", "xl/worksheets/sheet1.xml": b"<worksheet/>"})
    a = anexos_do_email(eml_bytes({"folha_setembro.xlsx": xlsx, "n.xml": nfe_xml()}), "u")
    assert sorted(x.nome for x in a) == ["folha_setembro.xlsx", "n.xml"]
    from mo_autonomo.documentos.classificador import classificar
    r = classificar(xlsx)
    assert r["classe"] == "DOCUMENTO_OFFICE" and "planilha" in r["erro"]


def test_zip_grande_legitimo_e_limite_configuravel():
    z = zip_bytes({f"n{i}.xml": b"<a/>" for i in range(2500)})
    assert len(expandir("lote.zip", z, "t")) == 2500
    with pytest.raises(ZipSuspeito, match="zip_max_arquivos"):
        expandir("lote.zip", z, "t", {"zip_max_arquivos": 100})


def test_milhar_sem_centavos_e_ambiguo_em_contexto_br():
    for v in ("1.500", "R$ 12.500", "1.234.567"):
        with pytest.raises(ValorInvalido, match="ambíguo"):
            dinheiro_br(v)
    assert dinheiro_br("R$ 1.500,00") == Decimal("1500.00") and dinheiro_br("150,00") == Decimal("150.00")
    assert dinheiro("2.345") == Decimal("2.35")  # XML/OFX: ponto decimal continua valendo


def test_imap_nao_baixa_de_novo_o_que_ja_foi_lido():
    class Falso:
        def __init__(self):
            self.fetches = 0

        def login(self, u, s): pass
        def select(self, p, readonly=False): return "OK", [b"2"]
        def response(self, c): return c, [b"9"]
        def logout(self): pass

        def uid(self, cmd, *a):
            if cmd == "search":
                return "OK", [b"1 2"]
            self.fetches += 1
            return "OK", [(b"x", eml_bytes({"a.xml": nfe_xml()}))]
    f = Falso()
    fonte = FonteImap("h", 993, "u", "s", desde=date(2026, 10, 1), fabrica=lambda: f)
    lidos = {"imap:INBOX:9:1"}
    msgs = list(fonte.mensagens(ja_lido=lambda k: k in lidos))
    assert [m.uid for m in msgs] == ["imap:INBOX:9:2"] and f.fetches == 1


def test_acao_bloqueada_reproposta_volta_a_proposta(tmp_path):
    from mo_autonomo.trilha.auditoria import Trilha
    t = Trilha(":memory:")
    a = {"tipo": "copiar_xml_rotina", "sha256": "s", "cnpj": "c", "pasta_tipo": "NFE_SAIDA"}
    t.registrar_acoes("L1", [a])
    t.marcar_acao(a, "BLOQUEADA", "CONFLITO")
    assert t.acoes_ja_propostas([a]) == set()
    t.registrar_acoes("L2", [a])
    assert t.con.execute("SELECT lote, estado FROM acoes").fetchall() == [("L2", "PROPOSTA")]


def test_dinheiro_br_formatos_americano_e_negativo_excel():
    for v in ("12,345.67", "1,500.00", "1,500"):
        with pytest.raises(ValorInvalido):
            dinheiro_br(v)
    assert dinheiro_br("-R$ 1.234,56") == Decimal("-1234.56")
    assert dinheiro_br("R$\xa01.234,56") == Decimal("1234.56")
    assert dinheiro_br("0,50") == Decimal("0.50") and dinheiro_br("100") == Decimal("100.00")


def test_zip_recusado_volta_quando_limite_aumenta(tmp_path):
    import yaml
    from mo_autonomo.aprovacao import lote as L
    from mo_autonomo.fluxos.ciclo import rodar_ciclo
    from tests.test_ponta_a_ponta import ctx_de, projeto
    base = projeto(tmp_path)
    cfgp = base / "config" / "config.yaml"
    cfg = yaml.safe_load(cfgp.read_text(encoding="utf-8"))
    cfg["entrada"] = {"zip_max_arquivos": 2}
    cfgp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    z = zip_bytes({f"{n}.xml": nfe_xml(numero=n) for n in (1, 2, 3)})
    (base / "entrada" / "1.eml").write_bytes(eml_bytes({"lote.zip": z}))
    e1 = rodar_ciclo(ctx_de(base))
    assert any(p["codigo"] == "ANEXO_ILEGIVEL" for p in e1["pendencias_gerais"])
    cfg["entrada"] = {"zip_max_arquivos": 100}
    cfgp.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    e2 = rodar_ciclo(ctx_de(base))
    acoes = [a for l in e2["lotes"] if not l.get("reapresentado") for a in L.carregar(Path(l["arquivo"]))["acoes"]]
    assert len(acoes) == 3


def test_limite_padrao_de_bytes_conservador():
    from mo_autonomo.entrada.anexos import LIMITES_PADRAO
    assert LIMITES_PADRAO["zip_max_bytes"] <= 512 * 1024 * 1024
