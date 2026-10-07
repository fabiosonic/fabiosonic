from pathlib import Path

import openpyxl

from mo_autonomo.clientes.cadastro import Carteira
from mo_autonomo.clientes.importar_planilha import conferir_pastas, converter, escrever, ler_planilha
from mo_autonomo.dominio.pastas import TIPOS_PADRAO
from mo_autonomo.util.documentos_id import formatar_cnpj
from tests.conftest import CNPJ_A, CNPJ_B, CNPJ_C, CPF_1


def planilha(tmp_path) -> Path:
    wb = openpyxl.Workbook()
    wb.active.title = "📊 Dashboard"
    ws = wb.create_sheet("📋 Cadastro de Clientes")
    ws.append(["CADASTRO DE CLIENTES"])
    ws.append([])
    ws.append(["CÓD.", "RAZÃO SOCIAL", "CNPJ / CPF", "CIDADE", "REGIME TRIBUTÁRIO", "SEGMENTO", "OBSERVAÇÕES", "STATUS"])
    ws.append([1.0, "Mercadinho Girassol Ltda", formatar_cnpj(CNPJ_A), "Itaboraí", "SIMPLES NACIONAL", "COMERCIO", "", "ATIVO"])
    ws.append([12.0, "Engenharia Ação/Obras LTDA.", CNPJ_B, "Rio", "LUCRO REAL", "SERVICO", "", "ATIVO"])
    ws.append([7.0, "Fulano MEI", CNPJ_C, "Niterói", "MEI", "", "", "ATIVO"])
    ws.append([8.0, "Pessoa Física", CPF_1, "Rio", "PF", "", "", "ATIVO"])
    ws.append([9.0, "Sem regime", "11222333000181", "Rio", "", "", "", "ATIVO"])
    ws.append([None, "Sem código", "11444777000161", "Rio", "SIMPLES NACIONAL", "", "", "ATIVO"])
    ws.append([10.0, "Repetida", formatar_cnpj(CNPJ_A), "Rio", "SIMPLES NACIONAL", "", "", "ATIVO"])
    ws.append([])
    p = tmp_path / "controle.xlsx"
    wb.save(p)
    return p


def test_converte_planilha_do_escritorio(tmp_path):
    empresas, pend = converter(ler_planilha(planilha(tmp_path)))
    assert [(e["codigo_dominio"], e["apelido"], e["regime"]) for e in empresas] == [
        ("1", "MERCADINHO GIRASSOL LTDA", "SIMPLES"), ("12", "ENGENHARIA ACAO OBRAS LTDA", "REAL"), ("7", "FULANO MEI", "MEI")]
    assert len(pend) == 4 and any("CPF" in p for p in pend) and any("repetido" in p for p in pend)
    assert any("regime" in p for p in pend) and any("CÓD." in p for p in pend)
    destino = tmp_path / "empresas.csv"
    escrever(empresas, destino)
    carteira = Carteira.carregar(destino)  # o arquivo gerado passa na validação do cadastro
    assert len(carteira) == 3 and carteira.get(CNPJ_B).pasta == "12-ENGENHARIA ACAO OBRAS LTDA"


def test_conferir_pastas_aponta_apelido_diferente(tmp_path):
    empresas, _ = converter(ler_planilha(planilha(tmp_path)))
    escrever(empresas, tmp_path / "e.csv")
    carteira = Carteira.carregar(tmp_path / "e.csv")
    base = tmp_path / "XML NOTAS"
    (base / "NFE SAIDA" / "1-MERCADINHO GIRASSOL LTDA").mkdir(parents=True)
    (base / "NFE ENTRADA" / "12-LMG ENGENHARIA").mkdir(parents=True)
    faltam = conferir_pastas(carteira, base, TIPOS_PADRAO)
    assert len(faltam) == 2
    assert any(f.startswith("12-ENGENHARIA") and "12-LMG ENGENHARIA" in f for f in faltam)
