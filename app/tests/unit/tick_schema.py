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


class MatchResult(_Strict):
    score1: int
    score2: int


class MatchEndEvent(_Strict):
    type: Literal["matchEnd"]
    result: MatchResult


TickEvent = Annotated[
    Union[GoalEvent, PeriodStartEvent, PauseEvent, MatchEndEvent],
    Field(discriminator="type"),
]


class TickPayload(_Strict):
    type: Literal["tick"]
    players: list[TickPlayerPosition]
    ballPosition: Position
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
    elapsedTime: int = Field(ge=0)
    phase: Literal["countdown", "playing", "paused", "finished"]
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

        # Cancha. La pelota puede estar dentro del arco (x apenas fuera de
        # [0, 100]) en el tick de un gol, y también en el último tick si el
        # gol cae ahí: matchEnd tiene prioridad sobre goal.
        ball_in_goal = isinstance(event, (GoalEvent, MatchEndEvent))
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