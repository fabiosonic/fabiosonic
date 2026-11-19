"""Linha de comando: ``python -m moxml <comando>`` (os .bat do Windows chamam estes comandos)."""

from __future__ import annotations

import argparse
import getpass
import json
import shutil
import socket
import ssl
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from . import __version__


def _app(migrar: bool = True):  # noqa: ANN202
    from .config import obter_config
    from .motor.aplicacao import criar_aplicacao
    from .motor.logs import configurar_logging

    cfg = obter_config()
    app = criar_aplicacao(cfg, migrar=migrar)
    configurar_logging(cfg.pasta_logs)
    return app


def _imprimir(obj) -> None:  # noqa: ANN001
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def cmd_init(a) -> None:  # noqa: ANN001
    app = _app()
    _imprimir({"home": str(app.cfg.home), "banco": app.cfg.url_banco.split("@")[-1], "modo": app.modo,
               "cofre": app.cofre.mecanismo, "xml": str(app.cfg.pasta_xml)})


def cmd_servidor(a) -> None:  # noqa: ANN001
    import uvicorn

    if sys.stdout is None or sys.stderr is None:  # pythonw.exe (tarefa agendada, sem console)
        from .config import obter_config
        pasta = obter_config().pasta_logs
        pasta.mkdir(parents=True, exist_ok=True)
        saida = open(pasta / "servidor.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stderr = saida

    from .api.app import criar_api

    app = _app()
    api = criar_api(app, iniciar_agendador=not a.sem_agendador)
    print(f"M&O XML Captador {__version__} — modo {app.modo} — http://{app.cfg.host}:{app.cfg.porta}")
    uvicorn.run(api, host=app.cfg.host, port=app.cfg.porta, log_level="info")


def cmd_capturar(a) -> None:  # noqa: ANN001
    from .motor.orquestrador import Opcoes, Orquestrador

    app = _app()
    hist = None
    if a.historico:
        hist = {}
        for item in a.historico:
            k, v = item.split("=")
            e, m, s = k.split("|")
            hist[(int(e), m, int(s))] = int(v)
    op = Opcoes(gatilho="HISTORICA" if hist else ("AGENDADA" if a.agendada else "MANUAL"),
                empresas=a.empresa or None, modelos=tuple(a.modelo or ["55", "65"]), a_partir_de=hist,
                paralelismo=a.paralelismo)
    lote = Orquestrador(app).executar(op)
    from sqlalchemy import select

    from .db.modelos import Execucao
    with app.sessoes() as s:
        _imprimir([{"empresa_id": x.empresa_id, "modelo": x.modelo, "status": x.status, "quantidade": x.quantidade,
                    "erros": x.erros, "detalhes": x.detalhes} for x in s.scalars(select(Execucao).where(Execucao.lote == lote))])


def cmd_empresa(a) -> None:  # noqa: ANN001
    from . import servicos
    e = servicos.cadastrar_empresa(_app(), a.razao, a.cnpj, a.uf, a.regime, a.pasta)
    _imprimir({"id": e.id, "cnpj": e.cnpj})


def cmd_certificado(a) -> None:  # noqa: ANN001
    from . import servicos
    senha = getpass.getpass("Senha do certificado (não será exibida): ")
    pfx = Path(a.pfx).read_bytes()
    c = servicos.cadastrar_certificado(_app(), a.empresa, pfx, senha, a.autorizado_por, a.termo)
    _imprimir({"id": c.id, "titular": c.titular, "cnpj": c.cnpj, "validade": c.validade, "status": c.status})


def cmd_semente(a) -> None:  # noqa: ANN001
    from . import servicos
    for arq in a.arquivos:
        info = servicos.importar_semente_bytes(_app(), a.empresa, Path(arq).read_bytes())
        _imprimir(info.__dict__)


def cmd_chaves(a) -> None:  # noqa: ANN001
    from . import servicos
    chaves = [ln.strip() for ln in Path(a.arquivo).read_text(encoding="utf-8").splitlines() if ln.strip()]
    _imprimir(servicos.adicionar_chaves(_app(), a.empresa, chaves))


def cmd_pasta(a) -> None:  # noqa: ANN001
    from . import servicos
    p = servicos.adicionar_pasta(_app(), str(Path(a.caminho).resolve()), a.empresa)
    _imprimir({"id": p.id, "caminho": p.caminho})


def cmd_importar(a) -> None:  # noqa: ANN001
    from .motor.orquestrador import Orquestrador
    _imprimir(Orquestrador(_app()).importar_pastas(caminho_unico=str(Path(a.caminho).resolve()), empresa_id=a.empresa))


def cmd_auditar(a) -> None:  # noqa: ANN001
    from sqlalchemy import select

    from .db.modelos import Empresa
    from .motor import auditoria
    app = _app()
    with app.sessoes() as s:
        out = {e.razao_social: auditoria.auditar(s, e.id) for e in s.scalars(select(Empresa))}
        s.commit()
    _imprimir(out)


def cmd_drive(a) -> None:  # noqa: ANN001
    from .integracoes.gdrive import sincronizar_drive
    _imprimir(sincronizar_drive(_app(), limite=a.limite))


def cmd_drive_autorizar(a) -> None:  # noqa: ANN001
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(a.client_secret, ["https://www.googleapis.com/auth/drive"])
    cred = flow.run_local_server(port=0)
    destino = Path(a.saida)
    destino.write_text(cred.to_json(), encoding="utf-8")
    print(f"token salvo em {destino}. Defina MOXML_GDRIVE_CREDENCIAIS={destino} (fora do repositório).")


def cmd_dominio(a) -> None:  # noqa: ANN001
    from .integracoes import dominio
    app = _app()
    destino = Path(a.destino) if a.destino else app.cfg.home / "exportacoes" / "dominio"
    _imprimir(dominio.exportar_lote(app, a.ano, a.mes, destino, a.empresa or None))


def cmd_backup(a) -> None:  # noqa: ANN001
    app = _app()
    cfg = app.cfg
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    destino = Path(a.destino) if a.destino else cfg.pasta_backup
    destino.mkdir(parents=True, exist_ok=True)
    arq = destino / f"moxml-backup-{stamp}.zip"
    with zipfile.ZipFile(arq, "w", zipfile.ZIP_DEFLATED) as z:
        if cfg.url_banco.startswith("sqlite"):
            import sqlite3
            tmp = destino / f"moxml-{stamp}.db"
            src = sqlite3.connect(cfg.url_banco.split("///", 1)[1])
            dst = sqlite3.connect(tmp)
            src.backup(dst)  # cópia consistente com o banco em uso
            src.close()
            dst.close()
            z.write(tmp, "banco/moxml.db")
            tmp.unlink()
        else:
            print("PostgreSQL: execute pg_dump (ver PLANO_IMPLANTACAO.md); incluindo apenas XMLs e cofre.")
        for p in Path(cfg.pasta_xml).rglob("*"):
            if p.is_file():
                z.write(p, Path("xml") / p.relative_to(cfg.pasta_xml))
        for p in Path(cfg.pasta_cofre).glob("*"):
            if p.is_file():
                z.write(p, Path("cofre") / p.name)  # segredos continuam cifrados (DPAPI: só abrem no mesmo usuário/PC)
    antigos = sorted(destino.glob("moxml-backup-*.zip"))[:-a.manter] if a.manter else []
    for x in antigos:
        x.unlink()
    _imprimir({"backup": str(arq), "tamanho_mb": round(arq.stat().st_size / 1e6, 2), "removidos": len(antigos)})


def _testar_tls(host: str, cafile: Path | None) -> str:
    try:
        ctx = ssl.create_default_context(cafile=str(cafile) if cafile else None)
        with socket.create_connection((host, 443), timeout=10) as sock, ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
            emissor = dict(x[0] for x in cert.get("issuer", ()))
            return f"OK ({tls.version()}, emissor {emissor.get('organizationName', '?')})"
    except Exception as e:  # noqa: BLE001
        return f"FALHA: {type(e).__name__}: {e}"


def cmd_diagnostico(a) -> None:  # noqa: ANN001
    from sqlalchemy import func, select, text

    from .db.modelos import Certificado, Empresa
    app = _app()
    cfg = app.cfg
    rel: dict = {"versao": __version__, "python": sys.version.split()[0], "modo": app.modo, "home": str(cfg.home),
                 "cofre": app.cofre.mecanismo}
    try:
        with app.sessoes() as s:
            s.execute(text("select 1"))
            rel["banco"] = {"ok": True, "empresas": s.scalar(select(func.count()).select_from(Empresa)),
                            "certificados_ativos": s.scalar(select(func.count()).select_from(Certificado)
                                                            .where(Certificado.ativo.is_(True)))}
    except Exception as e:  # noqa: BLE001
        rel["banco"] = {"ok": False, "erro": str(e)}
    livre = shutil.disk_usage(cfg.home).free / 1e9
    rel["disco_livre_gb"] = round(livre, 1)
    rel["conectividade_tls_sem_certificado_cliente"] = {
        h: _testar_tls(h, cfg.ca_bundle) for h in (
            "nfe.svrs.rs.gov.br", "nfce.svrs.rs.gov.br", "dfe-portal.svrs.rs.gov.br", "www.googleapis.com")}
    rel["matriz_rj"] = [{k: v for k, v in m.items() if k in ("modelo", "conector", "status")}
                        for m in app.registro.matriz(["RJ"])]
    if a.empresa:
        from .conectores.base import ContextoCaptura
        from .conectores.svrs_portal import SvrsPortalConector
        with app.sessoes() as s:
            emp = s.get(Empresa, a.empresa)
            reg = app.certificado_ativo(s, emp.id)
            if reg:
                cert = app.carregar_certificado(reg)
                for mod in ("55", "65"):
                    ctx = ContextoCaptura(empresa_id=emp.id, cnpj=emp.cnpj, uf=emp.uf, modelo=mod,
                                          cliente_http=lambda c=cert: app.cliente_http(emp.cnpj, c))
                    try:
                        rel[f"portal_svrs_{mod}"] = SvrsPortalConector().inspecionar(ctx)
                    except Exception as e:  # noqa: BLE001
                        rel[f"portal_svrs_{mod}"] = {"erro": f"{type(e).__name__}: {e}"}
            else:
                rel["portal_svrs"] = "empresa sem certificado"
    _imprimir(rel)
    saida = cfg.home / "evidencias" / f"diagnostico-{datetime.now():%Y%m%d-%H%M%S}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"\nRelatório salvo em {saida}")


def cmd_teste_real(a) -> None:  # noqa: ANN001
    from .teste_real import executar_teste_real
    _imprimir(executar_teste_real(_app(), a.empresa, a.chave, a.autorizado_por))


def cmd_svrs(a) -> None:  # noqa: ANN001
    """Ciclo SVRS para uma empresa: status dos webservices, descoberta por série/consulta,
    inspeção do Portal DF-e SVRS (detecta CAPTCHA) e download do XML completo. Grava evidência."""
    from sqlalchemy import select

    from .conectores.base import Capacidade, ContextoCaptura
    from .conectores.sefaz_consulta import SefazConsultaConector
    from .conectores.svrs_portal import SvrsPortalConector
    from .db.modelos import Empresa, Serie
    from .fiscal import xmlfiscal as xf
    app = _app()
    rel: dict = {"empresa_id": a.empresa, "modelos": a.modelo or ["55", "65"], "modo": app.modo,
                 "momento": datetime.now(UTC).isoformat(), "etapas": {}}
    with app.sessoes() as s:
        emp = s.get(Empresa, a.empresa)
        if emp is None:
            raise SystemExit("empresa não encontrada")
        rel["empresa"] = {"cnpj": emp.cnpj, "razao_social": emp.razao_social, "uf": emp.uf}
        reg = app.certificado_ativo(s, emp.id)
        if reg is None:
            raise SystemExit("empresa sem certificado A1 ativo (cadastre pelo painel antes do teste SVRS)")
        cert = app.carregar_certificado(reg)
        cons, portal = SefazConsultaConector(), SvrsPortalConector()
        for modelo in rel["modelos"]:
            etapa: dict = {}
            disp = portal.suporta(emp.uf, modelo)
            etapa["portal_disponivel"] = f"{disp.status.value} — {disp.motivo}"
            ctx = ContextoCaptura(empresa_id=emp.id, cnpj=emp.cnpj, uf=emp.uf, modelo=modelo, ambiente=1,
                                  cliente_soap=lambda c=cert: app.cliente_soap(emp.cnpj, c),
                                  cliente_http=lambda c=cert: app.cliente_http(emp.cnpj, c))
            # 1) inspeção do portal: detecta CAPTCHA sem baixar nada
            try:
                insp = portal.inspecionar(ctx)
                etapa["portal_captcha"] = insp.get("captcha")
                etapa["portal_formulario"] = insp.get("forms")
            except Exception as e:  # noqa: BLE001
                etapa["portal_inspecao_erro"] = f"{type(e).__name__}: {e}"
            # 2) descoberta pela consulta (uma série, a partir do último conhecido) para obter uma chave real
            chave = a.chave
            if not chave:
                sr = s.scalar(select(Serie).where(Serie.empresa_id == emp.id, Serie.modelo == modelo,
                                                  Serie.ativo.is_(True)).limit(1))
                if sr and sr.chave_semente:
                    chave = sr.chave_semente
            etapa["chave_usada"] = chave
            # 3) download do XML completo pelo portal SVRS
            if chave and Capacidade.RECUPERAR_XML in portal.capacidades:
                try:
                    rec = portal.recuperar_xml(ctx, chave)
                    d = xf.ler(rec.xml)
                    etapa["download"] = {"ok": d.e_xml_integral, "tipo": d.tipo.value,
                                         "assinatura_ok": d.assinatura_ok, "sha256": d.sha256}
                except Exception as e:  # noqa: BLE001
                    etapa["download_erro"] = f"{type(e).__name__}: {e}"
            rel["etapas"][modelo] = etapa
    saida = app.cfg.home / "evidencias" / f"svrs-{datetime.now():%Y%m%d-%H%M%S}.json"
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps(rel, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    _imprimir(rel)
    print(f"\nEvidência salva em {saida}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="moxml", description="M&O XML Captador — NF-e 55 e NFC-e 65 de saída")
    p.add_argument("--versao", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="cria pastas e aplica migrations").set_defaults(f=cmd_init)
    sp = sub.add_parser("servidor", help="painel web + agendador")
    sp.add_argument("--sem-agendador", action="store_true")
    sp.set_defaults(f=cmd_servidor)
    sp = sub.add_parser("capturar", help="executa a captura agora")
    sp.add_argument("--empresa", type=int, action="append")
    sp.add_argument("--modelo", choices=["55", "65"], action="append")
    sp.add_argument("--historico", action="append", help="'empresa|modelo|serie=numero_inicial'")
    sp.add_argument("--agendada", action="store_true", help="marca a execução como AGENDADA (uso do agendador do Windows)")
    sp.add_argument("--paralelismo", type=int, default=4)
    sp.set_defaults(f=cmd_capturar)
    sp = sub.add_parser("empresa", help="cadastra empresa")
    sp.add_argument("--razao", required=True)
    sp.add_argument("--cnpj", required=True)
    sp.add_argument("--uf", default="RJ")
    sp.add_argument("--regime")
    sp.add_argument("--pasta", help="nome da pasta do cliente no Drive (se diferente do padrão)")
    sp.set_defaults(f=cmd_empresa)
    sp = sub.add_parser("certificado", help="cadastra A1 (senha pedida no terminal)")
    sp.add_argument("--empresa", type=int, required=True)
    sp.add_argument("--pfx", required=True)
    sp.add_argument("--autorizado-por", required=True)
    sp.add_argument("--termo", required=True, help="referência do termo/contrato de autorização do cliente")
    sp.set_defaults(f=cmd_certificado)
    sp = sub.add_parser("semente", help="importa XML semente (um por modelo/série)")
    sp.add_argument("--empresa", type=int, required=True)
    sp.add_argument("arquivos", nargs="+")
    sp.set_defaults(f=cmd_semente)
    sp = sub.add_parser("chaves", help="cadastra chaves conhecidas (arquivo texto, uma por linha)")
    sp.add_argument("--empresa", type=int, required=True)
    sp.add_argument("arquivo")
    sp.set_defaults(f=cmd_chaves)
    sp = sub.add_parser("pasta", help="cadastra pasta monitorada do emissor")
    sp.add_argument("caminho")
    sp.add_argument("--empresa", type=int)
    sp.set_defaults(f=cmd_pasta)
    sp = sub.add_parser("importar", help="importa XMLs de uma pasta (histórico)")
    sp.add_argument("caminho")
    sp.add_argument("--empresa", type=int)
    sp.set_defaults(f=cmd_importar)
    sub.add_parser("auditar", help="recalcula lacunas de numeração").set_defaults(f=cmd_auditar)
    sp = sub.add_parser("drive", help="sincroniza com o Google Drive")
    sp.add_argument("--limite", type=int)
    sp.set_defaults(f=cmd_drive)
    sp = sub.add_parser("drive-autorizar", help="gera token OAuth do Google Drive")
    sp.add_argument("--client-secret", required=True)
    sp.add_argument("--saida", required=True)
    sp.set_defaults(f=cmd_drive_autorizar)
    sp = sub.add_parser("exportar-dominio", help="gera pacote de importação para o Domínio")
    sp.add_argument("--ano", type=int, required=True)
    sp.add_argument("--mes", type=int, required=True)
    sp.add_argument("--empresa", type=int, action="append")
    sp.add_argument("--destino")
    sp.set_defaults(f=cmd_dominio)
    sp = sub.add_parser("backup", help="backup do banco, XMLs e cofre")
    sp.add_argument("--destino")
    sp.add_argument("--manter", type=int, default=30)
    sp.set_defaults(f=cmd_backup)
    sp = sub.add_parser("diagnostico", help="verifica ambiente, banco, rede e (opcional) portal SVRS")
    sp.add_argument("--empresa", type=int, help="inspeciona o formulário do portal SVRS com o A1 desta empresa")
    sp.set_defaults(f=cmd_diagnostico)
    sp = sub.add_parser("svrs", help="ciclo SVRS de uma empresa: webservice + Portal DF-e SVRS (detecta CAPTCHA, baixa XML)")
    sp.add_argument("--empresa", type=int, required=True)
    sp.add_argument("--modelo", choices=["55", "65"], action="append")
    sp.add_argument("--chave", help="chave conhecida para o download (senão usa a chave semente da série)")
    sp.set_defaults(f=cmd_svrs)
    sp = sub.add_parser("teste-real", help="teste de aceitação com CNPJ autorizado e chave real conhecida")
    sp.add_argument("--empresa", type=int, required=True)
    sp.add_argument("--chave", required=True)
    sp.add_argument("--autorizado-por", required=True)
    sp.set_defaults(f=cmd_teste_real)
    a = p.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
