"""
Extrato via Open Finance → banco local idempotente → lançamentos contábeis para o Domínio.

Construído a partir do estudo em docs/estudo-openfinance-tecnospeed.md e da arquitetura observada em
docs/rea-openfinance-tecnospeed-arquitetura.md: a TecnoSpeed entrega o extrato Open Finance consumindo a
Pluggy por trás. Por isso há dois provedores com a mesma interface (`provedores.py`), e o resto do pacote
(armazenamento, exclusões na origem, classificação contábil, exportação) não depende de qual for contratado.
"""

__version__ = "0.1.0"
