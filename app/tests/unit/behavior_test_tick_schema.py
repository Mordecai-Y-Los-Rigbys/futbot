"""Schema Pydantic del mensaje `testTick` (`TestTickPayload` del AsyncAPI).

Es SOLO para tests, como `tick_schema.py`: valida contra el contrato lo que el
servidor realmente envía, con tipos estrictos y claves exactas. Se importa el
módulo (no las clases): pytest juntaría como tests las clases que empiezan con
"Test".
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from app.tests.unit.tick_schema import Position, TickPlayerPosition


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class TestStartEvent(_Strict):
    type: Literal["testStart"]
    countdownSeconds: int


class TestGoalEvent(_Strict):
    type: Literal["goal"]
    club: Literal["club1", "club2"]


class TestEndEvent(_Strict):
    type: Literal["testEnd"]
    reason: Literal["timeLimit"]


TestTickEvent = Annotated[
    Union[TestStartEvent, TestGoalEvent, TestEndEvent], Field(discriminator="type")
]


class TestTickPayload(_Strict):
    type: Literal["testTick"]
    players: list[TickPlayerPosition] = Field(min_length=6, max_length=6)
    ballPosition: Position
    score1: int = Field(ge=0)
    score2: int = Field(ge=0)
    elapsedTime: int
    phase: Literal["countdown", "playing", "finished"]
    event: Optional[TestTickEvent]
