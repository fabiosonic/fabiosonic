"""Registro de XMLs no banco + arquivo, com validação, deduplicação e eventos.

Regra de ouro: só é "recuperado" o documento cujo XML integral foi validado
(``DocumentoXML.e_xml_integral``). Consulta de situação atualiza status, nunca cria XML.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.modelos import ChaveConhecida, Documento, Empresa, Evento, Inutilizacao, Serie
from ..fiscal import chave as chv
from ..fiscal import xmlfiscal as xf
from ..fiscal.xmlfiscal import TipoXML
from .armazenamento import Armazenamento, caminho_relativo, nome_pasta, subpasta_modelo

PRIORIDADE_TIPO = {TipoXML.NFE_AUTORIZADA: 3, TipoXML.NFE_DENEGADA: 3, TipoXML.NFE_SEM_PROTOCOLO: 1}


@dataclass
class ResultadoRegistro:
    resultado: str  # NOVO | DUPLICADO | ATUALIZADO | CONFLITO | REJEITADO | EVENTO | INUTILIZACAO | RESUMO
    mensagem: str = ""
    chave: str | None = None
    documento_id: int | None = None


def _agora() -> datetime:
    return datetime.now(UTC)


class Repositorio:
    def __init__(self, sessao: Session, armazenamento: Armazenamento, modo: str):
        self.s = sessao
        self.arm = armazenamento
        self.modo = modo

    # ------------------------------------------------------------------ helpers
    def _pasta(self, emp: Empresa) -> str:
        return nome_pasta(emp.razao_social, emp.cnpj, emp.nome_pasta)

    def empresa_por_cnpj(self, cnpj: str | None) -> Empresa | None:
        if not cnpj:
            return None
        return self.s.scalar(select(Empresa).where(Empresa.cnpj == cnpj.zfill(14)))

    def _serie(self, emp_id: int, modelo: str, serie: int, ambiente: int) -> Serie:
        sr = self.s.scalar(select(Serie).where(Serie.empresa_id == emp_id, Serie.modelo == modelo,
                                               Serie.serie == serie, Serie.ambiente == ambiente))
        if sr is None:
            sr = Serie(empresa_id=emp_id, modelo=modelo, serie=serie, ambiente=ambiente)
            self.s.add(sr)
            self.s.flush()
        return sr

    def _atualizar_serie(self, emp_id: int, modelo: str, serie: int, ambiente: int, numero: int, recuperado: bool) -> None:
        sr = self._serie(emp_id, modelo, serie, ambiente)
        sr.ultimo_numero_identificado = max(sr.ultimo_numero_identificado or 0, numero)
        if recuperado:
            sr.ultimo_numero_recuperado = max(sr.ultimo_numero_recuperado or 0, numero)
        if sr.numero_inicial_controle is None or numero < sr.numero_inicial_controle:
            sr.numero_inicial_controle = numero

    # ------------------------------------------------------------------ chaves
    def registrar_chave(self, emp: Empresa, chave: str, origem: str, ambiente: int = 1) -> ChaveConhecida:
        ck = chv.analisar(chave)
        if ck.cnpj != emp.cnpj.zfill(14):
            raise ValueError(f"chave {chave} não pertence ao CNPJ {emp.cnpj}")
        cc = self.s.scalar(select(ChaveConhecida).where(ChaveConhecida.chave == ck.chave))
        if cc is None:
            cc = ChaveConhecida(empresa_id=emp.id, chave=ck.chave, modelo=ck.modelo, serie=ck.serie,
                                numero=ck.numero, ambiente=ambiente, origem=origem, status="PENDENTE")
            existe = self.s.scalar(select(Documento.id).where(Documento.chave == ck.chave))
            if existe:
                cc.status = "RECUPERADA"
            self.s.add(cc)
            self._atualizar_serie(emp.id, ck.modelo, ck.serie, ambiente, ck.numero, False)
            self.s.flush()
        return cc

    def registrar_situacao(self, emp: Empresa, chave: str, cstat: str, situacao: str, xmotivo: str) -> None:
        cc = self.s.scalar(select(ChaveConhecida).where(ChaveConhecida.chave == chave))
        if cc:
            cc.situacao_sefaz, cc.cstat_situacao, cc.mensagem = situacao, cstat, xmotivo[:500]
        doc = self.s.scalar(select(Documento).where(Documento.chave == chave))
        if doc:
            doc.situacao_verificada_em = _agora()
            if situacao == "CANCELADA":
                doc.situacao = "CANCELADA"

    # ------------------------------------------------------------------ XML
    def registrar_xml(self, conteudo: bytes, origem: str, empresa: Empresa | None = None,
                      chave_esperada: str | None = None) -> ResultadoRegistro:
        d = xf.ler(conteudo)
        if d.tipo in (TipoXML.INVALIDO, TipoXML.INCOMPLETO):
            return ResultadoRegistro("REJEITADO", f"{d.tipo}: " + "; ".join(p.mensagem for p in d.problemas))
        if chave_esperada and d.chave and d.chave != chave_esperada:
            return ResultadoRegistro("REJEITADO", f"XML retornado ({d.chave}) não corresponde à chave pedida", d.chave)
        emp = empresa or self.empresa_por_cnpj(d.cnpj_emitente)
        if emp is None:
            return ResultadoRegistro("REJEITADO", f"emitente {d.cnpj_emitente} não é empresa cadastrada", d.chave)
        if d.cnpj_emitente and d.cnpj_emitente.zfill(14) != emp.cnpj and d.tipo != TipoXML.EVENTO:
            return ResultadoRegistro("REJEITADO", f"CNPJ do XML ({d.cnpj_emitente}) incompatível com {emp.cnpj}", d.chave)
        if d.tipo in (TipoXML.EVENTO, TipoXML.EVENTO_SEM_PROTOCOLO):
            return self._registrar_evento(emp, d, origem)
        if d.tipo == TipoXML.INUTILIZACAO:
            return self._registrar_inut(emp, d, origem)
        if d.tipo in (TipoXML.RESUMO_NFE, TipoXML.RESUMO_EVENTO):
            if d.chave and chv.valida(d.chave):
                self.registrar_chave(emp, d.chave, f"resumo:{origem}")
            return ResultadoRegistro("RESUMO", "resumo registrado como chave conhecida (XML integral pendente)", d.chave)
        return self._registrar_nfe(emp, d, origem)

    def _registrar_nfe(self, emp: Empresa, d: xf.DocumentoXML, origem: str) -> ResultadoRegistro:
        graves = [p for p in d.problemas if p.grave]
        if graves:
            return ResultadoRegistro("REJEITADO", "; ".join(p.mensagem for p in graves), d.chave)
        existente = self.s.scalar(select(Documento).where(
            Documento.cnpj_emitente == emp.cnpj, Documento.ambiente == d.ambiente,
            Documento.modelo == d.modelo, Documento.chave == d.chave))
        if existente and existente.hash_sha256 == d.sha256:
            return ResultadoRegistro("DUPLICADO", "mesmo XML já registrado", d.chave, existente.id)
        if existente and PRIORIDADE_TIPO.get(TipoXML(existente.tipo_xml), 0) >= PRIORIDADE_TIPO.get(d.tipo, 0):
            # Já existe versão igual ou melhor (ex.: autorizada). Guarda o arquivo divergente apenas para auditoria.
            rel = caminho_relativo(self._pasta(emp), d.data_emissao, subpasta_modelo(d.modelo or "55"),
                                   f"{d.chave}-divergente.xml")
            g = self.arm.gravar(rel, d.conteudo)
            return ResultadoRegistro("CONFLITO" if d.tipo == TipoXML(existente.tipo_xml) else "DUPLICADO",
                                     f"já existe XML {existente.tipo_xml}; divergente guardado em {self.arm.relativo(g.caminho)}",
                                     d.chave, existente.id)
        sufixo = "procNFe" if d.e_xml_integral else "NFe-sem-protocolo"
        rel = caminho_relativo(self._pasta(emp), d.data_emissao, subpasta_modelo(d.modelo or "55"), f"{d.chave}-{sufixo}.xml")
        g = self.arm.gravar(rel, d.conteudo)
        situacao = {TipoXML.NFE_AUTORIZADA: "AUTORIZADA", TipoXML.NFE_DENEGADA: "DENEGADA"}.get(d.tipo, "SEM_PROTOCOLO")
        cancel = self.s.scalar(select(Evento.id).where(Evento.chave == d.chave, Evento.tipo_evento.in_(xf.TP_EVENTO_CANCELAMENTO)))
        if cancel and situacao == "AUTORIZADA":
            situacao = "CANCELADA"
        campos = dict(
            empresa_id=emp.id, chave=d.chave, cnpj_emitente=emp.cnpj, ambiente=d.ambiente or 1, modelo=d.modelo,
            serie=d.serie, numero=d.numero, data_emissao=d.data_emissao, valor=d.valor, tp_nf=d.tp_nf,
            situacao=situacao, tipo_xml=d.tipo.value, protocolo=d.protocolo, origem=origem,
            caminho_xml=self.arm.relativo(g.caminho), hash_sha256=d.sha256, assinatura_ok=d.assinatura_ok,
            problemas=[p.mensagem for p in d.problemas] or None, modo=self.modo,
        )
        if existente:
            for k, v in campos.items():
                setattr(existente, k, v)
            doc, res = existente, "ATUALIZADO"
        else:
            doc = Documento(**campos)
            self.s.add(doc)
            res = "NOVO"
        self._atualizar_serie(emp.id, d.modelo, d.serie, d.ambiente or 1, d.numero, d.e_xml_integral)
        cc = self.s.scalar(select(ChaveConhecida).where(ChaveConhecida.chave == d.chave))
        if cc and cc.situacao_sefaz:
            # situação já confirmada pela consulta oficial durante a descoberta
            doc.situacao_verificada_em = _agora()
            if cc.situacao_sefaz == "CANCELADA":
                doc.situacao = "CANCELADA"
        if cc and d.e_xml_integral:
            cc.status = "RECUPERADA"
        elif cc is None and not d.e_xml_integral:
            self.registrar_chave(emp, d.chave, f"xml-sem-protocolo:{origem}", d.ambiente or 1)
        self.s.flush()
        return ResultadoRegistro(res, sufixo, d.chave, doc.id)

    def _registrar_evento(self, emp: Empresa, d: xf.DocumentoXML, origem: str, protocolo: str | None = None) -> ResultadoRegistro:
        if not d.chave or not d.tp_evento:
            return ResultadoRegistro("REJEITADO", "evento sem chave ou tipo")
        if chv.analisar(d.chave).cnpj != emp.cnpj:
            return ResultadoRegistro("REJEITADO", "evento de NF-e de outro emitente", d.chave)
        amb = d.ambiente or 1
        existente = self.s.scalar(select(Evento).where(Evento.chave == d.chave, Evento.tipo_evento == d.tp_evento,
                                                       Evento.sequencia == (d.seq_evento or 1), Evento.ambiente == amb))
        if existente and existente.hash_sha256 == d.sha256:
            return ResultadoRegistro("DUPLICADO", "evento já registrado", d.chave)
        if existente and existente.protocolo and d.tipo == TipoXML.EVENTO_SEM_PROTOCOLO:
            return ResultadoRegistro("DUPLICADO", "evento com protocolo já registrado", d.chave)
        data = d.data_evento
        rel = caminho_relativo(self._pasta(emp), data, "EVENTOS",
                               f"{d.chave}-{d.tp_evento}-{d.seq_evento or 1:02d}-procEventoNFe.xml")
        g = self.arm.gravar(rel, d.conteudo)
        campos = dict(empresa_id=emp.id, chave=d.chave, tipo_evento=d.tp_evento, descricao=d.descricao_evento,
                      sequencia=d.seq_evento or 1, ambiente=amb, protocolo=d.protocolo or protocolo, cstat=d.cstat,
                      data_evento=d.data_evento, caminho_xml=self.arm.relativo(g.caminho), hash_sha256=d.sha256,
                      origem=origem, modo=self.modo)
        if existente:
            for k, v in campos.items():
                setattr(existente, k, v)
        else:
            self.s.add(Evento(**campos))
        if d.tp_evento in xf.TP_EVENTO_CANCELAMENTO and (d.protocolo or protocolo):
            doc = self.s.scalar(select(Documento).where(Documento.chave == d.chave))
            if doc:
                doc.situacao = "CANCELADA"
        self.s.flush()
        return ResultadoRegistro("EVENTO", f"{d.descricao_evento or d.tp_evento}", d.chave)

    def registrar_evento_bruto(self, conteudo: bytes, origem: str, emp: Empresa, protocolo: str | None) -> ResultadoRegistro:
        d = xf.ler(conteudo)
        if d.tipo not in (TipoXML.EVENTO, TipoXML.EVENTO_SEM_PROTOCOLO):
            return ResultadoRegistro("REJEITADO", f"não é evento: {d.tipo}")
        return self._registrar_evento(emp, d, origem, protocolo)

    def _registrar_inut(self, emp: Empresa, d: xf.DocumentoXML, origem: str) -> ResultadoRegistro:
        amb = d.ambiente or 1
        existente = self.s.scalar(select(Inutilizacao).where(
            Inutilizacao.empresa_id == emp.id, Inutilizacao.modelo == d.modelo, Inutilizacao.serie == d.serie,
            Inutilizacao.ambiente == amb, Inutilizacao.numero_inicial == d.numero,
            Inutilizacao.numero_final == d.numero_final))
        if existente:
            return ResultadoRegistro("DUPLICADO", "inutilização já registrada")
        rel = caminho_relativo(self._pasta(emp), datetime(d.ano_inut or 2000, 1, 1) if not d.data_autorizacao else d.data_autorizacao,
                               "EVENTOS", f"INUT-{d.modelo}-{d.serie:03d}-{d.numero:09d}-{d.numero_final:09d}-procInutNFe.xml")
        g = self.arm.gravar(rel, d.conteudo)
        self.s.add(Inutilizacao(empresa_id=emp.id, modelo=d.modelo, serie=d.serie, ambiente=amb, ano=d.ano_inut or 0,
                                numero_inicial=d.numero, numero_final=d.numero_final, protocolo=d.protocolo,
                                caminho_xml=self.arm.relativo(g.caminho), hash_sha256=d.sha256, origem=origem))
        self.s.flush()
        return ResultadoRegistro("INUTILIZACAO", f"faixa {d.numero}-{d.numero_final}")
