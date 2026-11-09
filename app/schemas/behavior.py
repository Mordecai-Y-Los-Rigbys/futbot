from typing import Literal

from pydantic import Field

from app.helpers.ids import MAX_ID
from app.schemas.base import CamelModel


class BehaviorSummary(CamelModel):
    """Solo id y nombre. El código no se expone acá (ver GET /behaviors/{id})."""

    id: int
    name: str


class BehaviorPage(CamelModel):
    items: list[BehaviorSummary]
    page: int
    page_size: int
    total: int


class BehaviorDetail(CamelModel):
    id: int
    name: str
    code: str


class BehaviorTestConnectionResponse(CamelModel):
    token_ws: str


class BehaviorTestMember(CamelModel):
    player_id: int = Field(ge=1, le=MAX_ID)
    club: Literal["club1", "club2"]
    role: Literal["forward", "midfield", "defense"]
    behavior_id: int = Field(ge=1, le=MAX_ID)


class BehaviorTestRequest(CamelModel):
    """Solo documenta el body: lo valida parse_behavior_test."""

    members: list[BehaviorTestMember] = Field(min_length=6, max_length=6)


def behavior_test_request_schema() -> dict:
    # Inline y sin $defs: FastAPI no registra este modelo en components.
    schema = BehaviorTestRequest.model_json_schema(mode="serialization")
    member = schema.pop("$defs")["BehaviorTestMember"]
    schema["properties"]["members"]["items"] = member
    return schema
