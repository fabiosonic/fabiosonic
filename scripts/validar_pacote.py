#!/usr/bin/env python3
"""Valida o pacote Paperclip da Moraes & Oliveira antes de importar.

Uso:  python3 scripts/validar_pacote.py [caminho-do-pacote]
Requer: PyYAML (pip install pyyaml)

Checa: frontmatter de COMPANY/AGENTS/SKILL/PROJECT/TASK, organograma (reportsTo),
skills referenciadas, donos de projeto, responsáveis das tarefas, rotinas x tarefas
recorrentes, cron, políticas e cargos válidos no Paperclip.
"""
import sys
from pathlib import Path

import yaml

ROLES = {"ceo", "cto", "cmo", "cfo", "security", "engineer", "designer", "pm", "qa",
         "devops", "researcher", "general"}
CONCURRENCY = {"coalesce_if_active", "always_enqueue", "skip_if_active"}
CATCH_UP = {"skip_missed", "enqueue_missed_with_cap"}
BUILTIN_SKILLS = {"paperclip"}  # skill nativa do Paperclip

erros, avisos = [], []


def frontmatter(path: Path) -> dict:
    texto = path.read_text(encoding="utf-8")
    if not texto.startswith("---\n"):
        erros.append(f"{path}: sem frontmatter")
        return {}
    try:
        fim = texto.index("\n---", 4)
    except ValueError:
        erros.append(f"{path}: frontmatter não fechado")
        return {}
    try:
        dados = yaml.safe_load(texto[4:fim]) or {}
    except yaml.YAMLError as exc:
        erros.append(f"{path}: YAML inválido no frontmatter: {exc}")
        return {}
    if not texto[fim + 4:].strip():
        avisos.append(f"{path}: corpo vazio")
    return dados


def cron_ok(expr: str) -> bool:
    partes = expr.split()
    limites = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 7)]
    if len(partes) != 5:
        return False
    for parte, (lo, hi) in zip(partes, limites):
        if parte == "*":
            continue
        for item in parte.split(","):
            for n in item.split("-"):
                if not n.isdigit() or not lo <= int(n) <= hi:
                    return False
    return True


def main() -> int:
    raiz = Path(sys.argv[1] if len(sys.argv) > 1 else
                Path(__file__).resolve().parent.parent / "paperclip" / "moraes-oliveira-contabilidade")
    company = frontmatter(raiz / "COMPANY.md")
    for campo in ("name", "description", "slug", "schema"):
        if not company.get(campo):
            erros.append(f"COMPANY.md: campo obrigatório ausente: {campo}")

    ext = yaml.safe_load((raiz / ".paperclip.yaml").read_text(encoding="utf-8")) or {}
    ext_agents = ext.get("agents") or {}
    ext_routines = ext.get("routines") or {}

    skills = {p.parent.name for p in raiz.glob("skills/*/SKILL.md")}
    for p in raiz.glob("skills/*/SKILL.md"):
        fm = frontmatter(p)
        if not fm.get("name") or not fm.get("description"):
            erros.append(f"{p}: skill sem name/description")

    agentes = {}
    for p in sorted(raiz.glob("agents/*/AGENTS.md")):
        fm = frontmatter(p)
        slug = fm.get("slug") or p.parent.name
        agentes[slug] = fm
        for s in fm.get("skills") or []:
            if s not in skills and s not in BUILTIN_SKILLS:
                erros.append(f"{p}: skill inexistente '{s}'")
        cfg = ext_agents.get(slug)
        if not cfg:
            erros.append(f".paperclip.yaml: agente '{slug}' sem configuração de adapter")
            continue
        if cfg.get("role") not in ROLES:
            erros.append(f".paperclip.yaml: cargo inválido para '{slug}': {cfg.get('role')}")
        if not isinstance(cfg.get("budgetMonthlyCents"), int):
            avisos.append(f".paperclip.yaml: '{slug}' sem budgetMonthlyCents (ficaria sem limite)")

    raizes = [s for s, fm in agentes.items() if fm.get("reportsTo") is None]
    if len(raizes) != 1:
        erros.append(f"organograma deve ter exatamente 1 topo; encontrados: {raizes}")
    for slug, fm in agentes.items():
        chefe = fm.get("reportsTo")
        if chefe is not None and chefe not in agentes:
            erros.append(f"agente '{slug}' reporta a inexistente '{chefe}'")
        visitados, atual = set(), slug
        while atual is not None and atual in agentes:
            if atual in visitados:
                erros.append(f"ciclo no organograma envolvendo '{slug}'")
                break
            visitados.add(atual)
            atual = agentes[atual].get("reportsTo")
    for slug in ext_agents:
        if slug not in agentes:
            erros.append(f".paperclip.yaml: agente '{slug}' sem AGENTS.md")

    projetos = {}
    for p in raiz.glob("projects/*/PROJECT.md"):
        fm = frontmatter(p)
        projetos[fm.get("slug") or p.parent.name] = fm
        if fm.get("owner") not in agentes:
            erros.append(f"{p}: owner inexistente '{fm.get('owner')}'")

    recorrentes = set()
    for p in raiz.rglob("TASK.md"):
        fm = frontmatter(p)
        slug = fm.get("slug") or p.parent.name
        if fm.get("assignee") not in agentes:
            erros.append(f"{p}: assignee inexistente '{fm.get('assignee')}'")
        if fm.get("project") and fm["project"] not in projetos:
            erros.append(f"{p}: projeto inexistente '{fm['project']}'")
        if fm.get("recurring"):
            recorrentes.add(slug)
            if slug not in ext_routines:
                erros.append(f"{p}: tarefa recorrente sem rotina em .paperclip.yaml")

    for slug, r in ext_routines.items():
        if slug not in recorrentes:
            erros.append(f"rotina '{slug}' sem TASK.md com recurring: true")
        if r.get("concurrencyPolicy") not in CONCURRENCY:
            erros.append(f"rotina '{slug}': concurrencyPolicy inválida")
        if r.get("catchUpPolicy") not in CATCH_UP:
            erros.append(f"rotina '{slug}': catchUpPolicy inválida")
        for t in r.get("triggers") or []:
            if t.get("kind") != "schedule" or not t.get("timezone") or not cron_ok(str(t.get("cronExpression", ""))):
                erros.append(f"rotina '{slug}': gatilho inválido {t}")

    orcamento = sum(c.get("budgetMonthlyCents", 0) for c in ext_agents.values()) / 100
    print(f"Agentes: {len(agentes)} | Skills: {len(skills)} | Projetos: {len(projetos)} | "
          f"Rotinas: {len(ext_routines)} | Orçamento mensal total: US$ {orcamento:.2f}")
    for a in avisos:
        print("AVISO:", a)
    for e in erros:
        print("ERRO:", e)
    print("OK — pacote válido." if not erros else f"{len(erros)} erro(s).")
    return 1 if erros else 0


if __name__ == "__main__":
    sys.exit(main())
