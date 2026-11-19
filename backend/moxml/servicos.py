"""Operações de negócio usadas pela API e pela linha de comando."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from .certificados.a1 import (
    carregar_pfx,
    impedimentos_bloqueantes,
    validar_para_empresa,
)
from .db.modelos import (
    Certificado,
    ChaveConhecida,
    Documento,
    Empresa,
    Evento,
    Execucao,
    Lacuna,
    PastaMonitorada,
    RegistroFonte,
)
from .fiscal import chave as chv
from .motor.aplicacao import Aplicacao
from .motor.repositorio import Repositorio
from .motor.semente import importar_semente


class ErroNegocio(ValueError):
    pass


def so_digitos(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def validar_cnpj(cnpj: str) -> str:
    """Valida CNPJ numérico ou alfanumérico (IN RFB 2.229/2024, vigente desde jul/2026):
    12 posições alfanuméricas + 2 DV numéricos, valor de cada caractere = ord(c) - 48."""
    c = re.sub(r"[^0-9A-Za-z]", "", cnpj or "").upper()
    if len(c) != 14 or not c[12:].isdigit() or c == c[0] * 14:
        raise ErroNegocio("CNPJ inválido")
    for tam in (12, 13):
        pesos = list(range(tam - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum((ord(d) - 48) * p for d, p in zip(c[:tam], pesos[-tam:], strict=False))
        dv = 0 if soma % 11 < 2 else 11 - soma % 11
        if int(c[tam]) != dv:
            raise ErroNegocio("CNPJ com dígito verificador inválido")
    return c


def cadastrar_empresa(app: Aplicacao, razao: str, cnpj: str, uf: str = "RJ", regime: str | None = None,
                      nome_pasta: str | None = None, captura_nfe: bool = True, captura_nfce: bool = True) -> Empresa:
    c = validar_cnpj(cnpj)
    with app.sessoes() as s:
        if s.scalar(select(Empresa.id).where(Empresa.cnpj == c)):
            raise ErroNegocio("empresa já cadastrada")
        e = Empresa(razao_social=razao.strip().upper(), cnpj=c, uf=uf.upper(), regime=regime, nome_pasta=nome_pasta,
                    captura_nfe=captura_nfe, captura_nfce=captura_nfce)
        s.add(e)
        s.commit()
        return e


def cadastrar_certificado(app: Aplicacao, empresa_id: int, pfx: bytes, senha: str, autorizado_por: str,
                          termo: str) -> Certificado:
    if not autorizado_por.strip() or not termo.strip():
        raise ErroNegocio("autorização expressa do titular é obrigatória (responsável e termo)")
    cert = carregar_pfx(pfx, senha)  # SenhaIncorreta / ErroCertificado propagam
    with app.sessoes() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            raise ErroNegocio("empresa não encontrada")
        problemas = validar_para_empresa(cert, emp.cnpj)
        bloq = impedimentos_bloqueantes(problemas)
        if app.modo == "REAL" and not cert.info.icp_brasil:
            bloq.append(f"certificado não emitido sob a ICP-Brasil (emissor: {cert.info.emissor}); "
                        "somente e-CNPJ A1 ICP-Brasil é aceito em produção")
        if bloq:
            raise ErroNegocio("; ".join(bloq))
        sufixo = secrets.token_hex(6)
        ref_pfx = app.cofre.guardar(f"pfx-{emp.cnpj}-{sufixo}", pfx)
        ref_senha = app.cofre.guardar(f"senha-{emp.cnpj}-{sufixo}", senha)
        for antigo in s.scalars(select(Certificado).where(Certificado.empresa_id == empresa_id,
                                                          Certificado.ativo.is_(True))):
            antigo.ativo, antigo.status = False, "SUBSTITUIDO"
        c = Certificado(empresa_id=empresa_id, escopo="EMPRESA", referencia_armazenamento_seguro=ref_pfx,
                        referencia_senha=ref_senha, titular=cert.info.titular, cnpj=cert.info.cnpj,
                        valido_de=cert.info.valido_de, validade=cert.info.valido_ate, serial=cert.info.serial,
                        impressao_digital=cert.info.impressao_digital_sha256, emissor=cert.info.emissor,
                        status=cert.info.status, autorizado_por=autorizado_por.strip(), termo_autorizacao=termo.strip())
        s.add(c)
        s.commit()
    app.limpar_cache_certificados()
    return c


def importar_semente_bytes(app: Aplicacao, empresa_id: int, conteudo: bytes):  # noqa: ANN201
    with app.sessoes() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            raise ErroNegocio("empresa não encontrada")
        info = importar_semente(Repositorio(s, app.armazenamento, app.modo), emp, conteudo)
        s.commit()
        return info


def adicionar_chaves(app: Aplicacao, empresa_id: int, chaves: list[str]) -> dict:
    res = {"aceitas": 0, "rejeitadas": []}
    with app.sessoes() as s:
        emp = s.get(Empresa, empresa_id)
        if emp is None:
            raise ErroNegocio("empresa não encontrada")
        repo = Repositorio(s, app.armazenamento, app.modo)
        for ch in chaves:
            try:
                ck = chv.analisar(ch)
                if ck.cnpj != emp.cnpj:
                    raise chv.ChaveInvalida(f"CNPJ da chave ({ck.cnpj}) difere da empresa")
                if ck.uf != emp.uf:
                    raise chv.ChaveInvalida(f"UF da chave ({ck.uf}) difere da empresa")
                repo.registrar_chave(emp, ck.chave, "manual")
                res["aceitas"] += 1
            except (chv.ChaveInvalida, ValueError) as e:
                res["rejeitadas"].append({"chave": ch, "motivo": str(e)})
        s.commit()
    return res


def adicionar_pasta(app: Aplicacao, caminho: str, empresa_id: int | None) -> PastaMonitorada:
    with app.sessoes() as s:
        p = PastaMonitorada(caminho=caminho, empresa_id=empresa_id)
        s.add(p)
        s.commit()
        return p


def resumo(app: Aplicacao) -> dict:
    with app.sessoes() as s:
        agora = datetime.now(UTC)
        ult = s.scalar(select(func.max(Execucao.fim)))
        lote = s.scalar(select(Execucao.lote).order_by(Execucao.inicio.desc()).limit(1))
        proc = s.scalar(select(func.count(func.distinct(Execucao.empresa_id))).where(Execucao.lote == lote)) if lote else 0
        por_modelo = dict(s.execute(select(Documento.modelo, func.count()).where(
            Documento.tipo_xml.in_(["NFE_AUTORIZADA", "NFE_DENEGADA"])).group_by(Documento.modelo)).all())
        erros_fonte = dict(s.execute(select(RegistroFonte.fonte, func.count()).where(
            RegistroFonte.erro.is_not(None), RegistroFonte.momento >= agora - timedelta(days=7))
            .group_by(RegistroFonte.fonte)).all())
        erros_exec = s.scalar(select(func.count()).select_from(Execucao).where(
            Execucao.status == "ERRO", Execucao.inicio >= agora - timedelta(days=7))) or 0
        return {
            "modo": app.modo,
            "empresas_cadastradas": s.scalar(select(func.count()).select_from(Empresa)) or 0,
            "empresas_ativas": s.scalar(select(func.count()).select_from(Empresa).where(Empresa.ativo.is_(True))) or 0,
            "empresas_processadas_ultimo_lote": proc or 0,
            "xmls_recuperados": sum(por_modelo.values()),
            "nfe_recuperadas": por_modelo.get("55", 0),
            "nfce_recuperadas": por_modelo.get("65", 0),
            "xmls_pendentes": s.scalar(select(func.count()).select_from(ChaveConhecida).where(
                ChaveConhecida.status != "RECUPERADA")) or 0,
            "documentos_cancelados": s.scalar(select(func.count()).select_from(Documento).where(
                Documento.situacao == "CANCELADA")) or 0,
            "eventos": s.scalar(select(func.count()).select_from(Evento)) or 0,
            "lacunas": s.scalar(select(func.count()).select_from(Lacuna)) or 0,
            "certificados_vencendo": s.scalar(select(func.count()).select_from(Certificado).where(
                Certificado.ativo.is_(True), Certificado.validade <= agora + timedelta(days=30))) or 0,
            "erros_por_fonte_7d": erros_fonte,
            "execucoes_com_erro_7d": erros_exec,
            "ultima_sincronizacao": ult.isoformat() if ult else None,
        }
