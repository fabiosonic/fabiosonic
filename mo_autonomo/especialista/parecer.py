"""Parecer técnico por empresa/competência (Markdown e XLSX)."""
from __future__ import annotations

from pathlib import Path

from ..util.arquivos import escrever_atomico
from ..util.documentos_id import formatar_cnpj
from .modelo import APONTAMENTO, CONTROLE, INDICIO

ORDEM = (APONTAMENTO, INDICIO, CONTROLE)
EXPLICA = {
    APONTAMENTO: "fundamentado em normas CONFERIDAS — pode virar ação",
    INDICIO: "alguma norma citada ainda NÃO conferida — não pode virar ação até a conferência",
    CONTROLE: "fato objetivo do documento, sem afirmação legal",
}


def _citacao(normas: list[dict]) -> str:
    if not normas:
        return "—"
    return "; ".join(f"{n['id']} ({n['status']})" for n in normas)


def markdown(empresa, competencia: str, perfil, achados: list[dict], pendencias: list[dict],
             documentos: int, regras_inativas: list[dict]) -> str:
    l = [f"# Parecer técnico — {empresa.apelido} ({formatar_cnpj(empresa.cnpj)})", "",
         f"- Competência: **{competencia}**", f"- Código Domínio: {empresa.codigo_dominio}",
         f"- Regime: **{perfil.regime or 'INDEFINIDO'}** (fonte: {perfil.regime_fonte})",
         f"- CNAE: {', '.join(perfil.cnaes) or 'não disponível'}", f"- Documentos analisados: {documentos}", ""]
    l += ["## Pendências (impedem aprovação)", ""]
    l += [f"- **{p['codigo']}** — {p['mensagem']}" + (f" (`{p['referencia']}`)" if p.get("referencia") else "")
          for p in pendencias] or ["- Nenhuma."]
    l.append("")
    for nat in ORDEM:
        grupo = [a for a in achados if a["natureza"] == nat]
        l += [f"## {nat} — {EXPLICA[nat]}", ""]
        if not grupo:
            l += ["- Nenhum.", ""]
            continue
        for a in grupo:
            l.append(f"- **{a['titulo']}** — {a['mensagem']}")
            if a.get("documento"):
                l.append(f"  - Documento: `{a['documento']}`")
            l.append(f"  - Base: {_citacao(a['normas'])}")
            if a.get("correcao"):
                l.append(f"  - Correção proposta: {a['correcao']}")
        l.append("")
    if regras_inativas:
        l += ["## Regras inativas nesta análise (falta conferência humana da norma)", ""]
        l += [f"- {r['regra']}: {r['motivo']}" for r in regras_inativas]
        l.append("")
    l += ["---", "Gerado automaticamente. Nenhuma ação foi executada sem aprovação (APROVADO ou aprovação "
          "por exceção registrada na trilha)."]
    return "\n".join(l)


def salvar(pasta: Path, nome: str, conteudo_md: str, achados: list[dict]) -> dict:
    pasta = Path(pasta)
    md = pasta / f"{nome}.md"
    escrever_atomico(md, conteudo_md.encode("utf-8"))
    xlsx = pasta / f"{nome}.xlsx"
    try:
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "achados"
        ws.append(["natureza", "regra", "titulo", "mensagem", "documento", "normas", "correcao", "bloqueia", "valor"])
        for a in achados:
            ws.append([a["natureza"], a["regra"], a["titulo"], a["mensagem"], a.get("documento"),
                       _citacao(a["normas"]), a.get("correcao"), "SIM" if a.get("bloqueia") else "NÃO",
                       str(a["valor"]) if a.get("valor") is not None else None])
        pasta.mkdir(parents=True, exist_ok=True)
        wb.save(xlsx)
    except ImportError:
        xlsx = None
    return {"md": str(md), "xlsx": str(xlsx) if xlsx else None}
