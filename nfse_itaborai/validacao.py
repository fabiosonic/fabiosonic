"""Críticas locais antes do envio: limites do XSD oficial (schemas/webserviceNFSe.xsd) e
exigências publicadas pela prefeitura na página "Manuais & Tabelas" (NTs 003 a 006)."""

from __future__ import annotations

from datetime import date, datetime

from .modelos import ISS_RETIDO_NAO, ISS_RETIDO_SIM, RESPONSAVEL, TRIBUTACAO, Rps
from .xml_rps import MAX_ITENS, so_digitos

DESDOBROS_COM_OBRA = {"141403", "141404"}
INICIO_OBRA_14_14 = date(2026, 6, 1)
INICIO_IBS_CBS = date(2026, 6, 1)

# Tamanhos máximos do XSD
LIMITES_ENDERECO = {"tipo_logradouro": 10, "logradouro": 80, "numero": 6, "complemento": 30, "bairro": 30}


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
        if len(it.descricao.strip()) > 190:
            erros.append(f"Item {n}: descrição com {len(it.descricao.strip())} caracteres (máximo 190).")
        if int(it.quantidade) != it.quantidade or it.quantidade < 1:
            erros.append(f"Item {n}: quantidade deve ser inteira e maior que zero.")
        if it.valor_unitario <= 0:
            erros.append(f"Item {n}: valor unitário deve ser maior que zero.")
    if len(rps.observacoes.strip()) > 190:
        erros.append("Observações com mais de 190 caracteres.")
    if len(rps.codigo_obra.strip()) > 6:
        erros.append("Código da obra com mais de 6 caracteres.")
    if len(rps.codigo_tributacao_municipio.strip()) > 9:
        erros.append("Código de tributação do município com mais de 9 caracteres.")

    if rps.tipo_tributacao not in TRIBUTACAO:
        erros.append(f"TipoDeTributacao inválido: {rps.tipo_tributacao!r} (use {', '.join(TRIBUTACAO)}).")
    if rps.iss_retido not in (ISS_RETIDO_SIM, ISS_RETIDO_NAO):
        erros.append("IssRetido deve ser '1' (sim) ou '2' (não).")
    if rps.responsavel not in RESPONSAVEL:
        erros.append("ResponsavelRecolhimento deve ser '1' (tomador) ou '2' (prestador).")

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
    if len(so_digitos(rps.cnae)) > 9:
        erros.append("CNAE com mais de 9 dígitos.")
    if item.zfill(4) == "0301":
        alertas.append("Item 03.01: confira o NBS atualizado em 01/05/2026 (Nota Técnica 006).")

    ind_op, class_trib = so_digitos(rps.indicador_operacao), so_digitos(rps.classificacao_tributaria)
    if hoje >= INICIO_IBS_CBS and not (ind_op and class_trib):
        erros.append("IBS/CBS obrigatório desde 01/06/2026: informe Indicador da Operação (cIndOp) e "
                     "Classificação Tributária (cClassTrib) — Tabela IBS x CBS / Nota Técnica 003.")
    for nome, v in (("Indicador da Operação", ind_op), ("Classificação Tributária", class_trib)):
        if v and not (1 <= int(v) <= 999999):
            erros.append(f"{nome} deve ter até 6 dígitos e ser maior que zero.")

    t = rps.tomador
    doc = so_digitos(t.cpf_cnpj)
    if doc and len(doc) not in (11, 14):
        erros.append("CPF/CNPJ do tomador inválido.")
    if doc and not t.razao_social.strip():
        erros.append("Razão social / nome do tomador não informado.")
    if len(t.razao_social.strip()) > 80:
        erros.append("Razão social do tomador com mais de 80 caracteres.")
    if len(so_digitos(t.inscricao_municipal)) > 10 or len(t.inscricao_estadual.strip()) > 14:
        erros.append("Inscrição municipal (máx. 10) ou estadual (máx. 14) do tomador muito longa.")
    if len(so_digitos(t.telefone)) > 11:
        erros.append("Telefone do tomador com mais de 11 dígitos.")
    e = t.endereco
    for campo, limite in LIMITES_ENDERECO.items():
        if len(str(getattr(e, campo)).strip()) > limite:
            erros.append(f"Endereço do tomador: '{campo}' com mais de {limite} caracteres.")
    if doc:
        if len(so_digitos(e.codigo_municipio)) != 7:
            erros.append("Código IBGE do município do tomador (7 dígitos) não informado.")
        if len(so_digitos(e.cep)) != 8:
            erros.append("CEP do tomador inválido.")
        if len(e.uf.strip()) != 2:
            erros.append("UF do tomador inválida.")

    x = rps.extras or {}
    if x.get("evento_nome") and not (x.get("evento_cep") and x.get("evento_lgr")):
        erros.append("Evento: o webservice de Itaboraí exige o endereço do evento (CEP e logradouro).")
    if rps.aliquota_iss < 0 or rps.aliquota_iss > 5:
        erros.append("Alíquota de ISS fora do intervalo legal (máximo 5% — LC 116/2003, art. 8º, II).")
    if rps.tipo_tributacao == "4" and rps.iss_retido == ISS_RETIDO_SIM and rps.aliquota_iss <= 0:
        erros.append("Simples Nacional com ISS retido: informe a alíquota efetiva de ISS do PGDAS-D "
                     "(LC 123/2006, art. 21, § 4º).")
    if rps.valor_liquido <= 0:
        erros.append("Valor líquido da nota ficou zerado ou negativo.")

    r = rps.retencoes
    if r.valor_pis or r.valor_cofins or r.valor_csll:
        alertas.append("Retenção de PIS/COFINS/CSLL informada: desde 01/06/2026 a prefeitura exige "
                       "Situação Tributária e Tipo de Retenção (Nota Técnica 005), que não constam do XSD "
                       "atual. Se o RPS for rejeitado por isso, emita esta nota pelo portal.")

    if erros:
        raise ErroValidacao(erros)
    return alertas
