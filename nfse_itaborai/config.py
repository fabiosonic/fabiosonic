"""Configurações do sistema (dados/config.json, fora do Git — contém senhas e chaves)."""

from __future__ import annotations

import copy
import json

from . import emissor, segredos

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
        "recorrente_ativa": True,   # cobrança recorrente dos atrasados (além das etapas fixas da régua)
        "recorrente_apos_dias": 5,  # começa N dias após o vencimento original
        "recorrente_a_cada_dias": 7,  # e repete a cada X dias enquanto não pagar
        "regua_email": True,
        "regua_whatsapp": True,
        # envios (e-mail e WhatsApp) só em horário comercial: segunda a sexta, entre as horas abaixo
        "envio_horario_comercial": True,
        "enviar_ao_gerar": True,        # manda o boleto assim que a cobrança é gerada (e-mail e WhatsApp, conforme a régua)
        "agradecer_pagamento": True,    # pagamento reconhecido: mensagem de agradecimento
        "enviar_nfse_paga": True,       # depois do agradecimento, envia a NFS-e emitida (link e XML no e-mail)
        "envio_hora_inicio": "08:00",
        "envio_hora_fim": "18:00",
        "anexar_boleto": True,      # e-mails de cobrança levam o PDF do boleto anexado
        "pix_nas_mensagens": False,     # PIX copia e cola no texto mesmo com o boleto (que já traz o QR Code) junto
        "bloquear_apos_dias": 60,   # alerta de cliente para suspensão/negociação
        # WhatsApp automático pelo WhatsApp Web do escritório (QR Code lido uma vez; sem API oficial)
        "whatsapp_web": False,          # liga sozinho quando o QR Code é lido em Configurações › WhatsApp
        "whatsapp_web_intervalo": 15,   # segundos (em média) entre uma mensagem e outra
        "whatsapp_web_limite": 40,      # máximo de mensagens por rodada do robô
        "whatsapp_web_visivel": False,  # mostrar a janela do navegador durante o envio
        "whatsapp_web_pdf": True,       # manda também o boleto em PDF (documento) logo depois da mensagem
        "whatsapp_web_navegador": "",   # caminho do navegador (vazio = Edge ou Chrome instalados)
        # WhatsApp pela API oficial da Meta (Cloud API): a régua envia sozinha, com modelos aprovados
        "whatsapp_api": False,      # desligado = fila com o link "Enviar" (envio manual pelo WhatsApp do escritório)
        "whatsapp_token": "",       # token permanente (usuário do sistema no Gerenciador de Negócios)
        "whatsapp_phone_id": "",    # ID do número de telefone (WhatsApp Manager › API)
        "whatsapp_idioma": "pt_BR",
        "whatsapp_modelo_lembrete": "cobranca_lembrete",
        "whatsapp_modelo_hoje": "cobranca_vence_hoje",
        "whatsapp_modelo_atraso": "cobranca_atraso",
        # cartão de crédito (InfinitePay): link por título; as taxas do cartão ficam sempre por conta do cliente
        "cartao_provedor": "",      # "" desligado | infinitepay
        "cartao_infinitepay_tag": "",  # InfiniteTag da conta (no app, canto superior esquerdo, sem o $)
        "cartao_oferecer": True,    # mensagens de cobrança levam o link "pagar com cartão"
        "cartao_taxa_1x": 4.20,     # % no crédito à vista — confira a SUA taxa no app da InfinitePay e ajuste
        "cartao_taxa_fixa": 0.0,    # R$ fixo por venda, se houver
    },
    "financeiro": {
        "dia_vencimento_padrao": 10,
        "prazo_avulso_dias": 5,     # vencimento de nota avulsa = emissão + N dias
        "inicio_financeiro": "",    # notas externas a partir desta data viram contas a receber (definido no 1º uso)
        "dia_geracao": 1,           # dia do mês em que a recorrência gera os títulos
        "aliquota_simples_pct": 3.99,  # usada só sem histórico; com histórico calcula pelo RBT12 (Anexo III)
        "das_mei_mensal": "",       # MEI: valor do DAS-MEI do mês (INSS + ISS), para a DRE
        "presuncao_pct": "32",      # Lucro Presumido: presunção do IRPJ/CSLL para serviços (32%)
        "iss_fixo_mensal": 0,       # ISS fixo pago à prefeitura por mês (R$), dedução na DRE quando não houver lançamento
        "iss_fixo": True,           # escritório contábil: ISS fixo fora do DAS (LC 123, art. 18, § 22-A)
        "extrato_inter_ate": "",    # último dia já baixado pela API de extrato do Inter
        "contas_bancarias": [],     # contas (banco-agência-conta) dos extratos desta empresa; preenchida no 1º OFX
        "categorias_despesa": ["Aluguel", "Folha", "Pró-labore", "Impostos", "Sistemas", "Energia/Internet",
                               "Contador/Assessoria", "Marketing", "Bancárias", "Outras"],
    },
    "decimo_terceiro": {            # 13º honorário: cobrado de cada contrato ativo no fim do ano
        "ativo": True,
        "parcelas": [{"percentual": 50, "vencimento": "30/11"}, {"percentual": 50, "vencimento": "20/12"}],
        "emitir_nfse": True,
        "descricao": "13º HONORÁRIO",
    },
    "pastas": {
        "xml_nfse": "",             # vazio = IMPORTAR XML/importados/<CNPJ> (dentro da pasta do sistema)
        "extratos": "~/Downloads",  # o robô importa todo .ofx novo que aparecer aqui
        "relatorios": "~/Downloads/Relatorios financeiros",  # fechamentos mensais em HTML (abrir/imprimir/PDF)
        "boletos": "~/Downloads/Boletos",
        "backup_copia": "",  # segunda cópia dos backups (pendrive, HD externo, pasta sincronizada); vazio = só local  # PDF + dados de pagamento de cada boleto, em subpastas AAAA-MM
    },
    "fiscal": {                     # regra geral (cada tomador pode ter a sua: cadastro do cliente)
        "regime": "",               # mei | simples | presumido | real ("" = pelo opSimpNac antigo)
        "iss_retido": False, "aliquota_iss_retido": "",
        "ret_irrf_pct": "0", "ret_pis_pct": "0", "ret_cofins_pct": "0", "ret_csll_pct": "0", "ret_inss_pct": "0",
        "ibscbs": "auto",           # auto (regime regular já; Simples/MEI a partir de 2027) | sempre | nunca
        "ind_final": "auto",        # auto (CPF = consumo pessoal) | 0 | 1
        # avançados: carga aproximada, PIS/COFINS próprio e IBS/CBS (tributação regular, diferimento, crédito presumido)
        "tot_trib_modo": "auto", "p_tot_fed": "", "p_tot_est": "", "p_tot_mun": "", "pis_cofins_cst": "",
        "p_pis": "", "p_cofins": "", "cst_reg": "", "class_trib_reg": "", "c_cred_pres": "",
        "p_dif_uf": "", "p_dif_mun": "", "p_dif_cbs": "",
        "lido_dos_xml": False,
        "incentivo_fiscal": "",     # webservice de Itaboraí: IncentivoFiscalImunidade (sim | imune | nao | "" = .env)
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
        # regra geral da NFS-e (a recorrência do cliente pode ter regra própria, que vale primeiro):
        # geracao = emite ao gerar o contas a receber | baixa = emite ao dar baixa (pagamento confirmado)
        # lancar = só lança o contas a receber, sem NFS-e | nada = não emite e não lança (recorrência)
        "nfse_quando": "",
        "nfse_apos_pagamento": False,  # legado: equivale a nfse_quando = "baixa"
        "migrado_regra_baixa": True,   # configuração já gravada nesta versão: não muda a regra escolhida
    },
    # senha que protege os backups (vazia = backup .zip comum); guardada protegida, como as demais senhas
    "seguranca": {"backup_senha": ""},
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
        "extrato_inter": True,      # baixa o extrato do Inter pela API (escopo extrato.read) e concilia
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


SEGREDOS = (("smtp", "senha"), ("cobranca", "inter_client_secret"), ("emissao", "certificado_senha"),
            ("seguranca", "backup_senha"), ("cobranca", "whatsapp_token"))


def _arquivo():
    return emissor.RAIZ / "dados" / "config.json"


def _mesclar(base: dict, extra: dict) -> dict:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _mesclar(base[k], v)
        else:
            base[k] = v
    return base


CNPJ_REGRA_BAIXA = {"24875410000144"}     # Moraes & Oliveira Contabilidade: NFS-e só na baixa


def _cnpj_da_pasta(arq=None) -> str:
    """CNPJ da empresa ativa (dona desta configuração), lido do .env da empresa como faz o emissor."""
    try:
        return "".join(ch for ch in str(emissor.env("ITABORAI_CNPJ") or "") if ch.isdigit())
    except Exception:  # noqa: BLE001 — sem .env legível, nenhuma regra é trocada
        return ""


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
        # v3.4.4 (pedido do escritório): na Moraes & Oliveira a NFS-e só sai na baixa (pagamento reconhecido ou
        # baixa manual). Muda uma única vez e só nela; as demais empresas mantêm a regra de cada uma.
        emi = salvo.setdefault("emissao", {})
        if not emi.get("migrado_regra_baixa"):
            if _cnpj_da_pasta(arq) in CNPJ_REGRA_BAIXA:
                emi.update(nfse_quando="baixa", nfse_apos_pagamento=True)
            emi["migrado_regra_baixa"] = True
            arq.write_text(json.dumps(salvo, indent=2, ensure_ascii=False), encoding="utf-8")
        # XML das notas: passa a ser lido da pasta do sistema (IMPORTAR XML), não mais de Downloads
        if "downloads" in str(salvo.get("pastas", {}).get("xml_nfse", "")).lower():
            salvo["pastas"]["xml_nfse"] = ""
            arq.write_text(json.dumps(salvo, indent=2, ensure_ascii=False), encoding="utf-8")
        # sem serviços de terceiros: remove configurações antigas de WhatsApp por API e consulta à Receita
        removidos = [salvo.pop("whatsapp", None), salvo.get("automacao", {}).pop("enriquecer_contatos", None)]
        if any(r is not None for r in removidos):
            arq.write_text(json.dumps(salvo, indent=2, ensure_ascii=False), encoding="utf-8")
        _mesclar(cfg, salvo)
    for sec, campo in SEGREDOS:          # senhas ficam protegidas no disco e abertas só na memória
        cfg[sec][campo] = segredos.revelar(cfg[sec].get(campo, ""))
    return cfg


def salvar(novo: dict) -> dict:
    cfg = _mesclar(carregar(), novo)
    arq = _arquivo()
    arq.parent.mkdir(parents=True, exist_ok=True)
    disco = copy.deepcopy(cfg)
    for sec, campo in SEGREDOS:
        disco[sec][campo] = segredos.proteger(disco[sec].get(campo, ""))
    arq.write_text(json.dumps(disco, indent=2, ensure_ascii=False), encoding="utf-8")
    return cfg


def publico(cfg: dict | None = None) -> dict:
    """Cópia para a tela, sem expor senhas (mostra só se estão preenchidas)."""
    c = copy.deepcopy(cfg or carregar())
    from .fiscal import regime
    c["fiscal"]["regime"] = regime(c)          # tela sempre mostra o regime em vigor (nunca um padrão enganoso)
    for sec, campo in SEGREDOS:
        c[sec][campo] = "••••••" if c[sec].get(campo) else ""
    return c


def salvar_da_tela(novo: dict) -> dict:
    """Salva o que veio da tela, mantendo senhas quando o campo vier mascarado."""
    reg = (novo.get("fiscal") or {}).get("regime")
    if reg in ("mei", "simples", "presumido", "real"):   # o regime define a situação no Simples da DPS
        novo.setdefault("emissao", {})["op_simp_nac"] = {"mei": "2", "simples": "3"}.get(reg, "1")
    for sec, campo in SEGREDOS:
        if novo.get(sec, {}).get(campo) == "••••••":
            novo[sec].pop(campo)
    bs = (novo.get("seguranca") or {}).get("backup_senha")
    if bs and len(bs) < 6:
        raise ValueError("A senha do backup precisa ter ao menos 6 caracteres.")
    return publico(salvar(novo))
