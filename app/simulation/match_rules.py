"""Reglas del partido alrededor de la física: arranque, goles, pausas, reacomodo y fin.

Todo es CPU puro y sin I/O: lo usan igual el loop en tiempo real (MatchRunner)
y el simulador sin espera (simulate_match).

Línea de tiempo (a 20 ticks/s), con P períodos:

    countdown(1) playing(1) | pausa(1) countdown(2) playing(2) | ... | countdown(P) playing(P)

- countdown: el primer tick trae `periodStart`. Nadie se mueve.
- playing: los behaviors y la física corren. El último tick del último
  período es `finished` con `matchEnd`.
- paused: el primer tick trae `pause`. Todo congelado y el reloj detenido.

Al empezar cada countdown posterior a una pausa, el partido se reinicia como
un saque normal (posiciones iniciales, pelota quieta, cooldowns en cero), haya
habido gol antes de la pausa o no.

Si el último tick de un período es un gol, el reacomodo del gol se aplica en
el primer tick de la pausa: la pelota nunca queda dentro del arco en `paused`.
"""

import enum
import math
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
    PAUSED = "paused"
    FINISHED = "finished"


class Event(str, enum.Enum):
    PERIOD_START = "periodStart"
    GOAL = "goal"
    PAUSE = "pause"
    MATCH_END = "matchEnd"


class PauseReason(str, enum.Enum):
    HYDRATION = "hydration"
    HALFTIME = "halftime"


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
    elapsed: float  # segundos de juego (no avanza en la cuenta regresiva ni en las pausas)
    remaining: float
    period: int  # en un countdown, el período que arranca; en una pausa, el que terminó
    scoring_team: Team | None = None  # quién anotó, solo si event == GOAL
    pause_reason: PauseReason | None = None  # solo en ticks `paused`
    pause_remaining_seconds: int | None = None  # solo en ticks `paused`
    pause_duration_seconds: int | None = None  # solo en ticks `paused`


@dataclass(frozen=True)
class _Segment:
    """Tramo consecutivo de ticks de una misma fase."""

    phase: Phase
    ticks: int
    period: int
    restart: bool = False  # su primer tick reinicia el partido (saque normal)


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
        pause_seconds: float = C.PAUSE_SECONDS,
    ) -> None:
        self._state = state
        self._behaviors = behaviors
        self._countdown_ticks = round(countdown_seconds * C.TICKS_PER_SECOND)
        self._pause_ticks = round(pause_seconds * C.TICKS_PER_SECOND)
        self._pause_seconds = pause_seconds
        self._play_ticks = round(duration_seconds * C.TICKS_PER_SECOND)
        if periods < 1 or self._play_ticks < periods:
            raise ValueError("el partido tiene que durar al menos un tick por período")
        self._periods = periods
        self._segments = self._build_segments()
        self._seg_index = 0
        self._offset = 0  # posición dentro del segmento actual
        self._seq = 0
        self._played = 0  # ticks de juego efectivo ya jugados
        self._score_1 = 0
        self._score_2 = 0
        self._pending_reset = False
        self._finished = False

    def _build_segments(self) -> list[_Segment]:
        base = self._play_ticks // self._periods
        segments: list[_Segment] = []
        for period in range(1, self._periods + 1):
            if period > 1 and self._pause_ticks > 0:
                segments.append(_Segment(Phase.PAUSED, self._pause_ticks, period - 1))
            restart = period > 1  # lo reinicia el primer tramo no-pausa del período
            if self._countdown_ticks > 0:
                segments.append(_Segment(Phase.COUNTDOWN, self._countdown_ticks, period, restart))
                restart = False
            # el último período absorbe el resto de la división
            ticks = base if period < self._periods else self._play_ticks - base * (period - 1)
            segments.append(_Segment(Phase.PLAYING, ticks, period, restart))
        return segments

    @property
    def finished(self) -> bool:
        return self._finished

    @property
    def total_ticks(self) -> int:
        return sum(s.ticks for s in self._segments)

    @property
    def pause_starts(self) -> list[float]:
        """Segundos de juego en los que empieza cada pausa."""
        starts, played = [], 0
        for segment in self._segments:
            if segment.phase is Phase.PLAYING:
                played += segment.ticks
            elif segment.phase is Phase.PAUSED:
                starts.append(played / C.TICKS_PER_SECOND)
        return starts

    def advance(self) -> TickResult:
        if self._finished:
            raise RuntimeError("el partido ya terminó")
        seq = self._seq
        self._seq += 1
        segment = self._segments[self._seg_index]
        offset = self._offset
        self._offset += 1
        if self._offset == segment.ticks:
            self._seg_index += 1
            self._offset = 0

        if offset == 0 and segment.restart:
            self._restart()

        if segment.phase is Phase.PAUSED:
            return self._pause_tick(seq, segment, offset)
        if segment.phase is Phase.COUNTDOWN:
            event = Event.PERIOD_START if offset == 0 else None
            return self._result(seq, segment, event)
        return self._play(seq, segment)

    def _restart(self) -> None:
        """Saque normal: posiciones iniciales, pelota libre y quieta, sin
        movimientos previos y cooldowns en cero. También descarta un reacomodo
        por gol pendiente."""
        self._state = reset_positions(self._state)
        self._pending_reset = False

    def _pause_tick(self, seq: int, segment: _Segment, offset: int) -> TickResult:
        if offset == 0 and self._pending_reset:
            # Gol en el último tick del período: el tick siguiente al gol (el primero
            # de la pausa) ya tiene todo en posiciones iniciales (contrato `goal`).
            self._reset_after_goal()
        # Congelado: no corren behaviors ni física, y el estado no cambia.
        ticks_left = segment.ticks - offset
        remaining = math.ceil(ticks_left / C.TICKS_PER_SECOND)  # de N a 0
        event = Event.PAUSE if offset == 0 else None
        return self._result(
            seq,
            segment,
            event,
            pause_reason=self._pause_reason(segment.period),
            pause_remaining=remaining,
        )

    def _pause_reason(self, period: int) -> PauseReason:
        if period == self._periods // 2:
            return PauseReason.HALFTIME
        return PauseReason.HYDRATION

    def _play(self, seq: int, segment: _Segment) -> TickResult:
        play_index = self._played
        self._played += 1
        event: Event | None = None
        scorer: Team | None = None
        if self._pending_reset:
            self._reset_after_goal()
        else:
            scorer = self._play_tick(play_index, segment.period)
        if scorer is not None:
            event = Event.GOAL

        phase = Phase.PLAYING
        if self._played == self._play_ticks:
            # matchEnd tiene prioridad: si el último tick fue gol, igual suma al marcador.
            phase, event = Phase.FINISHED, Event.MATCH_END
            self._finished = True
        return self._result(seq, segment, event, phase=phase, scorer=scorer)

    def _reset_after_goal(self) -> None:
        """Tick siguiente al gol: todos en sus posiciones, pelota libre en el
        centro, cooldowns reiniciados. El reloj sigue corriendo."""
        self._state = reset_positions(self._state)
        self._state.tick += 1
        self._pending_reset = False

    def _play_tick(self, play_index: int, period: int) -> Team | None:
        """Corre los behaviors y la física de un tick. Devuelve quién hizo gol, o None."""
        clock = MatchClock(
            elapsed=play_index / C.TICKS_PER_SECOND,
            remaining=(self._play_ticks - play_index) / C.TICKS_PER_SECOND,
            period=period,
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

    def _result(
        self,
        seq: int,
        segment: _Segment,
        event: Event | None,
        phase: Phase | None = None,
        scorer: Team | None = None,
        pause_reason: PauseReason | None = None,
        pause_remaining: int | None = None,
    ) -> TickResult:
        elapsed = self._played / C.TICKS_PER_SECOND
        paused = segment.phase is Phase.PAUSED
        return TickResult(
            tick=seq,
            phase=phase or segment.phase,
            event=event,
            state=self._state,
            score_1=self._score_1,
            score_2=self._score_2,
            elapsed=elapsed,
            remaining=self._play_ticks / C.TICKS_PER_SECOND - elapsed,
            period=segment.period,
            scoring_team=scorer,
            pause_reason=pause_reason,
            pause_remaining_seconds=pause_remaining,
            pause_duration_seconds=round(self._pause_seconds) if paused else None,
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
    periods: int = C.PERIODS,
    pause_seconds: float = C.PAUSE_SECONDS,
) -> MatchSession:
    """Crea el estado inicial (la semilla entra acá) y la sesión del partido."""
    state = create_initial_state(team_1.players, team_2.players, seed)
    return MatchSession(
        state,
        behaviors_by_key(team_1, team_2),
        duration_seconds,
        countdown_seconds,
        periods,
        pause_seconds,
    )