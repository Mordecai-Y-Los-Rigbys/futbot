from datetime import datetime, timezone
from typing import Literal

from pydantic import field_serializer

from app.schemas.base import CamelModel


class MatchClub(CamelModel):
    id: int
    username: str
    name: str  # el spec expone el club_name como `name`


class MatchResponse(CamelModel):
    """Schema `Match` del contrato."""

    id: int
    league_id: int | None = None
    name: str | None = None
    status: Literal["scheduled", "started", "finished", "cancelled"]
    club1: MatchClub
    club2: MatchClub | None = None
    scheduled_at: datetime | None = None
    created_at: datetime
    result: dict | None = None

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class MatchPage(CamelModel):
    items: list[MatchResponse]
    page: int
    page_size: int
    total: int
