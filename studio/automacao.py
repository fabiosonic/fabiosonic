"""Piloto automático: cria os posts da semana e publica no Instagram na hora marcada."""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta

from avatar_contabil import config

from . import fluxo, ia, pautas
from .db import Conteudo, Pauta, Perfil, agora, registrar, select, sessao
from .instagram import Instagram
from .servicos import cfg, criar_conteudo
from .travas import legenda_final

ROBO = "piloto automático"
ESTILOS_POR_ORIGEM = {
    "fiscal": ["checklist", "passo_a_passo"],
    "noticia": ["noticia", "antes_depois", "mito_verdade"],
    "ideia": ["problema_solucao", "mito_verdade"],
}


# ---------- criação automática ----------

def horarios_livres(perfil: Perfil, ocupados: set[date], agora_: datetime) -> list[datetime]:
    """Próximos dias/horários do perfil dentro da antecedência, sem conteúdo marcado no dia."""
    h, m = (int(x) for x in (perfil.auto_horario or "11:30").split(":"))
    dias = perfil.dias_auto()
    saida = []
    for d in range(0, max(1, perfil.auto_antecedencia) + 1):
        quando = datetime.combine(agora_.date() + timedelta(days=d), datetime.min.time()).replace(hour=h, minute=m)
        if quando.weekday() in dias and quando.date() not in ocupados and quando > agora_ + timedelta(hours=2):
            saida.append(quando)
    return saida


def _candidatas(s, perfil: Perfil) -> list[Pauta]:
    usadas = {c.pauta_id for c in s.exec(select(Conteudo).where(Conteudo.perfil_id == perfil.id)).all()}
    return [p for p in s.exec(select(Pauta).where(Pauta.arquivada == False)).all() if p.id not in usadas]  # noqa: E712


def escolher_pauta(perfil: Perfil, quando: datetime, candidatas: list[Pauta], notas: dict[int, int], nota_minima: int) -> Pauta | None:
    """Prioridade: vencimento fiscal na semana seguinte ao post > notícia bem avaliada > ideia."""
    def dias_ate(p: Pauta) -> int:
        try:
            return (date.fromisoformat(p.data_ref) - quando.date()).days
        except (TypeError, ValueError):
            return 999

    fiscais = sorted((p for p in candidatas if p.origem == "fiscal" and 0 <= dias_ate(p) <= 7), key=dias_ate)
    noticias = sorted((p for p in candidatas if p.origem == "noticia" and notas.get(p.id, 0) >= nota_minima),
                      key=lambda p: notas.get(p.id, 0), reverse=True)
    ideias = [p for p in candidatas if p.origem == "ideia"]
    for grupo in (fiscais, noticias, ideias):
        if grupo:
            return grupo[0]
    return None


def gerar_para_perfil(s, perfil: Perfil, agora_: datetime | None = None) -> list[Conteudo]:
    agora_ = agora_ or agora()
    ocupados = {c.agendado_para.date() for c in s.exec(select(Conteudo).where(Conteudo.perfil_id == perfil.id)).all()
                if c.agendado_para and c.status != fluxo.AJUSTE}
    horarios = horarios_livres(perfil, ocupados, agora_)
    if not horarios:
        return []
    candidatas = _candidatas(s, perfil)
    noticias = [p for p in candidatas if p.origem == "noticia"]
    notas = ia.triar(perfil, noticias) if noticias else {}
    nota_minima = cfg()["roteiro"].get("nota_minima", 7)
    formatos = perfil.formatos_auto()
    criados = []
    for i, quando in enumerate(horarios):
        pauta = escolher_pauta(perfil, quando, candidatas, notas, nota_minima)
        if pauta is None:
            break
        candidatas.remove(pauta)
        estilos = ESTILOS_POR_ORIGEM.get(pauta.origem, ["noticia"])
        c = criar_conteudo(s, perfil, pauta, formatos[i % len(formatos)], estilos[i % len(estilos)], "", ROBO, automatico=True)
        c.agendado_para = quando
        if not c.j("alertas"):
            fluxo.enviar_revisao(c)  # vai direto para a fila do contador
        registrar(s, c.id, ROBO, "data planejada", quando.strftime("%d/%m/%Y %H:%M"))
        s.add(c)
        criados.append(c)
    return criados


def gerar_automatico() -> dict[str, int]:
    """Busca pautas e cria os conteúdos de todos os perfis com piloto automático ligado."""
    hoje = date.today()
    proximo = (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
    resultado = {}
    with sessao() as s:
        try:
            pautas.importar_noticias(s, cfg())
        except Exception as e:  # feed fora do ar não impede o resto
            registrar(s, None, ROBO, "falha ao buscar notícias", str(e)[:300])
        pautas.importar_fiscais(s, hoje.year, hoje.month)
        pautas.importar_fiscais(s, proximo.year, proximo.month)
        s.commit()
        for perfil in s.exec(select(Perfil).where(Perfil.auto_ativo == True)).all():  # noqa: E712
            try:
                resultado[perfil.nome] = len(gerar_para_perfil(s, perfil))
                s.commit()
            except Exception as e:
                s.rollback()
                registrar(s, None, ROBO, f"falha ao gerar para {perfil.nome}", str(e)[:300])
                s.commit()
                resultado[perfil.nome] = 0
    return resultado


# ---------- publicação ----------

def urls_midia(c: Conteudo) -> list[str]:
    base = cfg()["studio"].get("url_publica", "").rstrip("/")
    if not base:
        raise RuntimeError("Defina studio.url_publica no config.yaml (endereço público do Studio) para o Instagram baixar as imagens.")
    return [f"{base}/m/{c.midia_token}/{i}.jpg" for i in range(len(c.j("arquivos")))]


def publicar(s, c: Conteudo, perfil: Perfil, usuario: str) -> str:
    if c.status not in (fluxo.PRODUZIDO, fluxo.AGENDADO):
        raise fluxo.FluxoInvalido("Só é possível publicar conteúdos prontos.")
    if config.dry_run():
        midia_id = "simulado-dry-run"
    else:
        if not perfil.instagram_conectado:
            raise RuntimeError("Conecte o Instagram no perfil (ID da conta e token).")
        ig = Instagram(perfil.ig_user_id, perfil.ig_token, cfg()["studio"].get("instagram_api", "https://graph.facebook.com/v21.0"))
        midia_id = ig.publicar(urls_midia(c), legenda_final(cfg(), perfil, c.j("dados")))
    info = c.j("publicacao") or {}
    info["instagram"] = {"id": midia_id, "quando": agora().isoformat()}
    c.guardar("publicacao", info)
    c.status, c.erro, c.atualizado_em = fluxo.PUBLICADO, "", agora()
    registrar(s, c.id, usuario, "publicado no Instagram", midia_id)
    return midia_id


def publicar_vencidos(maximo_tentativas: int = 3) -> int:
    """Publica tudo que está agendado com horário já alcançado."""
    feitos = 0
    with sessao() as s:
        vencidos = s.exec(select(Conteudo).where(Conteudo.status == fluxo.AGENDADO)).all()
        for c in vencidos:
            if not c.agendado_para or c.agendado_para > agora() or c.j("publicacao").get("postiz"):
                continue
            perfil = s.get(Perfil, c.perfil_id)
            try:
                publicar(s, c, perfil, ROBO)
                feitos += 1
            except Exception as e:
                info = c.j("publicacao") or {}
                info["tentativas"] = info.get("tentativas", 0) + 1
                c.guardar("publicacao", info)
                c.erro = f"Falha ao publicar (tentativa {info['tentativas']}): {e}"[:2000]
                if info["tentativas"] >= maximo_tentativas:
                    c.status = fluxo.ERRO
                registrar(s, c.id, ROBO, "falha ao publicar", str(e)[:500])
            s.add(c)
            s.commit()
    return feitos


# ---------- agendador ----------

def _marca_dia() -> str:
    arq = config.DADOS / "studio" / "ultima_geracao.txt"
    return arq.read_text().strip() if arq.exists() else ""


def _marcar_hoje() -> None:
    arq = config.DADOS / "studio" / "ultima_geracao.txt"
    arq.parent.mkdir(parents=True, exist_ok=True)
    arq.write_text(date.today().isoformat())


def ciclo() -> None:
    """Uma volta do agendador: publica o que venceu e, uma vez por dia, cria os posts."""
    auto = cfg()["studio"].get("automacao", {})
    publicar_vencidos()
    if datetime.now().hour >= auto.get("hora_geracao", 7) and _marca_dia() != date.today().isoformat():
        _marcar_hoje()
        gerar_automatico()


def iniciar_agendador() -> threading.Thread | None:
    auto = cfg()["studio"].get("automacao", {})
    if not auto.get("ativo"):
        return None

    def laco():
        while True:
            try:
                ciclo()
            except Exception as e:  # nunca derruba o servidor
                print(f"[piloto automático] erro: {e}")
            time.sleep(max(1, auto.get("intervalo_minutos", 5)) * 60)

    t = threading.Thread(target=laco, name="piloto-automatico", daemon=True)
    t.start()
    return t
