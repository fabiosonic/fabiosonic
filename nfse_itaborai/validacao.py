"""Críticas locais antes do envio, conforme as exigências publicadas pela prefeitura
na página "Manuais & Tabelas" (Reforma Tributária, NTs 003 a 006)."""

from __future__ import annotations

from datetime import date, datetime

from .modelos import ISS_RETIDO_NAO, ISS_RETIDO_SIM, RESPONSAVEL, TRIBUTACAO, Rps
from .xml_rps import MAX_ITENS, so_digitos

DESDOBROS_COM_OBRA = {"141403", "141404"}
INICIO_OBRA_14_14 = date(2026, 6, 1)


class ErroValidacao(Exception):
    def __init__(self, erros: list[str]):
        super().__init__("; ".join(erros))
        self.erros = erros


def validar(rps: Rps, hoje: date | None = None) -> list[str]:
    """Levanta ErroValidacao com os impeditivos; devolve a lista de alertas."""
    hoje = hoje or (rps.data_emissao.date() if isinstance(rps.data_emissao, datetime) else date.today())
    erros: list[str] = []
    alertas: list[str] = []

    if not so_digitos(rps.numero):
        erros.append("Número do RPS não informado.")
    if not rps.itens:
        erros.append("Informe ao menos um item de serviço.")
    if len(rps.itens) > MAX_ITENS:
        erros.append(f"O webservice aceita no máximo {MAX_ITENS} itens por RPS.")
    for n, it in enumerate(rps.itens, 1):
        if not it.descricao.strip():
            erros.append(f"Item {n}: descrição vazia.")
        if len(it.descricao.strip()) > 60:
            erros.append(f"Item {n}: descrição com {len(it.descricao.strip())} caracteres (máximo 60). "
                         "Use 'observacoes' para o texto longo.")
        if int(it.quantidade) != it.quantidade or it.quantidade < 1:
            erros.append(f"Item {n}: quantidade deve ser inteira e maior que zero.")
        if it.valor_unitario <= 0:
            erros.append(f"Item {n}: valor unitário deve ser maior que zero.")
    if len(rps.observacoes.strip()) > 190:
        erros.append("Observações com mais de 190 caracteres.")

    if rps.tipo_tributacao not in TRIBUTACAO:
        erros.append(f"TipoDeTributacao inválido: {rps.tipo_tributacao!r} (use {', '.join(TRIBUTACAO)}).")
    if rps.iss_retido not in (ISS_RETIDO_SIM, ISS_RETIDO_NAO):
        erros.append("IssRetido deve ser '1' (sim) ou '2' (não).")
    if rps.responsavel_recolhimento not in RESPONSAVEL:
        erros.append("ResponsavelRecolhimento deve ser '', '1' (tomador) ou '2' (intermediário).")
    if rps.iss_retido == ISS_RETIDO_SIM and rps.responsavel_recolhimento == "":
        erros.append("ISS retido exige ResponsavelRecolhimento = '1' (tomador) ou '2' (intermediário).")

    item = so_digitos(rps.item_lista_servico)
    if len(item) not in (3, 4):
        erros.append("Item da lista da LC 116 inválido (ex.: 17.19).")
    nbs = so_digitos(rps.codigo_nbs)
    if len(nbs) != 9:
        erros.append("Código NBS obrigatório desde 01/01/2026 (9 dígitos) — Tabela 116 x NBS.")
    desdobro = so_digitos(rps.codigo_desdobro)
    if len(desdobro) != 6:
        erros.append("Código desdobro obrigatório desde 01/01/2026 (6 dígitos) — Tabela Desdobro.")
    elif item and desdobro[:4] != item.zfill(4):
        erros.append(f"Desdobro {desdobro} não pertence ao item {rps.item_lista_servico}.")
    if desdobro in DESDOBROS_COM_OBRA and hoje >= INICIO_OBRA_14_14 and not rps.codigo_obra.strip():
        erros.append(f"Desdobro {desdobro}: obrigatório informar o código da obra cadastrada no módulo "
                     "de Construção Civil da Prefeitura (Nota Técnica 004).")
    if len(so_digitos(rps.cnae)) < 7:
        erros.append("CNAE (ClassificacaoCNAE) obrigatório, 7 dígitos.")
    if item.zfill(4) == "0301":
        alertas.append("Item 03.01: confira o NBS atualizado em 01/05/2026 (Nota Técnica 006).")

    t = rps.tomador
    doc = so_digitos(t.cpf_cnpj)
    if doc and len(doc) not in (11, 14):
        erros.append("CPF/CNPJ do tomador inválido.")
    if doc and not t.razao_social.strip():
        erros.append("Razão social / nome do tomador não informado.")
    e = t.endereco
    if doc:
        if len(so_digitos(e.codigo_municipio)) != 7:
            erros.append("Código IBGE do município do tomador (7 dígitos) não informado.")
        if len(so_digitos(e.cep)) != 8:
            erros.append("CEP do tomador inválido.")
        if len(e.uf.strip()) != 2:
            erros.append("UF do tomador inválida.")

    if rps.aliquota_iss < 0 or rps.aliquota_iss > 5:
        erros.append("Alíquota de ISS fora do intervalo legal (0% a 5%).")
    if rps.valor_liquido <= 0:
        erros.append("Valor líquido da nota ficou zerado ou negativo.")

    r = rps.retencoes
    if r.valor_pis or r.valor_cofins or r.valor_csll:
        alertas.append("Retenção de PIS/COFINS/CSLL informada: desde 01/06/2026 a prefeitura exige "
                       "Situação Tributária e Tipo de Retenção (Nota Técnica 005). Se o RPS for "
                       "rejeitado por isso, emita esta nota pelo portal.")

    if erros:
        raise ErroValidacao(erros)
    return alertas
