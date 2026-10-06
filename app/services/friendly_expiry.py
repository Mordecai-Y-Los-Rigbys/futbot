import asyncio
import logging
from contextlib import AbstractContextManager
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

from starlette.concurrency import run_in_threadpool

from app.repositories.match_expiry_abstract import (
    AbstractMatchExpiryRepository,
    WaitingFriendlyData,
)
from app.services.match_timing import MAX_FRIENDLY_WAIT


EXPIRY_RETRIES = 3
EXPIRY_RETRY_DELAY = 2.0  # segundos

logger = logging.getLogger(__name__)

RepoScope = Callable[[], AbstractContextManager[AbstractMatchExpiryRepository]]
CloseMatch = Callable[[int], Awaitable[None]]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FriendlyExpiryService:
    """Cancela los amistosos cuyo creador espera `wait` sin que se una un rival.

    Una tarea asyncio por amistoso, programada al crearlo. Vive en memoria del
    proceso, igual que MatchConnectionManager: es válido porque el despliegue
    es de 1 worker (ver ensure_single_worker). Si la app se reinicia, `recover()`
    reprograma lo pendiente leyendo la base.

    Al vencer:
        1. UPDATE condicional del partido a `cancelled` (la base decide la
           carrera contra el rival que se une).
        2. Solo si lo canceló: close_match(), que cierra las conexiones del
           creador con 1000 / waitExpired.
    """

    def __init__(
        self,
        repo_scope: RepoScope,
        close_match: CloseMatch,
        wait: timedelta = MAX_FRIENDLY_WAIT,
    ) -> None:
        self._repo_scope = repo_scope
        self._close_match = close_match
        self.wait = wait  # inyectable para los tests; en producción, MAX_FRIENDLY_WAIT
        self._tasks: dict[int, asyncio.Task] = {}

    def schedule(self, match_id: int, created_at: datetime | None = None) -> None:
        """Programa el vencimiento: `created_at + wait` (por defecto, desde ahora).
        Llamar con el event loop corriendo, después de confirmar la creación del
        amistoso en la base."""
        self.unschedule(match_id)
        deadline = (created_at or _utcnow()) + self.wait
        delay = max(0.0, (deadline - _utcnow()).total_seconds())
        self._tasks[match_id] = asyncio.get_running_loop().create_task(self._run(match_id, delay))

    def unschedule(self, match_id: int) -> None:
        """Cancela el timer (por ejemplo, cuando el rival se une)."""
        task = self._tasks.pop(match_id, None)
        if task is not None:
            task.cancel()

    def shutdown(self) -> None:
        """Cancela todos los vencimientos pendientes. Se llama al apagar la app."""
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def expire(self, match_id: int) -> bool:
        """Cancela el amistoso si sigue en espera. True si lo canceló."""
        self._tasks.pop(match_id, None)

        def cancel() -> bool:
            with self._repo_scope() as repo:
                return repo.cancel_if_waiting_friendly(match_id)

        cancelled = await run_in_threadpool(cancel)
        if cancelled:
            await self._close_match(match_id)
        return cancelled

    async def recover(self) -> None:
        """Al arrancar: reprograma los amistosos en espera. Los que ya vencieron
        se cancelan enseguida (delay 0); al resto les queda su tiempo real."""

        def waiting() -> list[WaitingFriendlyData]:
            with self._repo_scope() as repo:
                return repo.list_waiting_friendlies()

        for item in await run_in_threadpool(waiting):
            self.schedule(item.match_id, item.created_at)

    async def _run(self, match_id: int, delay: float) -> None:
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise
        await self._expire_with_retries(match_id)

    async def _expire_with_retries(self, match_id: int) -> None:
        for attempt in range(1, EXPIRY_RETRIES + 1):
            try:
                await self.expire(match_id)
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "No se pudo caducar el amistoso del partido %s (intento %s/%s)",
                    match_id,
                    attempt,
                    EXPIRY_RETRIES,
                )
                if attempt < EXPIRY_RETRIES:
                    await asyncio.sleep(EXPIRY_RETRY_DELAY * attempt)
        logger.error(
            "Se agotaron los reintentos para caducar el partido %s; "
            "queda en espera hasta el próximo recover()",
            match_id,
        )
