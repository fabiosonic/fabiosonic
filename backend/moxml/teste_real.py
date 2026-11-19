"""Teste de aceitação com CNPJ AUTORIZADO e documento real previamente conhecido (seção 17).

Executa, para UM modelo por vez (55 ou 65), os critérios de aceitação e grava evidência em
``<MOXML_HOME>/evidencias/``. Faz poucas chamadas (≈6) e nunca altera nada na SEFAZ.

Critérios: 1 fonte identificada · 2 acesso autorizado · 3 autenticação · 4 descoberta ·
5 XML autorizado recuperado · 6 conteúdo validado · 7 armazenado · 8 repetível · 9 sem duplicidade ·
10 execução automática (verificada separadamente pelo histórico de execuções AGENDADA).
"""

from __future__ import annotations

import json
import traceback
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from .certificados.a1 import impedimentos_bloqueantes, validar_para_empresa
from .conectores.base import ContextoCaptura
from .conectores.dist_dfe import DistribuicaoDFeConector
from .conectores.sefaz_consulta import DescobertaImpossivel, SefazConsultaConector
from .conectores.svrs_portal import SvrsPortalConector
from .db.modelos import Empresa, Execucao
from .fiscal import chave as chv
from .fiscal import xmlfiscal as xf
from .motor.aplicacao import Aplicacao
from .motor.repositorio import Repositorio


def executar_teste_real(app: Aplicacao, empresa_id: int, chave_conhecida: str, autorizado_por: str) -> dict:
    if app.modo != "REAL":
        raise RuntimeError("teste real exige MOXML_MODO=REAL")
    ck = chv.analisar(chave_conhecida)
    rel: dict = {"inicio": datetime.now(UTC).isoformat(), "modelo": ck.modelo, "uf": ck.uf, "chave": ck.chave,
                 "autorizado_por": autorizado_por, "criterios": {}, "chamadas": []}
    crit = rel["criterios"]

    def marca(n: int, status: str, detalhe: str) -> None:
        crit[str(n)] = {"status": status, "detalhe": detalhe}

    with app.sessoes() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None or emp.cnpj != ck.cnpj:
            raise RuntimeError("a chave informada não pertence à empresa selecionada")
        rel["empresa"] = {"cnpj": emp.cnpj, "razao_social": emp.razao_social}
        reg = app.certificado_ativo(s, emp.id)
        marca(1, "OK", "NFeConsultaProtocolo SVRS + Portal DF-e SVRS DownloadXMLDFe (catálogo oficial)")
        if reg is None:
            marca(2, "FALHA", "empresa sem certificado A1 autorizado cadastrado")
            return _gravar(app, rel)
        cert = app.carregar_certificado(reg)
        bloq = impedimentos_bloqueantes(validar_para_empresa(cert, emp.cnpj))
        marca(2, "FALHA" if bloq else "OK",
              "; ".join(bloq) or f"A1 de {cert.info.titular}, autorização registrada por {reg.autorizado_por}")
        if bloq:
            return _gravar(app, rel)
        ctx = ContextoCaptura(empresa_id=emp.id, cnpj=emp.cnpj, uf=ck.uf, modelo=ck.modelo, ambiente=1,
                              cliente_soap=lambda: app.cliente_soap(emp.cnpj, cert),
                              cliente_http=lambda: app.cliente_http(emp.cnpj, cert))
        cons, portal = SefazConsultaConector(), SvrsPortalConector()
        # 3. autenticação + situação
        try:
            sit = cons.consultar_situacao(ctx, ck.chave)
            rel["chamadas"].append({"servico": "NFeConsultaProtocolo", "cstat": sit.cstat, "xmotivo": sit.xmotivo})
            marca(3, "OK" if sit.cstat in ("100", "101", "110", "150", "151", "155") else "FALHA",
                  f"cStat {sit.cstat} — {sit.xmotivo}")
        except Exception as e:  # noqa: BLE001
            marca(3, "FALHA", f"{type(e).__name__}: {e}")
            return _gravar(app, rel)
        # 4. descoberta J04/562 com cNF zerado para a série/número conhecidos
        try:
            dt = datetime(ck.ano, ck.mes, 1)
            r = cons.sondar_numero(ctx, ck.serie, ck.numero, dt)
            rel["chamadas"].append({"servico": "NFeConsultaProtocolo (descoberta)", "cstat": r.cstat, "xmotivo": r.xmotivo})
            marca(4, "OK" if r.chave == ck.chave else "FALHA",
                  f"chave descoberta {r.chave} (esperada {ck.chave}); cStat {r.cstat}")
        except DescobertaImpossivel as e:
            marca(4, "IMPOSSIVEL_PELO_METODO", str(e))
        except Exception as e:  # noqa: BLE001
            marca(4, "FALHA", f"{type(e).__name__}: {e}")
        # 5/6. XML integral: NF-e 55 → DistDFe por chave (webservice); NFC-e 65 → portal SVRS.
        fontes_xml = []
        if ck.modelo == "55":
            fontes_xml.append(("dist_dfe_chave", DistribuicaoDFeConector()))
        fontes_xml.append(("svrs_portal_download", portal))
        try:
            rel["portal_inspecao"] = portal.inspecionar(ctx)
        except Exception as e:  # noqa: BLE001
            rel["portal_inspecao"] = {"erro": f"{type(e).__name__}: {e}"}
        xml = None
        origem_xml = None
        ultimo = ""
        for nome_fonte, conector in fontes_xml:
            try:
                rec = conector.recuperar_xml(ctx, ck.chave)
                xml, origem_xml = rec.xml, nome_fonte
                rel["chamadas"].append({"servico": nome_fonte, "resultado": "XML recebido"})
                break
            except Exception as e:  # noqa: BLE001
                ultimo = f"{nome_fonte}: {type(e).__name__}: {e}"
                rel["chamadas"].append({"servico": nome_fonte, "resultado": ultimo})
        try:
            if xml is None:
                raise RuntimeError(ultimo or "nenhuma fonte entregou XML")
            rel["fonte_xml"] = origem_xml
            d = xf.ler(xml)
            marca(5, "OK" if d.chave == ck.chave and d.tipo in (xf.TipoXML.NFE_AUTORIZADA, xf.TipoXML.NFE_DENEGADA) else "FALHA",
                  f"tipo {d.tipo}, chave {d.chave}")
            marca(6, "OK" if d.e_xml_integral and d.assinatura_ok else "FALHA",
                  f"assinatura_ok={d.assinatura_ok}; problemas={[p.mensagem for p in d.problemas]}")
            rel["xml_sha256"] = d.sha256
        except Exception as e:  # noqa: BLE001
            marca(5, "FALHA", f"{type(e).__name__}: {e}")
            marca(6, "NAO_TESTADO", "sem XML")
            rel["traceback"] = traceback.format_exc()[-2000:]
        if xml is not None and crit["6"]["status"] == "OK":
            repo = Repositorio(s, app.armazenamento, app.modo)
            r1 = repo.registrar_xml(xml, origem_xml or "teste_real", emp, ck.chave)
            s.commit()
            marca(7, "OK" if r1.resultado in ("NOVO", "ATUALIZADO", "DUPLICADO") else "FALHA", f"{r1.resultado} {r1.mensagem}")
            fonte2 = DistribuicaoDFeConector() if origem_xml == "dist_dfe_chave" else portal
            try:
                xml2 = fonte2.recuperar_xml(ctx, ck.chave).xml
                marca(8, "OK" if xf.sha256(xml2) == xf.sha256(xml) else "FALHA",
                      "segundo download idêntico" if xf.sha256(xml2) == xf.sha256(xml) else "conteúdo divergente")
                r2 = repo.registrar_xml(xml2, "svrs_portal_download", emp, ck.chave)
                s.commit()
                marca(9, "OK" if r2.resultado == "DUPLICADO" else "FALHA", r2.resultado)
            except Exception as e:  # noqa: BLE001
                marca(8, "FALHA", f"{type(e).__name__}: {e}")
        agendadas = s.scalars(select(Execucao).where(Execucao.empresa_id == emp.id, Execucao.modelo == ck.modelo,
                                                     Execucao.gatilho == "AGENDADA", Execucao.status == "SUCESSO")).first()
        marca(10, "OK" if agendadas else "NAO_TESTADO",
              "há execução AGENDADA com sucesso" if agendadas else "aguardar execução agendada e repetir o teste")
    return _gravar(app, rel)


def _gravar(app: Aplicacao, rel: dict) -> dict:
    rel["fim"] = datetime.now(UTC).isoformat()
    ok = all(rel["criterios"].get(str(i), {}).get("status") == "OK" for i in range(1, 11))
    rel["operacional"] = ok
    pasta = Path(app.cfg.home) / "evidencias"
    pasta.mkdir(parents=True, exist_ok=True)
    nome = f"teste_real_{rel.get('empresa', {}).get('cnpj', 'x')}_{rel['modelo']}_{datetime.now():%Y%m%d%H%M%S}.json"
    (pasta / nome).write_text(json.dumps(rel, ensure_ascii=False, indent=2), encoding="utf-8")
    rel["arquivo_evidencia"] = str(pasta / nome)
    return rel
