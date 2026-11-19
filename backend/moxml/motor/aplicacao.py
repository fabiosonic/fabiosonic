"""Contêiner de serviços: configuração, banco, cofre, armazenamento, conectores e fábricas de clientes."""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..certificados.a1 import CertificadoA1, carregar_pfx
from ..config import Configuracoes, Modo
from ..conectores.apisimples import ApiSimplesConector
from ..conectores.pastas import PastaEmissorConector
from ..conectores.registro import Registro
from ..conectores.sefaz_consulta import SefazConsultaConector
from ..conectores.sefaz_sae import SefazSaeConector
from ..conectores.svrs_portal import SvrsPortalConector
from ..db.modelos import Certificado, ConectorConfig, RegistroFonte
from ..db.sessao import aplicar_migrations, fabrica
from ..seguranca.cofre import Cofre
from ..sefaz.transporte import ClienteSoap, LimitadorTaxa
from .armazenamento import Armazenamento

_RE_CSTAT = re.compile(rb"<cStat>(\d{3})</cStat>")
_RE_MOTIVO = re.compile(rb"<xMotivo>([^<]{0,400})</xMotivo>")


@dataclass
class Aplicacao:
    cfg: Configuracoes
    sessoes: sessionmaker[Session]
    cofre: Cofre
    armazenamento: Armazenamento
    registro: Registro
    limitador: LimitadorTaxa
    # Fábricas de transporte: em SIMULADO apontam para o laboratório; em REAL, para a rede com mTLS.
    transporte_soap: Callable[[str], httpx.BaseTransport | None] = lambda _cnpj: None
    transporte_http: Callable[[str], httpx.BaseTransport | None] = lambda _cnpj: None
    _cache_cert: dict[str, CertificadoA1] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    @property
    def modo(self) -> str:
        return self.cfg.modo.value

    # ----------------------------------------------------------------- certificados
    def certificado_ativo(self, s: Session, empresa_id: int) -> Certificado | None:
        return s.scalar(select(Certificado).where(Certificado.empresa_id == empresa_id, Certificado.ativo.is_(True))
                        .order_by(Certificado.validade.desc()))

    def carregar_certificado(self, reg: Certificado) -> CertificadoA1:
        with self._lock:
            if reg.impressao_digital in self._cache_cert:
                return self._cache_cert[reg.impressao_digital]
        cert = carregar_pfx(self.cofre.ler(reg.referencia_armazenamento_seguro),
                            self.cofre.ler_texto(reg.referencia_senha))
        with self._lock:
            self._cache_cert[reg.impressao_digital] = cert
        return cert

    def limpar_cache_certificados(self) -> None:
        with self._lock:
            self._cache_cert.clear()

    # ----------------------------------------------------------------- clientes
    def cliente_soap(self, cnpj: str, cert: CertificadoA1 | None) -> ClienteSoap:
        transp = self.transporte_soap(cnpj)
        if transp is not None:
            return ClienteSoap(None, self.cfg.timeout_segundos, self.cfg.retentativas, self.limitador, transport=transp,
                               dormir=lambda _s: None, registrar=self._registrador(cnpj))
        if self.cfg.modo != Modo.REAL:
            raise RuntimeError("modo SIMULADO sem transporte de laboratório configurado")
        if cert is None:
            raise RuntimeError("certificado A1 obrigatório para acesso real")
        return ClienteSoap(cert.contexto_ssl(self.cfg.ca_bundle), self.cfg.timeout_segundos, self.cfg.retentativas,
                           self.limitador, registrar=self._registrador(cnpj))

    def _registrador(self, cnpj: str):  # noqa: ANN202
        """Auditoria de chamadas: guarda serviço, cStat e xMotivo (nunca o envelope completo)."""
        def registrar(servico: str, _req: bytes, resp: bytes | None, erro: str | None) -> None:
            cstat = xmotivo = None
            if resp:
                m = _RE_CSTAT.search(resp)
                cstat = m.group(1).decode() if m else None
                m = _RE_MOTIVO.search(resp)
                xmotivo = m.group(1).decode("utf-8", "replace")[:300] if m else None
            try:
                with self.sessoes() as s:
                    s.add(RegistroFonte(fonte="sefaz", servico=servico, cnpj=cnpj, cstat=cstat, xmotivo=xmotivo,
                                        erro=erro, modo=self.modo))
                    s.commit()
            except Exception:  # noqa: BLE001 - auditoria não pode derrubar a captura
                pass
        return registrar

    def cliente_http(self, cnpj: str, cert: CertificadoA1 | None) -> httpx.Client:
        transp = self.transporte_http(cnpj)
        cab = {"User-Agent": "MO-XML-Captador/1.0 (+contribuinte; uso com certificado do emitente)"}
        if transp is not None:
            return httpx.Client(transport=transp, timeout=self.cfg.timeout_segundos, headers=cab)
        if self.cfg.modo != Modo.REAL or cert is None:
            raise RuntimeError("certificado A1 obrigatório para acesso real ao portal")
        return httpx.Client(verify=cert.contexto_ssl(self.cfg.ca_bundle), timeout=self.cfg.timeout_segundos,
                            headers=cab)

    def conector_ativo(self, s: Session, nome: str, padrao: bool) -> bool:
        c = s.scalar(select(ConectorConfig).where(ConectorConfig.nome == nome))
        return padrao if c is None else c.ativo


def criar_registro(cfg: Configuracoes, cofre: Cofre, apisimples_transport: httpx.BaseTransport | None = None) -> Registro:
    extra = str(cfg.home / "catalogo_local.json")

    def chave_emitente(cnpj: str) -> str | None:
        nome = f"apisimples-emitente-{cnpj}"
        return cofre.ler_texto(nome) if cofre.existe(nome) else None

    def chave_conta() -> str | None:
        return cofre.ler_texto("apisimples-conta") if cofre.existe("apisimples-conta") else None

    conectores = [
        SefazSaeConector(extra),
        SefazConsultaConector(catalogo_extra=extra),
        SvrsPortalConector(extra),
        PastaEmissorConector(),
        ApiSimplesConector(cfg.apisimples_base_url, chave_emitente, ativo=cfg.apisimples_ativo,
                           transport=apisimples_transport, chave_conta=chave_conta),
    ]
    return Registro({c.nome: c for c in conectores})


def criar_aplicacao(cfg: Configuracoes, migrar: bool = True) -> Aplicacao:
    cfg.garantir_pastas()
    if migrar:
        aplicar_migrations(cfg.url_banco)
    cofre = Cofre(cfg.pasta_cofre)
    app = Aplicacao(cfg=cfg, sessoes=fabrica(cfg.url_banco), cofre=cofre, armazenamento=Armazenamento(cfg.pasta_xml),
                    registro=criar_registro(cfg, cofre),
                    limitador=LimitadorTaxa(por_minuto={"dfe-portal.svrs.rs.gov.br": 12}, padrao_por_minuto=30)
                    if cfg.modo == Modo.REAL else LimitadorTaxa(padrao_por_minuto=1_000_000))
    if cfg.modo == Modo.SIMULADO:
        from ..simulador.sefaz_fake import laboratorio_padrao

        lab = laboratorio_padrao(app)
        app.transporte_soap = lambda _c: lab.transport()
        app.transporte_http = lambda _c: lab.transport()
    return app
