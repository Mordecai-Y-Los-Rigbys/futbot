"""Reglas del partido alrededor de la física: arranque, goles, reacomodo y fin.

Todo es CPU puro y sin I/O: lo usan igual el loop en tiempo real (MatchRunner)
y el simulador sin espera (simulate_match).

Línea de tiempo (a 20 ticks/s):
    ticks 0 .. CT-1      fase countdown (CT = cuenta regresiva en ticks).
                         El tick 0 trae el evento periodStart. Nadie se mueve.
    ticks CT .. CT+N-1   fase playing (N = ticks de juego).
    último tick          fase finished con el evento matchEnd.
"""

import enum
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.simulation import constants as C
from app.simulation.behaviors.primitives import MatchClock
from app.simulation.behaviors.executor import run_behaviors
from app.simulation.behaviors.sandbox import CompiledBehavior
from app.simulation.physics import (
    PlayerSetup,
    create_initial_state,
    reset_positions,
    step,
)
from app.simulation.state import Goal, MatchState, PlayerKey, Team
from app.domain.team_member import MemberRole


class Phase(str, enum.Enum):
    COUNTDOWN = "countdown"
    PLAYING = "playing"
    FINISHED = "finished"


class Event(str, enum.Enum):
    PERIOD_START = "periodStart"
    GOAL = "goal"
    MATCH_END = "matchEnd"


@dataclass(frozen=True)
class TeamSetup:
    """Los tres titulares de un club y el comportamiento de cada rol."""

    players: Sequence[PlayerSetup]
    behaviors: Mapping[MemberRole, CompiledBehavior]


@dataclass(frozen=True)
class TickResult:
    tick: int  # número de secuencia, desde 0
    phase: Phase
    event: Event | None
    state: MatchState
    score_1: int
    score_2: int
    elapsed: float  # segundos de juego (no avanza en la cuenta regresiva)
    remaining: float
    period: int
    scoring_team: Team | None = None  # quién anotó, solo si event == GOAL


class MatchSession:
    """Estado de un partido en curso. `advance()` produce el siguiente tick.

    No es thread-safe: un partido se avanza de a un tick por vez (el runner
    espera cada tick antes de pedir el siguiente).
    """

    def __init__(
        self,
        state: MatchState,
        behaviors: Mapping[PlayerKey, CompiledBehavior],
        duration_seconds: float,
        countdown_seconds: float = C.COUNTDOWN_SECONDS,
        periods: int = C.PERIODS,
    ) -> None:
        self._state = state
        self._behaviors = behaviors
        self._countdown_ticks = round(countdown_seconds * C.TICKS_PER_SECOND)
        self._play_ticks = round(duration_seconds * C.TICKS_PER_SECOND)
        if self._play_ticks < 1:
            raise ValueError("el partido tiene que durar al menos un tick")
        self._periods = periods
        self._period_ticks = max(1, self._play_ticks // periods)
        self._seq = 0
        self._score_1 = 0
        self._score_2 = 0
        self._pending_reset = False
        self._finished = False

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def total_ticks(self) -> int:
        return self._countdown_ticks + self._play_ticks

    def advance(self) -> TickResult:
        if self._finished:
            raise RuntimeError("el partido ya terminó")
        seq = self._seq
        self._seq += 1
        event: Event | None = Event.PERIOD_START if seq == 0 else None

        if seq < self._countdown_ticks:
            return self._result(seq, Phase.COUNTDOWN, event, played=0)

        play_index = seq - self._countdown_ticks
        scorer: Team | None = None
        if self._pending_reset:
            self._reset_after_goal()
        else:
            scorer = self._play_tick(play_index)
        if scorer is not None:
            event = Event.GOAL

        phase = Phase.PLAYING
        if play_index == self._play_ticks - 1:
            # matchEnd tiene prioridad: si el último tick fue gol, igual suma al marcador.
            phase, event = Phase.FINISHED, Event.MATCH_END
            self._finished = True
        return self._result(seq, phase, event, played=play_index + 1, scorer=scorer)

    def _reset_after_goal(self) -> None:
        """Tick siguiente al gol: todos en sus posiciones, pelota libre en el
        centro, cooldowns reiniciados. El reloj sigue corriendo."""
        self._state = reset_positions(self._state)
        self._state.tick += 1
        self._pending_reset = False

    def _play_tick(self, play_index: int) -> Team | None:
        """Corre los behaviors y la física de un tick. Devuelve quién hizo gol, o None."""
        clock = MatchClock(
            elapsed=play_index / C.TICKS_PER_SECOND,
            remaining=(self._play_ticks - play_index) / C.TICKS_PER_SECOND,
            period=self._period(play_index),
        )
        actions = run_behaviors(self._state, self._behaviors, clock)
        result = step(self._state, actions)
        self._state = result.state
        scorer = None
        for result_event in result.events:
            if isinstance(result_event, Goal):
                scorer = result_event.scoring_team
                self._register_goal(scorer)
        return scorer

    def _register_goal(self, scorer: Team) -> None:
        if scorer is Team.HOME:
            self._score_1 += 1
        else:
            self._score_2 += 1
        self._pending_reset = True

    def _period(self, play_index: int) -> int:
        return min(self._periods, play_index // self._period_ticks + 1)

    def _result(
        self,
        seq: int,
        phase: Phase,
        event: Event | None,
        played: int,
        scorer: Team | None = None,
    ) -> TickResult:
        elapsed = played / C.TICKS_PER_SECOND
        return TickResult(
            tick=seq,
            phase=phase,
            event=event,
            state=self._state,
            score_1=self._score_1,
            score_2=self._score_2,
            elapsed=elapsed,
            remaining=self._play_ticks / C.TICKS_PER_SECOND - elapsed,
            period=self._period(max(0, played - 1)),
            scoring_team=scorer,
        )


def behaviors_by_key(team_1: TeamSetup, team_2: TeamSetup) -> dict[PlayerKey, CompiledBehavior]:
    out: dict[PlayerKey, CompiledBehavior] = {}
    for team, setup in ((Team.HOME, team_1), (Team.AWAY, team_2)):
        for role, behavior in setup.behaviors.items():
            out[(team, role.number)] = behavior
    return out


def build_session(
    team_1: TeamSetup,
    team_2: TeamSetup,
    duration_seconds: float,
    seed: int,
    countdown_seconds: float = C.COUNTDOWN_SECONDS,
) -> MatchSession:
    """Crea el estado inicial (la semilla entra acá) y la sesión del partido."""
    state = create_initial_state(team_1.players, team_2.players, seed)
    return MatchSession(
        state, behaviors_by_key(team_1, team_2), duration_seconds, countdown_seconds
    )
