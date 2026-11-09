"""Juega una prueba de un comportamiento en tiempo real, a 20 ticks por segundo."""

import asyncio
import json
import logging
import secrets
import time
from collections.abc import Awaitable, Callable

from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from app.repositories.team_abstract import StarterData
from app.services.behavior_test_broadcast import build_test_tick_payload
from app.services.behavior_test_rules import build_test_session
from app.simulation import constants as C
from app.simulation.match_rules import MatchSession, Phase

logger = logging.getLogger(__name__)

END_CODE = 1000
END_REASON = "testEnd"
ERROR_CODE = 1011
ERROR_REASON = "testError"


class BehaviorTestRunner:
    def __init__(
        self,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        seed_factory: Callable[[], int] = lambda: secrets.randbits(63),
    ) -> None:
        self._sleep = sleep
        self._monotonic = monotonic
        self._seed_factory = seed_factory

    async def run(
        self,
        websocket: WebSocket,
        behavior_id: int,
        club_1: list[StarterData],
        club_2: list[StarterData],
    ) -> None:
        """Juega la prueba y la transmite. Al terminar cierra con 1000 testEnd.

        Si el cliente se va, el endpoint cancela esta tarea: la prueba termina ahí.
        """
        try:
            seed = self._seed_factory()
            logger.info("Prueba del behavior %s arranca con seed=%s", behavior_id, seed)
            session = await run_in_threadpool(build_test_session, club_1, club_2, seed)
            await self._play(websocket, session)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falló la prueba del behavior %s", behavior_id)
            try:
                await websocket.close(code=ERROR_CODE, reason=ERROR_REASON)
            except Exception:
                pass  # el cliente ya se había ido

    async def _play(self, websocket: WebSocket, session: MatchSession) -> None:
        start = self._monotonic()
        while True:
            result = await run_in_threadpool(session.advance)
            payload = build_test_tick_payload(result)
            await websocket.send_text(json.dumps(payload, separators=(",", ":")))
            if result.phase is Phase.FINISHED:
                await websocket.close(code=END_CODE, reason=END_REASON)
                return
            # Agenda absoluta, como en el partido: el tick n sale en start + n * 50 ms.
            next_at = start + (result.tick + 1) * C.SECONDS_PER_TICK
            await self._sleep(max(0.0, next_at - self._monotonic()))
