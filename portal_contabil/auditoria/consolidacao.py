"""Consolida achados repetidos por documento em um achado por regra.

O relatório para o cliente fica legível ("7 NFS-e com retenção indevida") e o índice
de conformidade não é distorcido pela quantidade de notas. O detalhe nota a nota
continua disponível em `Resultado.achados_detalhados` e na aba do Excel.
"""
from __future__ import annotations

import re
from collections import defaultdict

from ..modelos import SEVERIDADES, Achado
from ..util import ZERO, moeda, q2

LIMIAR = 3
TITULO = {
    "DOC001": "documento(s) sem protocolo de autorização",
    "DOC002": "documento(s) com uso denegado",
    "DOC003": "documento(s) com chave de acesso inválida",
    "DOC004": "documento(s) com CNPJ/CPF inválido",
    "DOC005": "numeração(ões) emitida(s) em duplicidade",
    "NFE001": "nota(s) com soma dos itens diferente do total",
    "NFE002": "nota(s) com valor total (vNF) inconsistente",
    "NFE003": "nota(s) com CFOP incompatível com o tipo de operação",
    "NFE004": "nota(s) com CFOP incompatível com a UF de destino",
    "NFE005": "nota(s) com CRT incompatível com CST/CSOSN",
    "NFS001": "NFS-e com retenção federal sobre prestador do Simples Nacional",
    "NFS002": "NFS-e com alíquota de retenção fora do padrão",
    "NFS003": "NFS-e com alíquota de ISS fora da faixa de 2% a 5%",
    "NFS004": "NFS-e com valor líquido inconsistente",
}
_ROTULO = re.compile(r"^((?:NF-e|NFC-e|NFS-e) nº [^\s:]+(?: série [^\s:]+)?)")
_ORDEM = {s: i for i, s in enumerate(SEVERIDADES)}


def _rotulo(a: Achado) -> str:
    m = _ROTULO.match(a.titulo)
    return m.group(1) if m else a.titulo


def consolidar(achados: list[Achado]) -> list[Achado]:
    grupos: dict[str, list[Achado]] = defaultdict(list)
    for a in achados:
        if a.codigo in TITULO:
            grupos[a.codigo].append(a)

    saida: list[Achado] = []
    feitos: set[str] = set()
    for a in achados:
        if a.valor is not None:
            a.valor = q2(a.valor)
        lista = grupos.get(a.codigo)
        if not lista or len(lista) < LIMIAR:
            saida.append(a)
            continue
        if a.codigo in feitos:
            continue
        feitos.add(a.codigo)
        valores = [x.valor for x in lista if x.valor is not None]
        exemplos = "; ".join(_rotulo(x) + (f" ({moeda(x.valor)})" if x.valor else "") for x in lista[:10])
        saida.append(Achado(
            codigo=a.codigo,
            severidade=min((x.severidade for x in lista), key=_ORDEM.__getitem__),
            categoria=a.categoria,
            titulo=f"{len(lista)} {TITULO[a.codigo]}",
            descricao=f"Ocorrências: {exemplos}{' …' if len(lista) > 10 else ''}. Exemplo: {lista[0].descricao}",
            recomendacao=a.recomendacao,
            base_legal=a.base_legal,
            referencia=f"{len(lista)} documentos (detalhe na aba 'Achados detalhados')",
            valor=q2(sum(valores, ZERO)) if valores else None,
            ocorrencias=len(lista),
        ))
    return saida
