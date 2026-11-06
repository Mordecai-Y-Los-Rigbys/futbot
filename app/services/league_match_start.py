import asyncio
import logging
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from typing import Awaitable, Callable

from starlette.concurrency import run_in_threadpool

from app.repositories.league_match_start_abstract import (
    AbstractLeagueMatchStartRepository,
    PendingLeagueMatch,
)

START_RETRIES = 3
START_RETRY_DELAY = 2.0  # segundos

logger = logging.getLogger(__name__)

RepoScope = Callable[[], AbstractContextManager[AbstractLeagueMatchStartRepository]]
OnStart = Callable[[int], Awaitable[None]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class LeagueMatchStartService:
    """Arranca cada partido de liga en su `scheduled_at`.

    Una tarea asyncio por partido, en memoria del proceso. Al llegar la hora,
    chequea que el partido siga `scheduled` y llama al runner.

    Si la app se reinicia, `recover()` reprograma los partidos de liga que
    siguen `scheduled`. Los que ya tendrían que haber arrancado, arrancan enseguida.
    """
    
    def __init__(self, repo_scope: RepoScope, on_start: OnStart | None = None) -> None:
        self._repo_scope = repo_scope
        self._on_start = on_start
        self._tasks: dict[int, asyncio.Task] = {}
        
    def schedule(self, match_id: int, scheduled_at: datetime) -> None:
        """Llamar con el event loop corriendo y el partido ya guardado.

        Si el horario ya pasó, el delay es negativo y asyncio.sleep vuelve enseguida.
        """
        self.unschedule(match_id)
        delay = (scheduled_at - _utcnow()).total_seconds()
        self._tasks[match_id] = asyncio.get_running_loop().create_task(
            self._run(match_id, delay)
        )
        
    def unschedule(self, match_id: int) -> None:
        """Cancela el arranque pendiente del partido, si lo hay."""
        task = self._tasks.pop(match_id, None)
        if task is not None:
            task.cancel()

    def shutdown(self) -> None:
        """Cancela todos los arranques pendientes. Se llama al apagar la app."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def start(self, match_id: int) -> bool:
        """Arranca el partido si sigue `scheduled`. True si lo arrancó."""
        self._tasks.pop(match_id, None)

        def ready() -> bool:
            with self._repo_scope() as repo:
                return repo.is_ready_to_start(match_id)

        is_ready = await run_in_threadpool(ready)
        if is_ready and self._on_start is not None:
            try:
                await self._on_start(match_id)
            except Exception:
                logger.exception("Falló el arranque de la simulación del partido %s", match_id)
        return is_ready

    async def schedule_league(self, league_id: int) -> None:
        """Agenda los partidos de una liga recién iniciada."""
        for match in await self._pending(league_id):
            self.schedule(match.match_id, match.scheduled_at)

    async def recover(self) -> None:
        """Al arrancar la app, reprograma los partidos de liga que siguen `scheduled`."""
        for match in await self._pending(None):
            self.schedule(match.match_id, match.scheduled_at)

    async def _pending(self, league_id: int | None) -> list[PendingLeagueMatch]:
        def pending() -> list[PendingLeagueMatch]:
            with self._repo_scope() as repo:
                return repo.list_pending_start(league_id)

        return await run_in_threadpool(pending)

    async def _run(self, match_id: int, delay: float) -> None:
        await asyncio.sleep(delay)
        for attempt in range(1, START_RETRIES + 1):
            try:
                await self.start(match_id)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "No se pudo arrancar el partido %s (intento %s/%s)",
                    match_id,
                    attempt,
                    START_RETRIES,
                )
                if attempt < START_RETRIES:
                    await asyncio.sleep(START_RETRY_DELAY * attempt)
        logger.error(
            "Se agotaron los reintentos para arrancar el partido %s; "
            "queda `scheduled` hasta el próximo recover()",
            match_id,
        )