"""Testa a navegação recursiva do cliente Google Drive com um serviço simulado."""
from datetime import datetime

from mo_obrigacoes.drive import extrair_id_pasta
from mo_obrigacoes.drive.google import PASTA, GoogleDriveClient

ARVORE = {
    "raiz": [{"id": "p2026", "name": "2026", "mimeType": PASTA}],
    "p2026": [{"id": "p09", "name": "09 - Setembro", "mimeType": PASTA},
              {"id": "atalho", "name": "x", "mimeType": "application/vnd.google-apps.shortcut"}],
    "p09": [{"id": "f1", "name": "DAS.pdf", "mimeType": "application/pdf", "size": "123", "md5Checksum": "abc",
             "createdTime": "2026-10-10T12:00:00.000Z", "modifiedTime": "2026-10-10T12:00:00.000Z",
             "webViewLink": "https://drive/f1", "lastModifyingUser": {"emailAddress": "cliente@x.com"}},
            {"id": "f2", "name": "velho.pdf", "mimeType": "application/pdf",
             "createdTime": "2026-01-01T00:00:00Z", "modifiedTime": "2026-01-01T00:00:00Z"}],
}


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self):
        return self.r


class _Files:
    def list(self, q, **_):
        pai = q.split("'")[1]
        return _Req({"files": ARVORE.get(pai, [])})


class _Servico:
    def files(self):
        return _Files()


def test_listagem_recursiva_e_filtro_incremental():
    c = GoogleDriveClient("", servico=_Servico())
    arqs = list(c.listar_arquivos("raiz"))
    assert [a.caminho for a in arqs] == ["2026/09 - Setembro/DAS.pdf", "2026/09 - Setembro/velho.pdf"]
    assert arqs[0].enviado_por == "cliente@x.com" and arqs[0].tamanho == 123
    novos = list(c.listar_arquivos("raiz", modificado_apos=datetime(2026, 6, 1)))
    assert [a.id for a in novos] == ["f1"]


def test_extrair_id_pasta():
    assert extrair_id_pasta("https://drive.google.com/drive/folders/1AbC_d-E?usp=sharing") == "1AbC_d-E"
    assert extrair_id_pasta("1AbC") == "1AbC"
