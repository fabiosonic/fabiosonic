import zipfile
from datetime import date

from mo_autonomo.clientes.receita import extrair_carteira
from tests.conftest import CNPJ_A, CNPJ_B


def test_extrai_so_carteira(tmp_path):
    a, b = CNPJ_A, CNPJ_B
    est = (f'"{a[:8]}";"{a[8:12]}";"{a[12:]}";"1";"FANTASIA";"02";"20200101";"00";"";"";"20200101";"4781400";'
           f'"4782201,4789099";"RUA";"X";"1";"";"CENTRO";"20000000";"RJ";"6001"\n'
           f'"99999999";"0001";"00";"1";"OUTRA";"02";"20200101";"00";"";"";"20200101";"1111111";"";"";"";"";"";"";"";"SP";"7107"\n')
    with zipfile.ZipFile(tmp_path / "Estabelecimentos0.zip", "w") as z:
        z.writestr("K3241.ESTABELE", est.encode("latin-1"))
    (tmp_path / "Empresas0.csv").write_bytes(
        f'"{a[:8]}";"ALFA COMÉRCIO LTDA";"2062";"49";"1000,00";"01";""\n'.encode("latin-1"))
    (tmp_path / "Simples.csv").write_bytes(f'"{a[:8]}";"S";"20200101";"00000000";"N";"00000000";"00000000"\n'.encode("latin-1"))
    r = extrair_carteira(tmp_path, {a, b})
    assert set(r) == {a}
    assert r[a]["estabelecimento"]["cnaes_secundarias"] == ["4782201", "4789099"]
    assert r[a]["empresa"]["razao_social"] == "ALFA COMÉRCIO LTDA"
    assert r[a]["simples"]["data_opcao_simples"] == date(2020, 1, 1)
    assert r[a]["simples"]["data_exclusao_simples"] is None
