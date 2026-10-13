"""Dados de demonstração: empresas fictícias e um 'Drive' local com documentos de exemplo."""
from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .agenda import gerar_agenda
from .calendario import competencia_anterior, parse_competencia
from .drive.local import LocalDriveClient
from .models import Empresa, Responsavel
from .monitor import Monitor
from .pastas import NOMES_MESES, criar_estrutura_ano, nome_pasta_empresa
from .pdfsimples import gerar_pdf


def gerar_cnpj(base8: str, filial: str = "0001") -> str:
    b = base8 + filial
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    r = sum(int(d) * p for d, p in zip(b, p1)) % 11
    d1 = "0" if r < 2 else str(11 - r)
    r = sum(int(d) * p for d, p in zip(b + d1, [6] + p1)) % 11
    d2 = "0" if r < 2 else str(11 - r)
    return b + d1 + d2


def fmt(c: str) -> str:
    return f"{c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"


EMPRESAS = [
    dict(codigo="0001", razao_social="PADARIA BOM PAO LTDA", nome_fantasia="Padaria Bom Pão", base="11222333",
         regime="SIMPLES", uf="SP", municipio="Campinas", comercio=True, servicos=False, possui_funcionarios=True),
    dict(codigo="0002", razao_social="CLINICA VIDA SAUDAVEL LTDA", nome_fantasia="Clínica Vida", base="22333444",
         regime="PRESUMIDO", uf="SP", municipio="Campinas", servicos=True, area_saude=True, possui_funcionarios=True,
         retem_tributos=True),
    dict(codigo="0003", razao_social="DISTRIBUIDORA NORTE SUL LTDA", nome_fantasia="Norte Sul", base="33444555",
         regime="REAL", uf="MG", municipio="Uberlândia", comercio=True, servicos=False, possui_funcionarios=True,
         retem_tributos=True),
    dict(codigo="0004", razao_social="JOAO DA SILVA DESIGN", nome_fantasia="JS Design (MEI)", base="44555666",
         regime="MEI", uf="SP", municipio="Valinhos", servicos=True, possui_prolabore=False),
]


def criar_demo(s: Session, raiz: Path, competencia: str | None = None) -> dict:
    comp = competencia or competencia_anterior(date.today())
    ano, mes = parse_competencia(comp)
    drive = LocalDriveClient(raiz)

    resp = {}
    for nome, email, dep in [("Ana Moraes", "ana@moraeseoliveira.com.br", "FISCAL"),
                             ("Bruno Oliveira", "bruno@moraeseoliveira.com.br", "CONTABIL"),
                             ("Carla Souza", "carla@moraeseoliveira.com.br", "PESSOAL")]:
        r = s.scalar(select(Responsavel).where(Responsavel.nome == nome))
        if r is None:
            r = Responsavel(nome=nome, email=email, departamento=dep)
            s.add(r)
        resp[dep] = r
    s.flush()

    empresas = {}
    for d in EMPRESAS:
        d = dict(d)
        cnpj = gerar_cnpj(d.pop("base"))
        emp = s.scalar(select(Empresa).where(Empresa.cnpj == cnpj))
        if emp is None:
            emp = Empresa(cnpj=cnpj, **d)
            emp.email_cliente = f"financeiro@{d['codigo']}.exemplo.com.br"
            s.add(emp)
        emp.resp_fiscal, emp.resp_contabil, emp.resp_pessoal = resp["FISCAL"], resp["CONTABIL"], resp["PESSOAL"]
        emp.drive_folder_id = nome_pasta_empresa(emp)
        drive.garantir_pasta(emp.drive_folder_id, "")
        criar_estrutura_ano(drive, emp, ano, [mes])
        empresas[emp.codigo] = emp
    s.flush()
    gerar_agenda(s, comp)

    pasta_mes = f"{ano}/{mes:02d} - {NOMES_MESES[mes - 1]}"
    mm_aaaa = f"{mes:02d}/{ano}"
    padaria, clinica, distrib, mei = (empresas[c] for c in ("0001", "0002", "0003", "0004"))

    def salvar(emp: Empresa, sub: str, nome: str, linhas: list[str] | None = None, conteudo: bytes | None = None):
        destino = raiz / emp.drive_folder_id / pasta_mes / sub / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo if conteudo is not None else gerar_pdf(linhas or []))

    salvar(padaria, "01 - Fiscal", "Recibo PGDAS.pdf", [
        "Programa Gerador do Documento de Arrecadacao do Simples Nacional - Declaratorio",
        "Recibo de Entrega da Apuracao", f"CNPJ Matriz: {fmt(padaria.cnpj)}", f"Periodo de Apuracao (PA): {mm_aaaa}"])
    salvar(padaria, "01 - Fiscal", f"DAS {mes:02d}-{ano}.pdf", [
        "Documento de Arrecadacao do Simples Nacional", f"CNPJ {fmt(padaria.cnpj)}",
        f"Periodo de Apuracao: {mm_aaaa}", "Valor Total do Documento 3.512,44"])
    salvar(padaria, "03 - Pessoal", "Holerites.pdf", [
        "Recibo de Pagamento de Salario", f"Empregador CNPJ {fmt(padaria.cnpj)}", f"Competencia: {mm_aaaa}"])
    salvar(padaria, "04 - Documentos do Cliente", "extrato itau.pdf", [
        "Extrato de conta corrente", "Saldo anterior 10.000,00", f"Periodo: {mm_aaaa}"])
    # documento de outra empresa salvo na pasta errada
    salvar(padaria, "01 - Fiscal", "guia icms.pdf", [
        "Documento de Arrecadacao Estadual - DAE", "ICMS", f"CNPJ {fmt(distrib.cnpj)}", f"Referencia: {mm_aaaa}"])

    salvar(clinica, "01 - Fiscal", "Recibo DCTFWeb.pdf", [
        "Recibo de Entrega da DCTFWeb", f"CNPJ: {fmt(clinica.cnpj)}", f"Periodo de Apuracao: {mm_aaaa}"])
    salvar(clinica, "01 - Fiscal", "DARF PIS COFINS.pdf", [
        "Documento de Arrecadacao de Receitas Federais", f"CNPJ {fmt(clinica.cnpj)}",
        f"Periodo de Apuracao 30/{mm_aaaa}", "Codigo de Receita 8109"])
    salvar(clinica, "03 - Pessoal", "FGTS.pdf", [
        "Guia do FGTS Digital - GFD", f"Empregador: {fmt(clinica.cnpj)}", f"Competencia: {mm_aaaa}"])
    salvar(clinica, "04 - Documentos do Cliente", "scan_0001.pdf", ["Documento digitalizado sem identificacao"])

    nfe = (f'<?xml version="1.0"?><nfeProc><NFe><infNFe><emit><CNPJ>{distrib.cnpj}</CNPJ></emit>'
           f"<ide><dhEmi>{ano}-{mes:02d}-15T10:00:00-03:00</dhEmi></ide></infNFe></NFe></nfeProc>")
    salvar(distrib, "04 - Documentos do Cliente", f"NFe_{ano}{mes:02d}_000123.xml", conteudo=nfe.encode())
    salvar(distrib, "01 - Fiscal", "EFD Contribuicoes recibo.pdf", [
        "Recibo de Entrega de Escrituracao Fiscal Digital", "EFD-Contribuicoes", f"CNPJ {fmt(distrib.cnpj)}",
        f"Periodo: 01/{mm_aaaa} a 28/{mm_aaaa}"])

    salvar(mei, "01 - Fiscal", f"DAS-MEI {mes:02d}{ano}.pdf", [
        "Documento de Arrecadacao do Simples Nacional", "PGMEI - Microempreendedor Individual",
        f"CNPJ {fmt(mei.cnpj)}", f"Periodo de Apuracao: {mm_aaaa}"])

    r = Monitor(s, drive).sincronizar(completo=True)
    return {"competencia": comp, "empresas": len(empresas), "drive_local": str(raiz), **r.as_dict()}
