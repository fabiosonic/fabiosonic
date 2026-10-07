"""Calendário de obrigações por cliente.

As obrigações vêm SÓ de normas CONFERIDAS que tenham o parâmetro `obrigacoes`:
    obrigacoes:
      - {codigo: DAS, descricao: "...", dia: <n>, meses_apos_competencia: 1, regimes: [SIMPLES]}
A aplicabilidade também respeita `aplica_se` da norma (regime, UF, município, CNAE).

Ajuste de vencimento (regra do ESCRITÓRIO, não legal): sábado, domingo ou feriado (lista em
`calendario.feriados` do config) -> antecipa para o dia útil anterior. Alertas: N dias antes
(config `calendario.dias_alerta`, padrão [3, 0]).
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


class CalendarioInvalido(ValueError):
    pass


@dataclass
class Vencimento:
    cnpj: str
    apelido: str
    codigo: str
    descricao: str
    competencia: str
    vencimento_legal: date
    vencimento: date
    norma: str


def dia_util_anterior(d: date, feriados: set[date]) -> date:
    while d.weekday() >= 5 or d in feriados:
        d -= timedelta(days=1)
    return d


def _data_vencimento(competencia: str, dia: int, meses_apos: int) -> date:
    ano, mes = map(int, competencia.split("-"))
    mes += meses_apos
    ano += (mes - 1) // 12
    mes = (mes - 1) % 12 + 1
    ultimo = calendar.monthrange(ano, mes)[1]
    if not 1 <= dia <= 31:
        raise CalendarioInvalido(f"dia de vencimento inválido: {dia}")
    return date(ano, mes, min(dia, ultimo))


def obrigacoes_conferidas(catalogo) -> list[tuple[object, dict]]:
    out = []
    for n in catalogo.normas.values():
        if not n.conferida:
            continue
        for ob in n.parametros.get("obrigacoes") or []:
            for campo in ("codigo", "dia", "meses_apos_competencia"):
                if campo not in ob:
                    raise CalendarioInvalido(f"{n.id}: obrigação sem {campo}")
            out.append((n, ob))
    return out


def gerar(competencia: str, perfis_por_cnpj: dict, catalogo, feriados: set[date]) -> list[Vencimento]:
    """`perfis_por_cnpj`: {cnpj: PerfilFiscal} já montados para a competência."""
    venc = []
    for n, ob in obrigacoes_conferidas(catalogo):
        legal = _data_vencimento(competencia, int(ob["dia"]), int(ob["meses_apos_competencia"]))
        if not n.vigente_em(legal):
            continue
        for cnpj, perfil in perfis_por_cnpj.items():
            if perfil is None or perfil.regime is None:
                continue  # regime indefinido: não chuta obrigação (sem_regime() avisa no resumo)
            if ob.get("regimes") and perfil.regime not in ob["regimes"]:
                continue
            if not n.aplica_ao_perfil(perfil):
                continue
            venc.append(Vencimento(cnpj, perfil.apelido, ob["codigo"], ob.get("descricao", ob["codigo"]),
                                   competencia, legal, dia_util_anterior(legal, feriados), n.id))
    return sorted(venc, key=lambda v: (v.vencimento, v.apelido, v.codigo))


def sem_regime(perfis_por_cnpj: dict, catalogo) -> list[str]:
    """Empresas cujo vencimento NÃO foi calculado por regime indefinido (só se há obrigação conferida)."""
    if not obrigacoes_conferidas(catalogo):
        return []
    out = []
    for cnpj, p in perfis_por_cnpj.items():
        if p is None or p.regime is None:
            motivos = ", ".join(x.codigo for x in (getattr(p, "pendencias", None) or [])) if p else "sem perfil"
            out.append(f"{getattr(p, 'apelido', None) or cnpj}: regime indefinido ({motivos or 'sem motivo'})")
    return out


def alertas(vencimentos: list[Vencimento], hoje: date, dias: tuple[int, ...] = (3, 0)) -> list[dict]:
    """Alerta tudo que vence entre hoje e o maior prazo configurado (não perde alerta se o PC não
    rodou no dia exato, ex.: fim de semana)."""
    out, janela = [], max(dias) if dias else 0
    for v in vencimentos:
        faltam = (v.vencimento - hoje).days
        if 0 <= faltam <= janela:
            out.append({"quando": "HOJE" if faltam == 0 else f"em {faltam} dia(s)", "vencimento": v})
    return out


def competencias_para_alerta(hoje: date, catalogo) -> list[str]:
    """Competências cujo vencimento pode cair perto de hoje (até o maior meses_apos_competencia)."""
    maior = max([int(ob["meses_apos_competencia"]) for _, ob in obrigacoes_conferidas(catalogo)] or [1])
    out = []
    y, m = hoje.year, hoje.month
    for k in range(0, maior + 1):
        mm = m - k
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        out.append(f"{yy:04d}-{mm:02d}")
    return sorted(out)
