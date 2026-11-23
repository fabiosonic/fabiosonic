"""Portal Contábil: importação e auditoria automática de documentos fiscais."""
from .auditoria import auditar
from .importadores import Importador, importar

__version__ = "0.1.0"
__all__ = ["auditar", "importar", "Importador"]
