"""Schema Pydantic del mensaje `tick` (`TickPayload` del AsyncAPI).

Es SOLO para tests: no se usa al emitir (los ticks salen a 20 por segundo y
se arman como dict). Sirve para validar contra el contrato lo que el servidor
realmente envía: tipos estrictos, claves exactas y coherencia entre `phase` y
`event`.

Los valores de la cancha están escritos a mano a propósito (no se importan de
`app.simulation.constants`): así el test compara el código contra el contrato
y no contra sí mismo.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator

FIELD_LENGTH = 100.0  # x de 0 a 100 (AsyncAPI, schema Position)
FIELD_WIDTH = 60.0  # y de 0 a 60
GOAL_MARGIN = 5.0  # "apenas" fuera de [0, 100] cuando la pelota está dentro del arco


class _Strict(BaseModel):
    # Sin claves de más y sin conversiones ("3" no es 3, True no es 1).
    model_config = ConfigDict(extra="forbid", strict=True)


class Position(_Strict):
    x: float
    y: float


class TickPlayerPosition(_Strict):
    playerId: int
    position: Position


class GoalEvent(_Strict):
    type: Literal["goal"]
    scoringClub: str


class PeriodStartEvent(_Strict):
    type: Literal["periodStart"]
    periodNumber: int = Field(ge=1, le=4)
    countdownSeconds: int


class PauseEvent(_Strict):
    type: Literal["pause"]
    reason: Literal["hydration", "halftime"]
    durationSeconds: int = Field(ge=1)


Club = Literal["club1", "club2"]


class PenaltyKickRecord(_Strict):
    club: Club
    kickerId: int
    kickerName: str = Field(max_length=20)
    round: int = Field(ge=1, le=5)
    scored: bool


class PenaltyShootout(_Strict):
    score1: int = Field(ge=0, le=5)
    score2: int = Field(ge=0, le=5)
    winner: Club
    kicks: list[PenaltyKickRecord]


class PenaltyCurrent(_Strict):
    club: Club
    kickerId: int
    kickerName: str = Field(max_length=20)
    defenderId: int
    defenderName: str = Field(max_length=20)


class PenaltiesStartEvent(_Strict):
    type: Literal["penaltiesStart"]


class PenaltyKickEvent(PenaltyKickRecord):
    type: Literal["penaltyKick"]


class MatchResult(_Strict):
    score1: int
    score2: int
    penalties: Optional[PenaltyShootout]


class MatchEndEvent(_Strict):
    type: Literal["matchEnd"]
    result: MatchResult


TickEvent = Annotated[
    Union[
        GoalEvent,
        PeriodStartEvent,
        PauseEvent,
        PenaltiesStartEvent,
        PenaltyKickEvent,
        MatchEndEvent,
    ],
    Field(discriminator="type"),
]


class TickPayload(_Strict):
    type: Literal["tick"]
    players: list[TickPlayerPosition]
    ballPosition: Position
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
    penaltyScore1: int = Field(ge=0)
    penaltyScore2: int = Field(ge=0)
    penaltyKicks: list[PenaltyKickRecord]
    penaltyCurrent: Optional[PenaltyCurrent]
    penaltyCountdownSeconds: Optional[int] = Field(ge=1, le=3)
    penaltyRemainingSeconds: Optional[int] = Field(ge=0, le=8)
    elapsedTime: int = Field(ge=0)
    pauseRemainingSeconds: Optional[int] = Field(ge=0)
    pausesLeft: int = Field(ge=0, le=3)  # obligatorio en todos los ticks
    phase: Literal["countdown", "playing", "paused", "penalties", "finished"]
    event: Optional[TickEvent]  # requerido: la clave siempre viaja, aunque sea null

    @model_validator(mode="after")
    def _coherent(self) -> "TickPayload":
        event = self.event

        # `finished` coincide con `matchEnd`, en las dos direcciones.
        if (self.phase == "finished") != isinstance(event, MatchEndEvent):
            raise ValueError("`phase: finished` y el evento `matchEnd` deben ir juntos")
        if isinstance(event, MatchEndEvent):
            if (event.result.score1, event.result.score2) != (self.score1, self.score2):
                raise ValueError("`result` de matchEnd no coincide con score1/score2")
        if isinstance(event, PeriodStartEvent) and self.phase != "countdown":
            raise ValueError("`periodStart` solo viaja con `phase: countdown`")
        if isinstance(event, GoalEvent) and self.phase != "playing":
            raise ValueError("`goal` solo viaja con `phase: playing`")
        if isinstance(event, PauseEvent) and self.phase != "paused":
            raise ValueError("`pause` solo viaja con `phase: paused`")
        if isinstance(event, (PenaltiesStartEvent, PenaltyKickEvent)) and self.phase != "penalties":
            raise ValueError("los eventos de la tanda solo viajan con `phase: penalties`")

        # El penal en curso y su tiempo viajan solo en la tanda.
        in_penalties = self.phase == "penalties"
        if in_penalties != (self.penaltyCurrent is not None):
            raise ValueError("`penaltyCurrent` viaja solo con `phase: penalties`")
        if in_penalties != (self.penaltyRemainingSeconds is not None):
            raise ValueError("`penaltyRemainingSeconds` viaja solo con `phase: penalties`")
        if not in_penalties and self.penaltyCountdownSeconds is not None:
            raise ValueError("`penaltyCountdownSeconds` viaja solo con `phase: penalties`")

        # El marcador de la tanda coincide con los penales convertidos.
        for club, score in (("club1", self.penaltyScore1), ("club2", self.penaltyScore2)):
            if score != sum(k.scored for k in self.penaltyKicks if k.club == club):
                raise ValueError("el marcador de la tanda no coincide con `penaltyKicks`")

        # `pauseRemainingSeconds` es un número en `paused` y null en el resto.
        if (self.phase == "paused") != (self.pauseRemainingSeconds is not None):
            raise ValueError("`pauseRemainingSeconds` viaja solo con `phase: paused`")

        # Cancha. La pelota puede estar dentro del arco (x apenas fuera de
        # [0, 100]) en el tick de un gol, y también en el último tick si el
        # gol cae ahí: matchEnd tiene prioridad sobre goal. En una pausa la
        # pelota siempre está dentro de la cancha.
        ball_in_goal = isinstance(event, (GoalEvent, PenaltyKickEvent, MatchEndEvent))
        margin = GOAL_MARGIN if ball_in_goal else 0.0
        ball = self.ballPosition
        if not -margin <= ball.x <= FIELD_LENGTH + margin:
            raise ValueError(f"ballPosition.x fuera de la cancha: {ball.x}")
        if not 0.0 <= ball.y <= FIELD_WIDTH:
            raise ValueError(f"ballPosition.y fuera de la cancha: {ball.y}")
        for p in self.players:
            if not (0.0 <= p.position.x <= FIELD_LENGTH and 0.0 <= p.position.y <= FIELD_WIDTH):
                raise ValueError(f"el jugador {p.playerId} está fuera de la cancha")
        return self
