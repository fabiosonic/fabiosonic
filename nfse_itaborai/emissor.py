"""Orquestra: configuração, numeração de RPS/lote, validação, envio e arquivamento."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from . import cliente
from .modelos import Endereco, ItemServico, Prestador, Retencoes, Rps, Tomador
from .validacao import validar
from .xsd import validar_xsd
from .xml_rps import gerar_cancelamento, gerar_envio, so_digitos

FUSO = timezone(timedelta(hours=-3), "Brasilia")  # sem horário de verão desde 2019
RAIZ = Path(os.environ.get("ITABORAI_PASTA", Path.cwd()))


class ErroConfiguracao(Exception):
    pass


def carregar_env(caminho: Path | None = None) -> None:
    """Lê um arquivo .env simples (CHAVE=valor) sem sobrescrever variáveis já definidas."""
    caminho = caminho or RAIZ / ".env"
    if not caminho.exists():
        return
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        k, v = linha.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def prestador_do_ambiente() -> Prestador:
    carregar_env()
    faltando = [k for k in ("ITABORAI_CNPJ", "ITABORAI_IM", "ITABORAI_CHAVE") if not os.environ.get(k)]
    if faltando:
        raise ErroConfiguracao("Configure no arquivo .env: " + ", ".join(faltando) + " (veja .env.exemplo).")
    return Prestador(
        cnpj=so_digitos(os.environ["ITABORAI_CNPJ"]),
        inscricao_municipal=so_digitos(os.environ["ITABORAI_IM"]),
        chave_webservice=os.environ["ITABORAI_CHAVE"].strip(),
        inscricao_estadual=os.environ.get("ITABORAI_IE", ""),
        optante_simples=os.environ.get("ITABORAI_SIMPLES", "S").upper().startswith("S"),
        incentivo_fiscal=os.environ.get("ITABORAI_INCENTIVO", "N").upper().startswith("S"),
    )


def producao_autorizada(pedido_producao: bool) -> bool:
    """Produção só com o pedido explícito E a ciência registrada no .env."""
    if not pedido_producao:
        return False
    carregar_env()
    if os.environ.get("ITABORAI_AMBIENTE", "").lower() != "producao":
        raise ErroConfiguracao("Para emitir em produção defina ITABORAI_AMBIENTE=producao no .env.")
    if os.environ.get("ITABORAI_CIENTE_IRREVERSIVEL", "").upper() != "SIM":
        raise ErroConfiguracao(
            "A prefeitura avisa: iniciada a emissão via webservice, a emissão manual deixa de ser "
            "possível (irreversível). Se está ciente, defina ITABORAI_CIENTE_IRREVERSIVEL=SIM no .env.")
    return True


# ---------------------------------------------------------------- numeração

def _arquivo_sequencia() -> Path:
    return RAIZ / "dados" / "sequencia.json"


def _ler_sequencia() -> dict:
    """Usa o maior valor entre o .env e o controle local, para que ajustes no .env valham."""
    carregar_env()
    seq = {"proximo_rps": int(os.environ.get("ITABORAI_PROXIMO_RPS", "1")),
           "proximo_lote": int(os.environ.get("ITABORAI_PROXIMO_LOTE", "1"))}
    arq = _arquivo_sequencia()
    if arq.exists():
        salvo = json.loads(arq.read_text(encoding="utf-8"))
        # preserva outras numerações do arquivo (ex.: proximo_dps do canal nacional)
        seq = salvo | {k: max(v, int(salvo.get(k, 0))) for k, v in seq.items()}
    return seq


def _definir_proximo_rps(numero: int) -> None:
    seq = _ler_sequencia()
    seq["proximo_rps"] = numero
    _gravar_sequencia(seq)


# "Este Lote possui o número [3481] mas deveria ser [3509]"
_RPS_ESPERADO = re.compile(r"deveria ser \[(\d+)\]", re.IGNORECASE)


def rps_esperado(erros: list[str]) -> int | None:
    for e in erros:
        m = _RPS_ESPERADO.search(e)
        if m and "numero" in e.lower().replace("ú", "u"):
            return int(m.group(1))
    return None


def _gravar_sequencia(seq: dict) -> None:
    arq = _arquivo_sequencia()
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(seq, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- leitura do JSON

def _d(v) -> Decimal:
    return Decimal(str(v or 0).replace(",", ".")) if isinstance(v, str) else Decimal(str(v or 0))


def _data(v) -> date | None:
    if not v:
        return None
    v = str(v)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%Y", "%Y-%m"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida: {v}")


def rps_de_dict(d: dict) -> Rps:
    tom = d.get("tomador", {})
    end = tom.get("endereco", {})
    ret = d.get("retencoes", {})
    return Rps(
        numero=str(d.get("numero", "")),
        itens=[ItemServico(descricao=i["descricao"], valor_unitario=_d(i["valor_unitario"]),
                           quantidade=int(i.get("quantidade", 1))) for i in d.get("itens", [])],
        tomador=Tomador(
            cpf_cnpj=tom.get("cpf_cnpj", ""), razao_social=tom.get("razao_social", ""),
            inscricao_municipal=tom.get("inscricao_municipal", ""),
            inscricao_estadual=tom.get("inscricao_estadual", ""),
            telefone=tom.get("telefone", ""), email=tom.get("email", ""),
            endereco=Endereco(
                logradouro=end.get("logradouro", ""), numero=str(end.get("numero", "")),
                bairro=end.get("bairro", ""), codigo_municipio=str(end.get("codigo_municipio", "")),
                uf=end.get("uf", ""), cep=end.get("cep", ""),
                tipo_logradouro=end.get("tipo_logradouro", ""), complemento=end.get("complemento", ""),
                codigo_pais=int(end.get("codigo_pais", 1058)))),
        item_lista_servico=str(d.get("item_lista_servico", "")),
        codigo_nbs=str(d.get("codigo_nbs", "")),
        codigo_desdobro=str(d.get("codigo_desdobro", "")),
        cnae=str(d.get("cnae", "")),
        aliquota_iss=_d(d.get("aliquota_iss", 0)),
        tipo_tributacao=str(d.get("tipo_tributacao", "4")),
        iss_retido=str(d.get("iss_retido", "2")),
        responsavel_recolhimento=str(d.get("responsavel_recolhimento", "")),
        indicador_operacao=str(d.get("indicador_operacao", "")),
        classificacao_tributaria=str(d.get("classificacao_tributaria", "")),
        competencia=_data(d.get("competencia")),
        local_prestacao=str(d.get("local_prestacao", "3301900")),
        local_recolhimento=str(d.get("local_recolhimento", "3301900")),
        codigo_obra=str(d.get("codigo_obra", "")),
        codigo_tributacao_municipio=str(d.get("codigo_tributacao_municipio", "")),
        valor_deducoes=_d(d.get("valor_deducoes")),
        desconto_incondicionado=_d(d.get("desconto_incondicionado")),
        desconto_condicionado=_d(d.get("desconto_condicionado")),
        retencoes=Retencoes(**{k: _d(v) for k, v in ret.items()}),
        valor_total_tributos=_d(d.get("valor_total_tributos")),
        observacoes=d.get("observacoes", ""),
    )


# ---------------------------------------------------------------- operações

def _pasta_saida(rps_numero: str) -> Path:
    p = RAIZ / "saida" / datetime.now(FUSO).strftime("%Y-%m") / f"RPS_{rps_numero}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def preparar(rps: Rps, prestador: Prestador, producao: bool) -> tuple[str, str, list[str]]:
    """Numera (se preciso), valida e gera o XML. Devolve (xml, lote, alertas)."""
    agora = datetime.now(FUSO).replace(tzinfo=None, microsecond=0)
    rps.data_emissao = rps.data_emissao or agora
    seq = _ler_sequencia()
    if not so_digitos(rps.numero):
        rps.numero = str(seq["proximo_rps"])
    lote = str(seq["proximo_lote"])
    alertas = validar(rps)
    xml = gerar_envio(prestador, [rps], lote=lote, producao=producao, agora=agora)
    validar_xsd(xml)
    return xml, lote, alertas


def _avancar_sequencia(lote: str, rps_numero: str | None) -> None:
    """O lote avança a cada envio; o número do RPS só quando vira NFS-e em produção."""
    seq = _ler_sequencia()
    seq["proximo_lote"] = max(seq["proximo_lote"], int(lote) + 1)
    if rps_numero:
        seq["proximo_rps"] = max(seq["proximo_rps"], int(so_digitos(rps_numero)) + 1)
    _gravar_sequencia(seq)


def emitir(rps: Rps, producao: bool = False, url: str = cliente.URL_WEBSERVICE) -> cliente.Resposta:
    prestador = prestador_do_ambiente()
    producao = producao_autorizada(producao)
    numero_automatico = not so_digitos(rps.numero)
    resp = _enviar(rps, prestador, producao, url)
    # A prefeitura informa o RPS esperado; com numeração automática, corrige e reenvia uma vez.
    esperado = rps_esperado(resp.erros)
    if esperado and numero_automatico and str(esperado) != rps.numero:
        _definir_proximo_rps(esperado)
        anterior = rps.numero
        rps.numero = ""
        resp = _enviar(rps, prestador, producao, url)
        resp.alertas.insert(0, f"Numeração ajustada: a prefeitura esperava o RPS {esperado} "
                               f"(o controle local estava em {anterior}). Reenviado automaticamente.")
    return resp


def _enviar(rps: Rps, prestador: Prestador, producao: bool, url: str) -> cliente.Resposta:
    xml, lote, alertas = preparar(rps, prestador, producao)
    pasta = _pasta_saida(rps.numero)
    (pasta / "envio.xml").write_text(xml, encoding="utf-8")
    status, retorno = cliente.postar(xml, f"{lote}-env-lot.xml", url=url)
    (pasta / "retorno.xml").write_text(retorno, encoding="utf-8")
    resp = cliente.interpretar_emissao(xml, status, retorno)
    # Homologação não consome a numeração real de RPS
    _avancar_sequencia(lote, rps.numero if resp.sucesso and producao else None)
    for nota in resp.notas:
        if nota.xml:
            (pasta / f"NFSe_{nota.numero_nfse or rps.numero}.xml").write_text(nota.xml, encoding="utf-8")
    (pasta / "resumo.json").write_text(json.dumps({
        "ambiente": "producao" if producao else "homologacao", "lote": lote, "rps": rps.numero,
        "sucesso": resp.sucesso, "erros": resp.erros, "alertas": alertas,
        "notas": [asdict(n) | {"xml": None} for n in resp.notas],
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    resp.alertas = alertas
    resp.pasta = str(pasta)
    return resp


def cancelar(numero_nfse: str, justificativa: str, producao: bool = False,
             url: str = cliente.URL_WEBSERVICE) -> cliente.Resposta:
    if len(justificativa.strip()) < 15:
        raise ValueError("Justificativa do cancelamento deve ter ao menos 15 caracteres.")
    prestador = prestador_do_ambiente()
    producao = producao_autorizada(producao)
    agora = datetime.now(FUSO).replace(tzinfo=None, microsecond=0)
    xml = gerar_cancelamento(prestador, numero_nfse, justificativa, producao, agora=agora)
    pasta = RAIZ / "saida" / agora.strftime("%Y-%m") / f"CANCELAMENTO_{so_digitos(numero_nfse)}"
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "envio.xml").write_text(xml, encoding="utf-8")
    status, retorno = cliente.postar(xml, f"{so_digitos(numero_nfse)}-ped-can.xml", url=url)
    (pasta / "retorno.xml").write_text(retorno, encoding="utf-8")
    resp = cliente.interpretar_cancelamento(xml, status, retorno)
    resp.pasta = str(pasta)
    return resp


# ---------------------------------------------------------------- ambiente (tela)

def em_producao() -> bool:
    carregar_env()
    return (os.environ.get("ITABORAI_AMBIENTE", "").lower() == "producao"
            and os.environ.get("ITABORAI_CIENTE_IRREVERSIVEL", "").upper() == "SIM")


def definir_ambiente(producao: bool) -> None:
    """Grava ITABORAI_AMBIENTE / ITABORAI_CIENTE_IRREVERSIVEL no .env e no processo atual."""
    valores = {"ITABORAI_AMBIENTE": "producao" if producao else "homologacao",
               "ITABORAI_CIENTE_IRREVERSIVEL": "SIM" if producao else "NAO"}
    arq = RAIZ / ".env"
    linhas = arq.read_text(encoding="utf-8").splitlines() if arq.exists() else []
    feitas = set()
    for i, linha in enumerate(linhas):
        chave = linha.split("=", 1)[0].strip()
        if chave in valores:
            linhas[i] = f"{chave}={valores[chave]}"
            feitas.add(chave)
    linhas += [f"{k}={v}" for k, v in valores.items() if k not in feitas]
    arq.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    os.environ.update(valores)
