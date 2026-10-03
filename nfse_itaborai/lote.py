"""Emissão simplificada: cliente do cadastro + valor (+ descrição opcional), uma nota ou em lote."""

from __future__ import annotations

from decimal import Decimal

from . import clientes, emissor, nacional, servicos
from .validacao import ErroValidacao

def servico_padrao() -> dict:
    """Serviço padrão da empresa em uso (compatibilidade: o catálogo completo está em servicos.py)."""
    return servicos.padrao()


def montar_rps(cpf_cnpj: str, valor, descricao: str = "", competencia: str = "", servico_id: str = "") -> dict:
    """Dicionário de RPS pronto para emissor.rps_de_dict, a partir do cadastro e do serviço escolhido
    (sem escolha: o serviço habitual do cliente; sem esse: o padrão da empresa)."""
    cli = clientes.obter(cpf_cnpj)
    if not cli:
        raise ValueError(f"Cliente {cpf_cnpj} não está no cadastro.")
    p = servicos.obter(servico_id or cli.get("servico_id"))
    v = Decimal(str(valor).replace(".", "").replace(",", ".")) if "," in str(valor) else Decimal(str(valor))
    if v <= 0:
        raise ValueError("Valor deve ser maior que zero.")
    pct = str(p.get("ibpt_percentual") or "0").replace(",", ".")
    ibpt = (v * Decimal(pct) / 100).quantize(Decimal("0.01"))
    from . import fiscal
    return fiscal.aplicar({
        "numero": "", "competencia": competencia,
        "itens": [{"descricao": (descricao or p["descricao"]).strip(), "quantidade": 1, "valor_unitario": str(v)}],
        **{k: p[k] for k in ("item_lista_servico", "codigo_nbs", "codigo_desdobro", "cnae", "aliquota_iss",
                             "tipo_tributacao", "iss_retido", "indicador_operacao", "classificacao_tributaria",
                             "observacoes")},
        "valor_total_tributos": str(ibpt),
        "tomador": clientes.para_dict_tomador(cli),
        # local da prestação e do recolhimento: município da empresa emissora (multiempresa)
        "local_prestacao": _municipio(), "local_recolhimento": _municipio(),
    }, cli)


def _municipio() -> str:
    from . import config
    return clientes._digitos(config.carregar()["emissao"].get("municipio_emissor")) or "3301900"


def emitir_um(cpf_cnpj: str, valor, descricao: str = "", producao: bool = False, url: str | None = None,
              canal: str | None = None, servico_id: str = "") -> dict:
    """Emite pelo canal escolhido em Configurações > Emissão: municipal (Itaboraí) ou nacional (nfse.gov.br)."""
    canal = canal or nacional.canal()
    cli = clientes.obter(cpf_cnpj) or {}
    base = {"cpf_cnpj": cpf_cnpj, "cliente": cli.get("razao_social", cpf_cnpj), "valor": str(valor), "canal": canal}
    try:
        dados = montar_rps(cpf_cnpj, valor, descricao, servico_id=servico_id)
        alertas_fiscais = dados.pop("_alertas_fiscais", [])
        rps = emissor.rps_de_dict(dados)
        kw = {"url": url} if url else {}
        resp = (nacional.emitir if canal == "nacional" else emissor.emitir)(rps, producao=producao, **kw)
    except ErroValidacao as ex:
        return base | {"sucesso": False, "erros": ex.erros}
    except (ValueError, emissor.ErroConfiguracao) as ex:
        return base | {"sucesso": False, "erros": [str(ex)]}
    except OSError as ex:
        return base | {"sucesso": False, "erros": [f"Falha de comunicação: {ex}"]}
    nota = resp.notas[0] if resp.notas else None
    return base | {"sucesso": resp.sucesso, "erros": resp.erros, "alertas": alertas_fiscais + list(resp.alertas),
                   "pasta": resp.pasta,
                   "rps": nota.numero_rps if nota else "", "nfse": nota.numero_nfse if nota else "",
                   "link": nota.link if nota else "",
                   "chave": nota.codigo_verificacao if nota and canal == "nacional" else ""}


def emitir_lote(itens: list[dict], producao: bool = False, url: str | None = None) -> list[dict]:
    """itens: [{"cpf_cnpj": ..., "valor": ..., "descricao": opcional}] — emite em sequência."""
    vistos, resultado = set(), []
    for it in itens:
        chave = (clientes._digitos(it.get("cpf_cnpj")), str(it.get("valor")), it.get("descricao", ""))
        if chave in vistos:
            resultado.append({"cpf_cnpj": it.get("cpf_cnpj"), "valor": str(it.get("valor")), "sucesso": False,
                              "cliente": (clientes.obter(it.get("cpf_cnpj", "")) or {}).get("razao_social", ""),
                              "erros": ["Ignorada: duplicada no mesmo lote (mesmo cliente, valor e descrição)."]})
            continue
        vistos.add(chave)
        resultado.append(emitir_um(it.get("cpf_cnpj", ""), it.get("valor", 0), it.get("descricao", ""),
                                   producao=producao, url=url, servico_id=it.get("servico_id", "")))
    return resultado
