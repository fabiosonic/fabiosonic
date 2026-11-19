"""Rotina de captura: fila por empresa × modelo com isolamento de falhas e checkpoints persistentes.

Fluxo por empresa/modelo:
  1 certificado → 2 séries → 3 pastas do emissor → 4 descoberta (fontes oficiais; comercial opcional)
  → 5 recuperação do XML integral → 6 eventos (re-consulta na janela de cancelamento/CC-e)
  → 7 auditoria de numeração → registro da execução.
Uma falha em uma empresa nunca interrompe as demais. Cada chave descoberta é gravada (commit) antes de
avançar o checkpoint, então um reinício retoma do ponto em que parou sem perder documentos.
"""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from ..certificados.a1 import impedimentos_bloqueantes, validar_para_empresa
from ..conectores.base import Capacidade, ContextoCaptura, FonteSemDados, XmlRecuperado
from ..conectores.pastas import PastaEmissorConector
from ..conectores.registro import PRIORIDADE_RECUPERACAO
from ..conectores.sefaz_consulta import DescobertaImpossivel, SefazConsultaConector
from ..conectores.svrs_portal import CaptchaExigido, SvrsPortalConector
from ..db.modelos import (
    ArquivoImportado, Checkpoint, ChaveConhecida, Documento, Empresa, Execucao, LogExecucao, PastaMonitorada, Serie,
)
from ..fiscal import xmlfiscal as xf
from ..sefaz.transporte import LimiteExcedido
from . import auditoria
from .aplicacao import Aplicacao
from .logs import HUB
from .repositorio import Repositorio

log = logging.getLogger("moxml.motor")

JANELA_EVENTOS_DIAS = 35  # CC-e até 30 dias; cancelamento extemporâneo possível
REVERIFICAR_APOS = timedelta(hours=20)
RETENTAR_SEM_FONTE_APOS = timedelta(hours=6)


@dataclass
class Opcoes:
    gatilho: str = "MANUAL"  # AGENDADA | MANUAL | HISTORICA
    empresas: list[int] | None = None
    modelos: tuple[str, ...] = ("55", "65")
    a_partir_de: dict[tuple[int, str, int], int] | None = None  # (empresa, modelo, série) → número inicial (histórico)
    max_consultas_por_serie: int = 5000
    paralelismo: int = 4


class Orquestrador:
    def __init__(self, app: Aplicacao):
        self.app = app
        self._executando = False

    # ------------------------------------------------------------------ util
    def _log(self, s: Session, exec_id: int | None, nivel: str, msg: str, empresa: str | None = None) -> None:
        HUB.publicar(nivel, msg, exec_id, empresa)
        getattr(log, nivel.lower() if nivel != "AVISO" else "warning", log.info)(msg)
        s.add(LogExecucao(execucao_id=exec_id, nivel=nivel, mensagem=msg[:4000]))

    def _checkpoints(self, s: Session, fonte: str, escopo: str):
        def ler(k: str) -> str | None:
            c = s.scalar(select(Checkpoint).where(Checkpoint.fonte == fonte, Checkpoint.escopo == f"{escopo}|{k}"))
            return c.valor if c else None

        def gravar(k: str, v: str) -> None:
            c = s.scalar(select(Checkpoint).where(Checkpoint.fonte == fonte, Checkpoint.escopo == f"{escopo}|{k}"))
            if c is None:
                s.add(Checkpoint(fonte=fonte, escopo=f"{escopo}|{k}", valor=v))
            else:
                c.valor = v
            s.commit()
        return ler, gravar

    @staticmethod
    def marcar_interrompidas(s: Session) -> int:
        r = s.execute(update(Execucao).where(Execucao.status == "EM_ANDAMENTO")
                      .values(status="INTERROMPIDA", fim=datetime.now(UTC)))
        s.commit()
        return r.rowcount or 0

    # ------------------------------------------------------------------ execução
    def executar(self, opcoes: Opcoes | None = None) -> str:
        opcoes = opcoes or Opcoes()
        lote = str(uuid.uuid4())
        with self.app.sessoes() as s:
            q = select(Empresa).where(Empresa.ativo.is_(True))
            if opcoes.empresas:
                q = q.where(Empresa.id.in_(opcoes.empresas))
            empresas = s.scalars(q.order_by(Empresa.razao_social)).all()
            self._log(s, None, "INFO", f"Lote {lote[:8]} iniciado ({opcoes.gatilho}, modo {self.app.modo}) "
                                       f"para {len(empresas)} empresa(s)")
            s.commit()
        self.importar_pastas(lote)
        tarefas = [(e.id, m) for e in empresas for m in opcoes.modelos
                   if (m == "55" and e.captura_nfe) or (m == "65" and e.captura_nfce)]
        with ThreadPoolExecutor(max_workers=max(1, opcoes.paralelismo), thread_name_prefix="captura") as ex:
            list(ex.map(lambda t: self._processar_seguro(t[0], t[1], lote, opcoes), tarefas))
        with self.app.sessoes() as s:
            for e in empresas:
                auditoria.auditar(s, e.id)
            self._log(s, None, "INFO", f"Lote {lote[:8]} concluído")
            s.commit()
        return lote

    def _processar_seguro(self, empresa_id: int, modelo: str, lote: str, opcoes: Opcoes) -> None:
        with self.app.sessoes() as s:
            emp = s.get(Empresa, empresa_id)
            ex = Execucao(lote=lote, empresa_id=empresa_id, modelo=modelo, gatilho=opcoes.gatilho, modo=self.app.modo,
                          detalhes={})
            s.add(ex)
            s.commit()
            nome = emp.razao_social if emp else str(empresa_id)
            try:
                det = self._processar(s, emp, modelo, ex, opcoes)
                ex.detalhes = det
                ex.quantidade = det.get("recuperados", 0)
                ex.erros = len(det.get("erros", []))
                ex.status = "SUCESSO" if not ex.erros and not det.get("pendencias") else "PARCIAL"
            except Exception as e:  # isolamento: nunca propaga para as outras empresas
                s.rollback()
                ex = s.get(Execucao, ex.id)
                ex.status, ex.erros = "ERRO", (ex.erros or 0) + 1
                ex.detalhes = {**(ex.detalhes or {}), "erro": f"{type(e).__name__}: {e}"}
                self._log(s, ex.id, "ERRO", f"[{nome}/{modelo}] falha: {type(e).__name__}: {e}", nome)
            ex.fim = datetime.now(UTC)
            s.commit()

    def _processar(self, s: Session, emp: Empresa, modelo: str, ex: Execucao, op: Opcoes) -> dict:
        det: dict = {"descobertos": 0, "recuperados": 0, "eventos": 0, "erros": [], "pendencias": [], "fontes": {}}
        tag = f"[{emp.razao_social}/{modelo}]"
        repo = Repositorio(s, self.app.armazenamento, self.app.modo)

        # 1. Certificado
        cert = None
        reg = self.app.certificado_ativo(s, emp.id)
        if reg is None:
            if self.app.modo == "REAL":
                det["pendencias"].append("CERTIFICADO_AUSENTE")
                self._log(s, ex.id, "AVISO", f"{tag} sem certificado A1 ativo: apenas pastas do emissor foram processadas")
                return det
        else:
            cert = self.app.carregar_certificado(reg)
            bloq = impedimentos_bloqueantes(validar_para_empresa(cert, emp.cnpj))
            if bloq:
                det["pendencias"].append("CERTIFICADO_INVALIDO")
                self._log(s, ex.id, "ERRO", f"{tag} certificado inapto: {'; '.join(bloq)}")
                return det

        ler, gravar = self._checkpoints(s, "motor", f"{emp.cnpj}|{modelo}|1")
        ctx = ContextoCaptura(
            empresa_id=emp.id, cnpj=emp.cnpj, uf=emp.uf, modelo=modelo, ambiente=1,
            obter_certificado=lambda: cert,
            cliente_soap=lambda: self.app.cliente_soap(emp.cnpj, cert),
            cliente_http=lambda: self.app.cliente_http(emp.cnpj, cert),
            ler_checkpoint=ler, gravar_checkpoint=gravar,
            log=lambda n, m: self._log(s, ex.id, n, f"{tag} {m}", emp.razao_social),
        )

        # 4. Descoberta
        for c in self.app.registro.com_capacidade(Capacidade.LISTAR, ["sefaz_sae_nfce", "sefaz_consulta", "apisimples"]):
            if c.comercial and not self.app.conector_ativo(s, c.nome, False):
                continue
            disp = c.verificar_disponibilidade(ctx)
            det["fontes"][c.nome] = disp.status.value
            if not disp.ok:
                continue
            try:
                if isinstance(c, SefazConsultaConector):
                    det["descobertos"] += self._descoberta_por_numeracao(s, c, ctx, emp, modelo, ex, op, det)
                else:
                    for d in c.listar_documentos(ctx):
                        repo.registrar_chave(emp, d.chave, c.nome)
                        if d.xml:
                            repo.registrar_xml(d.xml, c.nome, emp, d.chave)
                        det["descobertos"] += 1
                        s.commit()
            except LimiteExcedido as e:
                det["erros"].append(f"{c.nome}: {e}")
                self._log(s, ex.id, "AVISO", f"{tag} {c.nome}: limite da fonte — {e}")
            except DescobertaImpossivel as e:
                det["pendencias"].append(f"{c.nome}: IMPOSSIVEL_PELO_METODO")
                self._log(s, ex.id, "ERRO", f"{tag} {c.nome}: {e}")
            except Exception as e:  # noqa: BLE001
                det["erros"].append(f"{c.nome}: {type(e).__name__}: {e}")
                self._log(s, ex.id, "ERRO", f"{tag} {c.nome}: {type(e).__name__}: {e}")
            s.commit()

        # 5. Recuperação do XML integral
        det["recuperados"] += self._recuperar_pendentes(s, ctx, emp, modelo, ex, det)
        # 6. Eventos
        det["eventos"] += self._atualizar_eventos(s, ctx, emp, modelo, ex, det)
        s.commit()
        self._log(s, ex.id, "INFO", f"{tag} descobertos={det['descobertos']} recuperados={det['recuperados']} "
                                    f"eventos={det['eventos']} erros={len(det['erros'])}")
        return det

    # ------------------------------------------------------------------ descoberta J04/562
    def _descoberta_por_numeracao(self, s: Session, c: SefazConsultaConector, ctx: ContextoCaptura, emp: Empresa,
                                  modelo: str, ex: Execucao, op: Opcoes, det: dict) -> int:
        repo = Repositorio(s, self.app.armazenamento, self.app.modo)
        series = s.scalars(select(Serie).where(Serie.empresa_id == emp.id, Serie.modelo == modelo,
                                               Serie.ambiente == 1, Serie.ativo.is_(True))).all()
        if not series:
            det["pendencias"].append("SEM_SERIE_CADASTRADA")
            self._log(s, ex.id, "AVISO", f"[{emp.razao_social}/{modelo}] nenhuma série: importe um XML semente")
            return 0
        total = 0
        for sr in series:
            inicio = (op.a_partir_de or {}).get((emp.id, modelo, sr.serie)) or (sr.ultimo_numero_identificado or 0) + 1
            ultimo_doc = s.scalar(select(Documento.data_emissao).where(
                Documento.empresa_id == emp.id, Documento.modelo == modelo, Documento.serie == sr.serie)
                .order_by(Documento.numero.desc()).limit(1))
            ref = (ultimo_doc or sr.data_semente or datetime.now(UTC)).replace(tzinfo=None)
            nao_consta: list[int] = []
            maior = 0
            for r in c.descobrir_serie(ctx, sr.serie, inicio, ref, limite=op.max_consultas_por_serie):
                if r.chave:
                    repo.registrar_chave(emp, r.chave, "sefaz_consulta")
                    sit = r.situacao
                    if sit and sit.chave == r.chave:
                        repo.registrar_situacao(emp, r.chave, sit.cstat, sit.situacao, sit.xmotivo)
                        for ev in sit.eventos:
                            repo.registrar_evento_bruto(ev.xml, "sefaz_consulta", emp, ev.protocolo)
                    maior = max(maior, r.numero)
                    total += 1
                    s.commit()
                elif r.cstat == "217":
                    nao_consta.append(r.numero)
            for n in nao_consta:
                if n < maior:
                    auditoria.marcar_nao_consta(s, emp.id, modelo, sr.serie, 1, n,
                                                "consulta oficial (NFeConsultaProtocolo) retornou 217")
            s.commit()
        return total

    # ------------------------------------------------------------------ recuperação
    def _completar_protocolo(self, ctx: ContextoCaptura, rec: XmlRecuperado, chave: str) -> bytes:
        d = xf.ler(rec.xml)
        if d.tipo != xf.TipoXML.NFE_SEM_PROTOCOLO:
            return rec.xml
        cons = self.app.registro.get("sefaz_consulta")
        if cons is None or not cons.suporta(ctx.uf, ctx.modelo).ok:
            return rec.xml
        sit = cons.consultar_situacao(ctx, chave)
        if sit.prot_nfe and sit.chave == chave:
            return xf.montar_nfeproc(rec.xml, sit.prot_nfe)
        return rec.xml

    def _recuperar_pendentes(self, s: Session, ctx: ContextoCaptura, emp: Empresa, modelo: str, ex: Execucao,
                             det: dict) -> int:
        repo = Repositorio(s, self.app.armazenamento, self.app.modo)
        limite = datetime.now(UTC) - RETENTAR_SEM_FONTE_APOS
        pend = s.scalars(select(ChaveConhecida).where(
            ChaveConhecida.empresa_id == emp.id, ChaveConhecida.modelo == modelo,
            or_(ChaveConhecida.status == "PENDENTE",
                (ChaveConhecida.status.in_(["SEM_FONTE", "FALHA"])) & or_(ChaveConhecida.ultima_tentativa.is_(None),
                                                                           ChaveConhecida.ultima_tentativa < limite)))
            .order_by(ChaveConhecida.numero)).all()
        conectores = []
        for c in self.app.registro.com_capacidade(Capacidade.RECUPERAR_XML, PRIORIDADE_RECUPERACAO):
            if c.comercial and not self.app.conector_ativo(s, c.nome, False):
                continue
            if c.verificar_disponibilidade(ctx).ok:
                conectores.append(c)
        recuperados = 0
        inutilizaveis: set[str] = set()
        for cc in pend:
            cc.tentativas += 1
            cc.ultima_tentativa = datetime.now(UTC)
            obtido = False
            ultimo_erro = ""
            for c in conectores:
                if c.nome in inutilizaveis:
                    continue
                try:
                    rec = c.recuperar_xml(ctx, cc.chave)
                    xml = self._completar_protocolo(ctx, rec, cc.chave)
                    r = repo.registrar_xml(xml, c.nome, emp, cc.chave)
                    for ev in rec.eventos:
                        repo.registrar_evento_bruto(ev.xml, c.nome, emp, ev.protocolo)
                    if r.resultado in ("NOVO", "ATUALIZADO", "DUPLICADO") and \
                            s.scalar(select(Documento.tipo_xml).where(Documento.chave == cc.chave)) in ("NFE_AUTORIZADA", "NFE_DENEGADA"):
                        cc.status, cc.mensagem = "RECUPERADA", f"via {c.nome}"
                        recuperados += 1
                        obtido = True
                        break
                    ultimo_erro = f"{c.nome}: {r.resultado} {r.mensagem}"
                except FonteSemDados as e:
                    ultimo_erro = f"{c.nome}: {e}"
                except CaptchaExigido as e:
                    inutilizaveis.add(c.nome)
                    det["pendencias"].append(f"{c.nome}: CAPTCHA — IMPOSSIVEL_PELO_METODO")
                    self._log(s, ex.id, "ERRO", f"[{emp.razao_social}/{modelo}] {e}")
                except LimiteExcedido as e:
                    inutilizaveis.add(c.nome)
                    det["erros"].append(f"{c.nome}: {e}")
                except Exception as e:  # noqa: BLE001
                    ultimo_erro = f"{c.nome}: {type(e).__name__}: {e}"
                    det["erros"].append(f"{cc.chave}: {ultimo_erro}")
            if not obtido:
                cc.status = "SEM_FONTE" if not conectores or all(n in inutilizaveis for n in (c.nome for c in conectores)) \
                    else "FALHA"
                cc.mensagem = (ultimo_erro or "nenhuma fonte disponível para recuperar o XML integral")[:500]
            s.commit()
        if pend and not conectores:
            det["pendencias"].append("SEM_FONTE_DE_XML_INTEGRAL")
        return recuperados

    # ------------------------------------------------------------------ eventos
    def _atualizar_eventos(self, s: Session, ctx: ContextoCaptura, emp: Empresa, modelo: str, ex: Execucao,
                           det: dict) -> int:
        cons = self.app.registro.get("sefaz_consulta")
        if cons is None or not cons.suporta(ctx.uf, modelo).ok or ctx.cliente_soap is None:
            return 0
        repo = Repositorio(s, self.app.armazenamento, self.app.modo)
        agora = datetime.now(UTC)
        docs = s.scalars(select(Documento).where(
            Documento.empresa_id == emp.id, Documento.modelo == modelo, Documento.situacao == "AUTORIZADA",
            Documento.data_emissao >= agora - timedelta(days=JANELA_EVENTOS_DIAS),
            or_(Documento.situacao_verificada_em.is_(None), Documento.situacao_verificada_em < agora - REVERIFICAR_APOS))
        ).all()
        n = 0
        for doc in docs:
            try:
                sit = cons.consultar_situacao(ctx, doc.chave)
            except LimiteExcedido as e:
                det["erros"].append(f"eventos: {e}")
                break
            except Exception as e:  # noqa: BLE001
                det["erros"].append(f"eventos {doc.chave}: {e}")
                continue
            repo.registrar_situacao(emp, doc.chave, sit.cstat, sit.situacao, sit.xmotivo)
            for ev in sit.eventos:
                if repo.registrar_evento_bruto(ev.xml, "sefaz_consulta", emp, ev.protocolo).resultado == "EVENTO":
                    n += 1
            s.commit()
        return n

    # ------------------------------------------------------------------ pastas
    def importar_pastas(self, lote: str | None = None, caminho_unico: str | None = None,
                        empresa_id: int | None = None) -> dict:
        conector = self.app.registro.get("pasta_emissor")
        assert isinstance(conector, PastaEmissorConector)
        res = {"arquivos": 0, "novos": 0, "duplicados": 0, "rejeitados": 0, "incompletos": 0}
        with self.app.sessoes() as s:
            repo = Repositorio(s, self.app.armazenamento, self.app.modo)
            if caminho_unico:
                pastas = [PastaMonitorada(caminho=caminho_unico, empresa_id=empresa_id, recursivo=True)]
            else:
                pastas = s.scalars(select(PastaMonitorada).where(PastaMonitorada.ativo.is_(True))).all()

            def ja_visto(caminho: str, tamanho: int, mtime: float) -> bool:
                return s.scalar(select(ArquivoImportado.id).where(
                    ArquivoImportado.caminho == caminho, ArquivoImportado.tamanho == tamanho,
                    ArquivoImportado.mtime == mtime)) is not None

            for pm in pastas:
                emp = s.get(Empresa, pm.empresa_id) if pm.empresa_id else None
                try:
                    for arq in conector.varrer(pm.caminho, pm.recursivo, ja_visto):
                        res["arquivos"] += 1
                        if arq.conteudo is None:
                            res["incompletos"] += 1
                            continue
                        r = repo.registrar_xml(arq.conteudo, "pasta_emissor", emp)
                        chave_res = {"NOVO": "novos", "ATUALIZADO": "novos", "EVENTO": "novos", "INUTILIZACAO": "novos",
                                     "DUPLICADO": "duplicados", "REJEITADO": "rejeitados"}.get(r.resultado, "novos")
                        res[chave_res] += 1
                        if r.resultado == "REJEITADO":
                            self._log(s, None, "AVISO", f"pasta: {arq.caminho} rejeitado — {r.mensagem}")
                        h = xf.sha256(arq.conteudo)
                        ai = s.scalar(select(ArquivoImportado).where(ArquivoImportado.caminho == arq.caminho,
                                                                     ArquivoImportado.hash_sha256 == h))
                        if ai is None:
                            s.add(ArquivoImportado(caminho=arq.caminho, tamanho=arq.tamanho, mtime=arq.mtime,
                                                   hash_sha256=h, resultado=r.resultado))
                        else:
                            ai.tamanho, ai.mtime, ai.resultado = arq.tamanho, arq.mtime, r.resultado
                        s.commit()
                    if pm.id:
                        pm.ultima_varredura = datetime.now(UTC)
                except FileNotFoundError as e:
                    self._log(s, None, "ERRO", f"pasta monitorada indisponível: {e}")
                s.commit()
        return res


def executar_com_trava(orq: Orquestrador, opcoes: Opcoes) -> str | None:
    """Evita execuções sobrepostas dentro do mesmo processo."""
    if orq._executando:
        return None
    orq._executando = True
    t0 = time.monotonic()
    try:
        return orq.executar(opcoes)
    finally:
        orq._executando = False
        log.info("execução levou %.1fs", time.monotonic() - t0)
