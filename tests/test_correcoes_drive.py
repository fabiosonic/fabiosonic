"""Pacote E: cliente do Google Drive (injeção na query, novas tentativas, fuso) e falha de leitura."""
import pytest

from mo_obrigacoes.drive.base import ArquivoDrive, DriveClient, ErroLeitura
from mo_obrigacoes.drive.google import GoogleDriveClient

CHAMADAS = []


class _Req:
    def __init__(self, r):
        self.r = r

    def execute(self, num_retries=0):
        CHAMADAS.append(num_retries)
        return self.r


class _Files:
    def list(self, q, **_):
        return _Req({"files": []})

    def create(self, **_):
        return _Req({"id": "nova"})


class _Servico:
    def files(self):
        return _Files()


def test_id_de_pasta_com_aspas_e_recusado():
    c = GoogleDriveClient("", servico=_Servico())
    with pytest.raises(ValueError):
        list(c.listar_arquivos("abc' in parents or 'root"))
    with pytest.raises(ValueError):
        c.garantir_pasta("2026", "x' or name contains 'a")


def test_chamadas_com_novas_tentativas():
    CHAMADAS.clear()
    c = GoogleDriveClient("", servico=_Servico())
    list(c.listar_arquivos("raiz_123"))
    c.garantir_pasta("2026", "raiz_123")
    assert CHAMADAS and all(n >= 3 for n in CHAMADAS)


def test_falha_de_download_vira_erro_leitura():
    class Quebrado(DriveClient):
        def listar_arquivos(self, pasta_id, modificado_apos=None):
            return iter(())

        def baixar(self, arquivo):
            raise RuntimeError("403 rateLimitExceeded")

        def garantir_pasta(self, nome, pai_id):
            return ""

    with pytest.raises(ErroLeitura):
        Quebrado().ler_texto(ArquivoDrive(id="1", nome="a.pdf", mime_type="application/pdf", caminho="a.pdf"))
