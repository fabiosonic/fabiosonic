"""Regras de tributação do webservice de Itaboraí (Manual do Usuário Webservice, versão 2026 — XML de 28/09/2026).

Tipo de Tributação:
  0 Tributado no Município (Lucro Presumido/Real; recolhe o prestador)
  1 Tributado/Retido fora do Município (serviços da lista 1.1 prestados fora)
  2 Isento/Imune (MEI em qualquer item; imunes pela legislação municipal)
  3 Suspensão judicial (registrada no cadastro mobiliário)
  4 Simples Nacional (demais emissões do optante)
  5 Retido no Município (o tomador retém; obrigatório para a Prefeitura, fundos, COMDIT, BB e Caixa)
"""

from __future__ import annotations

ITABORAI = "3301900"

# 1.1 / 4.3 / 5.1 — itens cujo ISS é devido no local da prestação (podem ser tributados/retidos fora)
ITENS_LOCAL_PRESTACAO = {
    "03.04", "03.05", "07.02", "07.04", "07.05", "07.09", "07.10", "07.11", "07.12", "07.16", "07.17", "07.18",
    "07.19", "11.01", "11.02", "11.04", "12.01", "12.02", "12.03", "12.04", "12.05", "12.06", "12.07", "12.08",
    "12.09", "12.10", "12.11", "12.12", "12.14", "12.15", "12.16", "12.17", "16.01", "16.02", "17.05", "17.10",
    "20.01", "20.02", "20.03", "22.01",
}

# Tomadores que retêm o ISS obrigatoriamente (tipo 5), qualquer que seja o item
RETENCAO_OBRIGATORIA = {
    "28741080000155": "Prefeitura Municipal de Itaboraí",
    "11865033000110": "Fundo Municipal de Saúde de Itaboraí",
    "15184980000105": "Fundo de Assistência Social de Itaboraí",
    "15514275000110": "Fundo da Criança e do Adolescente de Itaboraí",
    "18946402000149": "Fundo Municipal do Meio Ambiente",
    "18946420000120": "Fundo Especial de Arrecadação da Procuradoria do Município de Itaboraí",
    "19004736000166": "Fundo Municipal de Trânsito",
    "19494733000158": "Fundo de Apoio ao Desporto e ao Lazer do Município de Itaboraí",
    "19534915000105": "Fundo Municipal de Iluminação Pública",
    "24322625000138": "Fundo Municipal de Habitação de Interesse Social",
    "31037687000163": "Fundo Municipal de Educação de Itaboraí",
    "39521310000197": "Fundo Municipal dos Direitos do Idoso de Itaboraí",
    "41331946000118": "Fundo Municipal do Trabalho de Itaboraí",
    "42780948000157": "Fundo Municipal de Economia Solidária",
    "43204519000102": "Fundo Municipal de Desenvolvimento Agropecuário",
    "43642167000169": "Fundo Municipal de Transportes de Itaboraí",
    "44032158000119": "Fundo Municipal de Turismo de Itaboraí",
    "44119354000125": "COMDIT – Companhia de Desenvolvimento de Itaboraí",
    "00000000117978": "Banco do Brasil S.A.",
    "00360305081198": "Caixa Econômica Federal",
    "00360305437634": "Caixa Econômica Federal",
}
# A Petrobras também consta na lista, mas o manual manda emitir pelas regras normais: o próprio webservice
# ajusta para "Retido no Município" quando o item permite (item 2 das observações).
PETROBRAS = "33000167012541"

# Desdobros que dispensam o endereço do imóvel (IBS/CBS) e códigos de operação que o exigem
DESDOBRO_SEM_IMOVEL = {"070201", "070202", "070401", "070501", "070502", "070601", "070602", "070701", "070801",
                       "071701", "071901"}
OPERACAO_COM_IMOVEL = {"020101", "020201", "020202", "020301", "020401"}
# Desdobros que exigem o grupo Evento
DESDOBRO_EVENTO = {"120101", "120201", "120301", "120401", "120501", "120601", "120701", "120801", "120901", "120902",
                   "120903", "121001", "121101", "121201", "121301", "121401", "121501", "121601", "121701"}
LIMITE_DEDUCAO_PCT = 40


def item(rps_item: str) -> str:
    d = "".join(c for c in str(rps_item or "") if c.isdigit())
    return f"{d[:2].zfill(2)}.{d[2:4]}" if len(d) >= 3 else ""


def tipo_tributacao(regime: str, item_lc: str, retido: bool, local_prestacao: str, local_recolhimento: str,
                    tomador: str, imune: bool = False, suspensa: bool = False,
                    casa: str = ITABORAI) -> tuple[str, bool, str]:
    """Devolve (tipo de tributação, ISS retido, local do recolhimento) conforme o manual.
    `casa` é o município da empresa emissora (multiempresa)."""
    casa = casa or ITABORAI
    local_prestacao = local_prestacao or casa
    local_recolhimento = local_recolhimento or casa
    obrigatoria = tomador in RETENCAO_OBRIGATORIA and casa == ITABORAI
    if suspensa:
        return "3", False, local_recolhimento
    if regime == "mei" or imune:
        return "2", False, casa
    if regime == "simples":
        if obrigatoria:
            return "5", True, casa
        if retido and local_recolhimento != casa:
            return "1", True, local_recolhimento
        if retido:
            return "5", True, casa
        return "4", False, casa
    # Lucro Presumido / Real
    if obrigatoria:
        return "5", True, casa
    if item(item_lc) in ITENS_LOCAL_PRESTACAO and local_prestacao != casa:
        return "1", retido, local_prestacao            # ISS devido no local da prestação (LC 116, art. 3º)
    if retido and local_recolhimento != casa:
        return "1", True, local_recolhimento
    if retido:
        return "5", True, casa
    return "0", False, casa


def validar(rps, regime: str) -> list[str]:
    """Regras do manual que o XSD não verifica (erros que fariam a prefeitura recusar o RPS)."""
    from .xml_rps import so_digitos
    erros: list[str] = []
    x = rps.extras or {}
    it, desd = item(rps.item_lista_servico), so_digitos(rps.codigo_desdobro)
    aliq = rps.aliquota_iss
    if regime == "simples" and rps.tipo_tributacao in ("1", "4", "5") and not (it == "17.19" and rps.tipo_tributacao == "4"):
        if not (2 <= aliq <= 5):
            erros.append("Simples Nacional: informe no serviço a alíquota EFETIVA do ISS contida no DAS (entre 2% e 5%), "
                         "como exige o manual do webservice de Itaboraí.")
    if regime in ("presumido", "real") and rps.tipo_tributacao in ("0", "1", "5") and aliq <= 0:
        erros.append("Lucro Presumido/Real: informe no serviço a alíquota do ISS da Tabela de Atividades do município.")
    if rps.valor_deducoes > 0:
        if not rps.codigo_obra.strip():
            erros.append("Dedução na base do ISS só é aceita com o Código da Obra cadastrado no módulo de Construção "
                         "Civil da prefeitura (6 caracteres).")
        if rps.valor_deducoes > rps.valor_servicos * LIMITE_DEDUCAO_PCT / 100:
            erros.append(f"Dedução limitada a {LIMITE_DEDUCAO_PCT}% do valor da nota (manual do webservice).")
    if so_digitos(rps.indicador_operacao) in OPERACAO_COM_IMOVEL and desd not in DESDOBRO_SEM_IMOVEL \
            and not (x.get("imovel_cep") and x.get("imovel_lgr")):
        erros.append("IBS/CBS: este Indicador de Operação exige o endereço do imóvel (Mais campos da nota › Imóvel).")
    if desd in DESDOBRO_EVENTO and not x.get("evento_nome"):
        erros.append("Este serviço (item 12) exige os dados do evento: nome, datas e endereço (Mais campos da nota › Evento).")
    t, e = rps.tomador, rps.tomador.endereco
    if len(so_digitos(t.cpf_cnpj)) == 14:
        faltam = [n for n, v in (("tipo de logradouro", e.tipo_logradouro), ("logradouro", e.logradouro),
                                 ("bairro", e.bairro), ("município", so_digitos(e.codigo_municipio)), ("UF", e.uf)) if not str(v).strip()]
        if faltam:
            erros.append("Tomador pessoa jurídica: preencha no cadastro do cliente " + ", ".join(faltam) + ".")
    return erros
