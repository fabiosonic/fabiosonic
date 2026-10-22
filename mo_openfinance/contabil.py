"""
Transações Open Finance → partidas contábeis (D/C) → TXT de importação de lançamentos do Domínio.

Diferença para o fluxo OFX (mo_dominio/lancamentos.py): o Open Finance traz CPF/CNPJ da contraparte e o
detalhe do boleto. Isso permite regras por documento, mais estáveis que regras por texto do histórico:

ordem de decisão (a primeira que resolver vence)
  1. contraparte = CNPJ da própria empresa         → transferência entre contas próprias (conta ponte)
  2. contraparte = CPF de sócio cadastrado          → PENDÊNCIA obrigatória (pró-labore? lucros? mútuo? AFAC?
                                                      cada um tem efeito tributário diferente; ninguém adivinha)
  3. contraparte em `documentos` (cliente/fornecedor com conta própria no plano)
  4. regras por texto/categoria (`regras`, mesmo formato do depara do OFX)
  5. entrada de CNPJ não cadastrado → `conta_clientes`; saída → `conta_fornecedores` (se configuradas)
  6. nada casou → conta transitória + pendência

Boleto pago com juros/multa/desconto informados é desdobrado (principal na contrapartida, juros e multa
em despesa financeira, desconto em receita financeira), desde que principal + juros + multa − desconto
feche com o valor debitado. Se não fechar, não desdobra e aponta pendência.

Cartão de crédito: a "conta banco" do cartão deve ser o passivo Cartão de crédito a pagar; a compra é
D despesa / C cartão (competência pela data da compra) e o pagamento da fatura, no extrato BANK, é
D cartão / C banco (regra por documento do emissor).
"""
import calendar
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from .modelo import Transacao, so_digitos


def normalizar(s):
    """Mesma normalização de texto do importador OFX (mo_dominio), sem depender daquele pacote."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().upper()


@dataclass
class Partida:
    data: str
    debito: str
    credito: str
    valor: Decimal
    historico: str
    complemento: str
    transacao: str
    pendente: str = ""      # motivo, quando caiu em conta transitória ou precisa de revisão


class Configuracao:
    """Configuração por empresa (JSON). Ver exemplos/openfinance/config_empresa.json."""

    def __init__(self, dados):
        self.cnpj = so_digitos(dados["cnpj"])
        self.contas_banco = {k: str(v) for k, v in dados["contas_banco"].items()}
        self.transitoria = str(dados["conta_transitoria"])
        self.transferencias = str(dados.get("conta_transferencias") or self.transitoria)
        self.socios = {so_digitos(c) for c in dados.get("socios_cpf", [])}
        self.documentos = {so_digitos(k): str(v) for k, v in dados.get("documentos", {}).items()}
        self.conta_clientes = str(dados.get("conta_clientes") or "")
        self.conta_fornecedores = str(dados.get("conta_fornecedores") or "")
        c = dados.get("contas", {})
        self.juros = str(c.get("juros_pagos") or self.transitoria)
        self.multas = str(c.get("multas_pagas") or self.juros)
        self.descontos = str(c.get("descontos_obtidos") or self.transitoria)
        self.historicos = dados.get("historicos", {})
        self.regras = []
        for r in dados.get("regras", []):
            alvo = r["padrao"]
            casa = re.compile(alvo[3:], re.I).search if alvo.lower().startswith("re:") else \
                (lambda txt, p=normalizar(alvo): p in normalizar(txt))
            self.regras.append({**r, "casa": casa, "sentido": (r.get("sentido") or "*").upper()[:1],
                                "conta": str(r["conta"])})

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, encoding="utf-8") as fh:
            return cls(json.load(fh))


def _hist(cfg, chave):
    return str(cfg.historicos.get(chave, ""))


def _contrapartida(t, cfg):
    """Devolve (conta, motivo_pendencia)."""
    doc = t.contraparte_doc
    if doc and doc == cfg.cnpj:
        return cfg.transferencias, ""
    if doc and doc in cfg.socios:
        return cfg.transitoria, "contraparte é sócio: definir se é pró-labore, lucros, mútuo ou AFAC"
    if doc and doc in cfg.documentos:
        return cfg.documentos[doc], ""
    sentido = "C" if t.entrada else "D"
    texto = " ".join(x for x in (t.descricao, t.contraparte_nome, t.categoria) if x)
    for r in cfg.regras:
        if r["sentido"] in ("*", sentido) and r["casa"](texto):
            return r["conta"], ""
    if len(doc) == 14:
        generica = cfg.conta_clientes if t.entrada else cfg.conta_fornecedores
        if generica:
            return generica, f"CNPJ {doc} sem conta própria: conferir cadastro de {'cliente' if t.entrada else 'fornecedor'}"
    return cfg.transitoria, "sem regra para esta transação"


def partidas(t: Transacao, cfg: Configuracao, estorno=False):
    banco = cfg.contas_banco.get(t.conta)
    if not banco:
        raise KeyError(f"conta {t.conta} sem conta contábil em contas_banco")
    contra, pend = _contrapartida(t, cfg)
    valor = abs(t.valor)
    compl = " - ".join(x for x in (t.contraparte_nome or t.descricao, t.referencia) if x)[:200]
    if t.parcela and t.total_parcelas:
        compl = f"{compl} (parcela {t.parcela}/{t.total_parcelas})"
    linhas = []

    def add(debito, credito, v, hist, comp, motivo=""):
        if v:
            linhas.append(Partida(t.data, debito, credito, v, hist, comp, t.id, motivo))

    if t.entrada:
        add(banco, contra, valor, _hist(cfg, "recebimento"), compl, pend)
    else:
        juros, multa, desc = (t.boleto_juros or Decimal(0)), (t.boleto_multa or Decimal(0)), (t.boleto_desconto or Decimal(0))
        principal = t.boleto_principal
        if principal is not None and (juros or multa or desc):
            if principal + juros + multa - desc == valor:
                add(contra, banco, principal - desc, _hist(cfg, "pagamento"), compl, pend)
                add(cfg.juros, banco, juros, _hist(cfg, "juros"), f"Juros s/ {compl}")
                add(cfg.multas, banco, multa, _hist(cfg, "multa"), f"Multa s/ {compl}")
                if desc:
                    # o título é baixado pelo principal cheio; o desconto é receita financeira
                    add(contra, cfg.descontos, desc, _hist(cfg, "desconto"), f"Desconto obtido s/ {compl}", pend)
            else:
                add(contra, banco, valor, _hist(cfg, "pagamento"), compl,
                    pend or f"boleto não fecha: {principal}+{juros}+{multa}-{desc} ≠ {valor}")
        else:
            add(contra, banco, valor, _hist(cfg, "pagamento"), compl, pend)

    if estorno:
        for p in linhas:
            p.debito, p.credito = p.credito, p.debito
            p.complemento = f"ESTORNO - transação removida na origem - {p.complemento}"[:200]
    return linhas


def fechamento_liberado(competencia: str, hoje: date, dias_reprocessamento=7):
    """Competência 'AAAA-MM' só fecha depois da janela de reprocessamento do provedor (7 dias corridos)."""
    ano, mes = map(int, competencia.split("-"))
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    return hoje > ultimo + timedelta(days=dias_reprocessamento)


def gravar_txt_dominio(caminho, linhas, colunas="data;debito;credito;valor;historico;complemento", codigo_empresa=""):
    """Mesmo formato do importador OFX: ';', dd/mm/aaaa, vírgula decimal, cp1252, sem cabeçalho."""
    ordem = colunas.split(";")
    with open(caminho, "w", encoding="cp1252", errors="replace", newline="\r\n") as fh:
        for p in linhas:
            a, m, d = p.data.split("-")
            campos = {"data": f"{d}/{m}/{a}", "debito": p.debito, "credito": p.credito,
                      "valor": f"{p.valor:.2f}".replace(".", ","), "historico": p.historico,
                      "complemento": p.complemento.replace(";", ","), "documento": p.transacao,
                      "empresa": codigo_empresa, "fitid": p.transacao}
            fh.write(";".join(str(campos[c]) for c in ordem) + "\n")


def gravar_pendencias(caminho, linhas):
    with open(caminho, "w", encoding="utf-8-sig") as fh:
        fh.write("data;valor;debito;credito;complemento;transacao;motivo\n")
        for p in linhas:
            if p.pendente:
                fh.write(f"{p.data};{p.valor:.2f};{p.debito};{p.credito};{p.complemento.replace(';', ',')};"
                         f"{p.transacao};{p.pendente}\n")
