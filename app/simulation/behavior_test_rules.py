"""Reglas de la prueba de un comportamiento de jugador.

La prueba no es un partido: hay un único jugador, en el lugar de club1, sin
compañeros ni rival, que ataca el arco de x = FIELD_LENGTH. Usa las mismas
reglas que un partido (MatchSession), con un solo período y sin pausas:

    countdown (3 s) | playing (60 s, el último tick es `finished`)

- countdown: el primer tick trae `testStart`. El jugador no se mueve.
- playing: el behavior y la física corren igual que en un partido. Tras un gol,
  en el tick siguiente el jugador y la pelota ya están en sus posiciones iniciales.
- finished: el último tick trae `testEnd`, aunque coincida con un gol (que
  igual suma en `goals`).

Un gol en el arco propio (x = 0) no suma ni trae evento, pero también reacomoda:
la pelota no puede quedar dentro del arco.

No hay DT: la sesión solo recibe el behavior del jugador. Y, como en el
partido, las reglas no esperan entre ticks: el ritmo lo pone la transmisión.
"""

import enum
from dataclasses import dataclass

from app.domain.team_member import MemberRole
from app.simulation import constants as C
from app.simulation.behaviors.sandbox import CompiledBehavior
from app.simulation.match_rules import Event, MatchSession, Phase
from app.simulation.physics import PlayerSetup, single_player_state
from app.simulation.state import MatchState, Stats, Team

# El jugador de la prueba no es uno del usuario: un delantero con las cinco stats iguales.
TEST_PLAYER = PlayerSetup(
    player_id=0,
    role=MemberRole.forward,
    stats=Stats(
        power=C.BEHAVIOR_TEST_STAT,
        agility=C.BEHAVIOR_TEST_STAT,
        control=C.BEHAVIOR_TEST_STAT,
        strength=C.BEHAVIOR_TEST_STAT,
        speed=C.BEHAVIOR_TEST_STAT,
    ),
)
TEST_PLAYER_KEY = (Team.HOME, TEST_PLAYER.role.number)


class BehaviorTestEvent(str, enum.Enum):
    TEST_START = "testStart"
    GOAL = "goal"
    TEST_END = "testEnd"


@dataclass(frozen=True)
class BehaviorTestTick:
    tick: int  # número de secuencia, desde 0
    phase: Phase  # countdown, playing o finished
    event: BehaviorTestEvent | None
    state: MatchState
    goals: int
    elapsed: float  # segundos de juego


class BehaviorTestSession:
    """Una prueba en curso. `advance()` produce el siguiente tick."""

    def __init__(
        self,
        behavior: CompiledBehavior,
        duration_seconds: float = C.BEHAVIOR_TEST_DURATION_SECONDS,
        countdown_seconds: float = C.BEHAVIOR_TEST_COUNTDOWN_SECONDS,
    ) -> None:
        self._match = MatchSession(
            single_player_state(TEST_PLAYER),
            {TEST_PLAYER_KEY: behavior},
            duration_seconds,
            countdown_seconds,
            periods=1,
            pause_seconds=0,
        )

    @property
    def finished(self) -> bool:
        return self._match.finished

    def advance(self) -> BehaviorTestTick:
        result = self._match.advance()
        return BehaviorTestTick(
            tick=result.tick,
            phase=result.phase,
            event=_test_event(result.event, result.scoring_team),
            state=result.state,
            goals=result.score_1,
            elapsed=result.elapsed,
        )


def _test_event(event: Event | None, scoring_team: Team | None) -> BehaviorTestEvent | None:
    if event is Event.PERIOD_START:
        return BehaviorTestEvent.TEST_START
    if event is Event.MATCH_END:
        return BehaviorTestEvent.TEST_END
    if event is Event.GOAL and scoring_team is Team.HOME:
        return BehaviorTestEvent.GOAL
    return None  # incluye el gol en el arco propio
