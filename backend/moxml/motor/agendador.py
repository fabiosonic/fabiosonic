"""Agendamento diário (várias execuções por dia) com APScheduler.

- ``max_instances=1`` + ``coalesce``: nunca há duas capturas simultâneas; execuções perdidas
  (computador desligado) são agrupadas em uma única ao religar (misfire_grace_time de 6h).
- Verificação diária de vencimento de certificados.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from ..db.modelos import Certificado
from .aplicacao import Aplicacao
from .logs import HUB
from .orquestrador import Opcoes, Orquestrador, executar_com_trava

log = logging.getLogger("moxml.agendador")
FUSO = ZoneInfo("America/Sao_Paulo")  # requer pacote tzdata no Windows


def horarios(texto: str) -> list[tuple[int, int]]:
    out = []
    for h in texto.split(","):
        h = h.strip()
        if not h:
            continue
        hh, mm = h.split(":")
        hh_i, mm_i = int(hh), int(mm)
        if not (0 <= hh_i < 24 and 0 <= mm_i < 60):
            raise ValueError(f"horário inválido: {h}")
        out.append((hh_i, mm_i))
    return out


def atualizar_status_certificados(app: Aplicacao) -> list[str]:
    alertas = []
    with app.sessoes() as s:
        agora = datetime.now(UTC)
        for c in s.scalars(select(Certificado).where(Certificado.ativo.is_(True))).all():
            validade = c.validade if c.validade.tzinfo else c.validade.replace(tzinfo=UTC)
            dias = (validade - agora).days
            novo = "VENCIDO" if dias < 0 else "VENCENDO" if dias <= 30 else "VALIDO"
            if novo != c.status:
                c.status = novo
            if novo != "VALIDO":
                msg = f"Certificado de {c.titular} ({c.cnpj}) {novo.lower()}: validade {validade:%d/%m/%Y} ({dias} dias)"
                alertas.append(msg)
                HUB.publicar("AVISO", msg)
        s.commit()
    return alertas


class Agendador:
    def __init__(self, app: Aplicacao, orq: Orquestrador):
        self.app, self.orq = app, orq
        self.sched = BackgroundScheduler(timezone=FUSO)

    def iniciar(self) -> None:
        for hh, mm in horarios(self.app.cfg.horarios_execucao):
            self.sched.add_job(self._rodar, CronTrigger(hour=hh, minute=mm, timezone=FUSO), id=f"captura-{hh:02d}{mm:02d}",
                               max_instances=1, coalesce=True, misfire_grace_time=6 * 3600, replace_existing=True)
        self.sched.add_job(lambda: atualizar_status_certificados(self.app), CronTrigger(hour=6, minute=50, timezone=FUSO),
                           id="certificados", replace_existing=True)
        if getattr(self.app.cfg, "executar_ao_iniciar", True):
            quando = datetime.now(FUSO) + timedelta(seconds=8)
            self.sched.add_job(self._rodar, DateTrigger(run_date=quando), id="inicial",
                               max_instances=1, coalesce=True, misfire_grace_time=600, replace_existing=True)
            log.info("primeira captura agendada para ~8s após iniciar")
        self.sched.start()
        log.info("agendador iniciado: %s", self.app.cfg.horarios_execucao)

    def _rodar(self) -> None:
        r = executar_com_trava(self.orq, Opcoes(gatilho="AGENDADA"))
        if r is None:
            HUB.publicar("AVISO", "execução agendada ignorada: já havia captura em andamento")
        if self.app.cfg.gdrive_ativo:
            try:
                from ..integracoes.gdrive import sincronizar_drive
                sincronizar_drive(self.app)
            except Exception as e:  # noqa: BLE001
                HUB.publicar("ERRO", f"Google Drive: {e}")

    def proximas(self) -> list[str]:
        return sorted(j.next_run_time.isoformat() for j in self.sched.get_jobs()
                      if j.next_run_time and j.id.startswith("captura-"))

    def parar(self) -> None:
        if self.sched.running:
            self.sched.shutdown(wait=False)
