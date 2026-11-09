"""Loop en tiempo real: una tarea asyncio por partido, a 20 ticks por segundo."""

import asyncio
import logging
import secrets
import threading
import time
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager

from starlette.concurrency import run_in_threadpool

from app.repositories.match_abstract import PenaltyShootoutData
from app.repositories.substitution_abstract import AbstractSubstitutionRepository
from app.services.match_broadcast import (
    SEND_TIMEOUT,
    TickContext,
    broadcast_tick,
    build_tick_payload,
    penalty_kick_record,
)
from app.simulation.behaviors.sandbox import CompiledBehavior
from app.simulation import constants as C
from app.simulation.match_rules import MatchSession, Phase, TickResult, build_session
from app.simulation.state import Team

logger = logging.getLogger(__name__)

END_CODE = 1000
END_REASON = "matchEnd"
ERROR_CODE = 1011
ERROR_REASON = "matchError"
MAX_TICK_COMPUTE = 0.1  # segundos: criterio de rendimiento


class MatchRunner:
    def __init__(
        self,
        manager,
        load_setup,
        repo_scope,
        substitution_scope: Callable[[], AbstractContextManager[AbstractSubstitutionRepository]],
        *,
        executor: ThreadPoolExecutor | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        seed_factory: Callable[[], int] = lambda: secrets.randbits(63),
        send_timeout: float = SEND_TIMEOUT,
    ) -> None:
        """Juega cada partido en tiempo real y transmite sus ticks.

        Una tarea asyncio por partido. El cálculo de cada tick corre en un pool de
        threads para no bloquear el event loop.
        """
        self._manager = manager
        self._load_setup = load_setup
        self._repo_scope = repo_scope
        self._substitution_scope = substitution_scope
        # El cálculo del tick es CPU puro: va a un pool de threads para no
        # bloquear el event loop (WebSockets y API REST).
        self._executor = executor or ThreadPoolExecutor(
            max_workers=8, thread_name_prefix="match-tick"
        )
        self._sleep = sleep
        self._monotonic = monotonic
        self._seed_factory = seed_factory
        self._send_timeout = send_timeout
        self._tasks: dict[int, asyncio.Task] = {}
        self._pending: dict[int, dict[int, CompiledBehavior]] = {}
        self._pending_lock = threading.Lock()

    def start(self, match_id: int) -> asyncio.Task:
        """Arranca el partido (idempotente). Hay que llamarlo con el event loop corriendo."""
        task = self._tasks.get(match_id)
        if task is not None and not task.done():
            return task
        task = asyncio.create_task(self._run(match_id), name=f"match-{match_id}")
        self._tasks[match_id] = task
        task.add_done_callback(lambda t, mid=match_id: self._forget(mid, t))
        return task

    def queue_behavior(self, match_id: int, player_id: int, behavior: CompiledBehavior) -> bool:
        """Deja pendiente el cambio de comportamiento de un jugador. Se aplica antes del
        próximo tick. Devuelve False si el partido no se está jugando en este proceso."""
        with self._pending_lock:
            if not self.is_running(match_id):
                return False
            self._pending.setdefault(match_id, {})[player_id] = behavior
        return True

    def is_running(self, match_id: int) -> bool:
        """True si el partido se está jugando en este proceso."""
        task = self._tasks.get(match_id)
        return task is not None and not task.done()

    async def shutdown(self) -> None:
        """Cancela los partidos en curso y apaga el pool de threads. Se llama al apagar la app."""
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        self._executor.shutdown(wait=False)

    def _forget(self, match_id: int, task: asyncio.Task) -> None:
        if self._tasks.get(match_id) is task:
            del self._tasks[match_id]
            with self._pending_lock:
                self._pending.pop(match_id, None)

    async def _run(self, match_id: int) -> None:
        try:
            setup = await run_in_threadpool(self._load_setup, match_id)
            # La semilla se genera al iniciar y entra al estado inicial del motor.
            seed = self._seed_factory()
            # Se loguea antes de guardarla: si falla la base, igual queda en el log.
            logger.info("Partido %s arranca con seed=%s", match_id, seed)
            await self._persist_seed(match_id, seed)
            session = build_session(
                setup.team_1,
                setup.team_2,
                setup.duration_seconds,
                seed,
                setup.countdown_seconds,
                setup.periods,
                setup.pause_seconds,
                setup.allow_draws,
            )
            context = TickContext(
                club_1=setup.club_1_name,
                club_2=setup.club_2_name,
                countdown_seconds=round(setup.countdown_seconds),
            )
            await self._play(match_id, session, context)
        except asyncio.CancelledError:
            raise
        except Exception:
            # El partido queda en `scheduled` (la recuperación es de los checkpoints).
            logger.exception("Falló el partido %s", match_id)
            await self._manager.close_match(match_id, ERROR_CODE, ERROR_REASON)

    async def _persist_seed(self, match_id: int, seed: int) -> None:
        """Guardar la semilla es para poder investigar el partido después: si
        falla, el partido se juega igual (la semilla ya quedó en el log)."""
        try:
            await run_in_threadpool(self._save_seed, match_id, seed)
        except Exception:
            logger.exception("No se pudo guardar la seed del partido %s", match_id)

    def _save_seed(self, match_id: int, seed: int) -> None:
        with self._repo_scope() as repo:
            repo.save_seed(match_id, seed)

    async def _play(self, match_id: int, session: MatchSession, context: TickContext) -> None:
        loop = asyncio.get_running_loop()
        started = False
        previous_phase: Phase | None = None
        start = self._monotonic()
        while True:
            began = self._monotonic()
            self._apply_pending(match_id, session)
            result = await loop.run_in_executor(self._executor, session.advance)
            compute = self._monotonic() - began
            if compute > MAX_TICK_COMPUTE:
                logger.warning(
                    "Tick %s del partido %s tardó %.3f s", result.tick, match_id, compute
                )

            if not started and result.phase is not Phase.COUNTDOWN:
                await run_in_threadpool(self._mark_started, match_id)
                started = True

            if previous_phase is Phase.PAUSED and result.phase is not Phase.PAUSED:
                # Terminó una pausa: se consume el cambio más antiguo de cada equipo.
                await run_in_threadpool(self._end_pause, match_id)
            previous_phase = result.phase

            finished = result.phase is Phase.FINISHED
            if finished:
                # Se guarda antes de avisar: quien se conecte después recibe 4409.
                await run_in_threadpool(self._save_result, match_id, result)
            await broadcast_tick(
                self._manager, match_id, build_tick_payload(result, context), self._send_timeout
            )
            if finished:
                await self._manager.close_match(match_id, END_CODE, END_REASON)
                return

            # Agenda absoluta: el tick n sale en start + n * 50 ms, sin acumular desfase.
            next_at = start + (result.tick + 1) * C.SECONDS_PER_TICK
            await self._sleep(max(0.0, next_at - self._monotonic()))

    def _mark_started(self, match_id: int) -> None:
        with self._repo_scope() as repo:
            repo.mark_started(match_id)

    def _end_pause(self, match_id: int) -> None:
        try:
            with self._substitution_scope() as repo:
                repo.delete_first_per_team(match_id)
        except Exception:
            logger.exception("No se pudieron borrar los cambios del partido %s", match_id)

    def _save_result(self, match_id: int, result: TickResult) -> None:
        with self._repo_scope() as repo:
            repo.finish(match_id, result.score_1, result.score_2, _penalties_data(result))

    def _apply_pending(self, match_id: int, session: MatchSession) -> None:
        """Aplica los cambios de behavior pendientes antes del próximo tick."""
        with self._pending_lock:
            pending = self._pending.pop(match_id, {})
        for player_id, behavior in pending.items():
            try:
                session.replace_behavior(player_id, behavior)
            except ValueError:
                logger.warning(
                    "Partido %s: el jugador %s ya no está en cancha", match_id, player_id
                )


def _penalties_data(result: TickResult) -> PenaltyShootoutData | None:
    shootout = result.shootout
    if shootout is None:
        return None
    return PenaltyShootoutData(
        score_1=shootout.score_1,
        score_2=shootout.score_2,
        winner=1 if shootout.winner is Team.HOME else 2,
        kicks=[penalty_kick_record(kick) for kick in shootout.kicks],
    )
