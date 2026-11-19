"""Certificados digitais A1 (PFX/P12) ICP-Brasil.

- Leitura do PFX com senha (erro claro para senha incorreta).
- Identificação do titular e do CNPJ (OID ICP-Brasil 2.16.76.1.3.3 no SubjectAltName,
  com fallback para o padrão "RAZAO SOCIAL:CNPJ" do CN).
- Verificação de validade e correspondência com o CNPJ da empresa.
- Criação de ``ssl.SSLContext`` para TLS com autenticação de cliente (mTLS), sem
  desabilitar a verificação do servidor.
"""

from __future__ import annotations

import os
import re
import ssl
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

OID_CNPJ = x509.ObjectIdentifier("2.16.76.1.3.3")
OID_CPF_PF = x509.ObjectIdentifier("2.16.76.1.3.1")
OID_RESPONSAVEL = x509.ObjectIdentifier("2.16.76.1.3.2")


class ErroCertificado(ValueError):
    pass


class SenhaIncorreta(ErroCertificado):
    pass


@dataclass
class InfoCertificado:
    titular: str
    cnpj: str | None
    cpf: str | None
    emissor: str
    serial: str
    valido_de: datetime
    valido_ate: datetime
    impressao_digital_sha256: str
    icp_brasil: bool

    def dias_para_vencer(self, agora: datetime | None = None) -> int:
        agora = agora or datetime.now(UTC)
        return (self.valido_ate - agora).days

    def vencido(self, agora: datetime | None = None) -> bool:
        agora = agora or datetime.now(UTC)
        return agora > self.valido_ate or agora < self.valido_de

    @property
    def status(self) -> str:
        if self.vencido():
            return "VENCIDO"
        if self.dias_para_vencer() <= 30:
            return "VENCENDO"
        return "VALIDO"


@dataclass
class CertificadoA1:
    pfx: bytes
    senha: str
    chave_privada: object
    certificado: x509.Certificate
    cadeia: list[x509.Certificate]
    info: InfoCertificado

    def pem_certificado(self) -> bytes:
        partes = [self.certificado.public_bytes(serialization.Encoding.PEM)]
        partes += [c.public_bytes(serialization.Encoding.PEM) for c in self.cadeia]
        return b"".join(partes)

    def pem_chave(self) -> bytes:
        return self.chave_privada.private_bytes(  # type: ignore[attr-defined]
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )

    def contexto_ssl(self, ca_bundle: Path | None = None) -> ssl.SSLContext:
        """SSLContext com o A1 como certificado de cliente.

        A verificação do servidor permanece obrigatória (CERT_REQUIRED + hostname).
        Os servidores SEFAZ usam cadeias ICP-Brasil/AC públicas: informe ``ca_bundle``
        com as ACs necessárias quando a cadeia não estiver no repositório do sistema."""
        ctx = ssl.create_default_context(cafile=str(ca_bundle) if ca_bundle else None)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        # load_cert_chain exige arquivos: gravação temporária 0600 removida imediatamente
        with tempfile.TemporaryDirectory(prefix="moxml-") as d:
            cp, kp = os.path.join(d, "c.pem"), os.path.join(d, "k.pem")
            for caminho, dados in ((cp, self.pem_certificado()), (kp, self.pem_chave())):
                fd = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as f:
                    f.write(dados)
            ctx.load_cert_chain(cp, kp)
        assert ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname
        return ctx


def _apenas_digitos(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def _alfanum(s: str) -> str:
    """CNPJ pode ser alfanumérico (IN RFB 2.229/2024)."""
    return re.sub(r"[^0-9A-Za-z]", "", s or "").upper()


def _other_names(cert: x509.Certificate) -> dict[str, bytes]:
    try:
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    except x509.ExtensionNotFound:
        return {}
    return {on.type_id.dotted_string: on.value for on in san.get_values_for_type(x509.OtherName)}


def _decodificar_valor_asn1(valor: bytes) -> str:
    """Extrai o texto de um valor DER simples (OCTET/PRINTABLE/UTF8 STRING), possivelmente
    encapsulado em [0] EXPLICIT."""
    v = valor
    for _ in range(3):
        if len(v) < 2:
            break
        tag, tam = v[0], v[1]
        ini = 2
        if tam & 0x80:
            n = tam & 0x7F
            tam = int.from_bytes(v[2:2 + n], "big")
            ini = 2 + n
        conteudo = v[ini:ini + tam]
        if tag in (0xA0,):  # contexto [0] — desce um nível
            v = conteudo
            continue
        if tag in (0x04, 0x13, 0x0C, 0x16):
            return conteudo.decode("latin-1", errors="ignore")
        break
    return v.decode("latin-1", errors="ignore")


def extrair_info(cert: x509.Certificate) -> InfoCertificado:
    cn = ""
    attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    if attrs:
        cn = str(attrs[0].value)
    outros = _other_names(cert)
    cnpj = None
    if OID_CNPJ.dotted_string in outros:
        cnpj = _alfanum(_decodificar_valor_asn1(outros[OID_CNPJ.dotted_string]))[:14] or None
    if not cnpj and ":" in cn:
        cand = _alfanum(cn.rsplit(":", 1)[1])
        cnpj = cand if len(cand) == 14 else None
    cpf = None
    if OID_CPF_PF.dotted_string in outros:
        dado = _apenas_digitos(_decodificar_valor_asn1(outros[OID_CPF_PF.dotted_string]))
        cpf = dado[8:19] if len(dado) >= 19 else None
    titular = cn.rsplit(":", 1)[0] if ":" in cn else cn
    emissor_attrs = cert.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
    emissor = str(emissor_attrs[0].value) if emissor_attrs else cert.issuer.rfc4514_string()
    org = " ".join(str(a.value) for a in cert.issuer.get_attributes_for_oid(NameOID.ORGANIZATION_NAME))
    return InfoCertificado(
        titular=titular,
        cnpj=cnpj,
        cpf=cpf,
        emissor=emissor,
        serial=format(cert.serial_number, "x"),
        valido_de=cert.not_valid_before_utc,
        valido_ate=cert.not_valid_after_utc,
        impressao_digital_sha256=cert.fingerprint(hashes.SHA256()).hex(),
        icp_brasil="ICP-Brasil" in org or "ICP-Brasil" in cert.issuer.rfc4514_string(),
    )


def carregar_pfx(pfx: bytes, senha: str) -> CertificadoA1:
    try:
        chave, cert, cadeia = pkcs12.load_key_and_certificates(pfx, senha.encode("utf-8") if senha else None)
    except ValueError as e:
        msg = str(e).lower()
        if "password" in msg or "mac" in msg or "decrypt" in msg:
            raise SenhaIncorreta("senha do certificado incorreta") from None
        raise ErroCertificado(f"arquivo PFX inválido: {e}") from None
    if cert is None or chave is None:
        raise ErroCertificado("PFX sem certificado ou sem chave privada")
    return CertificadoA1(pfx, senha, chave, cert, list(cadeia or []), extrair_info(cert))


def validar_para_empresa(cert: CertificadoA1, cnpj_empresa: str, agora: datetime | None = None) -> list[str]:
    """Retorna lista de impedimentos (vazia = apto)."""
    problemas: list[str] = []
    if cert.info.vencido(agora):
        problemas.append(f"certificado fora da validade ({cert.info.valido_de:%d/%m/%Y} a {cert.info.valido_ate:%d/%m/%Y})")
    if not cert.info.cnpj:
        problemas.append("certificado não contém CNPJ (e-CNPJ exigido)")
    elif _alfanum(cnpj_empresa) != cert.info.cnpj:
        # Mesma raiz (8 primeiros dígitos) é aceita: o e-CNPJ da matriz atende filiais em vários serviços,
        # mas é sinalizado para conferência manual.
        if cnpj_empresa[:8] == cert.info.cnpj[:8]:
            problemas.append(f"AVISO: certificado da matriz/filial {cert.info.cnpj} (mesma raiz) — confirmar aceitação pela fonte")
        else:
            problemas.append(f"CNPJ do certificado ({cert.info.cnpj}) difere do CNPJ da empresa ({cnpj_empresa})")
    return problemas


def impedimentos_bloqueantes(problemas: list[str]) -> list[str]:
    return [p for p in problemas if not p.startswith("AVISO")]
