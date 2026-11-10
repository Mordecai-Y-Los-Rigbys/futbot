from typing import Literal

from app.schemas.base import CamelModel


class LineupPlayer(CamelModel):
    player_id: int
    name: str
    role: Literal["forward", "midfield", "defense"]


class MatchLineups(CamelModel):
    club1: list[LineupPlayer]
    club2: list[LineupPlayer] | None
