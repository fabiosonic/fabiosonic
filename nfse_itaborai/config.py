"""Configurações do sistema (dados/config.json, fora do Git — contém senhas e chaves)."""

from __future__ import annotations

import copy
import json

from . import emissor

PADRAO = {
    "empresa": {
        "nome": "MORAES & OLIVEIRA CONTABILIDADE",
        "pix_chave": "",            # chave PIX que recebe (CNPJ, e-mail, telefone ou aleatória)
        "pix_cidade": "ITABORAI",
        "whatsapp": "",             # número do escritório, aparece nas mensagens
        "assinatura": "Moraes & Oliveira Contabilidade",
    },
    "smtp": {"host": "", "porta": 587, "usuario": "", "senha": "", "remetente": "", "ssl": False,
             "copia_para": ""},
    "cobranca": {
        "provedor": "inter",        # inter (boleto + PIX registrados na API do Banco Inter) | pix (copia e cola próprio) | nenhum
        "inter_client_id": "",
        "inter_client_secret": "",
        "inter_certificado": "",    # arquivo .crt gerado na integração do Inter
        "inter_chave": "",          # arquivo .key gerado na integração do Inter
        "inter_conta": "",          # nº da conta corrente (só se houver mais de uma)
        "inter_sandbox": False,
        "inter_dias_agenda": 60,    # dias após o vencimento em que o banco ainda aceita o pagamento (máx. 60)
        "multa_pct": 2.0,
        "juros_mes_pct": 1.0,
        "regua_dias": [-3, 0, 1, 5, 15, 30],
        "regua_email": True,
        "regua_whatsapp": True,
        "anexar_boleto": True,      # e-mails de cobrança levam o PDF do boleto anexado
        "bloquear_apos_dias": 60,   # alerta de cliente para suspensão/negociação
    },
    "financeiro": {
        "dia_vencimento_padrao": 10,
        "prazo_avulso_dias": 5,     # vencimento de nota avulsa = emissão + N dias
        "inicio_financeiro": "",    # notas externas a partir desta data viram contas a receber (definido no 1º uso)
        "dia_geracao": 1,           # dia do mês em que a recorrência gera os títulos
        "aliquota_simples_pct": 3.99,  # usada só sem histórico; com histórico calcula pelo RBT12 (Anexo III)
        "iss_fixo_mensal": 0,       # ISS fixo pago à prefeitura por mês (R$), dedução na DRE quando não houver lançamento
        "iss_fixo": True,           # escritório contábil: ISS fixo fora do DAS (LC 123, art. 18, § 22-A)
        "categorias_despesa": ["Aluguel", "Folha", "Pró-labore", "Impostos", "Sistemas", "Energia/Internet",
                               "Contador/Assessoria", "Marketing", "Bancárias", "Outras"],
    },
    "pastas": {
        "xml_nfse": "~/Downloads/nfse/MORAES OLIVEIRA CONTABILIDADE LTDA",  # XML das notas já emitidas
        "extratos": "~/Downloads",  # o robô importa todo .ofx novo que aparecer aqui
        "relatorios": "~/Downloads/Relatorios financeiros",  # fechamentos mensais em HTML (abrir/imprimir/PDF)
        "boletos": "~/Downloads/Boletos",  # PDF + dados de pagamento de cada boleto, em subpastas AAAA-MM
    },
    "emissao": {
        "canal": "municipal",       # municipal (webservice de Itaboraí) | nacional (Emissor Nacional, nfse.gov.br)
        "certificado_pfx": "",      # certificado A1 do escritório (.pfx) — exigido só no canal nacional
        "certificado_senha": "",
        "serie_dps": "900",         # série própria das DPS enviadas por este sistema
        "proximo_dps": 1,           # numeração da DPS (independente do RPS municipal)
        "municipio_emissor": "3301900",
        "op_simp_nac": "3",         # 1 não optante | 2 MEI | 3 ME/EPP
        "reg_ap_trib_sn": "2",      # 1 tudo no DAS | 2 federais no DAS e ISS fora (ISS fixo) | 3 tudo fora
        "reg_esp_trib": "6",        # 0 nenhum | 6 sociedade de profissionais (confirmar no cadastro municipal)
        "informar_im": False,       # IM só quando o município tem cadastro no Sistema Nacional
        "informar_ibscbs": True,    # grupo IBS/CBS (LC 214/2025) com cIndOp/cClassTrib do serviço padrão
    },
    "resumo": {"email_dono": "", "ultimo_envio": "", "dia_fechamento": 3, "ultimo_fechamento": ""},
    "regras_despesa": [             # palavra no histórico do extrato -> categoria
        ["DAS", "Impostos"], ["DARF", "Impostos"], ["GPS", "Impostos"], ["FGTS", "Folha"], ["SIMPLES", "Impostos"],
        ["TARIFA", "Bancárias"], ["TAR ", "Bancárias"], ["IOF", "Bancárias"], ["PACOTE", "Bancárias"],
        ["ENEL", "Energia/Internet"], ["LIGHT", "Energia/Internet"], ["VIVO", "Energia/Internet"],
        ["CLARO", "Energia/Internet"], ["OI ", "Energia/Internet"], ["ALUGUEL", "Aluguel"], ["CONDOMINIO", "Aluguel"],
        ["SALARIO", "Folha"], ["PRO LABORE", "Pró-labore"], ["PROLABORE", "Pró-labore"], ["DOMINIO", "Sistemas"],
        ["THOMSON", "Sistemas"], ["GOOGLE", "Sistemas"], ["MICROSOFT", "Sistemas"],
    ],
    "automacao": {
        "ativa": True,              # liga o robô (só emite NFS-e em produção)
        "importar_xml": True,       # clientes, contratos detectados e notas emitidas fora do sistema
        "importar_extratos": True,  # importa .ofx novos da pasta de extratos
        "despesas_do_extrato": True,  # débitos sem conta a pagar viram despesa paga, classificada por regra
        "resumo_diario": True,      # e-mail diário com o resumo para o dono
        "fechamento_mensal": True,  # relatório gerencial do mês anterior (DRE, indicadores, aging), salvo e enviado
        "gerar_titulos": True,
        "emitir_nfse": True,
        "criar_cobranca": True,
        "baixar_boletos": True,     # salva o PDF de cada boleto na pasta de boletos
        "regua": True,
        "sincronizar_banco": True,  # baixa automática dos boletos pagos (consulta no Inter)
        "despesas_recorrentes": True,
        "backup": True,
    },
}


SEGREDOS = (("smtp", "senha"), ("cobranca", "inter_client_secret"), ("emissao", "certificado_senha"))


def _arquivo():
    return emissor.RAIZ / "dados" / "config.json"


def _mesclar(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v
    return base


def carregar() -> dict:
    cfg = copy.deepcopy(PADRAO)
    arq = _arquivo()
    if arq.exists():
        salvo = json.loads(arq.read_text(encoding="utf-8"))
        # versões anteriores usavam Asaas ou só PIX: a cobrança passa a ser boleto+PIX direto no Banco Inter
        cob = salvo.get("cobranca", {})
        if not cob.get("migrado_inter"):
            if cob.get("provedor") in ("asaas", "pix"):
                cob["provedor"] = "inter"
            for k in [k for k in cob if k.startswith("asaas")]:
                cob.pop(k)
            cob["migrado_inter"] = True
            salvo["cobranca"] = cob
            arq.write_text(json.dumps(salvo, indent=2, ensure_ascii=False), encoding="utf-8")
        # sem serviços de terceiros: remove configurações antigas de WhatsApp por API e consulta à Receita
        removidos = [salvo.pop("whatsapp", None), salvo.get("automacao", {}).pop("enriquecer_contatos", None)]
        if any(r is not None for r in removidos):
            arq.write_text(json.dumps(salvo, indent=2, ensure_ascii=False), encoding="utf-8")
        _mesclar(cfg, salvo)
    return cfg


def salvar(novo: dict) -> dict:
    cfg = _mesclar(carregar(), novo)
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def publico(cfg: dict | None = None) -> dict:
    """Cópia para a tela, sem expor senhas (mostra só se estão preenchidas)."""
    c = copy.deepcopy(cfg or carregar())
    for sec, campo in SEGREDOS:
        c[sec][campo] = "••••••" if c[sec].get(campo) else ""
    return c


def salvar_da_tela(novo: dict) -> dict:
    """Salva o que veio da tela, mantendo senhas quando o campo vier mascarado."""
    for sec, campo in SEGREDOS:
        if novo.get(sec, {}).get(campo) == "••••••":
            novo[sec].pop(campo)
    return publico(salvar(novo))
