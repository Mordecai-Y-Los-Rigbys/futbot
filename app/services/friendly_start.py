import asyncio
import logging
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Awaitable, Callable

from starlette.concurrency import run_in_threadpool

from app.repositories.match_start_abstract import AbstractMatchStartRepository
from app.services.match_timing import FRIENDLY_COUNTDOWN

START_RETRIES = 3
START_RETRY_DELAY = 2.0  # segundos

logger = logging.getLogger(__name__)

RepoScope = Callable[[], AbstractContextManager[AbstractMatchStartRepository]]
OnStart = Callable[[int], Awaitable[None]]


class FriendlyStartService:
    """Arranca un amistoso `countdown` después de que se une el rival.

    Una tarea asyncio por partido, en memoria del proceso (igual que
    FriendlyExpiryService; el despliegue es de 1 worker). Chequea si
    el partido está listo para arrancar y, si lo está, llama al runner.

    Si la app se reinicia, `recover()` reprograma la cuenta de los partidos con
    rival que siguen `scheduled` (la cuenta reinicia desde cero: no se guarda
    cuándo se unió el rival).
    """

    def __init__(
        self,
        repo_scope: RepoScope,
        on_start: OnStart | None = None,
        countdown: timedelta = FRIENDLY_COUNTDOWN,
    ) -> None:
        self._repo_scope = repo_scope
        self._on_start = on_start
        self.countdown = countdown  # inyectable para los tests
        self._tasks: dict[int, asyncio.Task] = {}

    def schedule(self, match_id: int) -> None:
        """Llamar con el event loop corriendo y la unión ya confirmada."""
        self.unschedule(match_id)
        self._tasks[match_id] = asyncio.get_running_loop().create_task(
            self._run(match_id, self.countdown.total_seconds())
        )

    def unschedule(self, match_id: int) -> None:
        task = self._tasks.pop(match_id, None)
        if task is not None:
            task.cancel()

    def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    async def start(self, match_id: int) -> bool:
        """Arranca el partido si sigue en cuenta regresiva. True si lo arrancó."""
        self._tasks.pop(match_id, None)

        def mark() -> bool:
            with self._repo_scope() as repo:
                return repo.is_ready_to_start(match_id)

        ready = await run_in_threadpool(mark)
        if ready and self._on_start is not None:
            try:
                await self._on_start(match_id)
            except Exception:
                logger.exception("Falló el arranque de la simulación del partido %s", match_id)
        return ready

    async def recover(self) -> None:
        def pending() -> list[int]:
            with self._repo_scope() as repo:
                return repo.list_pending_start()

        for match_id in await run_in_threadpool(pending):
            self.schedule(match_id)

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
            "queda en cuenta regresiva hasta el próximo recover()",
            match_id,
        )
