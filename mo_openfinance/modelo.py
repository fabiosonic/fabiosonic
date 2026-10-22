"""
Transação normalizada, independente do provedor.

Regras que valem para qualquer provedor:
- `valor` é Decimal com sinal pela ótica da conta: positivo = entrou no banco (ou estorno no cartão),
  negativo = saiu do banco (ou compra no cartão). Os provedores mandam o valor sempre positivo + natureza;
  quem converte é o normalizador, num ponto só.
- `data` é a data de LANÇAMENTO (quando o saldo mudou). É a correta para conciliar o banco; competência
  vem do documento fiscal, não do extrato.
- `id` é a chave de idempotência (transactionId na TecnoSpeed, id na Pluggy). FITID não existe aqui.
"""
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class Transacao:
    id: str
    conta: str                     # accountHash (TecnoSpeed) ou accountId (Pluggy)
    tipo_extrato: str              # BANK | CREDIT_CARD
    data: str                      # YYYY-MM-DD (lançamento)
    valor: Decimal                 # com sinal, ver docstring do módulo
    descricao: str = ""
    categoria: str = ""
    meio: str = ""                 # PIX, TED, BOLETO, DEBIT_CARD...
    contraparte_nome: str = ""
    contraparte_doc: str = ""      # só dígitos (CPF/CNPJ de quem pagou, se entrada; de quem recebeu, se saída)
    referencia: str = ""
    boleto_principal: Optional[Decimal] = None
    boleto_juros: Optional[Decimal] = None
    boleto_multa: Optional[Decimal] = None
    boleto_desconto: Optional[Decimal] = None
    cartao_final: str = ""
    parcela: Optional[int] = None
    total_parcelas: Optional[int] = None
    estabelecimento_doc: str = ""
    estabelecimento_cnae: str = ""
    origem_protocolo: str = ""     # uniqueId do protocolo TecnoSpeed, quando houver
    bruto: dict = field(default_factory=dict, repr=False)

    @property
    def entrada(self):
        return self.valor > 0

    def para_dict(self):
        d = asdict(self)
        for k, v in d.items():
            if isinstance(v, Decimal):
                d[k] = str(v)
        return d


def so_digitos(s):
    return "".join(ch for ch in str(s or "") if ch.isdigit())


def dec(v):
    """Converte texto/número da API em Decimal sem passar por float (None continua None)."""
    if v is None or v == "":
        return None
    return Decimal(str(v)).quantize(Decimal("0.01"))
