"""Emissor de NFS-e da Prefeitura de Itaboraí/RJ via webservice (conversão de RPS em NFS-e)."""

__version__ = "3.15.0"

import warnings as _w

# certificados A1 gerados por alguns emissores vêm em BER; a leitura funciona, o aviso só polui o log
_w.filterwarnings("ignore", message=r".*PKCS#12 bundle could not be parsed as DER.*")
