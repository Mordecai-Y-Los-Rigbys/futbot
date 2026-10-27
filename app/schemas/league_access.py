from typing import Literal

from pydantic import BaseModel


class LeagueAccessFieldError(BaseModel):
    field: Literal["password"]
    reason: Literal["required", "invalidType"]


class UnlockLeagueBadRequest(BaseModel):
    code: Literal["invalidFields"]
    message: str
    errors: list[LeagueAccessFieldError]


class UnlockLeagueForbidden(BaseModel):
    code: Literal["invalidLeaguePassword"]
    message: str


class LeagueAccessForbidden(BaseModel):
    code: Literal["leagueAccessRequired"]
    message: str
