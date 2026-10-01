from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class LeagueCreator(CamelModel):
    id: int
    username: str
    name: str


class LeagueSummary(CamelModel):
    id: int
    name: str
    creator: LeagueCreator
    status: Literal["preparation", "started", "cancelled", "finished"]
    participants_count: int
    max_participants: int
    private: bool
    created_at: datetime

    @field_serializer("created_at")
    def _serialize_created_at(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class LeaguePage(CamelModel):
    items: list[LeagueSummary]
    page: int
    page_size: int
    total: int