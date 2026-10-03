"""Países mais usados em exportação/importação de serviços: sigla ISO (NFS-e Nacional), código BACEN (webservice
de Itaboraí, campo CodigoPais) e moeda pela tabela do BACEN (grupo comExt da DPS). Outros países: informe os
códigos no cadastro do cliente."""

PAISES = {  # ISO: (nome, código BACEN do país, código BACEN da moeda)
    "US": ("Estados Unidos", "2496", "220"),
    "PT": ("Portugal", "6076", "978"),
    "ES": ("Espanha", "2453", "978"),
    "FR": ("França", "2755", "978"),
    "IT": ("Itália", "3867", "978"),
    "DE": ("Alemanha", "0230", "978"),
    "GB": ("Reino Unido", "6289", "540"),
    "CA": ("Canadá", "1490", ""),
    "JP": ("Japão", "3999", ""),
    "CN": ("China", "1600", ""),
    "AR": ("Argentina", "0639", ""),
    "UY": ("Uruguai", "8451", ""),
    "PY": ("Paraguai", "5860", ""),
    "CL": ("Chile", "1589", ""),
    "MX": ("México", "4936", ""),
}
MOEDAS = {"220": "Dólar dos EUA", "978": "Euro", "540": "Libra esterlina"}


def bacen(iso: str) -> str:
    return PAISES.get(str(iso or "").upper(), ("", "", ""))[1]


def moeda(iso: str) -> str:
    return PAISES.get(str(iso or "").upper(), ("", "", ""))[2]
