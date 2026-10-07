import csv

from mo_autonomo.qualidade.amostra import gerar, medir
from mo_autonomo.trilha.auditoria import Trilha
from tests.conftest import CNPJ_A


def test_amostra_gerar_e_medir(tmp_path):
    t = Trilha(":memory:")
    for i in range(30):
        t.registrar_anexo(f"s{i:02d}", f"{i}.xml", "o", f"/bruto/{i}")
        t.registrar_documento(f"s{i:02d}", "NFE" if i < 25 else "PDF", f"k{i}", [CNPJ_A], "2026-10",
                              [{"cnpj": CNPJ_A, "tipo": "NFE_SAIDA"}], "OK")
    arq = tmp_path / "a.csv"
    r = gerar(t, arq, por_classe=10)
    assert r == {"amostra": 15, "universo": 30, "classes": {"NFE": 25, "PDF": 5}}
    assert gerar(t, tmp_path / "b.csv", por_classe=10)["amostra"] == 15
    assert arq.read_text(encoding="utf-8-sig") == (tmp_path / "b.csv").read_text(encoding="utf-8-sig")  # reprodutível
    with open(arq, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    for n, l in enumerate(linhas):
        l["conferencia"] = "ERRADO" if n == 0 else ("CERTO" if n < 14 else "")
    with open(arq, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]), delimiter=";")
        w.writeheader()
        w.writerows(linhas)
    m = medir(arq)
    assert m["conferidos"] == 14 and m["sem_conferencia"] == 1
    assert m["por_classe"]["NFE"]["errado"] == 1 and m["taxa_geral"] == round(13 / 14, 4)
