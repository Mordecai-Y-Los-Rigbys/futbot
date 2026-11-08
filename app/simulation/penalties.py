"""Tanda de penales (penal australiano) de un partido de liga sin empates.

Cada penal es un duelo entre un pateador y el defensor rival. Los clubes se
alternan empezando por club1, y cada club patea con sus tres titulares en
ciclo (PENALTY_KICKER_ORDER). Cada penal tiene una cuenta previa, con todo
quieto, y después el pateador tiene PENALTY_SECONDS de juego para convertir.

Línea de tiempo de un penal (a 20 ticks/s):

    cuenta previa (3 s) | juego (hasta 8 s, o hasta que termina el penal)

Un penal termina de tres formas:

    - la pelota entra en el arco rival: gol (`scored: true`);
    - se agotan los segundos del penal: errado (`scored: false`);
    - la pelota entra en el arco del propio pateador: errado
      (`scored: false`), y no es gol del rival.

En el tick siguiente empieza la cuenta previa del próximo penal, con los
jugadores nuevos.

Todo es sin I/O, como el resto de las reglas del partido.
"""

import math
import random
from collections.abc import Mapping
from dataclasses import dataclass

from app.domain.team_member import MemberRole
from app.simulation import constants as C
from app.simulation.behaviors.executor import run_behaviors
from app.simulation.behaviors.primitives import MatchClock
from app.simulation.behaviors.sandbox import CompiledBehavior
from app.simulation.physics import penalty_state, step
from app.simulation.state import Goal, MatchState, PlayerKey, Team


@dataclass(frozen=True)
class PenaltyKick:
    """Un penal ya ejecutado."""

    team: Team
    kicker_id: int
    kicker_name: str
    round: int
    scored: bool


@dataclass(frozen=True)
class PenaltyCurrent:
    """Penal en curso: quién patea y quién defiende."""

    team: Team
    kicker_id: int
    kicker_name: str
    defender_id: int
    defender_name: str


@dataclass(frozen=True)
class ShootoutStatus:
    """Estado completo de la tanda en un tick."""

    kicks: tuple[PenaltyKick, ...]
    score_1: int
    score_2: int
    current: PenaltyCurrent | None  # None cuando la tanda terminó
    countdown_seconds: int | None  # de 3 a 1 en la cuenta previa; None con la pelota en juego
    remaining_seconds: int | None  # de 8 a 0; None cuando la tanda terminó
    winner: Team | None


@dataclass(frozen=True)
class PenaltyTick:
    state: MatchState
    status: ShootoutStatus
    first: bool  # primer tick de la tanda
    kick: PenaltyKick | None  # el penal que terminó en este tick
    finished: bool


class Shootout:
    """Tanda en curso. `advance()` produce el siguiente tick."""

    def __init__(
        self,
        final_state: MatchState,
        behaviors: Mapping[PlayerKey, CompiledBehavior],
        elapsed: float,
        period: int,
    ) -> None:
        self._final_state = final_state  # acá vienen los jugadores que patean
        self._behaviors = behaviors
        self._elapsed = elapsed
        self._period = period
        self._rng = random.Random(final_state.seed)
        self._countdown_ticks = C.PENALTY_COUNTDOWN_SECONDS * C.TICKS_PER_SECOND
        self._kick_ticks = C.PENALTY_SECONDS * C.TICKS_PER_SECOND
        self._kicks: list[PenaltyKick] = []
        self._scores = {Team.HOME: 0, Team.AWAY: 0}
        self._taken = {Team.HOME: 0, Team.AWAY: 0}
        self._started = False
        self._winner: Team | None = None
        # Datos del penal actual, armados al empezar cada penal
        self._state: MatchState
        self._current: PenaltyCurrent
        self._offset = 0  # ticks jugados del penal
        self._begin_kick()

    def advance(self) -> PenaltyTick:
        first = not self._started
        self._started = True
        offset = self._offset
        self._offset += 1

        if offset < self._countdown_ticks:
            ticks_left = self._countdown_ticks - offset
            countdown = math.ceil(ticks_left / C.TICKS_PER_SECOND)  # de 3 a 1
            return self._tick(first, countdown, C.PENALTY_SECONDS)

        played = offset - self._countdown_ticks + 1
        scored = self._play_tick()
        remaining = math.ceil((self._kick_ticks - played) / C.TICKS_PER_SECOND)  # de 8 a 0

        if scored is None and played < self._kick_ticks:
            return self._tick(first, None, remaining)

        kick = self._register(scored is True)
        finished = self._decided()
        if finished:
            self._winner = self._pick_winner()

        tick = self._tick(first, None, remaining, kick, finished)
        if not finished:
            self._begin_kick()  # El tick siguiente ya es la cuenta previa del próximo

        return tick

    def _begin_kick(self) -> None:
        team = Team.HOME if len(self._kicks) % 2 == 0 else Team.AWAY
        role = C.PENALTY_KICKER_ORDER[self._taken[team] % len(C.PENALTY_KICKER_ORDER)]
        kicker_key = (team, role.number)
        defender_key = (team.opponent, MemberRole.defense.number)
        self._state = penalty_state(self._final_state, kicker_key, defender_key)
        self._offset = 0
        kicker = self._state.player(kicker_key)
        defender = self._state.player(defender_key)
        self._current = PenaltyCurrent(
            team, kicker.player_id, kicker.name, defender.player_id, defender.name
        )

    def _play_tick(self) -> bool | None:
        """Corre un tick del penal. True si el pateador convirtió, False si la
        pelota entró en su propio arco, None si no hubo gol."""

        # El reloj del partido está parado: no queda tiempo de juego y sigue el último período.
        clock = MatchClock(elapsed=self._elapsed, remaining=0.0, period=self._period)
        actions = run_behaviors(self._state, self._behaviors, clock)
        result = step(self._state, actions)
        self._state = result.state
        for event in result.events:
            if isinstance(event, Goal):
                return event.scoring_team is self._current.team
        return None

    def _register(self, scored: bool) -> PenaltyKick:
        team = self._current.team
        self._taken[team] += 1
        if scored:
            self._scores[team] += 1

        kick = PenaltyKick(
            team, self._current.kicker_id, self._current.kicker_name, self._taken[team], scored
        )
        self._kicks.append(kick)
        return kick

    def _decided(self) -> bool:
        """True si ya no quedan penales o si un club ya no puede ser alcanzado."""
        left = {team: C.PENALTY_KICKS_PER_CLUB - taken for team, taken in self._taken.items()}
        home, away = self._scores[Team.HOME], self._scores[Team.AWAY]
        if home + left[Team.HOME] < away or away + left[Team.AWAY] < home:
            return True
        return left[Team.HOME] == 0 and left[Team.AWAY] == 0

    def _pick_winner(self) -> Team:
        home, away = self._scores[Team.HOME], self._scores[Team.AWAY]
        if home != away:
            return Team.HOME if home > away else Team.AWAY
        return Team.HOME if self._rng.random() < 0.5 else Team.AWAY  # sorteo 50/50

    def _tick(
        self,
        first: bool,
        countdown: int | None,
        remaining: int,
        kick: PenaltyKick | None = None,
        finished: bool = False,
    ) -> PenaltyTick:

        status = ShootoutStatus(
            kicks=tuple(self._kicks),
            score_1=self._scores[Team.HOME],
            score_2=self._scores[Team.AWAY],
            current=None if finished else self._current,
            countdown_seconds=countdown,
            remaining_seconds=None if finished else remaining,
            winner=self._winner,
        )
        return PenaltyTick(self._state, status, first, kick, finished)
