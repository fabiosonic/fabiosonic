from fastapi.testclient import TestClient


def test_paginas(s, cfg, tmp_path):
    from mo_obrigacoes.demo import criar_demo
    from mo_obrigacoes.web.app import criar_app

    criar_demo(s, tmp_path / "drive", "2026-09")
    s.commit()
    with TestClient(criar_app()) as c:
        assert c.get("/").status_code == 401
        auth = ("admin", "segredo")
        for url in ["/", "/?competencia=2026-09", "/empresas", "/empresas/nova", "/empresas/1", "/empresas/1/editar",
                    "/tarefas?competencia=2026-09", "/tarefas?situacao=atrasada", "/documentos", "/documentos?situacao=",
                    "/obrigacoes", "/responsaveis", "/relatorios?competencia=2026-09", "/eventos", "/api/resumo?competencia=2026-09"]:
            r = c.get(url, auth=auth)
            assert r.status_code == 200, (url, r.text[:500])
        assert "PADARIA" in c.get("/empresas", auth=auth).text
        r = c.get("/relatorios/csv?competencia=2026-09", auth=auth)
        assert r.status_code == 200 and "Vencimento" in r.text
        tarefas = c.get("/api/tarefas?competencia=2026-09", auth=auth).json()
        pend = next(t for t in tarefas if t["status"] == "pendente")
        r = c.post(f"/tarefas/{pend['id']}/acao", data={"acao": "dispensar", "observacao": "sem movimento"}, auth=auth)
        assert r.status_code == 200  # segue o redirecionamento
        assert any(t["status"] == "dispensada" for t in c.get("/api/tarefas", auth=auth).json())
        r = c.post("/empresas/salvar", data={"codigo": "0999", "razao_social": "nova ltda", "cnpj": "04.252.011/0001-10",
                                             "regime": "PRESUMIDO", "servicos": "on", "ativa": "on",
                                             "drive_folder_id": "https://drive.google.com/drive/folders/ABC123?usp=x"}, auth=auth)
        assert r.status_code == 200 and "NOVA LTDA" in r.text
        assert "inválido" in c.post("/empresas/salvar", data={"codigo": "x", "razao_social": "y", "cnpj": "123"}, auth=auth).text
        dup = c.post("/empresas/salvar", data={"codigo": "0001", "razao_social": "z", "cnpj": "04.252.011/0001-10"}, auth=auth)
        assert "Já existe" in dup.text
